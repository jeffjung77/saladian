from datetime import datetime, timezone as dt_timezone
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import AuditLog, Subscription, Voucher
from .test_helpers import AuthenticatedLedgerTestCase


class AuditTests(AuthenticatedLedgerTestCase):
    def subscription(self, user=None):
        return Subscription.objects.create(user=user or self.user, company_name='로그 업체', business_number='123-45-67890',
            business_address='주소', business_phone='02-1234-5678', email='private@example.test', contact_name='개인 담당자', contact_phone='010-1234-5678')

    def test_login_failure_success_logout_without_recording_passwords(self):
        self.user.set_password('SecretAudit!887766')
        self.user.save()
        self.subscription()
        client = Client()
        client.post(reverse('login'), {'username': self.user.username, 'password': 'WrongSensitivePassword!'})
        failed = AuditLog.objects.filter(action='login').latest('pk')
        self.assertEqual(failed.result, 'invalid')
        client.post(reverse('login'), {'username': self.user.username, 'password': 'SecretAudit!887766'})
        logged_in = AuditLog.objects.filter(action='login').latest('pk')
        self.assertEqual(logged_in.actor_id, self.user.pk)
        self.assertEqual(logged_in.company_name, '로그 업체')
        self.assertEqual(logged_in.result, 'success')
        client.post(reverse('logout'))
        self.assertEqual(AuditLog.objects.filter(action='logout').latest('pk').actor_id, self.user.pk)
        stored = str(list(AuditLog.objects.values()))
        for secret in ['SecretAudit!887766', 'WrongSensitivePassword!', 'private@example.test', '개인 담당자']:
            self.assertNotIn(secret, stored)

    def test_voucher_create_update_delete_and_view_targets_are_logged(self):
        self.subscription()
        data = {'date': '2026-10-24', 'account_master': '5001', 'settlement_account': '1101', 'amount': '1000', 'memo': '비공개 적요 내용'}
        self.client.post(reverse('sales_new'), data)
        voucher = Voucher.objects.get()
        created = AuditLog.objects.filter(action='create', resource='매출전표').get()
        self.assertEqual(created.target, str(voucher.pk))
        self.assertEqual(created.company_user_id, self.user.pk)
        self.client.post(reverse('voucher_edit', args=[voucher.pk]), data)
        self.assertTrue(AuditLog.objects.filter(action='update', resource='전표', target=str(voucher.pk)).exists())
        self.client.get(reverse('dashboard'), {'search': '검색어-비공개'})
        self.assertEqual(AuditLog.objects.latest('pk').path, reverse('dashboard'))
        self.client.post(reverse('voucher_delete', args=[voucher.pk]))
        deleted = AuditLog.objects.filter(action='delete').get()
        self.assertEqual(deleted.target, str(voucher.pk))
        self.assertEqual(deleted.company_name, '로그 업체')
        self.assertFalse(Voucher.objects.exists())
        self.assertNotIn('비공개 적요 내용', str(list(AuditLog.objects.values())))

    def test_system_admin_target_company_filters_dates_and_readonly_permissions(self):
        item = self.subscription()
        admin = get_user_model().objects.create_user(username='audit-admin', is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        data = {name: getattr(item, name) for name in ['company_name', 'business_number', 'business_address', 'business_phone', 'email', 'contact_name', 'contact_phone']}
        self.client.post(reverse('subscription_edit', args=[item.pk]), data)
        event = AuditLog.objects.filter(action='update', resource='구독정보').get()
        self.assertEqual(event.actor_id, admin.pk)
        self.assertEqual(event.company_user_id, self.user.pk)
        self.assertEqual(event.company_name, '로그 업체')
        AuditLog.objects.filter(pk=event.pk).update(occurred_at=datetime(2026, 10, 23, 15, 1, tzinfo=dt_timezone.utc))
        url = reverse('audit_logs')
        response = self.client.get(url, {'company': '로그 업체', 'username': 'audit-admin', 'start': '2026-10-24', 'end': '2026-10-24', 'action': 'update'})
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertContains(response, '00:01:00')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertContains(self.client.get(reverse('voucher_entry')), url)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), '권한이 없습니다. 시스템관리자에게 문의하세요.', status_code=403)
        self.assertEqual(AuditLog.objects.filter(actor=self.user).latest('pk').result, 'denied')
        self.assertEqual(Client().get(url).status_code, 302)

    def test_validation_errors_filters_and_pagination(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=['is_staff', 'is_superuser'])
        self.client.post(reverse('sales_new'), {})
        self.assertTrue(AuditLog.objects.filter(action='create', result='invalid').exists())
        for i in range(55):
            AuditLog.objects.create(actor=self.user, actor_name=self.user.username, company_name='페이지 업체', action='view',
                resource='테스트', method='GET', status_code=200, result='success', path='/test/')
        response = self.client.get(reverse('audit_logs'), {'company': '페이지 업체', 'page': 2})
        self.assertEqual(len(response.context['page']), 5)
        self.assertEqual(response.context['page'].number, 2)
        response = self.client.get(reverse('audit_logs'), {'start': '2026-10-25', 'end': '2026-10-24'})
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertEqual(response.context['page'].paginator.count, 0)
