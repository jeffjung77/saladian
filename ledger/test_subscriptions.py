from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.urls import reverse
from .models import BusinessProfile, Subscription
from .test_helpers import AuthenticatedLedgerTestCase


class SubscriptionTests(AuthenticatedLedgerTestCase):
    def data(self, **overrides):
        data = {'company_name': '구독 업체', 'business_number': '1234567890', 'business_address': '서울 송파구',
                'business_phone': '02-1234-5678', 'email': 'subscription@example.test', 'contact_name': '담당', 'contact_phone': '010-1234-5678'}
        data.update(overrides)
        return data

    def test_registration_creates_one_subscription_and_admin_can_edit(self):
        self.assertRedirects(self.client.post(reverse('member_registration'), self.data()), reverse('member_registration'))
        item = Subscription.objects.get(user=self.user)
        self.assertEqual(item.business_number, '123-45-67890')
        self.client.post(reverse('member_registration'), self.data(company_name='변경 업체'))
        self.assertEqual(Subscription.objects.count(), 1)
        admin = get_user_model().objects.create_user(username='subscription-admin', is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        url = reverse('subscription_list')
        response = self.client.get(url, {'q': '변경 업체'})
        self.assertContains(response, '변경 업체')
        self.assertEqual(response.context['total'], 1)
        self.assertIn('no-store', response.headers['Cache-Control'])
        edit = reverse('subscription_edit', args=[item.pk])
        self.assertRedirects(self.client.post(edit, self.data(company_name='관리 수정', user=admin.pk)), url)
        item.refresh_from_db()
        self.assertEqual(item.user_id, self.user.pk)
        self.assertEqual(item.company_name, '관리 수정')
        self.assertNotContains(self.client.get(reverse('member_list')), '관리 수정')
        response = self.client.post(edit, self.data(business_phone='bad'))
        self.assertIn('business_phone', response.context['form'].errors)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('member_registration')), '관리 수정')
        self.assertContains(self.client.get(reverse('voucher_entry')), '업체명: 관리 수정')

    def test_subscription_management_is_system_admin_only_and_csrf_protected(self):
        self.client.post(reverse('member_registration'), self.data())
        item = Subscription.objects.get()
        for staff in [False, True]:
            self.user.is_staff = staff
            self.user.save(update_fields=['is_staff'])
            for url in [reverse('subscription_list'), reverse('subscription_edit', args=[item.pk])]:
                self.assertEqual(Client().get(url).status_code, 302)
                self.assertContains(self.client.get(url), '권한이 없습니다. 시스템관리자에게 문의하세요.', status_code=403)
            self.assertEqual(self.client.post(reverse('subscription_edit', args=[item.pk]), self.data()).status_code, 403)
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(reverse('subscription_edit', args=[item.pk]), self.data()).status_code, 403)
        self.assertContains(self.client.get(reverse('voucher_entry')), reverse('subscription_list'))

    def test_backfill_only_complete_legacy_profiles_and_is_idempotent(self):
        self.user.email = 'legacy@example.test'
        self.user.save(update_fields=['email'])
        values = self.data()
        values.pop('email')
        BusinessProfile.objects.create(user=self.user, **values)
        other = get_user_model().objects.create_user(username='incomplete-profile')
        BusinessProfile.objects.create(user=other, company_name='未完了')
        migrate = import_module('ledger.migrations.0022_migrate_completed_subscriptions').copy_completed
        for _ in range(2):
            migrate(apps, SimpleNamespace(connection=connection))
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(Subscription.objects.get().email, 'legacy@example.test')
        self.assertEqual(BusinessProfile.objects.count(), 2)
