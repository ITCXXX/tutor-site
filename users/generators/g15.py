# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=15: OGE10: Лыжники из разных стран
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    country_pool = [
        ("России",      "из России"),
        ("Норвегии",    "из Норвегии"),
        ("Швеции",      "из Швеции"),
        ("Финляндии",   "из Финляндии"),
        ("Дании",       "из Дании"),
        ("Германии",    "из Германии"),
        ("США",         "из США"),
        ("Великобритании", "из Великобритании"),
        ("Эстонии",     "из Эстонии"),
        ("Латвии",      "из Латвии"),
        ("Литвы",       "из Литвы"),
    ]
    chosen = random.sample(country_pool, 3)
    total = random.choice([8, 10, 16, 20, 25, 32, 40, 50])

    count_a = random.randint(1, total - 2)
    remaining = total - count_a
    count_b = random.randint(1, remaining - 1)
    count_c = remaining - count_b
    counts = [count_a, count_b, count_c]

    ask_indices = random.sample([0, 1, 2], 2)
    ask_indices.sort()
    third_index = [i for i in [0, 1, 2] if i not in ask_indices][0]
    favorable = counts[ask_indices[0]] + counts[ask_indices[1]]

    frac = Fraction(favorable, total)
    decimal_value = frac.numerator / frac.denominator
    decimal_str = f"{decimal_value:.6f}".rstrip('0').rstrip('.')

    def athlete_form(n):
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} спортсмен"
        elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
            return f"{n} спортсмена"
        else:
            return f"{n} спортсменов"

    name_a = chosen[ask_indices[0]][0]
    name_b = chosen[ask_indices[1]][0]
    from_a = chosen[ask_indices[0]][1]
    from_b = chosen[ask_indices[1]][1]
    from_c = chosen[third_index][1]

    condition_text = (
        f"В лыжных гонках участвуют {athlete_form(counts[third_index])} {from_c}, "
        f"{athlete_form(counts[ask_indices[0]])} {from_a} "
        f"и {athlete_form(counts[ask_indices[1]])} {from_b}. "
        f"Порядок, в котором спортсмены стартуют, определяется жребием. "
        f"Найдите вероятность того, что первым будет стартовать спортсмен "
        f"{from_a} или {from_b}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
