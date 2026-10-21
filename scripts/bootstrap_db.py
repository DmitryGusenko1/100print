"""Provision a new private cluster; never connect to a shared PostgreSQL instance."""
import os
from pathlib import Path
import secrets
import re
import subprocess

ROOT = Path('/opt/ceo-orchestrator')
DIST = ROOT / 'data/postgres-dist'
BIN = DIST / 'usr/lib/postgresql/16/bin'
SHARE = DIST / 'usr/share/postgresql/16'
LIB = DIST / 'usr/lib/postgresql/16/lib'
os.environ['LD_LIBRARY_PATH'] = str(DIST / 'usr/lib/x86_64-linux-gnu')
os.umask(0o077)
if (ROOT / '.env').exists() or (ROOT / 'data/pgdata').exists():
    raise SystemExit('Refusing to overwrite existing .env or cluster')
socket = ROOT / 'data/pgsocket'
socket.mkdir(exist_ok=True)
password = secrets.token_hex(32)
admin_password = secrets.token_hex(32)
pw = ROOT / 'data/init-password'
pw.write_text(admin_password)
try:
    subprocess.run([str(BIN/'initdb'), '-D', str(ROOT/'data/pgdata'), '-L', str(SHARE), '-U', 'ceo_cluster_admin', '--pwfile', str(pw), '--auth-local=scram-sha-256', '--auth-host=scram-sha-256', '--encoding=UTF8', '--locale=C.UTF-8'], check=True)
finally:
    pw.unlink(missing_ok=True)
with (ROOT/'data/pgdata/postgresql.conf').open('a') as f:
    f.write(f"\nlisten_addresses = ''\nport = 55433\nunix_socket_directories = '{socket}'\ndynamic_library_path = '{LIB}'\nmax_connections = 20\nshared_buffers = '32MB'\n")
control = SHARE/'extension/vector.control'
control.write_text(control.read_text().replace('$libdir/vector', str(LIB/'vector')))
(ROOT/'.env').write_text(f'CEO_DB_PASSWORD={password}\nCEO_POLL_SECONDS=2\nCEO_STALE_SECONDS=300\n')
subprocess.run([str(BIN/'pg_ctl'), '-D', str(ROOT/'data/pgdata'), '-l', str(ROOT/'logs/postgres.log'), 'start', '-w'], check=True)
import psycopg2
conn = psycopg2.connect(user='ceo_cluster_admin', password=admin_password, host=str(socket), port=55433, dbname='postgres')
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(f"CREATE ROLE ceo_orchestrator LOGIN PASSWORD '{password}'")
    cur.execute('CREATE DATABASE ceo_orchestrator OWNER ceo_orchestrator')
conn.close()
with psycopg2.connect(user='ceo_cluster_admin', password=admin_password, host=str(socket), port=55433, dbname='ceo_orchestrator') as conn:
    with conn.cursor() as cur:
        cur.execute('CREATE EXTENSION vector')

        cur.execute('ALTER ROLE ceo_cluster_admin NOLOGIN')
print('Private ceo_orchestrator cluster and pgvector ready; no TCP listener')
