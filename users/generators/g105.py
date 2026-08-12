# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=105: OGE12: Тип 8 — Архимед
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
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def generate_task():
    """№12 ОГЭ, Тип 8: F = ρgV. ρ=1000, g=9,8. V — десятичная ≤ 5 с до 2 знаков."""
    V_int = random.randint(1, 500)         # V = V_int/100, ∈ [0.01, 5.00]
    V = Fraction(V_int, 100)
    F = V * 9800
    text = (
        rf"Сила Архимеда, выталкивающая на поверхность погружённое в воду тело, "
        rf"вычисляется по формуле $F = \rho g V$, где $\rho = 1000$ кг/м³ — плотность "
        rf"воды, $g = 9{{,}}8$ м/с² — ускорение свободного падения, а $V$ — объём "
        rf"тела в кубических метрах. Сила $F$ измеряется в ньютонах. Найдите силу "
        rf"Архимеда, действующую на погружённое в воду тело объёмом "
        rf"{decimal_str(V)} куб. м. Ответ дайте в ньютонах."
    )
    return {"condition_text": text, "correct_answer": decimal_str(F)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
