"""Initialize only webapp1's isolated PostgreSQL cluster; never change port 5432."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / 'postgres_webapp1'
BIN = Path('C:/Program Files/PostgreSQL/18/bin')


def initialize():
    config = json.loads((ROOT / '.env.webapp1').read_text(encoding='utf-8'))
    if DATA.exists():
        raise SystemExit('Target PostgreSQL data directory already exists; refusing to overwrite.')
    password_file = ROOT / '.postgres-init-password'
    password_file.write_text(config['admin_password'] + '\n', encoding='utf-8')
    try:
        subprocess.run([str(BIN / 'initdb.exe'), '-D', str(DATA), '-U', config['admin_user'],
                        '--pwfile=' + str(password_file), '--auth=scram-sha-256',
                        '--encoding=UTF8', '--locale=C'], check=True)
    finally:
        password_file.unlink(missing_ok=True)
    with (DATA / 'postgresql.conf').open('a', encoding='utf-8') as stream:
        stream.write("\n# Isolated webapp1 development cluster\nlisten_addresses = '127.0.0.1'\n"
                     "port = 5433\nshared_buffers = '64MB'\nmax_connections = 40\n"
                     "timezone = 'Asia/Seoul'\npassword_encryption = 'scram-sha-256'\n")
    print('Initialized isolated PostgreSQL cluster at ' + str(DATA))


if __name__ == '__main__':
    initialize()
