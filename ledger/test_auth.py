from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse
from .models import Voucher, BusinessProfile
from .tests import journal_data

User = get_user_model()
TEST_PASSWORD = 'SecureLedger!Test9472'


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='existing', password=TEST_PASSWORD)

    def signup_data(self, **overrides):
        data = {'username': 'newmember', 'email': 'member@example.test', 'password1': TEST_PASSWORD, 'password2': TEST_PASSWORD,
                'company_name': '테스트 업체', 'business_number': '1234567890', 'contact_name': '담당자', 'contact_phone': '010-1234-5678'}
        data.update(overrides)
        return data

    def test_anonymous_redirects_and_public_registration(self):
        for name in ['dashboard', 'sales_new', 'expense_new', 'voucher_new', 'partner_ledger', 'account_ledger', 'balance_sheet', 'income_statement', 'accounts']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse('login') + '?next='))
        self.assertContains(self.client.get(reverse('login')), reverse('signup'))
        self.assertContains(self.client.get(reverse('signup')), '신규 사용자 등록')
        self.assertNotContains(self.client.get(reverse('login')), '우리 가게의 거래 한눈에')

    def test_signup_hashes_password_and_does_not_grant_privileges_or_existing_data(self):
        Voucher.objects.create(date='2026-10-23', kind='income', account='매출', amount=1000)
        data = self.signup_data(is_staff='on', is_superuser='on', owner=self.user.pk)
        self.assertRedirects(self.client.post(reverse('signup'), data), reverse('login'))
        user = User.objects.get(username='newmember')
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertNotEqual(user.password, TEST_PASSWORD)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.vouchers.exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_signup_rejects_duplicate_mismatch_weak_password_and_bad_email(self):
        for data in [self.signup_data(username='existing'), self.signup_data(password2='different'),
                     self.signup_data(password1='12345678', password2='12345678'), self.signup_data(email='invalid')]:
            response = self.client.post(reverse('signup'), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_all_registration_fields_are_required(self):
        response = self.client.get(reverse('signup'))
        fields = response.context['form'].fields
        self.assertEqual(set(fields), {'username', 'grade', 'email', 'company_name', 'business_number', 'contact_name', 'contact_phone', 'password1', 'password2'})
        self.assertTrue(all(field.required for field in fields.values()))
        for name in fields:
            if fields[name].disabled:
                continue
            data = self.signup_data()
            data[name] = ''
            response = self.client.post(reverse('signup'), data)
            self.assertEqual(response.status_code, 200)
            self.assertIn(name, response.context['form'].errors)
        for name in ['company_name', 'contact_name']:
            response = self.client.post(reverse('signup'), self.signup_data(**{name: '   '}))
            self.assertIn(name, response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='newmember').exists())
        self.assertFalse(BusinessProfile.objects.exists())

    def test_username_availability_is_public_and_matches_registration_validation(self):
        url = reverse('check_username')
        response = self.client.get(url, {'username': 'available_member'})
        self.assertTrue(response.json()['available'])
        self.assertEqual(response.json()['username'], 'available_member')
        self.assertIn('no-store', response.headers['Cache-Control'])
        for username in ['existing', 'EXISTING', 'ｅｘｉｓｔｉｎｇ']:
            response = self.client.get(url, {'username': username})
            self.assertFalse(response.json()['available'])
            response = self.client.post(reverse('signup'), self.signup_data(username=username))
            self.assertIn('username', response.context['form'].errors)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(self.client.post(url, {'username': 'available_member'}).status_code, 405)
        self.assertContains(self.client.get(reverse('signup')), 'id="check-username"')

    def test_username_availability_rejects_empty_invalid_and_long_ids(self):
        for username in ['', 'has space', '<script>', 'a' * 151]:
            response = self.client.get(reverse('check_username'), {'username': username})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()['available'])
            self.assertTrue(response.json()['message'])
        self.assertEqual(User.objects.count(), 1)

    def test_signup_rechecks_username_after_availability_check(self):
        self.assertTrue(self.client.get(reverse('check_username'), {'username': 'later_member'}).json()['available'])
        User.objects.create_user(username='later_member')
        response = self.client.post(reverse('signup'), self.signup_data(username='later_member'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(User.objects.filter(username='later_member').count(), 1)
        self.assertFalse(BusinessProfile.objects.exists())

    def test_registration_persists_company_details_for_correct_user(self):
        response = self.client.post(reverse('signup'), self.signup_data())
        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(username='newmember')
        profile = user.business_profile
        self.assertEqual(profile.company_name, '테스트 업체')
        self.assertEqual(profile.business_number, '123-45-67890')
        self.assertEqual(profile.contact_name, '담당자')
        self.assertEqual(profile.contact_phone, '010-1234-5678')
        self.assertEqual(user.email, 'member@example.test')
        self.assertFalse(BusinessProfile.objects.filter(user=self.user).exists())

    def test_business_number_and_contact_formats(self):
        for field, value in [('business_number', '123'), ('business_number', 'abcdefghij'),
                             ('business_number', '123-456-7890'), ('contact_phone', 'abc'),
                             ('contact_phone', '123'), ('contact_phone', '01012345678<script>')]:
            response = self.client.post(reverse('signup'), self.signup_data(**{field: value}))
            self.assertEqual(response.status_code, 200)
            self.assertIn(field, response.context['form'].errors)
        data = self.signup_data(business_number='123-45-67890', contact_phone='+82 10-1234-5678')
        self.assertRedirects(self.client.post(reverse('signup'), data), reverse('login'))
        self.assertEqual(User.objects.get(username='newmember').business_profile.business_number, '123-45-67890')

    def test_profile_failure_rolls_back_account_creation(self):
        from unittest.mock import patch
        with patch('ledger.auth_views.BusinessProfile.objects.create', side_effect=RuntimeError('profile failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('signup'), self.signup_data())
        self.assertFalse(User.objects.filter(username='newmember').exists())
        self.assertFalse(BusinessProfile.objects.exists())

    def test_login_logout_and_unsafe_next(self):
        response = self.client.post(reverse('login'), {'username': 'existing', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('login'), {'username': 'existing', 'password': TEST_PASSWORD, 'next': 'https://untrusted.example/'})
        self.assertRedirects(response, reverse('business_overview'))
        self.assertContains(self.client.get(reverse('dashboard')), 'existing')
        self.assertRedirects(self.client.get(reverse('signup')), reverse('dashboard'))
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_safe_next_and_inactive_user(self):
        response = self.client.post(reverse('login'), {'username': 'existing', 'password': TEST_PASSWORD, 'next': reverse('account_ledger')})
        self.assertRedirects(response, reverse('account_ledger'))
        self.client.logout()
        self.user.is_active = False
        self.user.save()
        self.client.post(reverse('login'), {'username': 'existing', 'password': TEST_PASSWORD})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_authentication_endpoints_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('signup'), self.signup_data()).status_code, 403)
        self.assertEqual(client.post(reverse('login'), {'username': 'existing', 'password': TEST_PASSWORD}).status_code, 403)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('logout')).status_code, 403)


class UserLedgerIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(username='alice')
        cls.bob = User.objects.create_user(username='bob')
        cls.mine = Voucher.objects.create(owner=cls.alice, date='2026-10-23', kind='income', account='매출-용역', account_master_id='5001', settlement_account_id='1101', amount=1000, partner='Alice 거래처', memo='내 전표')
        cls.other = Voucher.objects.create(owner=cls.bob, date='2026-10-23', kind='income', account='매출-용역', account_master_id='5001', settlement_account_id='1101', amount=9000, partner='Bob 거래처', memo='타인 전표')
        cls.legacy = Voucher.objects.create(date='2026-10-23', kind='income', account='기존 전표', amount=7000, partner='기존 거래처')

    def setUp(self):
        self.client.force_login(self.alice)

    def test_dashboard_and_partner_choices_are_private(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['count'], 1)
        self.assertEqual(response.context['income'], 1000)
        self.assertContains(response, '내 전표')
        self.assertNotContains(response, '타인 전표')
        response = self.client.get(reverse('partner_ledger'))
        self.assertContains(response, 'Alice 거래처')
        self.assertNotContains(response, 'Bob 거래처')
        self.assertNotContains(response, '기존 거래처')
        response = self.client.get(reverse('partner_ledger'), {'partner': 'name:Bob 거래처'})
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(response.context['rows'], [])

    def test_other_users_and_legacy_vouchers_cannot_be_accessed_by_id(self):
        for voucher in [self.other, self.legacy]:
            for name in ['voucher_edit', 'voucher_delete']:
                url = reverse(name, args=[voucher.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {}).status_code, 404)
        self.assertEqual(Voucher.objects.count(), 3)

    def test_create_owner_cannot_be_forged_and_journals_are_private(self):
        data = {'date': '2026-10-23', 'account_master': '5001', 'settlement_account': '1201', 'amount': '100', 'owner': self.bob.pk}
        self.assertRedirects(self.client.post(reverse('sales_new'), data), reverse('dashboard'))
        self.assertEqual(Voucher.objects.latest('pk').owner_id, self.alice.pk)
        data = journal_data(owner=self.bob.pk, date='2026-10-23', partner='공통 거래처')
        self.assertRedirects(self.client.post(reverse('voucher_new'), data), reverse('dashboard'))
        journal = Voucher.objects.latest('pk')
        self.assertEqual(journal.owner_id, self.alice.pk)
        self.assertEqual(journal.journal_lines.count(), 2)
        self.client.force_login(self.bob)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['count'], 1)
        self.assertEqual(list(response.context['journal_groups']), [])
        self.assertEqual(self.client.get(reverse('voucher_edit', args=[journal.pk])).status_code, 404)

    def test_reports_and_opening_balances_exclude_other_users(self):
        bs = self.client.get(reverse('balance_sheet'), {'as_of': '2026-10-23'}).context['report']
        self.assertEqual(bs['assets'], 1000)
        self.assertEqual(bs['excluded'], [])
        pl = self.client.get(reverse('income_statement'), {'start': '2026-10-01', 'end': '2026-10-23'}).context['report']
        self.assertEqual(pl['net_profit'], 1000)
        ledger = self.client.get(reverse('account_ledger'), {'account': '1101', 'start': '2026-10-24', 'end': '2026-10-25'}).context['report']
        self.assertEqual(ledger['opening'], 1000)
        self.assertEqual(ledger['closing'], 1000)
        self.assertEqual(ledger['excluded'], [])
        partner = self.client.get(reverse('partner_ledger'), {'partner': 'name:Alice 거래처', 'start': '2026-10-24'}).context
        self.assertEqual(partner['opening'], 1000)

    def test_legacy_assignment_is_explicit_preview_and_only_unassigned(self):
        output = StringIO()
        call_command('assign_legacy_vouchers', username='alice', stdout=output)
        self.legacy.refresh_from_db()
        self.assertIsNone(self.legacy.owner_id)
        self.assertIn('1건', output.getvalue())
        call_command('assign_legacy_vouchers', username='alice', apply=True, stdout=StringIO())
        self.legacy.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.legacy.owner_id, self.alice.pk)
        self.assertEqual(self.other.owner_id, self.bob.pk)
        with self.assertRaises(CommandError):
            call_command('assign_legacy_vouchers', username='missing', apply=True, stdout=StringIO())

    def test_superuser_uses_own_ledger_in_application(self):
        admin = User.objects.create_superuser(username='admin', password=TEST_PASSWORD)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse('dashboard')).context['count'], 0)
        self.assertEqual(self.client.get(reverse('voucher_edit', args=[self.mine.pk])).status_code, 404)
