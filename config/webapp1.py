"""Isolated PC development settings: PostgreSQL, port 8001, own cookies/media."""
import json
from .settings import *

_local = json.loads((BASE_DIR / '.env.webapp1').read_text(encoding='utf-8'))
SECRET_KEY = _local['secret_key']
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': _local['database'], 'USER': _local['user'], 'PASSWORD': _local['password'],
    'HOST': _local['host'], 'PORT': _local['port'],
    'CONN_MAX_AGE': 0,
    'OPTIONS': {'connect_timeout': 5},
    'TEST': {'NAME': 'test_easybook_webapp1'},
}}
SESSION_COOKIE_NAME = 'webapp1_sessionid'
CSRF_COOKIE_NAME = 'webapp1_csrftoken'
BOARD_EMAIL_ENABLED = False
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEPLOYMENT_SIMULATION_MODE = False
DEPLOYMENT_SCHEDULER_ENABLED = False
SERIALIZATION_MODULES = {'precise_json': 'config.precise_json'}
