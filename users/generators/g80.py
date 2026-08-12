# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=80: OGE7: Тип 9+10 — какая разность пол./отр.
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



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
