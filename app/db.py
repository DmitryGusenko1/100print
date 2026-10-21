import os
from pathlib import Path
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv
ROOT = Path('/opt/ceo-orchestrator')
load_dotenv(ROOT / '.env', override=True)

def connect():
    return psycopg2.connect(dbname='ceo_orchestrator', user='ceo_orchestrator',
        password=os.environ['CEO_DB_PASSWORD'], host=str(ROOT/'data/pgsocket'),
        port=55433, connect_timeout=5, cursor_factory=RealDictCursor)

def enqueue(cur, title, kind='echo', payload=None, source='cli', dedupe=None):
    task_id = str(uuid.uuid4())
    cur.execute('''INSERT INTO tasks(id,source,type,title,payload,dedupe_key)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(dedupe_key) DO NOTHING RETURNING id''',
        (task_id,source,kind,title,Json(payload or {}),dedupe))
    row=cur.fetchone()
    return str(row['id']) if row else None
