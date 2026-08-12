# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=3: OGE9: Линейное уравнение
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    x_frac = Fraction(random.randint(-70, 70), 10)
    x = float(x_frac)

    coeffs = [i for i in range(-5, 6) if i != 0]
    a = random.choice(coeffs)
    c = random.choice([i for i in coeffs if i != a])

    if random.random() < 0.3:
        d = 0
    else:
        d = random.randint(-20, 20)

    b_frac = (c - a) * x_frac + d
    if b_frac.denominator != 1:
        diff = (c - a) * x_frac
        found = False
        candidates = list(range(-20, 21))
        random.shuffle(candidates)
        for d_try in candidates:
            b_check = (c - a) * x_frac + d_try
            if b_check.denominator == 1:
                d = d_try
                b_frac = b_check
                found = True
                break
        if not found:
            x_frac = Fraction(random.randint(-7, 7))
            x = float(x_frac)
            d = random.randint(-20, 20)
            b_frac = (c - a) * x_frac + d

    b = int(b_frac)

    if x_frac.denominator == 1:
        answer_str = str(int(x_frac))
    else:
        answer_str = f"{x:.1f}".replace('.', ',')

    def format_side(coeff, free, swap):
        if coeff == 1:
            x_term = "x"
        elif coeff == -1:
            x_term = "-x"
        else:
            x_term = f"{coeff}x"
        if free == 0:
            return x_term
        if swap:
            if coeff == 1:
                return f"{free} + x"
            elif coeff == -1:
                return f"{free} - x"
            else:
                if coeff > 0:
                    return f"{free} + {coeff}x"
                else:
                    return f"{free} - {abs(coeff)}x"
        else:
            if free > 0:
                return f"{x_term} + {free}"
            else:
                return f"{x_term} - {abs(free)}"

    swap_left = random.choice([True, False])
    swap_right = random.choice([True, False])
    left = format_side(a, b, swap_left)
    right = format_side(c, d, swap_right)
    condition_text = f"Решите уравнение \\({left} = {right}\\)."
    return {"condition_text": condition_text, "correct_answer": answer_str}
