from .pagination import page_size
from functools import wraps
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from .models import Notice
from .receipt_quota import LIMIT
from .models import VoucherQuota, VoucherCreationUsage, Voucher
from .voucher_quota import limits_for


def system_required(view):
    @wraps(view)
    def checked(request, *args, **kwargs):
        if not request.user.is_superuser:
            return render(request, 'ledger/permission_denied.html', status=403)
        return view(request, *args, **kwargs)
    return login_required(checked)


@never_cache
@system_required
@require_GET
def user_voucher_counts(request):
    query = request.GET.get('q', '').strip()[:100]
    users = get_user_model().objects.select_related('subscription', 'business_profile', 'receipt_creation_usage').annotate(
        voucher_count=Count('vouchers', filter=Q(vouchers__opening_batch__isnull=True, vouchers__closing_batch__isnull=True), distinct=True),
        sales_count=Count('vouchers', filter=Q(vouchers__entry_type='sales', vouchers__opening_batch__isnull=True, vouchers__closing_batch__isnull=True), distinct=True),
        expense_count=Count('vouchers', filter=Q(vouchers__entry_type='expense', vouchers__opening_batch__isnull=True, vouchers__closing_batch__isnull=True), distinct=True),
        other_count=Count('vouchers', filter=Q(vouchers__entry_type='other', vouchers__opening_batch__isnull=True, vouchers__closing_batch__isnull=True), distinct=True),
        photo_completed=Count('receipt_photos', filter=Q(receipt_photos__status='completed'), distinct=True)).order_by('username')
    if query:
        users = users.filter(Q(username__icontains=query) | Q(subscription__company_name__icontains=query) | Q(business_profile__company_name__icontains=query))
    page = Paginator(users, page_size(request)).get_page(request.GET.get('page'))
    for user in page:
        usage = getattr(user, 'receipt_creation_usage', None)
        user.photo_used = usage.generated_count if usage else user.photo_completed
        user.limits = limits_for(user)
        user.photo_remaining = max(0, user.limits['photo']-user.photo_used) if user.limits['photo'] is not None else None
    return render(request, 'ledger/user_voucher_counts.html', {'page': page, 'q': query, 'photo_limit': LIMIT})


class VoucherQuotaForm(forms.ModelForm):
    class Meta:
        model = VoucherQuota
        fields = ['sales_limit', 'expense_limit', 'other_limit', 'photo_limit']


@never_cache
@system_required
@require_http_methods(['GET', 'POST'])
def voucher_quota_edit(request, pk):
    member = get_object_or_404(get_user_model(), pk=pk)
    policy = VoucherQuota.objects.filter(owner=member).first()
    initial = {key + '_limit': value for key, value in limits_for(member).items()}
    form = VoucherQuotaForm(request.POST if request.method == 'POST' else None, instance=policy, initial=initial)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        saved.owner = member
        saved.save()
        request._audit_target = member.pk
        messages.success(request, '전표 생성 한도를 저장했습니다.')
        return redirect('user_voucher_counts')
    counters = dict(VoucherCreationUsage.objects.filter(owner=member).values_list('entry_type', 'generated_count'))
    usage = [{'label': label, 'count': counters.get(key, Voucher.objects.filter(owner=member, entry_type=key, opening_batch__isnull=True, closing_batch__isnull=True).count())}
             for key, label in Voucher.EntryType.choices]
    return render(request, 'ledger/voucher_quota_form.html', {'form': form, 'member': member, 'usage': usage})


class NoticeForm(forms.ModelForm):
    def clean(self):
        data = super().clean()
        if data.get('start_date') and data.get('end_date') and data['end_date'] < data['start_date']:
            self.add_error('end_date', '게시 종료일은 시작일과 같거나 이후여야 합니다.')
        return data

    class Meta:
        model = Notice
        fields = ['title', 'start_date', 'end_date', 'body', 'published']
        widgets = {'body': forms.Textarea(attrs={'rows': 10}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}


@never_cache
@system_required
@require_GET
def notice_management(request):
    page = Paginator(Notice.objects.select_related('author'), page_size(request)).get_page(request.GET.get('page'))
    return render(request, 'ledger/notice_management.html', {'page': page})


@never_cache
@system_required
@require_http_methods(['GET', 'POST'])
def notice_edit(request, pk=None):
    notice = get_object_or_404(Notice, pk=pk) if pk else None
    form = NoticeForm(request.POST if request.method == 'POST' else None, instance=notice)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        if not notice:
            saved.author = request.user
        saved.save()
        request._audit_target = saved.pk
        messages.success(request, '공지사항을 저장했습니다.')
        return redirect('notice_management')
    return render(request, 'ledger/notice_form.html', {'form': form, 'notice': notice})


@never_cache
@system_required
@require_http_methods(['GET', 'POST'])
def notice_delete(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        notice.delete()
        messages.success(request, '공지사항을 삭제했습니다.')
        return redirect('notice_management')
    return render(request, 'ledger/notice_delete.html', {'notice': notice})


@never_cache
@login_required
@require_GET
def notice_detail(request, pk):
    source = Notice.objects.all() if request.user.is_superuser else Notice.objects.active()
    return render(request, 'ledger/notice_detail.html', {'notice': get_object_or_404(source, pk=pk)})
