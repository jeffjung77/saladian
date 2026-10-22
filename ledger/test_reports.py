from datetime import date
from django.test import TestCase
from django.urls import reverse
from .models import Account, Voucher, JournalLine
from .reports import balance_sheet, income_statement
from .tests import journal_data


class FinancialReportTests(TestCase):
    def journal(self, debits, credits, when='2026-01-01', closing=False):
        data = journal_data(debits, credits, date=when)
        if closing:
            data['is_closing'] = 'on'
        self.assertRedirects(self.client.post(reverse('voucher_new'), data), '/')
        return Voucher.objects.latest('pk')

    def simple(self, code, amount, kind, when='2026-01-01', settlement='1101'):
        return Voucher.objects.create(date=when, kind=kind, account=Account.objects.get(pk=code).name,
                                      account_master_id=code, settlement_account_id=settlement, amount=amount)

    def test_as_of_cumulative_and_period_boundaries(self):
        self.journal([('1101', '10000')], [('3101', '10000')], '2025-12-31')
        self.simple('5001', 1000, 'income', '2025-12-31')
        self.simple('5001', 20000, 'income', settlement='1201')
        self.simple('6505', 3000, 'expense', '2026-01-31')
        self.simple('5001', 9000, 'income', '2026-02-01')
        bs = balance_sheet(date(2026, 1, 31))
        self.assertEqual(bs['assets'], 28000)
        self.assertEqual(bs['equity'], 28000)
        self.assertEqual(bs['liabilities'], 0)
        self.assertEqual(bs['unclosed_profit'], 18000)
        self.assertEqual(bs['difference'], 0)
        pl = income_statement(date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(pl['net_profit'], 17000)
        self.assertEqual(pl['included_count'], 2)
        self.assertEqual(pl['sections'][0]['total'], 20000)

    def test_asset_acquisition_contra_accounts_and_borrowing(self):
        self.journal([('1101', '10000')], [('3101', '10000')])
        self.journal([('1102', '5000')], [('2101', '5000')])
        self.journal([('1571', '2000')], [('1101', '2000')])
        self.journal([('6507', '500')], [('1572', '500')])
        self.journal([('2101', '1000')], [('1102', '1000')])
        bs = balance_sheet(date(2026, 1, 31))
        self.assertEqual(bs['assets'], 13500)
        self.assertEqual(bs['liabilities'], 4000)
        self.assertEqual(bs['equity'], 9500)
        self.assertEqual(bs['difference'], 0)
        amounts = {r['account'].pk: r['amount'] for g in bs['sections'][0]['groups'] for r in g['rows']}
        self.assertEqual(amounts['1572'], -500)
        self.assertEqual(income_statement(date(2026, 1, 1), date(2026, 1, 31))['net_profit'], -500)

    def test_all_income_sections_refunds_and_cost_deductions(self):
        self.journal([('1101', '10000')], [('5001', '10000')])
        self.journal([('5001', '500')], [('1101', '500')])
        self.journal([('6102', '4000')], [('1101', '4000')])
        self.journal([('1301', '1000')], [('6103', '1000')])
        self.journal([('6505', '2000')], [('1101', '2000')])
        self.journal([('1101', '100')], [('6505', '100')])
        self.journal([('1101', '200')], [('9101', '200')])
        self.journal([('9501', '100')], [('1101', '100')])
        self.journal([('9801', '400')], [('2103', '400')])
        pl = income_statement(date(2026, 1, 1), date(2026, 1, 1))
        self.assertEqual([s['total'] for s in pl['sections']], [9500, 3000, 1900, 200, 100, 400])
        self.assertEqual(pl['gross_profit'], 6500)
        self.assertEqual(pl['operating_profit'], 4600)
        self.assertEqual(pl['pretax_profit'], 4700)
        self.assertEqual(pl['net_profit'], 4300)
        self.assertEqual(balance_sheet(date(2026, 1, 1))['difference'], 0)

    def test_closing_does_not_erase_income_or_double_count_equity(self):
        self.simple('5001', 1000, 'income')
        self.simple('6505', 200, 'expense')
        self.journal([('5001', '1000')], [('6505', '200'), ('3403', '800')], closing=True)
        pl = income_statement(date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(pl['net_profit'], 800)
        self.assertEqual(pl['closing_count'], 1)
        bs = balance_sheet(date(2026, 1, 31))
        self.assertEqual(bs['unclosed_profit'], 0)
        self.assertEqual(bs['assets'], 800)
        self.assertEqual(bs['equity'], 800)
        self.assertEqual(bs['difference'], 0)

    def test_missing_accounts_are_explicitly_excluded_and_can_be_fixed(self):
        voucher = Voucher.objects.create(date='2026-01-01', kind='income', account='매출', amount=1000)
        response = self.client.get(reverse('balance_sheet'), {'as_of': '2026-01-31'})
        self.assertEqual(len(response.context['report']['excluded']), 1)
        self.assertContains(response, '잠정 집계')
        self.assertContains(response, reverse('voucher_edit', args=[voucher.pk]))
        voucher.account_master_id = '5001'
        voucher.save()
        self.assertEqual(len(balance_sheet(date(2026, 1, 31))['excluded']), 1)
        self.client.post(reverse('voucher_edit', args=[voucher.pk]), {
            'date': '2026-01-01', 'kind': 'income', 'account_master': '5001',
            'settlement_account': '1101', 'amount': '1000'})
        bs = balance_sheet(date(2026, 1, 31))
        self.assertEqual(bs['excluded'], [])
        self.assertEqual(bs['assets'], 1000)
        self.assertEqual(bs['equity'], 1000)

    def test_invalid_journal_and_unknown_classification_not_silently_counted(self):
        voucher = Voucher.objects.create(date='2026-01-01', kind='journal', account='복합전표', amount=1000)
        JournalLine.objects.create(voucher=voucher, row=1, side='debit', account_id='1101', amount=1000)
        self.assertEqual(len(balance_sheet(date(2026, 1, 31))['excluded']), 1)
        JournalLine.objects.create(voucher=voucher, row=1, side='credit', account_id='5001', amount=1000)
        Account.objects.filter(pk='5001').update(category='미분류', element='')
        bs = balance_sheet(date(2026, 1, 31))
        self.assertEqual(bs['included_count'], 0)
        self.assertEqual(bs['assets'], 0)
        self.assertEqual(len(bs['excluded']), 1)

    def test_forms_reject_invalid_dates_and_render_empty_results(self):
        for name, params in [
            ('balance_sheet', {'as_of': 'bad'}),
            ('income_statement', {'start': '2026-02-01', 'end': '2026-01-01'}),
            ('income_statement', {'start': '2026-01-01'}),
        ]:
            response = self.client.get(reverse(name), params)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context['report'])
            self.assertTrue(response.context['form'].errors)
        for name in ['balance_sheet', 'income_statement']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['report']['included_count'], 0)
            self.assertContains(response, '반영 가능한 전표가 없습니다')
            self.assertContains(self.client.get('/'), reverse(name))

    def test_single_entry_requires_confirmed_settlement_and_no_duplicate_reporting(self):
        data = {'date': '2026-01-01', 'kind': 'income', 'account_master': '5001', 'amount': '1000'}
        response = self.client.post(reverse('sales_new'), data)
        self.assertIn('settlement_account', response.context['form'].errors)
        data['settlement_account'] = '5001'
        response = self.client.post(reverse('sales_new'), data)
        self.assertIn('settlement_account', response.context['form'].errors)
        data['settlement_account'] = '1201'
        self.assertRedirects(self.client.post(reverse('sales_new'), data), '/')
        pl = income_statement(date(2026, 1, 1), date(2026, 1, 1))
        self.assertEqual(pl['net_profit'], 1000)
        self.assertEqual(pl['included_count'], 1)
        bs = balance_sheet(date(2026, 1, 1))
        self.assertEqual(bs['assets'], 1000)
        self.assertEqual(bs['difference'], 0)
        self.assertEqual(JournalLine.objects.count(), 0)
