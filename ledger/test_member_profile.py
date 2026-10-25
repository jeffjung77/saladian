from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import BusinessProfile
from .test_helpers import AuthenticatedLedgerTestCase


class MemberProfileTests(AuthenticatedLedgerTestCase):
    def test_password_change_requires_current_password_and_preserves_session(self):
        self.user.set_password('OriginalSecret!7788')
        self.user.save()
        self.client.force_login(self.user)
        url = reverse('member_profile')
        response = self.client.get(url)
        self.assertContains(response, reverse('member_registration'))
        self.assertNotContains(response, 'id="id_company_name"')
        self.assertNotContains(response, 'id="profile-grade"')
        data = {'old_password': 'wrong', 'new_password1': 'ChangedSecret!9944', 'new_password2': 'ChangedSecret!9944'}
        self.assertIn('old_password', self.client.post(url, data).context['form'].errors)
        data['old_password'] = 'OriginalSecret!7788'
        data['new_password2'] = 'mismatch'
        self.assertIn('new_password2', self.client.post(url, data).context['form'].errors)
        data['new_password2'] = data['new_password1']
        self.assertRedirects(self.client.post(url, data), url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ChangedSecret!9944'))
        self.assertFalse(self.user.check_password('OriginalSecret!7788'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.assertEqual(Client().get(url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url, data).status_code, 403)

    def test_update_own_profile_without_changing_permissions(self):
        other = get_user_model().objects.create_user(username='profile-other', email='other@example.test')
        BusinessProfile.objects.create(user=other, company_name='다른 업체')
        url = reverse('member_registration')
        self.assertContains(self.client.get(reverse('member_profile')), url)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(BusinessProfile.objects.filter(user=self.user).exists())
        data = {'company_name': '내 업체', 'business_number': '1234567890', 'contact_name': '담당자',
                'business_type': '서비스업', 'business_category': '컨설팅',
                'contact_phone': '010-1234-5678', 'email': 'me@example.test', 'business_address': '서울시 송파구', 'business_phone': '02-1234-5678', 'user': other.pk, 'is_superuser': 'on', 'username': 'forged'}
        self.assertRedirects(self.client.post(url, data), url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.email, 'me@example.test')
        self.assertEqual(self.user.subscription.company_name, '내 업체')
        self.assertEqual(self.user.subscription.business_number, '123-45-67890')
        self.assertEqual(self.user.subscription.business_address, data['business_address'])
        self.assertEqual(self.user.subscription.business_phone, data['business_phone'])
        self.assertFalse(self.user.is_superuser)
        self.assertEqual(other.business_profile.company_name, '다른 업체')
        self.assertContains(self.client.get(reverse('voucher_entry')), '업체명: 내 업체')

    def test_optional_fields_validation_authentication_and_csrf(self):
        url = reverse('member_registration')
        self.assertEqual(Client().get(url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url, {}).status_code, 403)
        for field, value in [('email', 'bad'), ('business_number', '123'), ('contact_phone', 'abc')]:
            response = self.client.post(url, {field: value})
            self.assertIn(field, response.context['form'].errors)
        response = self.client.post(url, {})
        self.assertEqual(set(response.context['form'].errors), {'company_name', 'business_number', 'business_type', 'business_category', 'business_address', 'business_phone', 'email', 'contact_name', 'contact_phone'})
        self.assertTrue(all(field.required for field in response.context['form'].fields.values()))
