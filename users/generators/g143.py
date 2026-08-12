# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=143: OGE16: G11 — R описанной около прямоуг. треугольника
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import math
import random


# ─── Базовые геометрические хелперы ──────────────────────────────────────────

def _midpoint(P1, P2):
    return ((P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2)


def _angle_arc(vertex, P1, P2, label_text="", R=22, label_offset=16,
               arcs=1, arc_gap=4, font_size=13):
    """Дуга в углу vertex между лучами на P1 и P2 + опционально подпись.
    R адаптивно ограничен 32% длины меньшей соседней стороны."""
    vx, vy = vertex
    a1 = math.atan2(P1[1] - vy, P1[0] - vx)
    a2 = math.atan2(P2[1] - vy, P2[0] - vx)
    da = a2 - a1
    while da > math.pi:
        da -= 2 * math.pi
    while da < -math.pi:
        da += 2 * math.pi
    sweep = 1 if da > 0 else 0
    am = a1 + da / 2

    L1 = math.hypot(P1[0] - vx, P1[1] - vy)
    L2 = math.hypot(P2[0] - vx, P2[1] - vy)
    R = max(10, min(R, min(L1, L2) * 0.32))
    if abs(da) < math.radians(25):
        R = min(R, 16)

    out = []
    for i in range(arcs):
        r = R - i * arc_gap
        if r < 6:
            break
        x1 = vx + r * math.cos(a1)
        y1 = vy + r * math.sin(a1)
        x2 = vx + r * math.cos(a2)
        y2 = vy + r * math.sin(a2)
        out.append(
            f'<path d="M {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 0 {sweep} '
            f'{x2:.1f} {y2:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>'
        )
    if label_text:
        Lx = vx + (R + label_offset) * math.cos(am)
        Ly = vy + (R + label_offset) * math.sin(am) + 5
        out.append(
            f'<text x="{Lx:.1f}" y="{Ly:.1f}" font-family="Cambria, Georgia, serif" '
            f'font-size="{font_size}" fill="#1f1f1f" text-anchor="middle">{label_text}</text>'
        )
    return "".join(out)


def _vertex_dot(P, r=2.5):
    return f'<circle cx="{P[0]:.1f}" cy="{P[1]:.1f}" r="{r}" fill="#1f1f1f"/>'


def _segment(P1, P2, dashed=False, width=1.5):
    da = ' stroke-dasharray="4,3"' if dashed else ''
    return (
        f'<line x1="{P1[0]:.1f}" y1="{P1[1]:.1f}" x2="{P2[0]:.1f}" y2="{P2[1]:.1f}" '
        f'stroke="#1f1f1f" stroke-width="{width}"{da}/>'
    )


# ─── Хелперы для окружностей ─────────────────────────────────────────────────

def _circle(C, R, stroke_width=1.5):
    cx, cy = C
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R:.1f}" '
            f'fill="none" stroke="#1f1f1f" stroke-width="{stroke_width}"/>')


def _pt_on_circle(C, R, angle_deg):
    """Точка на окружности. 0° — справа, 90° — сверху (CCW в матем. смысле,
    с учётом инверсии Y в SVG)."""
    a = math.radians(angle_deg)
    return (C[0] + R * math.cos(a), C[1] - R * math.sin(a))


def _label_radial(P, name, center, offset=14, font_size=16, italic=True):
    """Подпись точки на окружности — радиально наружу от центра."""
    px, py = P
    cx, cy = center
    dx, dy = px - cx, py - cy
    L = math.hypot(dx, dy)
    if L < 1e-9:
        ox, oy = 0, -10
    else:
        ox = dx / L * offset
        oy = dy / L * offset
    style = "font-style:italic;" if italic else ""
    return (
        f'<text x="{px + ox:.1f}" y="{py + oy + 5:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="{font_size}" '
        f'fill="#1f1f1f" text-anchor="middle" style="{style}">{name}</text>'
    )


def _label_direction(P, name, direction, offset=14, font_size=15, italic=True):
    """Подпись точки в заданном направлении."""
    dl = math.hypot(direction[0], direction[1])
    if dl < 1e-9:
        dx, dy = 0, 1
    else:
        dx, dy = direction[0] / dl, direction[1] / dl
    lx = P[0] + dx * offset
    ly = P[1] + dy * offset + 5
    style = "font-style:italic;" if italic else ""
    return (
        f'<text x="{lx:.1f}" y="{ly:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="{font_size}" '
        f'fill="#1f1f1f" text-anchor="middle" style="{style}">{name}</text>'
    )


def _ans(x):
    """Форматирует число как ответ: '7' или '7,5'."""
    if x == int(x):
        return str(int(x))
    return f"{x:.1f}".replace(".", ",")


def _svg_wrap(body, w=320, h=240):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="Окружность" '
        f'style="display:block;margin:0.5em auto">{body}</svg>'
    )


_PYTH_G11 = []
for _m in range(2, 15):
    for _n in range(1, _m):
        if (_m - _n) % 2 == 1 and math.gcd(_m, _n) == 1:
            _a0 = _m * _m - _n * _n
            _b0 = 2 * _m * _n
            _c0 = _m * _m + _n * _n
            for _k in range(1, 101):
                if _c0 * _k > 100:
                    break
                _PYTH_G11.append((sorted([_a0 * _k, _b0 * _k])[0],
                                  sorted([_a0 * _k, _b0 * _k])[1],
                                  _c0 * _k))


def generate_task():
    """R описанной около прямоугольного треугольника = c/2.
    Подтипы:
      - 'legs': даны два катета (пифагорова тройка) → R
      - 'leg_hyp': дан катет и гипотенуза (катет < c, произвольные) → R
      - 'hyp_only': дана только гипотенуза → R = c/2
      - 'inverse': дан R → c = 2R
    """
    subtype = random.choice(['legs', 'leg_hyp', 'hyp_only', 'inverse'])

    if subtype == 'legs':
        a, b, c = random.choice(_PYTH_G11)
        if random.random() < 0.5:
            AC, BC = a, b
        else:
            AC, BC = b, a
        ask_text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AC = {AC}\\), \\(BC = {BC}\\). Найдите радиус описанной "
            f"около этого треугольника окружности."
        )
        R_val = c / 2
        answer = _ans(R_val)

    elif subtype == 'leg_hyp':
        # Произвольные: c ∈ [6, 50] (чётное чтобы R целое), катет < c.
        c = random.choice([n for n in range(6, 51) if n % 2 == 0])
        leg = random.randint(2, c - 1)
        AC, BC = c, leg  # неважно, какой именно катет упомянут (катет = leg)
        which_leg = random.choice(['AC', 'BC'])
        if which_leg == 'AC':
            ask_text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(AC = {leg}\\), \\(AB = {c}\\). Найдите радиус описанной "
                f"около этого треугольника окружности."
            )
        else:
            ask_text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {leg}\\), \\(AB = {c}\\). Найдите радиус описанной "
                f"около этого треугольника окружности."
            )
        answer = _ans(c / 2)
        AC, BC = leg, math.sqrt(c * c - leg * leg)  # для рисунка

    elif subtype == 'hyp_only':
        c = random.choice([n for n in range(4, 51) if n % 2 == 0])
        ask_text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AB = {c}\\). Найдите радиус описанной около этого "
            f"треугольника окружности."
        )
        answer = _ans(c / 2)
        # Для рисунка — произвольный острый угол
        ang = random.randint(25, 65)
        AC = c * math.cos(math.radians(ang))
        BC = c * math.sin(math.radians(ang))

    else:  # inverse
        R_val = random.randint(2, 30)
        ask_text = (
            f"Радиус описанной около прямоугольного треугольника окружности "
            f"равен \\({R_val}\\). Найдите гипотенузу этого треугольника."
        )
        answer = str(2 * R_val)
        # Для рисунка
        c = 2 * R_val
        ang = random.randint(25, 65)
        AC = c * math.cos(math.radians(ang))
        BC = c * math.sin(math.radians(ang))

    # Картинка: окружность с диаметром AB, C на верхней полуокружности.
    # Центр O НЕ показываем.
    O = (160, 130)
    R_px = 78
    A = _pt_on_circle(O, R_px, 180)
    B = _pt_on_circle(O, R_px, 0)
    angA_deg = math.degrees(math.atan2(BC, AC)) if AC > 0 else 45
    C = _pt_on_circle(O, R_px, 2 * angA_deg)

    body = _circle(O, R_px)
    body += _segment(A, B) + _segment(A, C) + _segment(B, C)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(11)
    for i in range(5):
        t = generate_task()
        print(f"[G11 #{i+1}] answer = {t['correct_answer']}")
