"""Business providers consume role/context/contracts, never select routing or execute tools."""
import json
from abc import ABC, abstractmethod

class BrainProvider(ABC):
    identity = 'abstract'

    @abstractmethod
    def respond(self, request):
        """Return a JSON object matching request.output_schema; no external effects."""

class DeterministicBrainProvider(BrainProvider):
    identity = 'deterministic-v1'

    def respond(self, request):
        op=request['operation']; data=request['input']; dept=request['department']
        if op=='skill':
            return {'summary':request['skill']['name']+': '+data['context']['goal'],
                'recommendations':[request['skill']['purpose'],'Collect baseline evidence before committing resources'],
                'risks':['Inputs are unverified; deterministic analysis is a workflow demonstration'],
                'assumptions':data['context']['assumptions'], 'evidence_gaps':['Validated business metrics and source evidence']}
        if op=='department':
            proposals={'marketing':'Run an acquisition experiment with a bounded budget',
                       'finance':'Require positive contribution and a hard spending cap'}
            return {'department':dept,'proposal':proposals.get(dept,'Validate '+dept+' assumptions with a bounded experiment'),
                'findings':data['findings'],'constraints':data['context']['constraints'],
                'risks':[r for f in data['findings'] for r in f['risks']], 'assumptions':data['context']['assumptions']}
        if op=='review':
            return {'reviewer':dept,'target':data['target']['department'],
                    'challenges':['Provide evidence for: '+data['target']['proposal']]}
        if op=='conflicts':
            positions={p['department']:p for p in data['positions']}
            conflicts=[]
            if 'marketing' in positions and 'finance' in positions:
                conflicts=[{'id':'marketing-finance-budget','departments':['marketing','finance'],
                    'issue':'Acquisition spend versus contribution and cash constraints',
                    'positions':[positions[d]['proposal'] for d in ('marketing','finance')]}]
            return {'conflicts':conflicts}
        if op=='resolve':
            return {'conflict_id':data['conflict']['id'], 'decision':'Only a capped experiment after baseline validation',
                'tradeoff':'Delay growth to preserve cash; scale only after contribution is measured',
                'unresolved':True,'required_evidence':['Actual CAC, contribution margin, cash availability and approved cap']}
        if op=='challenge':
            return {'challenges':['The proposal relies on unverified acquisition and margin assumptions',
                                  'A successful small experiment may not scale'],
                    'evidence_gaps':['Verified baseline metrics','Named accountable business owner'], 'blocking':True}
        if op=='synthesis':
            return {'decision':'Provisional plan: gather evidence before committing spending',
                'why':'Deterministic provider demonstrates the workflow; Critic challenges require validation',
                'alternatives_rejected':['Uncapped campaign spending','Scaling before validating contribution'],
                'risks':data['challenge']['challenges']+['Unresolved conflicts require evidence'],
                'assumptions':data['context']['assumptions']+['Business inputs remain unverified'],
                'action_plan':[{'action':'Collect CAC, margin and capacity baseline; resolve recorded challenges',
                    'owner':'Head of Operations','deadline':'Within 7 days of task acceptance', 'dependencies':['Finance and Marketing validation']}],
                'KPI':['Baseline CAC','Contribution margin','Experiment spending versus approved cap'],
                'next_decision_point':'After baseline evidence and unresolved conflict review; no spending authorized'}
        raise ValueError('Unsupported operation: '+op)

class ProductionBrainProvider(BrainProvider):
    """Strict JSON adapter around an explicitly supplied sandboxed process runner.

    The executable wrapper must accept one JSON request on stdin and emit one JSON
    object on stdout. The adapter fails closed on sandbox, timeout, or schema errors.
    No domain dependency on Codex; another provider may implement respond directly.
    """
    def __init__(self, runner, workdir, identity):
        self.runner=runner; self.workdir=workdir; self.identity=identity
        if not identity or identity.startswith('deterministic'): raise ValueError('Production identity required')

    def respond(self, request):
        response=self.runner.run(json.dumps(request,ensure_ascii=False),self.workdir,timeout=300)
        if not response['ok']: raise RuntimeError('Production brain failed (sandbox/process/timeout)')
        from .contracts import validate
        return validate(request['output_schema'],json.loads(response['stdout']))
