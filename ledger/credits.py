from .pagination import page_size
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from .models import CreditAccount, CreditTransaction
from .system_views import system_required
from .widgets import MoneyInput

MAX_CREDITS = 999999999999
POST_REWARD = 100


@transaction.atomic
def reward_post(post):
    key = f'board:{post.pk}'
    account, _ = CreditAccount.objects.get_or_create(owner=post.author)
    account = CreditAccount.objects.select_for_update().get(pk=account.pk)
    if CreditTransaction.objects.filter(source_key=key).exists():
        return False
    if not CreditAccount.objects.filter(pk=account.pk, balance__lte=MAX_CREDITS-POST_REWARD).update(
        balance=F('balance') + POST_REWARD, revision=F('revision') + 1):
        raise forms.ValidationError('보유 가능한 크레딧 범위를 초과했습니다. 시스템관리자에게 문의하세요.')
    account.refresh_from_db()
    CreditTransaction.objects.create(account=account, amount=POST_REWARD, balance_after=account.balance,
        reason=f'게시글 #{post.pk} 신규 작성', actor=post.author, post=post, source_key=key)
    return True


class CreditForm(forms.Form):
    balance = forms.IntegerField(label='변경할 보유 크레딧', min_value=0, max_value=MAX_CREDITS, widget=MoneyInput())
    reason = forms.CharField(label='변경 사유', max_length=300, widget=forms.Textarea(attrs={'rows': 2}))
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


@transaction.atomic
def adjust_credit(owner, balance, reason, revision, actor):
    account, _ = CreditAccount.objects.get_or_create(owner=owner)
    account = CreditAccount.objects.select_for_update().get(pk=account.pk)
    if account.revision != revision:
        raise forms.ValidationError('다른 작업에서 크레딧이 변경되었습니다. 새로고침 후 다시 확인하세요.')
    delta = balance - account.balance
    if not delta:
        raise forms.ValidationError('현재 잔액과 같은 값입니다. 변경할 크레딧을 입력하세요.')
    if not CreditAccount.objects.filter(pk=account.pk, revision=revision).update(balance=balance, revision=F('revision') + 1):
        raise forms.ValidationError('크레딧이 변경되었습니다. 새로고침 후 다시 확인하세요.')
    return CreditTransaction.objects.create(account=account, amount=delta, balance_after=balance, reason=reason, actor=actor)


@never_cache
@system_required
@require_GET
def credit_list(request):
    query = request.GET.get('q', '').strip()[:100]
    users = get_user_model().objects.select_related('credit_account', 'subscription', 'business_profile').order_by('username', 'pk')
    if query:
        users = users.filter(Q(username__icontains=query) | Q(subscription__company_name__icontains=query) | Q(business_profile__company_name__icontains=query))
    page = Paginator(users, page_size(request)).get_page(request.GET.get('page'))
    return render(request, 'ledger/credit_list.html', {'page': page, 'q': query})


@never_cache
@system_required
@require_http_methods(['GET', 'POST'])
def credit_edit(request, pk):
    member = get_object_or_404(get_user_model(), pk=pk)
    account = CreditAccount.objects.filter(owner=member).first()
    form = CreditForm(request.POST if request.method == 'POST' else None,
        initial={'balance': account.balance if account else 0, 'revision': account.revision if account else 0})
    request._audit_owner = member
    if request.method == 'POST' and form.is_valid():
        try:
            entry = adjust_credit(member, actor=request.user, **form.cleaned_data)
        except forms.ValidationError as exc:
            form.add_error(None, exc)
        else:
            request._audit_target = entry.pk
            messages.success(request, f'{member.username}님의 보유 크레딧을 변경했습니다.')
            return redirect('credit_edit', pk=member.pk)
    history = CreditTransaction.objects.filter(account__owner=member).select_related('actor')
    page = Paginator(history, 20).get_page(request.GET.get('page'))
    return render(request, 'ledger/credit_edit.html', {'member': member, 'account': account, 'form': form, 'page': page})
