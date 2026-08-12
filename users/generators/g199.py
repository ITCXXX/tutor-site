# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=199: OGE15: 05 — Медиана: определение и признак
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


SVG_MEDIAN_BM = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с медианой BM">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="200" y1="50" x2="160.00" y2="180.00" stroke="#1f1f1f" stroke-width="1.3"/>
  <line x1="100.0" y1="174.0" x2="100.0" y2="186.0" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="220.0" y1="174.0" x2="220.0" y2="186.0" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="160.00" cy="180.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="156.00" y="198.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">M</text>
</svg>"""
SVG_MEDIAN_BM_RIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с медианой BM, BM равно AM равно MC">
  <polygon points="40,180 100.00,76.08 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="100.00" y1="76.08" x2="160.00" y2="180.00" stroke="#1f1f1f" stroke-width="1.3"/>
  <line x1="98.0" y1="174.0" x2="98.0" y2="186.0" stroke="#1f1f1f" stroke-width="1.4"/><line x1="102.0" y1="174.0" x2="102.0" y2="186.0" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="218.0" y1="174.0" x2="218.0" y2="186.0" stroke="#1f1f1f" stroke-width="1.4"/><line x1="222.0" y1="174.0" x2="222.0" y2="186.0" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="134.2" y1="123.3" x2="123.8" y2="129.3" stroke="#1f1f1f" stroke-width="1.4"/><line x1="136.2" y1="126.8" x2="125.8" y2="132.8" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="100.00" cy="76.08" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="160.00" cy="180.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="86.00" y="72.08" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="156.00" y="198.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">M</text>
</svg>"""

def generate_task():
    subtype = random.choice(["definition", "right_sign"])
    if subtype == "definition":
        # Тип 7: BM медиана, AC задан, AM = AC/2.
        # Берём чётное AC, чтобы AM было целым.
        AC = random.choice([n for n in range(2, 201) if n % 2 == 0])
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(BM\\) — медиана, "
            f"\\(AC = {AC}\\). Найдите \\(AM\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_MEDIAN_BM}", "correct_answer": str(AC // 2)}
    else:
        # Тип 9: BM медиана, BM = AM = MC ⇒ ∠B = 90° ⇒ ∠A = 90° − ∠C.
        angC = random.randint(5, 85)
        text = (
            f"В треугольнике \\(ABC\\) проведена медиана \\(BM\\), причём "
            f"\\(BM = AM = MC\\), \\(\\angle C = {angC}°\\). "
            f"Найдите угол \\(A\\). Ответ дайте в градусах."
        )
        return {"condition_text": f"{text}<br><br>{SVG_MEDIAN_BM_RIGHT}", "correct_answer": str(90 - angC)}
