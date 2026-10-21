import json
import unittest
from app.organization.registry import Registry, CATALOG
from app.organization.routing import route
from app.organization.engine import Organization
from app.organization.store import MemoryStore
from app.project_memory import routing
from tests.test_organization import CountingBrain

class SpecialistTests(unittest.TestCase):
    def test_ten_business_scenarios_reach_specialists_and_memory(self):
        for i,ex in enumerate(json.loads((CATALOG/'examples.json').read_text())):
            with self.subTest(question=ex['question']):
                t={'id':str(i),'type':'ai-task','title':ex['question'],'payload':{}}
                brain=CountingBrain(); store=MemoryStore()
                result=Organization(brain,store).execute(t)
                self.assertNotEqual(result['routing']['level'],'L4')
                called={r['skill']['id'] for r in brain.calls if r['operation']=='skill'}
                self.assertTrue(set(ex['skills'])<=called,called)
                self.assertTrue(all(r['operation']!='skill' or r['skill']['id'] in result['routing']['skill_ids'] for r in brain.calls))
                self.assertTrue(store.steps)
                if result['routing']['level']=='L2':
                    head=next(r for r in brain.calls if r['operation']=='department')
                    self.assertTrue(head['input']['findings'])
                    self.assertEqual(brain.calls[-1]['operation'],'challenge')
                self.assertTrue(all('constraints' in r['input']['context'] for r in brain.calls if r['operation']=='skill'))
                self.assertEqual(routing(ex['question'])[0],result['routing']['level'])
    def test_explicit_composition_and_permissions(self):
        registry=Registry()
        for payload in ({'skill_ids':[]},{'skill_ids':['unknown']},{'skill_ids':['finance.pricing'],'departments':['seo']},
                        {'skill_ids':['strategy.product','strategy.analytics'],'level':'L1'}):
            with self.subTest(payload=payload),self.assertRaises(ValueError):
                route({'type':'ai-task','title':'x','payload':payload},registry)
        selected=route({'type':'ai-task','title':'x','payload':{'skill_ids':['finance.pricing','marketing.growth']}},registry)
        self.assertEqual(selected['level'],'L3')
    def test_all_specialist_specs_complete_and_l1_callable(self):
        registry=Registry()
        pack=[s for s in registry.skills.values() if s.get('priority')]
        self.assertEqual(sum(s['priority']=='first' for s in pack),8)
        self.assertEqual(len(pack),17)
        for s in pack:
            brain=CountingBrain()
            result=Organization(brain,MemoryStore()).execute({'id':s['id'],'type':'ai-task','title':'Explicit isolated analysis','payload':{'skill_id':s['id'],'level':'L1'}})
            self.assertEqual(len(brain.calls),1)
            self.assertEqual(result['skill_id'],s['id'])
