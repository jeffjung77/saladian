from django.test import TestCase
from django.urls import reverse
from .models import Voucher


class LedgerTests(TestCase):
    def data(self, **overrides):
        return dict(date='2026-10-22', kind='income', account='매출', amount='10000', partner='고객', memo='거래', **overrides)

    def test_create_edit_delete(self):
        response = self.client.post(reverse('voucher_new'), self.data())
        self.assertRedirects(response, reverse('dashboard'))
        voucher = Voucher.objects.get()
        data = self.data()
        data['amount'] = '12000'
        self.client.post(reverse('voucher_edit', args=[voucher.pk]), data)
        voucher.refresh_from_db()
        self.assertEqual(voucher.amount, 12000)
        self.client.get(reverse('voucher_delete', args=[voucher.pk]))
        self.assertTrue(Voucher.objects.exists())
        self.client.post(reverse('voucher_delete', args=[voucher.pk]))
        self.assertFalse(Voucher.objects.exists())

    def test_amount_validation(self):
        for amount in ['0', '-1', '1.5', '100000000000000']:
            data = self.data()
            data['amount'] = amount
            self.assertEqual(self.client.post(reverse('voucher_new'), data).status_code, 200)
        self.assertFalse(Voucher.objects.exists())

    def test_aggregation_and_period(self):
        Voucher.objects.create(date='2026-10-22', kind='income', account='매출', amount=10000)
        Voucher.objects.create(date='2026-10-22', kind='income', account='매출', amount=2000)
        Voucher.objects.create(date='2026-10-22', kind='expense', account='재료비', amount=3000)
        Voucher.objects.create(date='2026-09-01', kind='income', account='매출', amount=500)
        response = self.client.get('/', {'start': '2026-10-01', 'end': '2026-10-22'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['income'], 12000)
        self.assertEqual(response.context['expense'], 3000)
        self.assertEqual(response.context['balance'], 9000)
        self.assertEqual(response.context['count'], 3)
        self.assertEqual(next(g['total'] for g in response.context['groups'] if g['kind'] == 'income'), 12000)
        self.assertEqual(self.client.get('/').context['income'], 12500)

    def test_invalid_period_and_empty(self):
        self.assertEqual(self.client.get('/').context['balance'], 0)
        response = self.client.get('/', {'start': '2026-10-22', 'end': '2026-10-01'})
        self.assertContains(response, '종료일은 시작일 이후여야 합니다.')
        self.assertContains(self.client.get('/', {'start': 'bad'}), 'errorlist')

    def test_csrf(self):
        from django.test import Client
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('voucher_new'), self.data()).status_code, 403)

# Create your tests here.
