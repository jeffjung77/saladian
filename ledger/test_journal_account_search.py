from django.urls import reverse
from .models import Account, AccountPreference, Voucher
from .test_helpers import AuthenticatedLedgerTestCase
from .tests import journal_data


class JournalAccountSearchTests(AuthenticatedLedgerTestCase):
    def data(self, **fields):
        data = journal_data([('1101', '1000')], [('5001', '1000')])
        data['lines-0-debit_account'] = ''
        data['lines-0-credit_account'] = ''
        data.update(fields)
        return data

    def test_account_codes_and_exact_names_resolve_on_both_sides(self):
        data = self.data(**{'lines-0-debit_code': '1101', 'lines-0-credit_name': Account.objects.get(pk='5001').name})
        self.assertEqual(self.client.post(reverse('voucher_new'), data).status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(set(voucher.journal_lines.values_list('account_id', flat=True)), {'1101', '5001'})
        response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
        self.assertContains(response, 'value="1101"')
        self.assertContains(response, 'value="현금"')
        self.assertContains(response, 'lines-4-credit_code')
        self.assertContains(response, 'lines-4-debit_name')

    def test_unknown_ambiguous_and_mismatched_inputs_are_rejected(self):
        variants = [({'lines-0-debit_code': '9999'}, 'debit_code'),
                    ({'lines-0-debit_name': '존재하지 않는 과목'}, 'debit_name'),
                    ({'lines-0-debit_code': '1101', 'lines-0-debit_account': '1102'}, 'debit_code'),
                    ({'lines-0-debit_code': '1101', 'lines-0-debit_name': '예금'}, 'debit_name')]
        for fields, error in variants:
            response = self.client.post(reverse('voucher_new'), self.data(**fields))
            self.assertIn(error, response.context['rows'].forms[0].errors)
        Account.objects.create(code='1110', name='현금', category='당좌자산', element='자산')
        response = self.client.post(reverse('voucher_new'), self.data(**{'lines-0-debit_name': '현금'}))
        self.assertIn('debit_name', response.context['rows'].forms[0].errors)
        self.assertFalse(Voucher.objects.exists())

    def test_inactive_codes_cannot_bypass_account_selection(self):
        AccountPreference.objects.create(owner=self.user, account_id='1101', is_active=False)
        response = self.client.post(reverse('voucher_new'), self.data(**{'lines-0-debit_code': '1101', 'lines-0-credit_code': '5001'}))
        self.assertIn('debit_code', response.context['rows'].forms[0].errors)
        self.assertFalse(Voucher.objects.exists())

    def test_codes_in_name_fields_resolve_on_both_sides(self):
        data = self.data(**{'lines-0-debit_name': '1101', 'lines-0-credit_name': '5001'})
        self.assertEqual(self.client.post(reverse('voucher_new'), data).status_code, 302)
        self.assertEqual(set(Voucher.objects.get().journal_lines.values_list('account_id', flat=True)), {'1101', '5001'})

    def test_credit_code_in_name_field_with_selected_account(self):
        data = self.data(**{'lines-0-debit_code': '1101', 'lines-0-credit_name': '5001',
                           'lines-0-credit_code': '5001', 'lines-0-credit_account': '5001'})
        self.assertEqual(self.client.post(reverse('voucher_new'), data).status_code, 302)
