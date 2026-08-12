# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=111: OGE13: Тип 8+9 — квадр. без x
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def _interval(left_inf, lv, lo, rv, ro, right_inf):
    if left_inf:
        l_str = r"(-\infty"
    else:
        l_str = ("(" if lo else "[") + str(lv)
    if right_inf:
        r_str = r"+\infty)"
    else:
        r_str = str(rv) + (")" if ro else "]")
    return rf"${l_str};\ {r_str}$"


def _union(a, b):
    return f"{a} $\\cup$ {b}"


def _is_strict(sign):
    return sign in ('<', '>')


def _build_ineq(k, r, sign):
    """LaTeX неравенства вида kx² ⋛ k·r²  или  kx² − k·r² ⋛ 0  (рандомно)."""
    c = k * r * r
    style = random.choice(['shift', 'compare'])
    if k == 1:
        x_part = "x^2"
    else:
        x_part = f"{k}x^2"
    if style == 'shift':
        return f"{x_part} - {c} {sign} 0"
    return f"{x_part} {sign} {c}"


def generate_task():
    """№13 ОГЭ, T8+T9: квадратное вида kx² ⋛ c (без слагаемого с x).
    Корни ±r целые. Дистракторы: ошибка с ±r² (не извлёк корень) и направление."""
    k = random.choice([1, 4, 9, 16, 25])
    r = random.randint(1, 10)
    sign = random.choice(['<', '>', r'\leqslant', r'\geqslant'])
    strict = _is_strict(sign)
    open_b = strict

    # Решение: kx² − kr² ⋛ 0 равносильно x² − r² ⋛ 0.
    if sign in ('>', r'\geqslant'):
        correct = _union(
            _interval(True, 0, False, -r, open_b, False),
            _interval(False, r, open_b, 0, False, True),
        )
    else:
        correct = _interval(False, -r, open_b, r, open_b, False)

    # Wrong direction
    if sign in ('>', r'\geqslant'):
        wr_dir = _interval(False, -r, open_b, r, open_b, False)
    else:
        wr_dir = _union(
            _interval(True, 0, False, -r, open_b, False),
            _interval(False, r, open_b, 0, False, True),
        )

    # Wrong: использовали r² вместо r (забыли извлечь корень)
    r2 = r * r
    if sign in ('>', r'\geqslant'):
        wr_root = _union(
            _interval(True, 0, False, -r2, open_b, False),
            _interval(False, r2, open_b, 0, False, True),
        )
    else:
        wr_root = _interval(False, -r2, open_b, r2, open_b, False)

    # Wrong both
    if sign in ('>', r'\geqslant'):
        wr_both = _interval(False, -r2, open_b, r2, open_b, False)
    else:
        wr_both = _union(
            _interval(True, 0, False, -r2, open_b, False),
            _interval(False, r2, open_b, 0, False, True),
        )

    options = [correct, wr_dir, wr_root, wr_both]
    options = list(dict.fromkeys(options))
    # При r=1, r²=1 — wrong root совпадает с правильным. Заменим на дополнительный.
    while len(options) < 4:
        rr = random.choice([n for n in range(1, 11) if n != r and n != r2])
        if sign in ('>', r'\geqslant'):
            cand = _union(
                _interval(True, 0, False, -rr, open_b, False),
                _interval(False, rr, open_b, 0, False, True),
            )
        else:
            cand = _interval(False, -rr, open_b, rr, open_b, False)
        if cand not in options:
            options.append(cand)
    options = options[:4]
    correct_label = options[0]
    random.shuffle(options)
    correct_pos = options.index(correct_label) + 1

    condition_text = (
        rf"Укажите решение неравенства $${_build_ineq(k, r, sign)}.$$"
    )
    return {
        "condition_text": condition_text,
        "choices": options,
        "correct_answer": str(correct_pos),
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T5[{i+1}] ---")
        print(t['condition_text'])
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}")
        print()
