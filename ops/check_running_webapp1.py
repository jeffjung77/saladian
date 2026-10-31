"""Read-only HTTP smoke checks using a short-lived isolated test session."""
import json
import os
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.webapp1'
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.db import connection
from django.urls import reverse
from ledger.ledger_scope import member_ids
from ledger.models import Voucher

user = get_user_model().objects.get(username='sysadmin', is_superuser=True)
session = SessionStore()
session['_auth_user_id'] = str(user.pk)
session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
session['_auth_user_hash'] = user.get_session_auth_hash()
session['last_activity_at'] = time.time()
session.save()
routes = ['voucher_entry', 'business_overview', 'dashboard', 'balance_sheet', 'income_statement',
          'trial_balance', 'account_ledger', 'partner_ledger', 'expense_status', 'counterparties',
          'receipt_history', 'board_list', 'company_members', 'online_users']
result = {}
try:
    for route in routes:
        request = Request('http://127.0.0.1:8001' + reverse(route),
                          headers={'Cookie': 'webapp1_sessionid=' + session.session_key})
        with urlopen(request, timeout=15) as response:
            assert response.status == 200 and '/accounts/login/' not in response.url, route
            response.read()
            result[route] = response.status
finally:
    session.delete()
with connection.cursor() as cursor:
    cursor.execute('SELECT current_database(), inet_server_port(), version()')
    database, port, version = cursor.fetchone()
assert port == 5433 and connection.vendor == 'postgresql'
shared = {u.username: Voucher.objects.filter(owner_id__in=member_ids(u)).count()
          for u in get_user_model().objects.filter(username__in=['jeffjung', 'sysadmin'])}
report = {'database': database, 'database_port': port, 'version': version.split(',')[0],
          'http_checks': result, 'shared_voucher_counts': shared}
(root / 'migration_backup' / 'http-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
