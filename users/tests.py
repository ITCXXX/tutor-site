# -*- coding: utf-8 -*-
"""
Проверка ответов: промежутки для неравенств второй части ОГЭ.

Половина типов №20 — неравенства, и ответ у них множество, а не число.
До этих правок такой ответ уходил в проверку набора корней (там тоже «;»)
и правильный ответ засчитывался как неверный. Тесты закрывают ровно то,
на чём это ломалось, и то, за что ученик обиделся бы больше всего:
перепутанный тип скобки не должен проходить, а иначе записанное, но то же
самое множество — должен.
"""

from django.test import SimpleTestCase, TestCase

from users import (oge20_generators, oge21_generators, oge22_generators, oge23_generators,
                   oge24_generators, oge25_generators)
from users.plot_svg import graph_svg
from users.answer_check import (
    AnswerError, check_answer, check_interval_answer, check_pairs_answer,
    format_interval_set, looks_like_interval, parse_interval_set, parse_pairs,
)


class IntervalParsingTests(SimpleTestCase):

    def test_plain_interval(self):
        self.assertEqual(parse_interval_set('[0; 5)'), [(0.0, True, 5.0, False)])

    def test_union_by_plus_and_by_cup(self):
        want = [(float('-inf'), False, -7.0, True), (0.0, False, 7.0, True)]
        for text in ('(-inf; -7] + (0; 7]',
                     '(-∞;-7]∪(0;7]',
                     '(-∞;-7] U (0;7]',
                     '(-∞;-7] или (0;7]'):
            self.assertEqual(parse_interval_set(text), want, text)

    def test_x_prefix_and_trailing_dot(self):
        self.assertEqual(parse_interval_set('x ∈ (2; 3).'),
                         parse_interval_set('(2;3)'))

    def test_infinity_spellings(self):
        for text in ('(-∞; 5]', '(-inf; 5]', '(-oo; 5]', '(-бесконечность; 5]'):
            got = parse_interval_set(text)
            self.assertEqual(got, [(float('-inf'), False, 5.0, True)], text)

    def test_square_bracket_at_infinity_is_forgiven(self):
        """[-∞ математически бессмысленно, но на экзамене за это не снимают."""
        self.assertEqual(parse_interval_set('[-∞; 5]'), parse_interval_set('(-∞; 5]'))

    def test_isolated_point(self):
        self.assertEqual(parse_interval_set('{4}'), [(4.0, True, 4.0, True)])
        self.assertEqual(parse_interval_set('4'), [(4.0, True, 4.0, True)])

    def test_decimal_comma_is_not_a_separator(self):
        """«0,5» — это число, а не два конца промежутка."""
        self.assertEqual(parse_interval_set('[0,5; 2]'), [(0.5, True, 2.0, True)])

    def test_touching_intervals_are_merged(self):
        self.assertEqual(parse_interval_set('[1;2] + [2;3]'), [(1.0, True, 3.0, True)])

    def test_gap_is_not_merged(self):
        """(1;2) и (2;3) не склеиваются: точка 2 не входит ни в один."""
        self.assertEqual(len(parse_interval_set('(1;2) + (2;3)')), 2)

    def test_bad_input_raises(self):
        for text in ('', 'ерунда', '(3; 1)', '(5; 5)', '(1, 2)'):
            with self.assertRaises(AnswerError, msg=text):
                parse_interval_set(text)

    def test_format_is_canonical(self):
        self.assertEqual(format_interval_set(parse_interval_set('(-inf;-7]+(0;7]')),
                         '(-∞; -7] + (0; 7]')
        self.assertEqual(format_interval_set(parse_interval_set('{4}')), '{4}')



class PairAnswerTests(SimpleTestCase):
    """Системы уравнений: ответ — набор пар (x; y)."""

    ЭТАЛОН = '(2; 4), (2; -4)'

    def test_pairs_parse(self):
        self.assertEqual(parse_pairs('(2; 4), (2; -4)'), [(2.0, -4.0), (2.0, 4.0)])

    def test_order_of_pairs_does_not_matter(self):
        for text in ('(2; 4), (2; -4)', '(2;-4),(2;4)', '(2; 4), (2; -4).'):
            ok, _ = check_answer(text, self.ЭТАЛОН, kind='pairs')
            self.assertTrue(ok, text)

    def test_order_inside_a_pair_does_matter(self):
        """(2; 4) и (4; 2) — разные точки, и путать их нельзя."""
        ok, _ = check_answer('(4; 2), (2; -4)', self.ЭТАЛОН, kind='pairs')
        self.assertFalse(ok)

    def test_missing_pair(self):
        ok, _ = check_answer('(2; 4)', self.ЭТАЛОН, kind='pairs')
        self.assertFalse(ok)

    def test_hint_when_written_as_numbers(self):
        ok, msg = check_answer('2; 4', self.ЭТАЛОН, kind='pairs')
        self.assertFalse(ok)
        self.assertIn('парами', msg or '')

    def test_fractional_pair(self):
        ok, _ = check_answer('(1,25; 0), (2; -1)', '(1.25; 0), (2; -1)', kind='pairs')
        self.assertTrue(ok)

    def test_junk_does_not_crash(self):
        for text in ('', '(', '(;)', '(1;2;3)', 'ерунда', '(nan; 1)'):
            ok, _ = check_pairs_answer(text, self.ЭТАЛОН)
            self.assertFalse(ok, text)

    def test_kind_pairs_beats_the_interval_guess(self):
        """«(2; 4)» выглядит как промежуток — вид ответа решает спор."""
        self.assertTrue(looks_like_interval('(2; 4)'))
        ok, _ = check_answer('(2; 4), (2; -4)', self.ЭТАЛОН, kind='pairs')
        self.assertTrue(ok)


class GeneratorAnswerFormatTests(SimpleTestCase):
    """
    Ответ, который генератор объявил, обязан приниматься проверкой.

    Тест дешёвый, а ловит целый класс поломок: сменили запись ответа в
    генераторе — и все задачи типа перестали засчитываться, притом молча.
    """

    СИДОВ = 25

    def test_every_generator_answer_is_accepted(self):
        for номер, функция in sorted(oge20_generators.GENERATORS.items()):
            for seed in range(self.СИДОВ):
                task = oge20_generators.generate(номер, seed)
                ok, msg = check_answer(task['answer'], task['answer'],
                                       kind=task.get('answer_kind'),
                                       allow_fractions=task.get('allow_fractions', True))
                self.assertTrue(
                    ok, 'тип %d, сид %d: свой же ответ «%s» не принят (%s)'
                        % (номер, seed, task['answer'], msg))

    def test_every_generator_fills_the_contract(self):
        for номер, функция in sorted(oge20_generators.GENERATORS.items()):
            task = oge20_generators.generate(номер, 0)
            for поле in ('type', 'title', 'question_html', 'answer',
                         'answer_kind', 'solution_html', 'params'):
                self.assertIn(поле, task, 'тип %d: нет поля %s' % (номер, поле))
            self.assertEqual(task['type'], номер)
            self.assertIn(task['answer_kind'], ('roots', 'number', 'pairs', 'interval'))
            self.assertTrue(task['question_html'].strip())
            self.assertTrue(task['solution_html'].strip())

    def test_statements_have_no_dangling_signs(self):
        """«x - -1» и «+ -3» — это невычищенный знак, а не математика."""
        for номер in sorted(oge20_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                текст = oge20_generators.generate(номер, seed)['question_html']
                for мусор in ('- -', '+ -', '--', '+ +'):
                    self.assertNotIn(мусор, текст,
                                     'тип %d, сид %d: «%s» в условии' % (номер, seed, мусор))

class Oge22GeneratorTests(SimpleTestCase):
    """
    №22 — графики функций. Математику проверяет oge22_setup/verify_oge22.py:
    он численно считает пересечения прямой с графиком по кускам функции и
    сверяет с объявленным ответом. Здесь — контракт и то, что до ученика
    доедет: ответ обязан приниматься проверкой, в разборе обязан быть график,
    а тип, у которого ответ не меняется от задачи к задаче, бесполезен как
    тренажёр.
    """

    СИДОВ = 12

    def test_answers_are_accepted(self):
        for номер in sorted(oge22_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                task = oge22_generators.generate(номер, seed)
                ok, msg = check_answer(
                    task['answer'], task['answer'],
                    allow_fractions='/' in task['answer'],
                    kind=task['answer_kind'])
                self.assertTrue(ok, 'тип %d, сид %d: ответ «%s» не принят (%s)'
                                    % (номер, seed, task['answer'], msg))

    def test_solution_carries_a_graph(self):
        """Разбор «постройте график» без графика бессмыслен."""
        for номер in sorted(oge22_generators.GENERATORS):
            html = oge22_generators.generate(номер, 0)['solution_html']
            self.assertIn('<svg', html, 'тип %d' % номер)
            self.assertIn('Ответ:', html, 'тип %d' % номер)

    def test_answers_vary_between_seeds(self):
        """
        Если ответ один и тот же при любых параметрах, ученик запоминает его
        и перестаёт решать. Так было у банковского типа 15 («какое наибольшее
        число общих точек» — всегда 4), поэтому вопрос там заменён.
        """
        # Тип 5 — исключение по существу, а не по недосмотру: там ответ
        # равен {0} + [d²; +∞) при d ∈ {1, 2, 3}, то есть трёх разных
        # ответов не может быть больше и в самом банке (все 8 задач дают
        # h ∈ {1, 4, 9}). Условия при этом разные, и разбор задачи ответом
        # не заменяется: чтобы узнать h, его надо найти.
        МАЛО_ОТВЕТОВ = {5: 3}
        for номер in sorted(oge22_generators.GENERATORS):
            ответы = {oge22_generators.generate(номер, seed)['answer']
                      for seed in range(20)}
            порог = МАЛО_ОТВЕТОВ.get(номер, 4)
            self.assertGreaterEqual(len(ответы), порог,
                                    'тип %d: всего %d разных ответов на 20 сидах'
                                    % (номер, len(ответы)))
            # Планка по банку: там на тип приходится 8-10 задач, и наши
            # семейства не должны быть беднее источника. Самые тесные типы —
            # 8 и 16 (по 8 разных условий): у 16 единственный параметр a, и
            # расширять его нельзя, при a >= 3 выколотые точки сползаются к
            # оси и картинка перестаёт читаться.
            условия = {oge22_generators.generate(номер, seed)['question_html']
                       for seed in range(60)}
            self.assertGreaterEqual(len(условия), 8,
                                    'тип %d: всего %d разных условий на 60 сидах'
                                    % (номер, len(условия)))

    def test_condition_is_well_formed(self):
        for номер in sorted(oge22_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                текст = oge22_generators.generate(номер, seed)['question_html']
                self.assertIn('Постройте график функции', текст)
                for мусор in ('None', '%s', '{}', 'Fraction'):
                    self.assertNotIn(мусор, текст,
                                     'тип %d, сид %d: «%s»' % (номер, seed, мусор))

    def test_decimal_answers_have_no_fractions(self):
        """
        Обыкновенная дробь в ответе разрешена только там, где десятичной не
        существует (тип 6: k = a²/b²). Во всех остальных случаях дробь в
        ответе означала бы, что ученику её же и не примут.
        """
        for номер in sorted(oge22_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                task = oge22_generators.generate(номер, seed)
                if '/' not in task['answer']:
                    continue
                self.assertEqual(номер, 6,
                                 'тип %d, сид %d: обыкновенная дробь «%s»'
                                 % (номер, seed, task['answer']))

    def test_as_task_contract(self):
        for номер in sorted(oge22_generators.GENERATORS):
            данные = oge22_generators.as_task(номер, 0)
            for ключ in ('condition_text', 'correct_answer', 'answer_kind',
                         'solution_html', 'oge22_type'):
                self.assertIn(ключ, данные, 'тип %d' % номер)
            self.assertEqual(данные['oge22_type'], номер)
            self.assertTrue(данные['correct_answer'].strip(), 'тип %d' % номер)

    def test_answer_boundaries_fit_the_window(self):
        """Границу ответа обязано быть видно на картинке."""
        for номер in sorted(oge22_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                task = oge22_generators.generate(номер, seed)
                if task['ask'][0] != 'hline':
                    continue
                _, _, ymin, ymax = task['window']
                for низ, _, верх, _ in task['answer_set']:
                    for v in (низ, верх):
                        if v in (oge22_generators.INF, -oge22_generators.INF):
                            continue
                        self.assertTrue(ymin < v < ymax,
                                        'тип %d, сид %d: граница %s вне окна %s'
                                        % (номер, seed, v, task['window']))


class Oge24ScenarioTests(SimpleTestCase):
    """
    №24 — задачи на доказательство. Само доказательство машина не проверит,
    его читали два независимых рецензента. Здесь — то, что доедет до ученика
    сломанным: сюжет собирается на нескольких сидах, условие начинается с
    «Докажите», чертёж есть, формулы и теги закрыты, у сюжетов с числами
    числа удовлетворяют нужному соотношению.
    """

    СИДОВ = 6

    def test_contract(self):
        for номер in sorted(oge24_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                task = oge24_generators.generate(номер, seed)
                for ключ in ('title', 'statement_html', 'proof_html', 'figure', 'facts'):
                    self.assertIn(ключ, task, 'сюжет %d' % номер)
                self.assertIn('окажите', task['statement_html'], 'сюжет %d, сид %d' % (номер, seed))
                self.assertIsNotNone(task['figure'], 'сюжет %d: нет чертежа' % номер)
                self.assertTrue(task['facts'], 'сюжет %d: нет опорных фактов' % номер)

    def test_as_task_is_a_proof(self):
        for номер in sorted(oge24_generators.GENERATORS):
            данные = oge24_generators.as_task(номер, 0)
            self.assertEqual(данные['answer_kind'], 'proof', 'сюжет %d' % номер)
            self.assertEqual(данные['correct_answer'], 'solved')
            self.assertIn('<svg', данные['solution_html'], 'сюжет %d' % номер)
            self.assertIn('Доказательство.', данные['solution_html'], 'сюжет %d' % номер)

    def test_formulas_and_tags_are_closed(self):
        for номер in sorted(oge24_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                данные = oge24_generators.as_task(номер, seed)
                for текст in (данные['condition_text'], данные['solution_html']):
                    self.assertEqual(текст.count('\\('), текст.count('\\)'),
                                     'сюжет %d, сид %d: не сходятся \\( и \\)' % (номер, seed))
                    self.assertEqual(текст.count('\\['), текст.count('\\]'),
                                     'сюжет %d, сид %d: не сходятся \\[ и \\]' % (номер, seed))
                    for мусор in ('None', '%s', '%d', 'Fraction('):
                        self.assertNotIn(мусор, текст, 'сюжет %d, сид %d: «%s»' % (номер, seed, мусор))

    def test_trapezoid_numbers_satisfy_the_relation(self):
        """Сюжет 1: подобие держится на BD² = BC·AD, и числа обязаны ему подчиняться."""
        for seed in range(40):
            p = oge24_generators.generate(1, seed)['params']
            self.assertEqual(p['BD'] ** 2, p['BC'] * p['AD'], 'сид %d: %s' % (seed, p))
            self.assertNotEqual(p['BC'], p['AD'], 'сид %d: основания равны — не трапеция' % seed)


class ProofModeViewTests(TestCase):
    """
    Режим доказательства на сервере: разбор открывается до ответа только у
    задач с answer_kind = 'proof', отметка «solved» считается верным ответом,
    а у числовой задачи разбор до ответа закрыт.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from users.models import (Course, Module, Lesson, Assignment,
                                  ProblemGenerator, GeneratedProblem, Enrollment)
        User = get_user_model()
        self.student = User.objects.create_user(
            username='proof_student', password='x', role='student')
        course = Course.objects.create(title='Тест ОГЭ', slug='oge-test', is_public=True)
        module = Module.objects.create(course=course, title='Вторая часть', order=2)
        lesson = Lesson.objects.create(module=module, title='№24', order=24, lesson_type='practice')
        Enrollment.objects.create(course=course, student=self.student, is_active=True)
        gen = ProblemGenerator.objects.create(
            id=1101, name='OGE24: тест', generator_type='python_function', python_code='')
        self.assignment = Assignment.objects.create(
            lesson=lesson, title='Сюжет 1', description='', assignment_type='test',
            answer_type='text_input', required_correct=1, points=2,
            problem_generator=gen, order=1)
        данные = oge24_generators.as_task(1, 0)
        self.proof = GeneratedProblem.objects.create(
            student=self.student, assignment=self.assignment, task_data=данные,
            condition_text=данные['condition_text'],
            correct_answer=данные['correct_answer'], status='new')
        числовая = oge22_generators.as_task(6, 0)
        self.numeric = GeneratedProblem.objects.create(
            student=self.student, assignment=self.assignment, task_data=числовая,
            condition_text=числовая['condition_text'],
            correct_answer=числовая['correct_answer'], status='new')
        self.client.force_login(self.student)

    def test_solution_before_answer_only_for_proofs(self):
        r = self.client.get('/exam/solution/%d/' % self.proof.id, HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        self.assertIn('<svg', r.json()['solution_html'])
        r = self.client.get('/exam/solution/%d/' % self.numeric.id, HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 403)

    def test_self_mark_solved_counts_as_correct(self):
        import json
        r = self.client.post('/exam/check/%d/' % self.proof.id,
                             data=json.dumps({'answer': 'solved'}),
                             content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['correct'])
        self.assertIn('<svg', r.json()['solution_html'])
        self.proof.refresh_from_db()
        self.assertEqual(self.proof.status, 'solved')

    def test_self_mark_failed_still_returns_solution(self):
        import json
        r = self.client.post('/exam/check/%d/' % self.proof.id,
                             data=json.dumps({'answer': 'failed'}),
                             content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertFalse(r.json()['correct'])
        self.assertTrue(r.json()['solution_html'])

    def test_practice_page_shows_proof_ui(self):
        r = self.client.get('/assignment/%d/practice/' % self.assignment.id, HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="proof-row"')
        self.assertNotContains(r, 'Введите ответ:')


class GeometryGeneratorTests(SimpleTestCase):
    """
    №23 и №25 — геометрия с числовым ответом. Полную сверку делает
    oge23_setup/verify_geom.py (по координатам, 40 сидов на тип); здесь —
    короткий вариант той же сверки на нескольких сидах и контракт: ответ
    принимается проверкой сайта, значение ответа сходится с построением
    в координатах, в тексте нет мусора.
    """

    СИДОВ = 5
    МОДУЛИ = ((23, oge23_generators), (25, oge25_generators))

    def _значения(self, task):
        v = task['answer_value']
        return sorted(float(x) for x in (v if isinstance(v, (list, tuple)) else [v]))

    def test_answer_is_accepted(self):
        for номер, G in self.МОДУЛИ:
            for тип in sorted(G.GENERATORS):
                for seed in range(self.СИДОВ):
                    task = G.generate(тип, seed)
                    ok, msg = check_answer(task['answer'], task['answer'],
                                           allow_fractions=bool(task.get('allow_fractions')),
                                           kind=task.get('answer_kind', 'number'))
                    self.assertTrue(ok, '№%d тип %d сид %d: «%s» не принят (%s)'
                                        % (номер, тип, seed, task['answer'], msg))

    def test_formula_agrees_with_coordinates(self):
        """Формула ответа и построение в координатах — два независимых пути к одному числу."""
        for номер, G in self.МОДУЛИ:
            for тип in sorted(G.GENERATORS):
                for seed in range(self.СИДОВ):
                    task = G.generate(тип, seed)
                    измерено = task['check']()
                    измерено = sorted(float(x) for x in
                                      (измерено if isinstance(измерено, (list, tuple)) else [измерено]))
                    объявлено = self._значения(task)
                    self.assertEqual(len(измерено), len(объявлено), '№%d тип %d сид %d' % (номер, тип, seed))
                    for m, v in zip(измерено, объявлено):
                        self.assertAlmostEqual(m, v, delta=1e-6 * max(1.0, abs(v)),
                                               msg='№%d тип %d сид %d: координаты %.8g, формула %.8g'
                                                   % (номер, тип, seed, m, v))

    def test_texts_are_well_formed(self):
        for номер, G in self.МОДУЛИ:
            for тип in sorted(G.GENERATORS):
                данные = G.as_task(тип, 0)
                for текст in (данные['condition_text'], данные['solution_html']):
                    for мусор in ('None', '%s', '%d', 'Fraction('):
                        self.assertNotIn(мусор, текст, '№%d тип %d: «%s»' % (номер, тип, мусор))
                    self.assertEqual(текст.count('\\('), текст.count('\\)'), '№%d тип %d' % (номер, тип))
                self.assertIn('Найдите', данные['condition_text'], '№%d тип %d' % (номер, тип))
                self.assertIn('Ответ:', данные['solution_html'])

    def test_answers_vary(self):
        for номер, G in self.МОДУЛИ:
            for тип in sorted(G.GENERATORS):
                ответы = {G.generate(тип, seed)['answer'] for seed in range(20)}
                self.assertGreaterEqual(len(ответы), 4, '№%d тип %d: %d разных ответов на 20 сидах'
                                        % (номер, тип, len(ответы)))


class PlotSvgTests(SimpleTestCase):
    """
    Рисовалка графиков для разборов №22. Проверяем ровно то, что уже ломалось
    или могло сломаться незаметно: обрыв на асимптоте, обрезку прямой по окну
    и то, что за пределы окна ничего не вылезает.
    """

    def test_asymptote_breaks_the_curve(self):
        """1/x нельзя рисовать одной ломаной: получилась бы черта через экран."""
        svg = graph_svg([(lambda x: 1.0 / x, -6, -0.01), (lambda x: 1.0 / x, 0.01, 6)],
                        xmin=-6, xmax=6, ymin=-5, ymax=5)
        self.assertGreaterEqual(svg.count('<path d="M'), 2)

    def test_steep_ray_is_drawn(self):
        """
        y = 4x в окне x ∈ [-3; 3], y ∈ [-1; 9] выходит через верх и низ.
        Обрезка только по вертикальным границам теряла обе точки, и прямая
        просто не рисовалась — молча, без ошибки.
        """
        svg = graph_svg([(lambda x: x * x, -3, 3)], xmin=-3, xmax=3, ymin=-1, ymax=9,
                        rays=[(4, 'y = 4x')])
        self.assertIn('stroke-dasharray', svg)
        self.assertIn('y = 4x', svg)

    def test_gentle_ray_is_drawn(self):
        svg = graph_svg([(lambda x: x * x, -3, 3)], xmin=-8, xmax=5, ymin=-2, ymax=10,
                        rays=[(1, 'y = x')])
        self.assertIn('stroke-dasharray', svg)

    def test_hline_outside_window_is_skipped(self):
        svg = graph_svg([(lambda x: x, -2, 2)], xmin=-2, xmax=2, ymin=-2, ymax=2,
                        hlines=[(99, 'y = 99')])
        self.assertNotIn('y = 99', svg)

    def test_nothing_escapes_the_canvas(self):
        """Координаты точек кривой обязаны лежать внутри картинки."""
        import re
        w, h = 420, 340
        svg = graph_svg([(lambda x: x ** 3, -4, 4)], xmin=-4, xmax=4, ymin=-6, ymax=6,
                        width=w, height=h)
        for d in re.findall(r'<path d="M([^"]+)" fill="none"', svg):
            for пара in d.replace('M', '').split('L'):
                x, y = (float(v) for v in пара.split())
                self.assertTrue(-1 <= x <= w + 1, 'x=%s' % x)
                self.assertTrue(-1 <= y <= h + 1, 'y=%s' % y)

    def test_holes_and_dots(self):
        svg = graph_svg([(lambda x: x * x - 4, -5, 5)], xmin=-5, xmax=5, ymin=-6, ymax=8,
                        holes=[(2, 0)], dots=[(-2, 0)])
        self.assertEqual(svg.count('<circle'), 2)


class Oge21GeneratorTests(SimpleTestCase):
    """
    №21 — текстовые задачи. Математику проверяет oge21_setup/verify_oge21.py
    (подстановка ответа в уравнение задачи), здесь — контракт и русский язык:
    ответ обязан приниматься проверкой, а в условии не должно быть «на 3 часов».
    """

    СИДОВ = 30

    def test_answers_are_accepted(self):
        for номер in sorted(oge21_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                task = oge21_generators.generate(номер, seed)
                ok, msg = check_answer(task['answer'], task['answer'],
                                       allow_fractions=False)
                self.assertTrue(ok, 'тип %d, сид %d: ответ «%s» не принят (%s)'
                                    % (номер, seed, task['answer'], msg))

    def test_answers_are_decimal(self):
        """На ОГЭ ответ пишут десятичной дробью — обыкновенных быть не должно."""
        for номер in sorted(oge21_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                answer = oge21_generators.generate(номер, seed)['answer']
                self.assertNotIn('/', answer, 'тип %d, сид %d' % (номер, seed))

    def test_plural_agreement(self):
        forms = ('час', 'часа', 'часов')
        for n, want in ((1, 'час'), (2, 'часа'), (4, 'часа'), (5, 'часов'),
                        (11, 'часов'), (21, 'час'), (22, 'часа'), (25, 'часов'),
                        (111, 'часов'), (101, 'час')):
            self.assertEqual(oge21_generators.plural(n, forms), want, str(n))

    def test_genitive_after_preposition(self):
        """«из 21 детали», а не «из 21 деталь»."""
        forms = ('детали', 'деталей')
        self.assertEqual(oge21_generators.род(21, forms), 'детали')
        self.assertEqual(oge21_generators.род(22, forms), 'деталей')
        self.assertEqual(oge21_generators.род(11, forms), 'деталей')

    def test_statements_are_well_formed(self):
        import re
        плохо = ('на 3 часов', 'на 5 часа', '  ', 'из 1 деталь',
                 'километров/ч', 'None', '{')
        for номер in sorted(oge21_generators.GENERATORS):
            for seed in range(self.СИДОВ):
                текст = oge21_generators.generate(номер, seed)['question_html']
                текст = ' '.join(re.sub(r'<[^>]+>', ' ', текст).split())
                for мусор in плохо:
                    self.assertNotIn(мусор, текст,
                                     'тип %d, сид %d: «%s»' % (номер, seed, мусор))


class IntervalAnswerTests(SimpleTestCase):

    ЭТАЛОН = '(-inf; -7] + (0; 7]'

    def test_same_set_written_differently(self):
        for text in ('(-∞; -7] + (0; 7]',
                     '(-∞;-7]∪(0;7]',
                     '(-inf;-7] U (0;7]',
                     'x ∈ (-∞; -7] + (0; 7]',
                     '(0;7] + (-∞;-7]'):          # порядок не важен
            ok, _ = check_answer(text, self.ЭТАЛОН)
            self.assertTrue(ok, text)

    def test_bracket_type_matters(self):
        """Главное содержание ответа неравенства — какие концы включены."""
        for text in ('(-∞; -7) + (0; 7]', '(-∞; -7] + (0; 7)', '(-∞; -7] + [0; 7]'):
            ok, _ = check_answer(text, self.ЭТАЛОН)
            self.assertFalse(ok, text)

    def test_wrong_endpoint(self):
        ok, _ = check_answer('(-∞; -6] + (0; 7]', self.ЭТАЛОН)
        self.assertFalse(ok)

    def test_roots_instead_of_interval_get_a_hint(self):
        ok, msg = check_answer('-7; 7', self.ЭТАЛОН)
        self.assertFalse(ok)
        self.assertIn('промежутками', msg or '')

    def test_equal_sets_split_differently(self):
        ok, _ = check_answer('[1;2] + [2;3]', '[1;3]')
        self.assertTrue(ok)

    def test_point_in_union(self):
        for text in ('(-∞;-6) + {4}', '(-∞;-6) + 4', '{4} + (-∞;-6)'):
            ok, _ = check_answer(text, '(-inf;-6) + {4}')
            self.assertTrue(ok, text)

    def test_interval_route_does_not_break_roots(self):
        """Набор корней проверяется по-прежнему — скобок в нём нет."""
        ok, _ = check_answer('2;-2;-5', '-5;-2;2')
        self.assertTrue(ok)
        ok, _ = check_answer('2;-2', '-5;-2;2')
        self.assertFalse(ok)

    def test_plain_number_still_works(self):
        ok, _ = check_answer('15', '15')
        self.assertTrue(ok)

    def test_latex_answers_are_not_intervals(self):
        """
        У дроби в LaTeX тоже есть фигурные скобки. Если считать такой ответ
        множеством, он читается как «точка 0,75»: по значению сходится, а
        проверка канонической формы молча пропускается — и несократимую дробь
        перестаёт отличать от сокращаемой.
        """
        latex_frac_34 = chr(92) + 'frac{3}{4}'
        latex_sqrt_2 = chr(92) + 'sqrt{2}'
        latex_2sqrt3 = '2' + chr(92) + 'sqrt{3}'
        latex_frac_24 = chr(92) + 'frac{2}{4}'
        latex_frac_12 = chr(92) + 'frac{1}{2}'
        latex_sqrt_8 = chr(92) + 'sqrt{8}'
        latex_2sqrt2 = '2' + chr(92) + 'sqrt{2}'

        for text in (latex_frac_34, latex_sqrt_2, latex_2sqrt3, '3/4', '0.5', '15'):
            self.assertFalse(looks_like_interval(text), text)

        ok, msg = check_answer(latex_frac_24, latex_frac_12)
        self.assertFalse(ok)
        self.assertIn('Сократите', msg or '')

        ok, _ = check_answer(latex_sqrt_8, latex_2sqrt2)
        self.assertFalse(ok)

        ok, _ = check_answer(latex_frac_12, latex_frac_12)
        self.assertTrue(ok)

    def test_recognition(self):
        self.assertTrue(looks_like_interval('(-∞; -7] + (0; 7]'))
        self.assertTrue(looks_like_interval('{4}'))
        self.assertFalse(looks_like_interval('-5;-2;2'))
        self.assertFalse(looks_like_interval('15'))

    def test_junk_input_never_crashes(self):
        """
        Проверка ответа не имеет права падать: исключение мимо AnswerError
        уходит из view пятисоткой, ученик видит «ошибка соединения», а его
        попытка вообще не записывается. Голый минус ученики шлют регулярно.
        """
        for text in ('-', '+', '—', '(-;5)', '{-}', 'ерунда', '((((', '1e999',
                     '(nan;nan)', '(0;' + '9' * 400 + ')'):
            ok, _ = check_answer(text, self.ЭТАЛОН)
            self.assertFalse(ok, text)

    def test_lowercase_union_letter(self):
        """Латинскую «u» набирают без Shift — это тот же знак объединения."""
        ok, _ = check_answer('(-∞;-7] u (0;7]', self.ЭТАЛОН)
        self.assertTrue(ok)

    def test_reference_that_only_looks_like_a_set(self):
        """
        «бесконечно много решений» ловится по слову «бесконечн», но множеством
        не является: такой эталон обязан уйти в обычную проверку, иначе
        правильный ответ засчитывается как неверный.
        """
        ok, _ = check_answer('бесконечно много решений', 'бесконечно много решений')
        self.assertTrue(ok)

    def test_root_sign_instead_of_latex(self):
        r"""
        Корень ученик пишет знаком √ — так его ставит кнопка на странице.
        Внутри это тот же \sqrt{}, поэтому и проверка формы остаётся.
        """
        L = chr(92)
        эталон = '3+' + L + 'sqrt{5}'
        for text in ('3+√5', '3 + √5', '√5+3', эталон):
            ok, _ = check_answer(text, эталон)
            self.assertTrue(ok, text)

        ok, _ = check_answer('3+√6', эталон)
        self.assertFalse(ok)

        ok, msg = check_answer('√8', '2' + L + 'sqrt{2}')
        self.assertFalse(ok)
        self.assertIn('корн', (msg or '').lower())

    def test_irrational_roots_as_a_set(self):
        """Ответ вида a ± √b: два корня, порядок не важен."""
        L = chr(92)
        эталон = '3-' + L + 'sqrt{5}; 3+' + L + 'sqrt{5}'
        for text in ('3-√5; 3+√5', '3+√5; 3-√5'):
            ok, _ = check_answer(text, эталон)
            self.assertTrue(ok, text)
        ok, _ = check_answer('3-√5', эталон)
        self.assertFalse(ok)

    def test_interval_with_radical_ends(self):
        """Концы промежутка тоже бывают иррациональными: (3−√5; 3+√5)."""
        L = chr(92)
        эталон = '(3-' + L + 'sqrt{5}; 3+' + L + 'sqrt{5})'
        self.assertTrue(looks_like_interval(эталон))
        for text in ('(3-√5; 3+√5)', '(3 - √5; 3 + √5)', эталон):
            ok, _ = check_answer(text, эталон)
            self.assertTrue(ok, text)
        for text in ('[3-√5; 3+√5]', '(3-√5; 3+√6)'):
            ok, _ = check_answer(text, эталон)
            self.assertFalse(ok, text)

    def test_negative_sum_endpoint(self):
        """
        «-3-√2» — это сумма, а не минус от «3-√2». Разбор снимал знак и
        применял его ко всему выражению, получая -1,59 вместо -4,41: ответ
        разбирался, но с чужими концами, и верное решение не засчитывалось.
        """
        L = chr(92)
        эталон = '(-3-' + L + 'sqrt{2}; -3+' + L + 'sqrt{2})'
        концы = parse_interval_set(эталон)
        self.assertEqual(len(концы), 1)
        self.assertAlmostEqual(концы[0][0], -4.4142, places=3)
        self.assertAlmostEqual(концы[0][2], -1.5858, places=3)

        ok, _ = check_answer('(-3-√2; -3+√2)', эталон)
        self.assertTrue(ok)
        ok, _ = check_answer('(-3+√2; -3-√2)', эталон)   # концы наоборот
        self.assertFalse(ok)

    def test_empty_answer_is_not_correct(self):
        ok, _ = check_interval_answer('', self.ЭТАЛОН)
        self.assertFalse(ok)


class PWATests(TestCase):
    """Установка сайта на домашний экран.

    Проверяем не «страница открылась», а три вещи, на которых это ломается
    молча: service worker обязан отдаваться из корня, манифест — быть валидным
    JSON с иконками, а список для предзагрузки — состоять из настоящих адресов.
    """

    def test_манифест_отдаётся_и_описывает_приложение(self):
        r = self.client.get('/manifest.webmanifest', HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        данные = r.json()
        self.assertEqual(данные['display'], 'standalone')
        self.assertEqual(данные['scope'], '/')
        self.assertEqual(данные['start_url'], '/cards/')
        размеры = {и['sizes'] for и in данные['icons']}
        self.assertEqual(размеры, {'192x192', '512x512'})
        # Хотя бы одна иконка должна быть maskable, иначе Android обрежет
        # рисунок по кругу вместе с содержимым.
        self.assertIn('maskable', {и['purpose'] for и in данные['icons']})

    def test_service_worker_отдаётся_из_корня(self):
        r = self.client.get('/sw.js', HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        self.assertIn('javascript', r['Content-Type'])
        self.assertEqual(r['Service-Worker-Allowed'], '/')
        текст = r.content.decode('utf-8')
        self.assertIn('/static/css/tokens.css', текст)
        self.assertIn('/static/vendor/mathjax-3.2.2/tex-svg.js', текст)
        self.assertIn('/offline/', текст)

    def test_service_worker_не_кэшируется_браузером(self):
        """Иначе новый service worker не доедет до тех, у кого сайт уже стоит."""
        r = self.client.get('/sw.js', HTTP_HOST='127.0.0.1')
        self.assertIn('no-cache', r['Cache-Control'])

    def test_версия_кэша_меняется_вместе_с_файлами(self):
        from users import views_pwa

        первая = views_pwa._версия(views_pwa._адреса())
        вторая = views_pwa._версия(views_pwa._адреса() + ['/static/новый.css'])
        self.assertNotEqual(первая, вторая)
        self.assertEqual(первая, views_pwa._версия(views_pwa._адреса()))

    def test_офлайн_страница_открыта_всем(self):
        r = self.client.get('/offline/', HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Нет соединения')

    def test_манифест_подключён_к_страницам(self):
        r = self.client.get('/', HTTP_HOST='127.0.0.1')
        self.assertContains(r, 'rel="manifest"')
        self.assertContains(r, 'apple-touch-icon')
        self.assertContains(r, 'serviceWorker')


class SeedOgeCourseTests(TestCase):
    """Курс ОГЭ описан кодом, а не заводится руками в админке.

    Раньше все seed-команды начинались с поиска курса по slug и на новом
    сервере молча отказывались работать: «Курс ОГЭ (slug=oge-maths) не найден».
    """

    def _запустить(self, *аргументы):
        from io import StringIO

        from django.core.management import call_command

        вывод = StringIO()
        call_command('seed_oge_course', *аргументы, stdout=вывод)
        return вывод.getvalue()

    def test_создаёт_курс_и_три_модуля(self):
        from users.models import Course

        вывод = self._запустить()
        курс = Course.objects.get(slug='oge-maths')
        self.assertTrue(курс.is_public)
        self.assertEqual(курс.tracking_mode, Course.TRACKING_AUTO)
        self.assertEqual(
            sorted(курс.modules.values_list('title', flat=True)),
            sorted(['Задания 1-5', 'Первая часть', 'Вторая часть']),
        )
        self.assertIn('создан', вывод)

    def test_повторный_запуск_ничего_не_ломает(self):
        from users.models import Course

        self._запустить()
        курс = Course.objects.get(slug='oge-maths')
        курс.title = 'ОГЭ по математике, 9 класс'
        курс.save()

        вывод = self._запустить()
        курс.refresh_from_db()
        # Название, поправленное в админке, повторный запуск не затирает.
        self.assertEqual(курс.title, 'ОГЭ по математике, 9 класс')
        self.assertEqual(Course.objects.filter(slug='oge-maths').count(), 1)
        self.assertEqual(курс.modules.count(), 3)
        self.assertIn('уже есть', вывод)

    def test_после_курса_сид_второй_части_отрабатывает(self):
        """Ради этого всё и затевалось: seed_oge22 больше не упирается в курс."""
        from io import StringIO

        from django.core.management import call_command
        from users.models import Assignment

        self._запустить()
        вывод = StringIO()
        call_command('seed_oge22', stdout=вывод)
        self.assertNotIn('не найден', вывод.getvalue())
        self.assertEqual(
            Assignment.objects.filter(lesson__title__startswith='№22').count(), 17)

    def test_список_курсов_показывается_и_ничего_не_создаёт(self):
        from users.models import Course

        вывод = self._запустить('--list')
        self.assertIn('Курсов нет вообще', вывод)
        self.assertEqual(Course.objects.count(), 0)

