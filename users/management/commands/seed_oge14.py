# -*- coding: utf-8 -*-
"""
Management command: создаёт 6 ProblemGenerator-ов и Assignment-ов под урок
«Задание 14» курса ОГЭ. Тема — «Прогрессии» (арифметическая и геометрическая).

Идемпотентен: ре-ран не плодит дубли и не переписывает переименованный title
(поиск Assignment по lesson+order, а не по title).

Usage:
    python manage.py seed_oge14
    python manage.py seed_oge14 --clear   # снести и пересоздать
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Код генераторов
# ──────────────────────────────────────────────────────────────────────────────


GEN_T1_T4 = r'''
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
'''


GEN_T3 = r'''
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
'''


GEN_T2_T5_T7 = r'''
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
'''


GEN_T6 = r'''
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
'''


GEN_T8_T9 = r'''
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
'''


GEN_T10 = r'''
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


def _bouncing_ball():
    """Мячик: 1-й прыжок b₁ м, каждый следующий в k раз меньше.
    Найти n: первый прыжок < threshold."""
    factor = random.choice([2, 3])
    answer_n = random.randint(4, 8)        # хотим, чтобы ответ был именно n
    # Проектируем «от ответа»: bₙ < threshold ≤ b_{n-1}, всё в сантиметрах.
    # b₁ должно быть круглым, b в см и совпадать с условием в м.
    # Берём b₁ ∈ {120, 160, 240, 320, 480, 640} см или похожее (кратно factor^answer_n).
    base = random.choice([1, 2, 3, 4, 5, 6])
    b1_cm = base * factor ** (answer_n - 1)  # чтобы все шаги были целыми
    # Нужно, чтобы b1 в метрах звучало нормально: ≤ 5 м.
    if b1_cm < 100 or b1_cm > 500:
        # Пере-семплируем base иначе
        for _ in range(20):
            base = random.choice([1, 2, 3, 4, 5, 6, 8])
            b1_cm = base * factor ** (answer_n - 1)
            if 100 <= b1_cm <= 500:
                break
        else:
            b1_cm = 240  # дефолт
    b1_m_str = _decimal_str(Fraction(b1_cm, 100))
    bn = b1_cm
    for _ in range(answer_n - 1):
        bn = bn // factor
    bn_minus = bn * factor
    # Threshold выбираем строго между bn (исключительно) и bn_minus (включительно).
    # Простой выбор — целое число см между ними.
    if bn_minus - bn <= 1:
        # слишком тесно — увеличим разрыв через factor
        threshold = bn + 1
    else:
        threshold = random.randint(bn + 1, bn_minus)
    object_name = random.choice(["каучуковый мячик", "теннисный мячик", "резиновый шар"])
    text = (
        rf"С силой бросили {object_name} на асфальт. Отскочив, "
        rf"{object_name.split()[1]} подпрыгнул на {b1_m_str} м, а при каждом следующем "
        rf"прыжке он поднимался на высоту в {factor} раза меньше предыдущей. "
        rf"При каком по счёту прыжке {object_name.split()[1]} в первый раз не "
        rf"достигнет высоты {threshold} см?"
    )
    return text, str(answer_n)


def _falling_pressure():
    """Давление в баллоне: каждый раз падает в k раз. Найти момент, когда упадёт ниже порога."""
    factor = random.choice([2, 3])
    answer_n = random.randint(4, 7)
    base = random.choice([1, 2, 3, 4, 6])
    p1 = base * factor ** (answer_n - 1)
    if p1 < 8 or p1 > 256:
        for _ in range(20):
            base = random.choice([1, 2, 3, 4, 5, 6])
            p1 = base * factor ** (answer_n - 1)
            if 8 <= p1 <= 256:
                break
        else:
            p1 = 64
    pn = p1
    for _ in range(answer_n - 1):
        pn = pn // factor
    pn_minus = pn * factor
    if pn_minus - pn <= 1:
        threshold = pn + 1
    else:
        threshold = random.randint(pn + 1, pn_minus)
    period = random.choice([5, 10, 15, 30])
    text = (
        rf"В сосуде идёт химическая реакция, при которой за каждые {period} "
        rf"секунд давление падает в {factor} раза. В начальный момент давление "
        rf"в сосуде составляло {p1} кПа. На каком по счёту {period}-секундном "
        rf"замере давление окажется впервые ниже {threshold} кПа?"
    )
    return text, str(answer_n)


def generate_task():
    """№14 ОГЭ, T10: геом. прогрессия, найти номер члена, впервые меньшего порога."""
    scenario = random.choice([_bouncing_ball, _falling_pressure])
    text, answer = scenario()
    return {"condition_text": text, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(0)
    for i in range(10):
        t = generate_task()
        print(f"--- T6[{i+1}] ---")
        print(t['condition_text'])
        print(f"ответ: {t['correct_answer']}\n")
'''


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    # (order, gen_name, asg_title, code)
    (1, 'OGE14: Тип 1+4 — ариф., n-й член', 'Арифметическая прогрессия — n-й член', GEN_T1_T4),
    (2, 'OGE14: Тип 3 — через два члена', 'Арифметическая прогрессия — через два известных члена', GEN_T3),
    (3, 'OGE14: Тип 2+5+7 — ариф., сумма', 'Арифметическая прогрессия — сумма', GEN_T2_T5_T7),
    (4, 'OGE14: Тип 6 — до остановки', 'Арифметическая прогрессия — до полной остановки', GEN_T6),
    (5, 'OGE14: Тип 8+9 — геом., n-й член', 'Геометрическая прогрессия — n-й член', GEN_T8_T9),
    (6, 'OGE14: Тип 10 — геом., найти n', 'Геометрическая прогрессия — найти номер члена', GEN_T10),
]


class Command(BaseCommand):
    help = 'Создаёт «Задание 14» курса ОГЭ с 6 генераторами на прогрессии.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 14» и пересоздать.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден.'
            ))
            return

        # Ищем модуль 'Первая часть' по имени, не first() по order — иначе с
        # появлением модуля 'Задания 1-5' (order=0) создавался дубль урока.
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 14').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 14» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 14',
            defaults={'order': 14, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 14:
            lesson.order = 14
            lesson.save(update_fields=['order'])
        if created:
            self.stdout.write(self.style.SUCCESS(f'Урок создан: {lesson.title}'))

        existing_by_order = {a.order: a for a in lesson.assignments.all()}

        for order, gen_name, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                    'config': {},
                },
            )

            assign = existing_by_order.get(order)
            if assign:
                # title не перезаписываем — мог быть переименован вручную.
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'decimal_input'
                assign.required_correct = 3
                assign.save()
                shown_title = assign.title
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=order,
                    title=asg_title,
                    description='',
                    assignment_type='test',
                    answer_type='decimal_input',
                    required_correct=3,
                    problem_generator=generator,
                )
                shown_title = asg_title

            self.stdout.write(self.style.SUCCESS(f'  + [{order}] {shown_title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: «Задание 14» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
