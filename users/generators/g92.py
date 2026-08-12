# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=92: OGE10: Тип 12 — бросок монеты
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
