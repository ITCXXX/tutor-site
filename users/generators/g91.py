# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=91: OGE10: Тип 10 — условная
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
