# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=52: OGE8: power_subst_pow_div
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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
        formula = rf"\dfrac{{\left(a^{{{p}}}\right)^{{{q}}}}}{{a^{{{r}}}}}"
    else:
        formula = rf"\left(a^{{{p}}}\right)^{{{q}}} : a^{{{r}}}"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
