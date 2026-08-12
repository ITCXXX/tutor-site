# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=102: OGE12: Тип 5 — площадь
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
    """№12 ОГЭ, Тип 5: S = d1·d2·sin(α)/2, найти d1.
       sin α — десятичная дробь с одной цифрой после запятой."""
    sin_int = random.randint(1, 9)         # sin α = 0,1 .. 0,9
    sin_a = Fraction(sin_int, 10)
    d1 = random.randint(3, 25)
    d2 = random.randint(4, 25)
    S = Fraction(d1 * d2) * sin_a / 2
    text = (
        rf"Площадь четырёхугольника можно вычислить по формуле "
        rf"$S = \dfrac{{d_1 \cdot d_2 \sin \alpha}}{{2}}$, где $d_1$ и $d_2$ — "
        rf"длины диагоналей четырёхугольника, $\alpha$ — угол между диагоналями. "
        rf"Пользуясь этой формулой, найдите длину диагонали $d_1$, если $d_2 = {d2}$, "
        rf"$\sin \alpha = {decimal_str(sin_a)}$, а $S = {decimal_str(S)}$."
    )
    return {"condition_text": text, "correct_answer": str(d1)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
