# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=110: OGE13: Тип 6+7 — квадр. факторизованное
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def _factor(root):
    if root > 0:
        return f"(x - {root})"
    return f"(x + {abs(root)})"


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


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def _is_strict(sign):
    return sign in ('<', '>')


def generate_task():
    """OGE13 T6+T7: factored quadratic (x +/- a)(x +/- b) <=>= 0."""
    while True:
        r1 = random.randint(-10, 10)
        r2 = random.randint(-10, 10)
        if r1 == 0 or r2 == 0 or r1 == r2:
            continue
        if r1 > r2:
            r1, r2 = r2, r1
        if r2 - r1 < 2:
            continue
        break

    sign = random.choice(['<', '>', r'\leqslant', r'\geqslant'])
    strict = _is_strict(sign)
    open_b = strict

    if sign in ('>', r'\geqslant'):
        correct = _union(
            _interval(True, 0, False, r1, open_b, False),
            _interval(False, r2, open_b, 0, False, True),
        )
    else:
        correct = _interval(False, r1, open_b, r2, open_b, False)

    if sign in ('>', r'\geqslant'):
        wr_dir = _interval(False, r1, open_b, r2, open_b, False)
    else:
        wr_dir = _union(
            _interval(True, 0, False, r1, open_b, False),
            _interval(False, r2, open_b, 0, False, True),
        )

    s1, s2 = sorted([-r1, -r2])
    if sign in ('>', r'\geqslant'):
        wr_root = _union(
            _interval(True, 0, False, s1, open_b, False),
            _interval(False, s2, open_b, 0, False, True),
        )
    else:
        wr_root = _interval(False, s1, open_b, s2, open_b, False)

    if sign in ('>', r'\geqslant'):
        wr_both = _interval(False, s1, open_b, s2, open_b, False)
    else:
        wr_both = _union(
            _interval(True, 0, False, s1, open_b, False),
            _interval(False, s2, open_b, 0, False, True),
        )

    options = [correct, wr_dir, wr_root, wr_both]
    options = list(dict.fromkeys(options))
    while len(options) < 4:
        extra_root = random.choice([r for r in range(-10, 11)
                                    if r not in (r1, r2, -r1, -r2, 0)])
        if sign in ('>', r'\geqslant'):
            cand = _union(
                _interval(True, 0, False, min(r1, extra_root), open_b, False),
                _interval(False, max(r2, extra_root), open_b, 0, False, True),
            )
        else:
            lo, hi = sorted([r1, extra_root])
            cand = _interval(False, lo, open_b, hi, open_b, False)
        if cand not in options:
            options.append(cand)
    options = options[:4]
    correct_label = options[0]
    random.shuffle(options)
    correct_pos = options.index(correct_label) + 1

    condition_text = (
        rf"Укажите решение неравенства $${_factor(r1)}{_factor(r2)} {sign} 0.$$"
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
        print(f"--- T4[{i+1}] ---")
        print(t['condition_text'])
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}\n")
