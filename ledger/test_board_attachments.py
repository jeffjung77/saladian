import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from .models import BoardPost, BoardAttachment
from .test_helpers import AuthenticatedLedgerTestCase


class BoardAttachmentTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = override_settings(MEDIA_ROOT=self.directory.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def test_multiple_upload_private_download_preview_and_removal(self):
        photo = SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\nimage', content_type='image/png')
        doc = SimpleUploadedFile('notes.txt', b'feedback')
        self.client.post(reverse('board_new'), {'title': 'With files', 'body': 'Review', 'attachments': [photo, doc]})
        post = BoardPost.objects.get()
        self.assertEqual(post.attachments.count(), 2)
        image = post.attachments.get(original_name='photo.png')
        url = reverse('board_attachment', args=[image.pk])
        self.assertEqual(Client().get(url).status_code, 302)
        response = self.client.get(url)
        self.assertIn('attachment', response['Content-Disposition'])
        response.close()
        response = self.client.get(url, {'preview': 1})
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        response.close()
        other = get_user_model().objects.create_user(username='attachment-reader')
        self.client.force_login(other)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.client.post(reverse('board_edit', args=[post.pk]), {'title': 'x', 'body': 'x', 'remove_attachment': [image.pk]}).status_code, 403)
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('board_edit', args=[post.pk]), {'title': post.title, 'body': post.body, 'remove_attachment': [image.pk]})
        self.assertFalse(image.file.storage.exists(image.file.name))
        self.assertEqual(post.attachments.count(), 1)
        self.client.post(reverse('board_delete', args=[post.pk]))
        self.assertFalse(BoardAttachment.objects.exists())

    def test_count_size_and_invalid_post_do_not_save_files(self):
        uploads = [SimpleUploadedFile(f'{i}.txt', b'x') for i in range(6)]
        response = self.client.post(reverse('board_new'), {'title': 'x', 'body': 'x', 'attachments': uploads})
        self.assertIn('attachments', response.context['form'].errors)
        big = SimpleUploadedFile('large.txt', b'x' * (10 * 1024 * 1024 + 1))
        response = self.client.post(reverse('board_new'), {'title': 'x', 'body': 'x', 'attachments': [big]})
        self.assertIn('attachments', response.context['form'].errors)
        response = self.client.post(reverse('board_new'), {'title': '', 'body': '', 'attachments': [SimpleUploadedFile('x.txt', b'x')]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BoardPost.objects.exists())
        self.assertFalse(BoardAttachment.objects.exists())
