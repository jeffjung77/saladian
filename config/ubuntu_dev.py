"""HTTPS Ubuntu development settings. Secrets are provisioned on the server."""
import json
from .settings import *

_local = json.loads((BASE_DIR / '.env.ubuntu-dev.json').read_text(encoding='utf-8'))
SECRET_KEY = _local['secret_key']
DEBUG = False
ALLOWED_HOSTS = ['dev.easybook.bpms.co.kr', '52.79.77.85', '127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = ['https://dev.easybook.bpms.co.kr']
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': _local['database'], 'USER': _local['user'], 'PASSWORD': _local['password'],
    'HOST': '127.0.0.1', 'PORT': '5432', 'CONN_MAX_AGE': 0,
    'OPTIONS': {'connect_timeout': 5},
}}
STATIC_ROOT = BASE_DIR / 'staticfiles'
SESSION_COOKIE_NAME = 'easybook_dev_sessionid'
CSRF_COOKIE_NAME = 'easybook_dev_csrftoken'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
BOARD_EMAIL_ENABLED = False
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEPLOYMENT_SIMULATION_MODE = False
DEPLOYMENT_SCHEDULER_ENABLED = False
