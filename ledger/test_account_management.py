from datetime import date
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import Account, AccountPreference, Voucher
from .reports import balance_sheet
from .test_helpers import AuthenticatedLedgerTestCase
from .tests import journal_data


class AccountManagementTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])

    def data(self, **overrides):
        data = {'code': '5010', 'name': '추가 매출', 'category': '매출액', 'section': ''}
        data.update(overrides)
        return data

    def sales(self, **overrides):
        data = {'date': '2026-10-23', 'account_master': '5001', 'settlement_account': '1101', 'amount': '1000'}
        data.update(overrides)
        return data

    def test_create_validates_code_and_classification_and_supports_reports(self):
        self.assertRedirects(self.client.post(reverse('account_new'), self.data(owner='999', element='부채')), reverse('accounts'))
        account = Account.objects.get(pk='5010')
        self.assertEqual(account.owner, self.user)
        self.assertEqual(account.element, '수익')
        self.assertContains(self.client.get(reverse('sales_new')), '추가 매출')
        self.assertEqual(self.client.post(reverse('sales_new'), self.sales(account_master=account.pk)).status_code, 302)
        report = balance_sheet(date(2026, 10, 23), vouchers=Voucher.objects.filter(owner=self.user))
        self.assertEqual((report['assets'], report['equity'], report['difference']), (1000, 1000, 0))
        for data, field in [(self.data(), 'code'), (self.data(code='abcd'), 'code'), (self.data(code='123'), 'code'), (self.data(code='5011', category='unknown'), 'category')]:
            response = self.client.post(reverse('account_new'), data)
            self.assertIn(field, response.context['form'].errors)

    def test_disabled_accounts_rejected_for_new_entries_but_preserved_in_history(self):
        self.client.post(reverse('sales_new'), self.sales())
        voucher = Voucher.objects.get()
        for code in ['5001', '1101']:
            self.assertRedirects(self.client.post(reverse('account_status', args=[code]), {'is_active': '0'}), reverse('accounts'))
        response = self.client.post(reverse('sales_new'), self.sales())
        self.assertIn('account_master', response.context['form'].errors)
        self.assertIn('settlement_account', response.context['form'].errors)
        self.assertEqual(self.client.post(reverse('voucher_edit', args=[voucher.pk]), self.sales()).status_code, 302)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(balance_sheet(date(2026, 10, 23), vouchers=Voucher.objects.filter(owner=self.user))['assets'], 1000)
        response = self.client.get(reverse('account_ledger'), {'account': '5001', 'start': '2026-10-01', 'end': '2026-10-31'})
        self.assertEqual(response.context['report']['credit'], 1000)
        self.client.post(reverse('account_status', args=['5001']), {'is_active': '1'})
        self.assertTrue(AccountPreference.objects.get(owner=self.user, account_id='5001').is_active)

    def test_journal_preserves_original_inactive_accounts_only(self):
        data = journal_data([('1101', '1000')], [('5001', '1000')])
        self.client.post(reverse('voucher_new'), data)
        voucher = Voucher.objects.get()
        self.client.post(reverse('account_status', args=['1101']), {'is_active': '0'})
        self.assertEqual(self.client.post(reverse('voucher_edit', args=[voucher.pk]), data).status_code, 302)
        response = self.client.post(reverse('voucher_new'), data)
        self.assertIn('debit_account', response.context['rows'].forms[0].errors)

    def test_settings_and_custom_accounts_are_owner_scoped(self):
        other = get_user_model().objects.create_user(username='other-account-admin', is_staff=True)
        self.client.post(reverse('account_status', args=['1101']), {'is_active': '0'})
        self.client.post(reverse('account_new'), self.data())
        self.client.force_login(other)
        response = self.client.get(reverse('sales_new'))
        self.assertTrue(response.context['form'].fields['settlement_account'].queryset.filter(pk='1101').exists())
        self.assertNotContains(response, '추가 매출')
        self.assertEqual(self.client.post(reverse('account_status', args=['5010']), {'is_active': '1'}).status_code, 404)
        self.assertNotContains(self.client.get(reverse('account_ledger')), '추가 매출')
        response = self.client.post(reverse('sales_new'), self.sales(account_master='5010'))
        self.assertIn('account_master', response.context['form'].errors)

    def test_permissions_csrf_and_post_only(self):
        url = reverse('account_status', args=['1101'])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {'is_active': 'invalid'}).status_code, 400)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(url, {'is_active': '0'}).status_code, 403)
        self.user.is_staff = False
        self.user.save(update_fields=['is_staff'])
        self.assertEqual(self.client.post(url, {'is_active': '0'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('account_new'), self.data()).status_code, 403)
