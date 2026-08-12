# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=90: OGE10: Тип 9 — две категории
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
