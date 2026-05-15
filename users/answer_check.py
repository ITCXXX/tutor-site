# -*- coding: utf-8 -*-
"""
Универсальная проверка ответов: целые числа, десятичные дроби, обыкновенные дроби.
Если ученик вводит обыкновенную дробь — дополнительно проверяется её несократимость.

Поддерживаемые форматы:
    "5", "-7", "0", "  3 "
    "0.25", "-2.5", "0,5"  (точка и запятая равноправны)
    "3/4", "-5/12", "7/-3"
    "  1 / 3  "  (пробелы вокруг разрешены)
"""

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import gcd


class AnswerError(ValueError):
    pass


def _parse(s):
    """Возвращает (value: Fraction, is_fraction_form: bool, raw_num, raw_denom).

    Для дробного ввода raw_num/raw_denom — целые в том виде, как написал ученик
    (нужно для проверки сократимости). Для нечислового ответа — AnswerError.
    """
    if s is None:
        raise AnswerError('пустой ответ')
    s = str(s).strip().replace(' ', '')
    if not s:
        raise AnswerError('пустой ответ')

    if '/' in s:
        parts = s.split('/')
        if len(parts) != 2:
            raise AnswerError('некорректная дробь')
        try:
            num = int(parts[0])
            denom = int(parts[1])
        except ValueError:
            raise AnswerError('нечисловой числитель или знаменатель')
        if denom == 0:
            raise AnswerError('нулевой знаменатель')
        return Fraction(num, denom), True, num, denom

    # обычное число (с точкой или запятой)
    try:
        d = Decimal(s.replace(',', '.'))
    except InvalidOperation:
        raise AnswerError('не число')
    return Fraction(d), False, None, None


def check_answer(user_answer, correct_answer,
                 tolerance=Fraction(1, 1000), allow_fractions=True):
    """Возвращает (is_correct: bool, message: str | None).

    allow_fractions=False — отклоняет ввод вида «3/4» (актуально для ОГЭ,
    где принимаются только десятичные дроби).
    """
    if user_answer is None:
        user_answer = ''

    try:
        user_val, user_is_frac, raw_n, raw_d = _parse(user_answer)
    except AnswerError:
        if str(user_answer).strip().lower() == str(correct_answer or '').strip().lower():
            return True, None
        return False, None

    # ОГЭ: дробь как форма ответа недопустима
    if user_is_frac and not allow_fractions:
        return False, 'На ОГЭ ответ записывается десятичной дробью'

    try:
        correct_val, _, _, _ = _parse(correct_answer)
    except AnswerError:
        if str(user_answer).strip().lower() == str(correct_answer or '').strip().lower():
            return True, None
        return False, None

    if abs(user_val - correct_val) > tolerance:
        return False, None

    if user_is_frac and raw_d != 0:
        if raw_n == 0:
            return False, 'Запишите ответ как 0 (без дроби)'
        if gcd(abs(raw_n), abs(raw_d)) != 1:
            return False, 'Сократите дробь'

    return True, None
