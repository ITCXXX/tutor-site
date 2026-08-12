# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=205: OGE15: 11 — Площадь треугольника
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
SVG_AREA_AH = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с высотой CH к стороне AB">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="280" y1="180" x2="184.56" y2="62.54" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="4,3"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="184.56" cy="62.54" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="170.56" y="64.54" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">H</text>
</svg>"""
SVG_AREA_SIN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с углом при B">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <path d="M 179.8,66.4 A 26,26 0 0 0 213.6,72.1" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""

# Допустимые значения sin (даёт ≤1 знак после запятой при произведении).
SIN_RATIOS = [(3,5),(4,5),(5,13),(12,13),(8,17),(15,17),(24,25),(7,25),
              (20,29),(21,29),(1,2),(1,4),(3,4),(1,5),(2,5),(3,10),(7,10),(9,10)]


def generate_task():
    subtype = random.choice(["legs", "side_height", "two_sides_sin"])
    if subtype == "legs":
        # Тип 24: S = a·b/2 в прямоугольном треугольнике.
        a = random.randint(2, 50)
        b = random.randint(2, 50)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AC = {b}\\), \\(BC = {a}\\). Найдите площадь треугольника \\(ABC\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": _ans(a * b / 2)}
    elif subtype == "side_height":
        # Тип 25: S = a·h/2. Сторона a — это AB, высота h — CH.
        a = random.randint(2, 100)
        h = random.randint(1, 50)
        text = (
            f"В треугольнике \\(ABC\\) сторона \\(AB\\) равна \\({a}\\), "
            f"а высота \\(CH\\), проведённая к этой стороне, равна \\({h}\\). "
            f"Найдите площадь треугольника \\(ABC\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_AREA_AH}", "correct_answer": _ans(a * h / 2)}
    else:
        # Тип 26: S = ½·AB·BC·sin∠B.
        for _ in range(80):
            a = random.randint(3, 50)
            b = random.randint(3, 50)
            p, q = random.choice(SIN_RATIOS)
            num = a * b * p
            den = 2 * q
            if (num * 10) % den != 0:
                continue
            v = round(num / den, 1)
            S_str = (str(int(round(v))) if abs(v - round(v)) < 1e-9
                     else f"{v:.1f}".replace(".", ","))
            text = (
                f"В треугольнике \\(ABC\\) известно, что \\(AB = {a}\\), \\(BC = {b}\\), "
                f"\\(\\sin\\angle ABC = \\dfrac{{{p}}}{{{q}}}\\). "
                f"Найдите площадь треугольника \\(ABC\\)."
            )
            return {"condition_text": f"{text}<br><br>{SVG_AREA_SIN}", "correct_answer": S_str}
        # запасной вариант
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(AB = 14\\), \\(BC = 5\\), "
            f"\\(\\sin\\angle ABC = \\dfrac{{6}}{{7}}\\). "
            f"Найдите площадь треугольника \\(ABC\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_AREA_SIN}", "correct_answer": "30"}
