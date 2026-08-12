# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=73: OGE7: Тип 2 — какому промежутку принадлежит n/m
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
    №7 ОГЭ, Тип 2: «Какому из промежутков принадлежит число n/m?»
    Алгоритм по спеке: выбираем целевой промежуток через перекрёстное умножение.
    1) позиция правильного варианта pos ∈ [1, 4];
    2) D_min ∈ [0, 6] так, чтобы D = D_min + (pos-1) ∈ [1, 8];
    3) знаменатель m из {7, 9, 11, 13};
    4) числитель n с условием: D·m < 10·n < (D+1)·m, gcd(n, m) = 1.
    """
    pos = random.randint(1, 4)

    # допустимые диапазоны D_min для каждой позиции, чтобы D ∈ [1, 8]
    if pos == 1:
        D_min = random.randint(1, 6)
    elif pos == 2:
        D_min = random.randint(0, 6)
    elif pos == 3:
        D_min = random.randint(0, 6)
    else:
        D_min = random.randint(0, 5)

    D = D_min + (pos - 1)

    valid_ms = []
    for m in (7, 9, 11, 13):
        n_lo = D * m / 10
        n_hi = (D + 1) * m / 10
        ns = [n for n in range(int(n_lo) + 1, int(n_hi) + 1)
              if n_lo < n < n_hi and math.gcd(n, m) == 1]
        if ns:
            valid_ms.append((m, ns))

    m, ns = random.choice(valid_ms)
    n = random.choice(ns)

    def fmt(d):
        return f"0,{d}" if d > 0 else "0"

    choices = [
        f"$({fmt(D_min + i)};\\;{fmt(D_min + i + 1)})$"
        for i in range(4)
    ]

    condition_text = (
        rf"Какому из данных промежутков принадлежит число "
        rf"$\dfrac{{{n}}}{{{m}}}$?"
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
