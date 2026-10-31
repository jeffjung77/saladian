from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ledger'

    def ready(self):
        from . import notice_popup  # noqa: F401
        import os
        import sys
        from django.conf import settings
        if (getattr(settings, 'DEPLOYMENT_SIMULATION_MODE', False)
                and settings.DEPLOYMENT_SCHEDULER_ENABLED and 'runserver' in sys.argv
                and ('--noreload' in sys.argv or os.environ.get('RUN_MAIN') == 'true')):
            from .development_deployment import start_watcher
            start_watcher()
