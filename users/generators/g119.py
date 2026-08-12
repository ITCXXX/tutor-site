# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=119: OGE14: Тип 8+9 — геом., n-й член
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
from fractions import Fraction


def _decimal_str(f):
    if f.denominator == 1:
        return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num, den = abs(f.numerator), f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1:
        return sign + f"{num/den:.2f}".replace('.', ',')
    target = max(a, b)
    pad = num * (10 ** target) // den
    s = str(pad).rjust(target + 1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def _minute_word(n):
    if n % 100 in (11, 12, 13, 14): return "минут"
    last = n % 10
    if last == 1: return "минуту"
    if last in (2, 3, 4): return "минуты"
    return "минут"


def _times_word(n):
    """раз / раза в зависимости от числа."""
    if n % 100 in (11, 12, 13, 14): return "раз"
    last = n % 10
    if last in (2, 3, 4): return "раза"
    return "раз"


def _bacteria():
    """Растущая геом. прогрессия (q ∈ {2, 3}). Ответ — целое число."""
    q = random.choice([2, 3])
    n_steps = random.randint(3, 5)
    b1 = random.choice([2, 3, 4, 5, 6, 8, 10, 12])
    bN = b1 * q ** n_steps
    period = random.choice([10, 15, 20, 30])
    total_minutes = period * n_steps
    container = random.choice([
        ("чашку Петри с питательной средой", "колонию микроорганизмов", "колонии"),
        ("питательный раствор", "культуру бактерий", "культуры"),
        ("стерильный сосуд", "колонию бактерий", "колонии"),
    ])
    text = (
        rf"В ходе биологического эксперимента в {container[0]} поместили "
        rf"{container[1]} массой {b1} мг. За каждые {period} {_minute_word(period)} масса "
        rf"{container[2]} увеличивается в {q} {_times_word(q)}. Найдите массу "
        rf"{container[2]} через {total_minutes} {_minute_word(total_minutes)} после начала эксперимента. "
        rf"Ответ дайте в миллиграммах."
    )
    return text, str(bN)


def _isotope():
    """Убывающая геом. прогрессия с делителем. Параметры подобраны так, чтобы
    конечный член был целым."""
    factor = random.choice([2, 3, 4, 5])
    n_steps = random.randint(3, 5)
    bN_int = random.randint(1, 25)
    b1 = bN_int * factor ** n_steps
    period = random.choice([4, 5, 8, 10, 15, 20])
    total_minutes = period * n_steps
    flavor = random.choice(['cooling', 'isotope'])
    if flavor == 'cooling':
        text = (
            rf"При остывании раскалённого тела за каждые {period} {_minute_word(period)} "
            rf"температура уменьшается в {factor} {_times_word(factor)}. В начальный момент "
            rf"температура тела составляла {b1}${{}}^\circ$C. Найдите температуру "
            rf"тела через {total_minutes} {_minute_word(total_minutes)}. Ответ дайте в градусах Цельсия."
        )
    else:
        text = (
            rf"В ходе распада радиоактивного изотопа его масса уменьшается "
            rf"в {factor} {_times_word(factor)} каждые {period} {_minute_word(period)}. В начальный момент "
            rf"масса изотопа составляла {b1} мг. Найдите массу изотопа через "
            rf"{total_minutes} {_minute_word(total_minutes)}. Ответ дайте в миллиграммах."
        )
    return text, str(bN_int)


def _isotope_decimal():
    """Убывающая геом. с делителем 2 — даёт десятичные ответы (типа 12,5)."""
    n_steps = random.randint(3, 5)
    period = random.choice([5, 8, 10])
    bN_num = random.choice([5, 15, 25, 75, 125])  # bₙ в десятых: 0,5; 1,5; 2,5; 7,5; 12,5
    b1_num = bN_num * 2 ** n_steps
    b1 = Fraction(b1_num, 10)
    bN = Fraction(bN_num, 10)
    total_minutes = period * n_steps
    text = (
        rf"В ходе распада радиоактивного изотопа его масса уменьшается вдвое "
        rf"каждые {period} {_minute_word(period)}. В начальный момент масса изотопа составляла "
        rf"{_decimal_str(b1)} мг. Найдите массу изотопа через {total_minutes} {_minute_word(total_minutes)}. "
        rf"Ответ дайте в миллиграммах."
    )
    return text, _decimal_str(bN)


def generate_task():
    """№14 ОГЭ, T8+T9: геом. прогрессия, найти n-й член."""
    scenario = random.choice([_bacteria, _isotope, _isotope_decimal])
    text, answer = scenario()
    return {"condition_text": text, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(0)
    for i in range(10):
        t = generate_task()
        print(f"--- T5[{i+1}] ---")
        print(t['condition_text'])
        print(f"ответ: {t['correct_answer']}\n")
