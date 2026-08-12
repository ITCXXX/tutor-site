# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=74: OGE7: Тип 3 — какое число между двумя дробями
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
    №7 ОГЭ, Тип 3: «Какое число заключено между a/b и c/d?»
    Алгоритм:
    1) целевое десятичное D = K/10 (K ∈ [3, 30]);
    2) подбираем a/b — наибольшую дробь < D, но > (K-1)/10;
    3) подбираем c/d — наименьшую дробь > D, но < (K+1)/10;
    4) 4 варианта — последовательные десятичные шага 0,1.
    """
    DENOMS = [3, 5, 7, 8, 9, 11, 13, 14, 15, 17, 19]

    while True:
        K = random.randint(3, 30)

        # left bound a/b ∈ ((K-1)/10, K/10)
        valid_left = []
        for b in DENOMS:
            a = (K * b - 1) // 10
            if a > 0 and 10 * a > (K - 1) * b and math.gcd(a, b) == 1:
                valid_left.append((a, b))

        # right bound c/d ∈ (K/10, (K+1)/10)
        valid_right = []
        for d in DENOMS:
            c = K * d // 10 + 1
            if 10 * c < (K + 1) * d and math.gcd(c, d) == 1:
                valid_right.append((c, d))

        if valid_left and valid_right:
            break

    a, b = random.choice(valid_left)
    c, d = random.choice([(c, d) for (c, d) in valid_right if d != b] or valid_right)

    pos = random.randint(1, 4)
    K_min = K - (pos - 1)
    if K_min < 0:
        K_min = 0
        pos = K + 1

    def fmt(k):
        if k % 10 == 0:
            return f"{k // 10}"
        return f"{k // 10},{k % 10}"

    choices = [f"${fmt(K_min + i)}$" for i in range(4)]

    condition_text = (
        rf"Какое из следующих чисел заключено между числами "
        rf"$\dfrac{{{a}}}{{{b}}}$ и $\dfrac{{{c}}}{{{d}}}$?"
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
