from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import BoardPost


@override_settings(BOARD_EMAIL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='sender@example.com', BOARD_SITE_URL='https://easybook.bpms.co.kr')
class BoardEmailTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='board-writer')
        User.objects.create_user(username='board-admin', email='admin@example.com', is_superuser=True)
        User.objects.create_user(username='board-admin2', email='ADMIN@example.com', is_superuser=True)
        User.objects.create_user(username='board-inactive', email='inactive@example.com', is_superuser=True, is_active=False)
        User.objects.create_user(username='board-staff', email='staff@example.com', is_staff=True)
        self.client.force_login(self.user)

    def create_post(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('board_new'), {'title': 'Beta feedback', 'body': 'Please check this issue.'})

    def test_new_post_email_contents_recipients_and_no_edit_notification(self):
        self.assertEqual(self.create_post().status_code, 302)
        post = BoardPost.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.bcc, ['admin@example.com'])
        self.assertIn(post.body, email.body)
        self.assertIn(self.user.username, email.body)
        self.assertIn('https://easybook.bpms.co.kr' + reverse('board_detail', args=[post.pk]), email.body)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('board_edit', args=[post.pk]), {'title': 'Edited', 'body': 'Changed'})
        self.assertEqual(len(mail.outbox), 1)

    def test_failure_does_not_lose_post(self):
        with patch('ledger.board_email.EmailMessage.send', side_effect=OSError('SMTP unavailable')):
            self.assertEqual(self.create_post().status_code, 302)
        self.assertEqual(BoardPost.objects.count(), 1)

    def test_invalid_form_does_not_schedule_email(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.client.post(reverse('board_new'), {'title': '', 'body': ''})
        self.assertEqual(callbacks, [])
        self.assertFalse(BoardPost.objects.exists())

    @override_settings(BOARD_EMAIL_ENABLED=False)
    def test_disabled_configuration_does_not_send(self):
        self.assertEqual(self.create_post().status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
