# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=93: OGE10: Тип 13 — N_A/N
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
