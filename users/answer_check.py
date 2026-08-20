# -*- coding: utf-8 -*-
r"""
Универсальная проверка ответов с поддержкой LaTeX-команд.

Поддерживаемые форматы ввода:

    Простые:
        "5", "-7", "0", "  3 "                      — целые
        "0.25", "-2.5", "0,5"                       — десятичные (точка/запятая)
        "3/4", "-5/12"                              — обыкновенные дроби (запись «через слэш»)

    LaTeX-команды:
        \frac{a}{b}         — дробь        \frac{3}{4}
        \sqrt{n}            — корень       \sqrt{2}
        \frac{\sqrt{n}}{b}  — корень в числителе
        a\sqrt{n}           — коэффициент перед корнем,  2\sqrt{3}
        \frac{a\sqrt{n}}{b} — коэф. с корнем в числителе, \frac{2\sqrt{3}}{5}
        \frac{a}{b}\sqrt{n} — менее частая запись,        \frac{1}{2}\sqrt{3}

    Знаки и пробелы:
        Минус в начале или внутри числителя/знаменателя:  -\frac{1}{2}, \frac{-3}{4}
        Пробелы вокруг и внутри игнорируются

Алгоритм проверки:
    1. Парсим строку рекурсивным спуском в float.
    2. Сравниваем с эталоном численно (точность 1e-6 по умолчанию).
    3. Для дробей и корней дополнительно проверяем каноническую форму:
        – обыкновенная дробь должна быть несократимой;
        – подкоренное выражение не должно содержать полных квадратов > 1;
        – коэффициент и знаменатель внешней дроби с корнем должны быть взаимно просты.
"""

import math
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import gcd


class AnswerError(ValueError):
    pass


# ============================================================
#   Парсер LaTeX → float
# ============================================================

def _find_matching_brace(s, open_idx):
    """`open_idx` указывает на «{». Возвращает индекс соответствующей «}»."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    raise AnswerError('несбалансированные скобки')


_RX_NUM = re.compile(r'^(\d+(?:\.\d+)?)')


def _parse_expr(s):
    r"""Рекурсивно парсит LaTeX-подстроку в float, возвращает (value, consumed_len).
    Логика: первый «фактор» (число, \frac{}, \sqrt{}), потом, если есть продолжение
    без оператора (как в записи 2\sqrt{3}), умножаем.
    """
    if not s:
        raise AnswerError('пустое выражение')

    sign = 1
    pos = 0
    if s[pos] == '-':
        sign = -1
        pos += 1
    elif s[pos] == '+':
        pos += 1

    if pos >= len(s):
        raise AnswerError('висячий знак')

    # Первый фактор
    value, used = _parse_factor(s[pos:])
    pos += used
    value *= sign

    # «Слипшийся» множитель: 2\sqrt{3}, \frac{1}{2}\sqrt{3} и т. п.
    # Но НЕ если впереди явный оператор + или - — там должен быть отдельный
    # вызов; в нашей грамматике плюс/минус «внутри» не используем.
    while pos < len(s) and s[pos] not in '+-':
        more_val, more_used = _parse_factor(s[pos:])
        value *= more_val
        pos += more_used

    return value, pos


def _parse_factor(s):
    r"""Парсит ОДИН фактор: число | \frac{}{} | \sqrt{}. Возвращает (value, used)."""
    if s.startswith('\\frac{'):
        # Числитель
        open1 = 5  # позиция «{» сразу после \frac
        close1 = _find_matching_brace(s, open1)
        num_str = s[open1 + 1: close1]
        # Знаменатель
        if close1 + 1 >= len(s) or s[close1 + 1] != '{':
            raise AnswerError('у \\frac не найден знаменатель')
        open2 = close1 + 1
        close2 = _find_matching_brace(s, open2)
        denom_str = s[open2 + 1: close2]
        num_val, _ = _parse_expr(num_str)
        denom_val, _ = _parse_expr(denom_str)
        if denom_val == 0:
            raise AnswerError('деление на ноль')
        return num_val / denom_val, close2 + 1

    if s.startswith('\\sqrt{'):
        open1 = 5
        close1 = _find_matching_brace(s, open1)
        rad_str = s[open1 + 1: close1]
        rad_val, _ = _parse_expr(rad_str)
        if rad_val < 0:
            raise AnswerError('отрицательное подкоренное')
        return math.sqrt(rad_val), close1 + 1

    m = _RX_NUM.match(s)
    if m:
        return float(m.group(1)), len(m.group(1))

    raise AnswerError(f'неизвестный фрагмент: {s[:10]!r}')


def _normalize(s):
    if s is None:
        raise AnswerError('пустой ответ')
    s = str(s).strip()
    if not s:
        raise AnswerError('пустой ответ')
    s = s.replace(' ', '').replace(',', '.')
    return s


def _is_latex(s):
    """Есть ли в строке LaTeX-команды."""
    return '\\frac' in s or '\\sqrt' in s


def _parse_simple(s):
    """Старый парсер: целое, десятичное, обыкновенная дробь через `/`.
    Возвращает (float_value, kind, extra).
    """
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
        return float(Fraction(num, denom)), 'fraction', (num, denom)

    try:
        d = Decimal(s)
    except InvalidOperation:
        raise AnswerError('не число')
    return float(d), 'plain', None


def _parse_any(s_norm):
    """Возвращает (float_value, kind, extra_for_canon_check).

    kind ∈ {'plain', 'fraction', 'latex'}.
    Для 'latex' extra — исходная нормализованная строка (для проверки канон. формы).
    """
    if _is_latex(s_norm):
        val, used = _parse_expr(s_norm)
        if used != len(s_norm):
            raise AnswerError('лишние символы после выражения')
        return val, 'latex', s_norm
    return _parse_simple(s_norm)


# ============================================================
#   Проверка канонической формы для LaTeX
# ============================================================

_RX_FRAC_BLOCK = re.compile(r'\\frac\{(-?\d+)\}\{(-?\d+)\}')
_RX_SQRT_BLOCK = re.compile(r'\\sqrt\{(\d+)\}')


def _check_latex_canonical(s_norm):
    r"""Возвращает message или None, если форма канонична.
    Эвристика, без полного символьного упрощения:
      * Каждая прямая обыкновенная дробь \\frac{a}{b} с целыми a,b должна быть несократимой.
      * Каждое \\sqrt{n} не должно содержать делителей вида k², k≥2.
    Сложные комбинации (\\frac{a\\sqrt{b}}{c}) — частично: ищем коэф. перед \\sqrt
    внутри числителя \\frac и проверяем gcd с знаменателем.
    """
    # 1) Все простые \frac{a}{b}
    for m in _RX_FRAC_BLOCK.finditer(s_norm):
        a, b = int(m.group(1)), int(m.group(2))
        if b == 0:
            return 'деление на ноль'
        if a == 0:
            return 'Запишите ответ как 0 (без дроби)'
        if gcd(abs(a), abs(b)) != 1:
            return 'Сократите дробь'

    # 2) Все \sqrt{n} — без полных квадратов
    for m in _RX_SQRT_BLOCK.finditer(s_norm):
        n = int(m.group(1))
        if n < 0:
            return 'отрицательное подкоренное'
        k = 2
        while k * k <= n:
            if n % (k * k) == 0:
                return 'Вынесите множитель из-под корня'
            k += 1

    # 3) \frac{a\sqrt{b}}{c} — взаимная простота a и c
    pattern = re.compile(r'\\frac\{(-?\d+)\\sqrt\{(\d+)\}\}\{(-?\d+)\}')
    for m in pattern.finditer(s_norm):
        a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if c == 0:
            return 'деление на ноль'
        if gcd(abs(a), abs(c)) != 1:
            return 'Сократите дробь'

    # 4) \frac{\sqrt{b}}{c} с c != ±1 проверять gcd(1, c) бессмысленно — пропускаем

    return None


# ============================================================
#   Главная функция
# ============================================================

def check_answer(user_answer, correct_answer,
                 tolerance=1e-6, allow_fractions=True):
    """Возвращает (is_correct: bool, message: str | None).

    Численное сравнение с заданной точностью, плюс проверка канонической формы
    для дробей и корней.

    allow_fractions=False — отклоняет обыкновенные дроби (для ОГЭ, где
    допустимы только десятичные дроби в ответе).

    Мульти-ответ (вторая часть, несколько корней): если эталон содержит «;»,
    ответ ученика тоже разбивается по «;» и сравнивается как множество
    (порядок не важен, каждый корень должен встретиться ровно один раз).
    """
    if user_answer is None:
        user_answer = ''

    # ── Режим нескольких ответов (например, "-5;-2;2") ─────────
    if ';' in str(correct_answer or ''):
        return _check_answer_multi(
            user_answer, correct_answer,
            tolerance=tolerance, allow_fractions=allow_fractions,
        )

    try:
        s_user = _normalize(user_answer)
        u_val, u_kind, u_extra = _parse_any(s_user)
    except AnswerError:
        if str(user_answer).strip().lower() == str(correct_answer or '').strip().lower():
            return True, None
        return False, None

    if u_kind == 'fraction' and not allow_fractions:
        return False, 'На ОГЭ ответ записывается десятичной дробью'

    try:
        s_corr = _normalize(correct_answer)
        c_val, _, _ = _parse_any(s_corr)
    except AnswerError:
        if str(user_answer).strip().lower() == str(correct_answer or '').strip().lower():
            return True, None
        return False, None

    if abs(u_val - c_val) > tolerance:
        return False, None

    # === Каноническая форма ===
    if u_kind == 'fraction':
        raw_n, raw_d = u_extra
        if raw_n == 0:
            return False, 'Запишите ответ как 0 (без дроби)'
        if gcd(abs(raw_n), abs(raw_d)) != 1:
            return False, 'Сократите дробь'

    if u_kind == 'latex':
        msg = _check_latex_canonical(u_extra)
        if msg:
            return False, msg

    return True, None


# ============================================================
#   Мульти-ответ (несколько корней, вторая часть ОГЭ)
# ============================================================

def _check_answer_multi(user_answer, correct_answer,
                        tolerance=1e-6, allow_fractions=True):
    """Сравнение наборов ответов, разделённых «;».

    Порядок не важен. Каждый элемент проверяется обычным check_answer
    (значение + каноническая форма). Дубликаты не засчитываются:
    количество введённых ответов должно совпадать с эталоном.
    """
    corr_parts = [p for p in str(correct_answer).split(';') if p.strip()]
    user_parts = [p for p in str(user_answer).split(';') if p.strip()]

    if not user_parts:
        return False, None

    if len(user_parts) != len(corr_parts):
        return False, 'Проверьте количество корней'

    remaining = list(corr_parts)
    for up in user_parts:
        matched_idx = None
        first_msg = None
        for i, cp in enumerate(remaining):
            ok, msg = check_answer(up, cp, tolerance=tolerance,
                                   allow_fractions=allow_fractions)
            if ok:
                matched_idx = i
                break
            # Запоминаем содержательное сообщение («Сократите дробь» и т. п.):
            # значение совпало, но форма не каноническая.
            if msg and first_msg is None:
                first_msg = msg
        if matched_idx is None:
            return False, first_msg
        remaining.pop(matched_idx)

    return True, None
