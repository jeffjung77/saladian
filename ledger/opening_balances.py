from collections import defaultdict, deque
from datetime import timedelta, date
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .account_settings import visible_accounts
from .models import Account, Voucher, JournalLine, OpeningBalanceBatch
from .system_views import system_required
from .widgets import MoneyInput
from .audit import company_name

MAX_AMOUNT = Decimal('99999999999999')


class OwnerChoice(forms.ModelChoiceField):
    def label_from_instance(self, user):
        return f'{user.username} · {company_name(user) or "업체명 미등록"}'


class HeaderForm(forms.Form):
    owner = OwnerChoice(label='장부 사용자', queryset=get_user_model().objects.order_by('username'), empty_label=None)
    start_date = forms.DateField(label='사용 시작일', initial=timezone.localdate, widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    revision = forms.IntegerField(min_value=0, initial=0, widget=forms.HiddenInput)

    def clean_start_date(self):
        value = self.cleaned_data['start_date']
        if value < date(1900, 1, 2):
            raise forms.ValidationError('사용 시작일은 1900년 1월 2일 이후로 입력하세요.')
        return value


class BalanceRow(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), widget=forms.HiddenInput)
    debit = forms.DecimalField(label='차변 잔액', required=False, min_value=0, max_digits=14, decimal_places=0, widget=MoneyInput(attrs={'placeholder': '0'}))
    credit = forms.DecimalField(label='대변 잔액', required=False, min_value=0, max_digits=14, decimal_places=0, widget=MoneyInput(attrs={'placeholder': '0'}))

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = visible_accounts(owner)
        code = self.data.get(self.add_prefix('account')) if self.is_bound else self.initial.get('account')
        self.account_info = visible_accounts(owner).filter(pk=code).first()

    def clean(self):
        data = super().clean()
        if data.get('debit') and data.get('credit'):
            raise forms.ValidationError('같은 계정은 차변 또는 대변 한쪽에만 잔액을 입력하세요.')
        return data


class BalanceRows(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        used = set()
        for row in self.forms:
            account = row.cleaned_data.get('account')
            if account is None or account.pk in used:
                raise forms.ValidationError('계정 목록을 확인하고 화면을 새로고침한 뒤 다시 입력하세요.')
            used.add(account.pk)
        self.debit_total = sum((row.cleaned_data.get('debit') or 0 for row in self.forms), Decimal(0))
        self.credit_total = sum((row.cleaned_data.get('credit') or 0 for row in self.forms), Decimal(0))
        if not self.debit_total or self.debit_total != self.credit_total:
            raise forms.ValidationError('차변·대변 잔액을 각각 입력하고 합계를 일치시키세요.')
        if self.debit_total > MAX_AMOUNT:
            raise forms.ValidationError('기초잔액 합계는 99,999,999,999,999원 이하여야 합니다.')


Rows = forms.formset_factory(BalanceRow, formset=BalanceRows, extra=0, max_num=500, validate_max=True, absolute_max=500)


def paired_chunks(entries):
    """Split balanced postings into journals of at most five balanced pairs."""
    debits = deque([entry['account'], entry['debit']] for entry in entries if entry.get('debit'))
    credits = deque([entry['account'], entry['credit']] for entry in entries if entry.get('credit'))
    chunk = []
    while debits and credits:
        amount = min(debits[0][1], credits[0][1])
        chunk.append((debits[0][0], credits[0][0], amount))
        debits[0][1] -= amount
        credits[0][1] -= amount
        if not debits[0][1]:
            debits.popleft()
        if not credits[0][1]:
            credits.popleft()
        if len(chunk) == 5:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


@transaction.atomic
def save_opening(owner, start_date, revision, entries, actor):
    # Serialize first-time submissions on server databases; the unique owner also prevents duplicates.
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    previous = OpeningBalanceBatch.objects.select_for_update().filter(owner=owner).first()
    if revision != (previous.revision if previous else 0):
        raise forms.ValidationError('다른 작업에서 기초잔액을 변경했습니다. 화면을 새로고침한 뒤 다시 입력하세요.')
    if Voucher.objects.filter(owner=owner, opening_batch__isnull=True, date__lt=start_date).exists():
        raise forms.ValidationError('사용 시작일 이전에 일반 전표가 있습니다. 잔액의 이중 합산을 막기 위해 시작일과 기존 전표를 먼저 확인하세요.')
    batch = previous or OpeningBalanceBatch(owner=owner)
    batch.start_date = start_date
    batch.updated_by = actor
    batch.revision = revision + 1
    batch.save()
    batch.vouchers.all().delete()
    for chunk in paired_chunks(entries):
        voucher = Voucher.objects.create(owner=owner, opening_batch=batch, date=start_date-timedelta(days=1),
            entry_type='other', kind='journal', account='기초잔액', amount=sum(pair[2] for pair in chunk),
            memo=f'기초잔액 · 사용 시작일 {start_date:%Y-%m-%d}')
        JournalLine.objects.bulk_create([JournalLine(voucher=voucher, row=index, side=side, account=account,
            amount=amount, memo='기초잔액 이월') for index, (debit, credit, amount) in enumerate(chunk, 1)
            for side, account in [('debit', debit), ('credit', credit)]])
    return batch


@never_cache
@system_required
@require_http_methods(['GET', 'POST'])
def opening_balances(request):
    owner_id = request.POST.get('owner') if request.method == 'POST' else request.GET.get('owner', str(request.user.pk))
    owner = get_user_model().objects.filter(pk=owner_id).first() if str(owner_id).isascii() and str(owner_id).isdigit() and len(str(owner_id)) <= 18 else None
    batch = OpeningBalanceBatch.objects.filter(owner=owner).first() if owner else None
    initial = {'owner': owner, 'start_date': batch.start_date if batch else timezone.localdate(), 'revision': batch.revision if batch else 0}
    form = HeaderForm(request.POST if request.method == 'POST' else None, initial=initial)
    balances = defaultdict(lambda: Decimal(0))
    if batch:
        for line in JournalLine.objects.filter(voucher__opening_batch=batch):
            balances[line.account_id] += line.amount if line.side == 'debit' else -line.amount
    accounts = list(visible_accounts(owner)) if owner else []
    initial_rows = [{'account': account.pk, 'debit': max(balances[account.pk], 0) or '', 'credit': max(-balances[account.pk], 0) or ''} for account in accounts]
    rows = Rows(request.POST if request.method == 'POST' else None, initial=initial_rows, prefix='balances', form_kwargs={'owner': owner})
    if owner:
        request._audit_owner = owner
        request._audit_company = company_name(owner)
    if request.method == 'POST':
        header_valid, rows_valid = form.is_valid(), rows.is_valid()
        if header_valid and rows_valid:
            try:
                saved = save_opening(form.cleaned_data['owner'], form.cleaned_data['start_date'], form.cleaned_data['revision'], [row.cleaned_data for row in rows], request.user)
            except forms.ValidationError as exc:
                form.add_error(None, exc)
            else:
                request._audit_target = saved.pk
                messages.success(request, '계정별 기초잔액을 저장했습니다. 기존 기초잔액은 교체되며 일반 전표는 유지됩니다.')
                return redirect(f'{request.path}?owner={owner.pk}')
    return render(request, 'ledger/opening_balances.html', {'form': form, 'rows': rows, 'owner': owner, 'batch': batch})
