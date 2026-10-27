from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import BusinessProfile
from .test_helpers import AuthenticatedLedgerTestCase


class SystemMemberTests(AuthenticatedLedgerTestCase):
    def test_system_admin_can_change_member_grade_without_changing_other_data(self):
        self.make_staff()
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        member = get_user_model().objects.create_user(username='grade-target', password='OriginalSecret!123', email='target@example.test')
        url = reverse('member_grade', args=[member.pk])
        self.assertContains(self.client.get(reverse('member_list')), url)
        self.assertContains(self.client.get(url), 'grade-target')
        for grade, staff, superuser in [('2', True, False), ('3', True, True), ('1', False, False)]:
            self.assertRedirects(self.client.post(url, {'grade': grade, 'username': 'forged', 'is_active': ''}), reverse('member_list'))
            member.refresh_from_db()
            self.assertEqual((member.is_staff, member.is_superuser), (staff, superuser))
            self.assertEqual(member.username, 'grade-target')
            self.assertEqual(member.email, 'target@example.test')
            self.assertTrue(member.is_active)
            self.assertTrue(member.check_password('OriginalSecret!123'))
        response = self.client.post(url, {'grade': '9'})
        self.assertIn('grade', response.context['form'].errors)
        self.assertEqual(self.client.get(reverse('member_grade', args=[999999])).status_code, 404)

    def test_member_grade_permissions_and_csrf(self):
        url = reverse('member_grade', args=[self.user.pk])
        self.assertEqual(Client().get(url).status_code, 302)
        for staff in [False, True]:
            self.user.is_staff = staff
            self.user.save(update_fields=['is_staff'])
            for method in [self.client.get, self.client.post]:
                self.assertContains(method(url, {'grade': '3'}), '권한이 없습니다. 시스템관리자에게 문의하세요.', status_code=403)
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(url, {'grade': '1'}).status_code, 403)

    def test_last_system_admin_is_preserved_and_self_demotion_works_with_successor(self):
        self.make_staff()
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        url = reverse('member_grade', args=[self.user.pk])
        response = self.client.post(url, {'grade': '1'})
        self.assertIn('grade', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser)
        get_user_model().objects.create_user(username='successor', is_staff=True, is_superuser=True)
        self.assertRedirects(self.client.post(url, {'grade': '1'}), reverse('business_overview'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def data(self, **overrides):
        data = {'username': 'new-system-member', 'email': 'new@example.test',
                'company_name': '신규 업체', 'business_number': '1234567890',
                'contact_name': '담당자', 'contact_phone': '010-1234-5678',
                'password1': 'NewMember!Secure24680', 'password2': 'NewMember!Secure24680'}
        data.update(overrides)
        return data

    def make_staff(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])

    def test_only_system_administrator_can_assign_privileged_grades(self):
        self.make_staff()
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        for grade, staff, superuser in [('1', False, False), ('2', True, False), ('3', True, True)]:
            response = self.client.post(reverse('system_signup'), self.data(username=f'grade-{grade}', grade=grade))
            self.assertRedirects(response, reverse('member_list'))
            created = get_user_model().objects.get(username=f'grade-{grade}')
            self.assertEqual(created.is_staff, staff)
            self.assertEqual(created.is_superuser, superuser)
        response = self.client.post(reverse('system_signup'), self.data(username='bad-grade', grade='4'))
        self.assertIn('grade', response.context['form'].errors)
        self.assertFalse(get_user_model().objects.filter(username='bad-grade').exists())
        self.assertContains(self.client.get(reverse('member_list')), '3. 시스템관리자')

    def test_public_and_staff_cannot_forge_privileged_grade(self):
        response = Client().post(reverse('signup'), self.data(username='public-grade', grade='3'))
        self.assertRedirects(response, reverse('login'))
        self.make_staff()
        self.assertEqual(self.client.post(reverse('system_signup'), self.data(username='staff-grade', grade='3')).status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username='staff-grade').exists())
        member = get_user_model().objects.get(username='public-grade')
        self.assertFalse(member.is_staff)
        self.assertFalse(member.is_superuser)

    def test_access_requires_authenticated_staff_and_csrf(self):
        for name in ['system_signup', 'member_list']:
            url = reverse(name)
            self.assertEqual(Client().get(url).status_code, 302)
            response = self.client.get(url)
            self.assertContains(response, '권한이 없습니다. 시스템관리자에게 문의하세요.', status_code=403)
        self.assertEqual(self.client.post(reverse('system_signup'), self.data()).status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username='new-system-member').exists())
        self.make_staff()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse('system_signup'), self.data()).status_code, 403)

    def test_staff_registration_preserves_session_and_validates(self):
        self.make_staff()
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        url = reverse('system_signup')
        self.assertContains(self.client.get(url), reverse('check_username'))
        self.assertRedirects(self.client.post(url, self.data(grade='1', is_staff='on', is_superuser='on')), reverse('member_list'))
        created = get_user_model().objects.get(username='new-system-member')
        self.assertTrue(created.check_password(self.data()['password1']))
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertEqual(created.business_profile.company_name, '신규 업체')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        response = self.client.post(url, self.data())
        self.assertIn('username', response.context['form'].errors)
        response = self.client.post(url, self.data(username='missing-company', company_name=''))
        self.assertIn('company_name', response.context['form'].errors)
        self.assertFalse(get_user_model().objects.filter(username='missing-company').exists())

    def test_member_list_search_status_pagination_and_missing_profile(self):
        self.make_staff()
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        member = get_user_model().objects.create_user(username='inactive-member', email='inactive@example.test', is_active=False)
        BusinessProfile.objects.create(user=member, company_name='조회 대상 업체', business_number='123-45-67890', contact_name='담당자', contact_phone='010-0000-1234')
        url = reverse('member_list')
        response = self.client.get(url)
        self.assertEqual(response.context['total'], 2)
        self.assertEqual(response.context['inactive'], 1)
        self.assertNotContains(response, '조회 대상 업체')
        self.assertContains(response, self.user.username)
        self.assertIn('no-store', response.headers['Cache-Control'])
        for query in ['inactive-member']:
            response = self.client.get(url, {'q': query})
            self.assertEqual(response.context['page'].paginator.count, 1)
        get_user_model().objects.bulk_create([get_user_model()(username=f'page-member-{i}') for i in range(25)])
        response = self.client.get(url, {'page': 2})
        self.assertEqual(response.context['page'].number, 2)
        self.assertEqual(len(response.context['page']), 10)
