# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=82: OGE7: Тип 12 — какое неравенство для a, b верно
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def make_axis(min_v, max_v, ticks, labeled_ticks, points,
              width=750, height=80):
    pad = 30; line_y = 40; plot_w = width - 2 * pad
    def x(v): return pad + (v - min_v) / (max_v - min_v) * plot_w
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" style="max-width:750px;display:block;margin:0.8em auto;color:currentColor;">']
    p.append(f'<line x1="{pad-15}" y1="{line_y}" x2="{width-pad+5}" y2="{line_y}" stroke="currentColor" stroke-width="1.5"/>')
    p.append(f'<polygon points="{width-pad+15},{line_y} {width-pad+5},{line_y-5} {width-pad+5},{line_y+5}" fill="currentColor"/>')
    for t in ticks:
        tx = x(t)
        p.append(f'<line x1="{tx:.1f}" y1="{line_y-6}" x2="{tx:.1f}" y2="{line_y+6}" stroke="currentColor" stroke-width="1.5"/>')
    for t, lbl in labeled_ticks.items():
        tx = x(t)
        p.append(f'<text x="{tx:.1f}" y="{line_y+22}" text-anchor="middle" font-family="Times New Roman, serif" font-size="16" font-style="italic" fill="currentColor">{lbl}</text>')
    for pt in points:
        px = x(pt['value'])
        p.append(f'<circle cx="{px:.1f}" cy="{line_y}" r="4" fill="currentColor"/>')
        if pt.get('letter'):
            p.append(f'<text x="{px:.1f}" y="{line_y-12}" text-anchor="middle" font-family="Times New Roman, serif" font-size="16" font-style="italic" fill="currentColor">{pt["letter"]}</text>')
    p.append('</svg>')
    return ''.join(p)


def generate_task():
    """
    №7 ОГЭ, Тип 12: «Какое неравенство верно?» (две переменные a, b).
    Конкретные значения a и b — десятичные с ≤1 знаком после запятой.
    Из набора выражений {a+b, a-b, ab, ab², a²b} выбираем 4, рендерим
    каждое как «выражение </> 0», ровно одно — верное.
    """
    candidates = [-3, -2.5, -2, -1.5, -1, -0.5, 0.5, 1, 1.5, 2, 2.5, 3]
    while True:
        a = random.choice(candidates)
        b = random.choice(candidates)
        if a == b:
            continue
        if a + b == 0:
            continue
        # все выражения должны быть нулевые
        if 0 in (a + b, a - b, a * b, a * b * b, a * a * b):
            continue
        break

    expr_pool = [
        ('a + b', lambda: a + b),
        ('a - b', lambda: a - b),
        ('ab', lambda: a * b),
        ('ab^{2}', lambda: a * b * b),
        ('a^{2}b', lambda: a * a * b),
    ]
    chosen = random.sample(expr_pool, 4)

    correct_pos = random.randint(1, 4)
    inequalities = []
    for i, (expr_str, expr_fn) in enumerate(chosen):
        val = expr_fn()
        true_sign = '>' if val > 0 else '<'
        is_correct = (i + 1 == correct_pos)
        used_sign = true_sign if is_correct else ('<' if true_sign == '>' else '>')
        inequalities.append(f"${expr_str} {used_sign} 0$")

    sorted_vals = sorted({a, b, 0})
    margin = 0.5
    min_v = sorted_vals[0] - margin
    max_v = sorted_vals[-1] + margin

    points = [
        {'value': a, 'letter': 'a'},
        {'value': b, 'letter': 'b'},
    ]
    labeled = {0: '0'}
    svg = make_axis(min_v, max_v, [0], labeled, points)

    condition_text = (
        rf"На координатной прямой отмечены числа $a$ и $b$.{svg}"
        rf"Какое из следующих неравенств верно?"
    )
    return {"condition_text": condition_text, "choices": inequalities, "correct_answer": correct_pos}


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"--- T12[{i+1}] correct={t['correct_answer']} ---")
        print(t['condition_text'][:200] + '...')
        print(f"choices: {t['choices']}")
