# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=99: OGE12: Тип 1+2 — F ↔ C
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
from fractions import Fraction


def decimal_str(f):
    if f.denominator == 1: return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def degree_word(n_str):
    """n_str — строка вида '15' или '-31' или '5,4'. Возвращает «градус/градуса/градусов»."""
    if ',' in n_str:
        return "градуса"  # для дробных — обычно «градуса»
    n = abs(int(n_str.replace('−', '-')))
    if n % 100 in (11, 12, 13, 14):
        return "градусов"
    last = n % 10
    if last == 1: return "градус"
    if last in (2, 3, 4): return "градуса"
    return "градусов"


def generate_task():
    """
    №12 ОГЭ, объединённый Тип 1+2: перевод температур F↔C.
    Раздвоение: F→C (целые tF, tC) или C→F (tC целое, tF — десятичный с 1 знаком).
    """
    direction = random.choice(['F_to_C', 'C_to_F'])

    if direction == 'F_to_C':
        # Идём от ответа: tC = 5k, tF = 32 + 9k → оба целые
        k = random.choice([n for n in range(-13, 18) if n != 0])
        tF = 32 + 9 * k
        tC = 5 * k
        tF_str = decimal_str(Fraction(tF))
        text = (
            rf"Перевести значение температуры по шкале Фаренгейта в шкалу Цельсия "
            rf"позволяет формула $t_C = \dfrac{{5}}{{9}}(t_F - 32)$, где $t_C$ — "
            rf"температура в градусах Цельсия, $t_F$ — температура в градусах Фаренгейта. "
            rf"Скольким градусам по шкале Цельсия соответствует {tF_str} {degree_word(tF_str)} "
            rf"по шкале Фаренгейта?"
        )
        answer = decimal_str(Fraction(tC))
    else:
        # tC любое целое (можно не кратно 5). Тогда tF = 1.8·tC + 32 — десятичная с 1 знаком.
        tC = random.choice([n for n in range(-50, 51) if n != 0])
        tF_frac = Fraction(18, 10) * tC + 32
        tC_str = decimal_str(Fraction(tC))
        text = (
            rf"Чтобы перевести значение температуры по шкале Цельсия в шкалу Фаренгейта, "
            rf"пользуются формулой $t_F = 1{{,}}8 \cdot t_C + 32$, где $t_C$ — "
            rf"температура в градусах Цельсия, $t_F$ — температура в градусах Фаренгейта. "
            rf"Скольким градусам по шкале Фаренгейта соответствует {tC_str} {degree_word(tC_str)} "
            rf"по шкале Цельсия?"
        )
        answer = decimal_str(tF_frac)

    return {"condition_text": text, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(0)
    for i in range(6):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}\n     ответ = {t['correct_answer']}\n")
