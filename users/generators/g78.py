# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=78: OGE7: Тип 7 — какая точка соответствует n/d
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
from fractions import Fraction


def make_axis(min_v, max_v, ticks, labeled_ticks, points,
              width=700, height=80):
    pad = 30
    line_y = 40
    plot_w = width - 2 * pad
    def x(v):
        return pad + (v - min_v) / (max_v - min_v) * plot_w
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" style="max-width:700px;display:block;margin:0.8em auto;color:currentColor;">']
    parts.append(f'<line x1="{pad-15}" y1="{line_y}" x2="{width-pad+5}" y2="{line_y}" stroke="currentColor" stroke-width="1.5"/>')
    parts.append(f'<polygon points="{width-pad+15},{line_y} {width-pad+5},{line_y-5} {width-pad+5},{line_y+5}" fill="currentColor"/>')
    for t in ticks:
        tx = x(t)
        parts.append(f'<line x1="{tx:.1f}" y1="{line_y-6}" x2="{tx:.1f}" y2="{line_y+6}" stroke="currentColor" stroke-width="1.5"/>')
    for t, label in labeled_ticks.items():
        tx = x(t)
        parts.append(f'<text x="{tx:.1f}" y="{line_y+22}" text-anchor="middle" font-family="Times New Roman, serif" font-size="16" font-style="italic" fill="currentColor">{label}</text>')
    for p in points:
        px = x(p['value'])
        parts.append(f'<circle cx="{px:.1f}" cy="{line_y}" r="4" fill="currentColor"/>')
        if p.get('letter'):
            parts.append(f'<text x="{px:.1f}" y="{line_y-12}" text-anchor="middle" font-family="Times New Roman, serif" font-size="16" font-style="italic" fill="currentColor">{p["letter"]}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def generate_task():
    """
    №7 ОГЭ, Тип 7: «Какая из точек A, B, C, D соответствует числу n/d?»
    Спека пользователя: точки расположены близко к шкалам — на простых
    долях интервала (1/4, 1/2, 3/4), чтобы было ясно «больше или меньше половины».
    """
    a = random.randint(4, 8)
    NICE_OFFSETS = [
        Fraction(1, 4), Fraction(1, 3), Fraction(2, 5),
        Fraction(3, 5), Fraction(2, 3), Fraction(3, 4),
        Fraction(5, 4), Fraction(4, 3), Fraction(7, 5),
        Fraction(8, 5), Fraction(5, 3), Fraction(7, 4),
    ]
    # Подбираем 4 различных оффсета, попарно ≥ 1/5 друг от друга
    while True:
        chosen = sorted(random.sample(NICE_OFFSETS, 4))
        if all(chosen[i+1] - chosen[i] >= Fraction(1, 5) for i in range(3)):
            break

    target_idx = random.randint(0, 3)
    target_offset = chosen[target_idx]
    target_value = a + target_offset
    n = target_value.numerator
    d = target_value.denominator

    # Иногда «увеличим» дробь, чтобы знаменатель не был слишком маленьким
    if d <= 5:
        k = random.choice([2, 3])
        n *= k
        d *= k

    letters = ['A', 'B', 'C', 'D']
    correct_answer = target_idx + 1

    points = []
    for i, off in enumerate(chosen):
        points.append({'value': float(a + off), 'letter': letters[i]})

    ticks = [a, a + 1, a + 2]
    labeled = {a: str(a), a + 1: str(a + 1), a + 2: str(a + 2)}
    svg = make_axis(min_v=a - 0.3, max_v=a + 2.3,
                    ticks=ticks, labeled_ticks=labeled, points=points)

    condition_text = (
        rf"На координатной прямой отмечены точки $A$, $B$, $C$, $D$. "
        rf"Одна из них соответствует числу $\dfrac{{{n}}}{{{d}}}$."
        f"{svg}"
        rf"Какая это точка?"
    )
    return {
        "condition_text": condition_text,
        "choices": ["A", "B", "C", "D"],
        "correct_answer": correct_answer,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(3):
        t = generate_task()
        print(f"--- T7[{i+1}] correct={t['correct_answer']} ---")
        print(t['condition_text'][:280] + '...')
