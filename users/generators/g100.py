# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=100: OGE12: Тип 3 — мощность
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def generate_task():
    """№12 ОГЭ, Тип 3: P = I²R, найти R."""
    I = random.randint(3, 12)
    R = random.randint(2, 15)
    P = I * I * R
    text = (
        rf"Мощность постоянного тока (в ваттах) вычисляется по формуле $P = I^{{2}}R$, "
        rf"где $I$ — сила тока (в амперах), $R$ — сопротивление (в омах). Пользуясь "
        rf"этой формулой, найдите сопротивление $R$, если мощность составляет {P} Вт, "
        rf"а сила тока равна {I} А. Ответ дайте в омах."
    )
    return {"condition_text": text, "correct_answer": str(R)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:200]}...\n     ответ = {t['correct_answer']}\n")
