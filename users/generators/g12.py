# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=12: OGE10: Ручка пишет хорошо
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    bad = random.randint(1, 20)
    bad_str = f"0,{bad:02d}"
    good = 100 - bad
    good_value = good / 100
    good_str = f"{good_value:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"Вероятность того, что новая шариковая ручка пишет плохо "
        f"(или не пишет), равна {bad_str}. Покупатель в магазине выбирает "
        f"одну шариковую ручку. Найдите вероятность того, что эта ручка "
        f"пишет хорошо. Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": good_str}
