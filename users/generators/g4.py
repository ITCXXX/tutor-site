# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=4: OGE9: Уравнение со скобкой
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
        c_frac = a * (x_frac - b)

        if abs(c_frac) > 20:
            continue

        if x_frac.denominator == 1:
            answer_str = str(int(x_frac))
        else:
            answer_str = f"{float(x_frac):.1f}".replace('.', ',')

        if c_frac.denominator == 1:
            c_str = str(int(c_frac))
        else:
            c_str = f"{float(c_frac):.1f}".replace('.', ',')

        if b > 0:
            x_minus_b = f"x - {b}"
        elif b < 0:
            x_minus_b = f"x + {abs(b)}"
        else:
            x_minus_b = "x"

        if a == 1:
            left = x_minus_b
        elif a == -1:
            if b == 0:
                left = "-x"
            else:
                left = f"-({x_minus_b})"
        else:
            if b == 0:
                left = f"{a}x"
            else:
                left = f"{a}({x_minus_b})"

        c_tex = c_str.replace(',', '{,}')
        condition_text = f"Решите уравнение \\({left} = {c_tex}\\)."
        return {"condition_text": condition_text, "correct_answer": answer_str}
