"""Local Windows simulation: verify a local commit and back up SQLite; never deploy to Lightsail."""
from contextlib import closing
from datetime import timedelta
import logging
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from .deployment import windows
from .management.commands.deployment_jobs import Command
from .models import DeploymentSchedule

logger = logging.getLogger(__name__)


def git(*args):
    return subprocess.check_output(['git', '-c', f'safe.directory={settings.BASE_DIR.as_posix()}', *args],
        cwd=settings.BASE_DIR, timeout=20, stderr=subprocess.DEVNULL, text=True).strip()


def simulate_once(now=None):
    if not (settings.DEPLOYMENT_SIMULATION_MODE and settings.DEPLOYMENT_SCHEDULER_ENABLED):
        return
    now = now or timezone.now()
    # A stopped development server must not leave a simulated run blocking forever.
    DeploymentSchedule.objects.filter(status='running', started_at__lt=now-timedelta(minutes=5)).update(
        status='failed', finished_at=now, result='개발 서버 중단으로 모의 실행을 종료했습니다. 새로 예약하세요.')
    for action in Command.tick(now)['actions']:
        job = DeploymentSchedule.objects.get(pk=action['id'])
        try:
            if action['action'] == 'prepare':
                if not re.fullmatch('[0-9a-f]{40}', job.commit) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._/-]{0,99}', job.branch) or '..' in job.branch:
                    raise ValueError('Invalid commit or branch')
                git('cat-file', '-e', job.commit + '^{commit}')
                git('merge-base', '--is-ancestor', job.commit, 'refs/heads/' + job.branch)
                if timezone.now() >= windows(job)[0]:
                    raise ValueError('Preparation missed the announcement deadline')
                DeploymentSchedule.objects.filter(pk=job.pk, status='queued').update(status='ready',
                    result='개발 모의 실행 예약: 로컬 Git 커밋 확인 완료. 실제 코드는 변경하지 않습니다.')
            else:
                if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
                    raise ValueError('Simulation requires SQLite')
                directory = Path(settings.BASE_DIR).parent / 'development_deployment_backups' / f'{job.pk}-{now:%Y%m%dT%H%M%S}'
                directory.mkdir(parents=True, exist_ok=True)
                backup = directory / 'db.sqlite3'
                with closing(sqlite3.connect(settings.DATABASES['default']['NAME'])) as source, closing(sqlite3.connect(backup)) as dest:
                    source.backup(dest)
                    if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('Backup integrity check failed')
                DeploymentSchedule.objects.filter(pk=job.pk, status='running').update(status='simulated', finished_at=now,
                    backup_path=str(directory), previous_commit=git('rev-parse', 'HEAD'),
                    result='개발 모의 실행 완료: 로그아웃·점검·DB 백업을 확인했습니다. 코드 교체 및 운영 배포는 수행하지 않았습니다.')
        except Exception:
            logger.exception('Development deployment simulation failed (job=%s)', job.pk)
            DeploymentSchedule.objects.filter(pk=job.pk, status__in=['queued', 'ready', 'running']).update(
                status='failed', finished_at=now, result='개발 모의 실행 실패: 로컬 커밋·브랜치 또는 백업 경로를 확인하세요.')


def start_watcher():
    def watch():
        stop = threading.Event()
        while not stop.wait(5):
            close_old_connections()
            try:
                simulate_once()
            except Exception:
                logger.exception('Development deployment scheduler check failed')
            finally:
                close_old_connections()
    threading.Thread(target=watch, name='bpms-development-scheduler', daemon=True).start()
