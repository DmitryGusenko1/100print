"""Live PostgreSQL and HTTP/MCP contract checks, only ceo_orchestrator."""
import json
import os
import time
import unittest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.chatgpt_api import app
from app.db import connect, Json
from app import project_memory as memory
from app.providers import LocalBrainProvider
from app.organization.brain import DeterministicBrainProvider
from app.telegram_memory import receive, record_reply

class ChatGPTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['CEO_CHATGPT_TOKEN']='integration-test-token-'+'x'*40
        memory.migrate()
        cls.client=TestClient(app,base_url="http://localhost")
        cls.client.__enter__()
        cls.headers={'Authorization':'Bearer '+os.environ['CEO_CHATGPT_TOKEN']}

    @classmethod
    def tearDownClass(cls): cls.client.__exit__(None,None,None)

    def call(self,method,**data):
        response=self.client.post('/tools/'+method,json=data,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def new(self,source='chatgpt'):
        return self.call('create_or_resume_conversation',source=source,external_session_id='test-'+str(uuid.uuid4()))['id']

    def test_conversation_message_retrieval_and_idempotency(self):
        external=str(uuid.uuid4())
        a=self.call('create_or_resume_conversation',external_session_id=external)
        b=self.call('create_or_resume_conversation',external_session_id=external)
        self.assertEqual(a['id'],b['id'])
        cid=a['id']; request=str(uuid.uuid4())
        first=self.call('append_message',conversation_id=cid,text='Привет',request_id=request)
        again=self.call('append_message',conversation_id=cid,text='Привет',request_id=request)
        self.assertEqual(first['id'],again['id'])
        self.call('append_message',conversation_id=cid,text='Ответ',role='assistant',request_id=str(uuid.uuid4()))
        marker='контекст'+uuid.uuid4().hex
        self.call('append_decision',conversation_id=cid,text=marker+' стратегия позиционирования',request_id=str(uuid.uuid4()))
        package=self.call('get_relevant_context',conversation_id=self.new(),query=marker)
        self.assertTrue(any(marker in r['text'] for r in package['relevant_memory']))
        self.assertLessEqual(len(json.dumps(package,ensure_ascii=False)),16000)
        semantic='semantic'+uuid.uuid4().hex
        decision=self.call('append_decision',conversation_id=cid,text=semantic+' скидка для клиента',request_id=str(uuid.uuid4()),importance=1,confidence=1)
        found=self.call('search_memory',query='pricing')
        self.assertTrue(any(r['id']==decision['id'] for r in found))
        compact=self.call('get_relevant_context',conversation_id=cid,query='pricing',max_chars=2000)
        self.assertLessEqual(len(json.dumps(compact,ensure_ascii=False)),2000)

    def test_telegram_shared_memory(self):
        marker='общаяпамять'+uuid.uuid4().hex
        incoming=receive(-123456789,123,int(time.time_ns()),marker)
        reply=record_reply(incoming['conversation_id'],uuid.uuid4().hex,marker+' ответ')
        found=self.call('search_memory',query=marker)
        self.assertTrue(any(r['source']=='telegram' and r['id']==str(reply['id']) for r in found))
        self.call('append_decision',conversation_id=self.new(),text=marker+' решение',request_id=str(uuid.uuid4()))
        incoming=receive(-123456789,123,int(time.time_ns()),marker)
        self.assertTrue(any(r['source']=='chatgpt' for r in incoming['context']['relevant_memory']))

    def test_analysis_queue_all_routes_and_result(self):
        for question,level,departments in [
            ('Проверь метатеги','L1',{'seo'}),
            ('Подготовь отчет по продажам','L2',{'sales'}),
            ('Как нам позиционироваться?','L3',{'strategy','marketing','critic'}),
            ('Стоит ли снижать цену?','L3',{'sales','finance','marketing','critic'}),
            ('Как выйти в топ Google?','L3',{'seo','marketing','critic'}),
            ('Куда вложить 5 млн?','L3',{'finance','strategy','critic'}),
            ('Запускаем ли новую типографию?','L4',set())]:
            with self.subTest(question=question):
                cid=self.new();key=str(uuid.uuid4())
                # Prevent the daemon racing this test's provider execution.
                with connect() as conn,conn.cursor() as cur:
                    created=memory.create_task(cur,cid,question,key)
                    tid=created['task_id']
                    cur.execute("UPDATE tasks SET status='waiting' WHERE id=%s",(tid,))
                again=self.call('create_analysis_task',conversation_id=cid,text=question,request_id=key)
                self.assertEqual(tid,again['task_id']);self.assertEqual(created['level'],level)
                self.assertEqual(set(created['departments']),departments)
                with connect() as conn,conn.cursor() as cur:
                    cur.execute('SELECT * FROM tasks WHERE id=%s',(tid,));task=dict(cur.fetchone())
                with patch('app.providers.business_brain',return_value=DeterministicBrainProvider()):
                    result=LocalBrainProvider().execute(task)
                self.assertTrue(result['demonstration'])
                self.assertIn('change_conditions',result['analysis'])
                self.assertTrue(result['critic_challenge'])
                if 'finance' in departments and 'marketing' in departments:
                    self.assertTrue(result['conflicts']['conflicts'])
                with connect() as conn,conn.cursor() as cur:
                    memory.persist_analysis(cur,task,result)
                    cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s",(Json(result),tid))
                read=self.call('get_task_result',task_id=tid)
                self.assertEqual(read['result'],result)
                self.assertEqual(self.call('get_task_status',task_id=tid)['status'],'done')
                # Re-reading opens a fresh database connection on each request.
                self.assertEqual(self.call('get_task_result',task_id=tid)['result'],result)

    def test_auth_scope_validation(self):
        self.assertEqual(self.client.get('/health').status_code,401)
        for body in ({'project_id':'foreign','query':'x'},{'query':'x','limit':10000},{'query':'x','sql':'bad'}):
            self.assertEqual(self.client.post('/tools/search_memory',json=body,headers=self.headers).status_code,422)
        self.assertEqual(self.client.post('/tools/get_task_result',json={'task_id':str(uuid.uuid4())},headers=self.headers).status_code,404)
        self.assertEqual(self.client.post('/tools/append_message',json={'conversation_id':'bad','text':'x','request_id':'r'},headers=self.headers).status_code,422)

    def test_mcp_initialize_and_tools(self):
        headers={**self.headers,'Accept':'application/json, text/event-stream'}
        init=self.client.post('/mcp/',json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'test','version':'1'}}},headers=headers)
        self.assertEqual(init.status_code,200,init.text)
        listing=self.client.post('/mcp/',json={'jsonrpc':'2.0','id':2,'method':'tools/list'},headers=headers)
        self.assertEqual(listing.status_code,200,listing.text)
        self.assertEqual(len(listing.json()['result']['tools']),9)
        call=self.client.post('/mcp/',json={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'create_or_resume_conversation','arguments':{'input':{'external_session_id':str(uuid.uuid4())}}}},headers=headers)
        self.assertEqual(call.status_code,200,call.text)
        self.assertFalse(call.json()['result'].get('isError',False),call.text)
