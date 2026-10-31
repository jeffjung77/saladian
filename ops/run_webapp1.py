"""Entrypoint used by the isolated development server launcher."""
import atexit
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.chdir(root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.webapp1'
pid_file = root / 'logs' / 'server.pid'
pid_file.parent.mkdir(exist_ok=True)
pid_file.write_text(str(os.getpid()), encoding='ascii')
atexit.register(lambda: pid_file.unlink(missing_ok=True))
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py', 'runserver', '127.0.0.1:8001', '--noreload'])
