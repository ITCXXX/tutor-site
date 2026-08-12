# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=30: OGE8: Квадрат корня в числителе
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """№8 ОГЭ, Тип 17: (c·√n)² / m, ответ = 1/множитель (десятичная дробь)."""
    c = random.choice([2, 3, 4, 5])
    n = random.choice([2, 3, 5, 6, 7, 10])
    base = c * c * n
    multiplier = random.choice([2, 4, 5, 8, 10, 20, 25])
    m = base * multiplier

    answer = 1 / multiplier
    answer_str = f"{answer}".rstrip('0').rstrip('.').replace('.', ',')

    formula = rf"\dfrac{{({c}\sqrt{{{n}}})^{{2}}}}{{{m}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": answer_str,
    }
