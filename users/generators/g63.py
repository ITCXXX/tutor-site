# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=63: OGE8: sqrt_common_factor
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


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
        rf"\left(\sqrt{{{inner}}} {sign} \sqrt{{{c}}}\right)\cdot\sqrt{{{c}}}"
    )
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
