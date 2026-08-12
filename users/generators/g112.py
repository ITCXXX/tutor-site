# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=112: OGE13: Тип 10+11 — квадр. со свободным x
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


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def _build_ineq(c, sign):
    """LaTeX вида cx − x² ⋛ 0 или x² − cx ⋛ 0 (рандомно)."""
    style = random.choice(['minus_x2', 'x2_minus'])
    if style == 'minus_x2':
        # cx − x² ⋛ 0
        if c == 1:
            cx = "x"
        elif c == -1:
            cx = "-x"
        else:
            cx = f"{c}x"
        return f"{cx} - x^2 {sign} 0"
    # x² − cx ⋛ 0  (форма «нормализованная»)
    if c == 0:
        return f"x^2 {sign} 0"
    if c > 0:
        cx = "x" if c == 1 else f"{c}x"
        return f"x^2 - {cx} {sign} 0"
    # c < 0:  x² − (−|c|)x = x² + |c|x
    cx = "x" if c == -1 else f"{abs(c)}x"
    return f"x^2 + {cx} {sign} 0"


def _solution_in_form_x2_minus_cx(c, sign):
    """Возвращает корректный интервал решения для x² − cx ⋛ 0 в виде LaTeX-строки.
    Корни — 0 и c. Для cx − x² ⋛ 0 эквивалентно x² − cx ⋚ 0 (знак противоположный)."""
    strict = _is_strict(sign)
    open_b = strict
    r1, r2 = sorted([0, c])
    if sign in ('>', r'\geqslant'):
        return _union(
            _interval(True, 0, False, r1, open_b, False),
            _interval(False, r2, open_b, 0, False, True),
        )
    return _interval(False, r1, open_b, r2, open_b, False)


def generate_task():
    """№13 ОГЭ, T10+T11: квадратное вида cx − x² ⋛ 0 (или x² − cx ⋛ 0).
    Корни 0 и c (целое). Дистракторы — ±c, ±направление."""
    c = random.choice([n for n in range(-10, 11) if n != 0])
    sign = random.choice(['<', '>', r'\leqslant', r'\geqslant'])
    strict = _is_strict(sign)
    open_b = strict

    # Запоминаем «исходный» вид. Если выбрали cx − x², эффективно знак инвертируется
    # (поскольку −(x² − cx) ⋛ 0 ⇔ x² − cx ⋚ 0). Чтобы корректно посчитать ответ,
    # перейдём к нормализованной форме x² − cx ⋚ 0.
    style = random.choice(['minus_x2', 'x2_minus'])
    if style == 'minus_x2':
        text_ineq = _build_ineq_explicit(c, sign, 'minus_x2')
        eff_sign = _flip(sign)
    else:
        text_ineq = _build_ineq_explicit(c, sign, 'x2_minus')
        eff_sign = sign

    correct = _solution_in_form_x2_minus_cx(c, eff_sign)

    # Дистрактор 1: противоположное направление
    wr_dir = _solution_in_form_x2_minus_cx(c, _flip(eff_sign))
    # Дистрактор 2: с −c вместо c
    wr_root = _solution_in_form_x2_minus_cx(-c, eff_sign)
    # Дистрактор 3: −c + противоположное направление
    wr_both = _solution_in_form_x2_minus_cx(-c, _flip(eff_sign))

    options = [correct, wr_dir, wr_root, wr_both]
    options = list(dict.fromkeys(options))
    while len(options) < 4:
        cc = random.choice([n for n in range(-10, 11) if n not in (0, c, -c)])
        cand = _solution_in_form_x2_minus_cx(cc, eff_sign)
        if cand not in options:
            options.append(cand)
    options = options[:4]
    correct_label = options[0]
    random.shuffle(options)
    correct_pos = options.index(correct_label) + 1

    condition_text = rf"Укажите решение неравенства $${text_ineq}.$$"
    return {
        "condition_text": condition_text,
        "choices": options,
        "correct_answer": str(correct_pos),
    }


def _build_ineq_explicit(c, sign, style):
    if style == 'minus_x2':
        if c == 1:
            cx = "x"
        elif c == -1:
            cx = "-x"
        else:
            cx = f"{c}x"
        return f"{cx} - x^2 {sign} 0"
    # x² − cx ⋛ 0
    if c > 0:
        cx = "x" if c == 1 else f"{c}x"
        return f"x^2 - {cx} {sign} 0"
    cx = "x" if c == -1 else f"{abs(c)}x"
    return f"x^2 + {cx} {sign} 0"


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T6[{i+1}] ---")
        print(t['condition_text'])
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}\n")
