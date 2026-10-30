import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deployment_runner', Path(__file__).with_name('deployment_runner.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_failed_migration_restores_backup_and_keeps_target_pinned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / 'app'
            (app / 'config').mkdir(parents=True)
            (app / 'config/production.py').write_text('production')
            database = app / 'db.sqlite3'
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('create table original (value text)')
                db.execute("insert into original values ('preserved')")
            state = root / 'state'
            state.mkdir()
            statuses, commands = [], []

            def manage(operation, *args):
                if operation == 'info':
                    return {'database': str(database)}
                if operation == 'mark':
                    statuses.append(args[args.index('--status')+1])
                return {}

            def run(args, **kwargs):
                commands.append(args)
                if args[:3] == ['git', 'rev-parse', 'HEAD']:
                    return 'b'*40
                if 'migrate' in args:
                    with closing(sqlite3.connect(database)) as db, db:
                        db.execute('delete from original')
                    raise RuntimeError('simulated migration failure')
                return ''

            with patch.multiple(runner, APP=app, STATE=state, JOURNAL=state/'inprogress.json', BACKUPS=root/'backups'), \
                 patch.object(runner, 'manage', side_effect=manage), patch.object(runner, 'run', side_effect=run), \
                 patch.object(runner, 'validate'), patch.object(runner, 'service'), patch.object(runner, 'public_check'), \
                 patch.object(runner.subprocess, 'run'):
                runner.deploy({'id': 1, 'commit': 'a'*40, 'branch': '1-6'})
                self.assertIn('rolled_back', statuses)
                self.assertIn(['git', 'checkout', '--detach', 'a'*40], commands)
                self.assertIn(['git', 'checkout', '--detach', 'b'*40], commands)
                self.assertFalse(runner.JOURNAL.exists())
                with closing(sqlite3.connect(database)) as db:
                    self.assertEqual(db.execute('select value from original').fetchone()[0], 'preserved')


if __name__ == '__main__':
    unittest.main()
