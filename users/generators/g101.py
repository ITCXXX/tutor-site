# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=101: OGE12: Тип 4 — ускорение
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def generate_task():
    """№12 ОГЭ, Тип 4: a = ω²·R, найти R. ω и R целые."""
    omega = random.randint(2, 10)
    R = random.randint(2, 15)
    a = omega * omega * R
    text = (
        rf"Центростремительное ускорение при движении по окружности (в м/с²) "
        rf"вычисляется по формуле $a = \omega^{{2}}R$, где $\omega$ — угловая "
        rf"скорость (в с⁻¹), $R$ — радиус окружности (в метрах). Пользуясь этой "
        rf"формулой, найдите радиус $R$, если угловая скорость равна {omega} с⁻¹, "
        rf"а центростремительное ускорение равно {a} м/с². Ответ дайте в метрах."
    )
    return {"condition_text": text, "correct_answer": str(R)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:200]}...\n     ответ = {t['correct_answer']}\n")
