from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from .test_helpers import AuthenticatedLedgerTestCase
from .models import DeploymentSchedule, Voucher
from .deployment import windows, public_state
from .management.commands.deployment_jobs import Command


@override_settings(DEPLOYMENT_SCHEDULER_ENABLED=True)
class DeploymentTests(AuthenticatedLedgerTestCase):
    def job(self, status='ready'):
        return DeploymentSchedule.objects.create(scheduled_date=date(2026, 11, 5), status=status, commit='a'*40, created_by=self.user)

    def test_korea_window_crosses_previous_day(self):
        warn, cutoff, deploy = windows(self.job())
        self.assertEqual(warn.strftime('%Y-%m-%d %H:%M'), '2026-11-04 23:31')
        self.assertEqual(cutoff.strftime('%Y-%m-%d %H:%M'), '2026-11-05 00:00')
        self.assertEqual(deploy.strftime('%H:%M'), '00:01')

    def test_notice_cutoff_and_cancel(self):
        job = self.job()
        warn, cutoff, _ = windows(job)
        self.assertFalse(public_state(warn-timedelta(seconds=1))['active'])
        self.assertTrue(public_state(warn)['active'])
        self.assertFalse(public_state(warn)['blocked'])
        self.assertTrue(public_state(cutoff)['blocked'])
        job.status = 'cancelled'
        job.save()
        self.assertFalse(public_state(cutoff)['blocked'])

    def test_tick_only_runs_reserved_day_once(self):
        job = self.job()
        warn, cutoff, deploy = windows(job)
        self.assertEqual(Command.tick(warn)['actions'], [])
        self.assertTrue(Session.objects.exists())
        self.assertEqual(Command.tick(cutoff)['actions'], [])
        self.assertFalse(Session.objects.exists())
        job.refresh_from_db()
        self.assertEqual(job.sessions_cleared_at, cutoff)
        self.assertEqual(Command.tick(deploy)['actions'][0]['commit'], 'a'*40)
        self.assertEqual(Command.tick(deploy)['actions'], [])

    def test_no_reservation_keeps_sessions(self):
        self.assertEqual(Command.tick()['actions'], [])
        self.assertTrue(Session.objects.exists())

    def test_preflight_missed_and_late_execution_are_cancelled(self):
        job = self.job('queued')
        warn, _, deploy = windows(job)
        self.assertEqual(Command.tick(warn-timedelta(minutes=1))['actions'][0]['action'], 'prepare')
        self.assertEqual(Command.tick(warn)['actions'], [])
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        job.status = 'ready'
        job.save()
        self.assertEqual(Command.tick(deploy+timedelta(minutes=6))['actions'], [])
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')

    def test_midnight_blocks_login_and_writes(self):
        job = self.job()
        _, cutoff, _ = windows(job)
        with patch('ledger.deployment.timezone.now', return_value=cutoff):
            self.assertEqual(self.client.post(reverse('sales_new'), {'amount': '1000'}).status_code, 503)
            self.assertFalse(Voucher.objects.exists())
            self.assertNotIn('_auth_user_id', self.client.session)
            self.assertEqual(self.client.get(reverse('login')).status_code, 503)
            self.assertTrue(self.client.get(reverse('deployment_status')).json()['blocked'])
            self.assertEqual(self.client.get(reverse('deployment_maintenance')).status_code, 200)

    def test_only_superuser_manages_and_fixed_commit_validation(self):
        self.assertEqual(self.client.get(reverse('deployment_management')).status_code, 403)
        self.user.is_superuser = True
        self.user.save()
        with patch('ledger.deployment_views.timezone.now', return_value=windows(self.job('cancelled'))[0]-timedelta(days=2)):
            self.client.force_login(self.user)
            data = {'scheduled_date': '2026-11-05', 'branch': '1-6', 'commit': 'a'*40}
            self.assertEqual(self.client.post(reverse('deployment_management'), data).status_code, 302)
            self.assertEqual(DeploymentSchedule.objects.filter(status='queued').count(), 1)
            data['commit'] = 'HEAD;rm'
            self.assertEqual(self.client.post(reverse('deployment_management'), data).status_code, 200)
            self.assertEqual(DeploymentSchedule.objects.filter(status='queued').count(), 1)

    def test_poll_does_not_extend_idle_session(self):
        session = self.client.session
        session['last_activity_at'] = 100
        session.save()
        self.client.get(reverse('deployment_status'))
        self.assertEqual(self.client.session['last_activity_at'], 100)

    def test_cli_json_disabled_and_cancel(self):
        job = self.job()
        output = StringIO()
        call_command('deployment_jobs', 'cancel', job=job.pk, stdout=output)
        self.assertIn('updated', output.getvalue())
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')
        with override_settings(DEPLOYMENT_SCHEDULER_ENABLED=False):
            self.assertEqual(Command.tick()['actions'], [])
            self.assertFalse(public_state()['blocked'])

    def test_preparation_finishing_after_notice_time_is_rejected(self):
        job = self.job('queued')
        with patch('ledger.management.commands.deployment_jobs.timezone.now', return_value=windows(job)[0]):
            call_command('deployment_jobs', 'mark', job=job.pk, status='ready', stdout=StringIO())
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
