"""Each checkpoint commits independently; a recovered queue task resumes by UUID/key."""
import copy
import hashlib
import json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

class MemoryStore:
    def __init__(self): self.steps={}

    def get(self, task_id, key, digest):
        record=self.steps.get((str(task_id),key))
        if record and record[0]!=digest: raise ValueError('Checkpoint input/provider changed')
        return copy.deepcopy(record[1]) if record else None

    def put(self, task_id, key, digest, result, metadata):
        self.steps[(str(task_id),key)]=(digest,copy.deepcopy(result),metadata)

class PostgresStore:
    def get(self, task_id, key, digest):
        from app.db import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT fingerprint,result FROM organization_steps WHERE task_id=%s AND step_key=%s',(task_id,key))
            row=cur.fetchone()
            if row and row['fingerprint']!=digest: raise ValueError('Checkpoint input/provider changed')
            return row['result'] if row else None

    def put(self, task_id, key, digest, result, metadata):
        from app.db import connect, Json
        with connect() as conn, conn.cursor() as cur:
            cur.execute('''INSERT INTO organization_steps(task_id,step_key,fingerprint,result,metadata)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT(task_id,step_key) DO NOTHING''',
                (task_id,key,digest,Json(result),Json(metadata)))
            if key.startswith('handoff/'):
                cur.execute('''INSERT INTO organization_handoffs(task_id,handoff_key,body)
                    VALUES (%s,%s,%s) ON CONFLICT(task_id,handoff_key) DO NOTHING''', (task_id,key,Json(result)))
