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


def select_skills(text, registry):
    text=text.lower()
    selected=[sid for sid, spec in registry.skills.items()
            if spec.get('priority') and any(re.search(pattern, text) for pattern in spec['trigger_conditions'])]
    if re.search(r'заказ.*партн|партн.*сво.*производ',text) and 'operations.production' in selected:
        selected.append('finance.pricing')
    composition={'finance.procurement':['operations.production','finance.pricing'],
                 'operations.partnerships':['finance.pricing','strategy.product']}
    for sid in list(selected):
        selected.extend(composition.get(sid,[]))
    return list(dict.fromkeys(selected))


def route(task, registry):
    intent=IntentRouter().route(task)
    if intent=='unsupported': raise ValueError('Not a business task')
    payload=task.get('payload') or {}
    explicit=payload.get('skill_ids')
    if explicit is not None and payload.get('skill_id'): raise ValueError('Use skill_id or skill_ids, not both')
    if explicit is not None and (not isinstance(explicit,list) or not explicit or any(not isinstance(s,str) or s not in registry.skills for s in explicit)):
        raise ValueError('skill_ids must be a nonempty list of known skills')
    chosen=list(dict.fromkeys(explicit or ([payload['skill_id']] if payload.get('skill_id') else select_skills(task.get('title','')+' '+payload.get('problem',''),registry))))
    if any(s not in registry.skills for s in chosen): raise ValueError('Unknown skill')
    deps=DepartmentRouter().route(task)
    if chosen and payload.get('departments') is None:
        deps=list(dict.fromkeys(registry.skills[s]['allowed_departments'][0] for s in chosen))
    if any(not any(d in registry.skills[s]['allowed_departments'] for d in deps) for s in chosen):
        raise ValueError('Disallowed skill composition')
    level=ComplexityRouter().route(task,deps,intent)
    if payload.get('level') is None and chosen==['seo.seo'] and re.search(r'метатег|meta tag',task.get('title','').lower()): level='L1'
    if level=='L1' and len(chosen)>1: raise ValueError('L1 requires one skill')
    if level=='L3' and len(deps)<2: raise ValueError('L3 requires two to four functions')
    if level=='L3' and len(deps)>4: raise ValueError('L3 supports at most four functions; use L4')
    if level=='L4': deps=list(DEPARTMENTS)
    sid=task.get('payload',{}).get('skill_id')
    if sid and (sid not in registry.skills or not any(d in registry.skills[sid]['allowed_departments'] for d in deps)):
        raise ValueError('Unknown or disallowed skill')
    return {'intent':intent,'level':level,'departments':deps,'skill_id':sid or (chosen[0] if len(chosen)==1 else None),'skill_ids':chosen}
