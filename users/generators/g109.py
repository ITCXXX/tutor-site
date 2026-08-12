# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=109: OGE13: Тип 3+4 — система, рисунки
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



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
