import re
from datetime import timedelta
from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .deployment import KST, windows
from .models import DeploymentSchedule
from .system_views import system_required


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = DeploymentSchedule
        fields = ['scheduled_date', 'branch', 'commit', 'message']
        widgets = {'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
                   'message': forms.Textarea(attrs={'rows': 2})}

    def clean_commit(self):
        value = self.cleaned_data['commit'].lower().strip()
        if not re.fullmatch('[0-9a-f]{40}', value):
            raise forms.ValidationError('생략하지 않은 40자리 Git 커밋 ID를 입력하세요.')
        return value

    def clean_branch(self):
        value = self.cleaned_data['branch'].strip()
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._/-]{0,99}', value) or '..' in value or value.endswith('/'):
            raise forms.ValidationError('올바른 Git 브랜치명을 입력하세요.')
        return value

    def clean_scheduled_date(self):
        value = self.cleaned_data['scheduled_date']
        job = DeploymentSchedule(scheduled_date=value)
        if windows(job)[0] <= timezone.now() + timedelta(minutes=2):
            raise forms.ValidationError('사전 안내를 위해 배포 전날 23:29 이전에 예약하세요. 다음 배포 날짜를 선택해 주세요.')
        return value


@system_required
@require_http_methods(['GET', 'POST'])
def deployment_management(request):
    form = ScheduleForm(request.POST or None, initial={'scheduled_date': (timezone.now().astimezone(KST)+timedelta(days=1)).date(), 'branch': '1-6'})
    if request.method == 'POST':
        if request.POST.get('action') == 'cancel':
            try:
                job_id = int(request.POST.get('job', ''))
            except (ValueError, TypeError):
                job_id = None
            job = DeploymentSchedule.objects.filter(pk=job_id, status__in=['queued', 'ready']).first()
            if job and timezone.now() < windows(job)[1]:
                updated = DeploymentSchedule.objects.filter(pk=job.pk, status__in=['queued', 'ready']).update(status='cancelled', finished_at=timezone.now())
                if updated:
                    messages.success(request, '배포 예약을 취소했습니다.')
            else:
                messages.error(request, '이미 배포 점검이 시작되었거나 취소할 수 없는 예약입니다.')
            return redirect('deployment_management')
        if form.is_valid():
            try:
                job = form.save(commit=False)
                job.created_by = request.user
                job.save()
            except IntegrityError:
                form.add_error(None, '같은 날짜에 활성 배포 예약이 이미 있습니다.')
            else:
                messages.success(request, '예약을 등록했습니다. 서버 사전 검사 후 예약이 확정됩니다.')
                return redirect('deployment_management')
    per_page = 5 if request.GET.get('per_page') == '5' else 10
    page = Paginator(DeploymentSchedule.objects.all(), per_page).get_page(request.GET.get('page'))
    return render(request, 'ledger/deployment_management.html', {'form': form, 'page': page, 'per_page': per_page,
        'scheduler_enabled': settings.DEPLOYMENT_SCHEDULER_ENABLED,
        'simulation_mode': getattr(settings, 'DEPLOYMENT_SIMULATION_MODE', False)})
