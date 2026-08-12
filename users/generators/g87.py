# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=87: OGE6: Тип 3+4 — обыкн. дроби ·/:
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
    №6 ОГЭ, Тип 3+4: a/b · c/d или a/b : c/d.
    Идём от ответа: фиксируем R с конечным десятичным представлением,
    подбираем первую дробь f1, считаем f2 = R/f1 (умножение)
    или f2 = f1/R (деление).
    """
    op = random.choice(['*', '/'])

    for _ in range(80):
        R_den = random.choice([1, 2, 4, 5, 10, 20, 50])
        R_num = random.randint(1, 80)
        R = Fraction(R_num, R_den)

        b = random.randint(2, 20)
        a = random.randint(1, 30)
        f1 = Fraction(a, b)

        if op == '*':
            f2 = R / f1
        else:
            f2 = f1 / R

        if f2 == 0: continue
        if abs(f2.numerator) > 80 or f2.denominator > 80: continue
        if f1.denominator == 1: continue
        if f2.denominator == 1: continue
        break
    else:
        f1 = Fraction(3, 5); f2 = Fraction(7, 4); op = '*'; R = f1 * f2

    def flatex(f):
        return rf"\dfrac{{{f.numerator}}}{{{f.denominator}}}" if f.denominator > 1 else str(f.numerator)

    op_latex = r"\cdot" if op == '*' else ":"
    expression = f"{flatex(f1)} {op_latex} {flatex(f2)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
