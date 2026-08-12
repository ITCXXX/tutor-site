# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=79: OGE7: Тип 8 — десятичные без шкалы
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
    №7 ОГЭ, Тип 8: 4 десятичных числа разного масштаба, без шкалы, точки A..D
    в порядке возрастания, цель — сопоставить заданное число с буквой.
    Картинка: 4 равноудалённых точки на пустой прямой.
    """
    # Генерируем 4 различных десятичных числа.
    # Берём смесь: одно может быть отрицательным, остальные — положительные
    # с разным числом знаков после запятой.
    while True:
        nums = []
        # Иногда включаем отрицательное число
        if random.random() < 0.5:
            denom = random.choice([10, 100])
            nums.append(-random.randint(1, 5) / denom)
        # Малые положительные ~0,0X
        if random.random() < 0.5:
            nums.append(random.randint(1, 9) / 100)
        # Дополняем до 4-х: большие положительные ~0,X..1,X
        while len(nums) < 4:
            denom = random.choice([10, 100, 1000])
            v = random.randint(1, 999) / denom
            if 0.01 <= v <= 1.5:
                nums.append(v)

        nums = list({round(x, 3) for x in nums})  # дедупликация
        if len(nums) < 4:
            continue
        nums = nums[:4]
        s = sorted(nums)
        if all(s[i+1] - s[i] >= 0.04 for i in range(3)):
            break

    sorted_nums = sorted(nums)
    target_idx = random.randint(0, 3)
    target = sorted_nums[target_idx]

    # В условии числа перечисляются в случайном порядке
    display_order = sorted_nums[:]
    random.shuffle(display_order)

    def fmt(x):
        s = f"{x:g}"
        return s.replace('-', '−').replace('.', ',')

    nums_text = ";\\;".join(fmt(x) for x in display_order)

    # Картинка: 4 равноудалённых точки
    letters = ['A', 'B', 'C', 'D']
    points = [{'value': i + 1, 'letter': letters[i]} for i in range(4)]
    svg = make_axis(min_v=0, max_v=5, ticks=[],
                    labeled_ticks={}, points=points)

    condition_text = (
        rf"На координатной прямой точки $A$, $B$, $C$ и $D$ соответствуют числам "
        rf"${nums_text}$."
        f"{svg}"
        rf"Какой точке соответствует число ${fmt(target)}$?"
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
        print(f"--- T8[{i+1}] correct={t['correct_answer']} ---")
        print(t['condition_text'][:280] + '...')
