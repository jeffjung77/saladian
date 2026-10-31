from .ledger_scope import member_ids, anchor_user
from .voucher_quota import save_voucher, VoucherQuotaExceeded
from .models import JournalRowVAT
from .vat import VAT_FIELDS
from .excel import report_render
from decimal import Decimal
from datetime import timedelta
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import Sum, Q, F
from django.db import transaction, IntegrityError
from django.core.paginator import Paginator
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .forms import VoucherForm, PeriodForm, PartnerLedgerForm, JournalHeaderForm, JournalRows, BalanceSheetForm, IncomeStatementForm
from .models import Voucher, Account, JournalLine, Counterparty
from .forms import CounterpartyForm
from . import reports
from .forms import AccountLedgerForm
from .permissions import management_required
from .forms import AccountForm
from .models import AccountPreference
from .account_settings import visible_accounts
from .voucher_submission import prevent_duplicate_submission


@login_not_required
def business_overview(request):
    today = timezone.localdate()
    start = today.replace(day=1)
    if not request.user.is_authenticated:
        if not settings.DEBUG:
            return redirect_to_login(request.get_full_path())
        response = render(request, 'ledger/business_overview.html', {
            'guest_preview': True, 'today': today, 'start': start,
            'balance': {'assets': 0, 'liabilities': 0, 'equity': 0, 'liabilities_equity': 0, 'difference': 0, 'unclosed_profit': 0},
            'income': {'net_profit': 0, 'closing_count': 0},
            'cash_total': 0, 'cash_amount': 0, 'bank_amount': 0, 'cash_opening': 0, 'revenue': 0, 'expense': 0,
            'cash_points': [{'label': (start + timedelta(days=i)).strftime('%m/%d'), 'value': '0'} for i in range(today.day)],
            'profit_points': [{'label': label, 'value': '0'} for label in ['수익', '비용', '순이익']],
        })
        response['Cache-Control'] = 'private, no-store'
        return response
    source = Voucher.objects.filter(owner_id__in=member_ids(request.user))
    balance = reports.balance_sheet(today, vouchers=source)
    income = reports.income_statement(start, today, vouchers=source)
    accounts = {account.pk: account for account in Account.objects.all()}
    cash = {'1101': Decimal(0), '1102': Decimal(0)}
    changes = {}
    opening = Decimal(0)
    for voucher in source.filter(date__lte=today).select_related('account_master', 'settlement_account').prefetch_related('journal_lines__account', 'row_vat'):
        postings, reason = reports.voucher_postings(voucher, accounts)
        if reason:
            continue
        for posting in postings:
            if posting['account_id'] not in cash:
                continue
            cash[posting['account_id']] += posting['net']
            if voucher.date < start:
                opening += posting['net']
            else:
                changes[voucher.date] = changes.get(voucher.date, Decimal(0)) + posting['net']
    points = []
    running = opening
    day = start
    while day <= today:
        running += changes.get(day, Decimal(0))
        points.append({'label': day.strftime('%m/%d'), 'value': str(running)})
        day += timedelta(days=1)
    revenue = sum((section['total'] for section in income['sections'] if section['name'] in ('매출액', '영업외수익')), Decimal(0))
    expense = revenue - income['net_profit']
    response = render(request, 'ledger/business_overview.html', {
        'today': today, 'start': start, 'balance': balance, 'income': income,
        'cash_total': sum(cash.values(), Decimal(0)), 'cash_amount': cash['1101'], 'bank_amount': cash['1102'],
        'cash_opening': opening, 'revenue': revenue, 'expense': expense,
        'cash_points': points, 'profit_points': [
            {'label': '수익', 'value': str(revenue)}, {'label': '비용', 'value': str(expense)},
            {'label': '순이익', 'value': str(income['net_profit'])}],
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@require_http_methods(['GET'])
def counterparty_options(request):
    options = list(Counterparty.objects.filter(owner_id__in=member_ids(request.user)).values('id', 'name'))
    response = JsonResponse({'counterparties': options})
    response['Cache-Control'] = 'private, no-store'
    return response


@management_required
def counterparties(request):
    query = request.GET.get('q', '').strip()[:100]
    partners = Counterparty.objects.filter(owner_id__in=member_ids(request.user))
    if query:
        partners = partners.filter(Q(name__icontains=query) | Q(business_number__icontains=query) | Q(contact_name__icontains=query) | Q(phone__icontains=query))
    if query.upper().startswith('CP') and query[2:].isascii() and query[2:].isdigit() and len(query[2:]) <= 18:
        partners = Counterparty.objects.filter(owner_id__in=member_ids(request.user), pk=int(query[2:]))
    per_page = 5 if request.GET.get('per_page') == '5' else 10
    page = Paginator(partners, per_page).get_page(request.GET.get('page'))
    return render(request, 'ledger/counterparties.html', {
        'page': page, 'q': query, 'per_page': per_page,
        'page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1)})


@require_http_methods(['GET', 'POST'])
@management_required
def counterparty_edit(request, pk=None):
    partner = get_object_or_404(Counterparty, pk=pk, owner_id__in=member_ids(request.user)) if pk else None
    form = CounterpartyForm(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, instance=partner, user=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
                request._audit_target = str(form.instance.pk)
        except IntegrityError:
            if not Counterparty.objects.filter(owner_id__in=member_ids(request.user), name=form.cleaned_data['name']).exists():
                raise
            form.add_error('name', '이미 등록된 거래처명입니다.')
        else:
            messages.success(request, '거래처를 저장했습니다.')
            return redirect('counterparties')
    return render(request, 'ledger/counterparty_form.html', {'form': form, 'partner': partner})


def account_ledger(request):
    today = timezone.localdate()
    form = AccountLedgerForm(request.GET if any(key != 'export' for key in request.GET) else None, initial={'start': today.replace(month=1, day=1), 'end': today}, user=request.user)
    report = None
    if form.is_bound and form.is_valid():
        report = reports.account_ledger(form.cleaned_data['account'], form.cleaned_data['start'], form.cleaned_data['end'], vouchers=Voucher.objects.filter(owner_id__in=member_ids(request.user)))
    return report_render(request, 'ledger/account_ledger.html', {'form': form, 'report': report})


def trial_balance(request):
    today = timezone.localdate()
    form = BalanceSheetForm(request.GET if any(key != 'export' for key in request.GET) else {'as_of': today})
    report = reports.trial_balance(form.cleaned_data['as_of'], vouchers=Voucher.objects.filter(owner_id__in=member_ids(request.user))) if form.is_valid() else None
    return report_render(request, 'ledger/trial_balance.html', {'form': form, 'report': report})


def balance_sheet(request):
    today = timezone.localdate()
    form = BalanceSheetForm(request.GET if any(key != 'export' for key in request.GET) else {'as_of': today})
    report = reports.balance_sheet(form.cleaned_data['as_of'], vouchers=Voucher.objects.filter(owner_id__in=member_ids(request.user))) if form.is_valid() else None
    return report_render(request, 'ledger/balance_sheet.html', {'form': form, 'report': report})


def income_statement(request):
    today = timezone.localdate()
    form = IncomeStatementForm(request.GET if any(key != 'export' for key in request.GET) else {'start': today.replace(month=1, day=1), 'end': today})
    report = reports.income_statement(form.cleaned_data['start'], form.cleaned_data['end'], vouchers=Voucher.objects.filter(owner_id__in=member_ids(request.user))) if form.is_valid() else None
    return report_render(request, 'ledger/income_statement.html', {'form': form, 'report': report})


@management_required
def accounts(request):
    disabled = set(AccountPreference.objects.filter(owner_id__in=member_ids(request.user), is_active=False).values_list('account_id', flat=True))
    rows = list(visible_accounts(request.user))
    for account in rows:
        account.is_active = account.pk not in disabled
    return render(request, 'ledger/accounts.html', {'accounts': rows})


@management_required
@require_http_methods(['POST'])
def account_status(request, code):
    account = get_object_or_404(visible_accounts(request.user), pk=code)
    state = request.POST.get('is_active')
    if state not in ('0', '1'):
        return JsonResponse({'error': '사용 여부를 선택하세요.'}, status=400)
    with transaction.atomic():
        AccountPreference.objects.filter(owner_id__in=member_ids(request.user), account=account).delete()
        AccountPreference.objects.create(owner=anchor_user(request.user), account=account, is_active=state == '1')
    messages.success(request, f'{account} 계정을 {"사용" if state == "1" else "비사용"}으로 설정했습니다.')
    return redirect('accounts')


@management_required
@require_http_methods(['GET', 'POST'])
def account_new(request):
    form = AccountForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                account = form.save(commit=False)
                account.owner = request.user
                account.save()
                request._audit_target = account.pk
        except IntegrityError:
            if not Account.objects.filter(pk=form.cleaned_data['code']).exists():
                raise
            form.add_error('code', '이미 등록된 계정코드입니다.')
        else:
            messages.success(request, '신규 계정과목을 등록했습니다.')
            return redirect('accounts')
    return render(request, 'ledger/account_form.html', {'form': form})


def partner_ledger(request):
    form = PartnerLedgerForm(request.GET if any(key != 'export' for key in request.GET) else None, user=request.user)
    rows = []
    income = expense = opening = Decimal(0)
    partner_name = None
    journal_vouchers = Voucher.objects.none()
    if form.is_valid():
        selected = form.cleaned_data['partner']
        vouchers = Voucher.objects.select_related('account_master', 'counterparty').filter(owner_id__in=member_ids(request.user))
        if selected.startswith('master:'):
            partner = get_object_or_404(Counterparty, pk=selected[len('master:'):], owner_id__in=member_ids(request.user))
            partner_name = partner.name
            vouchers = vouchers.filter(counterparty=partner)
        else:
            partner = '' if selected == 'unassigned:' else selected[len('name:'):]
            partner_name = partner or '거래처 미입력'
            vouchers = vouchers.filter(counterparty__isnull=True, partner=partner)
        start, end = form.cleaned_data.get('start'), form.cleaned_data.get('end')
        if start:
            previous = vouchers.filter(date__lt=start).aggregate(income=Sum(F('amount') + F('vat_amount'), filter=Q(kind='income')), expense=Sum(F('amount') + F('vat_amount'), filter=Q(kind='expense')))
            opening = (previous['income'] or Decimal(0)) - (previous['expense'] or Decimal(0))
            vouchers = vouchers.filter(date__gte=start)
        if end:
            vouchers = vouchers.filter(date__lte=end)
        journal_vouchers = vouchers.filter(kind=Voucher.Kind.JOURNAL).prefetch_related('journal_lines__account', 'row_vat').order_by('date', 'pk')
        vouchers = vouchers.exclude(kind=Voucher.Kind.JOURNAL)
        running = opening
        for voucher in vouchers.order_by('date', 'pk'):
            if voucher.kind == Voucher.Kind.INCOME:
                income += voucher.gross_amount
                running += voucher.gross_amount
            else:
                expense += voucher.gross_amount
                running -= voucher.gross_amount
            rows.append({'voucher': voucher, 'balance': running})
    return report_render(request, 'ledger/partner_ledger.html', {
        'form': form, 'rows': rows, 'partner_name': partner_name,
        'income': income, 'expense': expense, 'opening': opening,
        'closing': opening + income - expense,
        'balance': income - expense,
        'journal_vouchers': journal_vouchers,
    })


def voucher_entry(request):
    return render(request, 'ledger/voucher_entry.html')


def dashboard(request):
    period = PeriodForm(request.GET)
    vouchers = Voucher.objects.select_related('account_master', 'counterparty').filter(owner_id__in=member_ids(request.user))
    if period.is_valid():
        if period.cleaned_data.get('start'):
            vouchers = vouchers.filter(date__gte=period.cleaned_data['start'])
        if period.cleaned_data.get('end'):
            vouchers = vouchers.filter(date__lte=period.cleaned_data['end'])
    else:
        vouchers = vouchers.none()
    totals = vouchers.aggregate(income=Sum(F('amount') + F('vat_amount'), filter=Q(kind='income')), expense=Sum(F('amount') + F('vat_amount'), filter=Q(kind='expense')))
    income, expense = totals['income'] or Decimal(0), totals['expense'] or Decimal(0)
    groups = vouchers.exclude(kind=Voucher.Kind.JOURNAL).order_by().values('kind', 'account', 'account_master_id').annotate(total=Sum('amount')).order_by('kind', '-total', 'account_master_id', 'account')
    journal_groups = JournalLine.objects.filter(voucher__in=vouchers).order_by().values('account_id', 'account__name').annotate(debit=Sum('amount', filter=Q(side='debit')), credit=Sum('amount', filter=Q(side='credit'))).order_by('account_id')
    vouchers = vouchers.prefetch_related('journal_lines__account', 'row_vat')
    page = Paginator(vouchers, 10).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    query.pop('export', None)
    return report_render(request, 'ledger/dashboard.html', {'period': period, 'vouchers': vouchers, 'voucher_page': page, 'page_query': query.urlencode(), 'page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1), 'groups': groups, 'journal_groups': journal_groups, 'income': income, 'expense': expense, 'balance': income-expense, 'count': page.paginator.count})


@require_http_methods(['GET', 'POST'])
@prevent_duplicate_submission
def edit(request, pk=None, entry_type=Voucher.EntryType.OTHER):
    voucher = get_object_or_404(Voucher, pk=pk, owner_id__in=member_ids(request.user)) if pk else None
    if voucher and voucher.closing_batch_id:
        return render(request, 'ledger/year_end_locked.html', status=403)
    if voucher and voucher.opening_batch_id:
        return render(request, 'ledger/opening_balance_locked.html', status=403)
    if (voucher and voucher.is_journal) or (not voucher and entry_type == Voucher.EntryType.OTHER):
        return journal_edit(request, voucher)
    if voucher:
        entry_type = voucher.entry_type
    form = VoucherForm(request.POST if request.method == 'POST' else None, instance=voucher, entry_type=entry_type, user=request.user)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        saved.owner = voucher.owner if voucher else request.user
        if not voucher:
            saved.submission_token = form.cleaned_data.get('submission_token')
        try:
            save_voucher(saved)
        except VoucherQuotaExceeded as exc:
            form.add_error(None, str(exc))
            form.quota_popup = str(exc)
            return render(request, "ledger/form.html", {"form": form, "voucher": voucher, "entry_type": entry_type, "entry_label": dict(Voucher.EntryType.choices)[entry_type]})
        request._audit_target = str(saved.pk)
        messages.success(request, f'전표가 저장되었습니다. 전표번호는 {saved.pk} 번입니다.', extra_tags=f'voucher-saved-popup voucher-entry-{saved.entry_type}')
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
    if voucher:
        for tax in voucher.row_vat.all():
            initial[tax.row - 1].update({name: getattr(tax, name) for name in VAT_FIELDS})
    data = request.POST if request.method == 'POST' else None
    form = JournalHeaderForm(data, instance=voucher, user=request.user)
    rows = JournalRows(data, prefix='lines', initial=initial, form_kwargs={'user': request.user})
    if request.method == 'POST':
        header_valid, rows_valid = form.is_valid(), rows.is_valid()
        if any(data.get(name) for name in VAT_FIELDS):
            form.add_error(None, '부가세 입력 위치가 행별 입력으로 변경되었습니다. 화면을 새로고침한 뒤 분개 행에 입력하세요.')
            header_valid = False
        if header_valid and rows_valid:
            try:
                with transaction.atomic():
                    saved = form.save(commit=False)
                    saved.owner = voucher.owner if voucher else request.user
                    if not voucher:
                        saved.submission_token = form.cleaned_data.get('submission_token')
                    saved.entry_type = Voucher.EntryType.OTHER
                    saved.kind = Voucher.Kind.JOURNAL
                    saved.account = '복합전표'
                    saved.account_master = None
                    saved.amount = rows.debit_total
                    for name in VAT_FIELDS:
                        setattr(saved, name, Decimal(0) if name in ('vat_amount', 'vat_deductible') else '')
                    save_voucher(saved)
                    request._audit_target = str(saved.pk)
                    saved.journal_lines.all().delete()
                    lines = []
                    for number, row in enumerate(rows, start=1):
                        for side in ['debit', 'credit']:
                            if row.cleaned_data.get(f'{side}_account'):
                                lines.append(JournalLine(voucher=saved, row=number, side=side, account=row.cleaned_data[f'{side}_account'], amount=row.cleaned_data[f'{side}_amount'], memo=row.cleaned_data.get('memo', '')))
                    JournalLine.objects.bulk_create(lines)
                    saved.row_vat.all().delete()
                    JournalRowVAT.objects.bulk_create([JournalRowVAT(voucher=saved, row=number,
                        **{name: row.cleaned_data.get(name, '') for name in VAT_FIELDS})
                        for number, row in enumerate(rows, start=1) if row.cleaned_data.get('vat_code')])
            except VoucherQuotaExceeded as exc:
                form.add_error(None, str(exc))
                form.quota_popup = str(exc)
                return render(request, "ledger/journal_form.html", {"form": form, "rows": rows, "voucher": voucher, "entry_type": "other", "visible_rows": 5})
            messages.success(request, f'전표가 저장되었습니다. 전표번호는 {saved.pk} 번입니다.', extra_tags='voucher-saved-popup voucher-entry-other')
            return redirect('dashboard')
    visible_rows = max([1] + [number for number, initial_row in enumerate(initial, start=1) if initial_row])
    if request.method == 'POST':
        try:
            visible_rows = max(visible_rows, min(5, max(1, int(request.POST.get('visible_line_count', 1)))))
        except (ValueError, TypeError):
            pass
        for number, row in enumerate(rows, start=1):
            if row.errors or any(row.data.get(row.add_prefix(field)) not in (None, '', '0') for field in row.fields):
                visible_rows = max(visible_rows, number)
    return render(request, 'ledger/journal_form.html', {'form': form, 'rows': rows, 'voucher': voucher, 'entry_type': 'other', 'visible_rows': visible_rows})


@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    voucher = get_object_or_404(Voucher, pk=pk, owner_id__in=member_ids(request.user))
    if voucher.closing_batch_id:
        return render(request, 'ledger/year_end_locked.html', status=403)
    if voucher.opening_batch_id:
        return render(request, 'ledger/opening_balance_locked.html', status=403)
    if request.method == 'POST':
        voucher.delete()
        messages.success(request, '전표를 삭제했습니다.')
        return redirect('dashboard')
    return render(request, 'ledger/delete.html', {'voucher': voucher})


@require_http_methods(['GET'])
@management_required
def counterparty_certificate(request, pk):
    partner = get_object_or_404(Counterparty, pk=pk, owner_id__in=member_ids(request.user))
    if not partner.business_certificate:
        raise Http404
    try:
        response = FileResponse(partner.business_certificate.open('rb'), as_attachment=True, filename='business-certificate.pdf', content_type='application/pdf')
    except FileNotFoundError:
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
