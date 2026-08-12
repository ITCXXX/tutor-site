# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=88: OGE6: Тип 5+6 — десятичные ±
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
    №6 ОГЭ, Тип 5+6: десятичная ± десятичная.
    Берём a, b ∈ [1.1, 9.9] с одним знаком после запятой (исключая целые),
    считаем R = a ± b.
    """
    op = random.choice(['+', '-'])
    for _ in range(50):
        a_int = random.randint(11, 99)
        b_int = random.randint(11, 99)
        if a_int % 10 == 0 or b_int % 10 == 0:
            continue
        a = Fraction(a_int, 10)
        b = Fraction(b_int, 10)
        R = a + b if op == '+' else a - b
        if R == 0:
            continue
        break
    else:
        a = Fraction(56, 10); b = Fraction(38, 10); R = a + b; op = '+'

    expression = f"{decimal_str(a)} {op} {decimal_str(b)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
