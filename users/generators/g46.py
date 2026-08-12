# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=46: OGE8: power_div_number
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 2: a^p / m, где m — натуральное число, равное a^q.
    База 2–13, ответ — натуральная степень a, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    max_q = 1
    while a ** (max_q + 1) <= 300 and max_q < 8:
        max_q += 1
    q = random.randint(1, max_q)

    p = k + q
    m = a ** q
    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\dfrac{{ {a}^{{{p}}} }}{{ {m} }}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
