#!/usr/bin/env bash
set -euo pipefail
cd /srv/bpms/app
test -f ops/deployment_runner.py
sudo -n install -d -m 755 /usr/local/lib/bpms
sudo -n install -m 644 ops/deployment_runner.py /usr/local/lib/bpms/deployment_runner.py
sudo -n install -m 644 ops/bpms-deployment.service /etc/systemd/system/bpms-deployment.service
sudo -n install -m 644 ops/bpms-deployment.timer /etc/systemd/system/bpms-deployment.timer
mkdir -p /srv/bpms/deploy
chmod 700 /srv/bpms/deploy
# Set only the scheduler flag. Preserve all existing secrets and settings.
sudo -n /usr/bin/python3 - <<'PY'
from pathlib import Path
path = Path('/etc/bpms.env')
lines = path.read_text().splitlines()
lines = [line for line in lines if not line.startswith('BPMS_DEPLOYMENT_SCHEDULER=')]
lines.append('BPMS_DEPLOYMENT_SCHEDULER=1')
path.write_text('\n'.join(lines) + '\n')
path.chmod(0o600)
PY
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now bpms-deployment.timer
sudo -n systemctl start bpms-deployment.service
sudo -n systemctl restart bpms
sudo -n systemctl is-active bpms bpms-deployment.timer
sudo -n systemctl list-timers bpms-deployment.timer --no-pager
