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


def _parse_sum(s):
    r"""
    Сумма слагаемых: «3-\sqrt{5}», «-2+\sqrt{3}», «\frac{1}{2}+1».

    Отдельный слой над _parse_expr понадобился, когда до курса дошли ответы
    вида a ± √b — корни уравнения (x−a)⁴+b(x−a)²+c=0 и концы промежутка в
    неравенстве −c/((x−a)²−d) ≥ 0. Раньше грамматика останавливалась на первом
    же плюсе, и такой ответ было физически нечем ввести.
    """
    total, pos = _parse_expr(s)
    while pos < len(s) and s[pos] in '+-':
        sign = 1 if s[pos] == '+' else -1
        pos += 1
        value, used = _parse_expr(s[pos:])
        if used == 0:
            raise AnswerError('висячий знак')
        total += sign * value
        pos += used
    return total, pos


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


# Корень ученик пишет одним знаком: «√5», «√(20)», «2√3». Так его вводит
# кнопка на странице, так же он выглядит в учебнике и так же его набирают на
# телефоне. Внутри всё сводится к \sqrt{...}, и дальше работает разбор LaTeX
# вместе с проверкой канонической формы: √8 по-прежнему попросит вынести
# множитель. Заставлять школьника писать \sqrt{} ради этого незачем.
_RX_SQRT_PAREN = re.compile(r'√\s*\(([^()]*)\)')
_RX_SQRT_PLAIN = re.compile(r'√\s*(\d+(?:[.,]\d+)?)')


def unify_roots(text):
    """«√5», «√(20)» → «\\sqrt{5}», «\\sqrt{20}». Прочее не трогает."""
    s = str(text or '')
    if '√' not in s:
        return s
    s = _RX_SQRT_PAREN.sub(lambda m: r'\sqrt{%s}' % m.group(1).strip(), s)
    s = _RX_SQRT_PLAIN.sub(lambda m: r'\sqrt{%s}' % m.group(1), s)
    return s


def _normalize(s):
    if s is None:
        raise AnswerError('пустой ответ')
    s = unify_roots(str(s).strip())
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
        val, used = _parse_sum(s_norm)
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

# ============================================================
#   Промежутки: ответы неравенств
# ============================================================
#
# Половина типов №20 ОГЭ — неравенства, и ответ у них не число и не набор
# корней, а множество: «x ∈ (−∞; −7] ∪ (0; 7]». Раньше такой ответ попадал
# в проверку набора корней, та резала строку по «;» и пыталась прочитать
# «(−∞» как число, — то есть правильный ответ засчитывался как неверный.
#
# Что здесь важно:
#
#   • скобки различаются. Круглая — конец не включён, квадратная — включён;
#     [0; 5) и (0; 5] это разные множества, и путать их нельзя;
#   • бесконечность пишут по-разному: ∞, inf, oo, +∞, −бесконечность. Рядом
#     с ней скобка всегда круглая по смыслу, поэтому квадратную у ∞ мы молча
#     считаем круглой, а не браковкой: на экзамене за это не снимают;
#   • объединение принимается и плюсом, и знаком ∪, и латинской U. Плюс —
#     основной: его видно на любой клавиатуре, и именно его показывают
#     ученику в подсказке;
#   • сравниваются множества, а не записи. [1; 2] + [2; 3] и [1; 3] — одно и
#     то же множество, и оба ответа верны. Поэтому промежутки перед сравнением
#     склеиваются;
#   • отдельная точка пишется как {4} или просто 4 — в ответах ФИПИ такие
#     куски встречаются постоянно (тип 20: (−∞; −6) ∪ {4}).

_INF_WORDS = ('бесконечность', 'infinity', 'infty', '\\infty', 'inf', 'oo', '∞')

# Опознаём промежуток по форме, а не по одной скобке. Фигурные скобки есть и
# у \frac{3}{4}, и у \sqrt{8}: такой ответ, уйдя в разбор множеств, читался бы
# как «точка 0.75» — сравнение по значению прошло бы, а проверка канонической
# формы (несократимая дробь, вынесенный множитель из-под корня) молча
# пропускалась бы, и \frac{2}{4} принималось вместо \frac{1}{2}.
_RX_INTERVAL_SHAPE = re.compile(r'[\[(][^;\[\]()]*;[^;\[\]()]*[\])]')
# (фигурные скобки внутри разрешены: \sqrt{5} — часть конца, а не вложенный
#  промежуток; круглые запрещены, чтобы «(1;2)+(3;4)» не слиплось в один кусок)
_RX_INFINITY = re.compile(r'∞|\binf\b|\binfty\b|\boo\b|бесконечн', re.I)
_RX_POINT_ONLY = re.compile(r'^\s*\{\s*[-+−–—]?[\d.,\s]+\}\s*$')


def looks_like_interval(text):
    """Похоже ли, что это ответ-множество, а не число и не набор корней."""
    s = unify_roots(str(text or ''))
    if _RX_INTERVAL_SHAPE.search(s):    # «(что-то; что-то]» — в том числе с √
        return True
    if '\\' in s:                       # одинокий \frac{3}{4} — это число
        return False
    if _RX_INFINITY.search(s):
        return True
    return bool(_RX_POINT_ONLY.match(s))  # одиночная точка «{4}»


def _endpoint(raw):
    """Конец промежутка: число или ±∞. Возвращает float."""
    s = str(raw).strip().replace(' ', '')
    if not s:
        raise AnswerError('пустой конец промежутка')

    # Знаки снимаем только чтобы опознать бесконечность. Само число разбирать
    # без знака нельзя: «-3-√2» — это не минус от «3-√2», а сумма двух
    # слагаемых, и вычитать её целиком означало бы -1,59 вместо -4,41.
    sign = 1.0
    голое = s
    # `голое[:1] in '+-−–—'` истинно и для пустой строки — пустая строка есть
    # подстрока любой; поэтому сравниваем символ, а не срез.
    while голое and голое[0] in '+-−–—':
        if голое[0] != '+':
            sign = -sign
        голое = голое[1:]
    if not голое:
        raise AnswerError('пустой конец промежутка')

    low = голое.lower()
    if low in _INF_WORDS or low.lstrip('\\') in _INF_WORDS:
        return sign * math.inf

    try:
        value, _kind, _extra = _parse_any(_normalize(s))   # со своим знаком
    except (ValueError, ArithmeticError) as exc:      # nan, 1e999 и прочий мусор
        raise AnswerError('не число') from exc
    if not math.isfinite(value):
        # Бесконечность к этому месту уже вернулась выше по словам из _INF_WORDS;
        # всё остальное бесконечное — это «1e999» или «nan», а не конец промежутка.
        raise AnswerError('не число')
    return value


def _split_top_level(text, seps):
    """Разбить строку по разделителям верхнего уровня (вне скобок)."""
    parts, buf, depth = [], [], 0
    for ch in text:
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if depth == 0 and ch in seps:
            parts.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append(''.join(buf))
    return [p.strip() for p in parts if p.strip()]


def _parse_piece(piece):
    """Один кусок объединения → (низ, низ_включён, верх, верх_включён)."""
    s = piece.strip()
    if not s:
        raise AnswerError('пустой промежуток')

    # Отдельная точка: {4} или просто 4
    if s[0] == '{' and s[-1] == '}':
        v = _endpoint(s[1:-1])
        if math.isinf(v):
            raise AnswerError('бесконечность не бывает точкой')
        return (v, True, v, True)
    if s[0] not in '([' or s[-1] not in ')]':
        v = _endpoint(s)
        if math.isinf(v):
            raise AnswerError('бесконечность не бывает точкой')
        return (v, True, v, True)

    lo_closed = s[0] == '['
    hi_closed = s[-1] == ']'
    inner = s[1:-1]

    ends = _split_top_level(inner, ';')
    if len(ends) != 2:
        # Запятая внутри — это десятичная запятая («0,5»), а не разделитель;
        # концы промежутка разделяются только точкой с запятой.
        raise AnswerError('концы промежутка разделяются точкой с запятой')

    lo = _endpoint(ends[0])
    hi = _endpoint(ends[1])
    if lo > hi:
        raise AnswerError('левый конец больше правого')
    if lo == hi and not (lo_closed and hi_closed):
        raise AnswerError('пустой промежуток')

    # У бесконечности скобка может быть только круглой — приводим молча.
    if math.isinf(lo):
        lo_closed = False
    if math.isinf(hi):
        hi_closed = False
    return (lo, lo_closed, hi, hi_closed)


def parse_interval_set(text):
    """
    Разобрать ответ-множество в список склеенных промежутков.

    Принимает «x ∈ (-inf; -7] + (0; 7]», «(−∞;−7]∪(0;7]», «[0;5)», «{4}», «4».
    Бросает AnswerError, если разобрать не удалось.
    """
    s = str(text or '').strip()
    if not s:
        raise AnswerError('пустой ответ')

    s = unify_roots(s)
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')
    s = re.sub(r'^\s*[xх]\s*(?:∈|in|\\in|принадлежит)\s*', '', s, flags=re.I)
    s = s.replace('\\cup', '+').replace('∪', '+').replace('⋃', '+')
    s = re.sub(r'\bu\b', '+', s, flags=re.I)      # и заглавная, и строчная
    s = re.sub(r'\bили\b', '+', s, flags=re.I)
    s = s.rstrip('.').strip()

    pieces = _split_top_level(s, '+')
    if not pieces:
        raise AnswerError('пустой ответ')

    parsed = [_parse_piece(p) for p in pieces]
    return _merge_intervals(parsed)


def _merge_intervals(items):
    """Склеить пересекающиеся и соприкасающиеся промежутки."""
    items = sorted(items, key=lambda it: (it[0], not it[1]))
    out = []
    for lo, lo_c, hi, hi_c in items:
        if not out:
            out.append([lo, lo_c, hi, hi_c])
            continue
        prev = out[-1]
        touches = lo < prev[2] or (lo == prev[2] and (prev[3] or lo_c))
        if touches:
            if hi > prev[2] or (hi == prev[2] and hi_c):
                prev[2], prev[3] = hi, hi_c
        else:
            out.append([lo, lo_c, hi, hi_c])
    return [tuple(x) for x in out]


def check_interval_answer(user_answer, correct_answer, tolerance=1e-9):
    """
    Сравнить два ответа-множества. Возвращает (верно, сообщение_или_None).

    Сравниваются именно множества: разбиение на куски и порядок не важны,
    а вот тип скобок важен — он и есть содержание ответа.
    """
    try:
        want = parse_interval_set(correct_answer)
    except AnswerError:
        return False, None                      # эталон не разобрался — не наша вина

    try:
        got = parse_interval_set(user_answer)
    except (AnswerError, ValueError, IndexError, ArithmeticError):
        return False, ('Ответ записывается промежутками, например: '
                       '(-∞; -7] + (0; 7]')

    if len(got) != len(want):
        return False, None
    for (a_lo, a_lc, a_hi, a_hc), (b_lo, b_lc, b_hi, b_hc) in zip(got, want):
        same_lo = (a_lo == b_lo) if (math.isinf(a_lo) or math.isinf(b_lo)) \
            else abs(a_lo - b_lo) <= tolerance
        same_hi = (a_hi == b_hi) if (math.isinf(a_hi) or math.isinf(b_hi)) \
            else abs(a_hi - b_hi) <= tolerance
        if not (same_lo and same_hi and a_lc == b_lc and a_hc == b_hc):
            return False, None
    return True, None


def format_interval_set(items):
    """Записать разобранное множество канонически — для подсказок и эталонов."""
    def end(v):
        if math.isinf(v):
            return '-∞' if v < 0 else '+∞'
        return ('%g' % v)

    chunks = []
    for lo, lo_c, hi, hi_c in items:
        if lo == hi:
            chunks.append('{%s}' % end(lo))
        else:
            chunks.append('%s%s; %s%s' % ('[' if lo_c else '(', end(lo),
                                          end(hi), ']' if hi_c else ')'))
    return ' + '.join(chunks)


# ============================================================
#   Пары: ответы систем уравнений
# ============================================================
#
# У системы ответ — не число и не множество, а набор пар «(x; y)». Отличить
# пару от промежутка по виду нельзя: «(2; 4)» читается и так и так. Поэтому
# вид ответа сюда приходит не догадкой, а явно — генератор объявляет его сам
# (answer_kind='pairs'), и вызывающий код передаёт kind в check_answer.
#
# Внутри пары порядок важен: (2; 4) и (4; 2) — разные ответы. Порядок самих
# пар не важен, как и у корней.

def parse_pairs(text):
    """«(2; 4), (2; -4)» → [(2, 4), (2, -4)], отсортировано."""
    s = unify_roots(str(text or '')).strip()
    if not s:
        raise AnswerError('пустой ответ')
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')
    s = s.rstrip('.').strip()

    chunks = [c for c in _split_top_level(s, ',\n') if c.strip()]
    if not chunks:
        raise AnswerError('пустой ответ')

    pairs = []
    for chunk in chunks:
        c = chunk.strip()
        if not (c.startswith('(') and c.endswith(')')):
            raise AnswerError('пара записывается в скобках: (x; y)')
        inner = _split_top_level(c[1:-1], ';')
        if len(inner) != 2:
            raise AnswerError('в паре два числа через точку с запятой')
        try:
            x, _k1, _e1 = _parse_any(_normalize(inner[0]))
            y, _k2, _e2 = _parse_any(_normalize(inner[1]))
        except (ValueError, ArithmeticError, IndexError) as exc:
            raise AnswerError('не число') from exc
        if not (math.isfinite(x) and math.isfinite(y)):
            raise AnswerError('не число')
        pairs.append((x, y))

    return sorted(pairs)


def check_pairs_answer(user_answer, correct_answer, tolerance=1e-9):
    """Сравнить наборы пар. Возвращает (верно, сообщение_или_None)."""
    try:
        want = parse_pairs(correct_answer)
    except AnswerError:
        return False, None

    try:
        got = parse_pairs(user_answer)
    except AnswerError:
        return False, 'Ответ системы записывается парами, например: (2; 4), (2; -4)'

    if len(got) != len(want):
        return False, None
    for (ax, ay), (bx, by) in zip(got, want):
        if abs(ax - bx) > tolerance or abs(ay - by) > tolerance:
            return False, None
    return True, None


def check_answer(user_answer, correct_answer,
                 tolerance=1e-6, allow_fractions=True, kind=None):
    """Возвращает (is_correct: bool, message: str | None).

    Численное сравнение с заданной точностью, плюс проверка канонической формы
    для дробей и корней.

    allow_fractions=False — отклоняет обыкновенные дроби (для ОГЭ, где
    допустимы только десятичные дроби в ответе).

    Мульти-ответ (вторая часть, несколько корней): если эталон содержит «;»,
    ответ ученика тоже разбивается по «;» и сравнивается как множество
    (порядок не важен, каждый корень должен встретиться ровно один раз).

    Ответ-множество (неравенства): если в эталоне есть скобки или ∞, ответ
    разбирается как объединение промежутков — см. check_interval_answer.
    """
    if user_answer is None:
        user_answer = ''

    # ── Вид ответа, объявленный генератором ────────────────────
    # Пару «(2; 4)» от промежутка «(2; 4)» по виду не отличить, поэтому там,
    # где вид известен заранее, он приходит сюда явно и догадки не нужны.
    if kind == 'pairs':
        return check_pairs_answer(user_answer, correct_answer)
    if kind == 'interval':
        return check_interval_answer(user_answer, correct_answer)

    # ── Ответ-множество: неравенства второй части ──────────────
    # Проверяется раньше набора корней: в промежутке тоже есть «;», и без
    # этой ветки «(-∞; -7] + (0; 7]» уходило бы в проверку корней и падало.
    if looks_like_interval(correct_answer):
        try:
            parse_interval_set(correct_answer)
        except AnswerError:
            pass        # эталон только похож на множество («бесконечно много
                        # решений») — пусть его смотрит обычная проверка
        else:
            return check_interval_answer(user_answer, correct_answer)

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
