# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=6: OGE9: Квадратное уравнение
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


def generate_task():
    r1 = random.randint(-20, 20)
    r2 = random.randint(-20, 20)
    b = -(r1 + r2)
    c = r1 * r2

    multiplier = 1
    if random.random() < 0.3:
        multiplier = random.choice([-5, -4, -3, -2, -1, 2, 3, 4, 5])

    a = 1 * multiplier
    b = b * multiplier
    c = c * multiplier

    ask_larger = random.choice([True, False])
    if ask_larger:
        answer = max(r1, r2)
        ask_text = "больший"
    else:
        answer = min(r1, r2)
        ask_text = "меньший"

    def format_equation(a, b, c):
        if a == 1:
            x2_part = "x^{2}"
        elif a == -1:
            x2_part = "-x^{2}"
        else:
            x2_part = f"{a}x^{{2}}"
        parts = [x2_part]
        if b > 0:
            parts.append(f"+ {b}x")
        elif b < 0:
            parts.append(f"- {abs(b)}x")
        if c > 0:
            parts.append(f"+ {c}")
        elif c < 0:
            parts.append(f"- {abs(c)}")
        return " ".join(parts) + " = 0"

    equation = format_equation(a, b, c)
    condition_text = (
        f"Найдите корни уравнения \\({equation}\\). "
        f"Если уравнение имеет более одного корня, "
        f"укажите {ask_text} из них."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
