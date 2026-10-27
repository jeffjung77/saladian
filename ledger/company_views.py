from .pagination import page_size
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Voucher, Counterparty, AccountPreference, AuditLog
from .account_settings import visible_accounts
from .forms import IncomeStatementForm, BalanceSheetForm, AccountLedgerForm
from . import reports

TABS = [('summary', '종합현황'), ('vouchers', '전표'), ('partners', '거래처'),
        ('accounts', '계정과목'), ('income', '손익계산서'), ('balance', '대차대조표'),
        ('account_ledger', '계정별원장'), ('partner_ledger', '거래처별원장'), ('logs', '로그')]


@never_cache
@require_GET
def company_list(request):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    query = request.GET.get('q', '').strip()[:100]
    companies = get_user_model().objects.select_related('subscription', 'business_profile').annotate(
        voucher_count=Count('vouchers', distinct=True), partner_count=Count('counterparties', distinct=True)).order_by('username')
    if query:
        companies = companies.filter(Q(username__icontains=query) | Q(subscription__company_name__icontains=query) |
            Q(subscription__business_number__icontains=query) | Q(business_profile__company_name__icontains=query))
    page = Paginator(companies, page_size(request)).get_page(request.GET.get('page'))
    return render(request, 'ledger/company_list.html', {'page': page, 'q': query})


@never_cache
@require_GET
def company_detail(request, company_id):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    owner = get_object_or_404(get_user_model().objects.select_related('subscription', 'business_profile'), pk=company_id)
    tab = request.GET.get('tab', 'summary')
    if tab not in dict(TABS):
        tab = 'summary'
    today = timezone.localdate()
    source = Voucher.objects.filter(owner=owner)
    period = IncomeStatementForm({'start': request.GET.get('start', today.replace(day=1)), 'end': request.GET.get('end', today)})
    as_of = BalanceSheetForm({'as_of': request.GET.get('as_of', today)})
    context = {'owner': owner, 'tab': tab, 'tabs': TABS, 'period': period, 'as_of': as_of,
        'voucher_count': source.count(), 'partner_count': Counterparty.objects.filter(owner=owner).count()}
    if tab in ('summary', 'income') and period.is_valid():
        context['income'] = reports.income_statement(period.cleaned_data['start'], period.cleaned_data['end'], vouchers=source)
    if tab in ('summary', 'balance') and as_of.is_valid():
        context['balance'] = reports.balance_sheet(as_of.cleaned_data['as_of'], vouchers=source)
        context['cash'] = sum((row['amount'] for section in context['balance']['sections'] for group in section['groups']
            for row in group['rows'] if row['account'].pk in ('1101', '1102')), Decimal(0))
    if tab == 'vouchers':
        context['page'] = Paginator(source.select_related('account_master', 'settlement_account', 'counterparty').prefetch_related('journal_lines__account'), 25).get_page(request.GET.get('page'))
    elif tab == 'partners':
        context['page'] = Paginator(Counterparty.objects.filter(owner=owner), 25).get_page(request.GET.get('page'))
    elif tab == 'accounts':
        disabled = set(AccountPreference.objects.filter(owner=owner, is_active=False).values_list('account_id', flat=True))
        accounts = list(visible_accounts(owner))
        for account in accounts:
            account.is_active = account.pk not in disabled
        context['accounts'] = accounts
    elif tab == 'logs':
        context['page'] = Paginator(AuditLog.objects.filter(company_user=owner), 50).get_page(request.GET.get('page'))
    elif tab == 'account_ledger':
        form = AccountLedgerForm({'account': request.GET.get('account', ''), 'start': request.GET.get('start', today.replace(day=1)), 'end': request.GET.get('end', today)}, user=owner)
        context['ledger_form'] = form
        if request.GET.get('account') and form.is_valid():
            context['ledger'] = reports.account_ledger(form.cleaned_data['account'], form.cleaned_data['start'], form.cleaned_data['end'], vouchers=source)
    elif tab == 'partner_ledger':
        context['partners'] = Counterparty.objects.filter(owner=owner)
        selected = request.GET.get('partner')
        if selected:
            partner = get_object_or_404(Counterparty, pk=selected if selected.isascii() and selected.isdigit() and len(selected) <= 18 else 0, owner=owner)
            context['selected_partner'] = partner
            if period.is_valid():
                vouchers = source.filter(counterparty=partner, date__gte=period.cleaned_data['start'], date__lte=period.cleaned_data['end'])
                context['page'] = Paginator(vouchers.select_related('account_master', 'settlement_account', 'counterparty').prefetch_related('journal_lines__account'), 25).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query['tab'] = tab
    query.pop('page', None)
    context['query'] = query.urlencode()
    return render(request, 'ledger/company_detail.html', context)
