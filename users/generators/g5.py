# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=5: OGE9: Уравнение со скобкой и kx
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
        k = random.choice([i for i in range(-5, 6) if i != 0])
        k_left = random.choice([True, False])

        if k_left:
            net_coeff = a + k
        else:
            net_coeff = a - k

        if net_coeff == 0:
            continue

        if k_left:
            c_frac = a * (x_frac - b) + k * x_frac
        else:
            c_frac = a * (x_frac - b) - k * x_frac

        if abs(c_frac) > 20:
            continue
        if c_frac.denominator != 1:
            continue

        c = int(c_frac)

        if x_frac.denominator == 1:
            answer_str = str(int(x_frac))
        else:
            answer_str = f"{float(x_frac):.1f}".replace('.', ',')

        if b > 0:
            x_minus_b = f"x - {b}"
        elif b < 0:
            x_minus_b = f"x + {abs(b)}"
        else:
            x_minus_b = "x"

        if a == 1:
            bracket_part = x_minus_b
        elif a == -1:
            bracket_part = f"-({x_minus_b})" if b != 0 else "-x"
        else:
            bracket_part = f"{a}({x_minus_b})" if b != 0 else f"{a}x"

        if k == 1:
            kx_str = "+ x"
        elif k == -1:
            kx_str = "- x"
        elif k > 0:
            kx_str = f"+ {k}x"
        else:
            kx_str = f"- {abs(k)}x"

        if k_left:
            left = f"{bracket_part} {kx_str}"
            right = str(c)
        else:
            left = bracket_part
            right = f"{c} {kx_str}"

        condition_text = f"Решите уравнение \\({left} = {right}\\)."
        return {"condition_text": condition_text, "correct_answer": answer_str}
