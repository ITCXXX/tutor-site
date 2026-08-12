# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=197: OGE15: 03 — Углы через чевиану (простые)
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


SVG_HEIGHT_BH = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с высотой BH">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="200" y1="50" x2="200.00" y2="180.00" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="4,3"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="180.00" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="204.00" y="198.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">H</text>
</svg>"""
SVG_BISECTOR_AD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с биссектрисой AD">
  <polygon points="40,180 200,50 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="40" y1="180" x2="236.97" y2="110.07" stroke="#1f1f1f" stroke-width="1.3"/>
  <path d="M 54.0,168.6 A 18,18 0 0 1 57.0,174.0" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>
  <path d="M 68.3,170.0 A 30,30 0 0 1 70.0,180.0" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>
  <circle cx="40.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="200.00" cy="50.00" r="2.5" fill="#1f1f1f"/><circle cx="280.00" cy="180.00" r="2.5" fill="#1f1f1f"/><circle cx="236.97" cy="110.07" r="2.5" fill="#1f1f1f"/>
  <text x="22.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="195.00" y="42.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288.00" y="200.00" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="242.97" y="106.07" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">D</text>
</svg>"""

def generate_task():
    subtype = random.choice(["height", "bisector"])
    if subtype == "height":
        # Тип 5: BH высота, ∠BAC = α → ∠ABH = 90° − α.
        a = random.randint(5, 85)
        text = (
            f"В остроугольном треугольнике \\(ABC\\) проведена высота \\(BH\\), "
            f"\\(\\angle A = {a}°\\). Найдите угол \\(ABH\\). "
            f"Ответ дайте в градусах."
        )
        return {"condition_text": f"{text}<br><br>{SVG_HEIGHT_BH}", "correct_answer": str(90 - a)}
    else:
        # Тип 6: AD биссектриса, ∠BAC = α → ∠BAD = α/2.
        # Чтобы ∠BAD было целым, берём чётный угол.
        a = random.choice([n for n in range(10, 161) if n % 2 == 0])
        text = (
            f"В треугольнике \\(ABC\\) проведена биссектриса \\(AD\\), "
            f"\\(\\angle A = {a}°\\). Найдите угол \\(BAD\\). "
            f"Ответ дайте в градусах."
        )
        return {"condition_text": f"{text}<br><br>{SVG_BISECTOR_AD}", "correct_answer": str(a // 2)}
