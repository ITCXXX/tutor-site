# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=58: OGE8: sqrt_den_over
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """№8 ОГЭ, Тип 18: m / (c·√n)², m = c²n·k. Ответ = k."""
    c = random.choice([2, 3, 4, 5])
    n = random.choice([2, 3, 5, 6, 7, 10])
    base = c * c * n
    k = random.randint(2, 13)
    m = base * k

    formula = rf"\dfrac{{{m}}}{{({c}\sqrt{{{n}}})^{{2}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(k),
    }
