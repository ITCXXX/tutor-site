# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=194: Палладий: случайные двуслоги
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401


import random
from users.palladium import SYLLABLES, join_palladium

def generate_task():
    s1 = random.choice(SYLLABLES)
    s2 = random.choice(SYLLABLES)
    answer = join_palladium(s1, s2)
    return {
        "condition_text": (
            "Запишите по системе Палладия двусложное слово (слитно, "
            "без пробелов, без тонов):<br><br>"
            f"<b style=\"font-size:1.4em;\">{s1} {s2}</b>"
        ),
        "correct_answer": answer,
        "pinyin1": s1,
        "pinyin2": s2,
    }
