# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=83: OGE7: Тип 13 — между какими числами √n
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def generate_task():
    """
    №7 ОГЭ, Тип 13: «Между какими числами заключено √n?»
    Алгоритм:
    1) граничные числа k и k+1 (k ∈ [4, 9]);
    2) диапазон n ∈ (k², (k+1)²);
    3) корень и 4 варианта.
    """
    k = random.randint(4, 9)
    n_min = k * k + 1
    n_max = (k + 1) ** 2 - 1
    n = random.randint(n_min, n_max)

    correct = (k, k + 1)

    # Плановые отвлекающие
    half = max(2, n // 2)
    third = max(2, n // 3)
    candidates = [
        (n - 1, n + 1),
        (half - 1, half + 1),
        (third - 1, third + 1),
    ]
    distractors = [c for c in candidates if c != correct and c[0] >= 1]
    distractors = list(dict.fromkeys(distractors))[:3]

    used = {correct, *distractors}
    while len(distractors) < 3:
        rk = random.randint(2, max(20, n // 4))
        cand = (rk, rk + 1)
        if cand not in used:
            distractors.append(cand)
            used.add(cand)

    options = [correct] + distractors
    random.shuffle(options)
    pos = options.index(correct) + 1

    choices = [f"${a}$ и ${b}$" for (a, b) in options]
    condition_text = rf"Между какими числами заключено число $\sqrt{{{n}}}$?"

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
