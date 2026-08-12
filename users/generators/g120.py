# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=120: OGE14: Тип 10 — геом., найти n
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
