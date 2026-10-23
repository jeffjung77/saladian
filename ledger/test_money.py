from django.urls import reverse
from .models import Voucher
from .widgets import MoneyInput
from .test_helpers import AuthenticatedLedgerTestCase
from .tests import journal_data


class MoneyTests(AuthenticatedLedgerTestCase):
    def test_format_and_parse_preserve_value_and_reject_malformed_groups(self):
        widget = MoneyInput()
        self.assertEqual(widget.format_value('1000'), '1,000')
        self.assertEqual(widget.format_value('-123456789'), '-123,456,789')
        self.assertEqual(widget.format_value('99999999999999'), '99,999,999,999,999')
        self.assertEqual(widget.value_from_datadict({'amount': '1,234,567'}, {}, 'amount'), '1234567')
        self.assertEqual(widget.value_from_datadict({'amount': '1,23'}, {}, 'amount'), '1,23')

    def test_sales_amounts_save_and_redisplay_with_commas(self):
        data = {'date': '2026-10-23', 'account_master': '5001', 'settlement_account': '1101',
                'amount': '100,000', 'vat_code': 'T02', 'vat_document': 'D01', 'vat_amount': '10,000'}
        response = self.client.post(reverse('sales_new'), data)
        self.assertEqual(response.status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.amount, 100000)
        self.assertEqual(voucher.vat_amount, 10000)
        response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
        self.assertContains(response, 'value="100,000"')
        self.assertContains(response, 'value="10,000"')
        self.assertContains(response, 'data-money="true"')
        for invalid in ['1,23', '-1,000', '1,000.5']:
            data['amount'] = invalid
            response = self.client.post(reverse('sales_new'), data)
            self.assertIn('amount', response.context['form'].errors)

    def test_journal_inputs_accept_formatted_amounts(self):
        data = journal_data([('1101', '1,000')], [('5001', '1,000')])
        response = self.client.post(reverse('voucher_new'), data)
        self.assertEqual(response.status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.amount, 1000)
        self.assertContains(self.client.get(reverse('voucher_edit', args=[voucher.pk])), 'value="1,000"')
