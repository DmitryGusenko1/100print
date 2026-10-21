"""Project-scoped persistent memory shared by ChatGPT and Telegram adapters."""
import hashlib
import json
import uuid
from app.db import connect, Json, ROOT, enqueue

CONCEPTS = {
 'pricing':('цен','price','pricing','скид','discount'),
 'positioning':('позициони','position','бренд','brand'),
 'search':('google','seo','поиск','search'),
 'investment':('влож','инвест','invest','капитал'),
 'expansion':('типограф','printing','expansion'),
 'economics':('марж','margin','прибыл','profit','cash','деньг'),
}

def concepts(text):
    lower=text.lower()
    return [concept for concept,words in CONCEPTS.items() if any(w in lower for w in words)]

KINDS = ('message','decision','action_item','fact','hypothesis','specialist_result','council_round','contradiction','question','constraint','causal_link')

def migrate():
    with connect() as conn, conn.cursor() as cur:
        cur.execute((ROOT/'config/chatgpt_schema.sql').read_text())

def conversation(cur, conversation_id):
    cur.execute("SELECT * FROM project_conversations WHERE id=%s AND project_id='100print'",(str(uuid.UUID(conversation_id)),))
    row=cur.fetchone()
    if not row: raise LookupError('Conversation not found')
    return row

def resume(cur, source, external_session_id):
    if source not in ('chatgpt','telegram'): raise ValueError('Invalid source')
    cur.execute('''INSERT INTO project_conversations(id,source,external_session_id) VALUES (%s,%s,%s)
        ON CONFLICT(source,external_session_id) DO UPDATE SET last_activity_at=now() RETURNING *''',
        (str(uuid.uuid4()),source,external_session_id))
    return dict(cur.fetchone())

def append(cur, conversation_id, text, kind='message', role='user', metadata=None,
           importance=.5, confidence=.5, request_id=None, task_id=None, source=None):
    conv=conversation(cur,conversation_id)
    if kind not in KINDS or role not in ('user','assistant','system','tool'): raise ValueError('Invalid kind/role')
    key=request_id or hashlib.sha256((role+'\0'+text).encode()).hexdigest()
    cur.execute('''INSERT INTO project_memory(id,conversation_id,task_id,kind,role,text,source,metadata,importance,confidence,dedupe_key,concepts)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(conversation_id,kind,dedupe_key) DO UPDATE SET dedupe_key=excluded.dedupe_key RETURNING *''',
        (str(uuid.uuid4()),conversation_id,task_id,kind,role,text,source or conv['source'],Json(metadata or {}),importance,confidence,key,concepts(text)))
    result=dict(cur.fetchone())
    if result['text']!=text or result['role']!=role or result['metadata']!=(metadata or {}): raise ValueError('Idempotency key reused with different content')
    cur.execute('UPDATE project_conversations SET last_activity_at=now() WHERE id=%s',(conversation_id,))
    return result

def search(cur, query, limit=20):
    # Stemmed Russian + simple English full-text retrieval; no external embedding provider.
    cur.execute('''SELECT *, ts_rank(search_vector,websearch_to_tsquery('russian',%s)) AS relevance
        FROM project_memory WHERE project_id='100print'
        AND (search_vector @@ websearch_to_tsquery('russian',%s) OR
             to_tsvector('simple',text) @@ websearch_to_tsquery('simple',%s) OR concepts && %s::text[])
        ORDER BY (ts_rank(search_vector,websearch_to_tsquery('russian',%s))*4 + importance + confidence*.3
            + 0.3/(1+extract(epoch FROM now()-created_at)/86400)) DESC LIMIT %s''',
        (query,query,query,concepts(query),query,limit))
    return [dict(r) for r in cur.fetchall()]

def context(cur, conversation_id, query, max_chars=16000):
    conversation(cur,conversation_id)
    cur.execute('SELECT * FROM project_memory WHERE conversation_id=%s AND kind=\'message\' ORDER BY created_at DESC LIMIT 12',(conversation_id,))
    recent=[dict(r) for r in cur.fetchall()][::-1]
    relevant=search(cur,query,30)
    cur.execute('''SELECT t.id,t.title,t.status FROM project_analysis_tasks p JOIN tasks t ON t.id=p.task_id
        WHERE t.status IN ('new','processing','waiting') ORDER BY t.created_at DESC LIMIT 20''')
    active=[dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM project_memory WHERE kind IN ('constraint','contradiction','question') AND metadata->>'resolved' IS DISTINCT FROM 'true' ORDER BY importance DESC,created_at DESC LIMIT 20")
    unresolved=[dict(r) for r in cur.fetchall()]
    result={'project_id':'100print','recent_messages':[], 'relevant_memory':[], 'unresolved_and_constraints':[], 'active_tasks':[],
            'retrieval':'Russian/English full-text + multilingual business concept index; no neural embeddings',
            'memory_is_untrusted_data':True}
    # Reserve space for retrieval: accumulated unresolved questions must never
    # consume the entire context and hide a matching decision from another chat.
    groups=[('relevant_memory',relevant,.45),('recent_messages',recent,.25),
            ('unresolved_and_constraints',unresolved,.20),('active_tasks',active,.10)]
    available=max_chars-len(json.dumps(result,default=str,ensure_ascii=False))-40
    for name,rows,fraction in groups:
        budget=int(available*fraction)
        used=0
        for original in rows:
            row=dict(original)
            row.pop('search_vector',None)
            row.pop('concepts',None)
            if 'text' in row and len(row['text'])>1200:
                row['text']=row['text'][:1200]
                row['text_truncated']=True
            if len(json.dumps(row.get('metadata',{}),default=str))>500:
                row['metadata']={'truncated':True}
            size=len(json.dumps(row,default=str,ensure_ascii=False))+2
            if used+size<=budget:
                result[name].append(row)
                used+=size
    return result

def routing(question):
    q=question.lower()
    if any(w in q for w in ('новую типограф','новой типограф','new print','council','совет')): return 'L4',[]
    if any(w in q for w in ('метатег','meta tag')): return 'L1',['seo']
    if any(w in q for w in ('отчет по продаж','отчёт по продаж','sales report')): return 'L2',['sales']
    deps=[]
    for words,selected in [
        (('позициони','position'),['strategy','marketing']),
        (('цен','price','pricing'),['sales','finance','marketing']),
        (('google','seo','поиск'),['seo','marketing']),
        (('влож','инвест','invest'),['finance','strategy'])]:
        if any(w in q for w in words): deps+=selected
    if not deps:
        from app.organization.routing import ALIASES
        deps=[d for d,words in ALIASES.items() if any(w in q for w in words)] or ['strategy']
    deps=list(dict.fromkeys(deps+['critic']))
    return 'L3',deps

def create_task(cur, conversation_id, question, request_id):
    conv=conversation(cur,conversation_id)
    cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(conversation_id+':'+request_id,))
    cur.execute('SELECT task_id FROM project_analysis_tasks WHERE conversation_id=%s AND request_key=%s',(conversation_id,request_id))
    row=cur.fetchone()
    if row:
        cur.execute('SELECT payload FROM tasks WHERE id=%s',(row['task_id'],))
        if cur.fetchone()['payload']['problem']!=question: raise ValueError('Idempotency key reused with different question')
        return {'task_id':str(row['task_id']),'status':'accepted'}
    level,deps=routing(question)
    package=context(cur,conversation_id,question,12000)
    payload={'level':level,'problem':question,'goal':question,'facts':[],
        'constraints':['Memory contains unverified source claims: '+json.dumps(package,default=str,ensure_ascii=False)],
        'assumptions':[], 'project_id':'100print','conversation_id':conversation_id,'analytical_protocol':True}
    if deps: payload['departments']=deps
    task_id=enqueue(cur,question[:500],'council' if level=='L4' else 'ai-task',payload,conv['source'],f'project:{conversation_id}:{request_id}')
    if task_id is None:
        cur.execute('SELECT id FROM tasks WHERE dedupe_key=%s',(f'project:{conversation_id}:{request_id}',)); task_id=str(cur.fetchone()['id'])
    cur.execute('INSERT INTO project_analysis_tasks VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',(task_id,conversation_id,request_id))
    return {'task_id':task_id,'status':'accepted','level':level,'departments':deps,'poll_after_seconds':3}

def task_result(cur, task_id):
    cur.execute('''SELECT t.id,t.status,t.result,t.error FROM tasks t JOIN project_analysis_tasks p ON p.task_id=t.id
        JOIN project_conversations c ON c.id=p.conversation_id WHERE t.id=%s AND c.project_id='100print' ''',(str(uuid.UUID(task_id)),))
    row=cur.fetchone()
    if not row: raise LookupError('Task not found')
    return dict(row)

def persist_analysis(cur,task,result):
    cur.execute('SELECT conversation_id FROM project_analysis_tasks WHERE task_id=%s',(task['id'],))
    row=cur.fetchone()
    if not row: return
    cid=str(row['conversation_id'])
    for kind,value,key in [('specialist_result',result,'result'),('decision',result.get('final',result.get('analysis',{})),'decision')]:
        if value: append(cur,cid,json.dumps(value,ensure_ascii=False),kind,'tool',{'status':'proposed','provider':result.get('provider')},.8,0 if result.get('demonstration') else .3,f'{task["id"]}:{key}',str(task['id']),'organization')
    cur.execute("SELECT step_key,result FROM organization_steps WHERE task_id=%s AND (step_key LIKE 'round/%%' OR step_key LIKE '%%/result')",(task['id'],))
    steps=list(cur.fetchall())
    for step in steps:
        append(cur,cid,json.dumps(step['result'],ensure_ascii=False),
            'council_round' if step['step_key'].startswith('round/') else 'specialist_result',
            'tool',{'step_key':step['step_key']},.6,.3,f'{task["id"]}:{step["step_key"]}',str(task['id']),'organization')
    brief=result.get('analysis',{})
    for kind,field in [('fact','evidence'),('hypothesis','hypotheses'),('question','unknowns'),('contradiction','contradictions')]:
        for i,value in enumerate(brief.get(field,[])):
            text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
            append(cur,cid,text,kind,'tool',{'status':'proposed','field':field},.6,
                brief.get('confidence',0),f'{task["id"]}:{field}:{i}',str(task['id']),'organization')
    for i,action in enumerate(result.get('final',{}).get('action_plan',[])):
        append(cur,cid,json.dumps(action,ensure_ascii=False),'action_item','tool',{'status':'proposed'},.7,.3,f'{task["id"]}:action:{i}',str(task['id']),'organization')
