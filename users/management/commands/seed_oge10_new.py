# -*- coding: utf-8 -*-
"""
Management command: создаёт 9 ProblemGenerator-ов и Assignment-ов под существующий
урок «Задание 10» курса ОГЭ. Старые 7 прототипов не трогает.
Код генераторов inline в этом файле — внешних файлов больше нет.

Usage:
    python manage.py seed_oge10_new
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max

from users.models import Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Код генераторов
# ──────────────────────────────────────────────────────────────────────────────


GEN_T9 = r'''
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


def _noun_form(n, sg_gen, gen_pl):
    if n % 100 in (11, 12, 13, 14):
        return gen_pl
    last = n % 10
    if last in (2, 3, 4):
        return sg_gen
    return gen_pl


def generate_task():
    """№10 ОГЭ, новый Тип 9: классическая вероятность с двумя категориями."""
    SCENARIOS = [
        ("Под классной доской в лотке лежат", "маркер",   "маркера",   "маркеров"),
        ("В коробке хранятся",                "карандаш", "карандаша", "карандашей"),
        ("В мешке лежат",                     "шарик",    "шарика",    "шариков"),
        ("На столе разложены",                "брелок",   "брелока",   "брелоков"),
    ]
    COLORS = [
        ("чёрный",   "чёрных"),
        ("синий",    "синих"),
        ("красный",  "красных"),
        ("зелёный",  "зелёных"),
        ("жёлтый",   "жёлтых"),
        ("белый",    "белых"),
        ("оранжевый","оранжевых"),
    ]
    lead, obj_sg, obj_sg_gen, obj_gen_pl = random.choice(SCENARIOS)
    c1, c2 = random.sample(COLORS, 2)

    total = random.choice([10, 20, 25, 40, 50, 80, 100])
    a = random.randint(max(2, total // 4), total - max(2, total // 4))
    b = total - a

    if random.random() < 0.5:
        ask_count, ask_color_nom = a, c1[0]
    else:
        ask_count, ask_color_nom = b, c2[0]

    P = Fraction(ask_count, total)
    noun_after_b = _noun_form(b, obj_sg_gen, obj_gen_pl)

    text = (
        f"{lead} {a} {c1[1]} и {b} {c2[1]} {noun_after_b}. "
        f"Из коробки берут случайный {obj_sg}. "
        f"Найдите вероятность того, что он окажется {ask_color_nom}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": text, "correct_answer": decimal_str(P)}
'''


GEN_T10 = r'''
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


def _noun_form(n, sg_gen, gen_pl):
    if n % 100 in (11, 12, 13, 14):
        return gen_pl
    last = n % 10
    if last in (2, 3, 4):
        return sg_gen
    return gen_pl


def generate_task():
    """
    №10 ОГЭ, новый Тип 10: условная вероятность («первый — Х»).
    Идём от ответа: P = num / denom, где (denom + 1) — общее число предметов,
    (num + 1) — число предметов того цвета, что вытащили первым.
    Случайно выбираем, какой цвет — «первый».
    """
    SCENARIOS = [
        ("карандаш",  "карандаша", "карандашей",  "карандашом"),
        ("маркер",    "маркера",   "маркеров",    "маркером"),
        ("шарик",     "шарика",    "шариков",     "шариком"),
    ]
    COLORS = [
        ("жёлтый",   "жёлтых",   "жёлтым"),
        ("зелёный",  "зелёных",  "зелёным"),
        ("красный",  "красных",  "красным"),
        ("синий",    "синих",    "синим"),
        ("белый",    "белых",    "белым"),
        ("чёрный",   "чёрных",   "чёрным"),
    ]
    obj_sg, obj_sg_gen, obj_gen_pl, obj_instr = random.choice(SCENARIOS)
    color_a, color_b = random.sample(COLORS, 2)

    # P = (first_count - 1) / (total - 1)
    NICE_DENOMS = [10, 20, 25, 40, 50]
    while True:
        denom = random.choice(NICE_DENOMS)
        num = random.randint(2, denom - 4)
        total = denom + 1
        first_count = num + 1
        other_count = total - first_count
        if other_count >= 5 and first_count >= 5:
            break

    # 50/50: какой цвет — первый
    first_is_a = random.random() < 0.5
    if first_is_a:
        a_count = first_count
        b_count = other_count
        first_color_nom = color_a[0]
        first_color_instr = color_a[2]
    else:
        a_count = other_count
        b_count = first_count
        first_color_nom = color_b[0]
        first_color_instr = color_b[2]

    P = Fraction(first_count - 1, total - 1)
    noun_after_b = _noun_form(b_count, obj_sg_gen, obj_gen_pl)

    text = (
        f"Из ящика, где хранятся {a_count} {color_a[1]} и {b_count} {color_b[1]} {noun_after_b}, "
        f"не глядя достали два {obj_sg_gen}. "
        f"Известно, что первый {obj_sg} оказался {first_color_instr}. "
        f"Найдите вероятность того, что второй {obj_sg} тоже оказался {first_color_instr}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": text, "correct_answer": decimal_str(P)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        print(f"     ответ = {t['correct_answer']}\n")
'''


GEN_T12 = r'''
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


ORDINALS_PREP = {
    2: "втором", 3: "третьем", 4: "четвёртом", 5: "пятом",
    6: "шестом", 7: "седьмом", 8: "восьмом", 9: "девятом", 10: "десятом",
    11: "одиннадцатом", 12: "двенадцатом", 13: "тринадцатом",
    14: "четырнадцатом", 15: "пятнадцатом", 16: "шестнадцатом",
    17: "семнадцатом", 18: "восемнадцатом", 19: "девятнадцатом", 20: "двадцатом",
    21: "двадцать первом", 22: "двадцать втором", 23: "двадцать третьем",
    24: "двадцать четвёртом",
}


def generate_task():
    """
    №10 ОГЭ, новый Тип 12: бросок монеты в серии.
    Подвох — номер броска не важен; P(решка) = (n - кол_орлов) / n.
    """
    n = random.choice([20, 25])
    k_oryol = random.randint(int(n * 0.35), int(n * 0.65))
    k_reshka = n - k_oryol
    P = Fraction(k_reshka, n)

    throw_num = random.randint(3, n - 2)
    ordinal = ORDINALS_PREP[throw_num]

    text = (
        f"Монету бросили {n} раз. Известно, что орёл выпал {k_oryol} раз. "
        f"Найдите вероятность того, что при {ordinal} по счёту броске выпала решка."
    )
    return {"condition_text": text, "correct_answer": decimal_str(P)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        print(f"     ответ = {t['correct_answer']}\n")
'''


GEN_T13 = r'''
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


def generate_task():
    """
    №10 ОГЭ, новый Тип 13: «N равновозможных исходов, из которых N_A благоприятствуют A».
    Идём от ответа: P с конечной десятичной → строим N и N_A.
    """
    NICE_DENOMS = [2, 4, 5, 8, 10, 20, 25, 50]
    while True:
        d = random.choice(NICE_DENOMS)
        num = random.randint(1, d - 1)
        P = Fraction(num, d)
        m_min = max(2, (10 + P.denominator - 1) // P.denominator)
        m_max = 100 // P.denominator
        if m_min > m_max:
            continue
        m = random.randint(m_min, m_max)
        n = P.denominator * m
        n_a = P.numerator * m
        if 0 < n_a < n:
            break

    text = (
        rf"В случайном опыте $N = {n}$ равновозможных элементарных событий, "
        rf"из которых $N_{{A}} = {n_a}$ благоприятствуют событию $A$. "
        rf"Вычислите вероятность события $A$. "
        rf"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": text, "correct_answer": decimal_str(P)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}")
        print(f"     ответ = {t['correct_answer']}\n")
'''


GEN_T14 = r'''
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


def make_tree_svg(p_a, p_na, q_b_a, q_nb_a, q_b_na, q_nb_na):
    width, height = 540, 260
    sx, sy = width/2, 30
    ax, ay = width/2 - 130, 110
    nax, nay = width/2 + 130, 110
    leaves_x = [ax - 60, ax + 30, nax - 30, nax + 60]
    leaves_y = 200
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" style="max-width:540px;display:block;margin:0.8em auto;color:currentColor;">']
    edges = [
        (sx, sy, ax, ay, p_a),
        (sx, sy, nax, nay, p_na),
        (ax, ay, leaves_x[0], leaves_y, q_b_a),
        (ax, ay, leaves_x[1], leaves_y, q_nb_a),
        (nax, nay, leaves_x[2], leaves_y, q_b_na),
        (nax, nay, leaves_x[3], leaves_y, q_nb_na),
    ]
    for x1, y1, x2, y2, label in edges:
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="currentColor" stroke-width="1.5"/>')
        mx = x1 + 0.45 * (x2 - x1)
        my = y1 + 0.45 * (y2 - y1)
        # Сместим подпись чуть в сторону от линии
        offset_x = -10 if x2 < x1 else 10
        parts.append(f'<text x="{mx + offset_x:.1f}" y="{my:.1f}" text-anchor="middle" font-family="Times New Roman, serif" font-size="14" fill="currentColor">{label}</text>')

    nodes = [
        (sx, sy - 10, "S", False),
        (ax, ay - 10, "A", False),
        (nax, nay - 10, "A", True),
        (leaves_x[0], leaves_y + 18, "B", False),
        (leaves_x[1], leaves_y + 18, "B", True),
        (leaves_x[2], leaves_y + 18, "B", False),
        (leaves_x[3], leaves_y + 18, "B", True),
    ]
    for x, y_label, label, has_bar in nodes:
        # Узел (точка)
        circle_y = sy if label == "S" else (ay if label in ("A",) and not has_bar and x == ax else
                                            nay if label == "A" and has_bar else leaves_y)
        parts.append(f'<circle cx="{x:.1f}" cy="{circle_y:.1f}" r="3" fill="currentColor"/>')
        parts.append(f'<text x="{x:.1f}" y="{y_label:.1f}" text-anchor="middle" font-family="Times New Roman, serif" font-size="16" font-style="italic" fill="currentColor">{label}</text>')
        if has_bar:
            bar_y = y_label - 14
            parts.append(f'<line x1="{x-7:.1f}" y1="{bar_y:.1f}" x2="{x+7:.1f}" y2="{bar_y:.1f}" stroke="currentColor" stroke-width="1"/>')
    parts.append('</svg>')
    return ''.join(parts)


def generate_task():
    """№10 ОГЭ, новый Тип 14: дерево случайного опыта. Найти P(B)."""
    # Все вероятности — в десятых, чтобы P(B) была конечной десятичной
    p_a = Fraction(random.randint(1, 9), 10)
    q_b_a = Fraction(random.randint(1, 9), 10)
    q_b_na = Fraction(random.randint(1, 9), 10)
    p_na = 1 - p_a
    q_nb_a = 1 - q_b_a
    q_nb_na = 1 - q_b_na

    P_B = p_a * q_b_a + p_na * q_b_na

    svg = make_tree_svg(
        decimal_str(p_a), decimal_str(p_na),
        decimal_str(q_b_a), decimal_str(q_nb_a),
        decimal_str(q_b_na), decimal_str(q_nb_na),
    )
    text = (
        rf"На рисунке изображено дерево случайного опыта. "
        rf"Найдите вероятность события $B$.{svg}"
    )
    return {"condition_text": text, "correct_answer": decimal_str(P_B)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(3):
        t = generate_task()
        print(f"--- T14[{i+1}] ans={t['correct_answer']} ---")
        print(t['condition_text'][:200] + '...')
'''


GEN_T15 = r'''
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
'''


GEN_T16 = r'''
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
'''


GEN_T17 = r'''
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
'''


GEN_T18 = r'''
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
'''


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    # (gen_name, asg_title, code)
    ('OGE10: Тип 9 — две категории', 'Базовая вероятность (две категории)', GEN_T9),
    ('OGE10: Тип 10 — условная', 'Условная вероятность (первый — X)', GEN_T10),
    ('OGE10: Тип 12 — бросок монеты', 'Бросок монеты в серии', GEN_T12),
    ('OGE10: Тип 13 — N_A/N', 'Прямой расчёт N_A / N', GEN_T13),
    ('OGE10: Тип 14 — дерево', 'Дерево случайного опыта', GEN_T14),
    ('OGE10: Тип 15 — Эйлер (вероятности)', 'Диаграмма Эйлера: вероятности в областях', GEN_T15),
    ('OGE10: Тип 16 — Эйлер (количества)', 'Диаграмма Эйлера: количества в областях', GEN_T16),
    ('OGE10: Тип 17 — Эйлер (точки с вер.)', 'Диаграмма Эйлера: точки с подписями', GEN_T17),
    ('OGE10: Тип 18 — Эйлер (равновозм. точки)', 'Диаграмма Эйлера: равновозможные точки', GEN_T18),
]


class Command(BaseCommand):
    help = "Создаёт 9 новых ProblemGenerator-ов и Assignment-ов под урок «Задание 10»."

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            lesson = Lesson.objects.get(
                module__course__slug="oge-maths",
                title__iexact="Задание 10",
            )
        except Lesson.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                "Урок «Задание 10» в курсе ОГЭ (slug=oge-maths) не найден."
            ))
            return

        existing_max = lesson.assignments.aggregate(
            max_order=Max("order"),
        )["max_order"] or 0

        # Идентификация наших Assignment-ов идёт по `problem_generator.name`
        # (стабильный идентификатор), а не по title — title мог быть
        # переименован вручную в «Тип N».
        new_count = 0
        for gen_name, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    "generator_type": "python_function",
                    "python_code": code,
                    "config": {},
                },
            )

            existing = lesson.assignments.filter(problem_generator=generator).first()
            if existing:
                # title не перезаписываем — мог быть переименован.
                existing.assignment_type = "test"
                existing.answer_type = "decimal_input"
                existing.required_correct = 3
                existing.save()
                order = existing.order
                shown_title = existing.title
            else:
                order = existing_max + 1 + new_count
                new_count += 1
                Assignment.objects.create(
                    lesson=lesson,
                    order=order,
                    title=asg_title,
                    description="",
                    assignment_type="test",
                    answer_type="decimal_input",
                    required_correct=3,
                    problem_generator=generator,
                )
                shown_title = asg_title

            self.stdout.write(self.style.SUCCESS(f"  + [{order}] {shown_title}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nГотово: {len(PROTOTYPES)} прототипов «Задания 10» актуализированы."
        ))
