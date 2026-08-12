# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=16: OGE10: Такси
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    total = random.choice([8, 10, 16, 20, 25, 32, 40, 50])
    featured = random.randint(1, total - 2)
    remaining = total - featured
    split = random.randint(1, remaining - 1)
    second = split
    third = remaining - split

    colors = random.sample([
        "чёрный", "жёлтый", "зелёный", "белый", "синий", "красный"
    ], 3)

    ask_index = random.randint(0, 2)
    counts = [featured, second, third]
    ask_color = colors[ask_index]

    plural_map = {
        "чёрный":  ("чёрная", "чёрных",  "чёрных"),
        "жёлтый":  ("жёлтая", "жёлтых",  "жёлтых"),
        "зелёный": ("зелёная","зелёных", "зелёных"),
        "белый":   ("белая",  "белых",   "белых"),
        "синий":   ("синяя",  "синих",   "синих"),
        "красный": ("красная","красных", "красных"),
    }

    def color_form(color, n):
        one, few, many = plural_map[color]
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} {one}"
        else:
            return f"{n} {many}"

    neuter_map = {
        "чёрный":  "чёрное",
        "жёлтый":  "жёлтое",
        "зелёный": "зелёное",
        "белый":   "белое",
        "синий":   "синее",
        "красный": "красное",
    }

    frac = Fraction(counts[ask_index], total)
    decimal_value = frac.numerator / frac.denominator
    decimal_str = f"{decimal_value:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"В фирме такси в данный момент свободно {total} машин: "
        f"{color_form(colors[0], counts[0])}, "
        f"{color_form(colors[1], counts[1])} и "
        f"{color_form(colors[2], counts[2])}. "
        f"По вызову выехала одна из машин, случайно оказавшаяся ближе всего к заказчику. "
        f"Найдите вероятность того, что к нему приедет {neuter_map[ask_color]} такси. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
