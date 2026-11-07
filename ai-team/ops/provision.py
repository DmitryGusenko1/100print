#!/usr/bin/env python3
"""Provision only the isolated AI-team cluster and private configuration."""
import datetime, json, os, secrets, subprocess
from pathlib import Path
ROOT = Path('/opt/ceo-orchestrator/ai-team')
DIST = ROOT.parent / 'data/postgres-dist'
BIN = DIST / 'usr/lib/postgresql/16/bin'
os.umask(0o077)
os.environ['LD_LIBRARY_PATH'] = str(DIST / 'usr/lib/x86_64-linux-gnu')
runtime = ROOT / 'runtime'
for name in ['pgsocket', 'paperclip', 'hermes-home', 'sandbox', 'storage', 'logs', 'secrets']:
    (runtime / name).mkdir(parents=True, exist_ok=True, mode=0o700)
config = runtime / 'paperclip-config.json'
if config.exists():
    raise SystemExit('Already provisioned; refusing to overwrite keys or data')
password = secrets.token_hex(32)
pw = runtime / 'secrets/db-password'
pw.write_text(password)
subprocess.run([str(BIN/'initdb'), '-D', str(runtime/'pgdata'), '-L', str(DIST/'usr/share/postgresql/16'), '-U', 'ceo_ai_team', '--pwfile', str(pw), '--auth-local=trust', '--auth-host=scram-sha-256', '--encoding=UTF8', '--locale=C.UTF-8'], check=True, stdout=subprocess.DEVNULL)
with (runtime/'pgdata/postgresql.conf').open('a') as f:
    f.write(f"\nlisten_addresses='127.0.0.1'\nport=55438\nunix_socket_directories='{runtime/'pgsocket'}'\ndynamic_library_path='{DIST/'usr/lib/postgresql/16/lib'}'\nmax_connections=40\nshared_buffers='64MB'\n")
subprocess.run([str(BIN/'pg_ctl'), '-D', str(runtime/'pgdata'), '-l', str(runtime/'logs/postgres.log'), 'start', '-w'], check=True, stdout=subprocess.DEVNULL)
subprocess.run([str(BIN/'createdb'), '-h', str(runtime/'pgsocket'), '-p', '55438', '-U', 'ceo_ai_team', 'ceo_orchestrator'], check=True)
key = runtime/'secrets/master.key'
key.write_text(secrets.token_hex(32))
config.write_text(json.dumps({
 '$meta': {'version':1,'updatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'configure'},
 'database': {'mode':'postgres','connectionString':f'postgres://ceo_ai_team:{password}@127.0.0.1:55438/ceo_orchestrator','backup':{'enabled':False}},
 'logging':{'mode':'file','logDir':str(runtime/'logs')},
 'server':{'deploymentMode':'authenticated','exposure':'private','bind':'loopback','host':'127.0.0.1','port':3180,'serveUi':True},
 'auth':{'baseUrlMode':'explicit','publicBaseUrl':'http://localhost:3180','disableSignUp':False},
 'telemetry':{'enabled':False},'updates':{'checkEnabled':False},
 'storage':{'provider':'local_disk','localDisk':{'baseDir':str(runtime/'storage')}},
 'secrets':{'provider':'local_encrypted','localEncrypted':{'keyFilePath':str(key)}}
},indent=2))
(runtime/'service.env').write_text('BETTER_AUTH_SECRET='+secrets.token_hex(32)+'\n')
print('Provisioned isolated ceo_orchestrator on loopback:55438; secret files mode 0600')
