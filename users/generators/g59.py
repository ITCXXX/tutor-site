# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=59: OGE8: sqrt_diff_squares
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """№8 ОГЭ, Тип 25: (√a − √b)(√a + √b). Ответ = a − b."""
    perfect_squares = {n * n for n in range(1, 10)}
    while True:
        a = random.randint(2, 50)
        b = random.randint(2, 50)
        if a in perfect_squares or b in perfect_squares:
            continue
        if a == b:
            continue
        break

    answer = a - b

    if random.random() < 0.5:
        formula = rf"\left(\sqrt{{{a}}} + \sqrt{{{b}}}\right)\left(\sqrt{{{a}}} - \sqrt{{{b}}}\right)"
    else:
        formula = rf"\left(\sqrt{{{a}}} - \sqrt{{{b}}}\right)\left(\sqrt{{{a}}} + \sqrt{{{b}}}\right)"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
