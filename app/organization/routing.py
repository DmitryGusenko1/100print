"""Explicit structured commands take precedence over conservative text routing."""
import re

DEPARTMENTS = ('strategy','marketing','seo','sales','finance','operations','critic')
ALIASES = {'strategy':('strategy','стратег'), 'marketing':('marketing','маркетинг'),
 'seo':('seo','сео','поисков'), 'sales':('sales','продаж'),
 'finance':('finance','финанс','бюджет'), 'operations':('operations','операцион'),
 'critic':('critic','risk','критик','риск')}

class IntentRouter:
    def route(self, task):
        payload=task.get('payload') or {}
        kind=task.get('type','')
        labels=payload.get('labels',[])
        text=' '.join([task.get('title',''),payload.get('problem','')]).lower()
        if kind=='council' or 'council' in labels or re.search(r'\b(council|совет)\b',text): return 'council'
        if kind in ('ai-task',*DEPARTMENTS) or 'ai-task' in labels: return 'business-analysis'
        return 'unsupported'

class DepartmentRouter:
    def route(self, task):
        p=task.get('payload') or {}
        explicit=p.get('departments')
        if explicit is not None:
            if not isinstance(explicit,list) or not explicit or any(d not in DEPARTMENTS for d in explicit):
                raise ValueError('departments must be a nonempty list of known department IDs')
            return list(dict.fromkeys(explicit))
        selected=[d for d in DEPARTMENTS if d==task.get('type') or d in p.get('labels',[])]
        if not selected and p.get('skill_id'):
            selected=[p['skill_id'].split('.')[0]]
        if not selected:
            text=(task.get('title','')+' '+p.get('problem','')).lower()
            selected=[d for d in DEPARTMENTS if any(a in text for a in ALIASES[d])]
        return selected or ['strategy']

class ComplexityRouter:
    def route(self, task, departments, intent):
        explicit=(task.get('payload') or {}).get('level')
        if explicit is not None and explicit not in ('L1','L2','L3','L4'): raise ValueError('Unknown complexity level')
        minimum='L4' if intent=='council' else ('L3' if len(departments)>1 else 'L1')
        if explicit and explicit < minimum: raise ValueError('Level cannot omit required departments/council')
        return explicit or ('L2' if minimum=='L1' and not task.get('payload',{}).get('skill_id') else minimum)


def route(task, registry):
    intent=IntentRouter().route(task)
    if intent=='unsupported': raise ValueError('Not a business task')
    deps=DepartmentRouter().route(task)
    level=ComplexityRouter().route(task,deps,intent)
    if level=='L4': deps=list(DEPARTMENTS)
    sid=task.get('payload',{}).get('skill_id')
    if sid and (sid not in registry.skills or deps[0] not in registry.skills[sid]['allowed_departments']):
        raise ValueError('Unknown or disallowed skill')
    return {'intent':intent,'level':level,'departments':deps,'skill_id':sid}
