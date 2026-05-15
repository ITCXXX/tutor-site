# -*- coding: utf-8 -*-
"""
Management command: создаёт 8 ProblemGenerator-ов и Assignment-ов под урок
«Задание 13» курса ОГЭ. Тема — «Неравенства, системы неравенств».
Тип ответа: single_choice (4 варианта).

Идемпотентен: ре-ран не плодит дубли и не переписывает переименованный title
(поиск Assignment по lesson+order, а не по title).

Usage:
    python manage.py seed_oge13
    python manage.py seed_oge13 --clear   # снести и пересоздать
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Код генераторов
# ──────────────────────────────────────────────────────────────────────────────


GEN_T1 = r'''
import random


def _interval_str(boundary, sign):
    """Возвращает LaTeX интервала вида (-\\infty;\\ a) или [a;\\ +\\infty)."""
    b = str(boundary)
    if sign == '<':
        return rf"$(-\infty;\ {b})$"
    if sign == r'\leqslant':
        return rf"$(-\infty;\ {b}]$"
    if sign == '>':
        return rf"$({b};\ +\infty)$"
    if sign == r'\geqslant':
        return rf"$[{b};\ +\infty)$"
    raise ValueError(sign)


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def _term(coef):
    """Возвращает LaTeX для коэффициента при x: '3x', '-x', 'x', '-3x'."""
    if coef == 1: return "x"
    if coef == -1: return "-x"
    return f"{coef}x"


def _build_side(coef_x, const):
    """Собирает LaTeX вида 'ax + b', 'ax', 'b'."""
    parts = []
    if coef_x != 0:
        parts.append(_term(coef_x))
    if const != 0 or coef_x == 0:
        if not parts:
            parts.append(str(const))
        else:
            parts.append(("+ " if const > 0 else "- ") + str(abs(const)))
    return " ".join(parts) if parts else "0"


def generate_task():
    """№13 ОГЭ, Тип 1: линейное неравенство ax + b ⋛ cx + d → выбор интервала.

    Параметры подобраны так, чтобы типичная ошибка переноса константы через знак
    неравенства давала граничную точку −x₀, а забытый «переворот» при делении на
    отрицательный коэффициент — обратное направление. 4 варианта = ±x₀ × ±знак.
    """
    while True:
        x0 = random.choice([n for n in range(-9, 10) if n not in (-1, 0, 1)])
        k = random.choice([-5, -4, -3, -2, 2, 3, 4, 5])
        a = random.choice([-3, -2, -1, 1, 2, 3])
        c = a - k
        if c == 0 or c == a:
            continue
        # Из ax + b ⋛ cx + d следует kx ⋛ d − b. Чтобы ответ был x ⋛̃ x₀,
        # нужно d − b = k·x₀. При этом ошибка переноса (не сменили знак)
        # даёт граничную точку −x₀.
        side = random.choice(['left', 'right'])
        if side == 'left':
            b = -k * x0
            d = 0
        else:
            b = 0
            d = k * x0
        if abs(b) > 60 or abs(d) > 60:
            continue
        break

    sign_problem = random.choice(['<', '>', r'\leqslant', r'\geqslant'])
    sign_answer = sign_problem if k > 0 else _flip(sign_problem)

    lhs = _build_side(a, b)
    rhs = _build_side(c, d)
    condition_text = (
        rf"Укажите решение неравенства $${lhs} {sign_problem} {rhs}.$$"
    )

    correct_label = _interval_str(x0, sign_answer)
    options = [
        correct_label,
        _interval_str(-x0, sign_answer),
        _interval_str(x0, _flip(sign_answer)),
        _interval_str(-x0, _flip(sign_answer)),
    ]
    random.shuffle(options)
    correct_pos = options.index(correct_label) + 1

    return {
        "condition_text": condition_text,
        "choices": options,
        "correct_answer": str(correct_pos),
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T1[{i+1}] ---")
        print(t['condition_text'])
        print("choices:")
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}\n")
'''


GEN_T2 = r'''
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
'''


GEN_T3 = r'''
import random


def _new_pid():
    return 'h' + str(random.randint(100000, 999999))


def axis_svg(low, high, labeled, region, width=420, height=70):
    """Числовая прямая [low; high] со штриховкой над участком и подписями.
    labeled: list of (value, str_label).
    region:
        ('one', 'left',  v, closed)   — заштрихована левая полупрямая до v
        ('one', 'right', v, closed)
        ('between', a, b, ac, bc)
        ('outside', a, b, ac, bc)
        ('empty',)                    — без штриховки
    """
    pad = 30
    line_y = height // 2 + 6
    plot_w = width - 2 * pad

    def x_of(v):
        return pad + (v - low) / (high - low) * plot_w

    pid = _new_pid()
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" style="max-width:{width}px;display:block;margin:0.5em auto;'
        f'color:currentColor;">',
        f'<defs><pattern id="{pid}" patternUnits="userSpaceOnUse" width="6" height="6" '
        f'patternTransform="rotate(-60)">'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" stroke-width="1"/>'
        f'</pattern></defs>',
    ]
    hatch_h = 14

    def band(x0, x1):
        if x1 - x0 < 0.5:
            return ''
        return (f'<rect x="{x0:.1f}" y="{line_y - hatch_h}" '
                f'width="{x1 - x0:.1f}" height="{hatch_h}" fill="url(#{pid})"/>')

    def circle(x, closed):
        if closed:
            return f'<circle cx="{x:.1f}" cy="{line_y}" r="4.5" fill="currentColor"/>'
        return (f'<circle cx="{x:.1f}" cy="{line_y}" r="4.5" fill="white" '
                f'stroke="currentColor" stroke-width="1.6"/>')

    rtype = region[0]
    if rtype == 'one':
        side, val, closed = region[1], region[2], region[3]
        vx = x_of(val)
        if side == 'left':
            parts.append(band(pad - 15, vx))
        else:
            parts.append(band(vx, width - pad + 5))
    elif rtype == 'between':
        a, b, ac, bc = region[1:5]
        parts.append(band(x_of(a), x_of(b)))
    elif rtype == 'outside':
        a, b, ac, bc = region[1:5]
        parts.append(band(pad - 15, x_of(a)))
        parts.append(band(x_of(b), width - pad + 5))
    # 'empty' — без штриховки

    # Сама ось
    parts.append(
        f'<line x1="{pad - 15}" y1="{line_y}" x2="{width - pad + 5}" y2="{line_y}" '
        f'stroke="currentColor" stroke-width="1.5"/>'
    )
    parts.append(
        f'<polygon points="{width - pad + 15},{line_y} {width - pad + 5},{line_y - 5} '
        f'{width - pad + 5},{line_y + 5}" fill="currentColor"/>'
    )

    # Точки на границах
    if rtype == 'one':
        side, val, closed = region[1], region[2], region[3]
        parts.append(circle(x_of(val), closed))
    elif rtype in ('between', 'outside'):
        a, b, ac, bc = region[1:5]
        parts.append(circle(x_of(a), ac))
        parts.append(circle(x_of(b), bc))

    # Подписи
    for v, label in labeled:
        parts.append(
            f'<text x="{x_of(v):.1f}" y="{line_y + 22}" text-anchor="middle" '
            f'font-family="Times New Roman, serif" font-size="16" font-style="italic" '
            f'fill="currentColor">{label}</text>'
        )

    parts.append('</svg>')
    return ''.join(parts)


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def _is_strict(sign):
    return sign in ('<', '>')


def _build_ineq_with_root(root, sign):
    style = random.choice(['shift_zero', 'simple', 'scaled'])
    if style == 'shift_zero':
        if root >= 0:
            lhs = f"x - {root}" if root != 0 else "x"
        else:
            lhs = f"x + {abs(root)}"
        return f"{lhs} {sign} 0"
    if style == 'simple':
        return f"x {sign} {root}"
    # scaled
    A = random.choice([2, 3])
    B = random.choice([-6, -4, -2, 0, 2, 4, 6])
    C = A * root + B
    if abs(C) > 30:
        return f"x {sign} {root}"
    x_part = "x" if A == 1 else f"{A}x"
    if B == 0:
        lhs = x_part
    elif B > 0:
        lhs = f"{x_part} + {B}"
    else:
        lhs = f"{x_part} - {abs(B)}"
    return f"{lhs} {sign} {C}"


def _axis_for_region(region, low, high, labeled):
    """Шорткат: передаёт нашу регионовую модель в axis_svg."""
    return axis_svg(low, high, labeled, region)


def generate_task():
    """№13 ОГЭ, T3+T4: система двух линейных неравенств → выбор картинки.

    Подформа A — оба знака одинаковые (одностороннее решение).
    Подформа B — разные знаки (ограниченный отрезок).
    Подформа C — разные знаки, но альфа > бета (нет решений).
    """
    subform = random.choice(['A', 'A', 'B', 'B', 'C'])  # B и A чаще, C редко

    strict = random.choice([True, False])

    if subform == 'A':
        sign = random.choice(['>', r'\geqslant']) if random.random() < 0.5 else random.choice(['<', r'\leqslant'])
        if strict:
            sign = '>' if sign in ('>', r'\geqslant') else '<'
        else:
            sign = r'\geqslant' if sign in ('>', r'\geqslant') else r'\leqslant'

        while True:
            alpha = random.randint(-9, 9)
            beta = random.randint(-9, 9)
            if alpha != beta:
                break

        if sign in ('>', r'\geqslant'):
            answer_b = max(alpha, beta)
            wrong_b = min(alpha, beta)
            ans_left_inf = False
        else:
            answer_b = min(alpha, beta)
            wrong_b = max(alpha, beta)
            ans_left_inf = True

        # 4 региона: правильный + 3 ошибки
        if ans_left_inf:
            correct_region = ('one', 'left', answer_b, not strict)
            wr_min_max = ('one', 'left', wrong_b, not strict)
            wr_dir = ('one', 'right', answer_b, not strict)
            wr_both = ('one', 'right', wrong_b, not strict)
        else:
            correct_region = ('one', 'right', answer_b, not strict)
            wr_min_max = ('one', 'right', wrong_b, not strict)
            wr_dir = ('one', 'left', answer_b, not strict)
            wr_both = ('one', 'left', wrong_b, not strict)

        regions = [correct_region, wr_min_max, wr_dir, wr_both]
        labeled_pts = [(alpha, str(alpha)), (beta, str(beta))]
        ineq1 = _build_ineq_with_root(alpha, sign)
        ineq2 = _build_ineq_with_root(beta, sign)
        low = min(alpha, beta) - 3
        high = max(alpha, beta) + 3

    elif subform == 'B':
        while True:
            alpha = random.randint(-8, 6)
            beta = random.randint(alpha + 2, 9)
            if alpha < beta:
                break
        sign1 = '>' if strict else r'\geqslant'
        sign2 = '<' if strict else r'\leqslant'
        ineq1 = _build_ineq_with_root(alpha, sign1)
        ineq2 = _build_ineq_with_root(beta, sign2)

        correct_region = ('between', alpha, beta, not strict, not strict)
        wr_outside = ('outside', alpha, beta, not strict, not strict)
        wr_only_first = ('one', 'right', alpha, not strict)
        wr_only_second = ('one', 'left', beta, not strict)
        regions = [correct_region, wr_outside, wr_only_first, wr_only_second]
        labeled_pts = [(alpha, str(alpha)), (beta, str(beta))]
        low = alpha - 3
        high = beta + 3

    else:  # 'C' — нет решений
        # `x ≥ alpha, x ≤ beta` с alpha > beta → пусто.
        while True:
            alpha = random.randint(-3, 9)
            beta = random.randint(-9, alpha - 2)
            if alpha > beta:
                break
        sign1 = '>' if strict else r'\geqslant'
        sign2 = '<' if strict else r'\leqslant'
        ineq1 = _build_ineq_with_root(alpha, sign1)
        ineq2 = _build_ineq_with_root(beta, sign2)
        # Правильный — пустое множество. Дистракторы — обычные ответы.
        correct_region = ('empty',)
        wr_int = ('between', beta, alpha, not strict, not strict)  # «забыл, что α > β»
        wr_only_first = ('one', 'right', alpha, not strict)
        wr_only_second = ('one', 'left', beta, not strict)
        regions = [correct_region, wr_int, wr_only_first, wr_only_second]
        labeled_pts = [(alpha, str(alpha)), (beta, str(beta))]
        low = min(alpha, beta) - 3
        high = max(alpha, beta) + 3

    correct_region = regions[0]
    random.shuffle(regions)
    correct_pos = regions.index(correct_region) + 1

    options_svg = [_axis_for_region(r, low, high, labeled_pts) for r in regions]
    condition_text = (
        rf"Укажите решение системы неравенств "
        rf"$$\begin{{cases}}{ineq1},\\ {ineq2}.\end{{cases}}$$"
    )
    return {
        "condition_text": condition_text,
        "choices": options_svg,
        "correct_answer": str(correct_pos),
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"--- T3[{i+1}] ---")
        print(t['condition_text'])
        print(f"correct: {t['correct_answer']}")
        print("choices: 4 SVG (длины: " + ', '.join(str(len(c)) for c in t['choices']) + ")")
        print()
'''


GEN_T4 = r'''
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
'''


GEN_T5 = r'''
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
'''


GEN_T6 = r'''
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
'''


GEN_T7 = r'''
import random


def _new_pid():
    return 'h' + str(random.randint(100000, 999999))


def axis_svg(low, high, labeled, region, width=420, height=70):
    pad = 30
    line_y = height // 2 + 6
    plot_w = width - 2 * pad

    def x_of(v):
        return pad + (v - low) / (high - low) * plot_w

    pid = _new_pid()
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" style="max-width:{width}px;display:block;margin:0.5em auto;'
        f'color:currentColor;">',
        f'<defs><pattern id="{pid}" patternUnits="userSpaceOnUse" width="6" height="6" '
        f'patternTransform="rotate(-60)">'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" stroke-width="1"/>'
        f'</pattern></defs>',
    ]
    hatch_h = 14

    def band(x0, x1):
        if x1 - x0 < 0.5:
            return ''
        return (f'<rect x="{x0:.1f}" y="{line_y - hatch_h}" '
                f'width="{x1 - x0:.1f}" height="{hatch_h}" fill="url(#{pid})"/>')

    def circle(x, closed):
        if closed:
            return f'<circle cx="{x:.1f}" cy="{line_y}" r="4.5" fill="currentColor"/>'
        return (f'<circle cx="{x:.1f}" cy="{line_y}" r="4.5" fill="white" '
                f'stroke="currentColor" stroke-width="1.6"/>')

    rtype = region[0]
    if rtype == 'one':
        side, val, closed = region[1], region[2], region[3]
        vx = x_of(val)
        if side == 'left':
            parts.append(band(pad - 15, vx))
        else:
            parts.append(band(vx, width - pad + 5))
    elif rtype == 'between':
        a, b, ac, bc = region[1:5]
        parts.append(band(x_of(a), x_of(b)))
    elif rtype == 'outside':
        a, b, ac, bc = region[1:5]
        parts.append(band(pad - 15, x_of(a)))
        parts.append(band(x_of(b), width - pad + 5))

    parts.append(
        f'<line x1="{pad - 15}" y1="{line_y}" x2="{width - pad + 5}" y2="{line_y}" '
        f'stroke="currentColor" stroke-width="1.5"/>'
    )
    parts.append(
        f'<polygon points="{width - pad + 15},{line_y} {width - pad + 5},{line_y - 5} '
        f'{width - pad + 5},{line_y + 5}" fill="currentColor"/>'
    )

    if rtype == 'one':
        side, val, closed = region[1], region[2], region[3]
        parts.append(circle(x_of(val), closed))
    elif rtype in ('between', 'outside'):
        a, b, ac, bc = region[1:5]
        parts.append(circle(x_of(a), ac))
        parts.append(circle(x_of(b), bc))

    for v, label in labeled:
        parts.append(
            f'<text x="{x_of(v):.1f}" y="{line_y + 22}" text-anchor="middle" '
            f'font-family="Times New Roman, serif" font-size="16" font-style="italic" '
            f'fill="currentColor">{label}</text>'
        )
    parts.append('</svg>')
    return ''.join(parts)


def _is_strict(sign):
    return sign in ('<', '>')


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def _solve(form, a, sign):
    """Возвращает регион (для axis_svg) и набор подписей точек.
    form='ax':  x² − a·x ⋛ 0 → корни 0 и a.
    form='a2':  x² − a² ⋛ 0 → корни ±a.
    """
    strict = _is_strict(sign)
    open_b = strict
    if form == 'ax':
        r1, r2 = sorted([0, a])
    else:
        r1, r2 = -a, a
    if sign in ('>', r'\geqslant'):
        return ('outside', r1, r2, open_b, open_b), [(r1, str(r1)), (r2, str(r2))]
    return ('between', r1, r2, open_b, open_b), [(r1, str(r1)), (r2, str(r2))]


def _ineq_text(form, a, sign):
    """LaTeX неравенства: 'x^2 - a·x ⋛ 0' или 'x^2 - a^2 ⋛ 0'."""
    if form == 'ax':
        ax_part = "x" if a == 1 else f"{a}x"
        return rf"$x^2 - {ax_part} {sign} 0$"
    a2 = a * a
    return rf"$x^2 - {a2} {sign} 0$"


def generate_task():
    """№13 ОГЭ, Тип 12: по картинке выбрать одно из 4 неравенств вида
    x² − a·x ⋛ 0 или x² − a² ⋛ 0."""
    a = random.randint(2, 9)
    form_correct = random.choice(['ax', 'a2'])
    sign_correct = random.choice(['<', '>', r'\leqslant', r'\geqslant'])

    region, labeled = _solve(form_correct, a, sign_correct)
    # Картинка — диапазон оси
    if form_correct == 'ax':
        roots = sorted([0, a])
    else:
        roots = [-a, a]
    low = roots[0] - max(3, abs(a) // 2 + 1)
    high = roots[1] + max(3, abs(a) // 2 + 1)
    svg = axis_svg(low, high, labeled, region)

    # 4 варианта: декартово произведение {ax, a2} × {sign, flip}.
    sign_flipped = _flip(sign_correct)
    opt_correct = _ineq_text(form_correct, a, sign_correct)
    opt_form_other = _ineq_text('a2' if form_correct == 'ax' else 'ax', a, sign_correct)
    opt_sign_other = _ineq_text(form_correct, a, sign_flipped)
    opt_both = _ineq_text('a2' if form_correct == 'ax' else 'ax', a, sign_flipped)

    options = [opt_correct, opt_form_other, opt_sign_other, opt_both]
    random.shuffle(options)
    correct_pos = options.index(opt_correct) + 1

    condition_text = (
        rf"Укажите неравенство, решение которого изображено на рисунке."
        f"{svg}"
    )
    return {
        "condition_text": condition_text,
        "choices": options,
        "correct_answer": str(correct_pos),
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"--- T7[{i+1}] ---")
        print(t['condition_text'][:120], '...')
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}\n")
'''


GEN_T8 = r'''
import random


def _new_pid():
    return 'h' + str(random.randint(100000, 999999))


def axis_svg(low, high, labeled, region, width=420, height=70):
    pad = 30
    line_y = height // 2 + 6
    plot_w = width - 2 * pad

    def x_of(v):
        return pad + (v - low) / (high - low) * plot_w

    pid = _new_pid()
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" style="max-width:{width}px;display:block;margin:0.5em auto;'
        f'color:currentColor;">',
        f'<defs><pattern id="{pid}" patternUnits="userSpaceOnUse" width="6" height="6" '
        f'patternTransform="rotate(-60)">'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" stroke-width="1"/>'
        f'</pattern></defs>',
    ]
    hatch_h = 14

    def band(x0, x1):
        if x1 - x0 < 0.5:
            return ''
        return (f'<rect x="{x0:.1f}" y="{line_y - hatch_h}" '
                f'width="{x1 - x0:.1f}" height="{hatch_h}" fill="url(#{pid})"/>')

    def circle(x, closed):
        if closed:
            return f'<circle cx="{x:.1f}" cy="{line_y}" r="4.5" fill="currentColor"/>'
        return (f'<circle cx="{x:.1f}" cy="{line_y}" r="4.5" fill="white" '
                f'stroke="currentColor" stroke-width="1.6"/>')

    rtype = region[0]
    if rtype == 'between':
        a, b, ac, bc = region[1:5]
        parts.append(band(x_of(a), x_of(b)))
    elif rtype == 'outside':
        a, b, ac, bc = region[1:5]
        parts.append(band(pad - 15, x_of(a)))
        parts.append(band(x_of(b), width - pad + 5))

    parts.append(
        f'<line x1="{pad - 15}" y1="{line_y}" x2="{width - pad + 5}" y2="{line_y}" '
        f'stroke="currentColor" stroke-width="1.5"/>'
    )
    parts.append(
        f'<polygon points="{width - pad + 15},{line_y} {width - pad + 5},{line_y - 5} '
        f'{width - pad + 5},{line_y + 5}" fill="currentColor"/>'
    )

    if rtype in ('between', 'outside'):
        a, b, ac, bc = region[1:5]
        parts.append(circle(x_of(a), ac))
        parts.append(circle(x_of(b), bc))

    for v, label in labeled:
        parts.append(
            f'<text x="{x_of(v):.1f}" y="{line_y + 22}" text-anchor="middle" '
            f'font-family="Times New Roman, serif" font-size="16" font-style="italic" '
            f'fill="currentColor">{label}</text>'
        )
    parts.append('</svg>')
    return ''.join(parts)


def _is_strict(sign):
    return sign in ('<', '>')


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def generate_task():
    """№13 ОГЭ, Тип 13: по картинке выбрать одно из 4 неравенств вида
    x² ± a² ⋛ 0. Правильный — строго x² − a² с подходящим знаком (картинку
    «всё/пусто» не рисуем)."""
    a = random.randint(1, 9)
    sign = random.choice(['<', '>', r'\leqslant', r'\geqslant'])
    strict = _is_strict(sign)
    open_b = strict

    if sign in ('>', r'\geqslant'):
        region = ('outside', -a, a, open_b, open_b)
    else:
        region = ('between', -a, a, open_b, open_b)
    labeled = [(-a, str(-a)), (a, str(a))]
    low = -a - 3
    high = a + 3
    svg = axis_svg(low, high, labeled, region)

    a2 = a * a
    sign_flip = _flip(sign)
    opt_correct = rf"$x^2 - {a2} {sign} 0$"
    opt_plus_same = rf"$x^2 + {a2} {sign} 0$"
    opt_minus_flip = rf"$x^2 - {a2} {sign_flip} 0$"
    opt_plus_flip = rf"$x^2 + {a2} {sign_flip} 0$"

    options = [opt_correct, opt_plus_same, opt_minus_flip, opt_plus_flip]
    random.shuffle(options)
    correct_pos = options.index(opt_correct) + 1

    condition_text = (
        rf"Укажите неравенство, решение которого изображено на рисунке."
        f"{svg}"
    )
    return {
        "condition_text": condition_text,
        "choices": options,
        "correct_answer": str(correct_pos),
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"--- T8[{i+1}] ---")
        print(t['condition_text'][:120], '...')
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}\n")
'''


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    # (order, gen_name, asg_title, code)
    (1, 'OGE13: Тип 1 — линейное', 'Линейное неравенство', GEN_T1),
    (2, 'OGE13: Тип 2+5 — система, текст', 'Система линейных неравенств (текст)', GEN_T2),
    (3, 'OGE13: Тип 3+4 — система, рисунки', 'Система линейных неравенств (рисунок)', GEN_T3),
    (4, 'OGE13: Тип 6+7 — квадр. факторизованное', 'Квадратное неравенство (разложенное)', GEN_T4),
    (5, 'OGE13: Тип 8+9 — квадр. без x', 'Квадратное неравенство x²+c', GEN_T5),
    (6, 'OGE13: Тип 10+11 — квадр. со свободным x', 'Квадратное неравенство cx−x²', GEN_T6),
    (7, 'OGE13: Тип 12 — рисунок→неравенство', 'По рисунку выбрать неравенство (x²±ax / x²±a²)', GEN_T7),
    (8, 'OGE13: Тип 13 — рисунок→неравенство (только a²)', 'По рисунку выбрать неравенство (x²±a²)', GEN_T8),
]


class Command(BaseCommand):
    help = 'Создаёт «Задание 13» курса ОГЭ с 8 генераторами на неравенства.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 13» и пересоздать.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден.'
            ))
            return

        # Ищем модуль 'Первая часть' по имени, не first() по order — иначе с
        # появлением модуля 'Задания 1-5' (order=0) создавался дубль урока.
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 13').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 13» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 13',
            defaults={'order': 13, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 13:
            lesson.order = 13
            lesson.save(update_fields=['order'])
        if created:
            self.stdout.write(self.style.SUCCESS(f'Урок создан: {lesson.title}'))

        existing_by_order = {a.order: a for a in lesson.assignments.all()}

        for order, gen_name, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                    'config': {},
                },
            )

            assign = existing_by_order.get(order)
            if assign:
                # title не перезаписываем — мог быть переименован вручную.
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'single_choice'
                assign.required_correct = 3
                assign.save()
                shown_title = assign.title
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=order,
                    title=asg_title,
                    description='',
                    assignment_type='test',
                    answer_type='single_choice',
                    required_correct=3,
                    problem_generator=generator,
                )
                shown_title = asg_title

            self.stdout.write(self.style.SUCCESS(f'  + [{order}] {shown_title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: «Задание 13» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
