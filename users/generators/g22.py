# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=22: OGE8: Степень произведения
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    """
    №8 ОГЭ, Тип 6+7 (объединённый): композит (ab)^n и раздельные множители
    a^p · b^q на разных сторонах дроби. Композит может быть в числителе
    или в знаменателе; рендерится как (a·b)^n либо как (ab)^n со
    свёрнутым произведением — случайно.
    """
    while True:
        a = random.randint(2, 12)
        b = random.randint(2, 12)
        if a != b:
            break

    n = random.randint(4, 8)

    pairs = [(0, 1), (1, 0),
             (0, 2), (2, 0), (1, 1),
             (0, 3), (3, 0), (1, 2), (2, 1)]
    da, db = random.choice(pairs)

    composite_in_numerator = random.random() < 0.5
    render_as_product = random.random() < 0.5

    if composite_in_numerator:
        p = n - da
        q = n - db
    else:
        p = n + da
        q = n + db

    answer = (a ** da) * (b ** db)

    if render_as_product:
        composite_latex = rf"{a * b}^{{{n}}}"
    else:
        x, y = (a, b) if random.random() < 0.5 else (b, a)
        composite_latex = rf"({x} \cdot {y})^{{{n}}}"

    if random.random() < 0.5:
        separate_latex = rf"{a}^{{{p}}} \cdot {b}^{{{q}}}"
    else:
        separate_latex = rf"{b}^{{{q}}} \cdot {a}^{{{p}}}"

    if composite_in_numerator:
        formula = rf"\dfrac{{ {composite_latex} }}{{ {separate_latex} }}"
    else:
        formula = rf"\dfrac{{ {separate_latex} }}{{ {composite_latex} }}"

    condition_text = rf"Найдите значение выражения ${formula}$."
    return {"condition_text": condition_text, "correct_answer": str(answer)}
