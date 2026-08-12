# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=108: OGE13: Тип 2+5 — система, текст
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def _interval(left_inf, lv, lo, rv, ro, right_inf):
    """Возвращает LaTeX интервала.
       left_inf=True ⇒ слева −∞; иначе lv,lo (open?).
       right_inf=True ⇒ справа +∞; иначе rv,ro.
    """
    if left_inf:
        l_str = r"(-\infty"
    else:
        l_br = "(" if lo else "["
        l_str = f"{l_br}{lv}"
    if right_inf:
        r_str = r"+\infty)"
    else:
        r_br = ")" if ro else "]"
        r_str = f"{rv}{r_br}"
    return rf"${l_str};\ {r_str}$"


def _union(left, right):
    return f"{left} $\\cup$ {right}"


def _ineq_text(coef_x, b_const, sign, c_const):
    """LaTeX: 'A·x + B ⋛ C'. coef_x ∈ {1,2,3}; знак неравенства один из <, ≤, >, ≥."""
    parts = []
    if coef_x == 1:
        parts.append("x")
    else:
        parts.append(f"{coef_x}x")
    if b_const != 0:
        parts.append(("+ " if b_const > 0 else "- ") + str(abs(b_const)))
    lhs = " ".join(parts)
    return rf"{lhs} {sign} {c_const}"


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def _is_strict(sign):
    return sign in ('<', '>')


def generate_task():
    """№13 ОГЭ, T2+T5: система двух линейных неравенств → интервал текстом.

    Подформа A — оба неравенства одного направления (одностороннее решение).
    Подформа B — разные направления (ограниченный интервал).
    """
    subform = random.choice(['A', 'B'])

    if subform == 'A':
        # Оба знака одинаковые: оба ≥/> или оба ≤/<
        sign = random.choice(['<', '>', r'\leqslant', r'\geqslant'])
        # Две границы; обязательно различные
        while True:
            alpha = random.randint(-9, 9)
            beta = random.randint(-9, 9)
            if alpha != beta:
                break
        # Решение: ⋛ ≥/>: x ⋛ max(α, β); иначе x ⋛ min(α, β)
        if sign in ('>', r'\geqslant'):
            answer_bound = max(alpha, beta)
            wrong_bound = min(alpha, beta)
            answer_left_inf = False
        else:
            answer_bound = min(alpha, beta)
            wrong_bound = max(alpha, beta)
            answer_left_inf = True

        strict = _is_strict(sign)
        # 4 варианта: { (вн./нет, корень) × прав./не прав. направление } — упрощённо
        if answer_left_inf:
            correct = _interval(True, 0, False, answer_bound, strict, False)
            wrong_min_max = _interval(True, 0, False, wrong_bound, strict, False)
            wrong_dir = _interval(False, answer_bound, strict, 0, False, True)
            wrong_both = _interval(False, wrong_bound, strict, 0, False, True)
        else:
            correct = _interval(False, answer_bound, strict, 0, False, True)
            wrong_min_max = _interval(False, wrong_bound, strict, 0, False, True)
            wrong_dir = _interval(True, 0, False, answer_bound, strict, False)
            wrong_both = _interval(True, 0, False, wrong_bound, strict, False)

        options = [correct, wrong_min_max, wrong_dir, wrong_both]

        # Запись неравенств: каждое в виде «x − a ⋛ 0» или «x ⋛ a»; разнообразим.
        ineq1 = _build_ineq_with_root(alpha, sign)
        ineq2 = _build_ineq_with_root(beta, sign)

    else:
        # Подформа B: разные направления, ответ — отрезок [α; β]
        while True:
            alpha = random.randint(-8, 6)
            beta = random.randint(alpha + 2, 9)
            if alpha < beta:
                break
        # Знак выбираем: первое неравенство ≥/> (даст x ≥ α), второе ≤/< (даст x ≤ β)
        s_strict = random.choice([True, False])
        if s_strict:
            sign1 = '>'
            sign2 = '<'
        else:
            sign1 = r'\geqslant'
            sign2 = r'\leqslant'

        ineq1 = _build_ineq_with_root(alpha, sign1)
        ineq2 = _build_ineq_with_root(beta, sign2)

        correct = _interval(False, alpha, s_strict, beta, s_strict, False)
        wrong_union = _union(
            _interval(True, 0, False, alpha, s_strict, False),
            _interval(False, beta, s_strict, 0, False, True),
        )
        wrong_only_first = _interval(False, alpha, s_strict, 0, False, True)
        wrong_only_second = _interval(True, 0, False, beta, s_strict, False)

        options = [correct, wrong_union, wrong_only_first, wrong_only_second]

    random.shuffle(options)
    correct_pos = options.index(correct) + 1

    condition_text = (
        rf"Укажите решение системы неравенств "
        rf"$$\begin{{cases}}{ineq1},\\ {ineq2}.\end{{cases}}$$"
    )

    return {
        "condition_text": condition_text,
        "choices": options,
        "correct_answer": str(correct_pos),
    }


def _build_ineq_with_root(root, sign):
    """Возвращает LaTeX неравенства с корнем `root` и знаком `sign`,
    в одном из вариантов формы: x − a ⋛ 0, x + a ⋛ 0, ax + b ⋛ c,…"""
    style = random.choice(['shift_zero', 'simple', 'scaled'])

    if style == 'shift_zero':
        # x − root ⋛ 0  (или x + |root| ⋛ 0 при root<0)
        if root >= 0:
            lhs = f"x - {root}" if root != 0 else "x"
        else:
            lhs = f"x + {abs(root)}"
        return f"{lhs} {sign} 0"

    if style == 'simple':
        # x ⋛ root
        if root == 0:
            return f"x {sign} 0"
        if root > 0:
            return f"x {sign} {root}"
        return f"x {sign} {root}"  # отрицательный число — Python даст «-3»

    # scaled: A·x + B ⋛ C, где (C − B) / A = root
    A = random.choice([2, 3])
    B = random.choice([-6, -4, -2, 0, 2, 4, 6])
    C = A * root + B
    if abs(C) > 30:
        return f"x {sign} {root}"
    if A == 1:
        x_part = "x"
    else:
        x_part = f"{A}x"
    if B == 0:
        lhs = x_part
    elif B > 0:
        lhs = f"{x_part} + {B}"
    else:
        lhs = f"{x_part} - {abs(B)}"
    return f"{lhs} {sign} {C}"


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T2[{i+1}] ---")
        print(t['condition_text'])
        print("choices:")
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}\n")
