from django import forms
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import AuditLog
from .audit import ACTIONS, RESULTS


class AuditFilter(forms.Form):
    company = forms.CharField(label='업체명', required=False, max_length=150)
    username = forms.CharField(label='사용자 아이디', required=False, max_length=150)
    start = forms.DateField(label='시작일', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='종료일', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    action = forms.ChoiceField(label='작업', required=False, choices=[('', '전체')] + ACTIONS)
    result = forms.ChoiceField(label='결과', required=False, choices=[('', '전체')] + RESULTS)

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise forms.ValidationError('종료일은 시작일 이후여야 합니다.')
        return data


@never_cache
@require_GET
def audit_logs(request):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    form = AuditFilter(request.GET)
    logs = AuditLog.objects.select_related('company_user')
    if form.is_valid():
        data = form.cleaned_data
        if data.get('company'):
            logs = logs.filter(Q(company_name__icontains=data['company']) | Q(company_user__subscription__company_name__icontains=data['company']))
        if data.get('username'):
            logs = logs.filter(actor_name__icontains=data['username'])
        if data.get('start'):
            logs = logs.filter(occurred_at__date__gte=data['start'])
        if data.get('end'):
            logs = logs.filter(occurred_at__date__lte=data['end'])
        for field in ('action', 'result'):
            if data.get(field):
                logs = logs.filter(**{field: data[field]})
    else:
        logs = logs.none()
    query = request.GET.copy()
    query.pop('page', None)
    page = Paginator(logs, 50).get_page(request.GET.get('page'))
    return render(request, 'ledger/audit_logs.html', {'form': form, 'page': page, 'query': query.urlencode()})
