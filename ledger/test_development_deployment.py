from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from django.test import override_settings
from .test_helpers import AuthenticatedLedgerTestCase
from .models import DeploymentSchedule
from .deployment import windows, public_state
from .development_deployment import simulate_once


@override_settings(DEPLOYMENT_SIMULATION_MODE=True, DEPLOYMENT_SCHEDULER_ENABLED=True)
class DevelopmentDeploymentTests(AuthenticatedLedgerTestCase):
    def job(self, status='queued'):
        return DeploymentSchedule.objects.create(scheduled_date=date(2026, 11, 8), status=status,
            branch='1-6', commit='a'*40, created_by=self.user)

    def test_local_commit_prepares_and_cancelled_job_stays_cancelled(self):
        job = self.job()
        now = windows(job)[0]
        from datetime import timedelta
        with patch('ledger.development_deployment.git', return_value=''), patch('ledger.development_deployment.timezone.now', return_value=now-timedelta(hours=1)):
            simulate_once(now-timedelta(hours=1))
            job.refresh_from_db()
            self.assertEqual(job.status, 'ready')
            job.status = 'cancelled'
            job.save()
            simulate_once(now)
            job.refresh_from_db()
            self.assertEqual(job.status, 'cancelled')

    def test_simulation_backs_up_and_reopens_without_checkout(self):
        job = self.job('ready')
        now = windows(job)[2]
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = ('ok',)
        with TemporaryDirectory() as temp, override_settings(BASE_DIR=Path(temp)/'app'), \
             patch('ledger.development_deployment.settings', SimpleNamespace(
                 DEPLOYMENT_SIMULATION_MODE=True, DEPLOYMENT_SCHEDULER_ENABLED=True,
                 BASE_DIR=Path(temp)/'app', DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'mock.sqlite3'}})), \
             patch('ledger.development_deployment.sqlite3.connect', return_value=connection), \
             patch('ledger.development_deployment.git', return_value='b'*40) as git:
            simulate_once(now)
            job.refresh_from_db()
            self.assertEqual(job.status, 'simulated')
            self.assertTrue(Path(job.backup_path).is_dir())
            self.assertFalse(public_state(now)['blocked'])
            connection.backup.assert_called_once()
            git.assert_called_once_with('rev-parse', 'HEAD')

    def test_production_mode_never_simulates(self):
        job = self.job()
        with override_settings(DEPLOYMENT_SIMULATION_MODE=False), patch('ledger.development_deployment.git') as git:
            simulate_once()
            job.refresh_from_db()
            self.assertEqual(job.status, 'queued')
            git.assert_not_called()
