"""Telegram transport adapter. Same database, context and queue as ChatGPT."""
from app.db import connect
from app import project_memory as memory

def receive(chat_id, user_id, message_id, text, *, analyze=False):
    with connect() as conn,conn.cursor() as cur:
        conv=memory.resume(cur,'telegram',str(chat_id))
        cid=str(conv['id'])
        message=memory.append(cur,cid,text,metadata={'telegram_user_id':str(user_id),'telegram_message_id':message_id},request_id=f'telegram:{message_id}')
        result={'conversation_id':cid,'message_id':str(message['id']),
                'context':memory.context(cur,cid,text)}
        if analyze: result['task']=memory.create_task(cur,cid,text,f'telegram:{message_id}')
        return result

def record_reply(conversation_id,message_id,text):
    with connect() as conn,conn.cursor() as cur:
        return memory.append(cur,conversation_id,text,role='assistant',request_id=f'telegram:reply:{message_id}')
