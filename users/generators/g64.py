# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=64: OGE8: sqrt_neg_product
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 27: √((−a)^p · a^q), p, q — чётные.
    Случайно ставим минус на одном из множителей.
    Ответ = a^((p+q)/2).
    """
    a = random.randint(2, 5)
    k = random.randint(2, 6)
    total = 2 * k

    p = 2 * random.randint(1, k - 1)
    q = total - p

    minus_first = random.random() < 0.5
    if minus_first:
        formula = rf"\sqrt{{(-a)^{{{p}}} \cdot a^{{{q}}}}}"
    else:
        formula = rf"\sqrt{{a^{{{p}}} \cdot (-a)^{{{q}}}}}"

    answer = a ** k
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
