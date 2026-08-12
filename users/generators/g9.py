# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=9: OGE9: Уравнение с двумя скобками
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    while True:
        x_frac = Fraction(random.randint(-70, 70), 10)
        a = random.choice([i for i in range(-5, 6) if i != 0])
        b = random.randint(-20, 20)
        n = random.choice([i for i in range(-5, 6) if i != 0])
        m = random.randint(-20, 20)
        second_left = random.choice([True, False])

        if second_left:
            net_coeff = a + n
        else:
            net_coeff = a - n

        if net_coeff == 0:
            continue

        if second_left:
            c_frac = a * (x_frac - b) + n * (x_frac - m)
        else:
            c_frac = a * (x_frac - b) - n * (x_frac - m)

        if abs(c_frac) > 20:
            continue
        if c_frac.denominator != 1:
            continue

        c = int(c_frac)

        if x_frac.denominator == 1:
            answer_str = str(int(x_frac))
        else:
            answer_str = f"{float(x_frac):.1f}".replace('.', ',')

        def format_bracket(coeff, free):
            abs_coeff = abs(coeff)
            if free > 0:
                inner = f"x - {free}"
            elif free < 0:
                inner = f"x + {abs(free)}"
            else:
                inner = "x"
            if abs_coeff == 1:
                return f"({inner})" if free != 0 else "x"
            else:
                return f"{abs_coeff}({inner})" if free != 0 else f"{abs_coeff}x"

        def format_signed(coeff, free, is_first=False):
            bracket = format_bracket(coeff, free)
            if is_first:
                return f"-{bracket}" if coeff < 0 else bracket
            else:
                return f"- {bracket}" if coeff < 0 else f"+ {bracket}"

        first = format_signed(a, b, is_first=True)
        second = format_signed(n, m, is_first=False)

        if second_left:
            left = f"{first} {second}"
            right = str(c)
        else:
            left = first
            right = f"{c} {second}"

        condition_text = f"Решите уравнение \\({left} = {right}\\)."
        return {"condition_text": condition_text, "correct_answer": answer_str}
