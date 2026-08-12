# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=51: OGE8: power_subst_one_base
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 9+10: a^p · a^q [op] a^r при a = N.
    [op] — двоеточие или дробь. Знак q — случайный.
    """
    a = random.randint(2, 7)
    k = random.randint(2, 5)
    use_colon = random.random() < 0.5
    q_negative = random.random() < 0.35

    while True:
        p = random.randint(8, 25)
        if q_negative:
            q = -random.randint(5, 15)
        else:
            q = random.randint(5, 18)
        r = p + q - k
        if 5 <= r <= 25:
            break

    answer = a ** k

    if use_colon:
        formula = rf"a^{{{p}}} \cdot a^{{{q}}} : a^{{{r}}}"
    else:
        formula = rf"\dfrac{{a^{{{p}}} \cdot a^{{{q}}}}}{{a^{{{r}}}}}"

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
