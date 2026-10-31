import json
from pathlib import Path
import psycopg
from psycopg import sql

root = Path(__file__).resolve().parents[1]
config = json.loads((root / '.env.webapp1').read_text(encoding='utf-8'))
with psycopg.connect(host=config['host'], port=config['port'], dbname='postgres',
                     user=config['admin_user'], password=config['admin_password'],
                     autocommit=True) as connection:
    if connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (config['database'],)).fetchone():
        raise SystemExit('Database already exists; refusing to overwrite.')
    # CREATEDB is for Django test databases in this isolated development cluster only.
    if not connection.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (config['user'],)).fetchone():
        connection.execute(sql.SQL('CREATE ROLE {} LOGIN CREATEDB PASSWORD {}').format(
            sql.Identifier(config['user']), sql.Literal(config['password'])))
    connection.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING {}').format(
        sql.Identifier(config['database']), sql.Identifier(config['user']), sql.Literal('UTF8')))
print('Created isolated application role and database. Passwords are kept in .env.webapp1.')
