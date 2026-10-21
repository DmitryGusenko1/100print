"""Single-worker durable queue with transactional scheduling and crash recovery."""
import concurrent.futures
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

# Preserve compatibility with the already installed systemd ExecStart.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import ROOT, Json, connect, enqueue
from app.providers import LocalBrainProvider

stop = False

def start_database():
    dist=ROOT/'data/postgres-dist'
    env={**os.environ,'LD_LIBRARY_PATH':str(dist/'usr/lib/x86_64-linux-gnu')}
    command=[str(dist/'usr/lib/postgresql/16/bin/pg_ctl'),'-D',str(ROOT/'data/pgdata')]
    if subprocess.run(command+['status'],env=env,stdout=subprocess.DEVNULL).returncode:
        subprocess.run(command+['-l',str(ROOT/'logs/postgres.log'),'start','-w'],env=env,check=True,timeout=60)

def recover(cur, startup=False, active=None):
    cur.execute('''SELECT id,attempts,max_attempts FROM tasks WHERE status='processing'
        AND (%s OR started_at < now() - %s * interval '1 second')
        AND (%s::uuid IS NULL OR id != %s::uuid) FOR UPDATE''',
        (startup,int(os.getenv('CEO_STALE_SECONDS','300')),active,active))
    for row in cur.fetchall():
        status='new' if row['attempts'] < row['max_attempts'] else 'failed'
        cur.execute('''UPDATE tasks SET status=%s,error='Interrupted worker; recovered',
            updated_at=now(),available_at=now(),finished_at=CASE WHEN %s='failed' THEN now() END WHERE id=%s''', (status,status,row['id']))
        cur.execute("UPDATE agent_runs SET status='interrupted',finished_at=now(),error='Worker interrupted' WHERE task_id=%s AND status='processing'",(row['id'],))
        logging.warning('recovered task=%s status=%s',row['id'],status)

def due(cur,name,seconds):
    cur.execute('''INSERT INTO scheduler_state(name,last_run) VALUES (%s,now())
        ON CONFLICT(name) DO UPDATE SET last_run=now()
        WHERE scheduler_state.last_run < now() - %s * interval '1 second' RETURNING name''',(name,seconds))
    return cur.fetchone() is not None

def maintenance(cur, active):
    cur.execute('''INSERT INTO heartbeats VALUES ('orchestrator',now(),%s)
        ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,details=excluded.details''',
        (Json({'pid':os.getpid(),'active_task':active}),))
    if due(cur,'maintenance',60):
        recover(cur,active=active)
        cur.execute("SELECT id,task_id FROM handoffs WHERE status='pending' AND updated_at < now()-interval '5 minutes' FOR UPDATE")
        for handoff in cur.fetchall():
            enqueue(cur,'Review pending handoff','follow_up',{'parent_task':str(handoff['task_id'])},'scheduler',f"handoff:{handoff['id']}")
            cur.execute("UPDATE handoffs SET status='waiting',updated_at=now() WHERE id=%s",(handoff['id'],))
    if due(cur,'hourly',3600):
        cur.execute("SELECT id FROM tasks WHERE status IN ('new','waiting','processing') AND type!='follow_up' AND updated_at < now()-interval '1 hour'")
        for row in cur.fetchall():
            enqueue(cur,'Review inactive task','follow_up',{'parent_task':str(row['id'])},'scheduler',f"followup:{row['id']}")
    if due(cur,'daily',86400):
        cur.execute("SELECT status,count(*) AS count FROM tasks GROUP BY status")
        counts={row['status']:row['count'] for row in cur.fetchall()}
        cur.execute("SELECT count(*) AS n FROM tasks WHERE status='done' AND finished_at > now()-interval '1 day'")
        completed=cur.fetchone()['n']
        cur.execute("SELECT id,title,status FROM tasks WHERE status IN ('waiting','failed') OR result->>'requires_decision'='true' OR (status='processing' AND started_at < now()-interval '5 minutes') ORDER BY created_at DESC LIMIT 100")
        needs=[dict(row,id=str(row['id'])) for row in cur.fetchall()]
        cur.execute('''INSERT INTO reports(day,body) VALUES (current_date,%s) ON CONFLICT(day) DO UPDATE SET body=excluded.body''',
            (Json({'counts':counts,'completed_last_day':completed,'requires_decision_or_stuck':needs,'automatic_actions':['bounded retry','deduplicated follow-up','handoff review']}),))
        logging.info('daily report counts=%s',counts)

def claim(cur):
    cur.execute('''SELECT * FROM tasks WHERE status='new' AND available_at<=now()
        ORDER BY priority DESC,created_at FOR UPDATE SKIP LOCKED LIMIT 1''')
    task=cur.fetchone()
    if not task: return None
    from app.organization.routing import DEPARTMENTS
    business=task['type'] in ('ai-task','council',*DEPARTMENTS)
    cur.execute("SELECT id FROM agents WHERE enabled AND id=%s",('chief-of-staff' if business else 'local',))
    agent=cur.fetchone()
    if not agent: return None
    task=dict(task); task['assigned_to']=agent['id']
    cur.execute("UPDATE tasks SET status='processing',started_at=now(),updated_at=now(),attempts=attempts+1,assigned_to=%s,error=NULL WHERE id=%s",(agent['id'],task['id']))
    cur.execute("INSERT INTO agent_runs(task_id,agent_id,status) VALUES (%s,%s,'processing') RETURNING id",(task['id'],agent['id']))
    task['run_id']=cur.fetchone()['id']
    cur.execute('INSERT INTO decisions(task_id,body) VALUES (%s,%s)',(task['id'],Json({'agent':agent['id'],'reason':'business routing pending' if business else 'enabled local handler'})))
    logging.info('task=%s new -> processing agent=%s',task['id'],agent['id'])
    return task

def finish(cur, task, result=None, error=None):
    if error:
        cur.execute('SELECT attempts,max_attempts FROM tasks WHERE id=%s FOR UPDATE',(task['id'],))
        row=cur.fetchone(); status='new' if row['attempts']<row['max_attempts'] else 'failed'
        delay=min(300,2**row['attempts'])
    else:
        status='done'; delay=0
    cur.execute('''UPDATE tasks SET status=%s,result=%s,error=%s,updated_at=now(),
        finished_at=CASE WHEN %s IN ('done','failed') THEN now() END,
        available_at=now()+%s*interval '1 second' WHERE id=%s''',
        (status,Json(result) if result is not None else None,error,status,delay,task['id']))
    cur.execute('UPDATE agent_runs SET status=%s,finished_at=now(),result=%s,error=%s WHERE id=%s',
        ('failed' if error else 'done',Json(result) if result is not None else None,error,task['run_id']))
    if result:
        from app.project_memory import persist_analysis
        persist_analysis(cur,task,result)
    if result and result.get('requires_decision'):
        cur.execute('INSERT INTO decisions(task_id,body) VALUES (%s,%s)',(task['id'],Json(result)))
    logging.info('task=%s processing -> %s error=%s',task['id'],status,error)

def main():
    global stop
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[RotatingFileHandler(ROOT/'logs/orchestrator.log',maxBytes=5_000_000,backupCount=3),logging.StreamHandler()])
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda *_: globals().__setitem__('stop',True))
    start_database()
    # Session-level lock prohibits two workers from recovering each other's tasks.
    lock=connect(); lock.autocommit=True
    with lock.cursor() as cur:
        cur.execute('SELECT pg_try_advisory_lock(310003) AS locked')
        if not cur.fetchone()['locked']: raise RuntimeError('Worker already running')
    with connect() as conn, conn.cursor() as cur:
        cur.execute((ROOT/'config/schema.sql').read_text())
        cur.execute((ROOT/'config/chatgpt_schema.sql').read_text())
        from app.organization.registry import Registry
        Registry().sync(cur)
        recover(cur,startup=True)
    from dotenv import load_dotenv
    load_dotenv(ROOT/'config/chatgpt.env',override=False)
    api=None
    def start_api():
        return subprocess.Popen([sys.executable,'-m','uvicorn','app.chatgpt_api:app',
            '--host','127.0.0.1','--port','8096'],cwd=ROOT,
            stdout=open(ROOT/'logs/chatgpt-api.log','a'),stderr=subprocess.STDOUT)
    provider=LocalBrainProvider(); current=None; future=None
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    github_pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    github_future=None; github_next=0
    try:
        while not stop:
            if os.getenv('CEO_CHATGPT_MANAGED','1')=='1' and os.getenv('CEO_CHATGPT_TOKEN') and (api is None or api.poll() is not None):
                api=start_api()
            if os.getenv('CEO_GITHUB_AI_ENABLED','1')=='1' and time.monotonic()>=github_next:
                if github_future is None or github_future.done():
                    if github_future is not None:
                        try: github_future.result()
                        except Exception: logging.exception('GitHub AI poll failed; retry next minute')
                    from app.organization.github import poll
                    github_future=github_pool.submit(poll)
                    github_next=time.monotonic()+60
            # Also validates that the singleton lock session remains alive.
            with lock.cursor() as cur: cur.execute('SELECT 1')
            with connect() as conn, conn.cursor() as cur:
                maintenance(cur,str(current['id']) if current else None)
                if future and future.done():
                    try: result=future.result(); error=None
                    except Exception as exc: result=None;error=str(exc)[:2000]
                    finish(cur,current,result,error)
                    future=None;current=None
            if not future:
                with connect() as conn, conn.cursor() as cur: current=claim(cur)
                # Commit processing before starting any side effects.
                if current: future=pool.submit(provider.execute,current)
            time.sleep(max(0.2,float(os.getenv('CEO_POLL_SECONDS','2'))))
    finally:
        if api is not None:
            api.terminate()
            try: api.wait(timeout=10)
            except subprocess.TimeoutExpired: api.kill()
        github_pool.shutdown(wait=True)
        pool.shutdown(wait=True)
        lock.close()
        logging.info('worker stopped; any uncommitted result recovered on next start')

if __name__=='__main__':
    main()
