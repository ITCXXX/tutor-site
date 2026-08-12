# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=106: OGE12: Тип 9+10 — колодец
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def generate_task():
    """№12 ОГЭ, объединённый Тип 9+10: C = a + b·n. Линейная стоимость колодца."""
    FIRMS = [
        ("Чистая вода", 6500, 4000),
        ("Родник",      6000, 4100),
        ("Источник",    7000, 3800),
        ("Колодезь",    5500, 4200),
        ("Артезианка",  8000, 3900),
    ]
    firm, base, per = random.choice(FIRMS)
    n = random.randint(3, 25)
    C = base + per * n
    text = (
        rf"В фирме «{firm}» стоимость (в рублях) колодца из железобетонных колец "
        rf"рассчитывается по формуле $C = {base} + {per}n$, где $n$ — число колец, "
        rf"установленных в колодце. Пользуясь этой формулой, рассчитайте стоимость "
        rf"колодца из {n} колец. Ответ дайте в рублях."
    )
    return {"condition_text": text, "correct_answer": str(C)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}\n     ответ = {t['correct_answer']}\n")
