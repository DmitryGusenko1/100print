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

ANALYTICAL = obj({'question': TEXT, 'evidence': TEXTS, 'assumptions': TEXTS,
    'unknowns': TEXTS, 'hypotheses': {'type':'array','minItems':2,'maxItems':4,
        'items':obj({'hypothesis':TEXT,'arguments_for':TEXTS,'arguments_against':TEXTS})},
    'counterarguments':TEXTS,'contradictions':TEXTS,'risks':TEXTS,
    'confidence':{'type':'number','minimum':0,'maximum':1}, 'decision':TEXT,
    'change_conditions':TEXTS})

# Explicit production analytical artifact; old keys retained for API consumers.
BRIEF_FIELDS = {'position':TEXT, 'evidence':TEXTS, 'assumptions':TEXTS,
    'alternatives':TEXTS, 'arguments_for':TEXTS, 'arguments_against':TEXTS,
    'risks':TEXTS, 'confidence':{'type':'number','minimum':0,'maximum':1},
    'objections':TEXTS, 'recommendation':TEXT, 'change_conditions':TEXTS}
POSITION = obj({**POSITION['properties'], **BRIEF_FIELDS})
ANALYTICAL = obj({**ANALYTICAL['properties'], **BRIEF_FIELDS})
CHALLENGE = obj({**CHALLENGE['properties'], 'alternative_hypotheses':TEXTS})
