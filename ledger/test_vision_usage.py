from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import ReceiptPhoto, VisionUsage
from .test_helpers import AuthenticatedLedgerTestCase


class VisionUsageTests(AuthenticatedLedgerTestCase):
    def test_records_requests_retries_failure_and_no_duplicate(self):
        item = ReceiptPhoto.objects.create(owner=self.user, photo='sample.jpg', original_name='sample.jpg', image_type='image/jpeg')
        def recognize(photo, on_request):
            on_request()
            return '합계 1000'
        url = reverse('receipt_analyze', args=[item.pk])
        with patch('ledger.receipt_views.recognize_receipt', side_effect=recognize):
            self.client.post(url)
            self.client.post(url)
        events = list(VisionUsage.objects.order_by('pk'))
        self.assertEqual(len(events), 2)
        self.assertFalse(events[0].is_retry)
        self.assertTrue(events[1].is_retry)
        self.assertTrue(all(e.result == 'success' and e.api_attempted for e in events))
        with patch('ledger.receipt_views.recognize_receipt', side_effect=OSError()):
            self.client.post(url)
        event = VisionUsage.objects.latest('pk')
        self.assertEqual(event.result, 'failed')
        self.assertFalse(event.api_attempted)
        ReceiptPhoto.objects.filter(pk=item.pk).update(status='processing', ocr_started_at=timezone.now())
        self.client.post(url)
        self.assertEqual(VisionUsage.objects.count(), 3)

    def test_system_admin_only_and_company_period_aggregation(self):
        url = reverse('vision_usage')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.user.is_superuser = True
        self.user.save()
        other = get_user_model().objects.create_user(username='vision-other')
        VisionUsage.objects.create(owner=self.user, result='success', api_attempted=True)
        VisionUsage.objects.create(owner=self.user, result='failed', is_retry=True)
        old = VisionUsage.objects.create(owner=self.user, result='success', api_attempted=True)
        VisionUsage.objects.filter(pk=old.pk).update(requested_at=timezone.now()-timedelta(days=70))
        VisionUsage.objects.create(owner=other, result='failed', api_attempted=True)
        today = timezone.localdate().isoformat()
        response = self.client.get(url, {'start': today, 'end': today, 'company': self.user.pk})
        totals = response.context['totals']
        self.assertEqual(totals['requests'], 2)
        self.assertEqual(totals['success'], 1)
        self.assertEqual(totals['failed'], 1)
        self.assertEqual(totals['retries'], 1)
        self.assertEqual(totals['api_attempts'], 1)
        company = list(response.context['page'])[0]
        self.assertEqual(company.requests, 2)
        self.assertEqual(company.api_attempts, 1)
        response = self.client.get(url, {'start': today, 'end': today})
        self.assertEqual(response.context['totals']['requests'], 3)
        response = self.client.get(url, {'start': 'invalid'})
        self.assertEqual(response.context['totals']['requests'], 0)
