from datetime import date
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import ReceiptPhoto, Voucher, Account, AccountPreference, ReceiptCreationUsage
from .receipt_draft import extract_draft
from .test_helpers import AuthenticatedLedgerTestCase


class ReceiptDraftTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.item = ReceiptPhoto.objects.create(owner=self.user, photo='test.jpg', image_type='image/jpeg',
            original_name='test.jpg', ocr_text='상호: 가맹점\n2026-10-25\n공급가액 10,000\n부가세 1,000\n합계 11,000')
        self.url = reverse('receipt_expense', args=[self.item.pk])

    def data(self, **overrides):
        data = dict(date='2026-10-25', merchant='가맹점', account_master='6505', settlement_account='1101',
            counterparty='', amount='10,000', vat_amount='1,000', receipt_total='11,000', vat_code='T01',
            vat_document='D03', vat_deduction='C01', confirmed='on', memo='확인 후 저장')
        data.update(overrides)
        return data

    def test_extract_labeled_values_and_ambiguous_blanks(self):
        data = extract_draft(self.item.ocr_text)
        self.assertEqual(data['date'], date(2026, 10, 25))
        self.assertEqual(data['amount'], Decimal(10000))
        self.assertEqual(data['vat_amount'], Decimal(1000))
        self.assertEqual(data['merchant'], '가맹점')
        data = extract_draft('2026-10-24\n2026-10-25\n합계 11,000\n부가세 1,000')
        self.assertNotIn('date', data)
        self.assertEqual(data['amount'], Decimal(10000))
        self.assertNotIn('amount', extract_draft('합계 11,000'))

    def test_draft_display_create_and_idempotency(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['form'].initial['amount'], Decimal(10000))
        self.assertFalse(Voucher.objects.exists())
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.status_code == 200 else '')
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.kind, 'expense')
        self.assertEqual(voucher.entry_type, 'expense')
        self.assertEqual(voucher.owner, self.user)
        self.assertEqual(voucher.partner, '가맹점')
        self.assertEqual(voucher.gross_amount, Decimal(11000))
        self.item.refresh_from_db()
        self.assertEqual(self.item.voucher, voucher)
        self.assertEqual(self.item.status, 'completed')
        self.client.post(self.url, self.data())
        self.assertEqual(Voucher.objects.count(), 1)

    def test_invalid_totals_confirmation_and_tenant_access(self):
        for data, error in [(self.data(receipt_total='12000'), 'receipt_total'), (self.data(confirmed=''), 'confirmed'),
                            (self.data(vat_amount=''), 'vat_amount')]:
            response = self.client.post(self.url, data)
            self.assertIn(error, response.context['form'].errors)
        self.assertFalse(Voucher.objects.exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'review')
        other = get_user_model().objects.create_user(username='other-draft')
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 404)

    def test_unrecognized_fields_remain_blank(self):
        self.item.ocr_text = '읽을 수 있는 글자만 있음'
        self.item.save()
        response = self.client.get(self.url)
        self.assertIsNone(response.context['form']['date'].value())
        self.assertIsNone(response.context['form']['vat_amount'].value())

    def test_account_names_and_code_labels_can_be_typed(self):
        expense = Account.objects.get(pk='6505')
        settlement = Account.objects.get(pk='1101')
        response = self.client.post(self.url, self.data(account_master=expense.name, settlement_account=str(settlement)))
        self.assertEqual(response.status_code, 302)
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.account_master, expense)
        self.assertEqual(voucher.settlement_account, settlement)

    def test_typed_accounts_cannot_bypass_allowed_categories_or_usage(self):
        AccountPreference.objects.create(owner=self.user, account_id='6505', is_active=False)
        response = self.client.post(self.url, self.data(account_master=Account.objects.get(pk='6505').name))
        self.assertIn('account_master', response.context['form'].errors)
        response = self.client.post(self.url, self.data(account_master='1101', settlement_account='6505'))
        self.assertIn('account_master', response.context['form'].errors)
        self.assertIn('settlement_account', response.context['form'].errors)
        self.assertFalse(Voucher.objects.exists())

    def test_creation_quota_tenth_allowed_eleventh_rejected_and_counter_persistent(self):
        quota = ReceiptCreationUsage.objects.create(owner=self.user, generated_count=9)
        response = self.client.get(reverse('receipt_history'))
        self.assertEqual(response.context['receipt_remaining'], 1)
        self.client.post(self.url, self.data())
        quota.refresh_from_db()
        self.assertEqual(quota.generated_count, 10)
        self.client.post(self.url, self.data())
        quota.refresh_from_db()
        self.assertEqual(quota.generated_count, 10)
        # Removing the generated voucher does not restore the allowance.
        Voucher.objects.get().delete()
        next_item = ReceiptPhoto.objects.create(owner=self.user, photo='another.jpg', image_type='image/jpeg',
            original_name='another.jpg', ocr_text=self.item.ocr_text)
        response = self.client.post(reverse('receipt_expense', args=[next_item.pk]), self.data())
        self.assertContains(response, '0/10')
        self.assertFalse(Voucher.objects.exists())
        next_item.refresh_from_db()
        self.assertEqual(next_item.status, 'review')
        self.assertEqual(self.client.get(reverse('receipt_history')).context['receipt_remaining'], 0)

    def test_admin_unlimited_and_invalid_post_does_not_consume_allowance(self):
        self.client.post(self.url, self.data(confirmed=''))
        self.assertFalse(ReceiptCreationUsage.objects.exists())
        ReceiptCreationUsage.objects.create(owner=self.user, generated_count=15)
        self.user.is_staff = True
        self.user.save()
        self.assertFalse(self.client.get(reverse('receipt_history')).context['receipt_limited'])
        self.client.post(self.url, self.data())
        self.assertEqual(Voucher.objects.count(), 1)

    def test_existing_completed_receipts_count_toward_allowance(self):
        for _ in range(10):
            ReceiptPhoto.objects.create(owner=self.user, photo='old.jpg', image_type='image/jpeg', original_name='old.jpg', status='completed')
        self.assertEqual(self.client.get(reverse('receipt_history')).context['receipt_remaining'], 0)
        self.client.post(self.url, self.data())
        self.assertFalse(Voucher.objects.exists())
