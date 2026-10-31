from io import BytesIO
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from PIL import Image
from .models import ReceiptPhoto, Voucher
from .test_helpers import AuthenticatedLedgerTestCase
from unittest.mock import patch
from .receipt_ocr import ReceiptOCRError


class ReceiptTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.storage.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def photo(self):
        data = BytesIO()
        Image.new('RGB', (10, 10), 'white').save(data, format='JPEG')
        return SimpleUploadedFile('receipt.jpg', data.getvalue(), content_type='image/jpeg')

    def test_page_upload_preview_and_history(self):
        self.assertContains(self.client.get(reverse('voucher_entry')), reverse('receipt_home'))
        response = self.client.get(reverse('receipt_home'))
        self.assertContains(response, 'capture="environment"')
        for label in ['영수증 촬영', '사진 선택', '처리 내역']:
            self.assertContains(response, label)
        self.assertRedirects(self.client.post(reverse('receipt_home'), {'photo': self.photo(), 'status': 'completed'}), reverse('receipt_history'))
        item = ReceiptPhoto.objects.get()
        self.assertEqual(item.owner, self.user)
        self.assertEqual(item.status, 'review')
        self.assertFalse(Voucher.objects.exists())
        self.assertContains(self.client.get(reverse('receipt_history')), 'receipt.jpg')
        self.assertNotContains(self.client.get(reverse('receipt_history'), {'status': 'completed'}), 'receipt.jpg')
        response = self.client.get(reverse('receipt_photo', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertIn('no-store', response['Cache-Control'])
        if response.streaming:
            b''.join(response.streaming_content)

    def test_photos_and_history_are_owner_only(self):
        self.client.post(reverse('receipt_home'), {'photo': self.photo()})
        item = ReceiptPhoto.objects.get()
        other = get_user_model().objects.create_user(username='receipt-other', is_staff=True, is_superuser=True)
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse('receipt_history')), 'receipt.jpg')
        self.assertEqual(self.client.get(reverse('receipt_photo', args=[item.pk])).status_code, 404)
        for name in ['receipt_home', 'receipt_history']:
            self.assertEqual(Client().get(reverse(name)).status_code, 302)

    def test_up_to_ten_photos_and_all_files_validated(self):
        url = reverse('receipt_home')
        response = self.client.post(url, {'photo': [self.photo() for _ in range(10)]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReceiptPhoto.objects.filter(owner=self.user).count(), 10)
        response = self.client.post(url, {'photo': [self.photo() for _ in range(11)]})
        self.assertIn('photo', response.context['form'].errors)
        self.assertEqual(ReceiptPhoto.objects.count(), 10)

        response = self.client.post(url, {'photo': [self.photo(), SimpleUploadedFile('bad.jpg', b'not an image')]})
        self.assertIn('photo', response.context['form'].errors)
        self.assertEqual(ReceiptPhoto.objects.count(), 10)

    def test_history_ten_per_page_and_status_filter(self):
        for i in range(23):
            ReceiptPhoto.objects.create(owner=self.user, photo='test.jpg', image_type='image/jpeg', original_name=f'page-{i}.jpg')
        ReceiptPhoto.objects.create(owner=self.user, photo='failed.jpg', image_type='image/jpeg', original_name='failed.jpg', status='failed')
        url = reverse('receipt_history')
        response = self.client.get(url, {'status': 'review'})
        self.assertEqual(len(response.context['page']), 10)
        self.assertEqual(response.context['page'].paginator.count, 23)
        first = {item.pk for item in response.context['page']}
        self.assertContains(response, 'status=review&amp;page=2')
        response = self.client.get(url, {'status': 'review', 'page': 2})
        self.assertEqual(len(response.context['page']), 10)
        self.assertFalse(first & {item.pk for item in response.context['page']})
        response = self.client.get(url, {'status': 'review', 'page': 3})
        self.assertEqual(len(response.context['page']), 3)

    def test_invalid_file_and_missing_file_rejected_and_csrf_required(self):
        url = reverse('receipt_home')
        for data in [{}, {'photo': SimpleUploadedFile('fake.jpg', b'<script>alert(1)</script>', content_type='image/jpeg')}]:
            response = self.client.post(url, data)
            self.assertIn('photo', response.context['form'].errors)
        self.assertFalse(ReceiptPhoto.objects.exists())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url, {'photo': self.photo()}).status_code, 403)

    @patch('ledger.receipt_views.recognize_receipt')
    def test_ocr_success_safe_result_and_duplicate_guard(self, recognize):
        self.client.post(reverse('receipt_home'), {'photo': self.photo()})
        item = ReceiptPhoto.objects.get()
        recognize.return_value = '합계 11,000원\n<script>bad</script>'
        url = reverse('receipt_analyze', args=[item.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse('receipt_detail', args=[item.pk]))
        item.refresh_from_db()
        self.assertEqual(item.ocr_text, recognize.return_value)
        self.assertEqual(item.status, 'review')
        self.assertIsNotNone(item.analyzed_at)
        response = self.client.get(reverse('receipt_detail', args=[item.pk]))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>bad</script>')
        item.status = 'processing'
        item.save()
        self.client.post(url)
        self.assertEqual(recognize.call_count, 1)
        self.assertFalse(Voucher.objects.exists())

    @patch('ledger.receipt_views.recognize_receipt')
    def test_failure_retry_and_owner_scope(self, recognize):
        self.client.post(reverse('receipt_home'), {'photo': self.photo()})
        item = ReceiptPhoto.objects.get()
        url = reverse('receipt_analyze', args=[item.pk])
        recognize.side_effect = ReceiptOCRError('글자를 찾지 못했습니다.')
        self.client.post(url)
        item.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertEqual(item.ocr_error, '글자를 찾지 못했습니다.')
        recognize.side_effect = None
        recognize.return_value = '재분석 성공'
        self.client.post(url)
        item.refresh_from_db()
        self.assertEqual(item.status, 'review')
        self.assertEqual(item.ocr_error, '')
        other = get_user_model().objects.create_user(username='foreign-ocr')
        self.client.force_login(other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.get(reverse('receipt_detail', args=[item.pk])).status_code, 404)
        self.assertEqual(recognize.call_count, 2)

    @patch('ledger.receipt_ocr.vision.ImageAnnotatorClient')
    def test_vision_adapter(self, factory):
        from types import SimpleNamespace
        from .receipt_ocr import recognize_receipt
        self.client.post(reverse('receipt_home'), {'photo': self.photo()})
        client = factory.return_value
        client.document_text_detection.return_value = SimpleNamespace(error=SimpleNamespace(message=''), full_text_annotation=SimpleNamespace(text=' 가맹점 합계 1000 '))
        self.assertEqual(recognize_receipt(ReceiptPhoto.objects.get().photo), '가맹점 합계 1000')
        self.assertEqual(client.document_text_detection.call_args.kwargs['timeout'], 25)
        client.transport.close.assert_called_once()
