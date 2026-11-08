"""Project-venv startup interlock. No host configuration changes.

Temporary containment only: the shared identity can replace this Python code.
Telegram gateway transport and its status commands continue; agentic model turns
are paused because its Codex app-server currently has native host tool access.
"""
import json


def deny(*args, **kwargs):
    raise PermissionError('issue23: runtime isolation required; agent execution paused')


def deny_tool(*args, **kwargs):
    return json.dumps({'error': 'issue23_isolation_required', 'executed': False})


def install():
    import model_tools
    model_tools.handle_function_call = deny_tool
    # Include direct job execution, external-worker payloads and in-process ticks.
    import cron.scheduler as scheduler
    import cron.scheduler_tick as scheduler_tick
    scheduler_tick.tick = lambda *a, **kw: 0
    scheduler.tick = scheduler_tick.tick
    for name in ('run_job', 'run_one_job', '_run_one_job_body', '_run_external_worker_payload'):
        if not hasattr(scheduler, name):
            raise RuntimeError('Hermes scheduler interface changed; containment cannot start')
        setattr(scheduler, name, deny)
    from agent.transports.codex_app_server import CodexAppServerClient
    CodexAppServerClient.__init__ = deny


install()
