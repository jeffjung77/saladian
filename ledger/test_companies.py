from django.contrib.auth import get_user_model
from django.urls import reverse
from .company_views import TABS
from .models import AuditLog, Voucher, Counterparty
from .test_helpers import AuthenticatedLedgerTestCase


class CompanyTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.admin = get_user_model().objects.create_user(username='company-admin', is_staff=True, is_superuser=True)
        self.other = get_user_model().objects.create_user(username='other-company')
        Counterparty.objects.create(owner=self.other, name='Foreign partner')
        for owner, amount, memo in [(self.user, 1000, 'Selected company'), (self.other, 9000, 'Foreign voucher')]:
            Voucher.objects.create(owner=owner, date='2026-10-24', kind='income', entry_type='sales',
                account_master_id='5001', settlement_account_id='1101', amount=amount, memo=memo)
        self.url = reverse('company_detail', args=[self.user.pk])

    def test_only_system_admin_can_view_companies(self):
        for staff in (False, True):
            self.user.is_staff = staff
            self.user.save()
            self.assertEqual(self.client.get(reverse('company_list')).status_code, 403)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_all_tabs_and_tenant_isolation(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('company_list'), {'q': self.user.username})
        self.assertEqual(response.context['page'].paginator.count, 1)
        for tab, _ in TABS:
            response = self.client.get(self.url, {'tab': tab, 'start': '2026-10-01', 'end': '2026-10-31', 'as_of': '2026-10-31'})
            self.assertEqual(response.status_code, 200, tab)
            self.assertNotContains(response, 'Foreign voucher')
            self.assertNotContains(response, 'Foreign partner')
            self.assertEqual(response.context['voucher_count'], 1)
            if tab == 'income':
                self.assertEqual(response.context['income']['net_profit'], 1000)
            if tab == 'balance':
                self.assertEqual(response.context['balance']['assets'], 1000)
        response = self.client.get(self.url, {'tab': 'account_ledger', 'account': '1101', 'start': '2026-10-01', 'end': '2026-10-31'})
        self.assertEqual(response.context['ledger']['closing'], 1000)

    def test_readonly_and_foreign_partner_rejected_and_audited(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url, {'amount': 0}).status_code, 405)
        foreign = Counterparty.objects.get(owner=self.other)
        self.assertEqual(self.client.get(self.url, {'tab': 'partner_ledger', 'partner': foreign.pk}).status_code, 404)
        self.client.get(self.url)
        event = AuditLog.objects.latest('pk')
        self.assertEqual(event.actor_id, self.admin.pk)
        self.assertEqual(event.company_user_id, self.user.pk)
        self.assertEqual(event.target, str(self.user.pk))
        self.assertEqual(Voucher.objects.get(owner=self.user).amount, 1000)
