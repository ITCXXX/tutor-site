# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=196: OGE15: 02 — Углы. Равнобедренный
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


SVG_ISOSCELES = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равнобедренный треугольник ABC, AB равно BC">
  <polygon points="60,180 160.0,50 260,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="105.2" y1="111.3" x2="114.8" y2="118.7" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="214.8" y1="111.3" x2="205.2" y2="118.7" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="60.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="160.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="260.00" cy="180.00" r="2.5" fill="#1f1f1f"/>
  <text x="42.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="155.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="268.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""

def generate_task():
    # Тип 3: AB = BC, известен угол при вершине B, найти угол при основании.
    # Чтобы базовый угол был целым, апекс берём чётным от 10 до 170.
    apex = random.choice([n for n in range(10, 171) if n % 2 == 0])
    base = (180 - apex) // 2
    text = (
        f"В равнобедренном треугольнике \\(ABC\\) известно, что \\(AB = BC\\), "
        f"\\(\\angle B = {apex}°\\). Найдите \\(\\angle A\\). "
        f"Ответ дайте в градусах."
    )
    return {"condition_text": f"{text}<br><br>{SVG_ISOSCELES}", "correct_answer": str(base)}
