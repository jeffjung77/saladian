from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from .models import Account, Voucher, JournalLine, OpeningBalanceBatch, VoucherQuota, VoucherCreationUsage
from . import reports
from .voucher_quota import save_voucher


class OpeningBalanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='opening-admin', is_superuser=True, is_staff=True)
        self.owner = User.objects.create_user(username='opening-owner')
        self.other = User.objects.create_user(username='opening-other')
        self.url = reverse('opening_balances')
        self.client.force_login(self.admin)

    def data(self, entries=None, revision=0, **changes):
        entries = entries or [('1101', '10000', ''), ('3101', '', '10000')]
        values = dict(owner=self.owner.pk, start_date='2026-07-01', revision=revision)
        values.update({'balances-TOTAL_FORMS': str(len(entries)), 'balances-INITIAL_FORMS': str(len(entries)),
            'balances-MIN_NUM_FORMS': '0', 'balances-MAX_NUM_FORMS': '500'})
        for index, (code, debit, credit) in enumerate(entries):
            values.update({f'balances-{index}-account': code, f'balances-{index}-debit': debit, f'balances-{index}-credit': credit})
        values.update(changes)
        return values

    def test_permission_get_and_csrf(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.owner.is_staff = True
        self.owner.save()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url, {'owner': self.owner.pk}), '기초잔액 저장')
        self.assertFalse(OpeningBalanceBatch.objects.exists())
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.url, self.data()).status_code, 403)

    def test_balanced_opening_flows_into_reports_and_owner_scope(self):
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.owner, self.owner)
        self.assertEqual(voucher.date, date(2026, 6, 30))
        self.assertEqual(voucher.get_entry_type_display(), '기초잔액')
        source = Voucher.objects.filter(owner=self.owner)
        before = reports.balance_sheet(date(2026, 6, 29), vouchers=source)
        self.assertEqual(before['assets'], 0)
        after = reports.balance_sheet(date(2026, 7, 1), vouchers=source)
        self.assertEqual([after['assets'], after['equity'], after['difference']], [10000, 10000, 0])
        ledger = reports.account_ledger(Account.objects.get(pk='1101'), date(2026,7,1), date(2026,7,31), vouchers=source)
        self.assertEqual([ledger['opening'], ledger['closing'], ledger['debit']], [10000,10000,0])
        self.assertEqual(reports.balance_sheet(date(2026,7,1), vouchers=Voucher.objects.filter(owner=self.other))['assets'], 0)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('voucher_delete', args=[voucher.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('voucher_edit', args=[voucher.pk])).status_code, 403)
        self.assertTrue(Voucher.objects.filter(pk=voucher.pk).exists())

    def test_update_replaces_only_opening_and_repeated_post_is_rejected(self):
        self.client.post(self.url, self.data())
        regular = Voucher.objects.create(owner=self.owner, entry_type='sales', kind='income', date=date(2026,7,2), amount=100, account_master_id='5001', settlement_account_id='1101')
        response = self.client.post(self.url, self.data([('1101','20000',''),('3101','','20000')], revision=1))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 2)
        self.assertTrue(Voucher.objects.filter(pk=regular.pk).exists())
        self.assertEqual(OpeningBalanceBatch.objects.get().revision, 2)
        self.assertEqual(self.client.post(self.url, self.data(revision=1)).status_code, 200)
        self.assertEqual(Voucher.objects.filter(opening_batch__isnull=False).get().amount, 20000)

    def test_validation_and_existing_earlier_transactions(self):
        private = Account.objects.create(pk='9998', owner=self.other, name='private', category='당좌자산', element='자산')
        cases = [ [('1101','100',''),('3101','','90')], [('1101','-1',''),('3101','','1')],
            [('1101','1.5',''),('3101','','1.5')], [('1101','1','1')], [('1101','100',''),('1101','','100')],
            [(private.pk,'100',''),('3101','','100')]]
        for entries in cases:
            self.assertEqual(self.client.post(self.url, self.data(entries)).status_code, 200)
            self.assertFalse(OpeningBalanceBatch.objects.exists())
        Voucher.objects.create(owner=self.owner, date=date(2026,6,1), kind='income', amount=100)
        response = self.client.post(self.url, self.data())
        self.assertContains(response, '사용 시작일 이전에 일반 전표')
        self.assertFalse(OpeningBalanceBatch.objects.exists())

    def test_many_accounts_and_opening_does_not_consume_quota(self):
        codes = list(Account.objects.filter(element='자산').values_list('pk', flat=True)[:8])
        entries = [(code, '100', '') for code in codes] + [('3101', '', '800')]
        VoucherQuota.objects.create(owner=self.owner, other_limit=1)
        self.assertEqual(self.client.post(self.url, self.data(entries)).status_code, 302)
        self.assertEqual(Voucher.objects.count(), 2)
        accounts = {a.pk:a for a in Account.objects.all()}
        for voucher in Voucher.objects.all():
            postings, reason = reports.voucher_postings(voucher, accounts)
            self.assertIsNone(reason)
            self.assertEqual(sum(p['net'] for p in postings), 0)
            self.assertLessEqual(max(voucher.journal_lines.values_list('row', flat=True)), 5)
        save_voucher(Voucher(owner=self.owner, entry_type='other', kind='journal', amount=100, date=date(2026,7,2)))
        self.assertEqual(VoucherCreationUsage.objects.get(owner=self.owner, entry_type='other').generated_count, 1)

    def test_year_to_date_income_and_new_period(self):
        self.client.post(self.url, self.data([('1101','8000',''),('6505','2000',''),('5001','','10000')]))
        source = Voucher.objects.filter(owner=self.owner)
        self.assertEqual(reports.income_statement(date(2026,1,1), date(2026,7,31), vouchers=source)['net_profit'], 8000)
        self.assertEqual(reports.income_statement(date(2026,7,1), date(2026,7,31), vouchers=source)['net_profit'], 0)
        self.assertEqual(reports.balance_sheet(date(2026,7,1), vouchers=source)['difference'], 0)
