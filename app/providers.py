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
        raise ValueError(f'No handler registered for task type: {kind}')
