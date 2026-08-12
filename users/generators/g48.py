# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=48: OGE8: power_pow_div
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 4: (a^p)^q / a^r, где p>0, q<0, r<0.
    Итог: a^(p*q − r) = a^k, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    for _ in range(50):
        p = random.randint(2, 11)
        q = -random.randint(2, 9)
        r = p * q - k
        if 5 <= -r <= 30:
            break
    else:
        p, q = 3, -3
        r = p * q - k

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\dfrac{{ ({a}^{{{p}}})^{{{q}}} }}{{ {a}^{{{r}}} }}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
