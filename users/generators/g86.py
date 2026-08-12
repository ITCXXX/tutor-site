# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=86: OGE6: Тип 1+2 — обыкн. дроби ±
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



def decimal_str(f):
    if f.denominator == 1:
        return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1:
        return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad_num = num * (10 ** target) // den
    s = str(pad_num).rjust(target + 1, '0')
    int_part = s[:-target] or '0'
    dec_part = s[-target:].rstrip('0')
    return sign + (int_part + ',' + dec_part if dec_part else int_part)


def generate_task():
    """
    №6 ОГЭ, Тип 1+2: a/b ± c/d.
    Берём две положительные обыкновенные дроби с «удобными» знаменателями
    (только множители 2 и 5), считаем результат — он автоматически
    конечная десятичная дробь.
    """
    NICE_DENOMS = [2, 4, 5, 10, 20, 25, 50]
    op = random.choice(['+', '-'])

    for _ in range(50):
        b = random.choice(NICE_DENOMS)
        d = random.choice(NICE_DENOMS)
        a = random.randint(1, 4 * b)
        c = random.randint(1, 4 * d)
        f1 = Fraction(a, b)
        f2 = Fraction(c, d)
        if f1.denominator == 1 or f2.denominator == 1:
            continue
        R = f1 + f2 if op == '+' else f1 - f2
        if R == 0:
            continue
        if abs(R.numerator) > 200:
            continue
        break
    else:
        f1 = Fraction(1, 2); f2 = Fraction(3, 10); R = f1 + f2; op = '+'

    def flatex(f):
        return rf"\dfrac{{{f.numerator}}}{{{f.denominator}}}"

    expression = f"{flatex(f1)} {op} {flatex(f2)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
