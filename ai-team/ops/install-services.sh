#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run this script as root'; exit 1; }
for name in ceo-ai-team-paperclip ceo-ai-team-postgres; do
 if systemctl is-active --quiet "$name.service"; then systemctl stop "$name.service"; fi
done
runuser -u ceoorch -- python3 /opt/ceo-orchestrator/ai-team/ops/stop-temporary.py
if [ -f /opt/ceo-orchestrator/ai-team/runtime/pgdata/postmaster.pid ]; then
 runuser -u ceoorch -- env LD_LIBRARY_PATH=/opt/ceo-orchestrator/data/postgres-dist/usr/lib/x86_64-linux-gnu /opt/ceo-orchestrator/data/postgres-dist/usr/lib/postgresql/16/bin/pg_ctl -D /opt/ceo-orchestrator/ai-team/runtime/pgdata stop -m fast -w
fi
for name in ceo-ai-team-postgres ceo-ai-team-paperclip; do
 install -m 0644 "/opt/ceo-orchestrator/ai-team/ops/systemd/$name.service" "/etc/systemd/system/$name.service"
done
systemctl daemon-reload
systemctl enable --now ceo-ai-team-postgres.service ceo-ai-team-paperclip.service
systemctl is-active ceo-ai-team-postgres.service ceo-ai-team-paperclip.service
runuser -u ceoorch -- python3 - <<'CHECK'
import json,time,urllib.request
for attempt in range(45):
 try:
  with urllib.request.urlopen('http://localhost:3180/api/health',timeout=2) as response:
   status=json.load(response)
  if status.get('status')=='ok' and status.get('deploymentMode')=='authenticated': break
 except (OSError,ValueError): pass
 time.sleep(1)
else: raise SystemExit('Paperclip authenticated health did not become ready; no readiness marker created')
CHECK
install -o ceoorch -g ceoorch -m 0600 /dev/null /opt/ceo-orchestrator/data/ai-team-services-ready
