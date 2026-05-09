# -*- coding: utf-8 -*-
"""
Management command: наполнение «Задание 8» курса ОГЭ генераторами на степени.

Usage:
    python manage.py populate_oge8            # создать/обновить
    python manage.py populate_oge8 --clear    # удалить и пересоздать

Структура:
    Курс «ОГЭ» (slug=oge-maths)
      └ Модуль «Первая часть»
          └ Урок «Задание 8» (lesson_type='practice')
              └ Тип 1: Степень с одним основанием
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, ProblemGenerator


# ──────────────────────────────────────────────────────────────────────────────
# Генераторы
# ──────────────────────────────────────────────────────────────────────────────

GEN_POWER_ONE_BASE = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 1: значение выражения a^p · a^q / a^r с одной базой.
    База — натуральное число от 2 до 13.
    Итоговая степень не превышает 3 → ответ = a^k, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    neg = -random.randint(2, 12)
    r = random.randint(5, 15)
    pos = k - neg + r

    if random.random() < 0.5:
        e1, e2 = neg, pos
    else:
        e1, e2 = pos, neg

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\\dfrac{{ {a}^{{{e1}}} \\cdot {a}^{{{e2}}} }}{{ {a}^{{{r}}} }}$."
    )

    return {
        "condition_text": condition_text,
        "correct_answer": str(answer),
    }
'''


GEN_POWER_DIV_NUMBER = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 2: a^p / m, где m — натуральное число, равное a^q.
    База 2–13, ответ — натуральная степень a, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    max_q = 1
    while a ** (max_q + 1) <= 300 and max_q < 8:
        max_q += 1
    q = random.randint(1, max_q)

    p = k + q
    m = a ** q
    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\\dfrac{{ {a}^{{{p}}} }}{{ {m} }}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''


GEN_POWER_INV_PRODUCT = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 3: 1/a^(-p) · 1/a^q.
    База 2–13, ответ — натуральная степень a.
    Итог: a^p · a^(-q) = a^(p-q) = a^k.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    q = random.randint(5, 15)
    p = q + k

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\\dfrac{{1}}{{ {a}^{{{-p}}} }} \\cdot \\dfrac{{1}}{{ {a}^{{{q}}} }}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''


GEN_POWER_POW_DIV = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 4: (a^p)^q / a^r, где p>0, q<0, r<0.
    Итог: a^(p*q − r) = a^k, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    for _ in range(50):
        p = random.randint(2, 11)
        q = -random.randint(2, 9)
        r = p * q - k
        if 5 <= -r <= 30:
            break
    else:
        p, q = 3, -3
        r = p * q - k

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\\dfrac{{ ({a}^{{{p}}})^{{{q}}} }}{{ {a}^{{{r}}} }}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''


GEN_POWER_PROD_POW = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 5: a^p · (a^q)^r, где p<0, q>0, r>0.
    Итог: a^(p + q*r) = a^k, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    for _ in range(50):
        q = random.randint(2, 7)
        r = random.randint(2, 4)
        p = k - q * r
        if 3 <= -p <= 12:
            break
    else:
        q, r = 3, 2
        p = k - q * r

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"${a}^{{{p}}} \\cdot ({a}^{{{q}}})^{{{r}}}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''


GEN_POWER_COMPOSITE = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 6+7 (объединённый): композит (ab)^n и раздельные множители
    a^p · b^q на разных сторонах дроби. Композит может быть в числителе
    или в знаменателе; рендерится как (a·b)^n либо как (ab)^n со
    свёрнутым произведением — случайно.
    """
    while True:
        a = random.randint(2, 12)
        b = random.randint(2, 12)
        if a != b:
            break

    n = random.randint(4, 8)

    pairs = [(0, 1), (1, 0),
             (0, 2), (2, 0), (1, 1),
             (0, 3), (3, 0), (1, 2), (2, 1)]
    da, db = random.choice(pairs)

    composite_in_numerator = random.random() < 0.5
    render_as_product = random.random() < 0.5

    if composite_in_numerator:
        p = n - da
        q = n - db
    else:
        p = n + da
        q = n + db

    answer = (a ** da) * (b ** db)

    if render_as_product:
        composite_latex = rf"{a * b}^{{{n}}}"
    else:
        x, y = (a, b) if random.random() < 0.5 else (b, a)
        composite_latex = rf"({x} \\cdot {y})^{{{n}}}"

    if random.random() < 0.5:
        separate_latex = rf"{a}^{{{p}}} \\cdot {b}^{{{q}}}"
    else:
        separate_latex = rf"{b}^{{{q}}} \\cdot {a}^{{{p}}}"

    if composite_in_numerator:
        formula = rf"\\dfrac{{ {composite_latex} }}{{ {separate_latex} }}"
    else:
        formula = rf"\\dfrac{{ {separate_latex} }}{{ {composite_latex} }}"

    condition_text = rf"Найдите значение выражения ${formula}$."
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''


GEN_POWER_SUBST_ONE_BASE = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 9+10: a^p · a^q [op] a^r при a = N.
    [op] — двоеточие или дробь. Знак q — случайный.
    """
    a = random.randint(2, 7)
    k = random.randint(2, 5)
    use_colon = random.random() < 0.5
    q_negative = random.random() < 0.35

    while True:
        p = random.randint(8, 25)
        if q_negative:
            q = -random.randint(5, 15)
        else:
            q = random.randint(5, 18)
        r = p + q - k
        if 5 <= r <= 25:
            break

    answer = a ** k

    if use_colon:
        formula = rf"a^{{{p}}} \\cdot a^{{{q}}} : a^{{{r}}}"
    else:
        formula = rf"\\dfrac{{a^{{{p}}} \\cdot a^{{{q}}}}}{{a^{{{r}}}}}"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
'''


GEN_POWER_SUBST_POW_DIV = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 11+13: (a^p)^q [op] a^r при a = N.
    Полярность: либо все натуральные (дробь), либо q и r отрицательные (двоеточие).
    """
    a = random.randint(2, 7)
    k = random.randint(2, 5)
    polarity = random.choice(['positive', 'negative'])

    while True:
        p = random.randint(2, 8)
        if polarity == 'positive':
            q = random.randint(2, 5)
        else:
            q = -random.randint(2, 8)
        r = p * q - k
        if 8 <= abs(r) <= 22:
            break

    answer = a ** k

    if polarity == 'positive':
        formula = rf"\\dfrac{{\\left(a^{{{p}}}\\right)^{{{q}}}}}{{a^{{{r}}}}}"
    else:
        formula = rf"\\left(a^{{{p}}}\\right)^{{{q}}} : a^{{{r}}}"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
'''


GEN_POWER_SUBST_PROD_POW = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 12: a^p · (a^q)^r при a = N, p < 0.
    """
    a = random.randint(2, 7)
    k = random.randint(2, 5)

    while True:
        q = random.randint(2, 9)
        r = random.randint(2, 4)
        p = k - q * r
        if -15 <= p <= -6:
            break

    answer = a ** k

    formula = rf"a^{{{p}}} \\cdot \\left(a^{{{q}}}\\right)^{{{r}}}"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
'''


GEN_POWER_SUBST_MIXED = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 14: ((a^p)^q · a^r) / a^s при a = N.
    """
    a = random.randint(2, 7)
    k = random.randint(2, 5)

    while True:
        p = random.randint(3, 9)
        q = random.randint(2, 6)
        r = random.randint(3, 12)
        s = p * q + r - k
        if 13 <= s <= 30:
            break

    answer = a ** k

    formula = (
        rf"\\dfrac{{\\left(a^{{{p}}}\\right)^{{{q}}} \\cdot a^{{{r}}}}}"
        rf"{{a^{{{s}}}}}"
    )

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
'''


GEN_POWER_SUBST_AB = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 15: (a^P · (b^Q)^S) / (a·b)^R при a = N, b = √a.
    Степень b в упрощённом результате — чётная (0, 2, 4, 6).
    После подстановки b² = a → ответ = a^k_total, k_total ∈ {2, 3, 4, 5}.
    """
    a = random.choice([2, 3, 5, 6, 7])  # не полные квадраты
    k_total = random.randint(2, 5)

    valid_b_res = [b for b in (0, 2, 4, 6) if b // 2 <= k_total]
    b_residual = random.choice(valid_b_res)
    k_a = k_total - b_residual // 2

    while True:
        S = random.choice([2, 3, 4, 6])
        R = random.randint(12, 20)
        if (R + b_residual) % S != 0:
            continue
        Q = (R + b_residual) // S
        if 3 <= Q <= 10:
            break

    P = R + k_a
    answer = a ** k_total

    formula = (
        rf"\\dfrac{{a^{{{P}}} \\cdot \\left(b^{{{Q}}}\\right)^{{{S}}}}}"
        rf"{{(a \\cdot b)^{{{R}}}}}"
    )

    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $a = {a}$ и $b = \\sqrt{{{a}}}$."
        ),
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_OF_POWER = '''\
def generate_task():
    """№8 ОГЭ, Тип 16: √(a^n). Два режима: чётное n или a ∈ {4,9}."""
    mode = random.choice(['even_n', 'square_a'])

    if mode == 'square_a':
        a = random.choice([4, 9])
        n = random.randint(3, 6)
        root_a = int(a ** 0.5)
        answer = root_a ** n
    else:
        a = random.randint(2, 13)
        n = random.choice([2, 4, 6])
        answer = a ** (n // 2)

    formula = rf"\\sqrt{{{a}^{{{n}}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_NUM_OVER = '''\
def generate_task():
    """№8 ОГЭ, Тип 17: (c·√n)² / m, ответ = 1/множитель (десятичная дробь)."""
    c = random.choice([2, 3, 4, 5])
    n = random.choice([2, 3, 5, 6, 7, 10])
    base = c * c * n
    multiplier = random.choice([2, 4, 5, 8, 10, 20, 25])
    m = base * multiplier

    answer = 1 / multiplier
    answer_str = f"{answer}".rstrip('0').rstrip('.').replace('.', ',')

    formula = rf"\\dfrac{{({c}\\sqrt{{{n}}})^{{2}}}}{{{m}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": answer_str,
    }
'''


GEN_SQRT_DEN_OVER = '''\
def generate_task():
    """№8 ОГЭ, Тип 18: m / (c·√n)², m = c²n·k. Ответ = k."""
    c = random.choice([2, 3, 4, 5])
    n = random.choice([2, 3, 5, 6, 7, 10])
    base = c * c * n
    k = random.randint(2, 13)
    m = base * k

    formula = rf"\\dfrac{{{m}}}{{({c}\\sqrt{{{n}}})^{{2}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(k),
    }
'''


GEN_SQRT_TRIPLE_COEFFS = '''\
def generate_task():
    """№8 ОГЭ, Тип 19: c1·√a · c2·√b · √(a·b). Ответ = c1·c2·a·b."""
    non_squares = [2, 3, 5, 6, 7, 10, 11, 13, 14, 15, 17]
    while True:
        a = random.choice(non_squares)
        b = random.choice(non_squares)
        if a != b:
            break
    c1 = random.randint(2, 10)
    c2 = random.randint(2, 6)
    answer = c1 * c2 * a * b

    formula = (
        rf"{c1}\\sqrt{{{a}}} \\cdot {c2}\\sqrt{{{b}}} \\cdot \\sqrt{{{a * b}}}"
    )
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_TRIPLE = '''\
def generate_task():
    """№8 ОГЭ, Тип 20: √a · √(bc²) · √(ab). Ответ = abc."""
    a = random.choice([2, 3, 5, 7, 11, 13])
    b = random.choice([2, 3, 5, 7])
    c = random.randint(2, 5)
    if a == b:
        b = random.choice([x for x in [2, 3, 5, 7] if x != a])

    factors = [a, b * c * c, a * b]
    random.shuffle(factors)
    answer = a * b * c

    formula = (
        rf"\\sqrt{{{factors[0]}}} \\cdot \\sqrt{{{factors[1]}}} \\cdot \\sqrt{{{factors[2]}}}"
    )
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_QUOTIENT = '''\
def generate_task():
    """№8 ОГЭ, Тип 21: √(ac)·√(bc) / √(ab). Ответ = c."""
    c = random.randint(3, 13)
    while True:
        a = random.randint(2, 8)
        if random.random() < 0.15:
            b = 1
        else:
            b = random.randint(2, 8)
        if a == b:
            continue
        if a * c > 200 or b * c > 200 or a * b > 50:
            continue
        break

    A = a * c
    B = b * c
    C = a * b

    formula = rf"\\dfrac{{\\sqrt{{{A}}} \\cdot \\sqrt{{{B}}}}}{{\\sqrt{{{C}}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(c),
    }
'''


GEN_SQRT_COMMON_FACTOR = '''\
def generate_task():
    """№8 ОГЭ, Тип 22+23: (√(k²·c) ± √c)·√c. Ответ = c·(k ± 1)."""
    c = random.choice([2, 3, 5, 6, 7, 10, 11, 13])
    k = random.randint(2, 7)
    sign_plus = random.random() < 0.5

    inner = k * k * c
    if sign_plus:
        answer = c * (k + 1)
        sign = "+"
    else:
        answer = c * (k - 1)
        sign = "-"

    formula = (
        rf"\\left(\\sqrt{{{inner}}} {sign} \\sqrt{{{c}}}\\right)\\cdot\\sqrt{{{c}}}"
    )
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_DIFF_SQUARES = '''\
def generate_task():
    """№8 ОГЭ, Тип 25: (√a − √b)(√a + √b). Ответ = a − b."""
    perfect_squares = {n * n for n in range(1, 10)}
    while True:
        a = random.randint(2, 50)
        b = random.randint(2, 50)
        if a in perfect_squares or b in perfect_squares:
            continue
        if a == b:
            continue
        break

    answer = a - b

    if random.random() < 0.5:
        formula = rf"\\left(\\sqrt{{{a}}} + \\sqrt{{{b}}}\\right)\\left(\\sqrt{{{a}}} - \\sqrt{{{b}}}\\right)"
    else:
        formula = rf"\\left(\\sqrt{{{a}}} - \\sqrt{{{b}}}\\right)\\left(\\sqrt{{{a}}} + \\sqrt{{{b}}}\\right)"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_SQUARED_BINOM = '''\
def generate_task():
    """№8 ОГЭ, Тип 26: (√a ± b)² ∓ 2b·√a. Ответ = a + b²."""
    perfect_squares = {n * n for n in range(1, 8)}
    while True:
        a = random.randint(3, 30)
        b = random.randint(2, 9)
        if a in perfect_squares:
            continue
        break

    answer = a + b * b

    plus_inside = random.random() < 0.5
    if plus_inside:
        formula = (
            rf"\\left(\\sqrt{{{a}}} + {b}\\right)^{{2}} - {2 * b}\\sqrt{{{a}}}"
        )
    else:
        formula = (
            rf"\\left(\\sqrt{{{a}}} - {b}\\right)^{{2}} + {2 * b}\\sqrt{{{a}}}"
        )

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
'''


PROTOTYPES = [
    ('power_one_base',         'Степень с одним основанием',             GEN_POWER_ONE_BASE),
    ('power_div_number',       'Степень делённая на число',              GEN_POWER_DIV_NUMBER),
    ('power_inv_product',      'Произведение обратных степеней',         GEN_POWER_INV_PRODUCT),
    ('power_pow_div',          'Степень степени делённая на степень',    GEN_POWER_POW_DIV),
    ('power_prod_pow',         'Произведение степени и степени степени', GEN_POWER_PROD_POW),
    ('power_composite',        'Степень произведения',                   GEN_POWER_COMPOSITE),
    ('power_subst_one_base',   'Подстановка a: одно основание',          GEN_POWER_SUBST_ONE_BASE),
    ('power_subst_pow_div',    'Подстановка a: степень степени и степень', GEN_POWER_SUBST_POW_DIV),
    ('power_subst_prod_pow',   'Подстановка a: a^p · (a^q)^r',           GEN_POWER_SUBST_PROD_POW),
    ('power_subst_mixed',      'Подстановка a: смешанное выражение',     GEN_POWER_SUBST_MIXED),
    ('power_subst_ab',         'Подстановка a и b = √a',                 GEN_POWER_SUBST_AB),
    ('sqrt_of_power',          'Корень из степени',                      GEN_SQRT_OF_POWER),
    ('sqrt_num_over',          'Квадрат корня в числителе',              GEN_SQRT_NUM_OVER),
    ('sqrt_den_over',          'Квадрат корня в знаменателе',            GEN_SQRT_DEN_OVER),
    ('sqrt_triple_coeffs',     'Произведение корней с коэффициентами',   GEN_SQRT_TRIPLE_COEFFS),
    ('sqrt_triple',            'Произведение трёх корней',               GEN_SQRT_TRIPLE),
    ('sqrt_quotient',          'Частное произведения корней',            GEN_SQRT_QUOTIENT),
    ('sqrt_common_factor',     'Корни с общим множителем',               GEN_SQRT_COMMON_FACTOR),
    ('sqrt_diff_squares',      'Разность квадратов корней',              GEN_SQRT_DIFF_SQUARES),
    ('sqrt_squared_binom',     'Квадрат суммы/разности с корнем',        GEN_SQRT_SQUARED_BINOM),
]


class Command(BaseCommand):
    help = 'Создаёт «Задание 8» курса ОГЭ с генераторами на степени.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 8» и пересоздать.',
        )

    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден.'
            ))
            return

        module = course.modules.order_by('order').first()
        if not module:
            module = Module.objects.create(course=course, order=1, title='Первая часть')

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 8').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 8» удалено.'))

        lesson, _ = Lesson.objects.get_or_create(
            module=module, title='Задание 8',
            defaults={'order': 8, 'lesson_type': 'practice'},
        )
        if lesson.order != 8:
            lesson.order = 8
            lesson.save(update_fields=['order'])

        existing_orders = {a.order: a for a in lesson.assignments.all()}

        for i, (key, title, code) in enumerate(PROTOTYPES, start=1):
            gen_name = f'OGE8: {title}'
            gen, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                },
            )

            assign = existing_orders.get(i)
            if assign:
                assign.title = title
                assign.description = f'Генератор: {key}'
                assign.problem_generator = gen
                assign.answer_type = 'decimal_input'
                assign.required_correct = 3
                assign.save()
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=i,
                    title=title,
                    description=f'Генератор: {key}',
                    problem_generator=gen,
                    answer_type='decimal_input',
                    required_correct=3,
                )

        # Удаляем «лишние» прототипы (если их было больше)
        for order, a in existing_orders.items():
            if order < 1 or order > len(PROTOTYPES):
                a.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Готово: «Задание 8» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
