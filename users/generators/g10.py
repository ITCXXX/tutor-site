# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=10: OGE10: Билеты на экзамене
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    total = random.choice([10, 20, 25, 40, 50, 100])
    max_not = max(1, total // 3)
    not_learned = random.randint(1, max_not)
    learned = total - not_learned

    ask_learned = random.choice([True, False])
    if ask_learned:
        favorable = learned
        what = "выученный билет"
    else:
        favorable = not_learned
        what = "невыученный билет"

    frac = Fraction(favorable, total)
    decimal_str = f"{frac.numerator / frac.denominator:.6f}".rstrip('0').rstrip('.')

    names = ["Яша", "Саша", "Миша", "Коля", "Петя", "Дима", "Серёжа", "Антон"]
    name = random.choice(names)

    condition_text = (
        f"На экзамене {total} билетов, {name} не выучил "
        f"{not_learned} из них. Найдите вероятность того, что ему попадётся "
        f"{what}. Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
