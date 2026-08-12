# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=195: OGE15: 01 — Углы. Сумма и смежный
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


SVG_BASIC = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""
SVG_RIGHT_C = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Прямоугольный треугольник ABC, угол C равен 90°">
  <polygon points="40,180 280,60 40,60" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <polyline points="40.0,70.0 50.0,70.0 50.0,60.0" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="60.00" r="2.5" fill="#1f1f1f"/><circle cx="40.00" cy="60.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="288.00" y="56.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="22.00" y="56.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""
SVG_EXTERNAL_C = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с продолжением стороны AC за C">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="280" y1="180" x2="310.00" y2="180.00" stroke="#1f1f1f" stroke-width="1.3" stroke-dasharray="5,3"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="268.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""

def generate_task():
    subtype = random.choice(["third", "right_other", "external"])
    if subtype == "third":
        while True:
            a = random.randint(15, 150)
            b = random.randint(15, 150)
            c = 180 - a - b
            if 10 <= c <= 160:
                break
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(\\angle A = {a}°\\), "
            f"\\(\\angle B = {b}°\\). Найдите \\(\\angle C\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(c)
        svg = SVG_BASIC
    elif subtype == "right_other":
        a = random.choice([n for n in range(5, 86) if n != 45])
        b = 90 - a
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(\\angle A = {a}°\\). Найдите \\(\\angle B\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(b)
        svg = SVG_RIGHT_C
    else:
        c = random.randint(15, 170)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\({c}°\\). "
            f"Найдите внешний угол при вершине \\(C\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(180 - c)
        svg = SVG_EXTERNAL_C
    return {"condition_text": f"{text}<br><br>{svg}", "correct_answer": answer}
