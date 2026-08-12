# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=45: OGE8: power_one_base
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 1: значение выражения a^p · a^q / a^r с одной базой.
    База — натуральное число от 2 до 13.
    Итоговая степень не превышает 3 → ответ = a^k, k ∈ {1, 2, 3}.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    neg = -random.randint(2, 12)
    r = random.randint(5, 15)
    pos = k - neg + r

    if random.random() < 0.5:
        e1, e2 = neg, pos
    else:
        e1, e2 = pos, neg

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\dfrac{{ {a}^{{{e1}}} \cdot {a}^{{{e2}}} }}{{ {a}^{{{r}}} }}$."
    )

    return {
        "condition_text": condition_text,
        "correct_answer": str(answer),
    }
