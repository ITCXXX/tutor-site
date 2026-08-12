# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=13: OGE10: Ручки в магазине
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    total = random.choice([40, 50, 80, 100, 200])
    # (gen_pl, ask_form, fem_sg_nom, nom_pl)
    color_pool = [
        ("красных",     "красной",      "красная",      "красные"),
        ("синих",       "синей",        "синяя",        "синие"),
        ("зелёных",     "зелёной",      "зелёная",      "зелёные"),
        ("фиолетовых",  "фиолетовой",   "фиолетовая",   "фиолетовые"),
        ("чёрных",      "чёрной",       "чёрная",       "чёрные"),
        ("голубых",     "голубой",      "голубая",      "голубые"),
        ("оранжевых",   "оранжевой",    "оранжевая",    "оранжевые"),
    ]
    colors = random.sample(color_pool, 5)

    def pen_count(n, color):
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} {color[2]}"
        else:
            return f"{n} {color[0]}"

    a = random.randint(1, total // 5)
    b = random.randint(1, total // 5)
    c = random.randint(1, total // 5)
    remainder = total - a - b - c
    if remainder % 2 != 0:
        if c < total // 5:
            c += 1
        else:
            c -= 1
        remainder = total - a - b - c
    if remainder <= 0:
        a, b, c = total // 6, total // 6, total // 6
        remainder = total - a - b - c
        if remainder % 2 != 0:
            c += 1
            remainder = total - a - b - c

    half = remainder // 2
    counts = [a, b, c, half, half]
    ask_indices = random.sample(range(5), 2)
    favorable = counts[ask_indices[0]] + counts[ask_indices[1]]

    frac = Fraction(favorable, total)
    decimal_str = f"{frac.numerator / frac.denominator:.6f}".rstrip('0').rstrip('.')

    listing = ", ".join(pen_count(counts[i], colors[i]) for i in range(3))
    listing += f", остальные {colors[3][3]} и {colors[4][3]}, их поровну"

    ask1 = colors[ask_indices[0]][1]
    ask2 = colors[ask_indices[1]][1]

    condition_text = (
        f"В магазине канцтоваров продаётся {total} ручек: {listing}. "
        f"Найдите вероятность того, что случайно выбранная ручка будет "
        f"{ask1} или {ask2}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
