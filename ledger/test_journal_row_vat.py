from datetime import date
from importlib import import_module
from django.apps import apps
from django.db import connection
from django.urls import reverse
from .models import Voucher, JournalRowVAT
from .reports import balance_sheet
from .test_helpers import AuthenticatedLedgerTestCase
from .tests import journal_data


class JournalRowVATTests(AuthenticatedLedgerTestCase):
    def data(self):
        data = journal_data([('1101', '3300')], [('5001', '1000'), ('5001', '2000'), ('2107', '300')])
        for row, code, amount in [(0, 'T01', '100'), (1, 'T02', '200')]:
            data.update({f'lines-{row}-vat_enabled': 'on', f'lines-{row}-vat_code': code, f'lines-{row}-vat_trade': 'S',
                f'lines-{row}-vat_document': 'D03', f'lines-{row}-vat_amount': amount})
        return data

    def test_multiple_rows_save_edit_and_no_double_count(self):
        data = self.data()
        self.assertEqual(self.client.post(reverse('voucher_new'), data).status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.row_vat.count(), 2)
        self.assertEqual(list(voucher.row_vat.values_list('row', 'vat_amount')), [(1, 100), (2, 200)])
        self.assertEqual(voucher.vat_code, '')
        response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
        self.assertEqual(response.context['rows'].forms[1].initial['vat_code'], 'T02')
        self.assertNotIn('vat_code', response.context['form'].fields)
        report = balance_sheet(date(2026, 12, 31), vouchers=Voucher.objects.filter(owner=self.user))
        self.assertEqual((report['assets'], report['liabilities'], report['equity']), (3300, 300, 3000))
        self.assertEqual(self.client.post(reverse('voucher_edit', args=[voucher.pk]), data).status_code, 302)
        self.assertEqual(JournalRowVAT.objects.count(), 2)

    def test_each_row_validation_and_orphan_tax_rejected(self):
        data = self.data()
        data['lines-1-vat_trade'] = ''
        response = self.client.post(reverse('voucher_new'), data)
        self.assertIn('vat_trade', response.context['rows'].forms[1].errors)
        data = self.data()
        data.update({'lines-4-vat_enabled': 'on', 'lines-4-vat_code': 'E01', 'lines-4-vat_trade': 'S', 'lines-4-vat_document': 'D03'})
        response = self.client.post(reverse('voucher_new'), data)
        self.assertIn('vat_code', response.context['rows'].forms[4].errors)
        self.assertFalse(Voucher.objects.exists())

    def test_legacy_header_metadata_backfilled_once(self):
        voucher = Voucher.objects.create(owner=self.user, date='2026-10-22', kind='journal', amount=100,
            vat_code='T01', vat_trade='S', vat_document='D01', vat_amount=10)
        migrate = import_module('ledger.migrations.0033_journalrowvat').preserve_header_vat
        for _ in range(2):
            migrate(apps, connection.schema_editor())
        self.assertEqual(voucher.row_vat.count(), 1)
        self.assertEqual(voucher.row_vat.get().vat_amount, 10)

    def test_unchecked_rows_ignore_tax_and_existing_rows_start_checked(self):
        data = self.data()
        self.client.post(reverse('voucher_new'), data)
        voucher = Voucher.objects.get()
        url = reverse('voucher_edit', args=[voucher.pk])
        response = self.client.get(url)
        self.assertTrue(response.context['rows'].forms[0]['vat_enabled'].value())
        self.assertFalse(response.context['rows'].forms[4]['vat_enabled'].value())
        # Even stale tax fields in a forged POST cannot survive unchecked rows.
        data.pop('lines-0-vat_enabled')
        data.pop('lines-1-vat_enabled')
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(voucher.row_vat.count(), 0)

    def test_checked_row_requires_tax_code(self):
        data = journal_data()
        data['lines-0-vat_enabled'] = 'on'
        response = self.client.post(reverse('voucher_new'), data)
        self.assertIn('vat_code', response.context['rows'].forms[0].errors)
        self.assertFalse(Voucher.objects.exists())
