# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=98: OGE10: Тип 18 — Эйлер (равновозм. точки)
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


def euler_with_dots(distribution):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 260" width="100%" style="max-width:520px;display:block;margin:0.8em auto;color:currentColor;">']
    parts.append('<rect x="30" y="20" width="460" height="220" fill="none" stroke="currentColor" stroke-width="1.2"/>')
    parts.append('<circle cx="190" cy="135" r="80" fill="none" stroke="currentColor" stroke-width="1.5"/>')
    parts.append('<circle cx="330" cy="135" r="80" fill="none" stroke="currentColor" stroke-width="1.5"/>')
    parts.append('<text x="120" y="60" text-anchor="middle" font-family="Times New Roman, serif" font-size="20" font-style="italic" fill="currentColor">A</text>')
    parts.append('<text x="400" y="60" text-anchor="middle" font-family="Times New Roman, serif" font-size="20" font-style="italic" fill="currentColor">B</text>')

    region_names = ['only_a', 'inter', 'only_b', 'outside']
    for r_idx, count in enumerate(distribution):
        positions = REGION_POSITIONS[region_names[r_idx]][:count]
        for (x, y) in positions:
            parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="currentColor"/>')
    parts.append('</svg>')
    return ''.join(parts)


def generate_task():
    """
    №10 ОГЭ, новый Тип 18: равновозможные точки в диаграмме Эйлера.
    Подобно T17, но без подписей вероятностей у точек —
    каждая точка равноправна, P(событие) = (число в области) / N.
    """
    # Подбираем N такое, что итоговая P будет конечной десятичной
    # → N только из {5, 10, 20} (фактрые 2 и 5)
    while True:
        N_options = [5, 10]
        N = random.choice(N_options)
        # Распределяем по 4 областям, ≤ 3 в каждой
        dist = [0, 0, 0, 0]
        for _ in range(N):
            idx = random.randint(0, 3)
            if dist[idx] < 3:
                dist[idx] += 1
        if sum(dist) == N and all(d <= 3 for d in dist):
            break

    only_a, inter, only_b, outside = dist
    QUESTION_TYPES = [
        ("$A$",                  only_a + inter),
        ("$B$",                  only_b + inter),
        ("$A \\cap B$",          inter),
        ("$A \\cup B$",          only_a + only_b + inter),
        ("$\\overline{A \\cup B}$", outside),
    ]
    q_label, k = random.choice(QUESTION_TYPES)
    if k == 0:
        return generate_task()
    P = Fraction(k, N)

    svg = euler_with_dots(dist)
    text = (
        f"На рисунке изображена диаграмма Эйлера для случайных событий $A$ и $B$ "
        f"в некотором случайном опыте. Точками показаны все равновозможные "
        f"элементарные события опыта. Найдите вероятность события {q_label}.{svg}"
    )
    return {"condition_text": text, "correct_answer": decimal_str(P)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(3):
        t = generate_task()
        print(f"--- T18[{i+1}] ans={t['correct_answer']} ---")
