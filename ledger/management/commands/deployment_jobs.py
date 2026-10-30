import hashlib
import json
from pathlib import Path
from datetime import timedelta
from django.apps import apps
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from ledger.models import DeploymentSchedule
from ledger.deployment import windows


class Command(BaseCommand):
    help = 'Trusted server scheduler interface (not exposed as HTTP).'
    # Minute polling must not load the full receipt/OCR URL stack on a small server.
    # Release validation explicitly runs manage.py check and the health operation.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('operation', choices=['tick', 'mark', 'info', 'snapshot', 'verify', 'health', 'cancel'])
        parser.add_argument('--job', type=int)
        parser.add_argument('--status')
        parser.add_argument('--result', default='')
        parser.add_argument('--previous', default='')
        parser.add_argument('--backup', default='')
        parser.add_argument('--file')

    def handle(self, operation, **options):
        result = {}
        if operation == 'info':
            result = {'enabled': settings.DEPLOYMENT_SCHEDULER_ENABLED,
                'engine': settings.DATABASES['default']['ENGINE'], 'database': str(settings.DATABASES['default']['NAME'])}
        elif operation == 'tick':
            result = self.tick()
        elif operation in ['mark', 'cancel']:
            status = 'cancelled' if operation == 'cancel' else options['status']
            if status not in DeploymentSchedule.Status.values:
                raise CommandError('Invalid status')
            query = DeploymentSchedule.objects.filter(pk=options['job'])
            if operation == 'cancel':
                query = query.exclude(status='running')
            elif status == 'ready':
                query = query.filter(status='queued')
            values = {'status': status, 'result': options['result'][:3000]}
            if status == 'ready':
                pending = query.first()
                if pending and timezone.now() >= windows(pending)[0]:
                    status = 'failed'
                    values = {'status': status, 'result': '사전 검사가 안내 시작시간을 지나 완료되어 예약을 취소했습니다.'}
            if options['previous']:
                values['previous_commit'] = options['previous']
            if options['backup']:
                values['backup_path'] = options['backup']
            if status not in ['ready', 'running']:
                values['finished_at'] = timezone.now()
            result = {'updated': query.update(**values)}
        elif operation in ['snapshot', 'verify']:
            path = Path(options['file'])
            if operation == 'snapshot':
                state = {}
                for model in apps.get_models():
                    if model._meta.app_label not in ['auth', 'ledger'] or model.__name__ in ['AuditLog', 'DeploymentSchedule']:
                        continue
                    fields = [f.attname for f in model._meta.concrete_fields]
                    values = list(model.objects.order_by('pk').values(*fields))
                    state[model._meta.label] = {'fields': fields, 'count': len(values), 'digest': self.digest(values)}
                path.write_text(json.dumps(state), encoding='utf-8')
                path.chmod(0o600)
                result = {'models': len(state)}
            else:
                for label, expected in json.loads(path.read_text(encoding='utf-8')).items():
                    model = apps.get_model(label)
                    if self.digest(list(model.objects.order_by('pk').values(*expected['fields']))) != expected['digest']:
                        raise CommandError(f'Existing data changed: {label}')
                result = {'preserved': True}
        elif operation == 'health':
            from django.test import Client, override_settings
            from django.contrib.auth import get_user_model
            with override_settings(DEPLOYMENT_SCHEDULER_ENABLED=False):
                client = Client(HTTP_HOST='easybook.bpms.co.kr')
                assert client.get('/accounts/login/', secure=True).status_code == 200
                admin = get_user_model().objects.filter(is_active=True, is_superuser=True).first()
                if not admin:
                    raise CommandError('Active system administrator required')
                client.force_login(admin)
                for path in ['/', '/vouchers/', '/vouchers/sales/new/', '/vouchers/expenses/new/', '/vouchers/new/',
                             '/vouchers/summary/', '/reports/income-statement/', '/reports/balance-sheet/',
                             '/reports/trial-balance/', '/partners/', '/partners/import/', '/management/expenses/',
                             '/board/', '/system/deployments/']:
                    response = client.get(path, secure=True)
                    if response.status_code != 200:
                        raise CommandError(f'Health failure: {path} {response.status_code}')
                client.logout()
            result = {'healthy': True}
        self.stdout.write(json.dumps(result))

    @staticmethod
    def digest(values):
        return hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def tick(now=None):
        if not settings.DEPLOYMENT_SCHEDULER_ENABLED:
            return {'actions': []}
        now = now or timezone.now()
        actions = []
        with transaction.atomic():
            for job in DeploymentSchedule.objects.select_for_update().filter(status__in=['queued', 'ready']).order_by('scheduled_date'):
                warn, cutoff, deploy = windows(job)
                if now > deploy + timedelta(minutes=5):
                    job.status = 'failed'
                    job.result = '예약시간을 놓쳐 자동 실행하지 않았습니다. 새 날짜로 예약해 주세요.'
                    job.finished_at = now
                    job.save()
                    continue
                if now < warn - timedelta(days=1):
                    continue
                if job.status == 'queued':
                    # Full preflight must finish before the announcement begins.
                    if now >= warn:
                        job.status = 'failed'
                        job.finished_at = now
                        job.result = '사전 검사를 안내 시작시간 전에 완료하지 못해 배포를 취소했습니다.'
                        job.save()
                    else:
                        actions.append({'action': 'prepare', 'id': job.pk, 'commit': job.commit, 'branch': job.branch})
                    continue
                if now >= cutoff and not job.sessions_cleared_at:
                    Session.objects.all().delete()
                    job.sessions_cleared_at = now
                    job.save(update_fields=['sessions_cleared_at'])
                if now >= deploy:
                    job.status = 'running'
                    job.started_at = now
                    job.save(update_fields=['status', 'started_at'])
                    actions.append({'action': 'deploy', 'id': job.pk, 'commit': job.commit, 'branch': job.branch})
        return {'actions': actions}
