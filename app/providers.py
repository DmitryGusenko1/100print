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
            org=Organization(business_brain(),PostgresStore())
            result=org.execute(task)
            result['provider_metadata']=getattr(org.provider,'metadata',{'provider':org.provider.identity})
            result['model']=result['provider_metadata'].get('model')
            result['demonstration']=org.provider.identity.startswith('deterministic')
            if task.get('payload',{}).get('analytical_protocol'):
                from app.organization import contracts as c
                if 'critic_challenge' not in result:
                    result['critic_challenge']=org.ask('analytical/critic/v1','challenge','critic','head-critic',
                        {'question':task['title'],'result':result},c.CHALLENGE,
                        instructions='Challenge evidence, assumptions, contradictions and risks. Never automatically agree.')
                result['analysis']=org.ask('analytical/v1','analytical','strategy','chief-of-staff',
                    {'question':task['title'],'organization_result':result},c.ANALYTICAL,
                    instructions='Return a concise evidence-based analytical brief, never hidden chain-of-thought. Separate facts and assumptions; list unknowns; compare 2-4 hypotheses with arguments for and against each. Address Critic objections and internal contradictions. Include risks, calibrated confidence, recommendation and evidence that would change it. Never automatically agree with the user.')
                result['demonstration']=result['provider'].startswith('deterministic')
                result['requires_decision']=result.get('requires_decision',False) or result['critic_challenge']['blocking'] or result['analysis']['confidence']<.7
            return result
        raise ValueError(f'No handler registered for task type: {kind}')


def business_brain():
    """An explicit mode prevents a failed production run becoming mock advice."""
    import os
    from app.organization.brain import DeterministicBrainProvider
    mode=os.getenv('CEO_BRAIN_MODE','production')
    if mode=='deterministic': return DeterministicBrainProvider()
    if mode=='production':
        from app.organization.codex import ProductionCodexProvider
        return ProductionCodexProvider(os.getenv('CEO_BRAIN_WORKDIR','/opt/ceo-orchestrator'),
            os.getenv('CEO_BRAIN_MODEL','gpt-6.1-sol'), float(os.getenv('CEO_BRAIN_TIMEOUT','180')))
    raise ValueError('Unknown CEO_BRAIN_MODE')
