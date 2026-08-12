# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=55: OGE8: power_subst_ab
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 15: (a^P · (b^Q)^S) / (a·b)^R при a = N, b = √a.
    Степень b в упрощённом результате — чётная (0, 2, 4, 6).
    После подстановки b² = a → ответ = a^k_total, k_total ∈ {2, 3, 4, 5}.
    """
    a = random.choice([2, 3, 5, 6, 7])  # не полные квадраты
    k_total = random.randint(2, 5)

    valid_b_res = [b for b in (0, 2, 4, 6) if b // 2 <= k_total]
    b_residual = random.choice(valid_b_res)
    k_a = k_total - b_residual // 2

    while True:
        S = random.choice([2, 3, 4, 6])
        R = random.randint(12, 20)
        if (R + b_residual) % S != 0:
            continue
        Q = (R + b_residual) // S
        if 3 <= Q <= 10:
            break

    P = R + k_a
    answer = a ** k_total

    formula = (
        rf"\dfrac{{a^{{{P}}} \cdot \left(b^{{{Q}}}\right)^{{{S}}}}}"
        rf"{{(a \cdot b)^{{{R}}}}}"
    )

    return {
        "condition_text": (
            rf"Найдите значение выражения ${formula}$ "
            rf"при $a = {a}$ и $b = \sqrt{{{a}}}$."
        ),
        "correct_answer": str(answer),
    }
