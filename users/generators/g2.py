# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=2: 10 чашки
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


# users/problem_generators.py
import random
from fractions import Fraction

class CupsProbabilityGenerator:
    """
    Генератор задач про чашки с красными и синими цветами.
    Ответ – вероятность в виде конечной десятичной дроби.
    """

    def execute_generator(self, student):
        # 1. Выбираем общее число чашек вида 2^a * 5^b
        possible_totals = [10, 20, 25, 40, 50, 80, 100]
        total_cups = random.choice(possible_totals)

        # 2. Выбираем число красных чашек (хотя бы 1 и не все)
        red_cups = random.randint(1, total_cups - 1)
        blue_cups = total_cups - red_cups

        # 3. Вероятность = blue_cups / total_cups
        frac = Fraction(blue_cups, total_cups)  # автоматически сокращает дробь

        # 4. Переводим в десятичную строку (конечная дробь гарантирована)
        decimal_value = frac.numerator / frac.denominator
        decimal_str = f"{decimal_value:.6f}".rstrip('0').rstrip('.')

        text = (
            f"У бабушки {total_cups} чашек: {red_cups} с красными цветами, "
            f"остальные с синими. Бабушка наливает чай в случайно выбранную чашку. "
            f"Найдите вероятность того, что это будет чашка с синими цветами. "
            f"Ответ дайте в виде десятичной дроби."
        )

        task_data = {
            "total_cups": total_cups,
            "red_cups": red_cups,
            "blue_cups": blue_cups,
            "text": text,
            "correct_answer": decimal_str,
        }

        return task_data
