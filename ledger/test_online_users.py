import time
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class OnlineUsersTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('online-admin', password='test-secret')
        self.member = get_user_model().objects.create_user('online-member', password='test-secret')
        self.client.force_login(self.admin)

    def test_permission(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('online_users')).status_code, 403)

    def test_all_users_including_legacy_session_without_activity(self):
        clients = [Client(), Client()]
        other = get_user_model().objects.create_user('online-third', password='test-secret')
        for client, user in zip(clients, [self.member, other]):
            client.force_login(user)
        response = self.client.get(reverse('online_users'))
        self.assertEqual({row['username'] for row in response.context['page']},
                         {self.admin.username, self.member.username, other.username})

    def test_recent_sessions_grouped_and_stale_excluded(self):
        clients = [Client(), Client(), Client()]
        for index, client in enumerate(clients):
            client.force_login(self.member)
            session = client.session
            session['last_activity_at'] = time.time() - (1801 if index == 2 else 5)
            session.save()
        response = self.client.get(reverse('online_users'), {'q': self.member.username})
        self.assertEqual(response.status_code, 200)
        rows = list(response.context['page'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['sessions'], 2)
        self.member.set_password('changed-secret')
        self.member.save()
        response = self.client.get(reverse('online_users'), {'q': self.member.username})
        self.assertEqual(response.context['page'].paginator.count, 0)
