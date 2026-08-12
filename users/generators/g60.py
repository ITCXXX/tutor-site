# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=60: OGE8: sqrt_triple_coeffs
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """№8 ОГЭ, Тип 19: c1·√a · c2·√b · √(a·b). Ответ = c1·c2·a·b."""
    non_squares = [2, 3, 5, 6, 7, 10, 11, 13, 14, 15, 17]
    while True:
        a = random.choice(non_squares)
        b = random.choice(non_squares)
        if a != b:
            break
    c1 = random.randint(2, 10)
    c2 = random.randint(2, 6)
    answer = c1 * c2 * a * b

    formula = (
        rf"{c1}\sqrt{{{a}}} \cdot {c2}\sqrt{{{b}}} \cdot \sqrt{{{a * b}}}"
    )
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
