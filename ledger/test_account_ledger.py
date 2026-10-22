from datetime import date
from django.test import TestCase
from django.urls import reverse
from .models import Account, Voucher, JournalLine
from .reports import account_ledger, balance_sheet
from .tests import journal_data


class AccountLedgerTests(TestCase):
    def journal(self, debits=None, credits=None, when='2026-10-01', memo='전표적요', line_memo='', closing=False):
        data = journal_data(debits, credits, date=when, memo=memo)
        data['lines-0-memo'] = line_memo
        if closing:
            data['is_closing'] = 'on'
        self.assertRedirects(self.client.post(reverse('voucher_new'), data), '/')
        return Voucher.objects.latest('pk')

    def ledger(self, code='1101', start=date(2026, 10, 1), end=date(2026, 10, 31)):
        return account_ledger(Account.objects.get(pk=code), start, end)

    def test_opening_boundaries_running_balance_and_same_date_order(self):
        self.journal([('1101', '1000')], [('3101', '1000')], when='2026-09-30')
        first = self.journal([('1101', '500')], [('5001', '500')])
        second = self.journal([('6505', '200')], [('1101', '200')])
        self.journal([('6505', '100')], [('1101', '100')], when='2026-10-31')
        self.journal([('1101', '9999')], [('5001', '9999')], when='2026-11-01')
        report = self.ledger()
        self.assertEqual(report['opening'], 1000)
        self.assertEqual(report['debit'], 500)
        self.assertEqual(report['credit'], 300)
        self.assertEqual(report['closing'], 1200)
        self.assertEqual([r['balance'] for r in report['rows']], [1500, 1300, 1200])
        self.assertEqual([r['voucher'].pk for r in report['rows'][:2]], [first.pk, second.pk])
        self.assertEqual(balance_sheet(date(2026, 10, 31))['assets'], report['closing'])

    def test_credit_balances_and_same_account_on_both_sides_not_netted(self):
        self.journal([('1101', '1000')], [('5001', '1000')], when='2026-09-30')
        self.journal([('5001', '100')], [('1101', '100')])
        report = self.ledger('5001')
        self.assertEqual(report['opening_side'], '대변')
        self.assertEqual(report['opening_amount'], 1000)
        self.assertEqual(report['closing_side'], '대변')
        self.assertEqual(report['closing_amount'], 900)
        self.journal([('1102', '50')], [('1102', '50')])
        report = self.ledger('1102')
        self.assertEqual(len(report['rows']), 2)
        self.assertEqual(report['debit'], 50)
        self.assertEqual(report['credit'], 50)
        self.assertEqual(report['closing'], 0)
        self.assertEqual(report['closing_side'], '—')

    def test_simple_entries_primary_and_settlement_are_included_once(self):
        Voucher.objects.create(date='2026-10-01', kind='income', account='매출-용역', account_master_id='5001', settlement_account_id='1201', amount=1000, memo='외상 매출')
        Voucher.objects.create(date='2026-10-01', kind='expense', account='임차료', account_master_id='6505', settlement_account_id='1101', amount=200)
        self.assertEqual(self.ledger('1201')['debit'], 1000)
        self.assertEqual(self.ledger('5001')['credit'], 1000)
        self.assertEqual(self.ledger('6505')['debit'], 200)
        self.assertEqual(self.ledger('1101')['credit'], 200)
        self.assertEqual(self.ledger('1201')['rows'][0]['memo'], '외상 매출')
        self.assertIn('5001', self.ledger('1201')['rows'][0]['opposite'])

    def test_closing_and_line_memo_fallback_are_visible(self):
        self.journal(memo='전체 적요', line_memo='라인 공통 적요')
        self.journal(memo='비어 있으면 전체 적요')
        self.journal([('5001', '2000')], [('3403', '2000')], closing=True)
        report = self.ledger('5001')
        self.assertEqual(len(report['rows']), 3)
        self.assertEqual(report['closing'], 0)
        self.assertEqual(report['rows'][0]['memo'], '라인 공통 적요')
        self.assertEqual(report['rows'][1]['memo'], '비어 있으면 전체 적요')
        response = self.client.get(reverse('account_ledger'), {'account': '5001', 'start': '2026-10-01', 'end': '2026-10-31'})
        self.assertContains(response, '손익대체')
        self.assertContains(response, '라인 공통 적요')

    def test_invalid_sources_warn_including_opening_period(self):
        Voucher.objects.create(date='2026-09-01', kind='income', account='미확인', amount=100)
        broken = Voucher.objects.create(date='2026-10-01', kind='journal', account='복합전표', amount=100)
        JournalLine.objects.create(voucher=broken, row=1, side='debit', account_id='1101', amount=100)
        self.journal([('1102', '100')], [('3101', '100')], when='2026-11-01')
        report = self.ledger()
        self.assertEqual(len(report['excluded']), 2)
        self.assertEqual(report['closing'], 0)
        response = self.client.get(reverse('account_ledger'), {'account': '1101', 'start': '2026-10-01', 'end': '2026-10-31'})
        self.assertContains(response, '잠정 집계')
        self.assertContains(response, reverse('voucher_edit', args=[broken.pk]))

    def test_empty_period_preserves_opening_and_rejects_bad_filters(self):
        self.journal(when='2026-09-30')
        report = self.ledger()
        self.assertEqual(report['rows'], [])
        self.assertEqual(report['opening'], 1000)
        self.assertEqual(report['closing'], 1000)
        for params in [
            {'account': '9999', 'start': '2026-10-01', 'end': '2026-10-31'},
            {'account': '1101', 'start': '2026-10-31', 'end': '2026-10-01'},
            {'account': '1101', 'start': 'bad', 'end': '2026-10-31'},
            {'account': '1101'},
        ]:
            response = self.client.get(reverse('account_ledger'), params)
            self.assertIsNone(response.context['report'])
            self.assertTrue(response.context['form'].errors)
        initial = self.client.get(reverse('account_ledger'))
        self.assertIsNone(initial.context['report'])
        self.assertFalse(initial.context['form'].errors)
        self.assertContains(self.client.get('/'), reverse('account_ledger'))
