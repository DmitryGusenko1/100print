import json
from pathlib import Path
from jsonschema import Draft202012Validator
from .contracts import validate

CATALOG = Path(__file__).resolve().parents[2] / 'config/organization'

class Registry:
    def __init__(self, root=CATALOG):
        self.preset = json.loads((root/'100print.json').read_text())
        self.skills = {s['id']: s for s in json.loads((root/'skills.json').read_text())}
        self.roles = {r['id']: r for r in json.loads((root/'roles.json').read_text())}
        self.departments = {d['id']: d for d in json.loads((root/'departments.json').read_text())}
        for skill in self.skills.values():
            for key in ('id','name','version','purpose','allowed_departments','instructions','test_case'):
                if not skill[key]: raise ValueError('Incomplete skill: '+key)
            if skill.get('priority'):
                for key in ('trigger_conditions','required_inputs','analysis_checklist','output_contract','kpis','risks_failure_modes','escalation_rules'):
                    if not skill.get(key): raise ValueError('Incomplete specialist: '+key)
            for key in ('input_schema','output_schema'):
                Draft202012Validator.check_schema(skill[key])
            validate(skill['input_schema'],skill['test_case']['input'])
            validate(skill['output_schema'],skill['test_case']['expected'])
        for role in self.roles.values():
            for sid in role['skills']:
                if role['department'] not in self.skills[sid]['allowed_departments']:
                    raise ValueError('Skill not allowed for role')

    def sync(self, cur):
        from psycopg2.extras import Json
        for dept in self.departments.values():
            cur.execute('INSERT INTO departments(id,name) VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET name=excluded.name', (dept['id'],dept['name']))
        for role in self.roles.values():
            cur.execute('INSERT INTO agents(id,department_id) VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET department_id=excluded.department_id', (role['id'],role['department']))
            cur.execute('INSERT INTO organization_roles(id,definition) VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET definition=excluded.definition', (role['id'],Json(role)))
        for skill in self.skills.values():
            cur.execute('INSERT INTO skills_registry(id,version,definition) VALUES (%s,%s,%s) ON CONFLICT(id,version) DO UPDATE SET definition=excluded.definition', (skill['id'],skill['version'],Json(skill)))
