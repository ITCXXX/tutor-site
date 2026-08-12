# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=67: OGE8: sqrt_k_x_over_y
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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

    formula = rf"\sqrt{{\dfrac{{{K}x^{{{p}}}}}{{y^{{{q}}}}}}}"
    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $x = {x_val}$ и $y = {y_val}$."
        ),
        "correct_answer": str(answer),
    }
