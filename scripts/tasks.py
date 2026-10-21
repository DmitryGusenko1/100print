import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import connect, enqueue
p=argparse.ArgumentParser()
p.add_argument('command',choices=['add','show','status'])
p.add_argument('--title',default='Smoke test')
p.add_argument('--type',default='echo')
p.add_argument('--payload',default='{"message":"hello"}')
p.add_argument('--id')
a=p.parse_args()
with connect() as conn, conn.cursor() as cur:
    if a.command=='add': print(enqueue(cur,a.title,a.type,json.loads(a.payload)))
    elif a.command=='show':
        cur.execute('SELECT * FROM tasks WHERE id=%s',(a.id,));print(json.dumps(cur.fetchone(),default=str,ensure_ascii=False))
    else:
        cur.execute('SELECT * FROM heartbeats');print(json.dumps(cur.fetchall(),default=str))
        cur.execute('SELECT status,count(*) FROM tasks GROUP BY status');print(json.dumps(cur.fetchall(),default=str))
