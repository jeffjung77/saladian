import unicodedata
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .ledger_scope import company_name, ensure_membership
from .models import CompanyLedger, LedgerMembership, OpeningBalanceBatch, YearEndClosing
from .system_views import system_required


def name_key(name):
    return ' '.join(unicodedata.normalize('NFKC', name).split()).casefold()


class CompanyChoice(forms.ModelChoiceField):
    def label_from_instance(self, company):
        return f'{company.name or "업체명 미등록"} · 장부 {company.pk} ({company.anchor.username})'


class ApprovalForm(forms.Form):
    user = forms.ModelChoiceField(label='연결할 사용자', queryset=get_user_model().objects.order_by('username'))
    company = CompanyChoice(label='공유할 업체 장부', queryset=CompanyLedger.objects.filter(memberships__isnull=False).select_related('anchor').distinct().order_by('name', 'pk'))
    confirm = forms.BooleanField(label='해당 사용자의 기존 장부 자료도 선택 업체에 공유됨을 확인했습니다.')


@transaction.atomic
def approve(user, company, actor):
    # Serialize approvals and reject stale target/source selections.
    list(CompanyLedger.objects.select_for_update().order_by('pk'))
    membership = ensure_membership(user)
    if not company.memberships.exists():
        raise forms.ValidationError('사용 중인 업체 장부를 선택하세요.')
    if membership.company_id == company.pk:
        return
    if LedgerMembership.objects.filter(company=membership.company).count() != 1:
        raise forms.ValidationError('이미 공용 장부를 사용하는 회원은 다른 업체로 이동할 수 없습니다.')
    name = name_key(company_name(user))
    if not name or name != name_key(company.name):
        raise forms.ValidationError('사용등록 업체명과 대상 장부의 업체명이 같아야 승인할 수 있습니다.')
    ids = list(company.memberships.values_list('user_id', flat=True)) + [user.pk]
    if OpeningBalanceBatch.objects.filter(owner_id__in=ids).count() > 1:
        raise forms.ValidationError('양쪽 장부에 기초잔액이 있습니다. 중복 잔액을 먼저 확인하세요.')
    years = list(YearEndClosing.objects.filter(owner_id__in=ids).values_list('year', flat=True))
    if len(years) != len(set(years)):
        raise forms.ValidationError('같은 연도의 차기이월이 중복됩니다. 먼저 확인하세요.')
    previous = membership.company_id
    membership.company = company
    membership.save(update_fields=['company'])
    # Use the existing audit middleware for the actor and request details.
    return previous


@never_cache
@system_required
@require_http_methods(['GET', 'POST'])
def company_members(request):
    users = list(get_user_model().objects.select_related('subscription', 'business_profile').order_by('username'))
    for user in users:
        ensure_membership(user)
    form = ApprovalForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            approve(form.cleaned_data['user'], form.cleaned_data['company'], request.user)
        except forms.ValidationError as exc:
            form.add_error(None, exc)
        else:
            request._audit_target = str(form.cleaned_data['user'].pk)
            messages.success(request, '업체 장부 공유 연결을 승인했습니다.')
            return redirect('company_members')
    rows = LedgerMembership.objects.select_related('user', 'company', 'company__anchor').order_by('company_id', 'user__username')
    return render(request, 'ledger/company_members.html', {'form': form, 'memberships': rows})
