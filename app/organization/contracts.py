"""Versioned JSON contracts shared by skills, heads and interchangeable providers."""
from jsonschema import Draft202012Validator


def obj(properties, required=None):
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required,
            'additionalProperties': False}

TEXT = {'type': 'string', 'minLength': 1}
TEXTS = {'type': 'array', 'items': TEXT}
CONTEXT = obj({'problem': TEXT, 'goal': TEXT, 'constraints': TEXTS,
               'criteria': TEXTS, 'facts': TEXTS, 'assumptions': TEXTS})
SKILL_INPUT = obj({'context': CONTEXT})
FINDING = obj({'summary': TEXT, 'recommendations': TEXTS, 'risks': TEXTS,
               'assumptions': TEXTS, 'evidence_gaps': TEXTS})
POSITION = obj({'department': TEXT, 'proposal': TEXT, 'findings': {'type': 'array', 'items': FINDING},
                'constraints': TEXTS, 'risks': TEXTS, 'assumptions': TEXTS})
CONFLICT = obj({'id': TEXT, 'departments': {'type': 'array', 'items': TEXT, 'minItems': 2},
                'issue': TEXT, 'positions': TEXTS})
DISAGREEMENTS = obj({'conflicts': {'type': 'array', 'items': CONFLICT}})
RESOLUTION = obj({'conflict_id': TEXT, 'decision': TEXT, 'tradeoff': TEXT,
                  'unresolved': {'type': 'boolean'}, 'required_evidence': TEXTS})
CHALLENGE = obj({'challenges': TEXTS, 'evidence_gaps': TEXTS, 'blocking': {'type': 'boolean'}})
ACTION = obj({'action': TEXT, 'owner': TEXT, 'deadline': TEXT, 'dependencies': TEXTS})
FINAL = obj({'decision': TEXT, 'why': TEXT, 'alternatives_rejected': TEXTS,
             'risks': TEXTS, 'assumptions': TEXTS,
             'action_plan': {'type': 'array', 'items': ACTION, 'minItems': 1},
             'KPI': TEXTS, 'next_decision_point': TEXT})
REVIEW = obj({'reviewer': TEXT, 'target': TEXT, 'challenges': TEXTS})


def validate(schema, value):
    Draft202012Validator(schema).validate(value)
    return value
