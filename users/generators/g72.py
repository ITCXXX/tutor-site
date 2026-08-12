# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=72: OGE7: Тип 1 — между какими целыми n/m
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
import math


def generate_task():
    """
    №7 ОГЭ, Тип 1: «Между какими целыми числами заключено число n/m?»
    Алгоритм по спеке пользователя:
    1) знаменатель m > 6 (берём из [7, 19]);
    2) число k ∈ (5, 14), т.е. k ∈ [6, 13] — нижняя граница пары (k, k+1);
    3) n = m*k + δ, где δ ∈ [1, m-1], gcd(δ, m) = 1;
    4) случайно выбираем позицию правильного ответа среди 4 вариантов.
    """
    m = random.randint(7, 19)
    k = random.randint(6, 13)
    coprime_deltas = [d for d in range(1, m) if math.gcd(d, m) == 1]
    delta = random.choice(coprime_deltas)
    n = m * k + delta

    pos = random.randint(1, 4)
    start = k - (pos - 1)
    options = [(start + i, start + i + 1) for i in range(4)]
    choices = [f"${a}$ и ${b}$" for (a, b) in options]

    condition_text = (
        rf"Между какими целыми числами заключено число $\dfrac{{{n}}}{{{m}}}$?"
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
