from .test_helpers import AuthenticatedLedgerTestCase
from django.urls import reverse
from .models import Voucher
from .models import Account
from .account_catalog import ACCOUNTS
from .models import JournalLine


def journal_data(debits=None, credits=None, **header):
    data = {'date': '2026-10-22', 'counterparty': '', 'memo': '복합전표',
            'lines-TOTAL_FORMS': '5', 'lines-INITIAL_FORMS': '5',
            'lines-MIN_NUM_FORMS': '0', 'lines-MAX_NUM_FORMS': '5'}
    data.update(header)
    debits = [('1101', '1000')] if debits is None else debits
    credits = [('5001', '1000')] if credits is None else credits
    for index in range(5):
        for side, values in [('debit', debits), ('credit', credits)]:
            code, amount = values[index] if index < len(values) else ('', '')
            data[f'lines-{index}-{side}_account'] = code
            data[f'lines-{index}-{side}_amount'] = amount
    return data


class LedgerTests(AuthenticatedLedgerTestCase):
    def data(self, **overrides):
        return dict(date='2026-10-22', kind='income', account_master='5001', settlement_account='1101', amount='10000', counterparty=self.partner.pk, memo='거래', **overrides)

    def test_create_edit_delete(self):
        response = self.client.post(reverse('sales_new'), self.data())
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
            self.assertEqual(self.client.post(reverse('sales_new'), data).status_code, 200)
        self.assertFalse(Voucher.objects.exists())

    def test_aggregation_and_period(self):
        Voucher.objects.create(owner=self.user, date='2026-10-22', kind='income', account='매출', amount=10000)
        Voucher.objects.create(owner=self.user, date='2026-10-22', kind='income', account='매출', amount=2000)
        Voucher.objects.create(owner=self.user, date='2026-10-22', kind='expense', account='재료비', amount=3000)
        Voucher.objects.create(owner=self.user, date='2026-09-01', kind='income', account='매출', amount=500)
        response = self.client.get(reverse('dashboard'), {'start': '2026-10-01', 'end': '2026-10-22'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['income'], 12000)
        self.assertEqual(response.context['expense'], 3000)
        self.assertEqual(response.context['balance'], 9000)
        self.assertEqual(response.context['count'], 3)
        self.assertEqual(next(g['total'] for g in response.context['groups'] if g['kind'] == 'income'), 12000)
        self.assertEqual(self.client.get(reverse('dashboard')).context['income'], 12500)

    def test_invalid_period_and_empty(self):
        self.assertEqual(self.client.get(reverse('dashboard')).context['balance'], 0)
        response = self.client.get(reverse('dashboard'), {'start': '2026-10-22', 'end': '2026-10-01'})
        self.assertContains(response, '종료일은 시작일 이후여야 합니다.')
        self.assertContains(self.client.get(reverse('dashboard'), {'start': 'bad'}), 'errorlist')

    def test_csrf(self):
        from django.test import Client
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('sales_new'), self.data()).status_code, 403)

# Create your tests here.


class PartnerLedgerTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('partner_ledger')
        for date, partner, kind, amount in [
            ('2026-09-30', '가게 A', 'income', 100),
            ('2026-10-01', '가게 A', 'expense', 30),
            ('2026-10-01', '가게 A', 'income', 50),
            ('2026-10-31', '가게 A', 'expense', 10),
            ('2026-11-01', '가게 A', 'income', 900),
            ('2026-10-01', '가게 B', 'income', 999),
            ('2026-10-01', '', 'expense', 20),
        ]:
            Voucher.objects.create(owner=self.user, date=date, partner=partner, kind=kind, account='테스트', amount=amount)

    def test_period_opening_totals_and_order(self):
        response = self.client.get(self.url, {'partner': 'name:가게 A', 'start': '2026-10-01', 'end': '2026-10-31'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['opening'], 100)
        self.assertEqual(response.context['income'], 50)
        self.assertEqual(response.context['expense'], 40)
        self.assertEqual(response.context['closing'], 110)
        self.assertEqual([row['balance'] for row in response.context['rows']], [70, 120, 110])
        self.assertContains(response, '거래처별 원장')
        self.assertContains(response, '10 원')

    def test_all_dates_unassigned_and_empty_period(self):
        response = self.client.get(self.url, {'partner': 'name:가게 A'})
        self.assertEqual(response.context['closing'], 1010)
        self.assertEqual(len(response.context['rows']), 5)
        response = self.client.get(self.url, {'partner': 'unassigned:'})
        self.assertEqual(response.context['closing'], -20)
        self.assertEqual(len(response.context['rows']), 1)
        response = self.client.get(self.url, {'partner': 'name:가게 A', 'start': '2027-01-01'})
        self.assertEqual(response.context['opening'], 1010)
        self.assertEqual(response.context['rows'], [])

    def test_invalid_filters_and_initial_page(self):
        self.assertEqual(self.client.get(self.url).context['rows'], [])
        for params in [
            {'partner': 'name:unknown'},
            {'partner': 'name:가게 A', 'start': 'bad'},
            {'partner': 'name:가게 A', 'start': '2026-10-31', 'end': '2026-10-01'},
        ]:
            response = self.client.get(self.url, params)
            self.assertTrue(response.context['form'].errors)
            self.assertEqual(response.context['rows'], [])
        self.assertContains(self.client.get(reverse('dashboard')), reverse('partner_ledger'))


class AccountMasterTests(AuthenticatedLedgerTestCase):
    def data(self, code='5001'):
        return {'date': '2026-10-22', 'kind': 'income', 'account_master': code, 'settlement_account': '1101', 'amount': '1000'}

    def test_catalog_matches_all_provided_rows(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.assertEqual(Account.objects.count(), 118)
        self.assertEqual(list(Account.objects.values_list('code', 'name', 'category', 'section', 'element')), ACCOUNTS)
        self.assertContains(self.client.get(reverse('accounts')), '9801')
        self.assertContains(self.client.get(reverse('voucher_new')), '5001 · 매출-용역')

    def test_create_only_registered_accounts(self):
        for invalid in ['', '9999', '매출', '5001 · 매출-용역']:
            response = self.client.post(reverse('sales_new'), self.data(invalid))
            self.assertEqual(response.status_code, 200)
            self.assertIn('account_master', response.context['form'].errors)
        self.assertEqual(Voucher.objects.count(), 0)
        self.client.post(reverse('sales_new'), self.data())
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.account_master_id, '5001')
        self.assertEqual(voucher.account, '매출-용역')

    def test_duplicate_names_are_distinguished_by_code(self):
        for code in ['3202', '3302']:
            Voucher.objects.create(owner=self.user, date='2026-10-22', kind='income', account=Account.objects.get(pk=code).name, account_master_id=code, amount=1000)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(len(response.context['groups']), 2)
        self.assertEqual({g['account_master_id'] for g in response.context['groups']}, {'3202', '3302'})
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            Account.objects.get(pk='3202').delete()

    def test_legacy_voucher_requires_selection_on_edit(self):
        voucher = Voucher.objects.create(owner=self.user, date='2026-10-22', kind='income', account='기존과목', amount=1000)
        response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
        self.assertContains(response, '기존과목')
        self.client.post(reverse('voucher_edit', args=[voucher.pk]), self.data('9999'))
        voucher.refresh_from_db()
        self.assertIsNone(voucher.account_master_id)
        self.client.post(reverse('voucher_edit', args=[voucher.pk]), self.data('6505'))
        voucher.refresh_from_db()
        self.assertEqual(voucher.account_master_id, '6505')
        self.assertEqual(voucher.account, '임차료')


class EntryScreenTests(AuthenticatedLedgerTestCase):
    def data(self, code, kind='income'):
        return {'date': '2026-10-22', 'account_master': code, 'settlement_account': '1101', 'kind': kind, 'amount': '1000', 'counterparty': self.partner.pk}

    def test_screen_choices_and_defaults(self):
        sales = self.client.get(reverse('sales_new'))
        self.assertContains(sales, '<h1>매출입력</h1>', html=True)
        self.assertEqual(list(sales.context['form'].fields['account_master'].queryset.values_list('pk', flat=True)), ['5001'])
        self.assertEqual(sales.context['form'].initial['account_master'], '5001')
        expenses = self.client.get(reverse('expense_new'))
        codes = set(expenses.context['form'].fields['account_master'].queryset.values_list('pk', flat=True))
        self.assertTrue({'6101', '6505', '9501', '9801'} <= codes)
        self.assertTrue({'1101', '5001', '9101'}.isdisjoint(codes))
        self.assertEqual(self.client.get(reverse('voucher_new')).context['rows'].forms[0].fields['debit_account'].queryset.count(), 118)

    def test_kind_is_enforced_and_type_persisted(self):
        self.client.post(reverse('sales_new'), self.data('5001', 'expense'))
        sales = Voucher.objects.get(entry_type='sales')
        self.assertEqual(sales.kind, 'income')
        data = self.data('6505')
        data.pop('kind')
        self.client.post(reverse('expense_new'), data)
        expense = Voucher.objects.get(entry_type='expense')
        self.assertEqual(expense.kind, 'expense')
        self.client.post(reverse('voucher_new'), journal_data())
        self.assertTrue(Voucher.objects.filter(entry_type='other', kind='journal', amount=1000).exists())
        self.assertEqual(self.client.get(reverse('dashboard')).context['income'], 1000)
        self.assertEqual(self.client.get(reverse('dashboard')).context['expense'], 1000)

    def test_wrong_account_is_rejected_on_create_and_edit(self):
        for url, code in [('sales_new', '6505'), ('expense_new', '5001'), ('expense_new', '1101')]:
            response = self.client.post(reverse(url), self.data(code))
            self.assertIn('account_master', response.context['form'].errors)
        self.assertFalse(Voucher.objects.exists())
        self.client.post(reverse('sales_new'), self.data('5001'))
        voucher = Voucher.objects.get()
        url = reverse('voucher_edit', args=[voucher.pk])
        self.assertEqual(self.client.get(url).context['entry_type'], 'sales')
        self.client.post(url, self.data('6505'))
        voucher.refresh_from_db()
        self.assertEqual(voucher.account_master_id, '5001')
        data = self.data('5001', 'expense')
        data['amount'] = '2000'
        self.client.post(url, data)
        voucher.refresh_from_db()
        self.assertEqual(voucher.amount, 2000)
        self.assertEqual(voucher.entry_type, 'sales')
        self.assertEqual(voucher.kind, 'income')

    def test_empty_submission_shows_errors_and_navigation(self):
        for name in ['sales_new', 'expense_new', 'voucher_new']:
            response = self.client.post(reverse(name), {})
            self.assertTrue(response.context['form'].errors)
            self.assertContains(self.client.get(reverse('dashboard')), reverse(name))


class JournalTests(AuthenticatedLedgerTestCase):
    def test_common_memo_on_rows_with_only_one_side(self):
        data = journal_data(debits=[('1101', '1000')], credits=[('', ''), ('5001', '1000')])
        data['lines-0-memo'] = '차변만 있는 행'
        data['lines-1-memo'] = '대변만 있는 행'
        self.assertRedirects(self.client.post(reverse('voucher_new'), data), reverse('dashboard'))
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.journal_lines.get(row=1).memo, '차변만 있는 행')
        self.assertEqual(voucher.journal_lines.get(row=2).memo, '대변만 있는 행')

    def test_existing_different_memos_are_merged_without_loss(self):
        self.client.post(reverse('voucher_new'), journal_data())
        voucher = Voucher.objects.get()
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        from types import SimpleNamespace
        merge = import_module('ledger.migrations.0008_alter_journalline_memo').merge_memos
        for debit, credit, expected in [
            ('가' * 300, '나' * 300, '[차변] ' + '가' * 300 + ' / [대변] ' + '나' * 300),
            ('같은 적요', '같은 적요', '같은 적요'),
            ('', '한쪽 적요', '한쪽 적요'),
            ('차변 적요', '', '차변 적요'),
            ('', '', ''),
        ]:
            voucher.journal_lines.filter(side='debit').update(memo=debit)
            voucher.journal_lines.filter(side='credit').update(memo=credit)
            merge(apps, SimpleNamespace(connection=connection))
            self.assertEqual(set(voucher.journal_lines.values_list('memo', flat=True)), {expected})
            response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
            self.assertEqual(response.context['rows'].forms[0].initial['memo'], expected)
            merge(apps, SimpleNamespace(connection=connection))
            self.assertEqual(set(voucher.journal_lines.values_list('memo', flat=True)), {expected})

    def test_line_memos_save_edit_and_appear_in_views(self):
        data = journal_data(memo='전표 전체 적요', counterparty=self.partner.pk)
        data['lines-0-memo'] = '현금 입금 및 용역 매출'
        self.assertRedirects(self.client.post(reverse('voucher_new'), data), reverse('dashboard'))
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.memo, '전표 전체 적요')
        self.assertEqual(voucher.journal_lines.get(side='debit').memo, '현금 입금 및 용역 매출')
        self.assertEqual(voucher.journal_lines.get(side='credit').memo, '현금 입금 및 용역 매출')
        url = reverse('voucher_edit', args=[voucher.pk])
        response = self.client.get(url)
        self.assertEqual(response.context['rows'].forms[0].initial['memo'], '현금 입금 및 용역 매출')
        self.assertNotContains(response, 'lines-0-debit_memo')
        self.assertNotContains(response, 'lines-0-credit_memo')
        for path in [reverse('dashboard'), reverse('partner_ledger') + f'?partner=master%3A{self.partner.pk}', reverse('voucher_delete', args=[voucher.pk])]:
            response = self.client.get(path)
            self.assertContains(response, '현금 입금 및 용역 매출', count=1)
        data['lines-0-memo'] = '수정한 라인 적요'
        self.client.post(url, data)
        self.assertEqual(voucher.journal_lines.get(side='debit').memo, '수정한 라인 적요')
        self.assertEqual(voucher.journal_lines.get(side='credit').memo, '수정한 라인 적요')
        self.assertEqual(voucher.journal_lines.count(), 2)
        data['lines-0-memo'] = ''
        self.client.post(url, data)
        self.assertEqual(set(voucher.journal_lines.values_list('memo', flat=True)), {''})

    def test_line_memo_validation_and_invalid_edit_preserves_memos(self):
        data = journal_data()
        data['lines-0-memo'] = '가' * 1000
        self.assertRedirects(self.client.post(reverse('voucher_new'), data), reverse('dashboard'))
        voucher = Voucher.objects.get()
        url = reverse('voucher_edit', args=[voucher.pk])
        for field, value in [('lines-0-memo', '가' * 1001), ('lines-4-memo', '적요만 입력')]:
            invalid = dict(data)
            invalid[field] = value
            response = self.client.post(url, invalid)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['rows'].is_valid())
            self.assertEqual(voucher.journal_lines.get(side='debit').memo, '가' * 1000)
            self.assertEqual(voucher.journal_lines.count(), 2)

    def test_all_five_memos_remain_distinct_and_html_is_escaped(self):
        data = journal_data([('1101', '100')] * 5, [('5001', '100')] * 5)
        for index in range(5):
            data[f'lines-{index}-memo'] = f'row-{index} <script>alert(1)</script>'
        self.client.post(reverse('voucher_new'), data)
        voucher = Voucher.objects.get()
        for line in voucher.journal_lines.all():
            self.assertEqual(line.memo, data[f'lines-{line.row - 1}-memo'])
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_five_rows_and_unbalanced_submission(self):
        response = self.client.get(reverse('voucher_new'))
        self.assertEqual(len(response.context['rows']), 5)
        self.assertContains(response, 'lines-4-credit_amount')
        response = self.client.post(reverse('voucher_new'), journal_data(credits=[('5001', '999')]))
        self.assertContains(response, '차변 합계와 대변 합계가 일치해야')
        self.assertFalse(Voucher.objects.exists())
        self.assertFalse(JournalLine.objects.exists())

    def test_multi_line_save_edit_and_cascade_delete(self):
        data = journal_data(debits=[('1101', '700'), ('1201', '400')], credits=[('5001', '1000'), ('2107', '100')])
        self.assertRedirects(self.client.post(reverse('voucher_new'), data), reverse('dashboard'))
        voucher = Voucher.objects.get()
        self.assertTrue(voucher.is_journal)
        self.assertEqual(voucher.amount, 1100)
        self.assertEqual(voucher.journal_lines.count(), 4)
        url = reverse('voucher_edit', args=[voucher.pk])
        response = self.client.get(url)
        self.assertEqual(response.context['rows'].forms[1].initial['debit_account'], '1201')
        self.client.post(url, journal_data(debits=[('1102', '3000')], credits=[('2101', '3000')], memo='수정'))
        voucher.refresh_from_db()
        self.assertEqual(voucher.amount, 3000)
        self.assertEqual(voucher.memo, '수정')
        self.assertEqual(voucher.journal_lines.count(), 2)
        self.assertEqual(set(voucher.journal_lines.values_list('account_id', flat=True)), {'1102', '2101'})
        self.assertContains(self.client.get(reverse('voucher_delete', args=[voucher.pk])), '2101')
        self.client.post(reverse('voucher_delete', args=[voucher.pk]))
        self.assertFalse(JournalLine.objects.exists())

    def test_blank_partial_invalid_and_forged_rows_are_rejected(self):
        cases = [journal_data(debits=[], credits=[]),
                 journal_data(debits=[('1101', '')]),
                 journal_data(debits=[('', '1000')]),
                 journal_data(debits=[('9999', '1000')])]
        for amount in ['0', '-1', '1.5', '100000000000000']:
            cases.append(journal_data(debits=[('1101', amount)], credits=[('5001', amount)]))
        for count in ['0', '1', '6', '10000']:
            cases.append(dict(journal_data(), **{'lines-TOTAL_FORMS': count}))
        missing_management = journal_data()
        del missing_management['lines-TOTAL_FORMS']
        cases.append(missing_management)
        for data in cases:
            response = self.client.post(reverse('voucher_new'), data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['rows'].is_valid())
            self.assertFalse(Voucher.objects.exists())

    def test_full_five_rows_and_total_limit(self):
        debits = [('1101', '100')] * 5
        credits = [('1102', '100')] * 5
        self.assertRedirects(self.client.post(reverse('voucher_new'), journal_data(debits, credits)), reverse('dashboard'))
        self.assertEqual(JournalLine.objects.count(), 10)
        self.assertEqual(Voucher.objects.get().amount, 500)
        response = self.client.post(reverse('voucher_new'), journal_data([('1101', '99999999999999'), ('1102', '1')], [('5001', '99999999999999'), ('2107', '1')]))
        self.assertFalse(response.context['rows'].is_valid())
        self.assertEqual(Voucher.objects.count(), 1)

    def test_invalid_edit_and_database_error_preserve_old_lines(self):
        self.client.post(reverse('voucher_new'), journal_data())
        voucher = Voucher.objects.get()
        url = reverse('voucher_edit', args=[voucher.pk])
        old_lines = list(voucher.journal_lines.values_list('id', 'account_id', 'amount'))
        self.client.post(url, journal_data(credits=[('5001', '999')], memo='잘못된 수정'))
        voucher.refresh_from_db()
        self.assertEqual(voucher.memo, '복합전표')
        self.assertEqual(list(voucher.journal_lines.values_list('id', 'account_id', 'amount')), old_lines)
        from unittest.mock import patch
        with patch('ledger.views.JournalLine.objects.bulk_create', side_effect=RuntimeError('save failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(url, journal_data(memo='실패한 수정'))
        voucher.refresh_from_db()
        self.assertEqual(voucher.memo, '복합전표')
        self.assertEqual(list(voucher.journal_lines.values_list('id', 'account_id', 'amount')), old_lines)

    def test_reporting_partner_period_and_no_income_double_count(self):
        self.client.post(reverse('voucher_new'), journal_data(counterparty=self.partner.pk))
        Voucher.objects.create(owner=self.user, date='2026-10-22', kind='income', account='매출-용역', amount=200)
        dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard.context['count'], 2)
        self.assertEqual(dashboard.context['income'], 200)
        self.assertEqual(dashboard.context['expense'], 0)
        self.assertEqual(len(dashboard.context['groups']), 1)
        self.assertEqual({g['account_id']: (g['debit'] or 0, g['credit'] or 0) for g in dashboard.context['journal_groups']}, {'1101': (1000, 0), '5001': (0, 1000)})
        self.assertContains(dashboard, '차변·대변 내역')
        excluded = self.client.get(reverse('dashboard'), {'end': '2026-10-21'})
        self.assertEqual(list(excluded.context['journal_groups']), [])
        ledger = self.client.get(reverse('partner_ledger'), {'partner': f'master:{self.partner.pk}', 'start': '2026-10-22', 'end': '2026-10-22'})
        self.assertEqual(ledger.context['income'], 0)
        self.assertEqual(ledger.context['expense'], 0)
        self.assertEqual(len(ledger.context['journal_vouchers']), 1)
        self.assertContains(ledger, '1101 · 현금')
        ledger = self.client.get(reverse('partner_ledger'), {'partner': f'master:{self.partner.pk}', 'start': '2026-10-23'})
        self.assertEqual(ledger.context['opening'], 0)
        self.assertEqual(list(ledger.context['journal_vouchers']), [])
