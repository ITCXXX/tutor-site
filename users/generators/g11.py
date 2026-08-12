# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=11: OGE10: Фонарики
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


from fractions import Fraction

def generate_task():
    base_total = random.choice([10, 16, 20, 25, 32, 40, 50, 80, 100])
    base_broken = random.randint(1, min(10, base_total - 1))
    multiplier = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    total = base_total * multiplier
    broken = base_broken * multiplier
    working = total - broken

    ask_working = random.choice([True, False])
    if ask_working:
        favorable = working
        what = "окажется исправен"
    else:
        favorable = broken
        what = "окажется неисправен"

    frac = Fraction(favorable, total)
    decimal_value = frac.numerator / frac.denominator
    decimal_str = f"{decimal_value:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"В среднем из {total} карманных фонариков, поступивших в продажу, "
        f"{broken} неисправных. Найдите вероятность того, что выбранный "
        f"наудачу в магазине фонарик {what}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
