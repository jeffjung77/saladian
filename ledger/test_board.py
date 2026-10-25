from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import BoardPost
from .test_helpers import AuthenticatedLedgerTestCase


class BoardTests(AuthenticatedLedgerTestCase):
    def test_create_search_edit_and_delete_with_shared_member_visibility(self):
        response = self.client.post(reverse('board_new'), {'title': 'Beta feedback', 'body': 'Steps to reproduce', 'author': 999})
        post = BoardPost.objects.get()
        self.assertRedirects(response, reverse('board_detail', args=[post.pk]))
        self.assertEqual(post.author, self.user)
        self.assertContains(self.client.get(reverse('board_list'), {'q': 'reproduce'}), 'Beta feedback')
        self.assertEqual(self.client.get(reverse('board_list'), {'q': 'missing'}).context['page'].paginator.count, 0)
        self.client.post(reverse('board_edit', args=[post.pk]), {'title': 'Updated', 'body': '<script>alert(1)</script>'})
        self.assertContains(self.client.get(reverse('board_detail', args=[post.pk])), '&lt;script&gt;')
        self.assertEqual(self.client.get(reverse('board_delete', args=[post.pk])).status_code, 200)
        self.assertTrue(BoardPost.objects.exists())
        self.assertRedirects(self.client.post(reverse('board_delete', args=[post.pk])), reverse('board_list'))
        self.assertFalse(BoardPost.objects.exists())

    def test_authentication_author_permissions_and_system_admin_moderation(self):
        post = BoardPost.objects.create(author=self.user, title='Shared', body='Feedback')
        other = get_user_model().objects.create_user(username='board-other', is_staff=True)
        for name in ['board_list', 'board_new', 'board_detail', 'board_edit', 'board_delete']:
            url = reverse(name, args=[post.pk] if name in ['board_detail', 'board_edit', 'board_delete'] else [])
            self.assertEqual(Client().get(url).status_code, 302)
        self.client.force_login(other)
        self.assertContains(self.client.get(reverse('board_detail', args=[post.pk])), 'Shared')
        for name in ['board_edit', 'board_delete']:
            url = reverse(name, args=[post.pk])
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'title': 'Forged', 'body': 'Forged'}).status_code, 403)
        other.is_superuser = True
        other.save()
        self.assertEqual(self.client.get(reverse('board_edit', args=[post.pk])).status_code, 200)
        self.client.post(reverse('board_delete', args=[post.pk]))
        self.assertFalse(BoardPost.objects.exists())

    def test_required_fields_csrf_and_menu_position(self):
        response = self.client.post(reverse('board_new'), {'title': ' ', 'body': ' '})
        self.assertEqual(set(response.context['form'].errors), {'title', 'body'})
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('board_new'), {'title': 'x', 'body': 'x'}).status_code, 403)
        html = self.client.get(reverse('voucher_entry')).content.decode()
        self.assertLess(html.index('로그아웃</button>'), html.index('>게시판</a>'))
