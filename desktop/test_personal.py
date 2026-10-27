from io import BytesIO
from unittest import skipUnless
from unittest.mock import patch
from PIL import Image
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from ledger.models import Voucher, ReceiptPhoto


@skipUnless(getattr(settings, 'DESKTOP_MODE', False), 'Personal edition settings required')
class PersonalEditionTests(TestCase):
    def setup_personal(self):
        response = self.client.post('/desktop/setup/', {'username': 'owner', 'company_name': '내 업체',
            'password1': 'Personal-Only!48290', 'password2': 'Personal-Only!48290'})
        self.assertEqual(response.status_code, 302)
        return get_user_model().objects.get(username='owner')

    def test_first_run_single_account_and_cloud_routes_denied(self):
        self.assertRedirects(self.client.get('/'), '/desktop/setup/')
        user = self.setup_personal()
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertContains(self.client.get('/vouchers/'), '개인 PC용')
        for url in ['/board/', '/system/members/', '/accounts/signup/', '/accounts/registration/', '/admin/']:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get('/desktop/setup/').status_code, 302)
        self.assertNotContains(Client().get('/accounts/login/'), '회원가입')
        self.assertEqual(Client(enforce_csrf_checks=True).post('/desktop/setup/', {}).status_code, 403)

    def test_offline_vouchers_reports_and_excel(self):
        self.setup_personal()
        for route, code, kind in [('sales_new', '5001', 'income'), ('expense_new', '6505', 'expense')]:
            result = self.client.post(reverse(route), {'date': '2026-10-26', 'kind': kind,
                'account_master': code, 'settlement_account': '1101', 'amount': '10000', 'memo': '로컬 입력'})
            self.assertEqual(result.status_code, 302)
        from ledger.tests import journal_data
        self.assertEqual(self.client.post(reverse('voucher_new'), journal_data()).status_code, 302)
        self.assertEqual(Voucher.objects.count(), 3)
        for route in ('income_statement', 'balance_sheet', 'dashboard', 'account_ledger', 'partner_ledger'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        result = self.client.get(reverse('income_statement'), {'start': '2026-01-01', 'end': '2026-12-31', 'export': 'xlsx'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content[:2], b'PK')

    def test_local_photo_storage_and_google_only_on_explicit_analyze(self):
        self.setup_personal()
        photo = BytesIO()
        Image.new('RGB', (8, 8), 'white').save(photo, 'PNG')
        with patch('ledger.receipt_views.recognize_receipt', return_value='상호: 가맹점\n합계 1000') as recognize:
            response = self.client.post(reverse('receipt_home'), {'photo': SimpleUploadedFile('local.png', photo.getvalue(), content_type='image/png')})
            self.assertEqual(response.status_code, 302)
            item = ReceiptPhoto.objects.get()
            self.addCleanup(item.photo.delete, False)
            recognize.assert_not_called()
            response = self.client.get(reverse('receipt_photo', args=[item.pk]))
            self.assertEqual(response.status_code, 200)
            response.close()
            self.assertEqual(self.client.post(reverse('receipt_analyze', args=[item.pk])).status_code, 302)
            recognize.assert_called_once()

    def test_no_embedded_google_credentials_or_quota(self):
        user = self.setup_personal()
        from ledger.voucher_quota import limits_for
        self.assertTrue(all(value is None for value in limits_for(user).values()))
        from ledger.receipt_ocr import recognize_receipt
        from google.auth.exceptions import DefaultCredentialsError
        with patch('pathlib.Path.is_file', return_value=False):
            with self.assertRaises(DefaultCredentialsError):
                recognize_receipt(None)
