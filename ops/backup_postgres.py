"""Back up webapp1 only; credentials are passed through the child environment."""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
config = json.loads((root / '.env.webapp1').read_text(encoding='utf-8'))
output = root / 'migration_backup' / ('postgresql-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.dump')
environment = dict(os.environ, PGPASSWORD=config['password'])
subprocess.run(['C:/Program Files/PostgreSQL/18/bin/pg_dump.exe',
                '--host=' + config['host'], '--port=' + str(config['port']),
                '--username=' + config['user'], '--dbname=' + config['database'],
                '--format=custom', '--file=' + str(output), '--no-password'], env=environment, check=True)
print('PostgreSQL backup saved: ' + str(output))
