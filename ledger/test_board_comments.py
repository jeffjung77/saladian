from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import BoardPost, BoardComment
from .test_helpers import AuthenticatedLedgerTestCase


class BoardCommentTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.post = BoardPost.objects.create(author=self.user, title='Feedback', body='Test')
        self.other = get_user_model().objects.create_user(username='commenter')
        self.url = reverse('board_comment_new', args=[self.post.pk])

    def test_list_submission_count_detail_and_escaping(self):
        self.other.is_superuser = True
        self.other.save()
        self.client.force_login(self.other)
        response = self.client.post(self.url, {'body': '<script>test</script>', 'author': self.user.pk,
                                             'return_to': 'list', 'page': 1, 'q': 'Feedback'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('#post-', response.url)
        comment = BoardComment.objects.get()
        self.assertEqual(comment.author, self.other)
        listing = self.client.get(reverse('board_list'))
        self.assertEqual(listing.context['page'][0].comment_count, 1)
        self.assertContains(listing, self.url)
        self.assertContains(self.client.get(reverse('board_detail', args=[self.post.pk])), '&lt;script&gt;test&lt;/script&gt;')

    def test_validation_auth_csrf_and_post_only(self):
        self.assertEqual(Client().post(self.url, {'body': 'test'}).status_code, 302)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        for body in ['', '  ', 'x' * 2001]:
            self.assertEqual(self.client.post(self.url, {'body': body}).status_code, 400)
        self.assertFalse(BoardComment.objects.exists())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, {'body': 'test'}).status_code, 403)

    def test_delete_owner_and_system_admin_only_and_post_cascade(self):
        comment = BoardComment.objects.create(post=self.post, author=self.other, body='Reply')
        url = reverse('board_comment_delete', args=[comment.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.other.is_superuser = True
        self.other.save()
        self.assertEqual(self.client.post(url).status_code, 302)
        comment = BoardComment.objects.create(post=self.post, author=self.other, body='Reply')
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('board_comment_delete', args=[comment.pk])).status_code, 302)
        BoardComment.objects.create(post=self.post, author=self.other, body='Reply')
        self.post.delete()
        self.assertFalse(BoardComment.objects.exists())
