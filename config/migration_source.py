"""Read only migration input, copied using SQLite's online backup API."""
from .webapp1 import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                         'NAME': f'file:{BASE_DIR.as_posix()}/migration_backup/source.sqlite3?mode=ro',
                         'OPTIONS': {'uri': True}}}
