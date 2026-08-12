# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=81: OGE7: Тип 11 — какое утверждение для a верно
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


def _fmt_expr(form, k):
    """Чистый рендер: для k<0 в форме 'a-k' пишем a+|k| (без двойного минуса)."""
    if form == 'k-a':
        return f"{k} - a"  # «-5 - a» либо «5 - a»
    else:  # 'a-k'
        if k < 0:
            return f"a + {-k}"  # «a + 5»
        return f"a - {k}"


def generate_task():
    """
    №7 ОГЭ, Тип 11: «Какое утверждение верно?» (одна переменная a).
    a — полуцелое число с |a| > 2. Шкала: положительный a — линия 0..a+1;
    отрицательный — a-1..1. Метки только 0 и 1.
    """
    sign = random.choice(['positive', 'negative'])

    if sign == 'positive':
        a_int = random.randint(2, 7)
        a = a_int + 0.5
        ks = [a_int - 1, a_int, a_int + 1, a_int + 2]
        min_v = -0.5
        max_v = a + 1.5
    else:
        a_int = random.randint(2, 7)
        a = -(a_int + 0.5)
        ks = [-(a_int + 2), -(a_int + 1), -a_int, -(a_int - 1)]
        min_v = a - 1.5
        max_v = 1.5

    correct_pos = random.randint(1, 4)
    inequalities = []
    for i, k in enumerate(ks):
        is_correct = (i + 1 == correct_pos)
        if k < a:
            true_for_k_minus_a = '<'
            true_for_a_minus_k = '>'
        else:
            true_for_k_minus_a = '>'
            true_for_a_minus_k = '<'
        form = random.choice(['k-a', 'a-k'])
        true_sign = true_for_k_minus_a if form == 'k-a' else true_for_a_minus_k
        used_sign = true_sign if is_correct else ('<' if true_sign == '>' else '>')
        expr = _fmt_expr(form, k)
        inequalities.append(f"${expr} {used_sign} 0$")

    int_ticks = list(range(int(min_v) + 1, int(max_v) + 1))
    labeled = {0: '0', 1: '1'}
    points = [{'value': a, 'letter': 'a'}]
    svg = make_axis(min_v, max_v, int_ticks, labeled, points)

    condition_text = (
        rf"На координатной прямой отмечено число $a$.{svg}"
        rf"Какое из утверждений для этого числа является верным?"
    )
    return {"condition_text": condition_text, "choices": inequalities, "correct_answer": correct_pos}


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"--- T11[{i+1}] correct={t['correct_answer']} ---")
        print(f"choices: {t['choices']}")
