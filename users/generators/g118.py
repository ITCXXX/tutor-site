# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=118: OGE14: Тип 6 — до остановки
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def _braking_full_stop():
    """Торможение автомобиля до полной остановки."""
    d = random.choice([2, 3, 4, 5, 6, 8])     # шаг убывания
    k = random.randint(3, 7)                   # число «движущихся» секунд + 1
    a1 = k * d                                 # тогда a_(k+1) = 0
    s = a1 * (k + 1) // 2                      # сумма (a₁ + ... + a_(k+1)) = (k+1)·a₁/2
    text = (
        rf"Водитель автомобиля начал торможение. За первую секунду после начала "
        rf"торможения автомобиль проехал {a1} м, а за каждую следующую секунду "
        rf"он проезжал на {d} м меньше, чем за предыдущую. Сколько метров "
        rf"автомобиль прошёл до полной остановки?"
    )
    return text, str(s)


def _ball_stops_bouncing():
    """Прыжки мячика, теряющего одинаковую высоту с каждым прыжком."""
    d = random.choice([5, 10, 15, 20, 25])
    k = random.randint(3, 6)
    h1 = k * d
    s = h1 * (k + 1) // 2
    text = (
        rf"Прыгающий мячик с каждым ударом о землю теряет одинаковую высоту. "
        rf"После первого удара мячик подпрыгнул на высоту {h1} см, а каждый "
        rf"следующий подъём был на {d} см ниже предыдущего. На какую общую "
        rf"высоту мячик поднимался, пока окончательно не остановится? "
        rf"Ответ дайте в сантиметрах."
    )
    return text, str(s)


def _runner_decelerates():
    """Бегун постепенно снижает темп до остановки."""
    d = random.choice([2, 3, 4, 5])
    k = random.randint(4, 7)
    a1 = k * d
    s = a1 * (k + 1) // 2
    text = (
        rf"Уставший бегун начал замедляться: за первую секунду после момента, "
        rf"когда он начал тормозить, он пробежал {a1} м, а за каждую следующую "
        rf"секунду — на {d} м меньше, чем за предыдущую. Сколько метров пробежал "
        rf"бегун до полной остановки?"
    )
    return text, str(s)


def generate_task():
    """№14 ОГЭ, T6: ариф. прогрессия с убывающим шагом до a_n = 0; сумма."""
    scenario = random.choice([_braking_full_stop, _ball_stops_bouncing, _runner_decelerates])
    text, answer = scenario()
    return {"condition_text": text, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T4[{i+1}] ---")
        print(t['condition_text'])
        print(f"ответ: {t['correct_answer']}\n")
