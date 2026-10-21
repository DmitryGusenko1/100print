"""Business contracts and workflows; deterministic tests need no service/API."""
import copy
import json
import unittest
from unittest.mock import patch
from jsonschema import ValidationError
from app.organization import contracts as c
from app.organization.brain import DeterministicBrainProvider, ProductionBrainProvider
from app.organization.engine import Organization
from app.organization.registry import Registry
from app.organization.routing import route
from app.organization.store import MemoryStore
from app.organization.github import parse_issue


def task(level='L4', departments=None):
    return {'id':'00000000-0000-4000-8000-000000000005','type':'ai-task','title':'Plan acquisition',
        'payload':{'level':level,'departments':departments or ['marketing'],
                   'goal':'Validate growth','constraints':['Budget 1000'],'facts':[]}}

class CountingBrain(DeterministicBrainProvider):
    def __init__(self, fail_at=None): self.calls=[]; self.fail_at=fail_at
    def respond(self, request):
        self.calls.append(copy.deepcopy(request))
        if self.fail_at==len(self.calls): raise RuntimeError('Simulated interrupted process')
        return super().respond(request)

class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.store=MemoryStore();self.brain=CountingBrain();self.registry=Registry()
        self.org=Organization(self.brain,self.store,self.registry)

    def test_catalog_and_all_skill_test_cases(self):
        self.assertEqual(len(self.registry.skills),62)
        self.assertEqual(len(self.registry.departments),7)
        self.assertEqual(len(self.registry.roles),29)
        for dept in self.registry.departments.values():
            self.assertEqual(len(dept['specialists']),3)
        for skill in self.registry.skills.values():
            with self.subTest(skill=skill['id']):
                result=self.brain.respond({'operation':'skill','input':skill['test_case']['input'],
                    'skill':skill,'department':skill['allowed_departments'][0]})
                c.validate(skill['output_schema'],result)
                self.assertTrue(result['evidence_gaps'])
                self.assertIn(skill['name'],result['summary'])

    def test_l1_one_specialist(self):
        t=task('L1',['seo']);t['payload']['skill_id']='seo.02'
        result=self.org.execute(t)
        self.assertEqual(result['routing']['level'],'L1')
        self.assertEqual(result['skill_id'],'seo.02')
        self.assertEqual(len(self.brain.calls),1)
        self.assertIn('seo.specialist',result['specialist'])

    def test_l2_head_and_critic(self):
        result=self.org.execute(task('L2',['finance']))
        self.assertEqual(result['departmental_result']['department'],'finance')
        self.assertEqual(len(result['assignments']),1)
        self.assertEqual([c['role'] for c in self.brain.calls],['finance.specialist-1','head-finance','head-critic'])
        self.assertTrue(result['critic_challenge']['blocking'])
        self.assertTrue(result['requires_decision'])

    def test_l3_cross_department_handoff_and_agreement(self):
        result=self.org.execute(task('L3',['marketing','finance']))
        self.assertEqual(result['routing']['level'],'L3')
        keys=[key for (_,key) in self.store.steps]
        self.assertIn('handoff/marketing/finance/requested',keys)
        self.assertIn('handoff/marketing/finance/received',keys)
        inbound=[r for r in self.brain.calls if r['operation']=='department' and r['input']['inbound']]
        self.assertEqual(inbound[0]['input']['inbound'][0]['department'],'marketing')
        self.assertTrue(any('agreement-received' in k for k in keys))
        self.assertEqual(result['conflicts']['conflicts'][0]['departments'],['marketing','finance'])
        self.assertTrue(result['resolutions'][0]['unresolved'])
        self.assertTrue(result['requires_decision'])
        self.assertEqual(len(result['agreements']),2)
        self.assertEqual(self.brain.calls[-1]['input']['agreements'],result['agreements'])

    def test_remaining_head_objections_prevent_implicit_agreement(self):
        class OptimisticBrain(CountingBrain):
            def respond(self, request):
                result=super().respond(request)
                if request['operation']=='resolve': result['unresolved']=False
                if request['operation']=='challenge': result['blocking']=False
                return result
        result=Organization(OptimisticBrain(),MemoryStore()).execute(task('L3',['marketing','finance']))
        self.assertFalse(result['critic_challenge']['blocking'])
        self.assertFalse(result['resolutions'][0]['unresolved'])
        self.assertTrue(result['requires_decision'])

    def test_l4_all_rounds_independence_mutual_critique_and_critic(self):
        result=self.org.execute(task())
        self.assertEqual(len(result['routing']['departments']),7)
        for n in range(7): self.assertIn((task()['id'],f'round/{n}'),self.store.steps)
        heads=[r for r in self.brain.calls if r['operation']=='department']
        self.assertEqual(len(heads),7)
        self.assertTrue(all(not h['input']['inbound'] for h in heads))
        reviews=[r for r in self.brain.calls if r['operation']=='review' and 'own' in r['input']]
        self.assertEqual(len(reviews),42)
        synthesis=self.brain.calls[-1]
        self.assertEqual(synthesis['role'],'chief-of-staff')
        self.assertTrue(synthesis['input']['challenge']['blocking'])
        self.assertTrue(result['critic_challenge']['challenges'])
        c.validate(c.FINAL,result['final'])
        self.assertEqual(result['provider'],'deterministic-v1')

    def test_restart_resumes_checkpoints_without_repeating_completed_calls(self):
        original=CountingBrain(fail_at=12)
        with self.assertRaises(RuntimeError): Organization(original,self.store).execute(task())
        completed=len([r for r in original.calls[:-1]])
        resumed=CountingBrain()
        result=Organization(resumed,self.store).execute(task())
        baseline=CountingBrain();Organization(baseline,MemoryStore()).execute(task())
        self.assertEqual(completed+len(resumed.calls),len(baseline.calls))
        again=CountingBrain();self.assertEqual(Organization(again,self.store).execute(task()),result)
        self.assertEqual(again.calls,[])
        changed=task();changed['payload']['goal']='Changed goal'
        with self.assertRaisesRegex(ValueError,'changed'): Organization(resumed,self.store).execute(changed)

    def test_bad_provider_output_is_not_checkpointed(self):
        class Bad(DeterministicBrainProvider):
            def respond(self,r): return {'made_up':'data'}
        with self.assertRaises(ValidationError): Organization(Bad(),self.store).execute(task('L1'))
        self.assertNotIn((task()['id'],'L1/skill'),self.store.steps)

    def test_invalid_routing_and_skill_permissions(self):
        for payload in ({'level':'L0'},{'level':'L1','departments':['marketing','finance']},
                        {'departments':['unknown']},{'skill_id':'finance.01','departments':['seo']}):
            t=task();t['payload'].update(payload)
            with self.subTest(payload=payload),self.assertRaises(ValueError): route(t,self.registry)
        t=task();t['type']='council';t['payload']['level']='L2'
        with self.assertRaises(ValueError): route(t,self.registry)
        t=task();t['payload']={'skill_id':'marketing.01'}
        self.assertEqual(route(t,self.registry)['level'],'L1')
        t['payload']={};self.assertEqual(route(t,self.registry)['level'],'L2')

    def test_github_labels_json_and_allowlist(self):
        issue={'number':999,'title':'Growth','author':{'login':'DmitryGusenko1'},
               'body':'CEO-AI-TASK\n'+json.dumps({'type':'council','constraints':['Budget 1000']}),'labels':[]}
        parsed=parse_issue(issue);self.assertEqual(parsed['type'],'council')
        self.assertEqual(route(parsed,self.registry)['level'],'L4')
        issue['author']['login']='stranger';self.assertIsNone(parse_issue(issue))
        issue['author']['login']='DmitryGusenko1';issue['body']='Ordinary development issue'
        self.assertIsNone(parse_issue(issue))
        issue['labels']=[{'name':'seo'}]
        self.assertEqual(route(parse_issue(issue),self.registry)['departments'],['seo'])
        issue['body']='CEO-AI-TASK\n{"type":"shell","command":"bad"}'
        with self.assertRaises(ValueError): parse_issue(issue)

    def test_production_adapter_success_and_fail_closed(self):
        class Runner:
            def run(self,*args,**kwargs): return {'ok':True,'stdout':json.dumps({'challenges':[],'evidence_gaps':[],'blocking':False,'alternative_hypotheses':[]})}
        adapter=ProductionBrainProvider(Runner(),'/isolated/workspace','production-test')
        self.assertFalse(adapter.respond({'output_schema':c.CHALLENGE})['blocking'])
        with patch.object(adapter.runner,'run',return_value={'ok':False}):
            with self.assertRaises(RuntimeError): adapter.respond({'output_schema':c.CHALLENGE})
        with patch.object(adapter.runner,'run',return_value={'ok':True,'stdout':'{}'}):
            with self.assertRaises(ValidationError): adapter.respond({'output_schema':c.CHALLENGE})

    def test_domain_has_no_filesystem_network_or_process_side_effects(self):
        # Registry already loaded. Memory execution must not mutate files, spawn a
        # process or connect to anything; deployment DB is tested separately.
        with patch('pathlib.Path.write_text',side_effect=AssertionError('write forbidden')), \
             patch('subprocess.Popen',side_effect=AssertionError('process forbidden')), \
             patch('socket.socket.connect',side_effect=AssertionError('network forbidden')):
            self.org.execute(task())
