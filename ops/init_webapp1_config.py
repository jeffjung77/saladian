"""Generate machine-local credentials; never overwrite an existing configuration."""
import json
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / '.env.webapp1'
if target.exists():
    raise SystemExit('Configuration already exists; nothing changed.')
config = {'host': '127.0.0.1', 'port': 5433, 'database': 'easybook_webapp1',
          'user': 'easybook_webapp1', 'password': secrets.token_urlsafe(36),
          'admin_user': 'webapp1_admin', 'admin_password': secrets.token_urlsafe(36),
          'secret_key': secrets.token_urlsafe(50)}
target.write_text(json.dumps(config, indent=2), encoding='utf-8')
print('Created .env.webapp1 with new local credentials. No passwords were printed.')
