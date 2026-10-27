from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from .models import Voucher, JournalLine, YearEndClosing, VoucherQuota
from . import reports


class YearEndTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='closing-admin', is_staff=True)
        self.other = get_user_model().objects.create_user(username='closing-other')
        self.client.force_login(self.owner)
        self.url = reverse('year_end')

    def simple(self, amount=1000, kind='income', code='5001', year=2025):
        return Voucher.objects.create(owner=self.owner, date=date(year, 7, 1), kind=kind,
            amount=amount, account_master_id=code, settlement_account_id='1101')

    def confirm(self, response, year=2025):
        return self.client.post(self.url, {'year': year, 'action': 'execute', 'token': response.context['token']})

    def test_preview_confirmation_profit_reports_and_repeat(self):
        self.simple()
        self.simple(300, 'expense', '6503')
        source = Voucher.objects.filter(owner=self.owner)
        before = reports.balance_sheet(date(2025, 12, 31), vouchers=source)
        response = self.client.post(self.url, {'year': 2025})
        self.assertContains(response, '연말 차기이월을 수행할까요?')
        self.assertEqual(response.context['result']['net_profit'], 700)
        self.assertEqual(Voucher.objects.count(), 2)
        VoucherQuota.objects.create(owner=self.owner, other_limit=0)
        self.assertEqual(self.confirm(response).status_code, 302)
        closing = Voucher.objects.get(closing_batch__isnull=False)
        self.assertTrue(closing.is_closing)
        self.assertEqual(closing.date, date(2025, 12, 31))
        self.assertEqual(reports.income_statement(date(2025, 1, 1), date(2025, 12, 31), vouchers=source)['net_profit'], 700)
        after = reports.balance_sheet(date(2025, 12, 31), vouchers=source)
        self.assertEqual(after['equity'], before['equity'])
        self.assertEqual(after['unclosed_profit'], 0)
        trial = reports.trial_balance(date(2025, 12, 31), vouchers=source)
        self.assertTrue(all(r['debit_balance'] == r['credit_balance'] == 0 for r in trial['rows'] if r['account'].pk in ('5001', '6503')))
        retained = next(r for r in trial['rows'] if r['account'].pk == '3403')
        self.assertEqual(retained['credit_balance'], 700)
        for route in ('voucher_edit', 'voucher_delete'):
            self.assertEqual(self.client.get(reverse(route, args=[closing.pk])).status_code, 403)
        self.assertContains(self.confirm(response), '장부가 변경')
        rerun = self.client.post(self.url, {'year': 2025})
        self.assertEqual(self.confirm(rerun).status_code, 302)
        self.assertEqual(YearEndClosing.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 3)

    def test_loss_zero_profit_and_multi_voucher(self):
        self.simple(100, 'income')
        self.simple(500, 'expense', '6503')
        response = self.client.post(self.url, {'year': 2025})
        self.assertEqual(response.context['result']['net_profit'], -400)
        self.confirm(response)
        self.assertEqual(JournalLine.objects.filter(voucher__closing_batch__isnull=False, account_id='3403', side='debit').get().amount, 400)
        for code in ('6501', '6502', '6504', '6505', '6506', '6507', '6508'):
            self.simple(10, 'expense', code)
        self.confirm(self.client.post(self.url, {'year': 2025}))
        self.assertGreater(Voucher.objects.filter(closing_batch__isnull=False).count(), 1)
        for v in Voucher.objects.filter(closing_batch__isnull=False):
            lines = list(v.journal_lines.all())
            self.assertLessEqual(max(line.row for line in lines), 5)
            self.assertEqual(sum(l.amount for l in lines if l.side == 'debit'), v.amount)
            self.assertEqual(sum(l.amount for l in lines if l.side == 'credit'), v.amount)

    def test_stale_tampered_permissions_and_validation(self):
        voucher = self.simple()
        response = self.client.post(self.url, {'year': 2025})
        voucher.amount = 2000
        voucher.save()
        self.assertContains(self.confirm(response), '장부가 변경')
        self.assertFalse(YearEndClosing.objects.exists())
        self.assertContains(self.client.post(self.url, {'year': 2025, 'action': 'execute', 'token': 'invalid'}), '다시 확인')
        self.assertContains(self.client.post(self.url, {'year': 9998}), '12월 31일')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url, {'year': 2025}).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.other.is_staff = True
        self.other.save()
        self.assertContains(self.client.post(self.url, {'year': 2025}), '이월할 손익계정 잔액이 없습니다')
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_prior_and_later_year_guard_and_zero_profit(self):
        self.simple(100, year=2024)
        self.assertContains(self.client.post(self.url, {'year': 2025}), '이전 연도부터')
        self.confirm(self.client.post(self.url, {'year': 2024}), year=2024)
        self.simple(100, year=2025)
        self.simple(100, 'expense', '6503', year=2025)
        response = self.client.post(self.url, {'year': 2025})
        self.assertEqual(response.context['result']['net_profit'], 0)
        self.confirm(response)
        self.assertContains(self.client.post(self.url, {'year': 2024}), '이후 연도')
        self.assertFalse(JournalLine.objects.filter(voucher__closing_batch__year=2025, account_id='3403').exists())

    def test_invalid_source_blocks_all_writes(self):
        self.simple()
        Voucher.objects.create(owner=self.owner, date=date(2025, 12, 1), kind='income', amount=5)
        self.assertContains(self.client.post(self.url, {'year': 2025}), '미반영 전표')
        self.assertFalse(YearEndClosing.objects.exists())
