#!/usr/bin/env python3
"""Narrow Hermes MCP: tracked project documents/code and a harmless queue probe.

No shell, credentials, conversation history, production writes or plan approval.
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path('/opt/ceo-orchestrator')
sys.path.insert(0, str(ROOT))


def allowed_files():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    prefixes = ('docs/', 'app/', 'scripts/', 'tests/', 'ai-team/roles/', 'ai-team/evidence/')
    return sorted(n for n in names if n and (n.startswith(prefixes) or n == 'README.md')
                  and Path(n).suffix in ('.md', '.py', '.json')
                  and 'secret' not in n.lower())


def project_read(path: str = '') -> dict:
    """List allowed project files, or read one exact listed file (max 96 KiB)."""
    allowed = allowed_files()
    if not path:
        return {'files': allowed}
    target = ROOT / path
    # Reject symlinks including parent components, traversal and untracked runtime.
    if path not in allowed or target.resolve() != target or target.stat().st_size > 98304:
        raise ValueError('File outside project read grant')
    return {'path': path, 'content': target.read_text()}


def executor_probe(action: str = 'status') -> dict:
    """Submit/retrieve a fixed harmless echo probe on the real durable executor.

    This does not authorize functional work. No arbitrary task input is accepted.
    """
    if action == 'submit':
        from app.isolation import require_isolated_execution
        require_isolated_execution()
    from app.db import connect, enqueue
    if action not in ('status', 'submit'):
        raise ValueError('Expected status or submit')
    with connect() as conn, conn.cursor() as cur:
        if action == 'submit':
            enqueue(cur, 'Hermes issue22 executor acceptance', 'echo',
                    {'probe': 'issue22-hermes-access'}, 'hermes-project-access',
                    'issue22-hermes-access-v1')
        cur.execute("SELECT id,status,result FROM tasks WHERE source='hermes-project-access' AND dedupe_key='issue22-hermes-access-v1'")
        row = cur.fetchone()
        return {'task': dict(row, id=str(row['id'])) if row else None,
                'functional_work': 'requires real owner approval and an implemented task route'}


if __name__ == '__main__':
    from mcp.server.fastmcp import FastMCP
    server = FastMCP('ceo-project-access')
    server.tool()(project_read)
    server.tool()(executor_probe)
    server.run(transport='stdio')
