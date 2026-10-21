import copy
import unittest
from app.telegram_presentation import render_result, telegram_html, FOOTER


class PresentationTests(unittest.TestCase):
    def test_council_bounded_and_lossless(self):
        result = {'provider': 'private', 'routing': {'level': 'L4'}, 'final': {
            'decision': 'Проверить идею 100 типографий пилотом.',
            'why': ['Маржа важнее числа площадок.']*2 + ['Спрос '+('в регионе '*100)]*8,
            'risks': ['Нет подтверждённой экономики.']*10,
            'action_plan': [{'action': f'Проверить регион {i}', 'owner': 'SECRET'} for i in range(20)],
            'KPI': ['SECRET'], 'confidence': .7}}
        original = copy.deepcopy(result)
        text = render_result(result)
        self.assertLessEqual(len(text), 1800)
        self.assertEqual(text.count('Маржа важнее числа площадок.'), 1)
        self.assertIn('**Что делать дальше**', text)
        self.assertIn('Confidence: 70%', text)
        self.assertIn(FOOTER, text)
        self.assertNotIn('SECRET', text)
        self.assertNotIn('private', text)
        self.assertEqual(result, original)

    def test_detail_and_json_string(self):
        result = {'final': {'decision': 'Пилот', 'action_plan': [{'action': f'Шаг {i}'} for i in range(10)]}}
        self.assertNotIn('Шаг 9', render_result(result))
        self.assertIn('Шаг 9', render_result(result, 'Разбери подробно'))
        self.assertIn('Пилот', render_result({'result': '{"decision":"Пилот","task_id":"SECRET"}'}))
        self.assertNotIn('SECRET', render_result({'result': '{"decision":"Пилот","task_id":"SECRET"}'}))
        self.assertNotIn('SECRET', render_result({'metadata': 'SECRET'}))

    def test_short_and_html(self):
        text = render_result({'routing': {'level': 'L1'}, 'result': {'summary': 'Тираж — число экземпляров.'}})
        self.assertLess(len(text), 100)
        self.assertEqual(telegram_html('**Вывод**\nA < B & C <script>'), '<b>Вывод</b>\nA &lt; B &amp; C &lt;script&gt;')
        self.assertLessEqual(len(render_result({'final': {'decision': 'Очень длинно '*500}})), 1200)

    def test_department_and_sentence_structure(self):
        text = render_result({'departmental_result': {'proposal': 'Открыть пилот.', 'why': 'Спрос растёт. Маржу нужно проверить.'}})
        self.assertIn('Открыть пилот.', text)
        self.assertIn('• Спрос растёт.\n• Маржу нужно проверить.', text)
        self.assertNotIn('SECRET', render_result({'result': '{"provider":"SECRET" invalid'}))
