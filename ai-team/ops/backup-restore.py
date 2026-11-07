#!/usr/bin/env python3
"""Local backup and isolated restoration verification. Never touches shared DBs."""
import datetime, hashlib, json, os, shutil, subprocess, tarfile, tempfile
from pathlib import Path
ROOT = Path('/opt/ceo-orchestrator/ai-team')
R = ROOT/'runtime'
DIST = ROOT.parent/'data/postgres-dist'
BIN = DIST/'usr/lib/postgresql/16/bin'
ENV = dict(os.environ, LD_LIBRARY_PATH=str(DIST/'usr/lib/x86_64-linux-gnu'))
os.umask(0o077)
def run(name, *args, **kwargs):
    return subprocess.run([str(BIN/name), *map(str,args)], env=ENV, check=True, **kwargs)
def query(socket,port,sql):
    return run('psql','-h',socket,'-p',port,'-U','ceo_ai_team','-d','ceo_orchestrator','-At','-c',sql,capture_output=True,text=True).stdout.strip()
backup = ROOT/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, mode=0o700)
run('pg_dump','-h',R/'pgsocket','-p','55438','-U','ceo_ai_team','-d','ceo_orchestrator','-Fc','-f',backup/'database.dump')
files=['paperclip-config.json','service.env','secrets','storage','hermes-home','paperclip-home','sandbox']
with tarfile.open(backup/'state.tar.gz','w:gz') as tar:
    for name in files:
        if (R/name).exists(): tar.add(R/name,arcname=name)
checksums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in backup.iterdir()}
(backup/'sha256.json').write_text(json.dumps(checksums,indent=2))
for p in backup.iterdir(): p.chmod(0o600)
work = Path(tempfile.mkdtemp(prefix='restore-',dir=R))
started=False
try:
    sock=work/'sock';sock.mkdir(mode=0o700)
    run('initdb','-D',work/'db','-L',DIST/'usr/share/postgresql/16','-U','ceo_ai_team','--auth-local=trust','--auth-host=reject','--encoding=UTF8','--locale=C.UTF-8',stdout=subprocess.DEVNULL)
    with (work/'db/postgresql.conf').open('a') as f:
        f.write(f"\nlisten_addresses=''\nport=55439\nunix_socket_directories='{sock}'\ndynamic_library_path='{DIST/'usr/lib/postgresql/16/lib'}'\nshared_buffers='32MB'\n")
    run('pg_ctl','-D',work/'db','-l',work/'postgres.log','start','-w',stdout=subprocess.DEVNULL);started=True
    run('createdb','-h',sock,'-p','55439','-U','ceo_ai_team','ceo_orchestrator')
    run('pg_restore','-h',sock,'-p','55439','-U','ceo_ai_team','-d','ceo_orchestrator','--exit-on-error',backup/'database.dump',stdout=subprocess.DEVNULL)
    sql="SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    before=query(R/'pgsocket','55438',sql);after=query(sock,'55439',sql)
    assert before==after and 'agents' in after and 'companies' in after
    tables=['companies','agents','projects','issues','heartbeat_runs','approvals','invites']
    counts={}
    for table in tables:
        a=query(R/'pgsocket','55438',f'SELECT count(*) FROM "{table}"');b=query(sock,'55439',f'SELECT count(*) FROM "{table}"')
        assert a==b,(table,a,b)
        counts[table]=int(a)
    state=work/'state';state.mkdir(mode=0o700)
    with tarfile.open(backup/'state.tar.gz') as tar: tar.extractall(state,filter='data')
    for name in ['paperclip-config.json','service.env','secrets/master.key','secrets/db-password']:
        assert (R/name).read_bytes()==(state/name).read_bytes()
    evidence={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup':str(backup.relative_to(ROOT)), 'restored_database':'ceo_orchestrator','temporary_port':55439,'public_tables':len(after.splitlines()),'row_counts':counts,'config_and_key_byte_match':True,'status':'passed','limitation':'Pre-owner database; no company, agent, project, task or run continuity yet.'}
    (ROOT/'evidence/restore.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))
finally:
    if started: run('pg_ctl','-D',work/'db','stop','-m','fast','-w',stdout=subprocess.DEVNULL)
    shutil.rmtree(work)
