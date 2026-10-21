"""Telegram transport checks in a rolled-back transaction on our own PostgreSQL.
No network sends and no committed tasks for the live worker.
"""
import os
import unittest
from unittest.mock import patch
from app.db import connect, ROOT, Json
from app import telegram_bot as bot


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'CEO_TELEGRAM_ALLOWED_CHATS': '-110011',
            'CEO_TELEGRAM_ALLOWED_USERS': '110011'})
        self.env.start()
        self.real_notifications=bot.collect_notifications
        self.notifications=patch.object(bot,'collect_notifications')
        self.notifications.start()
        self.conn = connect()
        self.cur = self.conn.cursor()
        self.cur.execute((ROOT/'config/telegram_schema.sql').read_text())
        self.uid = 910011000001

    def tearDown(self):
        self.conn.rollback()
        self.cur.close()
        self.conn.close()
        self.notifications.stop()
        self.env.stop()

    def update(self, text, uid=None, chat=-110011, user=110011):
        return {'update_id': uid or self.uid, 'message': {
            'message_id': 1, 'chat': {'id': chat}, 'from': {'id': user}, 'text': text}}

    def rows(self, sql, args=()):
        self.cur.execute(sql, args)
        return self.cur.fetchall()

    def test_operational_commands_and_digest_dedup(self):
        from app.intelligence import put, review
        from datetime import datetime, timezone, timedelta
        artifact=put(self.cur,'question','issue15 Telegram review',key='issue15:telegram-review',
                     review_at=datetime.now(timezone.utc)-timedelta(days=1))
        review(self.cur)
        bot.ingest(self.cur,self.update('/snapshot'))
        bot.ingest(self.cur,self.update('/snooze '+str(artifact['id']),self.uid+1))
        bot.ingest(self.cur,self.update('/details '+str(artifact['id']),self.uid+2))
        bot.ingest(self.cur,self.update('/close invalid',self.uid+3))
        self.assertEqual(len(self.rows('SELECT * FROM telegram_inbox WHERE update_id BETWEEN %s AND %s',(self.uid,self.uid+3))),4)
        self.real_notifications(self.cur)
        bot.ingest(self.cur,self.update('/status',self.uid+4))
        self.real_notifications(self.cur)
        self.assertEqual(len(self.rows("SELECT * FROM telegram_outbox WHERE update_id BETWEEN %s AND %s AND kind LIKE 'review-%%'",(self.uid,self.uid+4))),1)
        rows=self.rows("SELECT update_id,kind,count(*) AS n FROM telegram_outbox WHERE kind LIKE 'review-%%' GROUP BY update_id,kind")
        self.assertTrue(all(r['n']==1 for r in rows))

    def test_allowlist_and_empty_updates(self):
        for update in [self.update('x', chat=999), self.update('x', user=999),
                       self.update('   '), {'update_id': self.uid}]:
            bot.ingest(self.cur, update)
        self.assertFalse(self.rows('SELECT * FROM telegram_inbox WHERE update_id=%s', (self.uid,)))
        with patch.dict(os.environ, {'CEO_TELEGRAM_ALLOWED_CHATS':'', 'CEO_TELEGRAM_ALLOWED_USERS':''}):
            self.assertFalse(bot.allowed(self.update('x')['message']))

    def test_commands_resume_new_and_duplicate(self):
        bot.ingest(self.cur, self.update('/start@printbot'))
        bot.ingest(self.cur, self.update('/start@printbot'))
        first = self.rows('SELECT * FROM telegram_inbox WHERE update_id=%s', (self.uid,))[0]
        self.assertIsNone(first['task_id'])
        bot.ingest(self.cur, self.update('/status', self.uid+1))
        second = self.rows('SELECT * FROM telegram_inbox WHERE update_id=%s', (self.uid+1,))[0]
        self.assertEqual(first['conversation_id'], second['conversation_id'])
        reply = self.rows('SELECT text FROM telegram_outbox WHERE update_id=%s', (self.uid+1,))[0]['text']
        self.assertIn('100print — статус', reply)
        self.assertIn('Общая память доступна', reply)
        self.assertIn('В очереди:', reply)
        self.assertIn('Активная задача:', reply)
        self.assertIn('AI-команда:', reply)
        bot.ingest(self.cur, self.update('/new', self.uid+2))
        third = self.rows('SELECT * FROM telegram_inbox WHERE update_id=%s', (self.uid+2,))[0]
        self.assertNotEqual(first['conversation_id'], third['conversation_id'])
        messages = self.rows('SELECT * FROM project_memory WHERE conversation_id=%s', (first['conversation_id'],))
        self.assertEqual(len(messages), 2)

    def test_analysis_routing_context_collection_and_restart(self):
        for i, (text, level) in enumerate([
            ('Проверь метатеги', 'L1'), ('Подготовь отчет по продажам', 'L2'),
            ('Стоит ли снижать цену?', 'L3'), ('Запускаем ли новую типографию?', 'L3')]):
            uid = self.uid+i
            bot.ingest(self.cur, self.update(text, uid))
            bot.ingest(self.cur, self.update(text, uid))
            task = self.rows('SELECT t.* FROM tasks t JOIN telegram_inbox i ON t.id=i.task_id WHERE i.update_id=%s', (uid,))[0]
            self.assertEqual(task['payload']['level'], level)
            self.assertTrue(task['payload']['analytical_protocol'])
            self.assertIn('recent_messages', task['payload']['constraints'][0])
            if level == 'L3': self.assertGreaterEqual(len(task['payload']['departments']),2)
            result = {'provider':'production-codex-v1', 'demonstration':False,
                      'final': {'recommendation': 'Ответ '+str(i)}}
            self.cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s", (Json(result), task['id']))
        bot.collect(self.cur)
        bot.collect(self.cur)
        replies = self.rows('SELECT * FROM telegram_outbox WHERE update_id BETWEEN %s AND %s', (self.uid, self.uid+3))
        self.assertEqual(len(replies), 8)
        self.assertEqual(sum(r['kind']=='ack' for r in replies), 4)
        self.assertEqual(sum(r['kind']=='final' for r in replies), 4)
        self.cur.execute("UPDATE telegram_outbox SET state='sending' WHERE update_id=%s", (self.uid,))
        bot.recover_outbox(self.cur)
        self.assertEqual(self.rows('SELECT state FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]['state'], 'uncertain')

    def test_demo_blocked_and_chunk_deduplication(self):
        bot.ingest(self.cur, self.update('Цена?'))
        self.cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=(SELECT task_id FROM telegram_inbox WHERE update_id=%s)",
                         (Json({'provider':'deterministic', 'demonstration':True, 'final':{'secret':'mock advice'}}), self.uid))
        bot.collect(self.cur)
        reply = self.rows("SELECT text FROM telegram_outbox WHERE update_id=%s AND kind='final'", (self.uid,))[0]['text']
        self.assertNotIn('mock advice', reply)
        self.cur.execute('DELETE FROM telegram_outbox WHERE update_id=%s', (self.uid,))
        text = '😀'*4000
        bot.queue_reply(self.cur, self.uid, text)
        bot.queue_reply(self.cur, self.uid, text)
        parts = self.rows('SELECT text FROM telegram_outbox WHERE update_id=%s ORDER BY part', (self.uid,))
        self.assertEqual(''.join(p['text'] for p in parts), text)
        self.assertTrue(all(len(p['text'].encode('utf-16-le'))//2 <= 4096 for p in parts))

    def delivery_context(self):
        # Keep real SQL, but roll all effects back in tearDown, including commits
        # that normally make the external-send intent durable.
        from unittest.mock import MagicMock
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = self.cur
        return patch.object(bot, 'connect', return_value=connection)

    def test_confirmed_delivery_persists_reply_once(self):
        bot.ingest(self.cur, self.update('/start'))
        with self.delivery_context(), patch.object(bot, 'api', return_value={'message_id': 123}) as send:
            bot.deliver_completed()
            bot.deliver_completed()
        self.assertEqual(send.call_count, 1)
        row = self.rows('SELECT * FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]
        self.assertEqual(row['state'], 'sent')
        self.assertEqual(row['telegram_message_id'], 123)
        replies = self.rows("SELECT * FROM project_memory WHERE dedupe_key=%s", (f'telegram:outbox:{row["id"]}',))
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]['role'], 'assistant')
        self.assertEqual(replies[0]['text'], row['text'])

    def test_ambiguous_send_is_not_retried(self):
        bot.ingest(self.cur, self.update('/start'))
        with self.delivery_context(), patch.object(bot, 'api', side_effect=TimeoutError('ambiguous')) as send:
            bot.deliver_completed()
            bot.recover_outbox(self.cur)
            bot.deliver_completed()
            bot.deliver_completed()
        self.assertEqual(send.call_count, 2)  # Original plus one distinct error notice.
        self.assertEqual(self.rows("SELECT state FROM telegram_outbox WHERE update_id=%s AND kind='final'", (self.uid,))[0]['state'], 'uncertain')

    def test_explicit_rejection_retries_and_saves_receipt(self):
        bot.ingest(self.cur, self.update('/start'))
        with self.delivery_context(), patch.object(bot, 'api', side_effect=bot.TelegramRejected(429, 2)) as send:
            bot.deliver_completed()
            bot.deliver_completed()
        self.assertEqual(send.call_count, 1)
        row = self.rows('SELECT * FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]
        self.assertEqual(row['state'], 'pending')
        self.assertEqual(row['api_response']['error_code'], 429)
        self.cur.execute("UPDATE telegram_outbox SET retry_at=now()-interval '1 second' WHERE update_id=%s", (self.uid,))
        with self.delivery_context(), patch.object(bot, 'api', return_value={'message_id': 124}):
            bot.deliver_completed()
            bot.deliver_completed()
        row = self.rows('SELECT * FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]
        self.assertEqual(row['state'], 'sent')
        self.assertEqual(row['attempts'], 2)
        self.assertEqual(row['api_response']['message_id'], 124)

    def test_memory_failure_cannot_erase_confirmed_receipt(self):
        bot.ingest(self.cur, self.update('/start'))
        with self.delivery_context(), patch.object(bot, 'api', return_value={'message_id': 125}) as send, patch.object(bot.memory, 'append', side_effect=RuntimeError):
            bot.deliver_completed()
            bot.deliver_completed()
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.rows('SELECT state FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]['state'], 'sent')

    def test_bad_request_retries_without_formatter(self):
        bot.ingest(self.cur, self.update('/start'))
        self.cur.execute("UPDATE telegram_outbox SET api_response=%s WHERE update_id=%s", (Json({'ok':False,'error_code':400}),self.uid))
        with self.delivery_context(), patch.object(bot, 'api', return_value={'message_id': 126}) as send:
            bot.deliver_completed()
        self.assertNotIn('parse_mode', send.call_args.args[1])

    def test_intake_audit_keeps_recoverable_accepted_update(self):
        bot.ingest(self.cur, self.update('Что такое тираж?'))
        bot.ingest(self.cur, self.update('private', self.uid+1, chat=999))
        rows = self.rows('SELECT * FROM telegram_update_audit WHERE update_id BETWEEN %s AND %s ORDER BY update_id', (self.uid,self.uid+1))
        self.assertEqual(rows[0]['body'], self.update('Что такое тираж?'))
        self.assertEqual(rows[1]['disposition'], 'allowlist-rejected')
        self.assertEqual(rows[1]['body'], {})

    def test_ack_progress_and_final_are_independent_and_durable(self):
        bot.ingest(self.cur, self.update('Что такое тираж?'))
        task = self.rows('SELECT t.* FROM tasks t JOIN telegram_inbox i ON i.task_id=t.id WHERE i.update_id=%s', (self.uid,))[0]
        self.assertEqual(task['payload']['level'], 'L1')
        self.cur.execute("UPDATE telegram_inbox SET created_at=now()-interval '31 seconds' WHERE update_id=%s", (self.uid,))
        bot.collect(self.cur)
        bot.collect(self.cur)
        rows = self.rows('SELECT kind,text FROM telegram_outbox WHERE update_id=%s ORDER BY id', (self.uid,))
        self.assertEqual([(r['kind'],r['text']) for r in rows], [('ack','Принял. Анализирую.'),('progress','Анализ ещё выполняется.')])
        self.cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s", (Json({'provider':'production-codex-v1','demonstration':False,'result':{'summary':'Тираж — число экземпляров.'}}),task['id']))
        with self.delivery_context(), patch.object(bot,'api',return_value={'message_id':123}) as send:
            for _ in range(5): bot.deliver_completed()
        self.assertEqual(send.call_count,3)
        self.assertIn('Тираж',send.call_args_list[-1].args[1]['text'])

    def test_failed_task_delivers_clear_error_after_ack(self):
        bot.ingest(self.cur, self.update('Вопрос'))
        self.cur.execute("UPDATE tasks SET status='failed' WHERE id=(SELECT task_id FROM telegram_inbox WHERE update_id=%s)",(self.uid,))
        bot.collect(self.cur)
        rows=self.rows("SELECT text FROM telegram_outbox WHERE update_id=%s AND kind='final'",(self.uid,))
        self.assertIn('Анализ не завершён',rows[0]['text'])

    def test_fast_slot_claims_l1_while_business_slot_is_busy(self):
        from app.main import claim
        from app.db import enqueue
        slow = enqueue(self.cur, 'Council slot test', 'echo', {'level':'L4'})
        fast = enqueue(self.cur, 'Fast slot test', 'echo', {'level':'L1'})
        self.cur.execute('UPDATE tasks SET priority=2147483647 WHERE id IN (%s,%s)', (slow,fast))
        normal = claim(self.cur)
        self.assertEqual(str(normal['id']), slow)
        quick = claim(self.cur, fast=True)
        self.assertEqual(str(quick['id']), fast)
        self.assertEqual(self.rows('SELECT status FROM tasks WHERE id=%s',(slow,))[0]['status'], 'processing')

    def test_executive_delivery_preserves_structured_result(self):
        bot.ingest(self.cur, self.update('Разбери подробно идею 100 типографий'))
        result = {'provider': 'production-codex-v1', 'demonstration': False,
                  'routing': {'level': 'L4'}, 'final': {
                      'decision': 'Проверить <пилот> & маржу.',
                      'action_plan': [{'action': f'Шаг {i}', 'owner': 'Директор', 'deadline': 'Неделя'} for i in range(7)],
                      'KPI': ['Маржа']}}
        self.cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=(SELECT task_id FROM telegram_inbox WHERE update_id=%s)", (Json(result), self.uid))
        bot.collect(self.cur)
        stored = self.rows('SELECT t.result FROM tasks t JOIN telegram_inbox i ON i.task_id=t.id WHERE i.update_id=%s', (self.uid,))[0]['result']
        self.assertEqual(stored, result)
        with self.delivery_context(), patch.object(bot, 'api', return_value={'message_id': 123}) as send:
            for _ in range(3):
                bot.deliver_completed()
        body = send.call_args.args[1]
        self.assertEqual(body['parse_mode'], 'HTML')
        self.assertIn('&lt;пилот&gt; &amp; маржу', body['text'])
        self.assertIn('Шаг 6', body['text'])
        self.assertIn('<b>Вывод</b>', body['text'])
        self.assertNotIn('production-codex-v1', body['text'])
