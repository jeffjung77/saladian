from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Voucher, VoucherQuota, VoucherCreationUsage
from .voucher_quota import save_voucher, limits_for, VoucherQuotaExceeded
from .receipt_quota import remaining_creations, is_limited


class VoucherQuotaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='quota-user')
        self.admin = get_user_model().objects.create_user(username='quota-admin', is_superuser=True)

    def test_independent_limits_edits_deletion_and_user_isolation(self):
        VoucherQuota.objects.create(owner=self.user, sales_limit=1, expense_limit=0, other_limit=None)
        first = Voucher(owner=self.user, entry_type='sales', kind='income', amount=10)
        save_voucher(first)
        first.amount = 20
        save_voucher(first)
        first.delete()
        for entry in ['sales', 'expense']:
            with self.assertRaises(VoucherQuotaExceeded):
                save_voucher(Voucher(owner=self.user, entry_type=entry, amount=10))
        save_voucher(Voucher(owner=self.user, entry_type='other', amount=10))
        save_voucher(Voucher(owner=self.admin, entry_type='sales', amount=10))
        self.assertEqual(VoucherCreationUsage.objects.get(owner=self.user, entry_type='sales').generated_count, 1)

    def test_admin_form_validation_and_defaults(self):
        url = reverse('voucher_quota_edit', args=[self.user.pk])
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url, {'sales_limit': 0}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'sales_limit': -1})
        self.assertFalse(VoucherQuota.objects.filter(owner=self.user).exists())
        self.assertEqual(self.client.post(url, {'sales_limit': 2, 'expense_limit': 3, 'other_limit': 4, 'photo_limit': 1}).status_code, 302)
        self.assertEqual(limits_for(self.user), dict(sales=2, expense=3, other=4, photo=1))
        self.assertEqual(remaining_creations(self.user), 1)
        self.client.post(url, {})
        self.assertFalse(is_limited(self.user))
        self.assertIsNone(limits_for(self.user)['sales'])
