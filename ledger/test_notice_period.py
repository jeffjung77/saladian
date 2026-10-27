from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Notice
from .system_views import NoticeForm


class NoticePeriodTests(TestCase):
    def test_period_boundaries_visibility_and_admin_access(self):
        User = get_user_model()
        admin = User.objects.create_user(username='period-admin', is_superuser=True)
        member = User.objects.create_user(username='period-member')
        today = timezone.localdate()
        active = Notice.objects.create(author=admin, title='Today', body='Active', published=True, start_date=today, end_date=today)
        future = Notice.objects.create(author=admin, title='Future', body='Scheduled', published=True, start_date=today+timedelta(days=1))
        expired = Notice.objects.create(author=admin, title='Expired', body='Old', published=True, end_date=today-timedelta(days=1))
        unlimited = Notice.objects.create(author=admin, title='Unlimited', body='Forever', published=True)
        self.assertEqual(set(Notice.objects.active()), {active, unlimited})
        self.assertEqual(future.publication_status, '게시 예정')
        self.assertEqual(expired.publication_status, '기간 종료')
        self.client.force_login(member)
        page = self.client.get(reverse('board_list'))
        self.assertEqual(set(page.context['notices']), {active, unlimited})
        self.assertEqual(set(page.context['popup_notices']), {active, unlimited})
        for notice in (future, expired):
            self.assertEqual(self.client.get(reverse('notice_detail', args=[notice.pk])).status_code, 404)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse('notice_detail', args=[expired.pk])).status_code, 200)
        form = NoticeForm({'title': 'Invalid', 'body': 'Test', 'published': True, 'start_date': today, 'end_date': today-timedelta(days=1)})
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)
