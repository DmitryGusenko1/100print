#!/usr/bin/env python3
"""Read-only verification of issue #9's real bridge/API analysis and durable artifacts."""
import json
from pathlib import Path
import sys
import os
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import ROOT, connect
from app.github_bridge import comments
from dotenv import load_dotenv


def verify():
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT t.*,b.reply_comment_id,b.delivered_at FROM tasks t
            JOIN chatgpt_bridge_comments b ON b.task_id=t.id
            WHERE b.session_id='production-e2e' ORDER BY t.created_at DESC LIMIT 1''')
        task = cur.fetchone()
        assert task and task['status'] == 'done', 'Production E2E has not completed'
        result = task['result']
        assert result['provider'] == 'production-codex-v1'
        assert result['demonstration'] is False
        assert result['model'] and result['provider_metadata']['model'] == result['model']
        assert 0 < result['analysis']['confidence'] <= 1
        positions = result['positions']
        departments = {p['department'] for p in positions}
        assert {'finance', 'marketing', 'sales'} <= departments
        assert all(p['position'] and p['recommendation'] for p in positions)
        # Aligned recommendations must not be turned into fabricated department conflicts.
        # Check the economic tradeoff even when the conflict map is honestly empty.
        indexed={p['department']:p for p in positions}
        assert indexed['finance']['risks']
        assert indexed['marketing']['arguments_for'] and indexed['sales']['arguments_for']
        tradeoff=json.dumps({'analysis':result['analysis'], 'final':result['final']},ensure_ascii=False).lower()
        assert ('марж' in tradeoff or 'прибыл' in tradeoff) and 'рост' in tradeoff
        assert result['analysis']['contradictions'], 'Missing economic tradeoff'
        assert result['critic_challenge']['challenges']
        assert result['critic_challenge']['alternative_hypotheses']
        assert result['analysis']['recommendation'] and result['final']['action_plan']
        cur.execute('SELECT step_key,fingerprint,result,metadata FROM organization_steps WHERE task_id=%s', (task['id'],))
        steps = {r['step_key']: dict(r) for r in cur.fetchall()}
        assert {f'round/{i}' for i in range(7)} <= steps.keys()
        assert 'analytical/v1' in steps
        calls = [r for r in steps.values() if r['metadata'].get('role')]
        assert calls and all(r['metadata']['model'] == result['model'] and
                             r['metadata']['provider'] == result['provider'] for r in calls)
        cur.execute('SELECT count(*) AS n FROM project_memory WHERE task_id=%s', (task['id'],))
        memory_count = cur.fetchone()['n']
        assert memory_count > 10
    snapshot = ROOT / 'data/issue9-before-restart.json'
    if snapshot.exists():
        for old in json.loads(snapshot.read_text()):
            assert all(steps[old['step_key']][k] == v for k, v in old.items())
    assert task['delivered_at'] and task['reply_comment_id'], 'Reply not yet delivered'
    reply = next(c for c in comments() if c['id'] == task['reply_comment_id'])
    assert f'task_id={task["id"]}' in reply['body'] and reply['body'].startswith('CHATGPT_OUT\n')
    brief = json.loads(reply['body'].split('\nresult=', 1)[1].split('\n<!--', 1)[0])
    assert brief['provider'] == result['provider'] and brief['demonstration'] is False
    assert brief['confidence'] > 0 and len(brief['positions']) >= 3
    assert brief['structured_recommendation']['recommendation']
    # Exercise the actual localhost #6 API, using only this project's token.
    load_dotenv(ROOT / 'config/chatgpt.env')
    request = urllib.request.Request('http://127.0.0.1:8096/tools/get_task_result',
        data=json.dumps({'task_id': str(task['id'])}).encode(),
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + os.environ['CEO_CHATGPT_TOKEN']})
    with urllib.request.urlopen(request, timeout=15) as response:
        api_result = json.load(response)
    assert api_result['result'] == result
    evidence = {'task_id': str(task['id']), 'provider': result['provider'], 'model': result['model'],
                'demonstration': False, 'confidence': result['analysis']['confidence'],
                'departments': sorted(departments), 'checkpoints': len(steps),
                'production_calls': len(calls), 'memory_artifacts': memory_count,
                'attempts': task['attempts'], 'api_result_verified': True,
                'reply_url': reply['html_url']}
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify()
