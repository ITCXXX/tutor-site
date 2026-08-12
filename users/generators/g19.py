# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=19: OGE8: Произведение обратных степеней
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 3: 1/a^(-p) · 1/a^q.
    База 2–13, ответ — натуральная степень a.
    Итог: a^p · a^(-q) = a^(p-q) = a^k.
    """
    a = random.randint(2, 13)
    k = random.randint(1, 3)

    q = random.randint(5, 15)
    p = q + k

    answer = a ** k

    condition_text = (
        rf"Найдите значение выражения "
        rf"$\dfrac{{1}}{{ {a}^{{{-p}}} }} \cdot \dfrac{{1}}{{ {a}^{{{q}}} }}$."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
