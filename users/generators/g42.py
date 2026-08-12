# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=42: OGE8: Корень полного квадрата со смеш. дробями
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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
        a_render = rf"{big_whole}\dfrac{{{big_num}}}{{{m}}}"
        b_render = rf"\dfrac{{{small_int}}}{{{m}}}"
        coef_a2, coef_ab, coef_b2 = 1, 2 * k, k * k
    else:
        a_render = rf"\dfrac{{{small_int}}}{{{m}}}"
        b_render = rf"{big_whole}\dfrac{{{big_num}}}{{{m}}}"
        coef_a2, coef_ab, coef_b2 = k * k, 2 * k, 1

    parts = []
    parts.append("a^{2}" if coef_a2 == 1 else f"{coef_a2}a^{{2}}")
    parts.append(f"{coef_ab}ab")
    parts.append("b^{2}" if coef_b2 == 1 else f"{coef_b2}b^{{2}}")
    formula = rf"\sqrt{{{' + '.join(parts)}}}"

    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $a = {a_render}$ и $b = {b_render}$."
        ),
        "correct_answer": str(K),
    }
