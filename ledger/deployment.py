"""Korea-time deployment windows. No shell operations run in web requests."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_not_required
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.views.decorators.http import require_GET
from .models import DeploymentSchedule

KST = ZoneInfo('Asia/Seoul')
ACTIVE = ['queued', 'ready', 'running', 'attention']


def windows(job):
    deploy = datetime.combine(job.scheduled_date, time(0, 1), tzinfo=KST)
    return deploy - timedelta(minutes=30), deploy - timedelta(minutes=1), deploy


def current_job(now=None):
    if not settings.DEPLOYMENT_SCHEDULER_ENABLED:
        return None
    now = now or timezone.now()
    # Running/uncertain jobs remain closed even if work crosses midnight.
    job = DeploymentSchedule.objects.filter(status__in=['running', 'attention']).order_by('scheduled_date').first()
    if job:
        return job
    return DeploymentSchedule.objects.filter(status__in=['queued', 'ready'],
        scheduled_date__lte=(now.astimezone(KST) + timedelta(days=1)).date()).order_by('scheduled_date').first()


def public_state(now=None):
    now = now or timezone.now()
    job = current_job(now)
    if not job:
        return {'active': False, 'blocked': False}
    warn, cutoff, deploy = windows(job)
    blocked = now >= cutoff
    return {'active': now >= warn, 'blocked': blocked, 'id': job.pk,
        'at': deploy.isoformat(), 'cutoff': cutoff.isoformat(),
        'label': deploy.strftime('%Y년 %m월 %d일 00:01 (한국시간)'),
        'simulation': getattr(settings, 'DEPLOYMENT_SIMULATION_MODE', False),
        'message': job.message or '서비스 업데이트가 예정되어 있습니다. 입력 중인 자료를 미리 저장해 주세요.'}


class DeploymentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ['/deployment/status/', '/maintenance/'] or request.path.startswith('/static/'):
            return self.get_response(request)
        state = public_state()
        if state['blocked']:
            if request.user.is_authenticated:
                logout(request)
            response = render(request, 'ledger/deployment_maintenance.html', {'deployment': state}, status=503)
            response['Retry-After'] = '60'
            response['Cache-Control'] = 'no-store'
            return response
        return self.get_response(request)


@login_not_required
@never_cache
@require_GET
def status(request):
    state = public_state()
    if state['blocked'] and request.user.is_authenticated:
        logout(request)
    return JsonResponse(state)


@login_not_required
@never_cache
@require_GET
def maintenance(request):
    return render(request, 'ledger/deployment_maintenance.html', {'deployment': public_state()})
