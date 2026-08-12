# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=43: OGE8: Корень полного квадрата (a−kb)²
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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

    formula = rf"\sqrt{{a^{{2}} - {2*k}ab + {k*k}b^{{2}}}}"
    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $a = {a}$ и $b = {b}$."
        ),
        "correct_answer": str(answer),
    }
