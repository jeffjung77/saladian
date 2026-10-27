from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Subscription, Notice, AuditLog


class SystemPageSizeTests(TestCase):
    def test_all_seven_lists_support_sizes_and_filter_links(self):
        User = get_user_model()
        admin = User.objects.create_user(username='size-admin', is_superuser=True)
        for index in range(12):
            member = User.objects.create_user(username=f'size-user-{index:02d}')
            Subscription.objects.create(user=member, company_name=f'Size Company {index}')
            Notice.objects.create(author=admin, title=f'Size Notice {index}', body='Test')
            AuditLog.objects.create(actor=admin, actor_name=admin.username, action='view', resource='Size', method='GET', status_code=200, result='success', path='/size-test/')
        self.client.force_login(admin)
        for name in ['member_list', 'subscription_list', 'company_list', 'user_voucher_counts', 'credit_list', 'notice_management', 'audit_logs']:
            with self.subTest(name=name):
                first = self.client.get(reverse(name), {'per_page': 5})
                self.assertEqual(first.status_code, 200)
                self.assertEqual(len(first.context['page']), 5)
                self.assertContains(first, '페이지당 표시')
                self.assertContains(first, 'per_page=5&amp;page=2')
                second = self.client.get(reverse(name), {'per_page': 5, 'page': 2})
                self.assertEqual(second.context['page'].number, 2)
                self.assertEqual(len(second.context['page']), 5)
                self.assertEqual(len(self.client.get(reverse(name), {'per_page': 10}).context['page']), 10)
                self.assertEqual(self.client.get(reverse(name), {'per_page': 'invalid'}).context['page'].paginator.per_page, 10)
