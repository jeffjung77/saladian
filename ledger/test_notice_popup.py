from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Notice


class NoticePopupTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='popup-admin', is_superuser=True)
        self.member = User.objects.create_user(username='popup-member')
        self.notices = [Notice.objects.create(author=self.admin, title=f'Notice {i}', body='Notice body', published=True) for i in range(7)]
        Notice.objects.create(author=self.admin, title='Hidden draft', body='Private draft', published=False)

    def test_published_notices_accumulate_for_every_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('board_list'))
        self.assertEqual(len(response.context['notices']), 7)
        self.assertEqual(len(response.context['popup_notices']), 7)
        self.assertNotContains(response, 'Hidden draft')
        self.assertContains(response, 'id="published-notice-popup"')
        self.assertContains(response, 'sessionStorage.getItem')
        self.assertContains(response, 'sessionStorage.setItem')
        self.assertContains(response, 'Notice 0')
        self.assertEqual(self.client.get(reverse('notice_detail', args=[Notice.objects.get(title='Hidden draft').pk])).status_code, 404)

    def test_cycle_stable_during_navigation_and_changes_after_login(self):
        self.client.force_login(self.member)
        first = self.client.get(reverse('voucher_entry')).context['notice_popup_cycle']
        self.assertEqual(self.client.get(reverse('board_list')).context['notice_popup_cycle'], first)
        self.client.logout()
        self.client.force_login(self.member)
        second = self.client.get(reverse('voucher_entry')).context['notice_popup_cycle']
        self.assertNotEqual(first, second)

    def test_no_popup_for_guest_unpublished_or_personal_edition(self):
        self.assertNotContains(self.client.get(reverse('business_overview'), follow=True), 'id="published-notice-popup"')
        self.client.force_login(self.member)
        with override_settings(DESKTOP_MODE=True):
            self.assertNotContains(self.client.get(reverse('voucher_entry')), 'id="published-notice-popup"')
        Notice.objects.update(published=False)
        self.assertNotContains(self.client.get(reverse('voucher_entry')), 'id="published-notice-popup"')
