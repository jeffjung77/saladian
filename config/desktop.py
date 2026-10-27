"""Settings exclusively for the packaged, loopback-only personal edition."""
from .settings import *
import secrets

DESKTOP_MODE = True
DEBUG = False
DATA_DIR = Path(os.environ.get('BPMS_DESKTOP_DATA', Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BPMS' / 'EasybookData'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
key_file = DATA_DIR / 'secret.key'
if not key_file.exists():
    try:
        with key_file.open('x', encoding='ascii') as output:
            output.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
SECRET_KEY = key_file.read_text(encoding='ascii')
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
ROOT_URLCONF = 'desktop.urls'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': DATA_DIR / 'easybook.sqlite3', 'OPTIONS': {'timeout': 30}}}
MEDIA_ROOT = DATA_DIR / 'receipts'
STATIC_ROOT = BASE_DIR / 'desktop_static'
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
MIDDLEWARE.insert(MIDDLEWARE.index('ledger.audit.AuditMiddleware'), 'desktop.middleware.PersonalEditionMiddleware')
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'desktop' / 'templates']
TEMPLATES[0]['OPTIONS']['context_processors'].append('desktop.views.desktop_context')
SESSION_COOKIE_NAME = 'bpms_personal_session'
CSRF_COOKIE_NAME = 'bpms_personal_csrf'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_SSL_REDIRECT = False
DESKTOP_LAUNCH_TOKEN = os.environ.get('BPMS_LAUNCH_TOKEN', '')
DESKTOP_GOOGLE_CREDENTIALS = DATA_DIR / 'google-vision.json'

