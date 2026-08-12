# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=203: OGE15: 09 — Тригонометрия. Определение sin/cos/tg
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random
from math import gcd

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


def _ratio_str(p, q):
    # Возвращает строку либо "X" либо "X,Y" если деление даёт ≤ 1 знака после запятой.
    if q == 0:
        return None
    if (p * 10) % q != 0:
        return None
    v = round(p / q, 1)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}".replace(".", ",")


def generate_task():
    func = random.choice(["sin", "cos", "tg"])
    for _ in range(400):
        if func == "tg":
            ac = random.randint(1, 60)
            bc = random.randint(1, 60)
            if ac == bc:
                continue
            ans = _ratio_str(ac, bc)
            if ans is None:
                continue
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {bc}\\), \\(AC = {ac}\\). "
                f"Найдите \\(\\operatorname{{tg}}\\angle B\\)."
            )
            return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": ans}
        else:
            ab = random.randint(2, 100)
            leg = random.randint(1, ab - 1)
            ans = _ratio_str(leg, ab)
            if ans is None:
                continue
            if func == "sin":
                text = (
                    f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                    f"\\(AC = {leg}\\), \\(AB = {ab}\\). Найдите \\(\\sin\\angle B\\)."
                )
            else:
                text = (
                    f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                    f"\\(BC = {leg}\\), \\(AB = {ab}\\). Найдите \\(\\cos\\angle B\\)."
                )
            return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": ans}
    # запасной вариант
    return {"condition_text": f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                              f"\\(AC = 3\\), \\(AB = 5\\). Найдите \\(\\sin\\angle B\\)."
                              f"<br><br>{SVG_RIGHT_C}",
            "correct_answer": "0,6"}
