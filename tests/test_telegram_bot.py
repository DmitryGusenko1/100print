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
        self.conn = connect()
        self.cur = self.conn.cursor()
        self.cur.execute((ROOT/'config/telegram_schema.sql').read_text())
        self.uid = 910011000001

    def tearDown(self):
        self.conn.rollback()
        self.cur.close()
        self.conn.close()
        self.env.stop()

    def update(self, text, uid=None, chat=-110011, user=110011):
        return {'update_id': uid or self.uid, 'message': {
            'message_id': 1, 'chat': {'id': chat}, 'from': {'id': user}, 'text': text}}

    def rows(self, sql, args=()):
        self.cur.execute(sql, args)
        return self.cur.fetchall()

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
        self.assertIn('production-codex-v1', reply)
        self.assertIn('memory=ceo_orchestrator/shared OK', reply)
        bot.ingest(self.cur, self.update('/new', self.uid+2))
        third = self.rows('SELECT * FROM telegram_inbox WHERE update_id=%s', (self.uid+2,))[0]
        self.assertNotEqual(first['conversation_id'], third['conversation_id'])
        messages = self.rows('SELECT * FROM project_memory WHERE conversation_id=%s', (first['conversation_id'],))
        self.assertEqual(len(messages), 2)

    def test_analysis_routing_context_collection_and_restart(self):
        for i, (text, level) in enumerate([
            ('Проверь метатеги', 'L1'), ('Подготовь отчет по продажам', 'L2'),
            ('Стоит ли снижать цену?', 'L3'), ('Запускаем ли новую типографию?', 'L4')]):
            uid = self.uid+i
            bot.ingest(self.cur, self.update(text, uid))
            bot.ingest(self.cur, self.update(text, uid))
            task = self.rows('SELECT t.* FROM tasks t JOIN telegram_inbox i ON t.id=i.task_id WHERE i.update_id=%s', (uid,))[0]
            self.assertEqual(task['payload']['level'], level)
            self.assertTrue(task['payload']['analytical_protocol'])
            self.assertIn('recent_messages', task['payload']['constraints'][0])
            if level == 'L3': self.assertIn('critic', task['payload']['departments'])
            result = {'provider':'production-codex-v1', 'demonstration':False,
                      'final': {'recommendation': 'Ответ '+str(i)}}
            self.cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s", (Json(result), task['id']))
        bot.collect(self.cur)
        bot.collect(self.cur)
        replies = self.rows('SELECT * FROM telegram_outbox WHERE update_id BETWEEN %s AND %s', (self.uid, self.uid+3))
        self.assertEqual(len(replies), 4)
        self.cur.execute("UPDATE telegram_outbox SET state='sending' WHERE update_id=%s", (self.uid,))
        bot.recover_outbox(self.cur)
        self.assertEqual(self.rows('SELECT state FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]['state'], 'uncertain')

    def test_demo_blocked_and_chunk_deduplication(self):
        bot.ingest(self.cur, self.update('Цена?'))
        self.cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=(SELECT task_id FROM telegram_inbox WHERE update_id=%s)",
                         (Json({'provider':'deterministic', 'demonstration':True, 'final':{'secret':'mock advice'}}), self.uid))
        bot.collect(self.cur)
        reply = self.rows('SELECT text FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]['text']
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
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.rows('SELECT state FROM telegram_outbox WHERE update_id=%s', (self.uid,))[0]['state'], 'uncertain')
