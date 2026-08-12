# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=65: OGE8: sqrt_k_frac
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 28: √(K·a^p / a^q), K — точный квадрат.
    m = p − q ∈ {2, 4, 6, 8} — задаёт показатель в ответе.
    Ответ = √K · a^(m/2).
    """
    K = random.choice([4, 9, 16, 25, 36, 49, 64, 81, 100, 121])
    sqrt_K = int(K ** 0.5)
    m = random.choice([2, 4, 6, 8])
    q = random.randint(8, 18)
    p = q + m
    a = random.randint(2, 7)

    answer = sqrt_K * (a ** (m // 2))

    formula = rf"\sqrt{{\dfrac{{{K}a^{{{p}}}}}{{a^{{{q}}}}}}}"
    return {
        "condition_text": rf"Найдите значение выражения ${formula}$ при $a = {a}$.",
        "correct_answer": str(answer),
    }
