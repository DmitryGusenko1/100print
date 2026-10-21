"""Optional allowlisted Telegram transport over the same durable project memory."""
import json
import os
import time
import urllib.request
from app.db import connect
from app.telegram_memory import receive, record_reply


def api(method,body):
    token=os.environ['CEO_TELEGRAM_TOKEN']
    request=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,
        data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=40) as response:
        result=json.load(response)
    if not result.get('ok'): raise RuntimeError('Telegram API rejected request')
    return result['result']


def deliver_completed():
    with connect() as conn,conn.cursor() as cur:
        cur.execute('''SELECT t.id,t.result,c.id AS conversation_id,c.external_session_id
            FROM project_analysis_tasks p JOIN tasks t ON t.id=p.task_id
            JOIN project_conversations c ON c.id=p.conversation_id
            WHERE c.source='telegram' AND t.status='done'
            AND NOT EXISTS (SELECT 1 FROM project_memory m WHERE m.conversation_id=c.id
                AND m.kind='message' AND m.dedupe_key='telegram:reply:analysis:'||t.id::text)
            ORDER BY t.created_at LIMIT 10''')
        pending=list(cur.fetchall())
    allowed=set(os.environ['CEO_TELEGRAM_ALLOWED_CHATS'].split(','))
    for row in pending:
        if row['external_session_id'] not in allowed: continue
        result=row['result']
        text=('DEMONSTRATION — не бизнес-консультация\n' if result.get('demonstration') else '')
        text+='task_id='+str(row['id'])+'\n'+json.dumps(result.get('analysis',result.get('final',result)),ensure_ascii=False)
        text=text[:4000]
        api('sendMessage',{'chat_id':row['external_session_id'],'text':text})
        record_reply(str(row['conversation_id']),'analysis:'+str(row['id']),text)


def main():
    allowed=set(os.environ.get('CEO_TELEGRAM_ALLOWED_CHATS','').split(','))-{''}
    if not allowed: raise RuntimeError('Explicit CEO_TELEGRAM_ALLOWED_CHATS required')
    with connect() as conn,conn.cursor() as cur:
        cur.execute("INSERT INTO scheduler_state(name,last_run) VALUES ('telegram-offset',to_timestamp(0)) ON CONFLICT DO NOTHING")
    while True:
        with connect() as conn,conn.cursor() as cur:
            cur.execute("SELECT extract(epoch FROM last_run)::bigint AS offset FROM scheduler_state WHERE name='telegram-offset'")
            offset=cur.fetchone()['offset']
        try:
            updates=api('getUpdates',{'offset':offset,'timeout':10,'allowed_updates':['message']})
            for update in updates:
                message=update.get('message',{})
                if str(message.get('chat',{}).get('id')) in allowed and message.get('text'):
                    received=receive(message['chat']['id'],message.get('from',{}).get('id',0),
                        message['message_id'],message['text'],analyze=True)
                    ack='Записано. Анализ выполняется: '+received['task']['task_id']
                    api('sendMessage',{'chat_id':message['chat']['id'],'text':ack})
                    record_reply(received['conversation_id'],message['message_id'],ack)
                with connect() as conn,conn.cursor() as cur:
                    cur.execute("UPDATE scheduler_state SET last_run=to_timestamp(%s) WHERE name='telegram-offset'",(update['update_id']+1,))
            deliver_completed()
        except Exception:
            # Avoid logging request URLs, which contain the token.
            import logging
            logging.warning('Telegram transport failed; durable offset and analysis tasks retained')
            time.sleep(5)

if __name__=='__main__': main()
