from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse
from .test_helpers import AuthenticatedLedgerTestCase
from .models import Voucher, ExpenseChartPreference
from .expense_views import monthly_expenses


class ExpenseStatusTests(AuthenticatedLedgerTestCase):
    def test_chart_has_separate_report_page(self):
        self.assertFalse(ExpenseChartPreference.objects.filter(owner=self.user).exists())
        response = self.client.get(reverse('business_overview'))
        self.assertNotContains(response, '비용 상위 10개 계정과목')
        ExpenseChartPreference.objects.create(owner=self.user, enabled=False)
        self.assertContains(self.client.get(reverse('expense_status')), '비용 상위 10개 계정과목')

    def expense(self, owner, amount, when=date(2026, 10, 1), closing=False):
        return Voucher.objects.create(owner=owner, date=when, kind='expense', account_master_id='6505', settlement_account_id='1101', amount=amount, is_closing=closing)

    def test_month_owner_and_closing_isolation(self):
        other = get_user_model().objects.create_user(username='other')
        self.expense(self.user, 3000)
        self.expense(self.user, 2000)
        self.expense(other, 9000)
        self.expense(self.user, 7000, date(2026, 9, 30))
        self.expense(self.user, 8000, closing=True)
        rows = monthly_expenses(self.user, date(2026, 10, 1))['expense_rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['amount'], 5000)

    def test_permissions_and_persistent_activation(self):
        url = reverse('expense_status')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.user.is_staff = True
        self.user.save()
        other = get_user_model().objects.create_user(username='other')
        self.client.post(url, {'month': '2026-10', 'user': other.pk, 'enabled': 'on'})
        self.assertFalse(ExpenseChartPreference.objects.exists())
        response = self.client.post(url, {'month': '2026-10', 'user': self.user.pk, 'enabled': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ExpenseChartPreference.objects.get(owner=self.user).enabled)
        self.assertContains(self.client.get(url), '비용 상위 10개 계정과목')
        self.assertEqual(self.client.get(url, {'month': 'invalid', 'user': self.user.pk}).status_code, 200)

    def test_superuser_can_configure_selected_user(self):
        self.user.is_superuser = True
        self.user.save()
        other = get_user_model().objects.create_user(username='other')
        self.client.post(reverse('expense_status'), {'month': '2026-10', 'user': other.pk, 'enabled': 'on'})
        self.assertTrue(ExpenseChartPreference.objects.get(owner=other).enabled)
