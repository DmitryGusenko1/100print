"""Lossless storage stays upstream; only public business fields reach Telegram."""
import html
import json
import re

DETAIL = re.compile(r'\b(подробно|детально|разбери|подробный|детальный)\b', re.I)
FOOTER = 'Если нужна детализация — разверну по блокам.'


def telegram_html(text):
    """Escape all provider content; support only our bold convention."""
    return re.sub(r'\*\*([^*\n]+)\*\*', r'<b>\1</b>', html.escape(text))


def render_result(result, question=''):
    detailed = bool(DETAIL.search(question))
    council = result.get('routing', {}).get('level') == 'L4'
    limit = 1800 if council else 1200
    if result.get('routing', {}).get('level') == 'L1':
        limit = 600
    omitted = False
    seen = set()

    def phrases(value):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                return [p for p in re.split(r'(?<=[.!?])\s+|\n+', value) if p.strip()]
            return phrases(parsed) if isinstance(parsed, (dict, list)) else [value]
        if isinstance(value, list):
            return [p for item in value for p in phrases(item)]
        if isinstance(value, dict):
            for key in ('action', 'summary', 'decision', 'recommendation', 'challenge'):
                if key in value:
                    items = phrases(value[key])
                    if detailed and key == 'action':
                        context = '; '.join(str(value[k]) for k in ('owner', 'deadline') if value.get(k))
                        if context:
                            items = [item+' ('+context+')' for item in items]
                    return items
        return []

    def select(value, count, width):
        nonlocal omitted
        output = []
        for phrase in phrases(value):
            phrase = re.sub(r'\s+', ' ', phrase).strip()
            phrase = re.sub(r'[`*]', '', phrase)
            key = phrase.casefold().rstrip('.!?')
            if not key or key in seen:
                continue
            seen.add(key)
            if not detailed and len(output) >= count:
                omitted = True
                continue
            if not detailed and len(phrase) > width:
                phrase = phrase[:width-1].rsplit(' ', 1)[0].rstrip(',;:')+'…'
                omitted = True
            output.append(phrase)
        return output

    value = result
    for key in ('final', 'analysis', 'result', 'departmental_result'):
        if result.get(key):
            value = result[key]
            break
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = {'summary': value} if not value.lstrip().startswith(('{', '[', '```')) else {}
    if not isinstance(value, dict):
        value = {}
    if not detailed and any(value.get(key) for key in ('assumptions', 'KPI', 'evidence_gaps', 'alternatives_rejected')):
        omitted = True
    sections = []
    conclusion = value.get('decision') or value.get('summary') or value.get('recommendation') or value.get('proposal') or value.get('position')
    text = select(conclusion, 1, 260)
    if text:
        sections.append('**Вывод**\n'+' '.join(text))
    for label, fields, count, width in [
        ('Главные идеи', ('why', 'evidence', 'arguments_for'), 3, 140),
        ('Риск / Critic', ('risks', 'counterarguments', 'objections'), 2, 130),
        ('Что делать дальше', ('action_plan', 'recommendations', 'next_decision_point', 'change_conditions'), 3, 120),
    ]:
        items = [value[k] for k in fields if value.get(k)]
        if detailed:
            extra = {'Главные идеи': ('assumptions', 'alternatives_rejected', 'KPI'),
                     'Риск / Critic': ('evidence_gaps',), 'Что делать дальше': ()}
            items += [value[k] for k in extra[label] if value.get(k)]
        selected = select(items, count, width)
        if selected:
            sections.append('**'+label+'**\n'+'\n'.join('• '+s for s in selected))
    confidence = value.get('confidence')
    if isinstance(confidence, (float, int)) and not isinstance(confidence, bool) and 0 <= confidence <= 1:
        sections.append(f'Confidence: {confidence:.0%}')
    if not sections:
        return 'Не удалось подготовить управленческое резюме. Уточните вопрос.'
    text = '\n\n'.join(sections)
    if not detailed and len(text) > limit-len(FOOTER)-2:
        text = text[:limit-len(FOOTER)-3].rsplit(' ', 1)[0].rstrip()+'…'
        # Never leave an unmatched bold delimiter after truncation.
        if text.count('**') % 2:
            text = text.rsplit('**', 1)[0].rstrip()+'…'
        omitted = True
    if omitted and not detailed:
        text += '\n\n'+FOOTER
    return text
