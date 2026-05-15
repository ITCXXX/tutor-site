# -*- coding: utf-8 -*-
"""
Management command: создаёт 14 ProblemGenerator-ов и Assignment-ов под урок
«Задание 7» курса ОГЭ. Тема — числовая прямая, дроби, корни, неравенства.

Код генераторов inline в этом файле — внешних файлов больше нет.
Идемпотентен: ре-ран не плодит дубли и не переписывает переименованные title.

Usage:
    python manage.py seed_oge7
    python manage.py seed_oge7 --clear   # снести и пересоздать
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Код генераторов
# ──────────────────────────────────────────────────────────────────────────────


GEN_T1 = r'''
import random
import math


def generate_task():
    """
    №7 ОГЭ, Тип 1: «Между какими целыми числами заключено число n/m?»
    Алгоритм по спеке пользователя:
    1) знаменатель m > 6 (берём из [7, 19]);
    2) число k ∈ (5, 14), т.е. k ∈ [6, 13] — нижняя граница пары (k, k+1);
    3) n = m*k + δ, где δ ∈ [1, m-1], gcd(δ, m) = 1;
    4) случайно выбираем позицию правильного ответа среди 4 вариантов.
    """
    m = random.randint(7, 19)
    k = random.randint(6, 13)
    coprime_deltas = [d for d in range(1, m) if math.gcd(d, m) == 1]
    delta = random.choice(coprime_deltas)
    n = m * k + delta

    pos = random.randint(1, 4)
    start = k - (pos - 1)
    options = [(start + i, start + i + 1) for i in range(4)]
    choices = [f"${a}$ и ${b}$" for (a, b) in options]

    condition_text = (
        rf"Между какими целыми числами заключено число $\dfrac{{{n}}}{{{m}}}$?"
    )
    return {
        "condition_text": condition_text,
        "choices": choices,
        "correct_answer": pos,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        for j, c in enumerate(t['choices']):
            mark = " ← " if j + 1 == t['correct_answer'] else "   "
            print(f"    {j+1}){mark}{c}")
'''


GEN_T2 = r'''
import random
import math


def generate_task():
    """
    №7 ОГЭ, Тип 2: «Какому из промежутков принадлежит число n/m?»
    Алгоритм по спеке: выбираем целевой промежуток через перекрёстное умножение.
    1) позиция правильного варианта pos ∈ [1, 4];
    2) D_min ∈ [0, 6] так, чтобы D = D_min + (pos-1) ∈ [1, 8];
    3) знаменатель m из {7, 9, 11, 13};
    4) числитель n с условием: D·m < 10·n < (D+1)·m, gcd(n, m) = 1.
    """
    pos = random.randint(1, 4)

    # допустимые диапазоны D_min для каждой позиции, чтобы D ∈ [1, 8]
    if pos == 1:
        D_min = random.randint(1, 6)
    elif pos == 2:
        D_min = random.randint(0, 6)
    elif pos == 3:
        D_min = random.randint(0, 6)
    else:
        D_min = random.randint(0, 5)

    D = D_min + (pos - 1)

    valid_ms = []
    for m in (7, 9, 11, 13):
        n_lo = D * m / 10
        n_hi = (D + 1) * m / 10
        ns = [n for n in range(int(n_lo) + 1, int(n_hi) + 1)
              if n_lo < n < n_hi and math.gcd(n, m) == 1]
        if ns:
            valid_ms.append((m, ns))

    m, ns = random.choice(valid_ms)
    n = random.choice(ns)

    def fmt(d):
        return f"0,{d}" if d > 0 else "0"

    choices = [
        f"$({fmt(D_min + i)};\\;{fmt(D_min + i + 1)})$"
        for i in range(4)
    ]

    condition_text = (
        rf"Какому из данных промежутков принадлежит число "
        rf"$\dfrac{{{n}}}{{{m}}}$?"
    )
    return {
        "condition_text": condition_text,
        "choices": choices,
        "correct_answer": pos,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        for j, c in enumerate(t['choices']):
            mark = " ← " if j + 1 == t['correct_answer'] else "   "
            print(f"    {j+1}){mark}{c}")
'''


GEN_T3 = r'''
import random
import math


def generate_task():
    """
    №7 ОГЭ, Тип 3: «Какое число заключено между a/b и c/d?»
    Алгоритм:
    1) целевое десятичное D = K/10 (K ∈ [3, 30]);
    2) подбираем a/b — наибольшую дробь < D, но > (K-1)/10;
    3) подбираем c/d — наименьшую дробь > D, но < (K+1)/10;
    4) 4 варианта — последовательные десятичные шага 0,1.
    """
    DENOMS = [3, 5, 7, 8, 9, 11, 13, 14, 15, 17, 19]

    while True:
        K = random.randint(3, 30)

        # left bound a/b ∈ ((K-1)/10, K/10)
        valid_left = []
        for b in DENOMS:
            a = (K * b - 1) // 10
            if a > 0 and 10 * a > (K - 1) * b and math.gcd(a, b) == 1:
                valid_left.append((a, b))

        # right bound c/d ∈ (K/10, (K+1)/10)
        valid_right = []
        for d in DENOMS:
            c = K * d // 10 + 1
            if 10 * c < (K + 1) * d and math.gcd(c, d) == 1:
                valid_right.append((c, d))

        if valid_left and valid_right:
            break

    a, b = random.choice(valid_left)
    c, d = random.choice([(c, d) for (c, d) in valid_right if d != b] or valid_right)

    pos = random.randint(1, 4)
    K_min = K - (pos - 1)
    if K_min < 0:
        K_min = 0
        pos = K + 1

    def fmt(k):
        if k % 10 == 0:
            return f"{k // 10}"
        return f"{k // 10},{k % 10}"

    choices = [f"${fmt(K_min + i)}$" for i in range(4)]

    condition_text = (
        rf"Какое из следующих чисел заключено между числами "
        rf"$\dfrac{{{a}}}{{{b}}}$ и $\dfrac{{{c}}}{{{d}}}$?"
    )
    return {
        "condition_text": condition_text,
        "choices": choices,
        "correct_answer": pos,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        for j, c in enumerate(t['choices']):
            mark = " ← " if j + 1 == t['correct_answer'] else "   "
            print(f"    {j+1}){mark}{c}")
'''


GEN_T4 = r'''
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
    №7 ОГЭ, Тип 4: 4 дроби с общим знаменателем, одна отмечена точкой A на прямой.
    Алгоритм опирается на T6 (один числитель в [a; a+1], три вне).
    Картинка: прямая 0..5, помечены 0 и 1, остальные штрихи без подписей.
    """
    a = random.randint(2, 4)
    b = a + 1
    d = random.choice([7, 9, 11, 13, 14, 17, 19])

    correct_num = random.randint(a * d + 1, b * d - 1)

    distractor_nums = []
    n_below = random.randint(0, 3)
    n_above = 3 - n_below
    for _ in range(n_below):
        distractor_nums.append(random.randint(max(1, (a - 2) * d + 1), a * d - 1))
    for _ in range(n_above):
        distractor_nums.append(random.randint(b * d + 1, (b + 2) * d - 1))

    numerators = [correct_num] + distractor_nums
    random.shuffle(numerators)
    pos = numerators.index(correct_num) + 1

    # Диапазон оси: от 0 до max(нужного целого + 1)
    max_int = (max(numerators) // d) + 1
    ticks = list(range(0, max_int + 1))
    labeled = {0: '0', 1: '1'}
    points = [{'value': correct_num / d, 'letter': 'A'}]
    svg = make_axis(min_v=0, max_v=max_int, ticks=ticks,
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
        print(f"--- T4[{i+1}] ---")
        print(t['condition_text'][:200] + '...')
        print(f"choices: {t['choices']}")
        print(f"correct: {t['correct_answer']}")
        print()
'''


GEN_T5 = r'''
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
'''


GEN_T6 = r'''
import random


def generate_task():
    """
    №7 ОГЭ, Тип 6: «Какое из чисел принадлежит отрезку [a; a+1]?»
    4 дроби с одинаковым знаменателем d, ровно одна в [a; a+1].
    """
    a = random.randint(3, 9)
    b = a + 1
    d = random.choice([7, 9, 11, 12, 13, 14, 15, 17, 19])

    correct_num = random.randint(a * d + 1, b * d - 1)

    distractor_nums = []
    n_below = random.randint(0, 3)
    n_above = 3 - n_below
    for _ in range(n_below):
        num = random.randint((a - 2) * d + 1, a * d - 1)
        distractor_nums.append(num)
    for _ in range(n_above):
        num = random.randint(b * d + 1, (b + 2) * d - 1)
        distractor_nums.append(num)

    numerators = [correct_num] + distractor_nums
    random.shuffle(numerators)
    pos = numerators.index(correct_num) + 1

    fracs = [rf"\dfrac{{{n}}}{{{d}}}" for n in numerators]
    nums_text = ", ".join(f"${f}$" for f in fracs[:-1]) + f" и ${fracs[-1]}$"
    condition_text = (
        rf"Какое из чисел {nums_text} принадлежит отрезку $[{a};\;{b}]$?"
    )
    choices = [f"${f}$" for f in fracs]

    return {
        "condition_text": condition_text,
        "choices": choices,
        "correct_answer": pos,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        for j, c in enumerate(t['choices']):
            mark = " ← " if j + 1 == t['correct_answer'] else "   "
            print(f"    {j+1}){mark}{c}")
'''


GEN_T7 = r'''
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
'''


GEN_T8 = r'''
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
'''


GEN_T9_T10 = r'''
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
    №7 ОГЭ, объединённый Тип 9+10.
    Точки a, b, c расставлены слева направо в одной из 6 перестановок.
    3 показываемые разности — по одной из каждой антисимметричной пары:
    {b-a, a-b}, {c-a, a-c}, {c-b, b-c}. Это даёт богаче выбор ответа.
    """
    question_type = random.choice(['positive', 'negative'])
    perms = ['abc', 'acb', 'bac', 'bca', 'cab', 'cba']
    pair1 = [('b', 'a'), ('a', 'b')]
    pair2 = [('c', 'a'), ('a', 'c')]
    pair3 = [('c', 'b'), ('b', 'c')]

    def sign_of_diff(diff, perm):
        x, y = diff
        return 1 if perm.index(x) > perm.index(y) else -1

    valid = []
    for perm in perms:
        for d1 in pair1:
            for d2 in pair2:
                for d3 in pair3:
                    diffs = [d1, d2, d3]
                    signs = [sign_of_diff(d, perm) for d in diffs]
                    if question_type == 'positive':
                        matches = [i for i, s in enumerate(signs) if s > 0]
                    else:
                        matches = [i for i, s in enumerate(signs) if s < 0]
                    if len(matches) == 0:
                        valid.append((perm, diffs, 4))
                    elif len(matches) == 1:
                        valid.append((perm, diffs, matches[0] + 1))

    perm, diffs, raw_correct = random.choice(valid)

    # Перемешиваем 3 разности для разнообразия позиции ответа
    order = [0, 1, 2]
    random.shuffle(order)
    shuffled_diffs = [diffs[i] for i in order]

    if raw_correct == 4:
        correct = 4
    else:
        # raw_correct: 1, 2 или 3 → исходный индекс
        original_index = raw_correct - 1
        new_position = order.index(original_index)
        correct = new_position + 1

    # Точки слева направо в перестановке
    letters = list(perm)
    positions = [1.0, 2.0, 3.0]
    points = [{'value': positions[i], 'letter': letters[i]} for i in range(3)]
    svg = make_axis(0, 4, [], {}, points)

    word = "положительна" if question_type == 'positive' else "отрицательна"
    diff_text = ", ".join(f"{d[0]}-{d[1]}" for d in shuffled_diffs)

    condition_text = (
        rf"На координатной прямой отмечены числа $a$, $b$ и $c$.{svg}"
        rf"Какая из разностей ${diff_text}$ {word}?"
    )
    choices = [f"${d[0]}-{d[1]}$" for d in shuffled_diffs] + ["ни одна из них"]
    return {"condition_text": condition_text, "choices": choices, "correct_answer": correct}


if __name__ == "__main__":
    random.seed(0)
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    diff_counts = {}
    for _ in range(2000):
        t = generate_task()
        counts[t['correct_answer']] += 1
        # Track which difference is the answer
        if t['correct_answer'] != 4:
            ans_diff = t['choices'][t['correct_answer'] - 1]
            diff_counts[ans_diff] = diff_counts.get(ans_diff, 0) + 1

    print("Распределение позиций ответа из 2000 прогонов:")
    for k, v in counts.items():
        print(f"  ans={k}: {v}")
    print()
    print("Какие именно разности встречаются как правильные:")
    for k, v in sorted(diff_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print()
    print("Несколько примеров:")
    random.seed(1)
    for i in range(5):
        t = generate_task()
        print(f"\n[{i+1}] correct={t['correct_answer']}")
        print(f"    {t['choices']}")
'''


GEN_T11 = r'''
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
'''


GEN_T12 = r'''
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
'''


GEN_T13 = r'''
import random


def generate_task():
    """
    №7 ОГЭ, Тип 13: «Между какими числами заключено √n?»
    Алгоритм:
    1) граничные числа k и k+1 (k ∈ [4, 9]);
    2) диапазон n ∈ (k², (k+1)²);
    3) корень и 4 варианта.
    """
    k = random.randint(4, 9)
    n_min = k * k + 1
    n_max = (k + 1) ** 2 - 1
    n = random.randint(n_min, n_max)

    correct = (k, k + 1)

    # Плановые отвлекающие
    half = max(2, n // 2)
    third = max(2, n // 3)
    candidates = [
        (n - 1, n + 1),
        (half - 1, half + 1),
        (third - 1, third + 1),
    ]
    distractors = [c for c in candidates if c != correct and c[0] >= 1]
    distractors = list(dict.fromkeys(distractors))[:3]

    used = {correct, *distractors}
    while len(distractors) < 3:
        rk = random.randint(2, max(20, n // 4))
        cand = (rk, rk + 1)
        if cand not in used:
            distractors.append(cand)
            used.add(cand)

    options = [correct] + distractors
    random.shuffle(options)
    pos = options.index(correct) + 1

    choices = [f"${a}$ и ${b}$" for (a, b) in options]
    condition_text = rf"Между какими числами заключено число $\sqrt{{{n}}}$?"

    return {
        "condition_text": condition_text,
        "choices": choices,
        "correct_answer": pos,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        for j, c in enumerate(t['choices']):
            mark = " ← " if j + 1 == t['correct_answer'] else "   "
            print(f"    {j+1}){mark}{c}")
'''


GEN_T14 = r'''
import random


def generate_task():
    """
    №7 ОГЭ, Тип 14: «Какое из √a, √(a+1), √N, √M принадлежит (a; a+1)?»
    Алгоритм:
    1) границы интервала a, a+1;
    2) под корнями: 4 числа — a, a+1 (ловушки) и N (в (a², (a+1)²)) + M (вне).
    """
    a = random.randint(5, 9)
    b = a + 1

    N = random.randint(a * a + 1, b * b - 1)

    # M — вне интервала, близко к нему
    if random.random() < 0.5:
        M = random.randint(max(1, a * a - 3), a * a - 1)
    else:
        M = random.randint(b * b + 1, b * b + 3)
    if M == N:
        M = M - 1 if M > 1 else M + 1

    # Школково всегда ставит a, a+1 первыми
    if random.random() < 0.5:
        options = [a, b, N, M]
        pos = 3
    else:
        options = [a, b, M, N]
        pos = 4

    choices = [f"$\\sqrt{{{x}}}$" for x in options]
    nums_text = ", ".join(c for c in choices[:-1]) + f" и {choices[-1]}"
    condition_text = (
        rf"Какое из чисел {nums_text} принадлежит промежутку $({a};\;{b})$?"
    )

    return {
        "condition_text": condition_text,
        "choices": choices,
        "correct_answer": pos,
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        for j, c in enumerate(t['choices']):
            mark = " ← " if j + 1 == t['correct_answer'] else "   "
            print(f"    {j+1}){mark}{c}")
'''


GEN_T15 = r'''
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
'''


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    # (order, gen_name, asg_title, code)
    (1, 'OGE7: Тип 1 — между какими целыми n/m', 'Дробь между целыми числами', GEN_T1),
    (2, 'OGE7: Тип 2 — какому промежутку принадлежит n/m', 'Дробь и десятичный промежуток', GEN_T2),
    (3, 'OGE7: Тип 3 — какое число между двумя дробями', 'Десятичное между двумя дробями', GEN_T3),
    (4, 'OGE7: Тип 4 — точка A, варианты-дроби', 'Точка A на прямой (дроби, целые)', GEN_T4),
    (5, 'OGE7: Тип 5 — точка A в [0;1] с шагом 0,1', 'Точка A на отрезке [0;1]', GEN_T5),
    (6, 'OGE7: Тип 6 — какое из чисел в [a;a+1]', 'Дробь в отрезке [a;a+1]', GEN_T6),
    (7, 'OGE7: Тип 7 — какая точка соответствует n/d', 'Точки A,B,C,D и дробь', GEN_T7),
    (8, 'OGE7: Тип 8 — десятичные без шкалы', 'Точки A,B,C,D и десятичные', GEN_T8),
    (9, 'OGE7: Тип 9+10 — какая разность пол./отр.', 'Знак разности (a, b, c)', GEN_T9_T10),
    (10, 'OGE7: Тип 11 — какое утверждение для a верно', 'Утверждение для числа a', GEN_T11),
    (11, 'OGE7: Тип 12 — какое неравенство для a, b верно', 'Неравенство для a и b', GEN_T12),
    (12, 'OGE7: Тип 13 — между какими числами √n', '√n между целыми', GEN_T13),
    (13, 'OGE7: Тип 14 — какое из √-чисел в (a;a+1)', '√n в промежутке (a;a+1)', GEN_T14),
    (14, 'OGE7: Тип 15 — какая точка соответствует √n', 'Точки A,B,C,D и √n', GEN_T15),
]


class Command(BaseCommand):
    help = 'Создаёт «Задание 7» курса ОГЭ с 14 генераторами на сравнение чисел.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 7» и пересоздать.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден.'
            ))
            return

        # Ищем модуль 'Первая часть' по имени, не first() по order — иначе с
        # появлением модуля 'Задания 1-5' (order=0) создавался дубль урока.
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 7').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 7» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 7',
            defaults={'order': 7, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 7:
            lesson.order = 7
            lesson.save(update_fields=['order'])
        if created:
            self.stdout.write(self.style.SUCCESS(f'Урок создан: {lesson.title}'))

        # Поиск Assignment по (lesson, order) — title мог быть переименован
        # вручную (например, в «Тип N»), поэтому по нему искать нельзя.
        existing_by_order = {a.order: a for a in lesson.assignments.all()}

        for order, gen_name, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                    'config': {},
                },
            )

            assign = existing_by_order.get(order)
            if assign:
                # title не перезаписываем — мог быть переименован.
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'single_choice'
                assign.required_correct = 3
                assign.save()
                shown_title = assign.title
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=order,
                    title=asg_title,
                    description='',
                    assignment_type='test',
                    answer_type='single_choice',
                    required_correct=3,
                    problem_generator=generator,
                )
                shown_title = asg_title

            self.stdout.write(self.style.SUCCESS(f'  + [{order:>2}] {shown_title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: «Задание 7» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
