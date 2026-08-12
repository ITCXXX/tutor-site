# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=49: OGE8: power_prod_pow
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 5: a^p · (a^q)^r, где p<0, q>0, r>0.
    Итог: a^(p + q*r) = a^k, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    for _ in range(50):
        q = random.randint(2, 7)
        r = random.randint(2, 4)
        p = k - q * r
        if 3 <= -p <= 12:
            break
    else:
        q, r = 3, 2
        p = k - q * r

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"${a}^{{{p}}} \cdot ({a}^{{{q}}})^{{{r}}}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
