# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=104: OGE12: Тип 7 — кинет. энергия
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
    """№12 ОГЭ, Тип 7: E = mv²/2, найти v. m, v целые. E может быть нецелым."""
    v = random.randint(5, 30)
    m = random.choice([500, 1000, 1200, 1500, 2000, 2400, 3000, 3500])
    E = Fraction(m * v * v, 2)
    text = (
        rf"Кинетическая энергия тела массой $m$ кг, двигающегося со скоростью $v$ м/с, "
        rf"вычисляется по формуле $E = \dfrac{{mv^{{2}}}}{{2}}$ и измеряется в джоулях "
        rf"(Дж). Известно, что автомобиль массой {m} кг обладает кинетической энергией "
        rf"{decimal_str(E)} джоулей. Найдите скорость этого автомобиля в метрах в секунду."
    )
    return {"condition_text": text, "correct_answer": str(v)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
