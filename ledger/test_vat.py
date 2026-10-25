from datetime import date
from decimal import Decimal
from django.urls import reverse
from .models import Voucher
from .reports import balance_sheet, income_statement, account_ledger
from .test_helpers import AuthenticatedLedgerTestCase
from .tests import journal_data


class VatTests(AuthenticatedLedgerTestCase):
    def data(self, **overrides):
        data = {'date': '2026-10-23', 'account_master': '5001', 'settlement_account': '1101',
                'amount': '1000', 'vat_code': 'T02', 'vat_document': 'D01', 'vat_amount': '100'}
        data.update(overrides)
        return data

    def test_sales_posts_tax_separately_and_preserves_edit(self):
        response = self.client.post(reverse('sales_new'), self.data())
        self.assertRedirects(response, reverse('dashboard'))
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.vat_trade, 'S')
        self.assertEqual(voucher.vat_display_code, 'T02-S-D01')
        self.assertEqual(voucher.gross_amount, 1100)
        source = Voucher.objects.filter(owner=self.user)
        bs = balance_sheet(date(2026, 10, 23), vouchers=source)
        self.assertEqual((bs['assets'], bs['liabilities'], bs['equity'], bs['difference']), (1100, 100, 1000, 0))
        self.assertEqual(income_statement(date(2026, 10, 1), date(2026, 10, 23), vouchers=source)['net_profit'], 1000)
        response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
        self.assertEqual(response.context['form'].initial['vat_amount'], Decimal(100))
        self.assertEqual(self.client.get(reverse('dashboard')).context['income'], 1100)

    def test_purchase_deduction_nondeduction_and_apportionment(self):
        for deduction, deductible, expense, input_tax in [('C01', '0', 1000, 100), ('C02', '0', 1100, 0), ('C03', '40', 1060, 40)]:
            with self.subTest(deduction=deduction):
                Voucher.objects.all().delete()
                response = self.client.post(reverse('expense_new'), self.data(account_master='6505', vat_deduction=deduction, vat_deductible=deductible, vat_reason='업무 목적 검토'))
                self.assertEqual(response.status_code, 302, response.context and response.context['form'].errors)
                source = Voucher.objects.filter(owner=self.user)
                self.assertEqual(income_statement(date(2026, 10, 1), date(2026, 10, 23), vouchers=source)['net_profit'], -expense)
                bs = balance_sheet(date(2026, 10, 23), vouchers=source)
                self.assertEqual(bs['difference'], 0)
                rows = {row['account'].pk: row['amount'] for section in bs['sections'] for group in section['groups'] for row in group['rows']}
                self.assertEqual(rows.get('1209', 0), input_tax)
                self.assertEqual(rows['1101'], -1100)

    def test_zero_rate_exempt_and_outside_remain_distinct(self):
        for code in ['E01', 'Z01', 'X']:
            self.assertEqual(self.client.post(reverse('sales_new'), self.data(vat_code=code, vat_amount='0')).status_code, 302)
        self.assertEqual(set(Voucher.objects.values_list('vat_code', flat=True)), {'E01', 'Z01', 'X'})

    def test_rejects_invalid_codes_negative_fractional_and_inconsistent_tax(self):
        for overrides, field in [({'vat_code': 'BAD'}, 'vat_code'), ({'vat_code': ''}, 'vat_code'),
                                 ({'vat_amount': '-1'}, 'vat_amount'), ({'vat_amount': '0.5'}, 'vat_amount'),
                                 ({'vat_code': 'E01'}, 'vat_amount'), ({'vat_code': 'Z01'}, 'vat_amount'),
                                 ({'vat_document': ''}, 'vat_document'), ({'vat_deduction': 'C01'}, 'vat_deduction')]:
            response = self.client.post(reverse('sales_new'), self.data(**overrides))
            self.assertIn(field, response.context['form'].errors)
        for overrides, field in [({'vat_deduction': 'C03', 'vat_deductible': '101', 'vat_reason': '안분'}, 'vat_deductible'),
                                 ({'vat_deduction': 'C09'}, 'vat_deduction'), ({'vat_deduction': 'C02'}, 'vat_reason')]:
            response = self.client.post(reverse('expense_new'), self.data(account_master='6505', **overrides))
            self.assertIn(field, response.context['form'].errors)
        self.assertFalse(Voucher.objects.exists())

    def test_journal_tax_must_match_manual_postings_and_is_not_added_twice(self):
        data = journal_data([('1101', '1100')], [('5001', '1000'), ('2107', '100')])
        data.update({'lines-0-vat_enabled': 'on', 'lines-0-vat_code': 'T02', 'lines-0-vat_trade': 'S', 'lines-0-vat_document': 'D01', 'lines-0-vat_amount': '100'})
        response = self.client.post(reverse('voucher_new'), data)
        self.assertEqual(response.status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.amount, 1100)
        bs = balance_sheet(date(2026, 12, 31), vouchers=Voucher.objects.filter(owner=self.user))
        self.assertEqual((bs['assets'], bs['liabilities'], bs['equity']), (1100, 100, 1000))
        data['lines-0-vat_amount'] = '200'
        response = self.client.post(reverse('voucher_new'), data)
        self.assertTrue(response.context['rows'].non_form_errors())
        self.assertEqual(Voucher.objects.count(), 1)

    def test_legacy_voucher_can_be_updated_to_vat(self):
        data = self.data(vat_code='', vat_document='', vat_amount='0')
        self.assertEqual(self.client.post(reverse('sales_new'), data).status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(self.client.post(reverse('voucher_edit', args=[voucher.pk]), self.data()).status_code, 302)
        voucher.refresh_from_db()
        self.assertEqual(voucher.vat_amount, 100)
        self.assertEqual(voucher.vat_trade, 'S')
