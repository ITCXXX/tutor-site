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


GEN_SQRT_NEG_PRODUCT = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 27: √((−a)^p · a^q), p, q — чётные.
    Случайно ставим минус на одном из множителей.
    Ответ = a^((p+q)/2).
    """
    a = random.randint(2, 5)
    k = random.randint(2, 6)
    total = 2 * k

    p = 2 * random.randint(1, k - 1)
    q = total - p

    minus_first = random.random() < 0.5
    if minus_first:
        formula = rf"\\sqrt{{(-a)^{{{p}}} \\cdot a^{{{q}}}}}"
    else:
        formula = rf"\\sqrt{{a^{{{p}}} \\cdot (-a)^{{{q}}}}}"

    answer = a ** k
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_K_FRAC = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 28: √(K·a^p / a^q), K — точный квадрат.
    m = p − q ∈ {2, 4, 6, 8} — задаёт показатель в ответе.
    Ответ = √K · a^(m/2).
    """
    K = random.choice([4, 9, 16, 25, 36, 49, 64, 81, 100, 121])
    sqrt_K = int(K ** 0.5)
    m = random.choice([2, 4, 6, 8])
    q = random.randint(8, 18)
    p = q + m
    a = random.randint(2, 7)

    answer = sqrt_K * (a ** (m // 2))

    formula = rf"\\sqrt{{\\dfrac{{{K}a^{{{p}}}}}{{a^{{{q}}}}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_INV_K_PROD = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 29: √((1/K)·x^p·y^q), K = c², c ∈ [2, 9].
    Один из (x, y) равен c — тогда деление на c всегда чистое.
    Ответ — натуральное число.
    """
    c = random.randint(2, 9)
    K = c * c

    p = random.choice([2, 4, 6])
    q = random.choice([2, 4])

    if random.random() < 0.5:
        x_val, y_val = c, random.randint(2, 7)
    else:
        x_val, y_val = random.randint(2, 7), c

    answer = (x_val ** (p // 2)) * (y_val ** (q // 2)) // c

    formula = rf"\\sqrt{{\\dfrac{{1}}{{{K}}}\\cdot x^{{{p}}}\\cdot y^{{{q}}}}}"
    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $x = {x_val}$ и $y = {y_val}$."
        ),
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_K_X_OVER_Y = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 30: √(K·x^p / y^q), q ∈ {2, 4}.
    K = (a·y^(q/2))² — y-часть всегда целиком сокращается.
    Ответ = a · x^(p/2).
    """
    q = random.choice([2, 4])
    p = random.choice([2, 4, 6])

    if q == 2:
        a_coeff = random.randint(2, 6)
        y_val = random.randint(2, 6)
    else:
        a_coeff = random.randint(2, 4)
        y_val = random.randint(2, 4)

    K = (a_coeff * (y_val ** (q // 2))) ** 2
    x_val = random.randint(2, 6)

    answer = a_coeff * (x_val ** (p // 2))

    formula = rf"\\sqrt{{\\dfrac{{{K}x^{{{p}}}}}{{y^{{{q}}}}}}}"
    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $x = {x_val}$ и $y = {y_val}$."
        ),
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_BINOM_MIXED = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 31: √((p·a + q·b)²) при подстановке смешанных дробей.
    (p, q) ∈ {(1, k), (k, 1)} для k ∈ {3, 4, 5, 6}.
    Без петель: подбираем (k, m) с gcd=1, K и small_int сразу валидны.
    """
    valid_pairs = [(k, m) for k in (3, 4, 5, 6) for m in (3, 5, 7, 9, 11, 13)
                   if math.gcd(k, m) == 1]
    k, m = random.choice(valid_pairs)

    K_min = max(3, (m + k) // m + 1)
    K = random.randint(K_min, 12)

    max_small = min(m - 1, ((K - 1) * m - 1) // k)
    small_int = random.randint(1, max_small)
    big_int = K * m - k * small_int
    big_whole = big_int // m
    big_num = big_int % m

    role = random.choice(['a_mixed', 'b_mixed'])
    if role == 'a_mixed':
        a_render = rf"{big_whole}\\dfrac{{{big_num}}}{{{m}}}"
        b_render = rf"\\dfrac{{{small_int}}}{{{m}}}"
        coef_a2, coef_ab, coef_b2 = 1, 2 * k, k * k
    else:
        a_render = rf"\\dfrac{{{small_int}}}{{{m}}}"
        b_render = rf"{big_whole}\\dfrac{{{big_num}}}{{{m}}}"
        coef_a2, coef_ab, coef_b2 = k * k, 2 * k, 1

    parts = []
    parts.append("a^{2}" if coef_a2 == 1 else f"{coef_a2}a^{{2}}")
    parts.append(f"{coef_ab}ab")
    parts.append("b^{2}" if coef_b2 == 1 else f"{coef_b2}b^{{2}}")
    formula = rf"\\sqrt{{{' + '.join(parts)}}}"

    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $a = {a_render}$ и $b = {b_render}$."
        ),
        "correct_answer": str(K),
    }
'''


GEN_SQRT_PERFECT_DIFF = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 32: √(a² − 2k·ab + k²·b²) = |a − kb|.
    Целые a, b ∈ [2, 9], k ∈ {2..6}, ответ ≠ 0.
    """
    while True:
        k = random.randint(2, 6)
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        if a != k * b:
            break

    answer = abs(a - k * b)

    formula = rf"\\sqrt{{a^{{2}} - {2*k}ab + {k*k}b^{{2}}}}"
    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $a = {a}$ и $b = {b}$."
        ),
        "correct_answer": str(answer),
    }
'''


GEN_SQRT_PERFECT_SUM_NEG_B = '''\
def generate_task():
    """
    №8 ОГЭ, Тип 33: √(a² + 2k·ab + k²·b²) = |a + kb|, b — отрицательное целое.
    a ∈ [2, 9], b ∈ [-9, -2], k ∈ {2..6}, ответ ≠ 0.
    """
    while True:
        k = random.randint(2, 6)
        a = random.randint(2, 9)
        b = -random.randint(2, 9)
        if a + k * b != 0:
            break

    answer = abs(a + k * b)

    formula = rf"\\sqrt{{a^{{2}} + {2*k}ab + {k*k}b^{{2}}}}"
    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $a = {a}$ и $b = {b}$."
        ),
        "correct_answer": str(answer),
    }
'''


# Группы (для будущих раскрывающихся секций в UI):
GROUP_POWERS_NUM   = 'Свойства степеней'
GROUP_POWERS_SUBST = 'Степени с подстановкой'
GROUP_SQRT_NUM     = 'Корни из чисел'
GROUP_SQRT_PRODS   = 'Произведения и частные корней'
GROUP_SQRT_SUBST   = 'Корни со степенями и подстановкой'
GROUP_SQRT_PERFECT = 'Полные квадраты под корнем'

# (key, group, title (LaTeX), code)
PROTOTYPES = [
    # ── Группа 1: Свойства степеней (числа без переменных)
    ('power_one_base',         GROUP_POWERS_NUM,   r'\(\dfrac{a^{p}\cdot a^{q}}{a^{r}}\)',                       GEN_POWER_ONE_BASE),
    ('power_div_number',       GROUP_POWERS_NUM,   r'\(\dfrac{a^{p}}{m}\)',                                      GEN_POWER_DIV_NUMBER),
    ('power_inv_product',      GROUP_POWERS_NUM,   r'\(\dfrac{1}{a^{-p}}\cdot\dfrac{1}{a^{q}}\)',                GEN_POWER_INV_PRODUCT),
    ('power_pow_div',          GROUP_POWERS_NUM,   r'\(\dfrac{(a^{p})^{q}}{a^{r}}\)',                            GEN_POWER_POW_DIV),
    ('power_prod_pow',         GROUP_POWERS_NUM,   r'\(a^{p}\cdot(a^{q})^{r}\)',                                 GEN_POWER_PROD_POW),
    ('power_composite',        GROUP_POWERS_NUM,   r'\((ab)^{n}\)',                                              GEN_POWER_COMPOSITE),

    # ── Группа 2: Степени с подстановкой переменной
    ('power_subst_one_base',   GROUP_POWERS_SUBST, r'\(a^{p}\cdot a^{q}\pm a^{r},\ a=N\)',                       GEN_POWER_SUBST_ONE_BASE),
    ('power_subst_pow_div',    GROUP_POWERS_SUBST, r'\((a^{p})^{q}\pm a^{r},\ a=N\)',                            GEN_POWER_SUBST_POW_DIV),
    ('power_subst_prod_pow',   GROUP_POWERS_SUBST, r'\(a^{p}\cdot(a^{q})^{r},\ a=N\)',                           GEN_POWER_SUBST_PROD_POW),
    ('power_subst_mixed',      GROUP_POWERS_SUBST, r'\(\dfrac{(a^{p})^{q}\cdot a^{r}}{a^{s}},\ a=N\)',           GEN_POWER_SUBST_MIXED),
    ('power_subst_ab',         GROUP_POWERS_SUBST, r'\(\dfrac{a^{P}\cdot(b^{Q})^{S}}{(ab)^{R}},\ b=\sqrt{a}\)',  GEN_POWER_SUBST_AB),

    # ── Группа 3: Корни из чисел и числовых дробей
    ('sqrt_of_power',          GROUP_SQRT_NUM,     r'\(\sqrt{a^{n}}\)',                                          GEN_SQRT_OF_POWER),
    ('sqrt_num_over',          GROUP_SQRT_NUM,     r'\(\dfrac{(c\sqrt{n})^{2}}{m}\)',                            GEN_SQRT_NUM_OVER),
    ('sqrt_den_over',          GROUP_SQRT_NUM,     r'\(\dfrac{m}{(c\sqrt{n})^{2}}\)',                            GEN_SQRT_DEN_OVER),
    ('sqrt_diff_squares',      GROUP_SQRT_NUM,     r'\((\sqrt{a}-\sqrt{b})(\sqrt{a}+\sqrt{b})\)',                GEN_SQRT_DIFF_SQUARES),

    # ── Группа 4: Произведения и частные корней
    ('sqrt_triple_coeffs',     GROUP_SQRT_PRODS,   r'\(c_{1}\sqrt{a}\cdot c_{2}\sqrt{b}\cdot\sqrt{ab}\)',        GEN_SQRT_TRIPLE_COEFFS),
    ('sqrt_triple',            GROUP_SQRT_PRODS,   r'\(\sqrt{a}\cdot\sqrt{bc^{2}}\cdot\sqrt{ab}\)',              GEN_SQRT_TRIPLE),
    ('sqrt_quotient',          GROUP_SQRT_PRODS,   r'\(\dfrac{\sqrt{ac}\cdot\sqrt{bc}}{\sqrt{ab}}\)',            GEN_SQRT_QUOTIENT),
    ('sqrt_common_factor',     GROUP_SQRT_PRODS,   r'\((\sqrt{k^{2}c}\pm\sqrt{c})\sqrt{c}\)',                    GEN_SQRT_COMMON_FACTOR),

    # ── Группа 5: Корни со степенями и подстановкой
    ('sqrt_neg_product',       GROUP_SQRT_SUBST,   r'\(\sqrt{(-a)^{p}\cdot a^{q}},\ a=N\)',                      GEN_SQRT_NEG_PRODUCT),
    ('sqrt_k_frac',            GROUP_SQRT_SUBST,   r'\(\sqrt{\dfrac{Ka^{p}}{a^{q}}},\ a=N\)',                    GEN_SQRT_K_FRAC),
    ('sqrt_inv_k_prod',        GROUP_SQRT_SUBST,   r'\(\sqrt{\dfrac{1}{K}\,x^{p}y^{q}},\ x,y=N\)',               GEN_SQRT_INV_K_PROD),
    ('sqrt_k_x_over_y',        GROUP_SQRT_SUBST,   r'\(\sqrt{\dfrac{Kx^{p}}{y^{q}}},\ x,y=N\)',                  GEN_SQRT_K_X_OVER_Y),

    # ── Группа 6: Полные квадраты под корнем
    ('sqrt_squared_binom',     GROUP_SQRT_PERFECT, r'\((\sqrt{a}\pm b)^{2}\mp 2b\sqrt{a}\)',                     GEN_SQRT_SQUARED_BINOM),
    ('sqrt_binom_mixed',       GROUP_SQRT_PERFECT, r'\(\sqrt{(p\,a+q\,b)^{2}}\)',                                GEN_SQRT_BINOM_MIXED),
    ('sqrt_perfect_diff',      GROUP_SQRT_PERFECT, r'\(\sqrt{a^{2}-2k\,ab+k^{2}b^{2}}\)',                        GEN_SQRT_PERFECT_DIFF),
    ('sqrt_perfect_sum_neg_b', GROUP_SQRT_PERFECT, r'\(\sqrt{a^{2}+2k\,ab+k^{2}b^{2}},\ b<0\)',                  GEN_SQRT_PERFECT_SUM_NEG_B),
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

        # Ищем модуль 'Первая часть' по имени, не first() по order — иначе с
        # появлением модуля 'Задания 1-5' (order=0) создавался дубль урока.
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

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

        for i, (key, group, title, code) in enumerate(PROTOTYPES, start=1):
            gen_name = f'OGE8: {key}'
            gen, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                },
            )

            # Группу храним в description — UI группирует по этому полю.
            description = f'group: {group}'

            assign = existing_orders.get(i)
            if assign:
                # title не перезаписываем — мог быть переименован вручную.
                assign.description = description
                assign.problem_generator = gen
                assign.answer_type = 'decimal_input'
                assign.required_correct = 3
                assign.save()
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=i,
                    title=title,
                    description=description,
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
