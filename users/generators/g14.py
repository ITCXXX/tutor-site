# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=14: OGE10: Пазлы детям
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    total = random.choice([10, 20, 25, 40, 50, 100])
    type_a_count = random.randint(1, total - 1)
    type_b_count = total - type_a_count

    themes = [
        ("с машинами",      "с видами городов"),
        ("с животными",     "с пейзажами"),
        ("с динозаврами",   "с замками"),
        ("со спортсменами", "с природой"),
        ("с самолётами",    "с морем"),
        ("с роботами",      "с цветами"),
    ]
    theme_a, theme_b = random.choice(themes)

    names = [
        ("Саша",   "Саше"),
        ("Миша",   "Мише"),
        ("Коля",   "Коле"),
        ("Петя",   "Пете"),
        ("Дима",   "Диме"),
        ("Серёжа", "Серёже"),
        ("Антон",  "Антону"),
        ("Маша",   "Маше"),
        ("Катя",   "Кате"),
        ("Аня",    "Ане"),
    ]
    name, name_dat = random.choice(names)

    ask_a = random.choice([True, False])
    if ask_a:
        favorable = type_a_count
        ask_theme = theme_a
    else:
        favorable = type_b_count
        ask_theme = theme_b

    frac = Fraction(favorable, total)
    decimal_str = f"{frac.numerator / frac.denominator:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"Родительский комитет закупил {total} пазлов для подарков детям, "
        f"из них {type_a_count} {theme_a} и {type_b_count} {theme_b}. "
        f"Подарки распределяются случайным образом, среди получателей есть {name}. "
        f"Найдите вероятность того, что {name_dat} достанется пазл {ask_theme}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
