from decimal import Decimal
from django.contrib import messages
from django.db.models import Sum, Q
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .forms import VoucherForm, PeriodForm, PartnerLedgerForm, JournalHeaderForm, JournalRows, BalanceSheetForm, IncomeStatementForm
from .models import Voucher, Account, JournalLine
from . import reports
from .forms import AccountLedgerForm


def account_ledger(request):
    today = timezone.localdate()
    form = AccountLedgerForm(request.GET if request.GET else None, initial={'start': today.replace(month=1, day=1), 'end': today})
    report = None
    if form.is_bound and form.is_valid():
        report = reports.account_ledger(form.cleaned_data['account'], form.cleaned_data['start'], form.cleaned_data['end'])
    return render(request, 'ledger/account_ledger.html', {'form': form, 'report': report})


def balance_sheet(request):
    today = timezone.localdate()
    form = BalanceSheetForm(request.GET if request.GET else {'as_of': today})
    report = reports.balance_sheet(form.cleaned_data['as_of']) if form.is_valid() else None
    return render(request, 'ledger/balance_sheet.html', {'form': form, 'report': report})


def income_statement(request):
    today = timezone.localdate()
    form = IncomeStatementForm(request.GET if request.GET else {'start': today.replace(month=1, day=1), 'end': today})
    report = reports.income_statement(form.cleaned_data['start'], form.cleaned_data['end']) if form.is_valid() else None
    return render(request, 'ledger/income_statement.html', {'form': form, 'report': report})


def accounts(request):
    return render(request, 'ledger/accounts.html', {'accounts': Account.objects.all()})


def partner_ledger(request):
    form = PartnerLedgerForm(request.GET if request.GET else None)
    rows = []
    income = expense = opening = Decimal(0)
    partner_name = None
    journal_vouchers = Voucher.objects.none()
    if form.is_valid():
        selected = form.cleaned_data['partner']
        partner = '' if selected == 'unassigned:' else selected[len('name:'):]
        partner_name = partner or '거래처 미입력'
        vouchers = Voucher.objects.select_related('account_master').filter(partner=partner)
        start, end = form.cleaned_data.get('start'), form.cleaned_data.get('end')
        if start:
            previous = vouchers.filter(date__lt=start).aggregate(income=Sum('amount', filter=Q(kind='income')), expense=Sum('amount', filter=Q(kind='expense')))
            opening = (previous['income'] or Decimal(0)) - (previous['expense'] or Decimal(0))
            vouchers = vouchers.filter(date__gte=start)
        if end:
            vouchers = vouchers.filter(date__lte=end)
        journal_vouchers = vouchers.filter(kind=Voucher.Kind.JOURNAL).prefetch_related('journal_lines__account').order_by('date', 'pk')
        vouchers = vouchers.exclude(kind=Voucher.Kind.JOURNAL)
        running = opening
        for voucher in vouchers.order_by('date', 'pk'):
            if voucher.kind == Voucher.Kind.INCOME:
                income += voucher.amount
                running += voucher.amount
            else:
                expense += voucher.amount
                running -= voucher.amount
            rows.append({'voucher': voucher, 'balance': running})
    return render(request, 'ledger/partner_ledger.html', {
        'form': form, 'rows': rows, 'partner_name': partner_name,
        'income': income, 'expense': expense, 'opening': opening,
        'closing': opening + income - expense,
        'balance': income - expense,
        'journal_vouchers': journal_vouchers,
    })


def dashboard(request):
    period = PeriodForm(request.GET)
    vouchers = Voucher.objects.select_related('account_master').all()
    if period.is_valid():
        if period.cleaned_data.get('start'):
            vouchers = vouchers.filter(date__gte=period.cleaned_data['start'])
        if period.cleaned_data.get('end'):
            vouchers = vouchers.filter(date__lte=period.cleaned_data['end'])
    else:
        vouchers = vouchers.none()
    totals = vouchers.aggregate(income=Sum('amount', filter=Q(kind='income')), expense=Sum('amount', filter=Q(kind='expense')))
    income, expense = totals['income'] or Decimal(0), totals['expense'] or Decimal(0)
    groups = vouchers.exclude(kind=Voucher.Kind.JOURNAL).order_by().values('kind', 'account', 'account_master_id').annotate(total=Sum('amount')).order_by('kind', '-total', 'account_master_id', 'account')
    journal_groups = JournalLine.objects.filter(voucher__in=vouchers).order_by().values('account_id', 'account__name').annotate(debit=Sum('amount', filter=Q(side='debit')), credit=Sum('amount', filter=Q(side='credit'))).order_by('account_id')
    return render(request, 'ledger/dashboard.html', {'period': period, 'vouchers': vouchers.prefetch_related('journal_lines__account'), 'groups': groups, 'journal_groups': journal_groups, 'income': income, 'expense': expense, 'balance': income-expense, 'count': vouchers.count()})


@require_http_methods(['GET', 'POST'])
def edit(request, pk=None, entry_type=Voucher.EntryType.OTHER):
    voucher = get_object_or_404(Voucher, pk=pk) if pk else None
    if (voucher and voucher.is_journal) or (not voucher and entry_type == Voucher.EntryType.OTHER):
        return journal_edit(request, voucher)
    if voucher:
        entry_type = voucher.entry_type
    form = VoucherForm(request.POST if request.method == 'POST' else None, instance=voucher, entry_type=entry_type)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '전표를 저장했습니다.')
        return redirect('dashboard')
    labels = dict(Voucher.EntryType.choices)
    return render(request, 'ledger/form.html', {'form': form, 'voucher': voucher, 'entry_type': entry_type, 'entry_label': labels[entry_type]})


def journal_edit(request, voucher=None):
    initial = [{} for _ in range(5)]
    if voucher:
        for line in voucher.journal_lines.all():
            initial[line.row - 1][f'{line.side}_account'] = line.account_id
            initial[line.row - 1][f'{line.side}_amount'] = line.amount
            initial[line.row - 1]['memo'] = line.memo
    data = request.POST if request.method == 'POST' else None
    form = JournalHeaderForm(data, instance=voucher)
    rows = JournalRows(data, prefix='lines', initial=initial)
    if request.method == 'POST':
        header_valid, rows_valid = form.is_valid(), rows.is_valid()
        if header_valid and rows_valid:
            with transaction.atomic():
                saved = form.save(commit=False)
                saved.entry_type = Voucher.EntryType.OTHER
                saved.kind = Voucher.Kind.JOURNAL
                saved.account = '복합전표'
                saved.account_master = None
                saved.amount = rows.debit_total
                saved.save()
                saved.journal_lines.all().delete()
                lines = []
                for number, row in enumerate(rows, start=1):
                    for side in ['debit', 'credit']:
                        if row.cleaned_data.get(f'{side}_account'):
                            lines.append(JournalLine(voucher=saved, row=number, side=side, account=row.cleaned_data[f'{side}_account'], amount=row.cleaned_data[f'{side}_amount'], memo=row.cleaned_data.get('memo', '')))
                JournalLine.objects.bulk_create(lines)
            messages.success(request, '차변·대변 전표를 저장했습니다.')
            return redirect('dashboard')
    return render(request, 'ledger/journal_form.html', {'form': form, 'rows': rows, 'voucher': voucher, 'entry_type': 'other'})


@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    voucher = get_object_or_404(Voucher, pk=pk)
    if request.method == 'POST':
        voucher.delete()
        messages.success(request, '전표를 삭제했습니다.')
        return redirect('dashboard')
    return render(request, 'ledger/delete.html', {'voucher': voucher})
