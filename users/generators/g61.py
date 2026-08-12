# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=61: OGE8: sqrt_triple
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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
        rf"\sqrt{{{factors[0]}}} \cdot \sqrt{{{factors[1]}}} \cdot \sqrt{{{factors[2]}}}"
    )
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
