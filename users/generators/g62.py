# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=62: OGE8: sqrt_quotient
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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

    formula = rf"\dfrac{{\sqrt{{{A}}} \cdot \sqrt{{{B}}}}}{{\sqrt{{{C}}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(c),
    }
