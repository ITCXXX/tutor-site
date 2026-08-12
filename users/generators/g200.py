# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=200: OGE15: 06 — Теорема Пифагора
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random

def _ans(x):
    """Превращает число в строку: целое без ',0', дробное — с запятой."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    rounded = round(x, 1)
    return f"{rounded:.1f}".replace(".", ",")


SVG_RIGHT_C = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Прямоугольный треугольник ABC, угол C равен 90°">
  <polygon points="40,180 280,60 40,60" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <polyline points="40.0,70.0 50.0,70.0 50.0,60.0" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="60.00" r="2.5" fill="#1f1f1f"/><circle cx="40.00" cy="60.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="288.00" y="56.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="22.00" y="56.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""

PYTH_TRIPLES = [
    (3, 4, 5), (5, 12, 13), (6, 8, 10), (7, 24, 25), (8, 15, 17),
    (9, 12, 15), (9, 40, 41), (10, 24, 26), (12, 16, 20), (12, 35, 37),
    (15, 20, 25), (15, 36, 39), (16, 30, 34), (18, 24, 30), (20, 21, 29),
    (20, 48, 52), (21, 28, 35), (24, 32, 40), (28, 45, 53), (30, 40, 50),
    (33, 44, 55), (36, 48, 60), (40, 42, 58), (45, 60, 75), (48, 55, 73),
    (60, 80, 100),
]

def generate_task():
    a, b, c = sorted(random.choice(PYTH_TRIPLES))   # a < b < c, c — гипотенуза
    direction = random.choice(["forward", "inverse"])
    if direction == "forward":
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AC = {b}\\), \\(BC = {a}\\). Найдите \\(AB\\)."
        )
        answer = str(c)
    else:
        which = random.choice(["hide_BC", "hide_AC"])
        if which == "hide_BC":
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(AC = {b}\\), \\(AB = {c}\\). Найдите \\(BC\\)."
            )
            answer = str(a)
        else:
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {a}\\), \\(AB = {c}\\). Найдите \\(AC\\)."
            )
            answer = str(b)
    return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": answer}
