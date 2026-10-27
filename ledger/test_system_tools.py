from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import Notice, Voucher, ReceiptPhoto, ReceiptCreationUsage
from .test_helpers import AuthenticatedLedgerTestCase


class SystemToolsTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.admin = get_user_model().objects.create_user(username='tools-admin', is_staff=True, is_superuser=True)

    def test_system_admin_only(self):
        notice = Notice.objects.create(author=self.admin, title='Draft', body='Private')
        urls = [reverse('user_voucher_counts'), reverse('notice_management'), reverse('notice_new'),
                reverse('notice_edit', args=[notice.pk]), reverse('notice_delete', args=[notice.pk])]
        for url in urls:
            self.assertEqual(Client().get(url).status_code, 302)
            self.assertEqual(self.client.get(url).status_code, 403)
        self.user.is_staff = True
        self.user.save()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code in (403, 405), True)

    def test_counts_are_not_multiplied_by_photo_joins_and_search(self):
        for entry, kind in [('sales', 'income'), ('expense', 'expense'), ('other', 'journal')]:
            Voucher.objects.create(owner=self.user, entry_type=entry, kind=kind, amount=1000)
        for _ in range(2):
            ReceiptPhoto.objects.create(owner=self.user, photo='unused', original_name='test.jpg', status='completed')
        ReceiptCreationUsage.objects.create(owner=self.user, generated_count=4)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('user_voucher_counts'), {'q': self.user.username})
        member = response.context['page'][0]
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertEqual([member.voucher_count, member.sales_count, member.expense_count, member.other_count], [3, 1, 1, 1])
        self.assertEqual([member.photo_used, member.photo_remaining], [4, 6])
        self.assertEqual(self.client.post(reverse('user_voucher_counts')).status_code, 405)

    def test_notice_publication_edit_delete_csrf_and_escape(self):
        self.client.force_login(self.admin)
        data = {'title': 'Beta notice', 'body': '<script>unsafe</script>'}
        self.assertEqual(self.client.post(reverse('notice_new'), data).status_code, 302)
        notice = Notice.objects.get()
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse('board_list')), notice.title)
        self.assertEqual(self.client.get(reverse('notice_detail', args=[notice.pk])).status_code, 404)
        self.client.force_login(self.admin)
        data['published'] = 'on'
        self.client.post(reverse('notice_edit', args=[notice.pk]), data)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('board_list')), notice.title)
        self.assertContains(self.client.get(reverse('notice_detail', args=[notice.pk])), '&lt;script&gt;')
        self.client.force_login(self.admin)
        delete = reverse('notice_delete', args=[notice.pk])
        self.client.get(delete)
        self.assertTrue(Notice.objects.exists())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(delete).status_code, 403)
        self.client.post(delete)
        self.assertFalse(Notice.objects.exists())
