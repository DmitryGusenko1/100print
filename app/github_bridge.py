"""Fixed-repository ChatGPT comment transport backed by project PostgreSQL memory."""
import json
import logging
import re
import subprocess
import time
from app.db import connect, ROOT, enqueue, Json
from app import project_memory as memory

REPO = 'DmitryGusenko1/100print'
ISSUE = 8
OWNER = 'DmitryGusenko1'


def api(path, body=None):
    endpoint = f'repos/{REPO}/issues/{ISSUE}/comments'
    if path not in (endpoint, endpoint + '?per_page=100') or (body is not None and path != endpoint):
        raise ValueError('Bridge endpoint outside allowlist')
    args = ['gh', 'api', path]
    if body is None:
        args += ['--paginate']
    else:
        args += ['--method', 'POST', '--input', '-']
    out = subprocess.run(args, input=json.dumps({'body': body}) if body is not None else None,
                         capture_output=True, text=True, timeout=45, check=True)
    if body is not None:
        return json.loads(out.stdout)
    # Older VPS gh emits consecutive JSON arrays and has no --slurp option.
    decoder = json.JSONDecoder()
    remaining = out.stdout.lstrip()
    pages = []
    while remaining:
        page, end = decoder.raw_decode(remaining)
        pages.append(page)
        remaining = remaining[end:].lstrip()
    return pages


def comments():
    return [c for page in api(f'repos/{REPO}/issues/{ISSUE}/comments?per_page=100') for c in page]


def parse(comment):
    if comment.get('user', {}).get('login') != OWNER:
        return None
    match = re.fullmatch(r'CHATGPT_IN\r?\nsession=([^\r\n]{1,200})\r?\nmessage=([\s\S]{1,30000})', comment.get('body', ''))
    if not match or not match[1].strip() or not match[2].strip():
        return None
    return match[1], match[2]


def migrate():
    memory.migrate()
    with connect() as conn, conn.cursor() as cur:
        cur.execute((ROOT / 'config/github_bridge_schema.sql').read_text())


def ingest(comment):
    parsed = parse(comment)
    if parsed is None:
        return
    session, text = parsed
    key = f'github-bridge:{REPO}:{ISSUE}:{comment["id"]}'
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT 1 FROM chatgpt_bridge_comments WHERE comment_id=%s', (comment['id'],))
        if cur.fetchone():
            return
        conv = memory.resume(cur, 'chatgpt', session)
        cid = str(conv['id'])
        memory.append(cur, cid, text, request_id=key,
                      metadata={'transport': 'github', 'issue': ISSUE, 'comment_id': comment['id']})
        # Control receipts and memory changes commit atomically with intake. They
        # never reach inference, and replay uses the same comment ID as analysis.
        operation, separator, content = text.partition('\n')
        if operation in ('CONTEXT', 'DECISION') and separator and content.strip():
            if operation == 'CONTEXT':
                result = {'operation': operation, 'context': memory.context(cur, cid, content)}
            else:
                item = memory.append(cur, cid, content, kind='decision',
                    metadata={'status': 'accepted', 'transport': 'github',
                              'comment_id': comment['id'], 'source': 'user-reported'},
                    request_id=key + ':decision')
                result = {'operation': operation, 'saved': True, 'memory_id': str(item['id']),
                          'decision_status': 'accepted', 'text': content}
            tid = enqueue(cur, operation + ' bridge receipt', 'echo', {}, 'chatgpt', key)
            cur.execute("UPDATE tasks SET status='done',result=%s,finished_at=now() WHERE id=%s",
                        (Json(json.loads(json.dumps(result, default=str))), tid))
            task = {'task_id': tid}
        else:
            # create_task retrieves server context before enqueueing analysis.
            task = memory.create_task(cur, cid, text, key)
        cur.execute('''INSERT INTO chatgpt_bridge_comments(comment_id,session_id,conversation_id,task_id)
                       VALUES (%s,%s,%s,%s)''', (comment['id'], session, cid, task['task_id']))
    logging.info('Bridge intake comment=%s task=%s', comment['id'], task['task_id'])


def brief(row):
    result = row['result'] or {}
    if result.get('operation') in ('CONTEXT', 'DECISION'):
        return {'status': row['status'], **result}
    analysis = result.get('analysis', {})
    return {'status': row['status'], 'provider': result.get('provider'),
            'model':result.get('model'), 'provider_metadata':result.get('provider_metadata'),
            'positions':[{k:v for k,v in p.items() if k!='findings'} for p in result.get('positions',[])],
            'structured_recommendation':{k:analysis.get(k) for k in ('position','recommendation',
                'arguments_for','arguments_against','objections','evidence','assumptions','change_conditions')},
            'conflicts':result.get('conflicts'),
            'synthesis':result.get('synthesis'),
            'demonstration': result.get('demonstration'), 'routing': result.get('routing'),
            'recommendation': analysis.get('decision'), 'alternatives': analysis.get('hypotheses', []),
            'risks': analysis.get('risks', []), 'critic': result.get('critic_challenge'),
            'confidence': analysis.get('confidence'), 'change_conditions': analysis.get('change_conditions', []),
            'requires_decision': result.get('requires_decision'), 'error': row['error']}


def deliver(existing, test_only=False):
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT b.*,t.status,t.result,t.error FROM chatgpt_bridge_comments b
                       JOIN tasks t ON t.id=b.task_id WHERE b.delivered_at IS NULL
                       AND t.status IN ('done','failed') AND (b.comment_id<0)=%s
                       ORDER BY b.comment_id''', (test_only,))
        rows = cur.fetchall()
    for row in rows:
        marker = f'<!-- ceo-chatgpt-result:{row["task_id"]} -->'
        found = next((c for c in existing if marker in c.get('body', '') and c.get('user', {}).get('login') == OWNER), None)
        # Compact bounded JSON remains parseable even for a verbose production provider.
        summary = brief(row)
        summary['request_comment_id'] = row['comment_id']
        encoded = json.dumps(summary, ensure_ascii=False, separators=(',', ':'))
        if len(encoded) > 45000:
            summary = {'status': row['status'], 'truncated': True,
                       'request_comment_id': row['comment_id'],
                       'operation': summary.get('operation'),
                       'provider':summary.get('provider'), 'model':summary.get('model'),
                       'demonstration':summary.get('demonstration'), 'confidence':summary.get('confidence'),
                       'provider_metadata':summary.get('provider_metadata'),
                       'recommendation': str(summary.get('recommendation', ''))[:4000],
                       'detail': 'Full result and artifacts in project memory by task_id'}
            encoded = json.dumps(summary, ensure_ascii=False)
        body = f'CHATGPT_OUT\nsession={row["session_id"]}\ntask_id={row["task_id"]}\nresult={encoded}\n{marker}'
        if found is None:
            found = api(f'repos/{REPO}/issues/{ISSUE}/comments', body)
            existing.append(found)
        with connect() as conn, conn.cursor() as cur:
            memory.append(cur, str(row['conversation_id']), body, role='assistant',
                          request_id=f'bridge-out:{row["task_id"]}', task_id=str(row['task_id']),
                          metadata={'transport': 'github', 'comment_id': found['id']})
            cur.execute('''UPDATE chatgpt_bridge_comments SET delivered_at=now(),reply_comment_id=%s
                           WHERE comment_id=%s''', (found['id'], row['comment_id']))
        logging.info('Bridge delivered task=%s reply=%s', row['task_id'], found['id'])


def poll():
    # Lock includes remote delivery: only one process may POST replies at a time.
    with connect() as lock, lock.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(818008) AS locked")
        if not cur.fetchone()['locked']:
            return
        try:
            existing = comments()
            cur.execute('SELECT last_comment_id FROM chatgpt_bridge_state WHERE issue_number=%s', (ISSUE,))
            last = cur.fetchone()['last_comment_id']
            for comment in sorted(existing, key=lambda c: c['id']):
                if comment['id'] <= last:
                    continue
                ingest(comment)
                # Intake committed first. Crash before cursor update safely replays by comment_id.
                cur.execute('UPDATE chatgpt_bridge_state SET last_comment_id=%s WHERE issue_number=%s', (comment['id'], ISSUE))
                lock.commit()
            deliver(existing)
        finally:
            cur.execute('SELECT pg_advisory_unlock(818008)')


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    migrate()
    logging.info('ChatGPT bridge active: %s#%s', REPO, ISSUE)
    while True:
        try:
            poll()
        except Exception:
            logging.exception('Bridge poll failed; durable work retained for retry')
        time.sleep(10)


if __name__ == '__main__':
    main()
