# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=116: OGE14: Тип 3 — через два члена
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def _seat_word(n):
    if n % 100 in (11, 12, 13, 14):
        return "мест"
    last = n % 10
    if last == 1: return "место"
    if last in (2, 3, 4): return "места"
    return "мест"


def _ord(n):
    return f"{n}-м"


def generate_task():
    """№14 ОГЭ, T3: ариф. прогрессия через два известных члена → найти a_N (последний).

    Проектирование: задаём a₁, d, всего N рядов. Выбираем два разных индекса k и m
    (k < m) — их значения a_k и a_m даём в условии. Ответ — a_N.
    """
    d = random.randint(1, 4)
    a1 = random.randint(8, 25)
    N = random.randint(10, 18)
    while True:
        k = random.randint(2, N - 3)
        m = random.randint(k + 2, N - 1)
        if m - k >= 2:
            break

    a_k = a1 + (k - 1) * d
    a_m = a1 + (m - 1) * d
    a_N = a1 + (N - 1) * d

    venue = random.choice(["амфитеатре", "концертном зале", "лекционной аудитории"])
    text = (
        rf"В {venue} {N} рядов, причём в каждом следующем ряду на одно и то же "
        rf"число мест больше, чем в предыдущем. В {_ord(k)} ряду {a_k} "
        rf"{_seat_word(a_k)}, а в {_ord(m)} ряду {a_m} {_seat_word(a_m)}. "
        rf"Сколько мест в последнем ряду?"
    )
    return {"condition_text": text, "correct_answer": str(a_N)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T2[{i+1}] ---")
        print(t['condition_text'])
        print(f"ответ: {t['correct_answer']}\n")
