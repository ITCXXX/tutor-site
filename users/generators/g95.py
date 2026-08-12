# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=95: OGE10: Тип 15 — Эйлер (вероятности)
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
    №10 ОГЭ, новый Тип 15: диаграмма Эйлера, в каждой из 4 областей
    подписана вероятность. Сумма всех = 1. Спрашивают P(A), P(B), P(A∩B), P(A∪B) или P(\\overline{A∪B}).
    """
    # Подбираем 4 десятых, сумма = 10
    while True:
        only_a = random.randint(1, 5)
        inter = random.randint(1, 4)
        only_b = random.randint(1, 5)
        outside = 10 - only_a - inter - only_b
        if 1 <= outside <= 6:
            break
    pa, pi, pb, po = (Fraction(only_a, 10), Fraction(inter, 10),
                     Fraction(only_b, 10), Fraction(outside, 10))

    QUESTION_TYPES = [
        ("$A$",                        pa + pi),
        ("$B$",                        pb + pi),
        ("$A \\cap B$",                pi),
        ("$A \\cup B$",                pa + pb + pi),
        ("$\\overline{A \\cup B}$",    po),
    ]
    q_label, p_value = random.choice(QUESTION_TYPES)
    svg = euler_with_text(decimal_str(pa), decimal_str(pi), decimal_str(pb), decimal_str(po))

    text = (
        f"На рисунке изображена диаграмма Эйлера для случайных событий $A$ и $B$ "
        f"в некотором случайном опыте с равновозможными исходами. В каждой из четырёх "
        f"областей указана вероятность соответствующего события. Найдите вероятность "
        f"события {q_label}.{svg}"
    )
    return {"condition_text": text, "correct_answer": decimal_str(p_value)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"--- T15[{i+1}] ans={t['correct_answer']} ---")
        print(t['condition_text'][:160] + '...')
