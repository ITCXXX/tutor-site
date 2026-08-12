# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=8: OGE9: Разность квадратов
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    a = random.randint(1, 20)
    r1 = a
    r2 = -a

    ask_larger = random.choice([True, False])
    if ask_larger:
        answer = max(r1, r2)
        ask_text = "больший"
    else:
        answer = min(r1, r2)
        ask_text = "меньший"

    equation = f"x^{{2}} - {a**2} = 0"
    condition_text = (
        f"Найдите корни уравнения \\({equation}\\). "
        f"Если уравнение имеет более одного корня, "
        f"укажите {ask_text} из них."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
