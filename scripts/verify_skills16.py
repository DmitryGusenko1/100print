"""Project-local production acceptance; no customer-facing external messages."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import connect, enqueue
from app.organization.registry import Registry

def main():
    registry=Registry()
    with connect() as conn,conn.cursor() as cur:
        registry.sync(cur)
        cur.execute("SELECT count(*) AS n FROM skills_registry WHERE definition ? 'priority'")
        assert cur.fetchone()['n']==17
        tid=enqueue(cur,'Как оценить качество макета до печати?','ai-task',
            {'level':'L2','skill_id':'operations.prepress','project_id':'100print',
             'facts':['Метаданные файла и требования оборудования пока не предоставлены.']},'integration-test')
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        with connect() as conn,conn.cursor() as cur:
            cur.execute('SELECT status,result FROM tasks WHERE id=%s',(tid,)); row=cur.fetchone()
            if row['status']=='done':
                result=row['result']
                assert result['provider']=='production-codex-v1' and not result['demonstration']
                assert result['routing']['level']=='L2'
                assert result['assignments'][0]['skill_id']=='operations.prepress'
                cur.execute('SELECT step_key,result FROM organization_steps WHERE task_id=%s',(tid,))
                steps={r['step_key']:r['result'] for r in cur.fetchall()}
                assert {'L2/specialist/operations.prepress','L2/operations/result','L2/critic'} <= steps.keys()
                assert steps['L2/specialist/operations.prepress']['evidence_gaps']
                report={'task_id':tid,'provider':result['provider'],'level':'L2','registered_specialists':17,'durable_steps':len(steps),'verified':True}
                Path('data/issue16-production.json').write_text(json.dumps(report,indent=2)+'\n')
                print(json.dumps(report)); return
            if row['status']=='failed': raise RuntimeError('Production task failed; inspect project task')
        time.sleep(3)
    raise RuntimeError('Production acceptance deadline exceeded')
if __name__=='__main__': main()
