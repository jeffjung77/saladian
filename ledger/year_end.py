from .ledger_scope import member_ids, anchor_user
import hashlib
import json
from datetime import date
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import Account, Voucher, JournalLine, YearEndClosing
from .permissions import management_required
from .opening_balances import paired_chunks, MAX_AMOUNT
from .reports import collect_balances, account_group, PL_CATEGORIES, ZERO


class ClosingForm(forms.Form):
    year = forms.IntegerField(label='결산연도', min_value=1900, max_value=9998)

    def clean_year(self):
        year = self.cleaned_data['year']
        if date(year, 12, 31) > timezone.localdate():
            raise forms.ValidationError('연말 차기이월은 해당 연도 12월 31일부터 수행할 수 있습니다.')
        return year


def preview(owner, year):
    source = Voucher.objects.filter(owner_id__in=member_ids(owner), date__lte=date(year, 12, 31)).exclude(closing_batch__year=year)
    accounts, balances, excluded, count = collect_balances(source)
    if excluded:
        raise forms.ValidationError('미반영 전표가 있습니다. 합계잔액 시산표에서 전표를 확인한 뒤 다시 수행하세요.')
    if YearEndClosing.objects.filter(owner_id__in=member_ids(owner), year__gt=year).exists():
        raise forms.ValidationError('이후 연도의 차기이월이 존재하여 이 연도를 변경할 수 없습니다.')
    _, prior, _, _ = collect_balances(source.filter(date__lt=date(year, 1, 1)))
    if any(value for code, value in prior.items() if account_group(accounts[code]) in PL_CATEGORIES):
        raise forms.ValidationError('이전 연도의 미이월 손익계정 잔액이 있습니다. 이전 연도부터 순서대로 차기이월하세요.')
    retained = accounts.get('3403')
    if retained is None or retained.element != '자본':
        raise forms.ValidationError('3403 이익잉여금 계정과목을 확인하세요.')
    entries = []
    net_profit = ZERO
    for code in sorted(balances):
        net = balances[code]
        if not net or account_group(accounts[code]) not in PL_CATEGORIES:
            continue
        entries.append({'account': accounts[code], 'debit': max(-net, ZERO), 'credit': max(net, ZERO)})
        net_profit -= net
    if net_profit:
        entries.append({'account': retained, 'debit': max(-net_profit, ZERO), 'credit': max(net_profit, ZERO)})
    debit = sum((r['debit'] for r in entries), ZERO)
    credit = sum((r['credit'] for r in entries), ZERO)
    if not entries and not YearEndClosing.objects.filter(owner_id__in=member_ids(owner), year=year).exists():
        raise forms.ValidationError('이월할 손익계정 잔액이 없습니다.')
    if debit != credit or debit > MAX_AMOUNT:
        raise forms.ValidationError('차변·대변 합계 또는 전표 금액 범위를 확인하세요.')
    # Include all source fields and journal rows so even offsetting changes invalidate confirmation.
    snapshot = list(source.order_by('pk').values())
    lines = list(JournalLine.objects.filter(voucher__in=source).order_by('pk').values())
    own = list(Voucher.objects.filter(owner_id__in=member_ids(owner), closing_batch__year=year).order_by('pk').values())
    own_lines = list(JournalLine.objects.filter(voucher__owner_id__in=member_ids(owner), voucher__closing_batch__year=year).order_by('pk').values())
    payload = [snapshot, lines, own, own_lines, list(Account.objects.order_by('pk').values()), year, owner.pk]
    fingerprint = hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()
    return dict(entries=entries, net_profit=net_profit, debit=debit, credit=credit, fingerprint=fingerprint,
                existing=YearEndClosing.objects.filter(owner_id__in=member_ids(owner), year=year).first(), included_count=count)


@transaction.atomic
def execute(owner, year, token):
    get_user_model().objects.select_for_update().get(pk=anchor_user(owner).pk)
    try:
        expected = signing.loads(token, salt='year-end', max_age=1800)
    except signing.BadSignature:
        raise forms.ValidationError('미리보기 유효시간이 지났습니다. 분개 미리보기를 다시 확인하세요.')
    result = preview(owner, year)
    if expected != [owner.pk, year, result['fingerprint']]:
        raise forms.ValidationError('미리보기 이후 장부가 변경되었습니다. 분개 미리보기를 다시 확인하세요.')
    batch = result['existing'] or YearEndClosing(owner=anchor_user(owner), year=year)
    batch.updated_by = owner
    batch.save()
    batch.vouchers.all().delete()
    for chunk in paired_chunks(result['entries']):
        voucher = Voucher.objects.create(owner=owner, closing_batch=batch, date=date(year, 12, 31),
            kind='journal', entry_type='other', is_closing=True, account='연말 차기이월',
            amount=sum(pair[2] for pair in chunk), memo=f'{year}년 연말 차기이월 · 손익계정 대체')
        JournalLine.objects.bulk_create([JournalLine(voucher=voucher, row=index, side=side, account=account,
            amount=amount, memo=f'{year}년 손익 이월') for index, (debit, credit, amount) in enumerate(chunk, 1)
            for side, account in [('debit', debit), ('credit', credit)]])
    return batch


@never_cache
@management_required
@require_http_methods(['GET', 'POST'])
def year_end(request):
    form = ClosingForm(request.POST if request.method == 'POST' else None,
                       initial={'year': timezone.localdate().year - 1})
    result = token = None
    if request.method == 'POST' and form.is_valid():
        year = form.cleaned_data['year']
        try:
            if request.POST.get('action') == 'execute':
                batch = execute(request.user, year, request.POST.get('token', ''))
                request._audit_target = batch.pk
                messages.success(request, f'{year}년 차기이월 전표를 저장했습니다. 손익계정 잔액을 이익잉여금으로 대체했습니다.')
                return redirect('year_end')
            result = preview(request.user, year)
            token = signing.dumps([request.user.pk, year, result['fingerprint']], salt='year-end')
        except forms.ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'ledger/year_end.html', {'form': form, 'result': result, 'token': token})
