from datetime import date
from importlib import import_module
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, Client
from django.urls import reverse
from .ledger_scope import ensure_membership, member_ids
from .company_members import approve
from .models import (CompanyLedger, LedgerMembership, BusinessProfile, Voucher,
                     Counterparty, Account, OpeningBalanceBatch, YearEndClosing, VoucherQuota, ReceiptPhoto)


class CompanyLedgerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.a = User.objects.create_user('shared-a', is_staff=True)
        self.b = User.objects.create_user('shared-b', is_staff=True)
        self.other = User.objects.create_user('separate-user', is_staff=True)
        self.admin = User.objects.create_superuser('shared-admin', password='secret')
        for user, name in [(self.a, '공유업체'), (self.b, '공유업체'), (self.other, '다른업체')]:
            BusinessProfile.objects.create(user=user, company_name=name, business_number='123-45-67890')
        company = CompanyLedger.objects.create(name='공유업체', anchor=self.a)
        LedgerMembership.objects.create(user=self.a, company=company)
        LedgerMembership.objects.create(user=self.b, company=company)
        self.partner = Counterparty.objects.create(owner=self.a, name='공유거래처')
        self.voucher = Voucher.objects.create(owner=self.a, date=date(2025, 7, 1), kind='income', entry_type='sales',
                                              account_master_id='5001', settlement_account_id='1101', amount=1000,
                                              counterparty=self.partner, partner=self.partner.name)
        Voucher.objects.create(owner=self.b, date=date(2025, 7, 2), kind='income', entry_type='sales',
                               account_master_id='5001', settlement_account_id='1101', amount=2000)
        Voucher.objects.create(owner=self.other, date=date(2025, 7, 2), kind='income', entry_type='sales',
                               account_master_id='5001', settlement_account_id='1101', amount=9000)
        self.client.force_login(self.b)

    def test_shared_reports_and_other_company_isolation(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['count'], 2)
        self.assertEqual(response.context['income'], 3000)
        report = self.client.get(reverse('income_statement'), {'start': '2025-01-01', 'end': '2025-12-31'})
        self.assertEqual(report.context['report']['net_profit'], 3000)
        self.assertContains(self.client.get(reverse('counterparties')), '공유거래처')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('dashboard')).context['count'], 1)
        self.assertEqual(self.client.get(reverse('voucher_edit', args=[self.voucher.pk])).status_code, 404)

    def test_create_and_edit_keep_authorship_and_individual_quota(self):
        response = self.client.post(reverse('sales_new'), {'date': '2025-08-01', 'account_master': '5001',
                'settlement_account': '1101', 'amount': '700', 'counterparty': self.partner.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Voucher.objects.latest('pk').owner, self.b)
        response = self.client.post(reverse('voucher_edit', args=[self.voucher.pk]), {
                'date': '2025-07-01', 'account_master': '5001', 'settlement_account': '1101',
                'amount': '800', 'counterparty': self.partner.pk})
        self.assertEqual(response.status_code, 302)
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.owner, self.a)
        VoucherQuota.objects.create(owner=self.b, sales_limit=0)
        response = self.client.post(reverse('sales_new'), {'date': '2025-08-01', 'account_master': '5001',
                'settlement_account': '1101', 'amount': '700'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())

    def test_custom_accounts_and_preferences_shared(self):
        Account.objects.create(code='9997', owner=self.a, name='공유계정', category='당좌자산', element='자산')
        response = self.client.get(reverse('accounts'))
        self.assertContains(response, '공유계정')
        self.assertEqual(self.client.post(reverse('account_status', args=['9997']), {'is_active': '0'}).status_code, 302)
        from .account_settings import selectable_accounts
        self.assertFalse(selectable_accounts(self.a).filter(pk='9997').exists())

    def test_year_end_is_company_wide_and_single_batch(self):
        response = self.client.post(reverse('year_end'), {'year': 2025})
        self.assertEqual(response.context['result']['net_profit'], 3000)
        self.assertEqual(self.client.post(reverse('year_end'), {'year': 2025, 'action': 'execute',
                              'token': response.context['token']}).status_code, 302)
        self.client.force_login(self.a)
        response = self.client.post(reverse('year_end'), {'year': 2025})
        self.assertEqual(self.client.post(reverse('year_end'), {'year': 2025, 'action': 'execute',
                              'token': response.context['token']}).status_code, 302)
        self.assertEqual(YearEndClosing.objects.count(), 1)

    def test_receipt_and_opening_balance_share_company_scope(self):
        receipt = ReceiptPhoto.objects.create(owner=self.a, photo='not-opened.jpg', original_name='shared-receipt.jpg', image_type='image/jpeg')
        self.assertContains(self.client.get(reverse('receipt_history')), 'shared-receipt.jpg')
        self.assertEqual(self.client.get(reverse('receipt_detail', args=[receipt.pk])).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('receipt_detail', args=[receipt.pk])).status_code, 404)
        from .opening_balances import save_opening
        rows = [{'account': Account.objects.get(pk='1101'), 'debit': 100, 'credit': 0},
                {'account': Account.objects.get(pk='3101'), 'debit': 0, 'credit': 100}]
        first = save_opening(self.b, date(2025, 1, 1), 0, rows, self.admin)
        second = save_opening(self.a, date(2025, 1, 1), first.revision, rows, self.admin)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(OpeningBalanceBatch.objects.count(), 1)

    def test_new_same_name_requires_approval_and_profile_rename_does_not_join(self):
        user = get_user_model().objects.create_user('pending-member')
        BusinessProfile.objects.create(user=user, company_name='공유업체', business_number='123-45-67890')
        ensure_membership(user)
        self.assertEqual(member_ids(user), [user.pk])
        company = self.a.ledger_membership.company
        approve(user, company, self.admin)
        self.assertEqual(set(member_ids(user)), {self.a.pk, self.b.pk, user.pk})
        self.other.business_profile.company_name = '공유업체'
        self.other.business_profile.save()
        self.assertEqual(member_ids(self.other), [self.other.pk])
        self.assertEqual(self.client.get(reverse('company_members')).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('company_members')).status_code, 200)


class ExistingCompanyMigrationTests(TestCase):
    def test_existing_names_link_and_blank_names_stay_separate(self):
        users = [get_user_model().objects.create_user('existing-' + str(i)) for i in range(4)]
        for user in users[:2]:
            BusinessProfile.objects.create(user=user, company_name='기존업체', business_number='123-45-67890')
        migration = import_module('ledger.migrations.0045_link_existing_company_ledgers')
        migration.link_existing(apps, connection.schema_editor())
        self.assertEqual(set(member_ids(users[0])), {users[0].pk, users[1].pk})
        self.assertEqual(member_ids(users[2]), [users[2].pk])
        self.assertEqual(member_ids(users[3]), [users[3].pk])
