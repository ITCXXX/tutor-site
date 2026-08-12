# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=204: OGE15: 10 — Тригонометрия. Найти сторону
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
            p_raw = random.randint(1, 15)
            q_raw = random.randint(1, 15)
        else:
            q_raw = random.randint(2, 12)
            p_raw = random.randint(1, q_raw - 1)
        g = gcd(p_raw, q_raw)
        p, q = p_raw // g, q_raw // g
        if p == q:
            continue
        step = q // gcd(10, q)
        candidates = [m * step for m in range(1, 21) if 2 <= m * step <= 80]
        if not candidates:
            continue
        K = random.choice(candidates)
        target = _ratio_str(K * p, q)
        if target is None:
            continue
        if func == "sin":
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\sin\\angle B = \\dfrac{{{p}}}{{{q}}}\\), \\(AB = {K}\\). "
                f"Найдите \\(AC\\)."
            )
        elif func == "cos":
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\cos\\angle B = \\dfrac{{{p}}}{{{q}}}\\), \\(AB = {K}\\). "
                f"Найдите \\(BC\\)."
            )
        else:
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\operatorname{{tg}}\\angle B = \\dfrac{{{p}}}{{{q}}}\\), "
                f"\\(BC = {K}\\). Найдите \\(AC\\)."
            )
        return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": target}
    return {"condition_text": f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                              f"\\(\\sin\\angle B = \\dfrac{{3}}{{5}}\\), \\(AB = 25\\). "
                              f"Найдите \\(AC\\).<br><br>{SVG_RIGHT_C}",
            "correct_answer": "15"}
