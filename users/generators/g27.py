# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=27: OGE8: Подстановка a: смешанное выражение
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 14: ((a^p)^q · a^r) / a^s при a = N.
    """
    a = random.randint(2, 7)
    k = random.randint(2, 5)

    while True:
        p = random.randint(3, 9)
        q = random.randint(2, 6)
        r = random.randint(3, 12)
        s = p * q + r - k
        if 13 <= s <= 30:
            break

    answer = a ** k

    formula = (
        rf"\dfrac{{\left(a^{{{p}}}\right)^{{{q}}} \cdot a^{{{r}}}}}"
        rf"{{a^{{{s}}}}}"
    )

    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
