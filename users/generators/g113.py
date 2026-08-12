# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=113: OGE13: Тип 12 — рисунок→неравенство
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
