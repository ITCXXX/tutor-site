# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=76: OGE7: Тип 5 — точка A в [0;1] с шагом 0,1
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
import math


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
        parts.append(f'<text x="{tx:.1f}" y="{line_y+22}" text-anchor="middle" font-family="Times New Roman, serif" font-size="14" font-style="italic" fill="currentColor">{label}</text>')
    for p in points:
        px = x(p['value'])
        parts.append(f'<circle cx="{px:.1f}" cy="{line_y}" r="4" fill="currentColor"/>')
        if p.get('letter'):
            parts.append(f'<text x="{px:.1f}" y="{line_y-12}" text-anchor="middle" font-family="Times New Roman, serif" font-size="16" font-style="italic" fill="currentColor">{p["letter"]}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def generate_task():
    """
    №7 ОГЭ, Тип 5: 4 дроби в (0, 1) с общим знаменателем, одна отмечена точкой A.
    Картинка: прямая [0; 1] с шагом 0,1, все 11 меток подписаны.
    """
    d = random.choice([17, 19, 21, 23, 27])
    # Подбираем 4 различных числителя в [1, d-1] с gcd=1, между ними расстояние ≥ 2/d
    while True:
        nums = sorted(random.sample(range(1, d), 4))
        diffs = [nums[i+1] - nums[i] for i in range(3)]
        if all(diff >= 2 for diff in diffs) and all(math.gcd(n, d) == 1 for n in nums):
            break

    correct_num = random.choice(nums)
    numerators = nums[:]
    random.shuffle(numerators)
    pos = numerators.index(correct_num) + 1

    # Прямая 0..1 с шагом 0,1
    ticks = [i / 10 for i in range(11)]
    def fmt_label(t):
        if t == 0:
            return '0'
        if t == 1:
            return '1'
        return f"0,{int(round(t * 10))}"
    labeled = {t: fmt_label(t) for t in ticks}
    points = [{'value': correct_num / d, 'letter': 'A'}]
    svg = make_axis(min_v=0, max_v=1, ticks=ticks,
                    labeled_ticks=labeled, points=points)

    fracs = [rf"\dfrac{{{n}}}{{{d}}}" for n in numerators]
    nums_text = ", ".join(f"${f}$" for f in fracs[:-1]) + f" и ${fracs[-1]}$"
    condition_text = (
        rf"Одно из чисел {nums_text} отмечено на числовой прямой точкой $A$."
        f"{svg}"
        rf"Какое это число?"
    )
    choices = [f"${f}$" for f in fracs]

    return {"condition_text": condition_text, "choices": choices, "correct_answer": pos}


if __name__ == "__main__":
    random.seed(0)
    for i in range(3):
        t = generate_task()
        print(f"--- T5[{i+1}] correct={t['correct_answer']} ---")
        print(t['condition_text'][:200] + '...')
