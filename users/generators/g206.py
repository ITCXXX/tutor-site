# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=206: OGE15: 12 — Средняя линия
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


SVG_MIDLINE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC со средней линией MN">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="120.00" y1="115.00" x2="240.00" y2="115.00" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="76.2" y1="142.8" x2="83.8" y2="152.2" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="156.2" y1="77.8" x2="163.8" y2="87.2" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="224.1" y1="77.7" x2="213.8" y2="83.9" stroke="#1f1f1f" stroke-width="1.4"/><line x1="226.2" y1="81.1" x2="215.9" y2="87.3" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="264.1" y1="142.7" x2="253.8" y2="148.9" stroke="#1f1f1f" stroke-width="1.4"/><line x1="266.2" y1="146.1" x2="255.9" y2="152.3" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="120.00" cy="115.00" r="2.5" fill="#1f1f1f"/><circle cx="240.00" cy="115.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="104.00" y="117.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">M</text>
  <text x="246.00" y="117.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">N</text>
</svg>"""

def generate_task():
    # MN = AC/2. Берём чётное AC.
    AC = random.choice([n for n in range(4, 201) if n % 2 == 0])
    text = (
        f"Точки \\(M\\) и \\(N\\) — середины сторон \\(AB\\) и \\(BC\\) "
        f"треугольника \\(ABC\\). Сторона \\(AC\\) равна \\({AC}\\). "
        f"Найдите \\(MN\\)."
    )
    return {"condition_text": f"{text}<br><br>{SVG_MIDLINE}", "correct_answer": str(AC // 2)}
