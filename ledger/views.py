from decimal import Decimal
from django.contrib import messages
from django.db.models import Sum, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from .forms import VoucherForm, PeriodForm
from .models import Voucher


def dashboard(request):
    period = PeriodForm(request.GET)
    vouchers = Voucher.objects.all()
    if period.is_valid():
        if period.cleaned_data.get('start'):
            vouchers = vouchers.filter(date__gte=period.cleaned_data['start'])
        if period.cleaned_data.get('end'):
            vouchers = vouchers.filter(date__lte=period.cleaned_data['end'])
    else:
        vouchers = vouchers.none()
    totals = vouchers.aggregate(income=Sum('amount', filter=Q(kind='income')), expense=Sum('amount', filter=Q(kind='expense')))
    income, expense = totals['income'] or Decimal(0), totals['expense'] or Decimal(0)
    groups = vouchers.order_by().values('kind', 'account').annotate(total=Sum('amount')).order_by('kind', '-total', 'account')
    return render(request, 'ledger/dashboard.html', {'period': period, 'vouchers': vouchers, 'groups': groups, 'income': income, 'expense': expense, 'balance': income-expense, 'count': vouchers.count()})


@require_http_methods(['GET', 'POST'])
def edit(request, pk=None):
    voucher = get_object_or_404(Voucher, pk=pk) if pk else None
    form = VoucherForm(request.POST or None, instance=voucher)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '전표를 저장했습니다.')
        return redirect('dashboard')
    return render(request, 'ledger/form.html', {'form': form, 'voucher': voucher})


@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    voucher = get_object_or_404(Voucher, pk=pk)
    if request.method == 'POST':
        voucher.delete()
        messages.success(request, '전표를 삭제했습니다.')
        return redirect('dashboard')
    return render(request, 'ledger/delete.html', {'voucher': voucher})
