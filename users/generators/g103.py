# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=103: OGE12: Тип 6 — потенц. энергия
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
    """№12 ОГЭ, Тип 6: P = mgh, найти m. g = 9,8."""
    m = random.randint(2, 50)
    h = random.randint(2, 30)
    g = Fraction(98, 10)
    P = Fraction(m) * g * h
    text = (
        rf"Если тело массой $m$ кг подвешено на высоте $h$ м над горизонтальной "
        rf"поверхностью земли, то его потенциальная энергия (в джоулях) вычисляется "
        rf"по формуле $P = mgh$, где $g = 9{{,}}8$ м/с² — ускорение свободного "
        rf"падения. Найдите массу тела, подвешенного на высоте {h} м над поверхностью "
        rf"земли, если его потенциальная энергия равна {decimal_str(P)} джоулям. "
        rf"Ответ дайте в килограммах."
    )
    return {"condition_text": text, "correct_answer": str(m)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
