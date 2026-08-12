# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=89: OGE6: Тип 7+8 — десятичные ·/:
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
    №6 ОГЭ, Тип 7+8: десятичная · десятичная или десятичная : десятичная.

    Умножение: a, b — оба с одной цифрой после запятой, R = a·b.
    Деление: ответ R и делитель b — десятичные ≤2 знаков (берём целое из
    [1, 999] и делим на 100). Делимое a = R·b — может иметь до 4 цифр после
    запятой. Ответ — произвольная десятичная дробь (возможны и целые случаи).
    """
    op = random.choice(['*', '/'])

    if op == '*':
        for _ in range(40):
            a_int = random.randint(11, 99)
            b_int = random.randint(11, 99)
            if a_int % 10 == 0 or b_int % 10 == 0:
                continue
            a = Fraction(a_int, 10)
            b = Fraction(b_int, 10)
            R = a * b
            break
        op_latex = r"\cdot"
    else:
        for _ in range(80):
            R_int = random.randint(11, 999)
            b_int = random.randint(11, 999)
            # Пропускаем R = 1 и b = 1 (тривиально).
            if R_int == 100 or b_int == 100:
                continue
            R = Fraction(R_int, 100)
            b = Fraction(b_int, 100)
            a = R * b
            # Масштаб делимого: 0,1 ≤ a ≤ 50.
            if a < Fraction(1, 10) or a > Fraction(50):
                continue
            break
        else:
            R = Fraction(36, 10); b = Fraction(25, 10); a = R * b
        op_latex = ":"

    expression = f"{decimal_str(a)} {op_latex} {decimal_str(b)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
