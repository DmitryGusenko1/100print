"""Explicit service crash test. Restarts ONLY our own ceo-orchestrator process."""
import os
import signal
import subprocess
import time
import unittest
import uuid
from pathlib import Path
import httpx
from dotenv import dotenv_values
from app.db import connect, Json
from unittest.mock import patch
from app.providers import LocalBrainProvider
from app.organization.brain import DeterministicBrainProvider
from app import project_memory as memory

class ChatGPTRestartTests(unittest.TestCase):
    def test_service_restart_preserves_conversation_and_task(self):
        headers={'Authorization':'Bearer '+dotenv_values('config/chatgpt.env')['CEO_CHATGPT_TOKEN']}
        def call(method,**body):
            response=httpx.post('http://127.0.0.1:8096/tools/'+method,json=body,headers=headers,timeout=10)
            response.raise_for_status()
            return response.json()
        marker='restart'+uuid.uuid4().hex
        conv=call('create_or_resume_conversation',external_session_id=marker)
        cid=conv['id']
        call('append_message',conversation_id=cid,text=marker,request_id=marker)
        call('append_decision',conversation_id=cid,text=marker+' сохранить память',request_id=marker)
        with connect() as conn,conn.cursor() as cur:
            task=memory.create_task(cur,cid,'Как нам позиционироваться? '+marker,marker)
            cur.execute("UPDATE tasks SET status='waiting' WHERE id=%s",(task['task_id'],))
        pid=int(subprocess.check_output(['systemctl','show','ceo-orchestrator.service','-p','MainPID','--value']))
        self.assertEqual(Path(f'/proc/{pid}').stat().st_uid,os.getuid())
        os.kill(pid,signal.SIGKILL)
        deadline=time.monotonic()+60
        while True:
            try:
                status=call('get_task_status',task_id=task['task_id'])
                self.assertEqual(status['status'],'waiting')
                break
            except (httpx.HTTPError,ConnectionError):
                if time.monotonic()>deadline: raise
                time.sleep(.5)
        resumed=call('create_or_resume_conversation',external_session_id=marker)
        self.assertEqual(resumed['id'],cid)
        self.assertTrue(any(r['text'].startswith(marker) for r in call('search_memory',query=marker)))
        self.assertTrue(any(t['id']==task['task_id'] for t in call('get_relevant_context',conversation_id=cid,query=marker)['active_tasks']))
        # The live worker stays production. Fixture inference is explicitly mocked in-process.
        with connect() as conn,conn.cursor() as cur:
            cur.execute('SELECT * FROM tasks WHERE id=%s',(task['task_id'],))
            queued=dict(cur.fetchone())
        with patch('app.providers.business_brain',return_value=DeterministicBrainProvider()):
            analytical_result=LocalBrainProvider().execute(queued)
        with connect() as conn,conn.cursor() as cur:
            memory.persist_analysis(cur,queued,analytical_result)
            cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s",
                        (Json(analytical_result),task['task_id']))
        result=call('get_task_result',task_id=task['task_id'])
        self.assertEqual(result['status'],'done',result)
        self.assertIn('analysis',result['result'])
        self.assertTrue(result['result']['demonstration'])
        with connect() as conn,conn.cursor() as cur:
            cur.execute('SELECT DISTINCT kind FROM project_memory WHERE task_id=%s',(task['task_id'],))
            kinds={r['kind'] for r in cur.fetchall()}
            self.assertTrue({'specialist_result','decision','action_item','council_round'}<=kinds)
