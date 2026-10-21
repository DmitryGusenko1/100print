from . import contracts as c
from .registry import Registry
from .routing import route
from .store import fingerprint

class DepartmentHead:
    def __init__(self, organization, department):
        self.org=organization; self.department=department
        self.definition=organization.registry.departments[department]

    def run(self, context, prefix, inbound=None):
        org=self.org; findings=[]; assignments=[]
        decomposition={'department':self.department,'head':self.definition['head'],
            'context_package':context,'assignments':[
                {'agent':rid,'skill_id':sid} for rid in self.definition['specialists']
                for sid in org.registry.roles[rid]['skills']]}
        org.checkpoint(prefix+'/accepted-and-decomposed',decomposition,lambda:decomposition)
        for rid in self.definition['specialists']:
            role=org.registry.roles[rid]
            for sid in role['skills']:
                findings.append(org.skill(context,sid,rid,prefix+'/specialist/'+sid))
                assignments.append({'agent':rid,'skill_id':sid})
        result=org.ask(prefix+'/result','department',self.department,self.definition['head'],
                       {'context':context,'findings':findings,'inbound':inbound or []},c.POSITION,
                       instructions='Accept context, synthesize specialist findings and inbound departmental results. State constraints, assumptions and risks; identify incompatible goals.')
        return {'departmental_result':result,'assignments':assignments}

class Organization:
    def __init__(self, provider, store, registry=None):
        self.provider=provider; self.store=store; self.registry=registry or Registry()

    def checkpoint(self, key, request, callback, schema=None):
        digest=fingerprint(request)
        cached=self.store.get(self.task_id,key,digest)
        if cached is not None:
            return c.validate(schema,cached) if schema else cached
        result=callback()
        if schema: c.validate(schema,result)
        self.store.put(self.task_id,key,digest,result,{'provider':self.provider.identity,
            'role':request.get('role'),'operation':request.get('operation',key)})
        return result

    def ask(self,key,operation,department,role,data,schema,**extra):
        request={'operation':operation,'department':department,'role':role,'input':data,
                 'output_schema':schema,'provider':self.provider.identity,**extra}
        return self.checkpoint(key,request,lambda:self.provider.respond(request),schema)

    def skill(self,context,sid,rid,key):
        skill=self.registry.skills[sid];role=self.registry.roles[rid]
        if sid not in role['skills'] or role['department'] not in skill['allowed_departments']:
            raise ValueError('Unauthorized skill assignment')
        data=c.validate(skill['input_schema'],{'context':context})
        return self.ask(key,'skill',role['department'],rid,data,skill['output_schema'],skill=skill)

    def handoff(self, source, target, context, source_result):
        base=f'handoff/{source}/{target}'
        package={'source':source,'target':target,'context_package':context,
                 'request':'Review the source proposal against your departmental constraints',
                 'source_result':source_result}
        self.checkpoint(base+'/requested',package,lambda:{'status':'requested',**package})
        response=DepartmentHead(self,target).run(context,base+'/analysis',[source_result])
        receipt={'status':'received','source':source,'target':target,'departmental_result':response['departmental_result']}
        self.checkpoint(base+'/received',receipt,lambda:receipt)
        return response['departmental_result']

    def execute(self, task):
        self.task_id=str(task['id']); p=task.get('payload') or {}
        routing=route(task,self.registry)
        context=c.validate(c.CONTEXT,{'problem':p.get('problem',task['title']),
            'goal':p.get('goal',task['title']), 'constraints':p.get('constraints',[]),
            'criteria':p.get('criteria',['Evidence-supported decision']), 'facts':p.get('facts',[]),
            'assumptions':p.get('assumptions',[])})
        manifest={'routing':routing,'context':context,'provider':self.provider.identity,
                  'catalog':fingerprint({'skills':self.registry.skills,'roles':self.registry.roles,'departments':self.registry.departments})}
        self.checkpoint('manifest',manifest,lambda:manifest)
        level=routing['level'];deps=routing['departments']
        if level=='L1':
            sid=routing['skill_id'] or self.registry.roles[self.registry.departments[deps[0]]['head']]['skills'][0]
            rid=next(r['id'] for r in self.registry.roles.values() if r['kind']=='specialist' and sid in r['skills'])
            result=self.skill(context,sid,rid,'L1/skill')
            return {'routing':routing,'provider':self.provider.identity,'specialist':rid,'skill_id':sid,'result':result}
        if level=='L2':
            result=DepartmentHead(self,deps[0]).run(context,'L2/'+deps[0])
            return {'routing':routing,'provider':self.provider.identity,**result}
        self.checkpoint('round/0',context,lambda:context,c.CONTEXT)
        # All initial positions see the same context and never each other's outputs.
        positions=[DepartmentHead(self,d).run(context,'round/1/'+d)['departmental_result'] for d in deps]
        self.checkpoint('round/1',{'positions':positions},lambda:{'positions':positions})
        reviews=[]
        if level=='L4':
            for source in positions:
                for target in positions:
                    if source['department']==target['department']: continue
                    reviews.append(self.ask('round/2/'+source['department']+'/'+target['department'],
                        'review',source['department'],self.registry.departments[source['department']]['head'],
                        {'context':context,'own':source,'target':target},c.REVIEW,
                        instructions='Challenge the target proposal from your departmental constraints. Require evidence and identify contradictions.'))
        else:
            # Explicit request/receipt protocol; receiving head can use the originating result.
            for target in deps[1:]:
                reviews.append(self.handoff(deps[0],target,context,positions[0]))
        self.checkpoint('round/2',{'reviews':reviews},lambda:{'reviews':reviews})
        conflicts=self.ask('round/3','conflicts','critic','head-critic',
            {'context':context,'positions':positions,'reviews':reviews},c.DISAGREEMENTS,
            instructions='Map conflicting claims and incompatible constraints. Preserve both positions; return no invented disagreement.')
        resolutions=[]; agreements=[]
        seen_conflicts=set()
        for conflict in conflicts['conflicts']:
            if conflict['id'] in seen_conflicts or any(d not in deps for d in conflict['departments']):
                raise ValueError('Invalid conflict identity or department')
            seen_conflicts.add(conflict['id'])
            resolution=self.ask('round/4/'+conflict['id'],'resolve','strategy','chief-of-staff',
                {'context':context,'conflict':conflict,'positions':positions},c.RESOLUTION,
                instructions='Resolve this conflict against round 0 criteria. Name tradeoff and required evidence; flag unresolved if evidence is missing.')
            resolutions.append(resolution)
            for dept in conflict['departments']:
                self.checkpoint('handoff/agreement/'+conflict['id']+'/'+dept, resolution,
                    lambda dept=dept,resolution=resolution:{'status':'agreement_requested','target':dept,'resolution':resolution})
                ack=self.ask('agreement/'+conflict['id']+'/'+dept,'review',dept,
                    self.registry.departments[dept]['head'],
                    {'context':context,'target':{'department':'chief-of-staff','proposal':resolution['decision']},'resolution':resolution},c.REVIEW,
                    instructions='Review the proposed conflict resolution. State remaining objections; do not claim consensus without evidence.')
                agreements.append({'conflict_id':conflict['id'],'department':dept,'review':ack})
                self.checkpoint('handoff/agreement-received/'+conflict['id']+'/'+dept,ack,
                    lambda dept=dept,ack=ack:{'status':'agreement_received','target':dept,'review':ack})
        self.checkpoint('round/4',{'resolutions':resolutions,'agreements':agreements},lambda:{'resolutions':resolutions,'agreements':agreements})
        challenge=self.ask('round/5','challenge','critic','head-critic',
            {'context':context,'positions':positions,'conflicts':conflicts,'resolutions':resolutions,'agreements':agreements},c.CHALLENGE,
            instructions='Attack assumptions, contradictions, failure modes, evidence gaps and alternative hypotheses. Mark blocking challenges.')
        final=self.ask('round/6','synthesis','strategy','chief-of-staff',
            {'context':context,'positions':positions,'reviews':reviews,'conflicts':conflicts,
             'resolutions':resolutions,'agreements':agreements,'challenge':challenge},c.FINAL,
            instructions='Synthesize a decision against round 0 criteria. Address every Critic challenge and unresolved conflict in risks/actions. Distinguish provisional conclusions; do not authorize execution. Include owners, relative deadlines, KPI and next decision point.')
        return {'routing':routing,'provider':self.provider.identity,'final':final,'conflicts':conflicts,
                'resolutions':resolutions,'agreements':agreements,'critic_challenge':challenge,
                'requires_decision':challenge['blocking'] or any(r['unresolved'] for r in resolutions) or any(a['review']['challenges'] for a in agreements)}
