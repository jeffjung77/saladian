"""Exercise the actual frozen Windows app using a fresh disposable data directory."""
from io import BytesIO
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
import requests
from PIL import Image

PROJECT = Path(__file__).resolve().parent.parent


def main():
    installer = PROJECT / 'dist/release/EasybookSetup.exe'
    assert subprocess.run([str(installer), '--ui-check'], timeout=30).returncode == 0, 'Installer GUI failed'
    with tempfile.TemporaryDirectory(prefix='personal-smoke-', dir=PROJECT / 'build') as temporary:
        root = Path(temporary)
        target = root / 'installed'
        result = subprocess.run([str(installer), '--silent', '--no-shortcuts', '--install-dir', str(target)], timeout=120)
        assert result.returncode == 0, f'Installer returned {result.returncode}'
        assert (target / 'Easybook.exe').is_file()
        env = os.environ.copy()
        for key in ('GOOGLE_APPLICATION_CREDENTIALS', 'DJANGO_SETTINGS_MODULE', 'PYTHONPATH', 'PYTHONHOME', 'DJANGO_SECRET_KEY'):
            env.pop(key, None)
        data = root / 'data'
        env['BPMS_DESKTOP_DATA'] = str(data)
        assert subprocess.run([str(target / 'Easybook.exe'), '--ui-check'], env=env, cwd=root, timeout=90).returncode == 0, 'Launcher GUI failed'
        process = subprocess.Popen([str(target / 'Easybook.exe'), '--serve-only'], env=env, cwd=root)
        try:
            deadline = time.monotonic() + 90
            while not (data / 'runtime.json').exists():
                if process.poll() is not None:
                    log = (data / 'easybook.log').read_text(encoding='utf-8') if (data / 'easybook.log').exists() else ''
                    raise AssertionError(f'Frozen startup failed {process.returncode}: {log}')
                if time.monotonic() > deadline:
                    raise AssertionError('Frozen startup timeout')
                time.sleep(0.2)
            info = json.loads((data / 'runtime.json').read_text(encoding='utf-8'))
            url = info['url']
            session = requests.Session()
            session.trust_env = False
            def get(path):
                return session.get(url + path, timeout=15)
            def post(path, values=None, **kwargs):
                headers = {'X-CSRFToken': session.cookies.get('bpms_personal_csrf', ''), 'Referer': url}
                return session.post(url + path, data=values or {}, headers=headers, timeout=20, **kwargs)

            response = get('desktop/setup/')
            assert response.status_code == 200
            with closing(sqlite3.connect(data / 'easybook.sqlite3')) as db:
                assert db.execute('select count(*) from auth_user').fetchone()[0] == 0
                assert db.execute('select count(*) from ledger_voucher').fetchone()[0] == 0
                assert db.execute('select count(*) from ledger_account').fetchone()[0] > 100
            response = post('desktop/setup/', dict(username='personal_smoke', company_name='Local Test',
                password1='Local-Only!483029', password2='Local-Only!483029'))
            assert response.status_code == 200 and response.url.endswith('/vouchers/'), f'Setup: {response.status_code} {response.text[:200]}'
            assert 'board/' not in response.text and 'system/' not in response.text
            response = get('static/branding/bpms-logo.png')
            assert response.status_code == 200 and response.content.startswith(b'\x89PNG')
            assert get('static/ledger/money.js').status_code == 200
            for path in ('accounts/signup/', 'board/', 'system/members/', 'admin/'):
                assert get(path).status_code == 404, path
            for path, code, kind in [('vouchers/sales/new/', '5001', 'income'), ('vouchers/expenses/new/', '6505', 'expense')]:
                get(path)
                response = post(path, dict(date='2026-10-26', kind=kind, account_master=code, settlement_account='1101', amount=1000, memo='Local'))
                assert response.url.endswith('/vouchers/summary/'), f'Voucher save failed {path}'
            for path in ('reports/income-statement/', 'reports/balance-sheet/', 'vouchers/summary/', 'accounts/ledger/', 'partners/ledger/'):
                assert get(path).status_code == 200, path
            response = get('reports/income-statement/?start=2026-01-01&end=2026-12-31&export=xlsx')
            assert response.status_code == 200 and zipfile.is_zipfile(BytesIO(response.content))
            get('receipts/')
            image = BytesIO()
            Image.new('RGB', (10,10), 'white').save(image, 'PNG')
            response = post('receipts/', files={'photo': ('local-test.png', image.getvalue(), 'image/png')})
            assert response.status_code == 200 and response.url.endswith('/receipts/history/')
            with closing(sqlite3.connect(data / 'easybook.sqlite3')) as db:
                assert db.execute('select count(*) from ledger_voucher').fetchone()[0] == 2
                pk, stored = db.execute('select id,photo from ledger_receiptphoto').fetchone()
                assert (data / 'receipts' / stored).is_file()
                assert db.execute('select count(*) from ledger_visionusage').fetchone()[0] == 0
            assert get(f'receipts/{pk}/photo/').status_code == 200
            # A missing personal Google key is handled without an outbound OCR request.
            assert post(f'receipts/{pk}/analyze/').status_code == 200
            with closing(sqlite3.connect(data / 'easybook.sqlite3')) as db:
                assert db.execute('select api_attempted from ledger_visionusage').fetchone()[0] == 0
            print('PASS: actual installer extraction, clean database, frozen startup, static files, setup/login, sales/expense, all reports, XLSX, photo storage, cloud routes denied, missing OCR credentials handled')
        finally:
            process.terminate()
            process.wait(timeout=15)
        # Restart the actual frozen app against the same data to verify persistence.
        (data / 'runtime.json').unlink(missing_ok=True)
        process = subprocess.Popen([str(target / 'Easybook.exe'), '--serve-only'], env=env, cwd=root)
        try:
            deadline = time.monotonic() + 30
            while not (data / 'runtime.json').exists():
                assert process.poll() is None, 'Restart failed'
                assert time.monotonic() < deadline, 'Restart timeout'
                time.sleep(0.2)
            with closing(sqlite3.connect(data / 'easybook.sqlite3')) as db:
                assert db.execute('select count(*) from ledger_voucher').fetchone()[0] == 2
            print('PASS: restart preserves user data')
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == '__main__':
    main()
