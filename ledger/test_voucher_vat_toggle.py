from django.urls import reverse
from .models import Voucher
from .test_helpers import AuthenticatedLedgerTestCase


class VoucherVatToggleTests(AuthenticatedLedgerTestCase):
    def data(self, **extra):
        return dict(date='2026-10-26', account_master='5001', settlement_account='1101',
                    amount='1000', _vat_toggle_present='1', vat_code='T02', vat_trade='S',
                    vat_document='D03', vat_amount='100', **extra)

    def test_unchecked_discards_tax_and_checked_preserves_tax_on_edit(self):
        self.assertEqual(self.client.post(reverse('sales_new'), self.data()).status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.vat_code, '')
        self.assertEqual(voucher.vat_amount, 0)
        self.client.post(reverse('voucher_edit', args=[voucher.pk]), self.data(vat_enabled='on'))
        voucher.refresh_from_db()
        self.assertEqual(voucher.vat_code, 'T02')
        self.assertEqual(voucher.vat_amount, 100)
        response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
        self.assertTrue(response.context['form'].initial['vat_enabled'])

    def test_toggle_appears_before_tax_code_on_both_entry_screens(self):
        for name in ['sales_new', 'expense_new']:
            response = self.client.get(reverse(name))
            html = response.content.decode()
            self.assertEqual(response.status_code, 200)
            self.assertLess(html.index('id="id_vat_enabled"'), html.index('id="id_vat_code"'))

    def test_expense_toggle_saves_tax_and_clears_it_when_unchecked(self):
        data = self.data(vat_enabled='on')
        data.update(account_master='6503', vat_trade='P', vat_deduction='C01')
        self.assertEqual(self.client.post(reverse('expense_new'), data).status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.kind, Voucher.Kind.EXPENSE)
        self.assertEqual(voucher.vat_amount, 100)
        self.assertEqual(voucher.vat_trade, 'P')
        data.pop('vat_enabled')
        self.assertEqual(self.client.post(reverse('voucher_edit', args=[voucher.pk]), data).status_code, 302)
        voucher.refresh_from_db()
        self.assertEqual(voucher.vat_code, '')
        self.assertEqual(voucher.vat_amount, 0)
