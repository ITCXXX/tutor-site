# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=115: OGE14: Тип 1+4 — ариф., n-й член
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def _amphi_word(n):
    """ряд / ряда / рядов в зависимости от числа."""
    if n % 100 in (11, 12, 13, 14):
        return "рядов"
    last = n % 10
    if last == 1: return "ряд"
    if last in (2, 3, 4): return "ряда"
    return "рядов"


def _seat_word(n):
    if n % 100 in (11, 12, 13, 14):
        return "мест"
    last = n % 10
    if last == 1: return "место"
    if last in (2, 3, 4): return "места"
    return "мест"


def _ord_word(n):
    """Порядковое числительное в винительном падеже: «1-й ряд», «10-м ряду»."""
    return f"{n}-м"


def _amphitheatre():
    """Ариф. с d > 0; вопрос про N-й ряд."""
    a1 = random.randint(15, 30)
    d = random.randint(1, 4)
    n = random.randint(7, 18)
    an = a1 + (n - 1) * d
    venue = random.choice([
        "В амфитеатре",
        "В театре",
        "В концертном зале",
    ])
    text = (
        rf"{venue} {n + random.randint(0, 5)} {_amphi_word(0)}. "
        rf"В первом ряду {a1} {_seat_word(a1)}, а в каждом следующем на {d} "
        rf"{_seat_word(d)} больше, чем в предыдущем. Сколько мест в "
        rf"{_ord_word(n)} ряду?"
    )
    # Поправка слова про общее число рядов: random.randint выше может дать число вне диапазона склонения.
    return text, str(an)


def _stadium():
    """Стадион/кинотеатр — то же, чуть другая формулировка."""
    a1 = random.randint(20, 40)
    d = random.randint(2, 5)
    n = random.randint(6, 15)
    an = a1 + (n - 1) * d
    obj = random.choice(["кинотеатре", "стадионе", "лекционной аудитории"])
    text = (
        rf"Зрительские ряды в {obj}: в первом ряду — {a1} мест, а в каждом следующем — на {d} места "
        rf"больше, чем в предыдущем. Сколько мест в {_ord_word(n)} ряду?"
    )
    return text, str(an)


def _cooling():
    """Охлаждение: a₁ = начальная температура, через t минут понизилась на t·k."""
    start_temp = random.choice([-7, -5, -3, -2, 2, 3, 5, 7, 10, 12, 15])
    rate = random.randint(2, 8)
    t = random.randint(3, 8)
    final = start_temp - t * rate
    duration = t + random.randint(1, 5)  # «опыт длился N минут»
    text = (
        rf"При проведении опыта вещество равномерно охлаждали в течение {duration} минут. "
        rf"При этом каждую минуту его температура уменьшалась на {rate} ${{}}^\circ$C. "
        rf"Найдите температуру вещества в градусах Цельсия через {t} "
        rf"{'минуту' if t == 1 else ('минуты' if 2 <= t % 10 <= 4 and t % 100 not in (12, 13, 14) else 'минут')} "
        rf"после начала опыта, если начальная температура вещества составляла "
        rf"{start_temp} ${{}}^\circ$C."
    )
    return text, str(final)


def _diver():
    """Водолаз спускается, давление возрастает на k каждые 10 м."""
    start_p = random.randint(1, 5) * 100  # начальное давление в гПа
    rate = random.randint(8, 15) * 10  # прирост на каждые 10 м
    t = random.randint(3, 8)
    final = start_p + t * rate
    text = (
        rf"При погружении водолаз каждые 10 метров отмечал прирост давления "
        rf"на {rate} гПа. У поверхности давление составляло {start_p} гПа. "
        rf"Какое давление зафиксирует водолаз через {t * 10} метров погружения?"
    )
    return text, str(final)


def generate_task():
    """№14 ОГЭ, T1+T4: ариф. прогрессия, найти n-й член."""
    scenario = random.choice([_amphitheatre, _stadium, _cooling, _diver])
    text, answer = scenario()
    return {"condition_text": text, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T1[{i+1}] ---")
        print(t['condition_text'])
        print(f"ответ: {t['correct_answer']}\n")
