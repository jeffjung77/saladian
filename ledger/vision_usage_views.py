from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Max
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .forms import IncomeStatementForm
from .models import VisionUsage


class UsageFilter(IncomeStatementForm):
    company = forms.ModelChoiceField(label='업체 회원', queryset=get_user_model().objects.order_by('username'), required=False, empty_label='전체 업체')
    q = forms.CharField(label='업체명·아이디 검색', required=False, max_length=100)


@never_cache
@login_required
@require_GET
def vision_usage(request):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    today = timezone.localdate()
    params = request.GET.copy()
    if not params.get('start') and 'start' not in params:
        params['start'] = today.replace(day=1).isoformat()
    if not params.get('end') and 'end' not in params:
        params['end'] = today.isoformat()
    form = UsageFilter(params)
    logs = VisionUsage.objects.none()
    companies = get_user_model().objects.none()
    if form.is_valid():
        logs = VisionUsage.objects.filter(requested_at__date__gte=form.cleaned_data['start'], requested_at__date__lte=form.cleaned_data['end'])
        companies = get_user_model().objects.select_related('subscription', 'business_profile').order_by('username')
        if form.cleaned_data['company']:
            companies = companies.filter(pk=form.cleaned_data['company'].pk)
        if form.cleaned_data['q']:
            q = form.cleaned_data['q']
            companies = companies.filter(Q(username__icontains=q) | Q(subscription__company_name__icontains=q) | Q(business_profile__company_name__icontains=q))
        logs = logs.filter(owner__in=companies)
    totals = logs.aggregate(requests=Count('pk'), success=Count('pk', filter=Q(result='success')),
        failed=Count('pk', filter=Q(result='failed')), pending=Count('pk', filter=Q(result='pending')),
        retries=Count('pk', filter=Q(is_retry=True)), api_attempts=Count('pk', filter=Q(api_attempted=True)))
    scope = Q(vision_usage__pk__in=logs.values('pk'))
    companies = companies.annotate(requests=Count('vision_usage', filter=scope),
        success=Count('vision_usage', filter=scope & Q(vision_usage__result='success')),
        failed=Count('vision_usage', filter=scope & Q(vision_usage__result='failed')),
        pending=Count('vision_usage', filter=scope & Q(vision_usage__result='pending')),
        retries=Count('vision_usage', filter=scope & Q(vision_usage__is_retry=True)),
        api_attempts=Count('vision_usage', filter=scope & Q(vision_usage__api_attempted=True)),
        latest_success_at=Max('vision_usage__finished_at', filter=scope & Q(vision_usage__result='success')))
    query = params.copy()
    query.pop('page', None)
    return render(request, 'ledger/vision_usage.html', {'form': form, 'totals': totals,
        'page': Paginator(companies, 25).get_page(request.GET.get('page')), 'query': query.urlencode()})
