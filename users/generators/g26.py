# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=26: OGE8: Подстановка a: a^p · (a^q)^r
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 12: a^p · (a^q)^r при a = N, p < 0.
    """
    a = random.randint(2, 7)
    k = random.randint(2, 5)

    while True:
        q = random.randint(2, 9)
        r = random.randint(2, 4)
        p = k - q * r
        if -15 <= p <= -6:
            break

    answer = a ** k

    formula = rf"a^{{{p}}} \cdot \left(a^{{{q}}}\right)^{{{r}}}"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
