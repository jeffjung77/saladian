from django.urls import reverse
from .test_helpers import AuthenticatedLedgerTestCase
from .tests import journal_data
from .models import Voucher


class JournalVisibleRowsTests(AuthenticatedLedgerTestCase):
    def test_new_form_one_row_existing_form_restores_used_rows(self):
        response = self.client.get(reverse('voucher_new'))
        self.assertEqual(response.context['visible_rows'], 1)
        self.assertContains(response, 'id="journal-add-row"')
        data = journal_data([('1101', '1000')], [('', ''), ('', ''), ('5001', '1000')])
        self.assertEqual(self.client.post(reverse('voucher_new'), data).status_code, 302)
        response = self.client.get(reverse('voucher_edit', args=[Voucher.objects.get().pk]))
        self.assertEqual(response.context['visible_rows'], 3)

    def test_errors_and_added_rows_are_not_hidden(self):
        data = journal_data()
        data['date'] = 'invalid'
        data['visible_line_count'] = '4'
        response = self.client.post(reverse('voucher_new'), data)
        self.assertEqual(response.context['visible_rows'], 4)
        data['lines-4-memo'] = '적요만 입력'
        response = self.client.post(reverse('voucher_new'), data)
        self.assertEqual(response.context['visible_rows'], 5)
        self.assertFalse(Voucher.objects.exists())
