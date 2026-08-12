# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=201: OGE15: 07 — Равносторонний. Сторона → чевиана
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


SVG_EQ_MEDIAN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равносторонний треугольник ABC с медианой CM">
  <polygon points="80,190 160.00,51.44 240,190" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="240" y1="190" x2="120.00" y2="120.72" stroke="#1f1f1f" stroke-width="1.3"/>
  <line x1="93.8" y1="154.1" x2="104.2" y2="160.1" stroke="#1f1f1f" stroke-width="1.4"/><line x1="95.8" y1="150.6" x2="106.2" y2="156.6" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="133.8" y1="84.8" x2="144.2" y2="90.8" stroke="#1f1f1f" stroke-width="1.4"/><line x1="135.8" y1="81.3" x2="146.2" y2="87.3" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="205.2" y1="117.7" x2="194.8" y2="123.7" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="160.0" y1="184.0" x2="160.0" y2="196.0" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="80.00" cy="190.00" r="2.5" fill="#1f1f1f"/><circle cx="160.00" cy="51.44" r="2.5" fill="#1f1f1f"/><circle cx="240.00" cy="190.00" r="2.5" fill="#1f1f1f"/><circle cx="120.00" cy="120.72" r="2.5" fill="#1f1f1f"/>
  <text x="62.00" y="210.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text><text x="155.00" y="43.44" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text><text x="248.00" y="210.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="104.00" y="122.72" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">M</text>
</svg>"""
SVG_EQ_HEIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равносторонний треугольник ABC с высотой CH">
  <polygon points="80,190 160.00,51.44 240,190" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="240" y1="190" x2="120.00" y2="120.72" stroke="#1f1f1f" stroke-width="1.3" stroke-dasharray="4,3"/>
  <line x1="114.8" y1="117.7" x2="125.2" y2="123.7" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="205.2" y1="117.7" x2="194.8" y2="123.7" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="160.0" y1="184.0" x2="160.0" y2="196.0" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="80.00" cy="190.00" r="2.5" fill="#1f1f1f"/><circle cx="160.00" cy="51.44" r="2.5" fill="#1f1f1f"/><circle cx="240.00" cy="190.00" r="2.5" fill="#1f1f1f"/><circle cx="120.00" cy="120.72" r="2.5" fill="#1f1f1f"/>
  <text x="62.00" y="210.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text><text x="155.00" y="43.44" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text><text x="248.00" y="210.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="104.00" y="122.72" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">H</text>
</svg>"""
SVG_EQ_BISECTOR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равносторонний треугольник ABC с биссектрисой CD">
  <polygon points="80,190 160.00,51.44 240,190" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="240" y1="190" x2="120.00" y2="120.72" stroke="#1f1f1f" stroke-width="1.3"/>
  <path d="M 231.0,174.4 A 18,18 0 0 0 224.4,181.0" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>
  <path d="M 214.0,175.0 A 30,30 0 0 0 210.0,190.0" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>
  <line x1="114.8" y1="117.7" x2="125.2" y2="123.7" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="205.2" y1="117.7" x2="194.8" y2="123.7" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="160.0" y1="184.0" x2="160.0" y2="196.0" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="80.00" cy="190.00" r="2.5" fill="#1f1f1f"/><circle cx="160.00" cy="51.44" r="2.5" fill="#1f1f1f"/><circle cx="240.00" cy="190.00" r="2.5" fill="#1f1f1f"/><circle cx="120.00" cy="120.72" r="2.5" fill="#1f1f1f"/>
  <text x="62.00" y="210.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text><text x="155.00" y="43.44" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text><text x="248.00" y="210.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="104.00" y="122.72" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">D</text>
</svg>"""

def generate_task():
    # Сторона равностороннего равна k·√3 → чевиана = 3k/2.
    # Берём чётное k, чтобы ответ был целым.
    k = random.choice([n for n in range(2, 61) if n % 2 == 0])
    side_text = f"{k}\\sqrt{{3}}"
    answer = str(3 * k // 2)

    element = random.choice(["median", "height", "bisector"])
    if element == "median":
        elem_acc = "медиану"     # винительный падеж — «Найдите медиану …»
        elem_seg = "CM"
        svg = SVG_EQ_MEDIAN
    elif element == "height":
        elem_acc = "высоту"
        elem_seg = "CH"
        svg = SVG_EQ_HEIGHT
    else:
        elem_acc = "биссектрису"
        elem_seg = "CD"
        svg = SVG_EQ_BISECTOR
    text = (
        f"Сторона равностороннего треугольника \\(ABC\\) равна "
        f"\\({side_text}\\). Найдите {elem_acc} \\({elem_seg}\\) "
        f"этого треугольника."
    )
    return {"condition_text": f"{text}<br><br>{svg}", "correct_answer": answer}
