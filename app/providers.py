from abc import ABC, abstractmethod

class BrainProvider(ABC):
    @abstractmethod
    def execute(self, task: dict) -> dict:
        """Return a JSON-serializable result for a durable task."""

class LocalBrainProvider(BrainProvider):
    def execute(self, task):
        import time
        kind = task['type']
        if kind == 'echo':
            time.sleep(min(60, max(0, float(task['payload'].get('delay_seconds',0)))))
            return {'echo':task['payload'], 'agent':'local'}
        if kind == 'follow_up':
            return {'requires_decision':True, 'parent_task':task['payload'].get('parent_task')}
        from app.organization.routing import DEPARTMENTS
        if kind in ('ai-task','council',*DEPARTMENTS):
            from app.organization.engine import Organization
            from app.organization.store import PostgresStore
            return Organization(business_brain(),PostgresStore()).execute(task)
        raise ValueError(f'No handler registered for task type: {kind}')


def business_brain():
    """An explicit mode prevents a failed production run becoming mock advice."""
    import os
    from app.organization.brain import DeterministicBrainProvider, ProductionBrainProvider
    mode=os.getenv('CEO_BRAIN_MODE','deterministic')
    if mode=='deterministic': return DeterministicBrainProvider()
    if mode=='production':
        from app.codex_runner import CodexRunner
        return ProductionBrainProvider(CodexRunner(os.environ['CEO_BRAIN_EXECUTABLE']),
            os.environ['CEO_BRAIN_WORKDIR'],os.environ['CEO_BRAIN_IDENTITY'])
    raise ValueError('Unknown CEO_BRAIN_MODE')
