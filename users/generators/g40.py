# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=40: OGE8: Корень (1/K)·x^p·y^q с подстановкой
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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

    formula = rf"\sqrt{{\dfrac{{1}}{{{K}}}\cdot x^{{{p}}}\cdot y^{{{q}}}}}"
    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $x = {x_val}$ и $y = {y_val}$."
        ),
        "correct_answer": str(answer),
    }
