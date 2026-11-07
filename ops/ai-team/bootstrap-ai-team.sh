#!/bin/bash
# One administrative entry point for the already prepared 100print deployment.
set -Eeuo pipefail
umask 077
BASE=/opt/ceo-orchestrator
TEAM="$BASE/ai-team"
fail() { echo "INSTALL INCOMPLETE: $*" >&2; exit 1; }
[[ ${EUID} -eq 0 ]] || fail "Run with sudo bash"
getent passwd ceoorch >/dev/null || fail "ceoorch account missing"
[[ -d "$TEAM/runtime" ]] || fail "Prepared ai-team installation missing"
[[ -f "$TEAM/ops/install-services.sh" ]] || fail "Prepared service installer missing"
[[ -f "$BASE/app/github_worker.py" ]] || fail "Server executor missing"
systemctl is-active --quiet ceo-github-worker.service || fail "ceo-github-worker is not running"
# Enable a persistent unprivileged service manager, not unrestricted sudo.
if ! dpkg-query -W -f='${Status}' dbus-user-session 2>/dev/null | grep -q 'install ok installed'; then
 apt-get update -qq
 DEBIAN_FRONTEND=noninteractive apt-get install -y dbus-user-session
fi
USER_UID=$(id -u ceoorch)
loginctl enable-linger ceoorch
systemctl start "user@${USER_UID}.service"
runuser -u ceoorch -- env XDG_RUNTIME_DIR="/run/user/$USER_UID" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_UID/bus" systemctl --user show-environment >/dev/null
# Check only the two prepared units before any handoff.
for unit in ceo-ai-team-postgres ceo-ai-team-paperclip; do
 unit_file="$TEAM/ops/systemd/$unit.service"
 [[ -f "$unit_file" ]] || fail "Missing $unit_file"
 grep -qx 'User=ceoorch' "$unit_file" || fail "$unit must run as ceoorch"
 systemd-analyze verify "$unit_file"
done
# Request is written before the readiness marker awakens the existing executor.
install -d -o ceoorch -g ceoorch -m 0700 "$BASE/data"
python3 - "$BASE/data/ai-team-launch-request.json" "$USER_UID" <<'PY'
import json,os,pwd,sys,time,uuid
p=sys.argv[1]
u=pwd.getpwnam("ceoorch")
data={"request_id":str(uuid.uuid4()),"requested_at":time.time(),"issue":18,
      "user_runtime_dir":"/run/user/"+sys.argv[2],"goal":"Hermes Telegram owner dialogue and approved overnight execution"}
tmp=p+".tmp"
with open(tmp,"w") as f:
 json.dump(data,f)
os.chmod(tmp,0o600);os.chown(tmp,u.pw_uid,u.pw_gid);os.replace(tmp,p)
PY
/bin/sh "$TEAM/ops/install-services.sh"
echo "Administrative setup passed. The server executor is resuming issue #18."
echo "Waiting for verified Telegram readiness; no success is claimed before its receipt."
python3 - "$BASE/data" <<'PY'
import json,pathlib,sys,time
d=pathlib.Path(sys.argv[1])
request=json.loads((d/"ai-team-launch-request.json").read_text())
last=""
for step in range(1200):
 try:
  r=json.loads((d/"ai-team-telegram-ready.json").read_text())
  if r.get("request_id")==request["request_id"] and r.get("status")=="VERIFIED":
   required=("model_inference","gateway_active","owner_allowlist","outbound_owner_message")
   if all(r.get(k) is True for k in required):
    print("VERIFIED: Hermes model and Telegram gateway are running; owner readiness message delivered.")
    print("Open your Telegram bot and approve the overnight plan there.")
    sys.exit(0)
  if r.get("request_id")==request["request_id"] and r.get("status")=="BLOCKED":
   print("INCOMPLETE: "+str(r.get("public_reason","See executor issue #18")));sys.exit(2)
 except (OSError,ValueError): pass
 if step%60==0:
  print("Waiting for executor verification (%d min); installation is not yet complete."%(step//60),flush=True)
 time.sleep(1)
print("INCOMPLETE: no verified Telegram receipt within 20 minutes. The executor remains running; see issue #18.")
sys.exit(3)
PY
