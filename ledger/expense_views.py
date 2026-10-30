from calendar import monthrange
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import ExpenseChartPreference, Voucher
from .reports import collect_balances


class ExpenseFilter(forms.Form):
    month = forms.DateField(input_formats=['%Y-%m'], widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month'}), label='조회 월')
    user = forms.ModelChoiceField(queryset=get_user_model().objects.none(), label='사용자')
    enabled = forms.BooleanField(required=False, label='사업현황에 비용 그래프 표시')

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = get_user_model().objects.order_by('username') if actor.is_superuser else get_user_model().objects.filter(pk=actor.pk)


def monthly_expenses(owner, month, end=None):
    start = month.replace(day=1)
    end = end or month.replace(day=monthrange(month.year, month.month)[1])
    accounts, balances, excluded, _ = collect_balances(Voucher.objects.filter(owner=owner, date__gte=start, date__lte=end, is_closing=False))
    rows = [{'name': a.name, 'code': a.code, 'amount': balances.get(a.pk, 0)} for a in accounts.values()
            if a.category in ('매출원가', '판매비와관리비', '영업외비용', '법인세비용') and balances.get(a.pk, 0) > 0]
    rows.sort(key=lambda r: (-r['amount'], r['code']))
    rows = rows[:10]
    maximum = max((r['amount'] for r in rows), default=1)
    for row in rows:
        row['width'] = float(row['amount'] / maximum * 100)
    return {'expense_rows': rows, 'expense_month': start, 'expense_excluded': len(excluded)}


@login_required
@require_http_methods(['GET', 'POST'])
def expense_status(request):
    data = request.POST if request.method == 'POST' else request.GET
    form = ExpenseFilter(data or None, actor=request.user, initial={'month': timezone.localdate().strftime('%Y-%m'), 'user': request.user.pk})
    context = {'form': form}
    if not data:
        context.update(monthly_expenses(request.user, timezone.localdate()))
        form.initial['enabled'] = ExpenseChartPreference.objects.filter(owner=request.user, enabled=True).exists()
    elif form.is_valid():
        owner = form.cleaned_data['user']
        month = form.cleaned_data['month']
        if request.method == 'POST':
            ExpenseChartPreference.objects.update_or_create(owner=owner, defaults={'enabled': form.cleaned_data['enabled']})
            return redirect(f"{request.path}?user={owner.pk}&month={form.cleaned_data['month']:%Y-%m}")
        form = ExpenseFilter(actor=request.user, initial={'user': owner.pk, 'month': form.cleaned_data['month'].strftime('%Y-%m'), 'enabled': ExpenseChartPreference.objects.filter(owner=owner, enabled=True).exists()})
        context['form'] = form
        context.update(monthly_expenses(owner, month))
    return render(request, 'ledger/expense_status.html', context)
