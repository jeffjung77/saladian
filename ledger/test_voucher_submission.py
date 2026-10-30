from uuid import uuid4
from django.urls import reverse
from .test_helpers import AuthenticatedLedgerTestCase
from .models import Voucher
from .tests import journal_data


class VoucherSubmissionTests(AuthenticatedLedgerTestCase):
    def test_sales_and_expense_retry_only_save_once(self):
        for route, code in [('sales_new', '5001'), ('expense_new', '6505')]:
            token = str(uuid4())
            data = dict(date='2026-10-30', account_master=code, settlement_account='1101', amount='1000', submission_token=token)
            for _ in range(2):
                response = self.client.post(reverse(route), data)
                self.assertEqual(response.status_code, 302)
            self.assertEqual(Voucher.objects.filter(submission_token=token).count(), 1)

    def test_journal_retry_only_save_once(self):
        token = str(uuid4())
        data = journal_data(submission_token=token)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('voucher_new'), data).status_code, 302)
        voucher = Voucher.objects.get(submission_token=token)
        self.assertEqual(voucher.journal_lines.count(), 2)
        self.assertEqual(Voucher.objects.count(), 1)

    def test_invalid_submission_preserves_values_and_can_be_corrected(self):
        data = dict(date='2026-10-30', account_master='5001', settlement_account='1101', amount='0', memo='유지할 내용', submission_token=str(uuid4()))
        response = self.client.post(reverse('sales_new'), data)
        self.assertContains(response, '유지할 내용')
        self.assertFalse(Voucher.objects.exists())
        data['amount'] = '1000'
        self.assertEqual(self.client.post(reverse('sales_new'), data).status_code, 302)

    def test_new_forms_have_different_tokens(self):
        url = reverse('sales_new')
        first = self.client.get(url).context['form']['submission_token'].value()
        second = self.client.get(url).context['form']['submission_token'].value()
        self.assertNotEqual(first, second)
