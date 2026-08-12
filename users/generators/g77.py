# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=77: OGE7: Тип 6 — какое из чисел в [a;a+1]
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def generate_task():
    """
    №7 ОГЭ, Тип 6: «Какое из чисел принадлежит отрезку [a; a+1]?»
    4 дроби с одинаковым знаменателем d, ровно одна в [a; a+1].
    """
    a = random.randint(3, 9)
    b = a + 1
    d = random.choice([7, 9, 11, 12, 13, 14, 15, 17, 19])

    correct_num = random.randint(a * d + 1, b * d - 1)

    distractor_nums = []
    n_below = random.randint(0, 3)
    n_above = 3 - n_below
    for _ in range(n_below):
        num = random.randint((a - 2) * d + 1, a * d - 1)
        distractor_nums.append(num)
    for _ in range(n_above):
        num = random.randint(b * d + 1, (b + 2) * d - 1)
        distractor_nums.append(num)

    numerators = [correct_num] + distractor_nums
    random.shuffle(numerators)
    pos = numerators.index(correct_num) + 1

    fracs = [rf"\dfrac{{{n}}}{{{d}}}" for n in numerators]
    nums_text = ", ".join(f"${f}$" for f in fracs[:-1]) + f" и ${fracs[-1]}$"
    condition_text = (
        rf"Какое из чисел {nums_text} принадлежит отрезку $[{a};\;{b}]$?"
    )
    choices = [f"${f}$" for f in fracs]

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
