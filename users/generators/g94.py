# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=94: OGE10: Тип 14 — дерево
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
