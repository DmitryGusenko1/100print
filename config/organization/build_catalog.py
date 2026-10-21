"""Rebuild the checked-in v1 catalog; no runtime generated roles or hidden prompts."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.organization.contracts import SKILL_INPUT, FINDING

CATALOG = {
 'strategy': [
 ('problem framing','Separate symptoms, root problem, decision owner and measurable goal.'),
 ('strategic options','Compare at least three feasible options including maintaining the status quo.'),
 ('prioritization','Rank initiatives by impact, effort, dependencies and confidence; explain tradeoffs.'),
 ('business model analysis','Map customers, value proposition, revenue streams, costs and defensibility.'),
 ('scenario analysis','Compare base, upside and downside scenarios with explicit drivers.'),
 ('decision memo','State the decision, evidence, rejected options and conditions to revisit.')],
 'marketing': [
 ('ICP / segmentation','Define customer segments by needs, buying triggers, ability to pay and exclusions.'),
 ('positioning','Describe target segment, reference category, differentiated promise and proof.'),
 ('offer analysis','Evaluate promise, packaging, price, proof, friction and customer value.'),
 ('channel strategy','Compare acquisition channels by audience fit, cost, lead time and measurement.'),
 ('campaign planning','Specify audience, message, channel, hypothesis, experiment and stop criteria.'),
 ('competitor analysis','Compare alternatives on customer value, pricing and proof; flag missing data.')],
 'seo': [
 ('semantic core planning','Plan seed themes, entities, geography and keyword discovery; do not invent search volumes.'),
 ('keyword clustering','Group supplied keywords by shared intent and target page; flag cannibalization.'),
 ('search intent','Classify informational, navigational, commercial and transactional intent with rationale.'),
 ('content brief','Specify target reader, intent, outline, evidence needed and conversion goal.'),
 ('on-page audit','Check title, H1, headings, relevance, metadata, images and conversion elements.'),
 ('technical SEO checklist','Check crawlability, indexation, canonicalization, sitemap, status codes and performance; mark unverified checks.'),
 ('internal linking','Propose contextual links, anchors, hub pages and orphan-page remediation.'),
 ('competitor SERP analysis','Compare supplied SERP evidence by intent, format, authority and content gaps; require fresh SERP data.')],
 'sales': [
 ('funnel analysis','Map funnel stages and conversion losses; distinguish missing data from zero.'),
 ('sales process','Define stages, entry/exit criteria, handoffs and responsible owners.'),
 ('objection analysis','Group objections, identify root concerns and propose evidence-based responses.'),
 ('offer-to-close logic','Connect buyer pain, offer, proof, commitment, follow-up and closing criteria.'),
 ('KPI / conversion diagnostics','Define denominators, periods and stage conversion metrics; locate largest losses.'),
 ('sales playbook','Provide discovery, qualification, messaging, objections and follow-up steps.')],
 'finance': [
 ('unit economics','Identify revenue per unit, variable costs, contribution margin and missing inputs.'),
 ('CAC/LTV','Define acquisition-cost allocation and cohort lifetime value; state retention and margin assumptions.'),
 ('margin','Separate gross, contribution and operating margin with consistent cost treatment.'),
 ('break-even','Use fixed costs divided by contribution per unit; identify invalid or missing inputs.'),
 ('ROI','Compare incremental benefit to total investment, time horizon and opportunity cost.'),
 ('scenario model','Model base, downside and upside using explicit financial drivers and sensitivities.'),
 ('budget sanity check','Check affordability, cash timing, contingency, caps and approval thresholds.')],
 'operations': [
 ('process decomposition','Break the outcome into inputs, activities, outputs and acceptance criteria.'),
 ('resource plan','Map capacity, skills, tools, cost and resource constraints to deliverables.'),
 ('bottleneck analysis','Identify throughput constraints, queues and critical path; propose verification.'),
 ('execution plan','Sequence deliverables, milestones, dependencies and completion criteria.'),
 ('owner/deadline assignment','Assign accountable role and relative deadline to every action; flag unavailable capacity.'),
 ('risk dependencies','Map dependencies, failure triggers, owners and mitigation actions.')],
 'critic': [
 ('assumption attack','List load-bearing assumptions, counterexamples and falsification experiments.'),
 ('contradiction detection','Compare proposals, facts, constraints and metrics; identify incompatible claims.'),
 ('pre-mortem','Assume the plan failed; identify plausible causes and early warning indicators.'),
 ('failure modes','Rank failure modes by severity, likelihood and detectability; state uncertainty.'),
 ('evidence gap','Separate verified facts from hypotheses and specify missing evidence that changes the decision.'),
 ('alternative hypothesis','Offer competing explanations and experiments that distinguish them.')],
}
SPECIALISTS = {
 'strategy':['Problem Analyst','Options Analyst','Decision Analyst'],
 'marketing':['Audience Analyst','Positioning Analyst','Campaign Planner'],
 'seo':['Keyword Analyst','Content Strategist','Technical SEO Analyst'],
 'sales':['Funnel Analyst','Deal Analyst','Sales Enablement Specialist'],
 'finance':['Unit Economics Analyst','Investment Analyst','Budget Analyst'],
 'operations':['Process Analyst','Resource Planner','Execution Planner'],
 'critic':['Assumption Analyst','Failure Analyst','Evidence Analyst']}

if __name__ == '__main__':
    skills=[]; roles=[{'id':'chief-of-staff','name':'CEO / Chief of Staff','kind':'chief','department':None,'skills':[]}]
    departments=[]
    for dept, entries in CATALOG.items():
        ids=[]
        for index,(name,instruction) in enumerate(entries):
            sid=f'{dept}.{index+1:02d}';ids.append(sid)
            skills.append({'id':sid,'name':name,'version':'1.0.0','purpose':instruction,
                'allowed_departments':[dept], 'input_schema':SKILL_INPUT,'output_schema':FINDING,
                'instructions': instruction+' Use only supplied facts. Label assumptions and evidence gaps. Never fabricate measurements. Return only the required JSON.',
                'test_case':{'input':{'context':{'problem':'Acquisition costs unknown','goal':'Plan a bounded experiment','constraints':['Budget 1000'],'criteria':['Positive contribution'],'facts':[],'assumptions':[]}},
                             'expected':{'summary':name+': requires evidence','recommendations':['Collect baseline data'], 'risks':['Unverified inputs'],'assumptions':[],'evidence_gaps':['Baseline measurements']}}})
        head='head-'+dept
        roles.append({'id':head,'name':'Chief Critic / Risk' if dept=='critic' else 'Head of '+dept.title(), 'kind':'head','department':dept,'skills':ids})
        specialists=[]
        for i,name in enumerate(SPECIALISTS[dept]):
            rid=f'{dept}.specialist-{i+1}';specialists.append(rid)
            roles.append({'id':rid,'name':name,'kind':'specialist','department':dept,'skills':ids[i::3]})
        departments.append({'id':dept,'name':dept.title(),'head':head,'specialists':specialists})
    target=Path(__file__).parent
    for name,data in [('skills',skills),('roles',roles),('departments',departments)]:
        (target/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
