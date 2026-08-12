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
    ans = f'(-inf; -{k}] U (0; {k}]'
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

GENERATORS = {
    1: get_type1,
    4: get_type4,
    7: get_type7,
    16: get_type16,
}


def generate(type_num, seed=None):
    rng = random.Random(seed)
    return GENERATORS[type_num](rng)


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
