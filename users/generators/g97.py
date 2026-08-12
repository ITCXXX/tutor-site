# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=97: OGE10: Тип 17 — Эйлер (точки с вер.)
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
from fractions import Fraction


def decimal_str(f):
    if f.denominator == 1: return str(f.numerator)
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return ip + ',' + dp if dp else ip


# Координаты точек для диаграммы Эйлера.
# Круг A: центр (190, 135), r=80.   Круг B: центр (330, 135), r=80.
# Каждая позиция выбрана с запасом, чтобы точка была чётко внутри своей области.
REGION_POSITIONS = {
    'only_a':  [(140, 135), (160, 105), (160, 165), (140, 115), (140, 155)],
    'inter':   [(260, 135), (260, 110), (260, 160)],
    'only_b':  [(380, 135), (360, 105), (360, 165), (380, 115), (380, 155)],
    'outside': [(75, 60), (455, 60), (260, 50), (75, 200), (455, 200)],
}


def euler_with_dots(dots, show_labels=True):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 260" width="100%" style="max-width:520px;display:block;margin:0.8em auto;color:currentColor;">']
    parts.append('<rect x="30" y="20" width="460" height="220" fill="none" stroke="currentColor" stroke-width="1.2"/>')
    parts.append('<circle cx="190" cy="135" r="80" fill="none" stroke="currentColor" stroke-width="1.5"/>')
    parts.append('<circle cx="330" cy="135" r="80" fill="none" stroke="currentColor" stroke-width="1.5"/>')
    parts.append('<text x="120" y="60" text-anchor="middle" font-family="Times New Roman, serif" font-size="20" font-style="italic" fill="currentColor">A</text>')
    parts.append('<text x="400" y="60" text-anchor="middle" font-family="Times New Roman, serif" font-size="20" font-style="italic" fill="currentColor">B</text>')

    region_dots = {'only_a': [], 'inter': [], 'only_b': [], 'outside': []}
    for region, val in dots:
        region_dots[region].append(val)

    for region_name, vals in region_dots.items():
        positions = REGION_POSITIONS[region_name]
        for (x, y), v in zip(positions, vals):
            parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="currentColor"/>')
            if show_labels and v is not None:
                parts.append(f'<text x="{x+8}" y="{y+5}" font-family="Times New Roman, serif" font-size="12" fill="currentColor">{v}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def generate_task():
    """
    №10 ОГЭ, новый Тип 17: точки в диаграмме Эйлера,
    у каждой подписана её вероятность (десятые), сумма = 1.
    """
    # Распределяем точки по 4 областям, чтобы суммарно было 4-6 точек, ≤ 3 в каждой
    while True:
        n_dots = random.randint(4, 6)
        dist = [0, 0, 0, 0]
        for _ in range(n_dots):
            idx = random.randint(0, 3)
            if dist[idx] < 3:
                dist[idx] += 1
        if sum(dist) == n_dots:
            break

    # Вероятности (целые «десятые», сумма = 10)
    while True:
        ks = [random.randint(1, 4) for _ in range(n_dots)]
        if sum(ks) == 10:
            break
        # Нормализуем: добавим/уберём
        s = sum(ks)
        if s < 10:
            for i in range(10 - s):
                idx = random.randint(0, n_dots - 1)
                if ks[idx] < 7:
                    ks[idx] += 1
        elif s > 10:
            for i in range(s - 10):
                idx = random.randint(0, n_dots - 1)
                if ks[idx] > 1:
                    ks[idx] -= 1
        if sum(ks) == 10 and all(k >= 1 for k in ks):
            break

    region_names = ['only_a', 'inter', 'only_b', 'outside']
    dots = []
    k_idx = 0
    for r_idx, c in enumerate(dist):
        for _ in range(c):
            prob = Fraction(ks[k_idx], 10)
            dots.append((region_names[r_idx], decimal_str(prob)))
            k_idx += 1

    # Вопрос
    region_dots_p = {r: 0 for r in region_names}
    k_idx = 0
    for r_idx, c in enumerate(dist):
        for _ in range(c):
            region_dots_p[region_names[r_idx]] += ks[k_idx]
            k_idx += 1

    QUESTION_TYPES = [
        ("$A$",                  region_dots_p['only_a'] + region_dots_p['inter']),
        ("$B$",                  region_dots_p['only_b'] + region_dots_p['inter']),
        ("$A \\cap B$",          region_dots_p['inter']),
        ("$A \\cup B$",          region_dots_p['only_a'] + region_dots_p['only_b'] + region_dots_p['inter']),
        ("$\\overline{A \\cup B}$", region_dots_p['outside']),
    ]
    q_label, k_total = random.choice(QUESTION_TYPES)
    if k_total == 0:
        # avoid 0 answer
        return generate_task()
    P = Fraction(k_total, 10)

    svg = euler_with_dots(dots, show_labels=True)
    text = (
        f"На рисунке изображена диаграмма Эйлера для случайных событий $A$ и $B$ "
        f"в некотором случайном опыте. Точками показаны все элементарные события, "
        f"и около каждого указана его вероятность. Найдите вероятность события {q_label}.{svg}"
    )
    return {"condition_text": text, "correct_answer": decimal_str(P)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(3):
        t = generate_task()
        print(f"--- T17[{i+1}] ans={t['correct_answer']} ---")
