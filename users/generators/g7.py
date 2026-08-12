# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=7: OGE9: Квадратное уравнение без свободного члена
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    r = random.choice([i for i in range(-10, 11) if i != 0])
    a = random.randint(3, 15)
    b = a * r
    r1, r2 = 0, r

    ask_larger = random.choice([True, False])
    if ask_larger:
        answer = max(r1, r2)
        ask_text = "больший"
    else:
        answer = min(r1, r2)
        ask_text = "меньший"

    equation = f"{a}x^{{2}} = {b}x"
    condition_text = (
        f"Решите уравнение \\({equation}\\). "
        f"Если уравнение имеет более одного корня, "
        f"в ответ запишите {ask_text} из корней."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
