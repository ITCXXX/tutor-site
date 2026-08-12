# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=29: OGE8: Корень из степени
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """№8 ОГЭ, Тип 16: √(a^n). Два режима: чётное n или a ∈ {4,9}."""
    mode = random.choice(['even_n', 'square_a'])

    if mode == 'square_a':
        a = random.choice([4, 9])
        n = random.randint(3, 6)
        root_a = int(a ** 0.5)
        answer = root_a ** n
    else:
        a = random.randint(2, 13)
        n = random.choice([2, 4, 6])
        answer = a ** (n // 2)

    formula = rf"\sqrt{{{a}^{{{n}}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$.",
        "correct_answer": str(answer),
    }
