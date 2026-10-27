from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django import forms
from unittest.mock import patch
from .models import BoardPost, CreditAccount, CreditTransaction
from .credits import reward_post, adjust_credit


class CreditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user(username='credit-writer')
        self.other = User.objects.create_user(username='credit-other')
        self.admin = User.objects.create_user(username='credit-admin', is_superuser=True)
        self.staff = User.objects.create_user(username='credit-staff', is_staff=True)
        self.client.force_login(self.author)

    def new_post(self):
        return self.client.post(reverse('board_new'), {'title': 'Feedback', 'body': 'Test issue'})

    def test_rewards_per_post_no_edit_comment_or_delete_repayment(self):
        self.assertEqual(self.new_post().status_code, 302)
        post = BoardPost.objects.get()
        account = CreditAccount.objects.get(owner=self.author)
        self.assertEqual(account.balance, 100)
        self.assertFalse(reward_post(post))
        self.client.post(reverse('board_edit', args=[post.pk]), {'title': 'Edit', 'body': 'Edited'})
        self.client.post(reverse('board_comment_new', args=[post.pk]), {'body': 'Comment'})
        self.client.post(reverse('board_delete', args=[post.pk]))
        account.refresh_from_db()
        self.assertEqual(account.balance, 100)
        self.assertIsNone(CreditTransaction.objects.get().post_id)
        self.new_post()
        account.refresh_from_db()
        self.assertEqual(account.balance, 200)
        self.assertEqual(CreditTransaction.objects.count(), 2)
        self.assertFalse(CreditAccount.objects.filter(owner=self.other).exists())
        response = self.client.get(reverse('board_list'))
        self.assertEqual(response.context['credit_balance'], 200)

    def test_invalid_or_rolled_back_post_earns_nothing(self):
        self.client.post(reverse('board_new'), {'title': '', 'body': ''})
        self.assertFalse(CreditAccount.objects.exists())
        with patch('ledger.board_views.reward_post', side_effect=RuntimeError('Failure')):
            with self.assertRaises(RuntimeError):
                self.new_post()
        self.assertFalse(BoardPost.objects.exists())
        self.assertFalse(CreditTransaction.objects.exists())

    def test_permissions_csrf_and_manual_history(self):
        url = reverse('credit_edit', args=[self.author.pk])
        for member in (self.author, self.staff):
            self.client.force_login(member)
            self.assertEqual(self.client.get(reverse('credit_list')).status_code, 403)
            self.assertEqual(self.client.post(url, {'balance': 500, 'revision': 0, 'reason': 'Forged'}).status_code, 403)
        self.client.force_login(self.admin)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url, {}).status_code, 403)
        self.assertContains(self.client.get(reverse('credit_list')), self.author.username)
        self.assertEqual(self.client.post(url, {'balance': '1,000', 'revision': 0, 'reason': 'Beta reward'}).status_code, 302)
        entry = CreditTransaction.objects.get()
        self.assertEqual((entry.amount, entry.balance_after, entry.actor), (1000, 1000, self.admin))
        self.assertContains(self.client.get(url), 'Beta reward')
        self.assertEqual(self.client.post(url, {'balance': 500, 'revision': 1, 'reason': 'Correction'}).status_code, 302)
        self.assertEqual(CreditTransaction.objects.first().amount, -500)
        self.assertEqual(self.client.get(reverse('credit_list'), {'q': self.other.username}).context['page'].paginator.count, 1)

    def test_invalid_and_stale_balance_changes_are_rejected(self):
        self.new_post()
        self.client.force_login(self.admin)
        url = reverse('credit_edit', args=[self.author.pk])
        for data in [dict(balance=-1, revision=1, reason='Negative'), dict(balance=10, revision=1, reason=''),
                     dict(balance=10, revision=0, reason='Stale')]:
            self.assertEqual(self.client.post(url, data).status_code, 200)
            self.assertEqual(CreditAccount.objects.get(owner=self.author).balance, 100)
        self.assertEqual(CreditTransaction.objects.count(), 1)
        with self.assertRaises(forms.ValidationError):
            adjust_credit(self.author, 100, 'Unchanged', 1, self.admin)

    def test_existing_posts_not_backfilled(self):
        BoardPost.objects.create(author=self.author, title='Old', body='Old post')
        self.assertEqual(self.client.get(reverse('board_list')).context['credit_balance'], 0)
        self.assertFalse(CreditAccount.objects.exists())
