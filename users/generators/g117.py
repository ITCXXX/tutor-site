# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=117: OGE14: Тип 2+5+7 — ариф., сумма
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
from fractions import Fraction


def _seat_word(n):
    if n % 100 in (11, 12, 13, 14):
        return "мест"
    last = n % 10
    if last == 1: return "место"
    if last in (2, 3, 4): return "места"
    return "мест"


def _decimal_str(f):
    """Fraction → строка с запятой. Гарантирует точное представление если знаменатель — степень 2 и 5."""
    if f.denominator == 1:
        return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num, den = abs(f.numerator), f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    target = max(a, b)
    pad = num * (10 ** target) // den
    s = str(pad).rjust(target + 1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def _amphitheatre_sum():
    """T2-стиль: амфитеатр, найти всего мест."""
    a1 = random.randint(15, 25)
    d = random.randint(1, 4)
    n = random.randint(10, 18)
    s = (a1 + a1 + (n - 1) * d) * n // 2
    venue = random.choice(["амфитеатре", "концертном зале", "лекционной аудитории"])
    text = (
        rf"В {venue} {n} рядов. В первом ряду {a1} {_seat_word(a1)}, "
        rf"а в каждом следующем на {d} {_seat_word(d)} больше, чем в предыдущем. "
        rf"Сколько всего мест в {venue}?"
    )
    return text, str(s)


def _braking_sum_known_n():
    """T5-стиль: торможение n секунд, проектируем без полной остановки."""
    n = random.randint(4, 7)
    d = random.randint(2, 5)            # шаг убывания (положительное число)
    # Чтобы в N секунд автомобиль ещё двигался, нужно a_n > 0.
    # a_n = a₁ - (n-1)d > 0 ⇒ a₁ > (n-1)d. Берём a₁ ≥ (n-1)d + 1.
    a1_min = (n - 1) * d + 1
    a1 = random.randint(a1_min, a1_min + 15)
    s = (2 * a1 - (n - 1) * d) * n // 2
    text = (
        rf"Водитель автомобиля начал торможение. За первую секунду после начала "
        rf"торможения автомобиль проехал {a1} м, а за каждую следующую секунду "
        rf"на {d} м меньше, чем за предыдущую. Сколько метров автомобиль прошёл "
        rf"за первые {n} секунд торможения?"
    )
    return text, str(s)


def _train_decimal():
    """T7-стиль: десятичные параметры с шагом 0,1. Параметры — мн. на 0.1."""
    p = random.randint(3, 9)            # a₁ = p / 10
    q = random.randint(1, 5)            # d = q / 10
    n = random.randint(5, 9)
    a1 = Fraction(p, 10)
    d = Fraction(q, 10)
    s = (2 * a1 + (n - 1) * d) * n / 2
    moving_thing = random.choice([
        ("Поезд начал движение от станции", "состав", "состав"),
        ("Самолёт начал разгон по взлётной полосе", "самолёт", "самолёт"),
        ("Лыжник начал спуск с горы", "лыжник", "лыжник"),
    ])
    text = (
        rf"{moving_thing[0]}. За первую секунду {moving_thing[1]} прошёл "
        rf"{_decimal_str(a1)} м, а за каждую следующую секунду на {_decimal_str(d)} м "
        rf"больше, чем за предыдущую. Сколько метров {moving_thing[2]} прошёл "
        rf"за первые {n} секунд движения?"
    )
    return text, _decimal_str(s)


def generate_task():
    """№14 ОГЭ, T2+T5+T7: ариф. прогрессия, найти сумму."""
    scenario = random.choice([_amphitheatre_sum, _braking_sum_known_n, _train_decimal])
    text, answer = scenario()
    return {"condition_text": text, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(0)
    for i in range(10):
        t = generate_task()
        print(f"--- T3[{i+1}] ---")
        print(t['condition_text'])
        print(f"ответ: {t['correct_answer']}\n")
