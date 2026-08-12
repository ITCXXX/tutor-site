# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=198: OGE15: 04 — Углы через чевиану (многоходовая)
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


SVG_BISECTOR_AK_EQ = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с биссектрисой AK, AK равно KC">
  <polygon points="40,180 100.00,76.08 280,180" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="40" y1="180" x2="160.00" y2="110.72" stroke="#1f1f1f" stroke-width="1.3"/>
  <path d="M 49.0,164.4 A 18,18 0 0 1 55.6,171.0" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>
  <path d="M 66.0,165.0 A 30,30 0 0 1 70.0,180.0" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>
  <line x1="97.0" y1="140.2" x2="103.0" y2="150.6" stroke="#1f1f1f" stroke-width="1.4"/>
  <line x1="223.0" y1="140.2" x2="217.0" y2="150.6" stroke="#1f1f1f" stroke-width="1.4"/>
  <circle cx="40" cy="180" r="2.5" fill="#1f1f1f"/>
  <circle cx="100.00" cy="76.08" r="2.5" fill="#1f1f1f"/>
  <circle cx="280" cy="180" r="2.5" fill="#1f1f1f"/>
  <circle cx="160.00" cy="110.72" r="2.5" fill="#1f1f1f"/>
  <text x="22" y="200" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="86.00" y="72.08" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288" y="200" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="166.00" y="105.72" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">K</text>
</svg>"""

def generate_task():
    # Тип 8: AK — биссектриса ∠BAC, AK = CK.
    # AK=KC ⇒ △AKC равнобедр. ⇒ ∠KAC = ∠C.
    # AK биссектриса ⇒ ∠BAC = 2·∠KAC = 2·∠C.
    # Сумма углов: ∠B = 180 − 3·∠C.
    # Берём ∠C так, чтобы 3·∠C < 180 и не давал тривиальных значений.
    angC = random.randint(10, 59)
    angB = 180 - 3 * angC
    text = (
        f"В треугольнике \\(ABC\\) проведена биссектриса \\(AK\\), причём "
        f"\\(AK = CK\\), \\(\\angle C = {angC}°\\). "
        f"Найдите угол \\(B\\). Ответ дайте в градусах."
    )
    return {"condition_text": f"{text}<br><br>{SVG_BISECTOR_AK_EQ}", "correct_answer": str(angB)}
