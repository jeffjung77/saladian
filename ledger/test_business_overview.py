from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from .models import Voucher, JournalLine
from .reports import balance_sheet, income_statement
from .test_helpers import AuthenticatedLedgerTestCase


class BusinessOverviewTests(AuthenticatedLedgerTestCase):
    def simple(self, when, code, amount, kind, **kwargs):
        return Voucher.objects.create(owner=self.user, date=when, kind=kind, account=code,
                                      account_master_id=code, settlement_account_id='1101', amount=amount, **kwargs)

    @patch('ledger.views.timezone.localdate', return_value=date(2026, 10, 23))
    def test_summary_matches_reports_and_excludes_future_and_other_users(self, _today):
        self.simple('2026-09-30', '5001', 1000, 'income')
        self.simple('2026-10-01', '6505', 200, 'expense')
        self.simple('2026-10-24', '5001', 5000, 'income')
        other = get_user_model().objects.create_user(username='overview-other')
        Voucher.objects.create(owner=other, date='2026-10-01', kind='income', account='5001', account_master_id='5001', settlement_account_id='1101', amount=9000)
        transfer = Voucher.objects.create(owner=self.user, date='2026-10-02', kind='journal', account='', amount=50)
        JournalLine.objects.create(voucher=transfer, row=1, side='debit', account_id='1102', amount=50)
        JournalLine.objects.create(voucher=transfer, row=1, side='credit', account_id='1101', amount=50)
        Voucher.objects.create(owner=self.user, date='2026-10-03', kind='income', account='unmapped', amount=300)
        response = self.client.get(reverse('business_overview'))
        self.assertContains(response, '사업현황 한눈에 보기')
        context = response.context
        self.assertEqual(context['cash_total'], 800)
        self.assertEqual(context['cash_opening'], 1000)
        self.assertEqual(context['cash_amount'], 750)
        self.assertEqual(context['bank_amount'], 50)
        self.assertEqual(context['revenue'], 0)
        self.assertEqual(context['expense'], 200)
        self.assertEqual(len(context['cash_points']), 23)
        self.assertEqual(context['cash_points'][-1]['value'], '800')
        self.assertEqual(len(context['balance']['excluded']), 1)
        source = Voucher.objects.filter(owner=self.user)
        self.assertEqual(context['balance']['assets'], balance_sheet(date(2026, 10, 23), vouchers=source)['assets'])
        self.assertEqual(context['income']['net_profit'], income_statement(date(2026, 10, 1), date(2026, 10, 23), vouchers=source)['net_profit'])
        self.assertIn('no-store', response.headers['Cache-Control'])

    @patch('ledger.views.timezone.localdate', return_value=date(2026, 1, 1))
    def test_empty_and_negative_balances_render(self, _today):
        response = self.client.get('/')
        self.assertEqual(response.context['cash_total'], 0)
        self.assertEqual(len(response.context['cash_points']), 1)
        self.assertContains(response, '집계할 전표가 없습니다')
        self.simple('2026-01-01', '6505', 500, 'expense')
        response = self.client.get('/')
        self.assertEqual(response.context['cash_total'], -500)
        self.assertEqual(response.context['income']['net_profit'], -500)
        self.assertContains(response, '-500')

    def test_landing_requires_login_and_existing_vouchers_remain_available(self):
        self.assertEqual(reverse('business_overview'), '/')
        self.assertEqual(Client().get('/').status_code, 302)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
