# -*- coding: utf-8 -*-
"""Параметрические генераторы задач ОГЭ, №20 (вторая часть).

Каждый тип — отдельная функция-генератор get_typeN(rng) -> dict:
    {
      'type':        int,                # номер типа (1..25)
      'title':       str,                # '№20. Тип 1'
      'question_html': str,              # условие (HTML + LaTeX \\( \\))
      'answer':      str,                # итоговый ответ для авто-проверки ('-5; -2; 2')
      'answer_set':  list,               # структурно (Fraction|int) для проверки
      'answer_kind': 'roots' | 'interval',
      'solution_html': str,              # оформленное решение (HTML + LaTeX)
      'params':      dict,               # параметры (для воспроизводимости)
    }

Решение оформлено в стиле банка ФИПИ / Школково: «Решение:» → пошаговые
преобразования (display-формулы \\[ \\]) → совокупность → «Ответ:».

Модуль самодостаточный (без Django) — можно гонять самотестом:
    venv/Scripts/python.exe -X utf8 users/oge20_generators.py
"""

import random
from fractions import Fraction


# --------------------------------------------------------------------------
# LaTeX-хелперы
# --------------------------------------------------------------------------

def poly_latex(coeffs, var='x'):
    """coeffs — от старшей степени к младшей. Возвращает LaTeX многочлена."""
    n = len(coeffs) - 1
    out = []
    for i, c in enumerate(coeffs):
        p = n - i
        if c == 0:
            continue
        a = abs(c)
        if p == 0:
            body = str(a)
        else:
            coef = '' if a == 1 else str(a)
            vp = var if p == 1 else f'{var}^{{{p}}}'
            body = coef + vp
        if not out:
            out.append(('-' if c < 0 else '') + body)
        else:
            out.append((' - ' if c < 0 else ' + ') + body)
    return ''.join(out) if out else '0'


def num_latex(v):
    """Целое или дробь → LaTeX (-\\frac{1}{2}, 3, \\frac{2}{3})."""
    f = Fraction(v)
    if f.denominator == 1:
        return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    return f'{sign}\\frac{{{abs(f.numerator)}}}{{{f.denominator}}}'


def num_plain(v):
    """Целое или дробь → строка для поля ответа ('-1/2', '3')."""
    f = Fraction(v)
    if f.denominator == 1:
        return str(f.numerator)
    return f'{f.numerator}/{f.denominator}'


def roots_answer(roots):
    """Список корней → ('канонический ответ', отсортированный список Fraction)."""
    uniq = sorted({Fraction(r) for r in roots})
    return '; '.join(num_plain(r) for r in uniq), uniq


def roots_latex(roots):
    uniq = sorted({Fraction(r) for r in roots})
    return ';\\ '.join(num_latex(r) for r in uniq)


def _sol(*blocks):
    return ''.join(blocks)


def _p(text):
    return f'<p>{text}</p>'


def _disp(latex):
    return f'\\[{latex}\\]'


def _cases(lines):
    """Совокупность: левая квадратная скобка + строки."""
    body = ' \\\\ '.join(lines)
    return f'\\left[\\begin{{array}}{{l}} {body} \\end{{array}}\\right.'


# --------------------------------------------------------------------------
# Метод интервалов — общий решатель для неравенств
# --------------------------------------------------------------------------
#
# Все типы 17–25 после преобразований сводятся к одному виду: произведение и
# частное скобок вида (x - r) в степенях, знак которого надо сравнить с нулём.
# Выводить ответ для каждого типа руками — одиннадцать возможностей ошибиться,
# причём ошибка будет тихой: задача выглядит правильно, а засчитывается
# неверно. Поэтому ответ считает один решатель, а генераторы только объявляют
# разложение на множители.
#
# Разложение задаётся списком (корень, кратность, где) — «num» для числителя,
# «den» для знаменателя, — плюс знак постоянного множителя. Кратности
# складываются: если корень есть и сверху и снизу поровну, он сокращается, но
# точка всё равно выкалывается — это выколотая точка типа 19.

INTERVAL_INF = float('inf')


def solve_sign_inequality(factors, op, const_sign=1):
    """
    Решить неравенство вида const * П(x - r)^k / П(x - r)^k  op  0.

    factors — [(корень, кратность, 'num'|'den'), ...]
    op      — '<', '<=', '>', '>='
    Возвращает список промежутков [(низ, низ_включён, верх, верх_включён), ...]
    в том же виде, в каком их понимает проверка ответов.
    """
    net = {}
    for root, mult, where in factors:
        net[root] = net.get(root, 0) + (mult if where == 'num' else -mult)

    roots = sorted(net)
    strict = op in ('<', '>')
    want_positive = op in ('>', '>=')

    def sign_at(x):
        """
        Знак выражения в точке, где оно определено и не равно нулю.

        Скобка (x - r) в чётной степени знака не меняет никогда, в нечётной —
        меняет левее своего корня. Отсюда весь метод интервалов и состоит.
        """
        s = const_sign
        for r, power in net.items():
            if power % 2 and x < r:
                s = -s
        return s

    # Область определения задаёт ИСХОДНОЕ выражение, а не сокращённое: любой
    # корень знаменателя выкалывается, даже если после сокращения он стал
    # обычным нулём. Иначе (x+3)²(x+1)/(x+3) включало бы точку -3, где на
    # самом деле ноль на ноль.
    excluded = {r for r, _m, where in factors if where == 'den'}
    zeros = {r for r, p in net.items() if p > 0 and r not in excluded}

    # Пробные точки между корнями
    bounds = [-INTERVAL_INF] + roots + [INTERVAL_INF]
    pieces = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        if lo == -INTERVAL_INF and hi == INTERVAL_INF:
            probe = 0.0
        elif lo == -INTERVAL_INF:
            probe = hi - 1.0
        elif hi == INTERVAL_INF:
            probe = lo + 1.0
        else:
            probe = (lo + hi) / 2.0
        good = (sign_at(probe) > 0) == want_positive
        if good:
            pieces.append((lo, False, hi, False))

    # Нули числителя включаются, если неравенство нестрогое
    if not strict:
        for r in sorted(zeros):
            pieces.append((r, True, r, True))

    # Склейка: смежные куски объединяются, если общая точка входит в ответ
    pieces.sort(key=lambda p: (p[0], not p[1]))
    merged = []
    for lo, lo_c, hi, hi_c in pieces:
        if merged and (lo < merged[-1][2]
                       or (lo == merged[-1][2] and (merged[-1][3] or lo_c))):
            prev = merged[-1]
            if hi > prev[2] or (hi == prev[2] and hi_c):
                prev[2], prev[3] = hi, hi_c
        else:
            merged.append([lo, lo_c, hi, hi_c])

    # Выколотые точки: полюсы и сократившиеся корни вырезаем из ответа
    result = []
    for lo, lo_c, hi, hi_c in merged:
        chunk = [(lo, lo_c, hi, hi_c)]
        for bad in sorted(excluded):
            new_chunk = []
            for a, a_c, b, b_c in chunk:
                if not (a < bad < b or (a == bad and a_c) or (b == bad and b_c)):
                    new_chunk.append((a, a_c, b, b_c))
                    continue
                if a < bad:
                    new_chunk.append((a, a_c, bad, False))
                if bad < b:
                    new_chunk.append((bad, False, b, b_c))
            chunk = new_chunk
        result.extend(chunk)

    return [p for p in result if p[0] < p[2] or (p[0] == p[2] and p[1] and p[3])]


def interval_answer(pieces):
    """Промежутки → строка ответа в том виде, который принимает проверка."""
    def end(v):
        if v == -INTERVAL_INF:
            return '-∞'
        if v == INTERVAL_INF:
            return '+∞'
        f = Fraction(v).limit_denominator(10 ** 6)
        return num_plain(f)

    out = []
    for lo, lo_c, hi, hi_c in pieces:
        if lo == hi:
            out.append('{%s}' % end(lo))
        else:
            out.append('%s%s; %s%s' % ('[' if lo_c else '(', end(lo),
                                       end(hi), ']' if hi_c else ')'))
    return ' + '.join(out)


def interval_latex(pieces):
    def end(v):
        if v == -INTERVAL_INF:
            return '-\\infty'
        if v == INTERVAL_INF:
            return '+\\infty'
        return num_latex(Fraction(v).limit_denominator(10 ** 6))

    out = []
    for lo, lo_c, hi, hi_c in pieces:
        if lo == hi:
            out.append('\\{%s\\}' % end(lo))
        else:
            out.append('%s%s;\\ %s%s' % ('\\left[' if lo_c else '\\left(', end(lo),
                                         end(hi), '\\right]' if hi_c else '\\right)'))
    return ' \\cup '.join(out)


# --------------------------------------------------------------------------
# Тип 1. Кубическое уравнение, группировка: x^3 + b x^2 - c x - bc = 0
# --------------------------------------------------------------------------

def get_type1(rng):
    b = rng.choice([2, 3, 4, 5, 6, 7])
    k = rng.choice([2, 3, 4, 5, 6])
    while k == b:                       # чтобы корни -b, k, -k были различны
        k = rng.choice([2, 3, 4, 5, 6])
    c = k * k
    coeffs = [1, b, -c, -b * c]
    eq = poly_latex(coeffs) + ' = 0'
    roots = [-b, k, -k]
    ans, ans_set = roots_answer(roots)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Сгруппируем слагаемые и вынесем общие множители:'),
        _disp(f'x^2(x + {b}) - {c}(x + {b}) = 0,'),
        _disp(f'(x + {b})(x^2 - {c}) = 0.'),
        _p('Разложим второй множитель по формуле разности квадратов:'),
        _disp(f'(x + {b})(x - {k})(x + {k}) = 0.'),
        _p('Произведение равно нулю, когда хотя бы один из множителей равен нулю:'),
        _disp(_cases([f'x + {b} = 0', f'x - {k} = 0', f'x + {k} = 0'])
              + '\\quad\\Leftrightarrow\\quad'
              + _cases([f'x = {-b}', f'x = {k}', f'x = {-k}']) + '.'),
        _p(f'<b>Ответ:</b> \\({roots_latex(roots)}.\\)'),
    )
    return {
        'type': 1, 'title': '№20. Тип 1',
        'question_html': _p(f'Решите уравнение \\({eq}.\\)'),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'solution_html': sol, 'params': {'b': b, 'k': k, 'c': c},
    }


# --------------------------------------------------------------------------
# Тип 4. x^4 = (a x - b)^2
# --------------------------------------------------------------------------

def _int_roots(A, B, C):
    """Целочисленные корни A x^2 + B x + C = 0 (A=1). Возвращает [] если не все целые/нет вещественных."""
    disc = B * B - 4 * A * C
    if disc < 0:
        return None                     # нет вещественных корней
    s = int(round(disc ** 0.5))
    if s * s != disc:
        return 'nonint'                 # вещественные, но не целые
    r1 = Fraction(-B + s, 2 * A)
    r2 = Fraction(-B - s, 2 * A)
    return sorted({r1, r2})


def get_type4(rng):
    while True:
        a = rng.choice([2, 3, 4, 5])
        b = rng.choice([3, 4, 5, 6, 7, 8, 9])
        # x^4 - (ax-b)^2 = 0 -> (x^2 - ax + b)(x^2 + ax - b) = 0
        rA = _int_roots(1, -a, b)       # x^2 - a x + b = 0
        rB = _int_roots(1, a, -b)       # x^2 + a x - b = 0
        if rA == 'nonint' or rB == 'nonint':
            continue
        roots = []
        for r in (rA or []):
            roots.append(r)
        for r in (rB or []):
            roots.append(r)
        roots = sorted(set(roots))
        # хотим 2–4 целых корня и хотя бы одну "пустую/полную" ветку для разнообразия
        if 1 <= len(roots) <= 4 and all(r.denominator == 1 for r in roots):
            break

    rhs = poly_latex([a, -b])           # a x - b
    ans, ans_set = roots_answer(roots)

    # описания веток
    def branch_text(coeffsA, label):
        rr = _int_roots(1, coeffsA[1], coeffsA[2])
        eq = poly_latex([1, coeffsA[1], coeffsA[2]]) + ' = 0'
        if rr is None:
            return _p(f'Уравнение \\({eq}\\) не имеет корней (дискриминант отрицателен).')
        rl = ';\\ '.join(num_latex(r) for r in rr)
        return _p(f'\\({eq}\\) \\(\\Rightarrow\\) \\(x = {rl}.\\)')

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Перенесём всё в левую часть и применим формулу разности квадратов '
           '\\(p^2 - q^2 = (p-q)(p+q)\\), где \\(p = x^2,\\ q = {0}\\):'.format(rhs)),
        _disp(f'x^4 - ({rhs})^2 = 0,'),
        _disp(f'\\left(x^2 - ({rhs})\\right)\\left(x^2 + ({rhs})\\right) = 0.'),
        _p('Раскроем скобки в каждом множителе и решим два квадратных уравнения:'),
        branch_text([1, -a, b], 'A'),
        branch_text([1, a, -b], 'B'),
        _p(f'<b>Ответ:</b> \\({roots_latex(roots)}.\\)'),
    )
    return {
        'type': 4, 'title': '№20. Тип 4',
        'question_html': _p(f'Решите уравнение \\(x^4 = ({rhs})^2.\\)'),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'solution_html': sol, 'params': {'a': a, 'b': b},
    }


# --------------------------------------------------------------------------
# Тип 7. 1/x^2 + b/x + c = 0, замена t = 1/x
# --------------------------------------------------------------------------

def get_type7(rng):
    # корни по t (целые, ненулевые, различные) -> x = 1/t
    while True:
        t1 = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4, 5, 6])
        t2 = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4, 5, 6])
        if t1 != t2:
            break
    b = -(t1 + t2)
    c = t1 * t2
    # уравнение: 1/x^2 + b/x + c = 0
    lhs = '\\frac{1}{x^2}'
    if b != 0:
        lhs += (' + ' if b > 0 else ' - ') + (f'\\frac{{{abs(b)}}}{{x}}' if abs(b) != 1 else '\\frac{1}{x}')
    if c != 0:
        lhs += (' + ' if c > 0 else ' - ') + str(abs(c))
    eq = lhs + ' = 0'

    roots = [Fraction(1, t1), Fraction(1, t2)]
    ans, ans_set = roots_answer(roots)
    tpoly = poly_latex([1, b, c], var='t') + ' = 0'

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Область допустимых значений: \\(x \\ne 0\\). Сделаем замену '
           '\\(t = \\dfrac{1}{x}\\); тогда \\(\\dfrac{1}{x^2} = t^2\\), и уравнение примет вид'),
        _disp(tpoly + '.'),
        _p('Его корни:'),
        _disp(_cases([f't = {t1}', f't = {t2}']) + '.'),
        _p('Вернёмся к переменной \\(x\\) по формуле \\(x = \\dfrac{1}{t}\\):'),
        _disp(_cases([f'x = \\dfrac{{1}}{{{t1}}} = {num_latex(Fraction(1, t1))}',
                      f'x = \\dfrac{{1}}{{{t2}}} = {num_latex(Fraction(1, t2))}']) + '.'),
        _p(f'<b>Ответ:</b> \\({roots_latex(roots)}.\\)'),
    )
    return {
        'type': 7, 'title': '№20. Тип 7',
        'question_html': _p(f'Решите уравнение \\({eq}.\\)'),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'solution_html': sol, 'params': {'b': b, 'c': c, 't1': t1, 't2': t2},
    }


# --------------------------------------------------------------------------
# Тип 16 (новый). x <= a/x, a = k^2  ->  интервалы
# --------------------------------------------------------------------------

def get_type16(rng):
    k = rng.choice([2, 3, 4, 5, 6, 7, 8])
    a = k * k
    # x <= a/x  ->  (x^2 - a)/x <= 0  ->  (x-k)(x+k)/x <= 0
    ans = f'(-∞; -{k}] + (0; {k}]'
    interval = [('-inf', -k, False, True), (0, k, False, True)]  # для проверки

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Область допустимых значений: \\(x \\ne 0\\). Перенесём всё в левую часть '
           'и приведём к общему знаменателю:'),
        _disp(f'x - \\frac{{{a}}}{{x}} \\le 0 \\quad\\Leftrightarrow\\quad '
              f'\\frac{{x^2 - {a}}}{{x}} \\le 0.'),
        _p('Разложим числитель по формуле разности квадратов:'),
        _disp(f'\\frac{{(x - {k})(x + {k})}}{{x}} \\le 0.'),
        _p(f'Отметим на числовой прямой нули числителя \\(x = \\pm{k}\\) и нуль '
           f'знаменателя \\(x = 0\\) (выколот) и расставим знаки методом интервалов. '
           f'Неравенство нестрогое, поэтому \\(x = \\pm{k}\\) включаем, а \\(x = 0\\) — нет.'),
        _disp(f'x \\in (-\\infty;\\ -{k}\\,] \\cup (\\,0;\\ {k}\\,].'),
        _p(f'<b>Ответ:</b> \\((-\\infty;\\ -{k}\\,] \\cup (\\,0;\\ {k}\\,].\\)'),
    )
    return {
        'type': 16, 'title': '№20. Тип 16',
        'question_html': _p(f'Решите неравенство \\(x \\le \\dfrac{{{a}}}{{x}}.\\)'),
        'answer': ans, 'answer_set': interval, 'answer_kind': 'interval',
        'solution_html': sol, 'params': {'k': k, 'a': a},
    }


# --------------------------------------------------------------------------
# Реестр
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Тип 2. Кубическое уравнение, слагаемые по разные стороны:
#        x^3 + a x^2 = b x + a b,   b = k^2
# --------------------------------------------------------------------------
#
# Разложение то же, что в типе 1 — (x + a)(x^2 - b) = 0, — меняется только
# вёрстка условия: часть слагаемых перенесена вправо. В банке ФИПИ это
# отдельный тип, потому что первый шаг решения другой: сначала собрать всё
# в одну сторону, и только потом группировать.
#
# Знак при a разворачивается: при a < 0 получается (x - |a|)(x^2 - b), и
# корень -a становится положительным. Задача та же, а вид другой.

def get_type2(rng):
    a0 = rng.choice([2, 3, 4, 5, 6, 7])
    k = rng.choice([2, 3, 4, 5, 6])
    while k == a0:                      # иначе корни -a и ±k совпадут
        k = rng.choice([2, 3, 4, 5, 6])
    a = a0 * rng.choice([1, -1])        # зеркало по знаку
    b = k * k

    left = poly_latex([1, a, 0, 0])[:-2].rstrip() if False else None
    # левая часть: x^3 + a x^2, правая: b x + a b
    left = poly_latex([1, a]) .replace('x', 'x')  # заглушка не нужна
    left = poly_latex([1, a, 0, 0])
    left = left.split(' - 0')[0].split(' + 0')[0]
    right = poly_latex([b, a * b])
    eq = left + ' = ' + right

    roots = [-a, k, -k]
    ans, ans_set = roots_answer(roots)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Перенесём все слагаемые в левую часть и сгруппируем:'),
        _disp(poly_latex([1, a, -b, -a * b]) + ' = 0,'),
        _disp('x^2(x ' + ('+ %d' % a if a > 0 else '- %d' % -a) + ') - '
              + str(b) + '(x ' + ('+ %d' % a if a > 0 else '- %d' % -a) + ') = 0,'),
        _disp('(x ' + ('+ %d' % a if a > 0 else '- %d' % -a) + ')(x^2 - ' + str(b) + ') = 0.'),
        _p('Второй множитель — разность квадратов:'),
        _disp('(x ' + ('+ %d' % a if a > 0 else '- %d' % -a)
              + ')(x - %d)(x + %d) = 0.' % (k, k)),
        _p('Произведение равно нулю, когда нулю равен хотя бы один множитель:'),
        _disp(_cases(['x = %d' % -a, 'x = %d' % k, 'x = %d' % -k]) + '.'),
        _p('<b>Ответ:</b> \\(' + roots_latex(roots) + '.\\)'),
    )
    return {
        'type': 2, 'title': '№20. Тип 2',
        'question_html': _p('Решите уравнение \\(' + eq + '.\\)'),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'solution_html': sol, 'params': {'a': a, 'k': k, 'b': b},
    }


# --------------------------------------------------------------------------
# Тип 3. (x - p)(x + q)^2 = c(x + q) — вынесение общего множителя
# --------------------------------------------------------------------------
#
# Ключ решения: не делить обе части на (x + q), иначе теряется корень -q.
# Правильно — перенести и вынести: (x + q)[(x - p)(x + q) - c] = 0.
#
# Генерируем от ответа. Задаём корни квадратного множителя r1 и r2 и число q,
# тогда p = r1 + r2 + q и c = -p q - r1 r2 — обе величины выводятся из
# условий Виета, перебирать ничего не нужно. Знак c не ограничиваем: в банке
# он положительный, но математике это безразлично, а разнообразия больше.

def get_type3(rng):
    for _ in range(60):
        q = rng.choice([1, 2, 3, 4, 5]) * rng.choice([1, -1])
        r1 = rng.choice([1, 2, 3, 4, 5])
        r2 = rng.choice([-6, -5, -4, -3, -2, -1])
        p = r1 + r2 + q
        c = -p * q - r1 * r2
        if c == 0:
            continue                    # выродится в (x-p)(x+q)^2 = 0
        if len({-q, r1, r2}) != 3:
            continue                    # корни должны быть различны
        break
    else:                               # до сюда практически не доходит
        q, r1, r2 = 4, 3, -5
        p, c = 2, 7

    quad = poly_latex([1, 2 * q, q * q])
    left = _bracket(p) + r'\left(' + quad + r'\right)'
    right = ('' if c == 1 else ('-' if c == -1 else str(c))) \
        + '(x ' + ('+ %d' % q if q > 0 else '- %d' % -q) + ')'
    roots = [-q, r1, r2]
    ans, ans_set = roots_answer(roots)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Второй множитель слева — полный квадрат:'),
        _disp(left + ' = ' + right + ',\\qquad (x '
              + ('+ %d' % q if q > 0 else '- %d' % -q) + ')^2 = ' + quad + '.'),
        _p('Перенесём всё влево и вынесем общий множитель '
           '\\(\\left(x ' + ('+ %d' % q if q > 0 else '- %d' % -q) + '\\right)\\) '
           '<i>(делить на него нельзя — потеряется корень)</i>:'),
        _disp('(x ' + ('+ %d' % q if q > 0 else '- %d' % -q)
              + ')\\Big[(x ' + ('- %d' % p if p >= 0 else '+ %d' % -p)
              + ')(x ' + ('+ %d' % q if q > 0 else '- %d' % -q)
              + ') - ' + ('%d' % c if c > 0 else '(%d)' % c) + '\\Big] = 0.'),
        _p('Раскроем скобки во втором множителе:'),
        _disp(poly_latex([1, q - p, -(p * q + c)]) + ' = 0.'),
        _p('Получаем совокупность:'),
        _disp(_cases(['x = %d' % -q, 'x = %d' % r1, 'x = %d' % r2]) + '.'),
        _p('<b>Ответ:</b> \\(' + roots_latex(roots) + '.\\)'),
    )
    return {
        'type': 3, 'title': '№20. Тип 3',
        'question_html': _p('Решите уравнение \\(' + left + ' = ' + right + '.\\)'),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'solution_html': sol, 'params': {'p': p, 'q': q, 'c': c, 'r1': r1, 'r2': r2},
    }


# --------------------------------------------------------------------------
# Тип 5. (x^2 - k^2)^2 + (x^2 + b x + c)^2 = 0 — сумма квадратов
# --------------------------------------------------------------------------
#
# Сумма квадратов равна нулю только тогда, когда оба слагаемых нули. Значит
# ответ — пересечение корней двух уравнений, и он всегда один: общий корень
# трёхчленов. Первый даёт ±k, второй раскладывается как (x - r)(x - t), где
# r — тот самый общий корень (+k или -k, это и есть зеркало).

def get_type5(rng):
    k = rng.choice([2, 3, 4, 5, 6, 7])
    r = k * rng.choice([1, -1])         # общий корень: +k или -k
    t = rng.choice([n for n in range(-8, 9) if n not in (0, k, -k)])

    quad = poly_latex([1, -(r + t), r * t])
    ans, ans_set = roots_answer([r])

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Сумма квадратов равна нулю только тогда, когда каждое слагаемое равно нулю:'),
        _disp('\\begin{cases} x^2 - %d = 0, \\\\ %s = 0. \\end{cases}' % (k * k, quad)),
        _p('Первое уравнение даёт \\(x = %d\\) или \\(x = %d\\), второе — '
           '\\(x = %d\\) или \\(x = %d\\).' % (k, -k, r, t)),
        _p('Общий корень один:'),
        _disp('x = %d.' % r),
        _p('<b>Ответ:</b> \\(%d.\\)' % r),
    )
    return {
        'type': 5, 'title': '№20. Тип 5',
        'question_html': _p('Решите уравнение \\(\\left(x^2 - %d\\right)^2 + '
                            '\\left(%s\\right)^2 = 0.\\)' % (k * k, quad)),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'solution_html': sol, 'params': {'k': k, 'r': r, 't': t},
    }


# --------------------------------------------------------------------------
# Тип 6. x^2 - p x + sqrt(q - x) = sqrt(q - x) + c — отбор корней по ОДЗ
# --------------------------------------------------------------------------
#
# Корни в обеих частях одинаковые и сокращаются, остаётся квадратное
# уравнение. Вся задача — в области определения: подкоренное выражение
# неотрицательно, и один из корней ей не удовлетворяет. Кто сократит корни и
# забудет про ОДЗ, получит лишний корень — за это и снимают балл.
#
# Зеркало: подкоренное выражение бывает и (x - q), тогда ОДЗ x >= q и
# отбрасывается меньший корень.

def get_type6(rng):
    upper = rng.choice([True, False])   # True: sqrt(q - x), ОДЗ x <= q
    keep = rng.choice([-6, -5, -4, -3, -2, -1]) if upper else rng.choice([4, 5, 6, 7, 8])
    drop = rng.choice([5, 6, 7, 8, 9]) if upper else rng.choice([-5, -4, -3, -2, -1])
    # q лежит строго между корнями — тогда один из них ОДЗ не проходит
    lo, hi = (keep, drop) if keep < drop else (drop, keep)
    q = rng.randint(lo, hi - 1) if hi - 1 >= lo else lo
    if upper and not (keep <= q < drop):
        q = keep if keep == drop - 1 else (keep + drop) // 2
    if not upper and not (drop < q <= keep):
        q = (keep + drop) // 2 + 1

    p = keep + drop
    c = -keep * drop
    # Печать подкоренного выражения: «x - -1» и «0 - x» — не математика,
    # а невычищенный минус. Собираем строку по знаку q.
    if upper:
        radicand = '-x' if q == 0 else '%d - x' % q
    elif q == 0:
        radicand = 'x'
    else:
        radicand = 'x - %d' % q if q > 0 else 'x + %d' % -q
    odz = ('x \\le %d' % q) if upper else ('x \\ge %d' % q)

    left = poly_latex([1, -p, 0])
    eq = left + ' + \\sqrt{' + radicand + '} = \\sqrt{' + radicand + '} + ' + str(c)
    if c < 0:
        eq = left + ' + \\sqrt{' + radicand + '} = \\sqrt{' + radicand + '} - ' + str(-c)

    ans, ans_set = roots_answer([keep])
    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Область определения: подкоренное выражение неотрицательно, '
           '\\(%s \\ge 0\\), то есть \\(%s\\).' % (radicand, odz)),
        _p('Одинаковые корни в обеих частях сокращаются:'),
        _disp(poly_latex([1, -p, -c]) + ' = 0,'),
        _disp(_cases(['x = %d' % keep, 'x = %d' % drop]) + '.'),
        _p('Проверяем по области определения: \\(x = %d\\) не подходит, '
           'остаётся \\(x = %d\\).' % (drop, keep)),
        _p('<b>Ответ:</b> \\(%d.\\)' % keep),
    )
    return {
        'type': 6, 'title': '№20. Тип 6',
        'question_html': _p('Решите уравнение \\(' + eq + '.\\)'),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'solution_html': sol,
        'params': {'p': p, 'c': c, 'q': q, 'keep': keep, 'drop': drop, 'upper': upper},
    }


# --------------------------------------------------------------------------
# Тип 13. Значение выражения по условию-пропорции
# --------------------------------------------------------------------------
#
# Дано (a - p b + q)/(p a - b + q) = r, спрашивают значение A a + B b + C.
# Раскрываем пропорцию:
#
#     a - p b + q = r(p a - b + q)
#     a(1 - r p) + b(r - p) + q(1 - r) = 0
#     (r p - 1) a + (p - r) b = q(1 - r)
#
# Видно, что спрашиваемая комбинация — ровно та, что выпадает из пропорции:
# A = r p - 1, B = p - r. Свободный член подбираем так, чтобы ответ был
# круглым числом в разумных пределах.

def get_type13(rng):
    p = rng.randint(2, 9)
    r = rng.randint(2, 9)
    while r == p:                       # иначе слагаемое с b исчезнет
        r = rng.randint(2, 9)
    q = rng.randint(1, 9)

    A = r * p - 1
    B = p - r
    K = q * (1 - r)                     # значение A a + B b
    answer = rng.randint(-20, 50)
    C = answer - K

    expr = poly_latex([A, B, C], var='a').replace('a^{2}', 'a^2')
    # poly_latex работает с одной буквой; собираем выражение вручную
    expr = ('%da' % A if A != 1 else 'a')
    expr += (' + %db' % B) if B > 0 else (' - %db' % -B)
    if B in (1, -1):
        expr = ('%da' % A if A != 1 else 'a') + (' + b' if B == 1 else ' - b')
    expr += (' + %d' % C) if C >= 0 else (' - %d' % -C)

    frac = '\\dfrac{a - %db + %d}{%da - b + %d}' % (p, q, p, q)
    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Умножим обе части равенства на знаменатель:'),
        _disp('a - %db + %d = %d\\left(%da - b + %d\\right).' % (p, q, r, p, q)),
        _p('Раскроем скобки и соберём подобные:'),
        _disp('a(1 - %d) + b(%d - %d) + %d(1 - %d) = 0,' % (r * p, r, p, q, r)),
        _disp('%da %s %db = %d.' % (A, '+' if B > 0 else '-', abs(B), K)),
        _p('Осталось подставить это в искомое выражение:'),
        _disp('%s = %d %s %d = %d.' % (expr, K, '+' if C >= 0 else '-', abs(C), answer)),
        _p('<b>Ответ:</b> \\(%d.\\)' % answer),
    )
    return {
        'type': 13, 'title': '№20. Тип 13',
        'question_html': _p('Найдите значение выражения \\(%s\\), если '
                            '\\(%s = %d.\\)' % (expr, frac, r)),
        'answer': str(answer), 'answer_set': [Fraction(answer)], 'answer_kind': 'number',
        'solution_html': sol,
        'params': {'p': p, 'r': r, 'q': q, 'A': A, 'B': B, 'C': C},
    }


# --------------------------------------------------------------------------
# Системы уравнений. Ответ — пары (x; y), вид ответа объявляем явно.
# --------------------------------------------------------------------------

def _pairs_answer(pairs):
    """[(x, y), ...] → ('(2; 4), (2; -4)', список пар Fraction)."""
    uniq = sorted({(Fraction(x), Fraction(y)) for x, y in pairs})
    text = ', '.join('(%s; %s)' % (num_plain(x), num_plain(y)) for x, y in uniq)
    return text, [list(p) for p in uniq]


def _pairs_latex(pairs):
    uniq = sorted({(Fraction(x), Fraction(y)) for x, y in pairs})
    return ';\\ '.join('(%s;\\ %s)' % (num_latex(x), num_latex(y)) for x, y in uniq)


def _system(line1, line2):
    return '\\begin{cases} %s, \\\\ %s. \\end{cases}' % (line1, line2)


# --------------------------------------------------------------------------
# Тип 10. { a x^2 + y = p ;  b x^2 - y = q } — сложение уравнений
# --------------------------------------------------------------------------
#
# Складываем: y уничтожается, остаётся (a + b) x^2 = p + q. Чтобы корни были
# целыми, правая часть обязана делиться на (a + b) и давать точный квадрат.
# Генерируем от ответа: берём k и y0, кладём p = a k² + y0, q = b k² - y0 —
# тогда сумма равна (a + b) k² по построению.

def get_type10(rng):
    a = rng.choice([1, 2, 3, 5])
    b = rng.choice([1, 2, 3, 6])
    k = rng.choice([1, 2, 3])
    y0 = rng.randint(-9, 9)
    p = a * k * k + y0
    q = b * k * k - y0

    line1 = '%sx^2 + y = %d' % ('' if a == 1 else a, p)
    line2 = '%sx^2 - y = %d' % ('' if b == 1 else b, q)
    pairs = [(-k, y0), (k, y0)]
    ans, ans_set = _pairs_answer(pairs)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Сложим уравнения — переменная \\(y\\) уничтожается:'),
        _disp('%dx^2 = %d,\\qquad x^2 = %d.' % (a + b, p + q, k * k)),
        _disp(_cases(['x = %d' % k, 'x = %d' % (-k)]) + '.'),
        _p('Подставим каждое значение в первое уравнение:'),
        _disp('y = %d - %s\\cdot %d = %d.' % (p, a, k * k, y0)),
        _p('<b>Ответ:</b> \\(%s.\\)' % _pairs_latex(pairs)),
    )
    return {
        'type': 10, 'title': '№20. Тип 10',
        'question_html': _p('Решите систему уравнений \\(%s\\)' % _system(line1, line2)),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'pairs',
        'solution_html': sol, 'params': {'a': a, 'b': b, 'k': k, 'y0': y0, 'p': p, 'q': q},
    }


# --------------------------------------------------------------------------
# Тип 11. { a x^2 - b x = y ;  m(a x - b) = y } — нельзя делить на скобку
# --------------------------------------------------------------------------
#
# Приравниваем правые части: x(a x - b) = m(a x - b). Соблазн сократить на
# (a x - b) и потерять корень; правильно — перенести и вынести:
# (a x - b)(x - m) = 0. Второй корень x = b/a бывает дробным — так и в банке,
# и это часть задачи, поэтому запрет дробей для такой задачи снимаем.

def get_type11(rng):
    a = rng.choice([2, 3, 4, 5, 7])
    b = rng.choice([3, 5, 6, 9, 10, 11, 15])
    m = rng.choice([1, 2, 3])
    while Fraction(b, a) == m:          # иначе корни совпадут
        b = rng.choice([3, 5, 6, 9, 10, 11, 15])

    x1 = Fraction(m)
    x2 = Fraction(b, a)
    y1 = m * (a * m - b)
    y2 = 0

    line1 = '%s - %sx = y' % (poly_latex([a, 0, 0])[:-3] + 'x^2' if False else
                              ('%sx^2' % ('' if a == 1 else a)), b)
    line1 = '%sx^2 - %dx = y' % ('' if a == 1 else a, b)
    line2 = '%dx - %d = y' % (m * a, m * b)

    pairs = [(x1, y1), (x2, y2)]
    ans, ans_set = _pairs_answer(pairs)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Приравняем правые части и вынесем общий множитель '
           '<i>(сокращать на скобку нельзя — потеряется корень)</i>:'),
        _disp('x(%dx - %d) = %d(%dx - %d),' % (a, b, m, a, b)),
        _disp('(%dx - %d)(x - %d) = 0.' % (a, b, m)),
        _disp(_cases(['x = %s' % num_latex(x2), 'x = %d' % m]) + '.'),
        _p('Для каждого \\(x\\) находим \\(y\\) из второго уравнения:'),
        _disp('y = %d\\left(%dx - %d\\right).' % (m, a, b)),
        _p('<b>Ответ:</b> \\(%s.\\)' % _pairs_latex(pairs)),
    )
    return {
        'type': 11, 'title': '№20. Тип 11',
        'question_html': _p('Решите систему уравнений \\(%s\\)' % _system(line1, line2)),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'pairs',
        'allow_fractions': True,
        'solution_html': sol, 'params': {'a': a, 'b': b, 'm': m},
    }


# --------------------------------------------------------------------------
# Тип 12. { a x^2 + b y^2 = c ;  k a x^2 + k b y^2 = c x } — пропорция левых частей
# --------------------------------------------------------------------------
#
# Левая часть второго уравнения ровно в k раз больше левой части первого,
# значит k·c = c·x, откуда x = k без всяких вычислений (c ≠ 0). Дальше y
# находится из первого уравнения. Собираем от ответа: c = a k² + b m².

def get_type12(rng):
    a = rng.choice([2, 3, 5])
    b = rng.choice([1, 2, 4, 6])
    k = rng.choice([2, 3, 4])
    m = rng.choice([1, 2, 3, 4, 5])
    c = a * k * k + b * m * m

    line1 = '%sx^2 + %sy^2 = %d' % ('' if a == 1 else a, '' if b == 1 else b, c)
    line2 = '%sx^2 + %sy^2 = %dx' % (k * a, '' if k * b == 1 else k * b, c)

    pairs = [(k, -m), (k, m)]
    ans, ans_set = _pairs_answer(pairs)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Левая часть второго уравнения в %d раза больше левой части первого:' % k),
        _disp('%d\\left(%sx^2 + %sy^2\\right) = %dx,\\qquad %d\\cdot %d = %dx,'
              % (k, '' if a == 1 else a, '' if b == 1 else b, c, k, c, c)),
        _disp('x = %d.' % k),
        _p('Подставим в первое уравнение:'),
        _disp('%s\\cdot %d + %sy^2 = %d,\\qquad y^2 = %d,'
              % ('' if a == 1 else a, k * k, '' if b == 1 else b, c, m * m)),
        _disp(_cases(['y = %d' % m, 'y = %d' % (-m)]) + '.'),
        _p('<b>Ответ:</b> \\(%s.\\)' % _pairs_latex(pairs)),
    )
    return {
        'type': 12, 'title': '№20. Тип 12',
        'question_html': _p('Решите систему уравнений \\(%s\\)' % _system(line1, line2)),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'pairs',
        'solution_html': sol, 'params': {'a': a, 'b': b, 'k': k, 'm': m, 'c': c},
    }


# --------------------------------------------------------------------------
# Неравенства. Ответ считает solve_sign_inequality — генератор только
# объявляет разложение на множители и знак.
# --------------------------------------------------------------------------

def _ineq_task(num, title, question, pieces, solution_blocks, params):
    ans = interval_answer(pieces)
    return {
        'type': num, 'title': title,
        'question_html': _p(question),
        'answer': ans, 'answer_set': pieces, 'answer_kind': 'interval',
        'solution_html': _sol(*solution_blocks),
        'params': params,
    }


def _sign_word(op):
    return {'<': '<', '<=': '\\le', '>': '>', '>=': '\\ge'}[op]


def _bracket(a):
    """(x - a) с правильным знаком."""
    if a == 0:
        return 'x'
    return '(x - %d)' % a if a > 0 else '(x + %d)' % -a


# --------------------------------------------------------------------------
# Тип 14. sqrt((x-a)^2) < b(x-a) — корень из квадрата это модуль
# --------------------------------------------------------------------------
#
# sqrt(t^2) = |t|, поэтому неравенство превращается в |t| < b t. При t <= 0
# левая часть неотрицательна, правая неположительна — решений нет. При t > 0
# получается t < b t, что при b > 1 верно всегда. Значит ответ — луч t > 0.
# Разворот знака неравенства зеркалит ответ во второй луч.

def get_type14(rng):
    a = rng.randint(2, 9) * rng.choice([1, -1])
    b = rng.randint(2, 12)
    less = rng.choice([True, False])
    op = '<' if less else '>'

    pieces = [(float(a), False, INTERVAL_INF, False)] if less \
        else [(-INTERVAL_INF, False, float(a), False)]

    t = _bracket(a)
    question = ('Решите неравенство \\(\\sqrt{%s^2} %s %d%s.\\)'
                % (t, _sign_word(op), b, t))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Обозначим \\(t = %s\\). Корень из квадрата — это модуль: '
           '\\(\\sqrt{t^2} = |t|\\), поэтому неравенство принимает вид' % t),
        _disp('|t| %s %dt.' % (_sign_word(op), b)),
        _p('При \\(t \\le 0\\) левая часть неотрицательна, а правая неположительна.'),
        _p('При \\(t > 0\\) неравенство сводится к \\(t(%d - 1) > 0\\), '
           'что верно всегда.' % b),
        _p('Значит, %s, то есть \\(%s\\).'
           % ('\\(t > 0\\)' if less else '\\(t < 0\\)',
              'x > %d' % a if less else 'x < %d' % a)),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(14, '№20. Тип 14', question, pieces, blocks,
                      {'a': a, 'b': b, 'op': op})


# --------------------------------------------------------------------------
# Тип 15. -c / ((x-a)^2 - d) >= 0 — знак задаёт знаменатель
# --------------------------------------------------------------------------
#
# Числитель отрицателен и не равен нулю, значит дробь неотрицательна только
# там, где знаменатель отрицателен: (x-a)^2 < d. Отсюда |x - a| < sqrt(d).
# Если d — точный квадрат, концы целые; если нет, в ответе появляется корень,
# и записать его теперь есть чем.

def get_type15(rng):
    a = rng.randint(-6, 6)
    квадрат = rng.choice([True, False])
    d = rng.choice([4, 9, 16, 25]) if квадрат else rng.choice([2, 3, 5, 6, 7, 10])
    c = rng.randint(7, 20)
    внутрь = rng.choice([True, False])          # >= 0 или <= 0

    import math as _math
    корень = _math.sqrt(d)
    if квадрат:
        lo_txt, hi_txt = str(a - int(корень)), str(a + int(корень))
        lo_tex, hi_tex = lo_txt, hi_txt
    else:
        lo_txt = ('%d-\\sqrt{%d}' % (a, d)) if a else ('-\\sqrt{%d}' % d)
        hi_txt = ('%d+\\sqrt{%d}' % (a, d)) if a else ('\\sqrt{%d}' % d)
        lo_tex, hi_tex = lo_txt, hi_txt

    сдвиг = '' if a == 0 else ('- %d' % a if a > 0 else '+ %d' % -a)
    модуль = 'x' if a == 0 else 'x %s' % сдвиг
    if внутрь:
        ans = '(%s; %s)' % (lo_txt, hi_txt)
        tex = '\\left(%s;\\ %s\\right)' % (lo_tex, hi_tex)
        знак, вывод = '\\ge', 'знаменатель отрицателен'
        неравенство = '%s^2 < %d' % (('x' if a == 0 else '(%s)' % модуль), d)
    else:
        ans = '(-∞; %s) + (%s; +∞)' % (lo_txt, hi_txt)
        tex = ('\\left(-\\infty;\\ %s\\right) \\cup \\left(%s;\\ +\\infty\\right)'
               % (lo_tex, hi_tex))
        знак, вывод = '\\le', 'знаменатель положителен'
        неравенство = '%s^2 > %d' % (('x' if a == 0 else '(%s)' % модуль), d)

    основание = 'x^2' if a == 0 else \
        '(x - %d)^2' % a if a > 0 else '(x + %d)^2' % -a
    question = ('Решите неравенство \\(\\dfrac{-%d}{%s - %d} %s 0.\\)'
                % (c, основание, d, знак))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Числитель \\(-%d\\) отрицателен при любом \\(x\\), поэтому дробь '
           'удовлетворяет неравенству ровно там, где %s:' % (c, вывод)),
        _disp(неравенство + ','),
        _p('Извлекаем корень:'),
        _disp('\\left|%s\\right| %s \\sqrt{%d}.'
              % (модуль, '<' if внутрь else '>', d)),
        _p('<b>Ответ:</b> \\(%s.\\)' % tex),
    ]
    return {
        'type': 15, 'title': '№20. Тип 15',
        'question_html': _p(question),
        'answer': ans, 'answer_set': None, 'answer_kind': 'interval',
        'solution_html': _sol(*blocks),
        'params': {'a': a, 'd': d, 'c': c, 'внутрь': внутрь, 'квадрат': квадрат},
    }


# --------------------------------------------------------------------------
# Тип 17. x^2/(x-a) <= x — переносим и сокращаем
# --------------------------------------------------------------------------
#
# x^2/(x-a) - x = (x^2 - x(x-a))/(x-a) = a x/(x-a). Дальше обычный метод
# интервалов. Знак a не ограничиваем: при a < 0 ответ зеркалится и вместо
# отрезка получаются два куска — задача та же, а разбор интереснее.

def get_type17(rng):
    a = rng.choice([2, 3, 5, 6, 7]) * rng.choice([1, -1])
    op = rng.choice(['<=', '>='])
    factors = [(0, 1, 'num'), (a, 1, 'den')]
    const = 1 if a > 0 else -1
    pieces = solve_sign_inequality(factors, op, const)

    question = ('Решите неравенство \\(\\dfrac{x^2}{x %s} %s x.\\)'
                % (('- %d' % a if a > 0 else '+ %d' % -a), _sign_word(op)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Перенесём всё в левую часть и приведём к общему знаменателю:'),
        _disp('\\dfrac{x^2 - x(x %s)}{x %s} = \\dfrac{%sx}{x %s} %s 0.'
              % (('- %d' % a if a > 0 else '+ %d' % -a),
                 ('- %d' % a if a > 0 else '+ %d' % -a),
                 a, ('- %d' % a if a > 0 else '+ %d' % -a), _sign_word(op))),
        _p('Отмечаем на прямой нуль числителя \\(x = 0\\) и выколотую точку '
           '\\(x = %d\\) и расставляем знаки.' % a),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(17, '№20. Тип 17', question, pieces, blocks,
                      {'a': a, 'op': op})


# --------------------------------------------------------------------------
# Тип 18. 1/x >= 1/(x-a)
# --------------------------------------------------------------------------
#
# 1/x - 1/(x-a) = -a / (x(x-a)). Числитель — постоянная, знак решают только
# два выколотых корня.

def get_type18(rng):
    a = rng.choice([2, 3, 5, 6, 7]) * rng.choice([1, -1])
    op = rng.choice(['<=', '>='])
    factors = [(0, 1, 'den'), (a, 1, 'den')]
    const = -1 if a > 0 else 1
    pieces = solve_sign_inequality(factors, op, const)

    question = ('Решите неравенство \\(\\dfrac{1}{x} %s \\dfrac{1}{x %s}.\\)'
                % (_sign_word(op), ('- %d' % a if a > 0 else '+ %d' % -a)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Перенесём вправо влево и приведём к общему знаменателю:'),
        _disp('\\dfrac{(x %s) - x}{x(x %s)} = \\dfrac{%d}{x(x %s)} %s 0.'
              % (('- %d' % a if a > 0 else '+ %d' % -a),
                 ('- %d' % a if a > 0 else '+ %d' % -a),
                 -a, ('- %d' % a if a > 0 else '+ %d' % -a), _sign_word(op))),
        _p('Числитель постоянен, значит знак дроби задаёт только знаменатель. '
           'Обе точки \\(x = 0\\) и \\(x = %d\\) выколоты.' % a),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(18, '№20. Тип 18', question, pieces, blocks,
                      {'a': a, 'op': op})


# --------------------------------------------------------------------------
# Тип 19. (x^2 - (p+q)x + pq)/(x - p) <= 0 — сокращение с выколотой точкой
# --------------------------------------------------------------------------
#
# Числитель раскладывается как (x - p)(x - q), скобка сокращается — но точка
# x = p всё равно выкалывается: в исходном выражении там ноль в знаменателе.
# Ради этой выколотой точки тип и существует.

def get_type19(rng):
    p = rng.randint(-6, 6)
    q = rng.randint(-6, 6)
    while q == p:
        q = rng.randint(-6, 6)
    op = rng.choice(['<=', '>='])
    factors = [(p, 1, 'num'), (q, 1, 'num'), (p, 1, 'den')]
    pieces = solve_sign_inequality(factors, op, 1)

    num = poly_latex([1, -(p + q), p * q])
    знам = 'x' if p == 0 else ('x - %d' % p if p > 0 else 'x + %d' % -p)
    question = ('Решите неравенство \\(\\dfrac{%s}{%s} %s 0.\\)'
                % (num, знам, _sign_word(op)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Разложим числитель на множители:'),
        _disp('\\dfrac{%s%s}{%s} %s 0.'
              % (_bracket(p), _bracket(q), знам, _sign_word(op))),
        _p('Скобка \\(%s\\) сокращается, но точка \\(x = %d\\) остаётся '
           '<b>выколотой</b>: в исходном выражении там ноль в знаменателе.'
           % (_bracket(p), p)),
        _disp('%s %s 0,\\qquad x \\ne %d.' % (_bracket(q), _sign_word(op), p)),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(19, '№20. Тип 19', question, pieces, blocks,
                      {'p': p, 'q': q, 'op': op})


# --------------------------------------------------------------------------
# Тип 20. a(x-r)^2/(x+s) <= 0 — полный квадрат в числителе
# --------------------------------------------------------------------------
#
# Числитель неотрицателен всегда, поэтому неравенство выполняется либо там,
# где знаменатель нужного знака, либо в единственной точке x = r, где
# числитель обращается в ноль. Отсюда ответ «промежуток плюс точка».

def get_type20(rng):
    a = rng.choice([2, 3])
    r = rng.randint(2, 8)
    s = rng.randint(2, 8) * rng.choice([1, -1])
    op = rng.choice(['<=', '>='])
    factors = [(r, 2, 'num'), (-s, 1, 'den')]
    pieces = solve_sign_inequality(factors, op, 1)

    num = poly_latex([a, -2 * a * r, a * r * r])
    question = ('Решите неравенство \\(\\dfrac{%s}{x %s} %s 0.\\)'
                % (num, ('+ %d' % s if s > 0 else '- %d' % -s), _sign_word(op)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('В числителе — полный квадрат:'),
        _disp('\\dfrac{%d%s^2}{x %s} %s 0.'
              % (a, _bracket(r), ('+ %d' % s if s > 0 else '- %d' % -s),
                 _sign_word(op))),
        _p('Числитель неотрицателен при любом \\(x\\), поэтому неравенство '
           'выполняется там, где знаменатель нужного знака, и отдельно '
           'в точке \\(x = %d\\), где числитель равен нулю.' % r),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(20, '№20. Тип 20', question, pieces, blocks,
                      {'a': a, 'r': r, 's': s, 'op': op})


# --------------------------------------------------------------------------
# Типы 21 и 22. Произведение с кратным корнем
# --------------------------------------------------------------------------
#
# (k - x)(x^2 - k^2) = -(x - k)^2 (x + k): корень k получается кратности два и
# знака не меняет, поэтому в ответе он оказывается изолированной точкой.
# Тип 22 — та же конструкция, но кратный корень спрятан в трёхчлен.

def get_type21(rng):
    k = rng.randint(2, 9)
    op = rng.choice(['>=', '<='])
    factors = [(k, 2, 'num'), (-k, 1, 'num')]
    pieces = solve_sign_inequality(factors, op, -1)

    question = ('Решите неравенство \\((%d - x)\\left(x^2 - %d\\right) %s 0.\\)'
                % (k, k * k, _sign_word(op)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Разложим на множители и вынесем знак:'),
        _disp('(%d - x)(x - %d)(x + %d) = -%s^2(x + %d) %s 0.'
              % (k, k, k, _bracket(k), k, _sign_word(op))),
        _p('Квадрат знака не меняет, поэтому решает только скобка '
           '\\((x + %d)\\); сама точка \\(x = %d\\) обращает произведение '
           'в ноль и потому входит в ответ отдельно.' % (k, k)),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(21, '№20. Тип 21', question, pieces, blocks,
                      {'k': k, 'op': op})


def get_type22(rng):
    m = rng.randint(2, 7)
    n = rng.randint(2, 8)
    while n == m:
        n = rng.randint(2, 8)
    op = rng.choice(['>=', '<='])
    factors = [(m, 2, 'num'), (-n, 1, 'num')]
    pieces = solve_sign_inequality(factors, op, -1)

    quad = poly_latex([1, n - m, -m * n])
    question = ('Решите неравенство \\((%d - x)\\left(%s\\right) %s 0.\\)'
                % (m, quad, _sign_word(op)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Разложим трёхчлен: его корни \\(%d\\) и \\(%d\\).' % (m, -n)),
        _disp('(%d - x)%s%s = -%s^2%s %s 0.'
              % (m, _bracket(m), _bracket(-n), _bracket(m), _bracket(-n),
                 _sign_word(op))),
        _p('Корень \\(x = %d\\) оказался кратным: он не меняет знак '
           'произведения и входит в ответ отдельной точкой.' % m),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(22, '№20. Тип 22', question, pieces, blocks,
                      {'m': m, 'n': n, 'op': op})


# --------------------------------------------------------------------------
# Тип 23. (x^2 + x - p)(x^2 + x - q) <= 0 — замена t = x^2 + x
# --------------------------------------------------------------------------
#
# Чтобы оба трёхчлена раскладывались на целые множители, свободные члены
# обязаны иметь вид k(k+1): тогда корни равны k и -(k+1).

def get_type23(rng):
    k = rng.randint(2, 5)
    n = rng.randint(k + 1, 7)
    op = rng.choice(['<=', '>='])
    p, q = k * (k + 1), n * (n + 1)
    factors = [(k, 1, 'num'), (-(k + 1), 1, 'num'),
               (n, 1, 'num'), (-(n + 1), 1, 'num')]
    pieces = solve_sign_inequality(factors, op, 1)

    question = ('Решите неравенство \\(\\left(x^2 + x - %d\\right)'
                '\\left(x^2 + x - %d\\right) %s 0.\\)' % (p, q, _sign_word(op)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Разложим каждый трёхчлен на множители:'),
        _disp('%s%s\\cdot %s%s %s 0.'
              % (_bracket(k), _bracket(-(k + 1)), _bracket(n), _bracket(-(n + 1)),
                 _sign_word(op))),
        _p('Четыре простых корня: \\(%d,\\ %d,\\ %d,\\ %d\\). '
           'Расставляем знаки методом интервалов.'
           % (-(n + 1), -(k + 1), k, n)),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(23, '№20. Тип 23', question, pieces, blocks,
                      {'k': k, 'n': n, 'p': p, 'q': q, 'op': op})


# --------------------------------------------------------------------------
# Типы 24 и 25. Произведение трёхчленов с общим корнем
# --------------------------------------------------------------------------
#
# Общий корень даёт кратность два: он не меняет знак, и в ответе становится
# либо изолированной точкой, либо выпадающей точкой внутри промежутка.

def _common_root_product(rng, num, op_choices):
    общий = rng.randint(-5, 5)
    a = rng.randint(-6, 6)
    b = rng.randint(-6, 6)
    while a == общий or b == общий or a == b:
        a = rng.randint(-6, 6)
        b = rng.randint(-6, 6)
    op = rng.choice(op_choices)

    factors = [(общий, 2, 'num'), (a, 1, 'num'), (b, 1, 'num')]
    pieces = solve_sign_inequality(factors, op, 1)

    q1 = poly_latex([1, -(общий + a), общий * a])
    q2 = poly_latex([1, -(общий + b), общий * b])
    question = ('Решите неравенство \\(\\left(%s\\right)\\left(%s\\right) %s 0.\\)'
                % (q1, q2, _sign_word(op)))
    blocks = [
        _p('<b>Решение.</b>'),
        _p('Разложим оба трёхчлена — у них общий корень \\(x = %d\\):' % общий),
        _disp('%s%s\\cdot %s%s %s 0,'
              % (_bracket(общий), _bracket(a), _bracket(общий), _bracket(b),
                 _sign_word(op))),
        _disp('%s^2%s%s %s 0.'
              % (_bracket(общий), _bracket(a), _bracket(b), _sign_word(op))),
        _p('Общий корень получил кратность два и знака не меняет — '
           'он входит в ответ отдельно.'),
        _p('<b>Ответ:</b> \\(%s.\\)' % interval_latex(pieces)),
    ]
    return _ineq_task(num, '№20. Тип %d' % num, question, pieces, blocks,
                      {'общий': общий, 'a': a, 'b': b, 'op': op})


def get_type24(rng):
    return _common_root_product(rng, 24, ['<='])


def get_type25(rng):
    return _common_root_product(rng, 25, ['>='])


# --------------------------------------------------------------------------
# Тип 8. 1/(x-a)^2 + b/(x-a) + c = 0 — замена t = 1/(x-a)
# --------------------------------------------------------------------------
#
# Тот же приём, что в типе 7, только дробь сдвинута. Замена t = 1/(x-a)
# превращает уравнение в квадратное; обратный ход x = a + 1/t даёт, как
# правило, дробные корни — это нормальный ответ второй части, поэтому запрет
# обыкновенных дробей для такой задачи снимаем.

def get_type8(rng):
    a = rng.randint(1, 5) * rng.choice([1, -1])
    t1 = rng.choice([-6, -5, -4, -3, -2, -1, 2, 3, 4, 5, 6])
    t2 = rng.choice([t for t in (-6, -5, -4, -3, -2, -1, 2, 3, 4, 5, 6) if t != t1])
    b = -(t1 + t2)
    c = t1 * t2

    roots = [Fraction(a) + Fraction(1, t1), Fraction(a) + Fraction(1, t2)]
    ans, ans_set = roots_answer(roots)
    скобка = _bracket(a)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Замена \\(t = \\dfrac{1}{%s}\\) (при \\(x \\ne %d\\)) '
           'превращает уравнение в квадратное:' % (скобка, a)),
        _disp(poly_latex([1, b, c], var='t') + ' = 0,'),
        _disp(_cases(['t = %d' % t1, 't = %d' % t2]) + '.'),
        _p('Возвращаемся к \\(x\\): из \\(t = \\dfrac{1}{%s}\\) следует '
           '\\(x = %d + \\dfrac{1}{t}\\).' % (скобка, a)),
        _disp(_cases(['x = %s' % num_latex(roots[0]),
                      'x = %s' % num_latex(roots[1])]) + '.'),
        _p('<b>Ответ:</b> \\(%s.\\)' % roots_latex(roots)),
    )
    вопрос = ('Решите уравнение \\(\\dfrac{1}{%s^2} %s \\dfrac{%s}{%s} %s %d = 0.\\)'
              % (скобка, '+' if b > 0 else '-', abs(b) if abs(b) != 1 else '1',
                 скобка, '+' if c > 0 else '-', abs(c)))
    return {
        'type': 8, 'title': '№20. Тип 8',
        'question_html': _p(вопрос),
        'answer': ans, 'answer_set': ans_set, 'answer_kind': 'roots',
        'allow_fractions': True,
        'solution_html': sol, 'params': {'a': a, 'b': b, 'c': c, 't1': t1, 't2': t2},
    }


# --------------------------------------------------------------------------
# Тип 9. (x-a)^4 + b(x-a)^2 + c = 0 — замена t = (x-a)^2
# --------------------------------------------------------------------------
#
# Замена даёт квадратное уравнение относительно t, но t = (x-a)^2 не может
# быть отрицательным — один корень отбрасывается. Это и есть содержание
# задачи: кто забудет про t >= 0, получит лишние корни.
#
# Уцелевший корень бывает точным квадратом (тогда ответ целый) и не бывает
# (тогда в ответе появляется корень) — берём и то и другое.

def get_type9(rng):
    a = rng.randint(1, 6) * rng.choice([1, -1])
    точный = rng.choice([True, False])
    t1 = rng.choice([1, 4, 9, 16]) if точный else rng.choice([2, 3, 5, 6, 7, 10])
    t2 = -rng.choice([1, 2, 3, 4, 5, 6])          # отрицательный корень отбрасывается
    b = -(t1 + t2)
    c = t1 * t2

    скобка = _bracket(a)
    if точный:
        k = int(round(t1 ** 0.5))
        корни_текст = '%d; %d' % (a - k, a + k)
        корни_tex = '%d;\\ %d' % (a - k, a + k)
    else:
        корни_текст = '%d-\\sqrt{%d}; %d+\\sqrt{%d}' % (a, t1, a, t1)
        корни_tex = '%d - \\sqrt{%d};\\ %d + \\sqrt{%d}' % (a, t1, a, t1)

    sol = _sol(
        _p('<b>Решение.</b>'),
        _p('Замена \\(t = %s^2\\), причём \\(t \\ge 0\\):' % скобка),
        _disp(poly_latex([1, b, c], var='t') + ' = 0,'),
        _disp(_cases(['t = %d' % t1, 't = %d' % t2]) + '.'),
        _p('Корень \\(t = %d\\) отрицателен и не подходит: квадрат '
           'неотрицателен. Остаётся' % t2),
        _disp('%s^2 = %d,\\qquad x = %d \\pm \\sqrt{%d}.' % (скобка, t1, a, t1)),
        _p('<b>Ответ:</b> \\(%s.\\)' % корни_tex),
    )
    вопрос = ('Решите уравнение \\(%s^4 %s %s%s^2 %s %d = 0.\\)'
              % (скобка, '+' if b > 0 else '-',
                 '' if abs(b) == 1 else abs(b), скобка,
                 '+' if c > 0 else '-', abs(c)))
    return {
        'type': 9, 'title': '№20. Тип 9',
        'question_html': _p(вопрос),
        'answer': корни_текст, 'answer_set': None, 'answer_kind': 'roots',
        'solution_html': sol,
        'params': {'a': a, 'b': b, 'c': c, 't1': t1, 't2': t2, 'точный': точный},
    }


GENERATORS = {
    1: get_type1,
    2: get_type2,
    3: get_type3,
    4: get_type4,
    5: get_type5,
    6: get_type6,
    7: get_type7,
    8: get_type8,
    9: get_type9,
    10: get_type10,
    11: get_type11,
    12: get_type12,
    13: get_type13,
    14: get_type14,
    15: get_type15,
    16: get_type16,
    17: get_type17,
    18: get_type18,
    19: get_type19,
    20: get_type20,
    21: get_type21,
    22: get_type22,
    23: get_type23,
    24: get_type24,
    25: get_type25,
}


def generate(type_num, seed=None):
    rng = random.Random(seed)
    return GENERATORS[type_num](rng)


# --------------------------------------------------------------------------
# Мост к платформе
# --------------------------------------------------------------------------
#
# Сайт ждёт от генератора словарь со своими именами полей: condition_text,
# correct_answer и несколько флагов, по которым страница решает, что показать
# ученику. Наши генераторы говорят на своём языке (question_html, answer,
# answer_kind) — здесь перевод, один на все двадцать пять типов.

def as_task(type_num, seed=None):
    """Задача типа type_num в том виде, в каком её ждёт платформа."""
    task = generate(type_num, seed)
    kind = task.get('answer_kind', 'number')
    return {
        'condition_text': task['question_html'],
        'correct_answer': task['answer'],
        'answer_kind': kind,
        # «+ корень» нужен там, где ответов несколько и каждый — отдельное
        # число. У промежутка и у пары ответ один и вводится строкой.
        'multi_answer': kind == 'roots' and ';' in task['answer'],
        'allow_fractions': bool(task.get('allow_fractions')),
        'solution_html': task.get('solution_html', ''),
        'oge20_type': type_num,
    }


# --------------------------------------------------------------------------
# Самотест: численная проверка корректности ответов
# --------------------------------------------------------------------------

def _selftest():
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    def check_roots_eq(f, roots, tol=1e-6):
        """f(x)=0 в каждом корне; и нет 'лишних' рядом — базовая проверка подстановкой."""
        return all(abs(f(float(r))) < tol for r in roots)

    ok = True

    # Тип 1: x^3 + b x^2 - c x - bc
    for s in range(200):
        d = generate(1, s)
        b, k, c = d['params']['b'], d['params']['k'], d['params']['c']
        f = lambda x: x**3 + b*x**2 - c*x - b*c
        if not check_roots_eq(f, [float(r) for r in d['answer_set']]):
            ok = False; print('FAIL type1', s, d['answer']); break
    else:
        print('type1: OK (200 сидов, подстановка корней)')

    # Тип 4: x^4 = (a x - b)^2
    for s in range(300):
        d = generate(4, s)
        a, b = d['params']['a'], d['params']['b']
        f = lambda x: x**4 - (a*x - b)**2
        roots = [float(r) for r in d['answer_set']]
        if not check_roots_eq(f, roots):
            ok = False; print('FAIL type4', s, d['answer'], a, b); break
        # проверим, что не пропустили целых корней
        found = set(roots)
        miss = [xx for xx in range(-15, 16) if abs(f(xx)) < 1e-9 and xx not in found]
        if miss:
            ok = False; print('MISS type4', s, 'пропущены', miss, d['answer']); break
    else:
        print('type4: OK (300 сидов, подстановка + полнота целых корней)')

    # Тип 7: 1/x^2 + b/x + c
    for s in range(300):
        d = generate(7, s)
        b, c = d['params']['b'], d['params']['c']
        f = lambda x: 1/x**2 + b/x + c
        if not check_roots_eq(f, [float(r) for r in d['answer_set']]):
            ok = False; print('FAIL type7', s, d['answer']); break
    else:
        print('type7: OK (300 сидов, подстановка)')

    # Тип 16: x <= a/x  -> проверим решение сэмплированием
    for s in range(200):
        d = generate(16, s)
        k = d['params']['k']; a = d['params']['a']
        def in_sol(x):
            return (x <= -k) or (0 < x <= k)
        def truth(x):
            if abs(x) < 1e-12: return None
            return x <= a / x
        bad = []
        xx = -3*k
        while xx <= 3*k:
            if abs(xx) > 1e-9:
                t = truth(xx); s_ = in_sol(xx)
                if t is not None and t != s_:
                    bad.append(round(xx, 3))
            xx += 0.25
        if bad:
            ok = False; print('FAIL type16', s, 'расхождения в', bad[:5], d['answer']); break
    else:
        print('type16: OK (200 сидов, сэмплирование решения)')

    print('\nИТОГ:', 'ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if ok else 'ЕСТЬ ОШИБКИ')
    # печать примеров
    print('\n--- Примеры (seed=0) ---')
    for t in (1, 4, 7, 16):
        d = generate(t, 0)
        import re
        q = re.sub('<[^>]+>', '', d['question_html'])
        print(f"[Тип {t}] {q}  ->  Ответ: {d['answer']}")


if __name__ == '__main__':
    _selftest()
