# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=37: OGE8: Квадрат суммы/разности с корнем
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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
            rf"\left(\sqrt{{{a}}} + {b}\right)^{{2}} - {2 * b}\sqrt{{{a}}}"
        )
    else:
        formula = (
            rf"\left(\sqrt{{{a}}} - {b}\right)^{{2}} + {2 * b}\sqrt{{{a}}}"
        )

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
