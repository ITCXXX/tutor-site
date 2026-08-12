# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=85: OGE7: Тип 15 — какая точка соответствует √n
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


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
    №7 ОГЭ, Тип 15: «Какая из точек A, B, C, D соответствует числу √n?»
    На основе T13 (выбор n не точного квадрата в (a², (a+2)²)),
    плюс картинка с 4 точками — одна на √n, три отвлекающих рядом.
    """
    a = random.randint(4, 8)
    n_min = a * a + 1
    n_max = (a + 2) ** 2 - 1
    perfect_squares = {k * k for k in range(1, 20)}
    while True:
        n = random.randint(n_min, n_max)
        if n not in perfect_squares:
            break

    target_value = n ** 0.5

    # Подбираем 3 отвлекающих позиции в (a, a+2), удалённых от √n на ≥ 0.18
    distractor_options = [a + k * 0.25 for k in range(1, 8)]
    distractor_options += [a + k / 3 for k in range(1, 6)]
    candidates = [v for v in distractor_options
                  if a < v < a + 2 and abs(v - target_value) >= 0.18]
    candidates = sorted(set(round(v, 4) for v in candidates))

    # Пытаемся выбрать 3 различных позиции с попарным расстоянием ≥ 0.18
    while True:
        distractors = random.sample(candidates, 3)
        all_positions = sorted(distractors + [target_value])
        diffs = [all_positions[i+1] - all_positions[i] for i in range(3)]
        if all(d >= 0.18 for d in diffs):
            break

    sorted_positions = sorted(distractors + [target_value])
    target_idx = sorted_positions.index(target_value)

    letters = ['A', 'B', 'C', 'D']
    points = [{'value': v, 'letter': letters[i]}
              for i, v in enumerate(sorted_positions)]

    ticks = [a, a + 1, a + 2]
    labeled = {a: str(a), a + 1: str(a + 1), a + 2: str(a + 2)}
    svg = make_axis(min_v=a - 0.3, max_v=a + 2.3,
                    ticks=ticks, labeled_ticks=labeled, points=points)

    condition_text = (
        rf"На координатной прямой отмечены точки $A$, $B$, $C$, $D$. "
        rf"Одна из них соответствует числу $\sqrt{{{n}}}$."
        f"{svg}"
        rf"Какая это точка?"
    )
    return {
        "condition_text": condition_text,
        "choices": ["A", "B", "C", "D"],
        "correct_answer": target_idx + 1,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(3):
        t = generate_task()
        print(f"--- T15[{i+1}] correct={t['correct_answer']} ---")
        print(t['condition_text'][:280] + '...')
