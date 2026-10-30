#!/usr/bin/env python3
"""Installed outside the checkout; run only by bpms-deployment.timer under flock."""
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

APP = Path('/srv/bpms/app')
STATE = Path('/srv/bpms/deploy')
PYTHON = '/srv/bpms/venv/bin/python'
JOURNAL = STATE / 'inprogress.json'
BACKUPS = Path('/srv/bpms/backups')


def run(args, timeout=180, **kwargs):
    result = subprocess.run(args, cwd=APP, text=True, capture_output=True, timeout=timeout, **kwargs)
    if result.returncode:
        # Full output stays in restricted server logs, not in HTML.
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f'Command failed: {args[0]} {args[1] if len(args)>1 else ""}')
    return result.stdout.strip()


def manage(operation, *args):
    return json.loads(run([PYTHON, 'manage.py', 'deployment_jobs', operation, *map(str, args)], timeout=180))


def mark(job, status, message, backup='', previous=''):
    manage('mark', '--job', job['id'], '--status', status, '--result', message,
           '--backup', backup, '--previous', previous)


def service(action):
    run(['sudo', '-n', 'systemctl', action, 'bpms'], timeout=120)


def validate(job):
    commit, branch = job['commit'], job['branch']
    if not re.fullmatch('[0-9a-f]{40}', commit) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._/-]{0,99}', branch) or '..' in branch:
        raise RuntimeError('Invalid deployment target')
    if run(['git', 'status', '--porcelain', '--untracked-files=no']):
        raise RuntimeError('Tracked working tree must be clean')
    run(['git', 'fetch', 'origin', f'+refs/heads/{branch}:refs/remotes/origin/{branch}'])
    run(['git', 'merge-base', '--is-ancestor', commit, f'refs/remotes/origin/{branch}'])
    run(['git', 'diff', '--exit-code', 'HEAD', commit, '--', 'requirements.txt'])
    # Both the target and rollback release must contain scheduler support.
    for ref in ['HEAD', commit]:
        run(['git', 'cat-file', '-e', f'{ref}:ledger/management/commands/deployment_jobs.py'])
    info = manage('info')
    if not info['enabled'] or info['engine'] != 'django.db.backends.sqlite3':
        raise RuntimeError('Current scheduler requires enabled configuration and SQLite backup support')
    run(['sudo', '-n', 'nginx', '-t'])
    if shutil.disk_usage(APP).free < 512 * 1024 * 1024:
        raise RuntimeError('Insufficient backup space')


def public_check(blocked):
    for attempt in range(10):
        try:
            return _public_check(blocked)
        except Exception:
            if attempt == 9:
                raise
            time.sleep(2)


def _public_check(blocked):
    data = json.loads(run(['curl', '--fail', '--silent', '--show-error', '--max-time', '20',
                           'https://easybook.bpms.co.kr/deployment/status/'], timeout=25))
    if bool(data.get('blocked')) != blocked:
        raise RuntimeError('Maintenance state mismatch')
    code = run(['curl', '--silent', '--show-error', '--max-time', '20', '--output', '/dev/null', '--write-out', '%{http_code}',
                'https://easybook.bpms.co.kr/accounts/login/'], timeout=25)
    if code != ('503' if blocked else '200'):
        raise RuntimeError('Public login health failed')


def rollback(state):
    service('stop')
    run(['git', 'checkout', '--detach', state['previous']])
    backup = Path(state['backup'])
    shutil.copy2(backup / 'production.py', APP / 'config/production.py')
    if state.get('database_backed_up') and (backup / 'db.sqlite3').exists():
        shutil.copy2(backup / 'db.sqlite3', state['database'])
    run([PYTHON, 'manage.py', 'collectstatic', '--noinput'])
    service('start')
    manage('health')
    public_check(True)
    mark(state['job'], 'rolled_back', '배포 실패 후 기존 코드와 DB를 복구하고 서비스 검증을 완료했습니다.', state['backup'], state['previous'])
    public_check(False)
    JOURNAL.unlink(missing_ok=True)


def deploy(job):
    previous = run(['git', 'rev-parse', 'HEAD'])
    backup = BACKUPS / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-scheduled-' + str(job['id']))
    backup.mkdir(mode=0o700, parents=True)
    database = manage('info')['database']
    state = {'job': job, 'previous': previous, 'backup': str(backup), 'database': database}
    save_state(state)
    try:
        validate(job)  # Recheck branch ancestry/dependencies immediately before touching the service.
        shutil.copy2(APP / 'config/production.py', backup / 'production.py')
        run(['sudo', '-n', 'cp', '/etc/bpms.env', str(backup / 'bpms.env')])
        run(['sudo', '-n', 'chmod', '600', str(backup / 'bpms.env')])
        (backup / 'previous-commit.txt').write_text(previous)
        with (backup / 'source.tar').open('wb') as output:
            subprocess.run(['git', 'archive', 'HEAD'], cwd=APP, stdout=output, check=True, timeout=120)
        service('stop')
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(backup / 'db.sqlite3')) as dest:
            source.backup(dest)
        state['database_backed_up'] = True
        save_state(state)
        if (APP / 'private_uploads').exists():
            with tarfile.open(backup / 'private-uploads.tar.gz', 'w:gz') as archive:
                archive.add(APP / 'private_uploads', arcname='private_uploads')
        manage('snapshot', '--file', backup / 'data-fingerprints.json')
        run(['git', 'checkout', '--detach', job['commit']])
        run([PYTHON, 'manage.py', 'check'])
        run([PYTHON, 'manage.py', 'migrate', '--noinput'])
        run([PYTHON, 'manage.py', 'collectstatic', '--noinput'])
        manage('verify', '--file', backup / 'data-fingerprints.json')
        manage('health')
        service('start')
        run(['sudo', '-n', 'systemctl', 'is-active', '--quiet', 'bpms'])
        public_check(True)
        mark(job, 'succeeded', '고정 커밋 배포·기존 데이터 보존·주요 화면 검증을 완료했습니다.', str(backup), previous)
        public_check(False)
        JOURNAL.unlink(missing_ok=True)
    except Exception:
        print('Deployment failed; attempting rollback.', file=sys.stderr)
        try:
            # Production settings may not have been copied if preflight failed.
            if not (backup / 'production.py').exists():
                shutil.copy2(APP / 'config/production.py', backup / 'production.py')
            rollback(state)
        except Exception:
            mark(job, 'attention', '자동 복구를 확인하지 못해 점검을 유지합니다. 서버 관리자 확인이 필요합니다.', str(backup), previous)
            raise


def save_state(state):
    temporary = STATE / 'inprogress.tmp'
    temporary.write_text(json.dumps(state))
    temporary.chmod(0o600)
    os.replace(temporary, JOURNAL)


def main():
    STATE.mkdir(mode=0o700, exist_ok=True)
    if JOURNAL.exists():
        rollback(json.loads(JOURNAL.read_text()))
    for job in manage('tick')['actions']:
        if job['action'] == 'prepare':
            try:
                validate(job)
                mark(job, 'ready', '고정 커밋·의존성·디스크·서버 설정 사전 검사 완료')
            except Exception:
                mark(job, 'failed', '사전 검사 실패: 커밋·브랜치·의존성·디스크·서버 로그를 확인하고 새로 예약하세요.')
        else:
            deploy(job)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(RuntimeError('Scheduler interrupted')))
    main()
