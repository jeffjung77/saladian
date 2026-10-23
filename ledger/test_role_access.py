from django.urls import reverse
from .models import Counterparty
from .test_helpers import AuthenticatedLedgerTestCase


class RoleAccessTests(AuthenticatedLedgerTestCase):
    def set_grade(self, grade):
        self.user.is_staff = grade in ('2', '3')
        self.user.is_superuser = grade == '3'
        self.user.save(update_fields=['is_staff', 'is_superuser'])

    def test_navigation_and_direct_access_for_each_grade(self):
        management = [reverse('counterparties'), reverse('counterparty_new'), reverse('counterparty_edit', args=[self.partner.pk]), reverse('accounts')]
        system = [reverse('member_list'), reverse('system_signup'), reverse('member_grade', args=[self.user.pk])]
        for grade in ['1', '2', '3']:
            self.set_grade(grade)
            response = self.client.get(reverse('business_overview'))
            if grade == '1':
                self.assertNotContains(response, '<summary>관리</summary>')
            else:
                self.assertContains(response, '<summary>관리</summary>')
            if grade == '3':
                self.assertContains(response, '<summary>시스템관리</summary>')
            else:
                self.assertNotContains(response, '<summary>시스템관리</summary>')
            for url in management:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403 if grade == '1' else 200)
            for url in system:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200 if grade == '3' else 403)
                if grade != '3':
                    self.assertContains(response, '권한이 없습니다. 시스템관리자에게 문의하세요.', status_code=403)
            for name in ['dashboard', 'sales_new', 'expense_new', 'voucher_new', 'balance_sheet', 'income_statement', 'account_ledger', 'partner_ledger']:
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_user_cannot_manage_counterparty_but_can_select_existing_master(self):
        for url in [reverse('counterparty_new'), reverse('counterparty_edit', args=[self.partner.pk])]:
            self.assertEqual(self.client.post(url, {'name': 'forged'}).status_code, 403)
        self.partner.refresh_from_db()
        self.assertNotEqual(self.partner.name, 'forged')
        self.assertEqual(Counterparty.objects.count(), 1)
        self.assertEqual(self.client.get(reverse('counterparty_certificate', args=[self.partner.pk])).status_code, 403)
        response = self.client.get(reverse('sales_new'))
        self.assertContains(response, self.partner.name)
        self.assertNotContains(response, reverse('counterparty_new'))
        self.assertEqual(self.client.get(reverse('counterparty_options')).json()['counterparties'][0]['id'], self.partner.pk)

    def test_administrator_cannot_post_to_any_system_action(self):
        self.set_grade('2')
        for name, args in [('system_signup', []), ('member_grade', [self.user.pk]), ('member_list', [])]:
            response = self.client.post(reverse(name, args=args), {'grade': '3', 'username': 'forged'})
            self.assertIn(response.status_code, [403, 405])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)

    def test_demotion_takes_effect_without_relogin(self):
        self.set_grade('3')
        self.assertEqual(self.client.get(reverse('member_list')).status_code, 200)
        self.set_grade('2')
        self.assertEqual(self.client.get(reverse('member_list')).status_code, 403)
        self.set_grade('1')
        self.assertEqual(self.client.get(reverse('counterparties')).status_code, 403)
