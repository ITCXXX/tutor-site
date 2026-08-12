# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=84: OGE7: Тип 14 — какое из √-чисел в (a;a+1)
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def generate_task():
    """
    №7 ОГЭ, Тип 14: «Какое из √a, √(a+1), √N, √M принадлежит (a; a+1)?»
    Алгоритм:
    1) границы интервала a, a+1;
    2) под корнями: 4 числа — a, a+1 (ловушки) и N (в (a², (a+1)²)) + M (вне).
    """
    a = random.randint(5, 9)
    b = a + 1

    N = random.randint(a * a + 1, b * b - 1)

    # M — вне интервала, близко к нему
    if random.random() < 0.5:
        M = random.randint(max(1, a * a - 3), a * a - 1)
    else:
        M = random.randint(b * b + 1, b * b + 3)
    if M == N:
        M = M - 1 if M > 1 else M + 1

    # Школково всегда ставит a, a+1 первыми
    if random.random() < 0.5:
        options = [a, b, N, M]
        pos = 3
    else:
        options = [a, b, M, N]
        pos = 4

    choices = [f"$\\sqrt{{{x}}}$" for x in options]
    nums_text = ", ".join(c for c in choices[:-1]) + f" и {choices[-1]}"
    condition_text = (
        rf"Какое из чисел {nums_text} принадлежит промежутку $({a};\;{b})$?"
    )

    return {
        "condition_text": condition_text,
        "choices": choices,
        "correct_answer": pos,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        for j, c in enumerate(t['choices']):
            mark = " ← " if j + 1 == t['correct_answer'] else "   "
            print(f"    {j+1}){mark}{c}")
