"""Allowlisted GitHub business command ingress and durable result delivery.

Uses gh's existing account; never reads credentials or executes issue text as code.
A closed issue is not an executable command. A unique DB dedupe key survives restarts.
"""
import json
import subprocess
from app.db import connect, enqueue
from .routing import DEPARTMENTS

REPO='DmitryGusenko1/100print'
OWNER='DmitryGusenko1'
TYPES=('ai-task','council',*DEPARTMENTS)

def gh(*args):
    result=subprocess.run(['gh',*args,'--repo',REPO],capture_output=True,text=True,timeout=30,check=True)
    return result.stdout


def parse_issue(issue):
    if issue.get('author',{}).get('login')!=OWNER: return None
    labels=[x['name'] if isinstance(x,dict) else x for x in issue.get('labels',[])]
    body=issue.get('body') or ''
    # Only an exact heading makes JSON executable; ordinary technical issues stay untouched.
    prefix='CEO-AI-TASK\n'
    marked=body.startswith(prefix)
    if not marked and not any(label in TYPES for label in labels): return None
    command=json.loads(body[len(prefix):]) if marked else {'problem':body or issue['title']}
    if not isinstance(command,dict): raise ValueError('Command must be a JSON object')
    allowed={'type','problem','goal','constraints','criteria','facts','assumptions','departments','level','skill_id'}
    if set(command)-allowed: raise ValueError('Unknown business command fields')
    kind=command.pop('type','council' if 'council' in labels else 'ai-task')
    if kind not in TYPES: raise ValueError('Unknown business command type')
    command['labels']=labels
    return {'title':issue['title'],'type':kind,'payload':command}


def ingest(issues):
    from .registry import Registry
    from .routing import route
    from .contracts import validate, CONTEXT
    registry=Registry(); inserted=[]
    for issue in issues:
        command=parse_issue(issue)
        if command is None: continue
        route(command,registry)  # Reject malformed requests before queueing.
        p=command['payload']
        validate(CONTEXT,{'problem':p.get('problem',command['title']),'goal':p.get('goal',command['title']),
            'constraints':p.get('constraints',[]),'criteria':p.get('criteria',[]),
            'facts':p.get('facts',[]),'assumptions':p.get('assumptions',[])})
        number=issue['number']
        with connect() as conn, conn.cursor() as cur:
            task_id=enqueue(cur,command['title'],command['type'],p,'github',f'github-ai:{REPO}:{number}')
            if task_id:
                cur.execute('INSERT INTO github_deliveries(issue_number,task_id) VALUES (%s,%s)',(number,task_id))
                inserted.append(task_id)
    return inserted


def deliver():
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT g.issue_number,t.id,t.status,t.result,t.error FROM github_deliveries g
            JOIN tasks t ON t.id=g.task_id WHERE g.delivered_at IS NULL AND t.status IN ('done','failed')''')
        pending=cur.fetchall()
    for row in pending:
        marker=f'<!-- ceo-ai-result:{row["id"]} -->'
        # A crash between GitHub and DB commit is recovered by finding the stable marker.
        comments=json.loads(gh('issue','view',str(row['issue_number']),'--json','comments'))['comments']
        existing=next((c for c in comments if marker in c['body']),None)
        url=existing.get('url') if existing else gh('issue','comment',str(row['issue_number']),'--body',
            marker+'\nCEO AI: '+row['status']+'\n\n```json\n'+json.dumps(row['result'] or {'error':row['error']},ensure_ascii=False,indent=2)[:55000]+'\n```').strip()
        with connect() as conn, conn.cursor() as cur:
            cur.execute('UPDATE github_deliveries SET delivered_at=now(),comment_url=%s WHERE issue_number=%s',(url,row['issue_number']))


def poll():
    import logging
    issues=json.loads(gh('issue','list','--state','open','--limit','100','--json','number,title,body,labels,author'))
    # Invalid issue never blocks other commands or delivery.
    for issue in issues:
        try: ingest([issue])
        except (ValueError, TypeError, KeyError) as exc:
            logging.warning('Rejected GitHub business command #%s: %s',issue['number'],type(exc).__name__)
        except Exception:
            logging.exception('GitHub business ingress failed for #%s',issue['number'])
    deliver()
