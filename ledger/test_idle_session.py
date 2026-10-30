import time
from django.urls import reverse
from .test_helpers import AuthenticatedLedgerTestCase
from .models import Voucher


class IdleSessionTests(AuthenticatedLedgerTestCase):
    def set_idle(self, seconds):
        session = self.client.session
        session['last_activity_at'] = time.time() - seconds
        session.save()

    def test_active_session_is_extended(self):
        self.set_idle(1700)
        self.assertEqual(self.client.post(reverse('session_activity')).status_code, 200)
        self.assertLess(time.time() - self.client.session['last_activity_at'], 5)
        self.assertEqual(self.client.session.get_expiry_age(), 1800)

    def test_idle_users_and_system_admins_are_logged_out(self):
        for admin in (False, True):
            self.user.is_superuser = admin
            self.user.save()
            self.client.force_login(self.user)
            self.set_idle(1801)
            self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_expired_post_does_not_save_voucher(self):
        self.set_idle(1801)
        response = self.client.post(reverse('sales_new'), {'date': '2026-10-30', 'account_master': '5001', 'settlement_account': '1101', 'amount': '1000'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Voucher.objects.exists())

    def test_expired_activity_returns_401(self):
        self.set_idle(1801)
        self.assertEqual(self.client.post(reverse('session_activity')).status_code, 401)

    def test_authenticated_page_has_idle_script(self):
        self.assertContains(self.client.get(reverse('business_overview')), 'idle_session.js')
