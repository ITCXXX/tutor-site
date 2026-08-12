# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=96: OGE10: Тип 16 — Эйлер (количества)
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


def euler_with_text(only_a, inter, only_b, outside):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 260" width="100%" style="max-width:520px;display:block;margin:0.8em auto;color:currentColor;">']
    parts.append('<rect x="30" y="20" width="460" height="220" fill="none" stroke="currentColor" stroke-width="1.2"/>')
    parts.append('<circle cx="190" cy="135" r="80" fill="none" stroke="currentColor" stroke-width="1.5"/>')
    parts.append('<circle cx="330" cy="135" r="80" fill="none" stroke="currentColor" stroke-width="1.5"/>')
    parts.append('<text x="120" y="60" text-anchor="middle" font-family="Times New Roman, serif" font-size="20" font-style="italic" fill="currentColor">A</text>')
    parts.append('<text x="400" y="60" text-anchor="middle" font-family="Times New Roman, serif" font-size="20" font-style="italic" fill="currentColor">B</text>')
    parts.append(f'<text x="140" y="142" text-anchor="middle" font-family="Times New Roman, serif" font-size="18" fill="currentColor">{only_a}</text>')
    parts.append(f'<text x="260" y="142" text-anchor="middle" font-family="Times New Roman, serif" font-size="18" fill="currentColor">{inter}</text>')
    parts.append(f'<text x="380" y="142" text-anchor="middle" font-family="Times New Roman, serif" font-size="18" fill="currentColor">{only_b}</text>')
    parts.append(f'<text x="445" y="50" text-anchor="middle" font-family="Times New Roman, serif" font-size="18" fill="currentColor">{outside}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def generate_task():
    """
    №10 ОГЭ, новый Тип 16: диаграмма Эйлера, в каждой из 4 областей
    указано количество равновозможных исходов. Сумма N — кратно 10
    (чтобы любая P была одной десятичной).
    """
    N = 10
    dist = [1, 1, 1, 1]
    remaining = N - 4
    for _ in range(remaining):
        idx = random.randint(0, 3)
        if dist[idx] < 5:
            dist[idx] += 1
        else:
            for j in range(4):
                if dist[j] < 5:
                    dist[j] += 1
                    break
    only_a, inter, only_b, outside = dist

    QUESTION_TYPES = [
        ("$A$",                        only_a + inter),
        ("$B$",                        only_b + inter),
        ("$A \\cap B$",                inter),
        ("$A \\cup B$",                only_a + only_b + inter),
        ("$\\overline{A \\cup B}$",    outside),
    ]
    q_label, count = random.choice(QUESTION_TYPES)
    P = Fraction(count, N)
    svg = euler_with_text(only_a, inter, only_b, outside)

    text = (
        f"На рисунке изображена диаграмма Эйлера для случайных событий $A$ и $B$ "
        f"в некотором случайном опыте с равновозможными исходами. В каждой области "
        f"указано, сколько исходов принадлежит этой области. Найдите вероятность "
        f"события {q_label}.{svg}"
    )
    return {"condition_text": text, "correct_answer": decimal_str(P)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"--- T16[{i+1}] ans={t['correct_answer']} ---")
