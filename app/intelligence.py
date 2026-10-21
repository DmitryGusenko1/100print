"""Project-local operational ledger. Stores structured evidence, never private reasoning."""
import hashlib
import json
import uuid
from app.db import Json, ROOT

TERMINAL = ('closed', 'done', 'rejected', 'validated')
STRATEGIC = ('business_model','portal_hypothesis','mvp_scope','customer_journey',
             'unit_economics','production_threshold','growth_stage','metric','risk','experiment','question')


def migrate(cur):
    cur.execute((ROOT/'config/intelligence_schema.sql').read_text())


def put(cur, kind, title, body=None, key=None, provenance=None, owner='chief-of-staff', deadline=None, review_at=None):
    body = body or {}
    key = key or hashlib.sha256((kind+'\0'+title.strip().casefold()).encode()).hexdigest()
    cur.execute('''INSERT INTO project_artifacts(id,artifact_type,title,body,dedupe_key,provenance,owner,deadline,review_at,summary)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,now()+interval '7 days'),%s)
        ON CONFLICT(dedupe_key) DO NOTHING RETURNING *''',
        (str(uuid.uuid4()),kind,title,Json(body),key,Json(provenance or {}),owner,deadline,review_at,title[:500]))
    row=cur.fetchone()
    if row: return dict(row)
    cur.execute('SELECT * FROM project_artifacts WHERE dedupe_key=%s',(key,))
    row=dict(cur.fetchone())
    if row['title']!=title or row['body']!=body: raise ValueError('Artifact idempotency conflict')
    return row


def link(cur, source, target, relation):
    cur.execute('INSERT INTO artifact_links VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',(source,target,relation))


def transition(cur, artifact_id, status, event_key, review_at=None):
    if status not in (*TERMINAL,'open','blocked','pending','active','snoozed'): raise ValueError('Unknown status')
    cur.execute('SELECT * FROM project_artifacts WHERE id=%s FOR UPDATE',(str(uuid.UUID(artifact_id)),))
    if not cur.fetchone(): raise LookupError('Artifact not found')
    cur.execute('''INSERT INTO artifact_history(artifact_id,event_key,body) VALUES (%s,%s,%s)
        ON CONFLICT DO NOTHING RETURNING id''',(artifact_id,event_key,Json({'status':status,'review_at':str(review_at) if review_at else None})))
    if cur.fetchone():
        cur.execute('UPDATE project_artifacts SET status=%s,review_at=COALESCE(%s,review_at),updated_at=now() WHERE id=%s',(status,review_at,artifact_id))


def record_analysis(cur, task, result):
    provenance={'task_id':str(task['id']), 'provider':result.get('provider'), 'status':'proposed'}
    final=result.get('final') or result.get('analysis') or result.get('result') or result.get('departmental_result') or {}
    decision_artifact=None
    decision=final.get('decision') or final.get('recommendation')
    if decision:
        row=put(cur,'decision',decision,final,key=f"analysis:{task['id']}:decision",provenance=provenance)
        decision_artifact=row['id']
        follow=put(cur,'follow_up','Пересмотреть: '+decision,{'decision_id':str(row['id'])},key=f"decision-review:{row['id']}",provenance=provenance)
        link(cur,follow['id'],row['id'],'follow_up')
    for kind,field in [('task','action_plan'),('hypothesis','hypotheses'),('question','unknowns'),('risk','risks')]:
        for i,value in enumerate(final.get(field,[])):
            title=value if isinstance(value,str) else value.get('action',value.get('hypothesis',json.dumps(value,ensure_ascii=False)))
            item=put(cur,kind,title,{'source_value':value},key='analysis-item:'+kind+':'+hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),provenance=provenance,
                owner=value.get('owner','chief-of-staff') if isinstance(value,dict) else 'chief-of-staff')
            if decision_artifact: link(cur,item['id'],decision_artifact,'depends_on')


def review(cur):
    cur.execute('''SELECT * FROM project_artifacts WHERE status NOT IN %s
        AND (deadline<=now() OR review_at<=now() OR (status='blocked' AND updated_at<now()-interval '1 day'))
        ORDER BY importance DESC LIMIT 100 FOR UPDATE SKIP LOCKED''',(TERMINAL,))
    for row in list(cur.fetchall()):
        # One event per review point; snoozing changes the point and permits a later reminder.
        key=f"review:{row['id']}:{row['review_at']}:{row['deadline']}"
        cur.execute('INSERT INTO project_events VALUES (%s,%s,%s,%s,now()) ON CONFLICT DO NOTHING',
                    (key,row['id'],'decision-needed' if row['artifact_type']=='decision' else 'overdue-follow-up',Json({'title':row['title'],'owner':row['owner']})))


def snapshot(cur):
    cur.execute('SELECT * FROM project_artifacts ORDER BY importance DESC,updated_at DESC LIMIT 200')
    rows=[dict(r) for r in cur.fetchall()]
    return {'project':'100print','where_we_are':[r for r in rows if r['artifact_type'] in STRATEGIC][:30],
            'testing':[r for r in rows if r['artifact_type'] in ('hypothesis','experiment','portal_hypothesis') and r['status'] not in TERMINAL][:10],
            'proven':[r for r in rows if r['status']=='validated'][:10],
            'unproven':[r for r in rows if r['artifact_type'] in ('hypothesis','question') and r['status'] not in TERMINAL][:10],
            'next_best_step':next((r['title'] for r in rows if r['artifact_type'] in ('task','experiment') and r['status'] not in TERMINAL),'Собрать подтверждённые данные о спросе, себестоимости и конверсии'),
            'decision_needed':[r for r in rows if r['artifact_type'] in ('decision','question') and r['status'] not in TERMINAL][:5]}


def metrics(cur):
    result={}
    for table,name in [('tasks','tasks'),('project_artifacts','artifacts')]:
        cur.execute(f'SELECT status,count(*) AS n FROM {table} GROUP BY status')
        result[name]={r['status']:r['n'] for r in cur.fetchall()}
    cur.execute("SELECT artifact_type,status,count(*) AS n FROM project_artifacts GROUP BY artifact_type,status")
    result['artifact_types']=[dict(r) for r in cur.fetchall()]
    cur.execute("SELECT avg(extract(epoch FROM finished_at-created_at)) AS seconds,count(*) FILTER(WHERE error IS NOT NULL) AS failures FROM tasks")
    result['response_latency_and_failures']=dict(cur.fetchone())
    cur.execute("SELECT result->'routing'->>'level' AS level,count(*) AS n FROM tasks WHERE result ? 'routing' GROUP BY 1")
    result['council_usage']=[dict(r) for r in cur.fetchall()]
    cur.execute('SELECT provider,avg((hits>0)::int) AS hit_proxy FROM retrieval_observations GROUP BY provider')
    result['retrieval']=[dict(r) for r in cur.fetchall()]
    cur.execute("SELECT to_regclass('telegram_outbox') AS available")
    if cur.fetchone()['available']:
        cur.execute('SELECT state,count(*) AS n FROM telegram_outbox GROUP BY state')
        result['telegram_delivery']={r['state']:r['n'] for r in cur.fetchall()}
    return result


def seed_strategy(cur):
    proposals={
        'business_model':'Гипотеза: портал объединяет спрос на печать и сеть производственных партнёров',
        'portal_hypothesis':'Проверить спрос на единый заказ и прозрачный расчёт печати',
        'mvp_scope':'Проверить MVP: заявка, ручной расчёт, выбор партнёра, контроль исполнения',
        'customer_journey':'Проверить путь: потребность → расчёт → заказ → производство → доставка → повтор',
        'unit_economics':'Измерить выручку, себестоимость, логистику, переделки, CAC и повторные заказы',
        'production_threshold':'Сравнить загрузку и вклад собственной мощности с ценой и качеством партнёров',
        'growth_stage':'Проверить этапы: ручной пилот → повторяемый спрос → автоматизация → масштабирование',
        'metric':'Собирать конверсию заявок, вклад на заказ, сроки, дефекты и долю повторных заказов',
        'risk':'Риск: масштабирование до подтверждения спроса и положительного вклада',
        'experiment':'Провести ограниченный пилот с интервью и измерением экономики заказов',
        'question':'Какие сегменты, цены, мощности и затраты подтверждены первичными данными?'}
    for kind,title in proposals.items():
        put(cur,kind,title,{'evidence_status':'unverified','origin':'issue15 planning baseline'},
            key='strategy-baseline:'+kind,provenance={'source':'issue15','classification':'hypothesis; requires validation'})


def executive_snapshot(value):
    def titles(key):
        return '; '.join(row['title'][:160]+(' ['+str(row['id'])+']' if key=='decision_needed' else '') for row in value[key][:2]) or 'Нет подтверждённых записей'
    return ('100print\nГде мы: '+titles('where_we_are')+
            '\nПроверяем: '+titles('testing')+'\nДоказано: '+titles('proven')+
            '\nНе доказано: '+titles('unproven')+'\nСледующий шаг: '+value['next_best_step'][:250]+
            '\nНужны решения: '+titles('decision_needed'))
