# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=150: OGE16: G18 — ромб: диагональ + tg → r
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


# Тройки (m, n, h) такие, что tg(α/2) = m/n и √(m²+n²) = h (пифагорова тройка)
_PYTH_RHOMBUS = [
    (3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29),
]


def generate_task():
    """В ромбе ABCD AC = d (диагональ), tg угла BAC = m/n.
    AC — диагональ от A до C, делит угол A пополам.
    Тогда BM = (m/n)·AM, где M — центр (пересечение диагоналей), AM = d/2.
    BM = m·d/(2n) → BD = 2·BM = m·d/n.
    Сторона ромба AB = √(AM² + BM²) = (d/2)·√(1 + m²/n²) = (d/(2n))·√(n²+m²).
    Берём пифагорову тройку (m, n, h) ⇒ AB = d·h/(2n).
    Площадь S = AC·BD/2 = d·(m·d/n)/2 = m·d²/(2n).
    Полупериметр p = 2·AB = d·h/n.
    r = S/p = (m·d²/(2n)) / (d·h/n) = m·d/(2h).

    Чтобы r было целым, берём d = 2h·k. Тогда r = m·k.
    """
    m, n, h = random.choice(_PYTH_RHOMBUS)
    k = random.randint(1, 5)
    d_val = 2 * h * k
    r_val = m * k
    ask_text = (
        f"В ромбе \\(ABCD\\) диагональ \\(AC = {d_val}\\), а тангенс угла "
        f"\\(BAC\\) равен \\(\\dfrac{{{m}}}{{{n}}}\\). Найдите радиус "
        f"вписанной в этот ромб окружности."
    )
    answer = str(r_val)

    # Картинка: ромб с обеими диагоналями.
    # AC горизонтально, BD вертикально, пересекаются в центре.
    O_view = (160, 125)
    # Масштаб: AC в пикселях = 160, тогда BD = (m/n)·160? нет.
    # BD/AC = (m·d/n) / d = m/n. Возьмём AC_px = 160, BD_px = AC_px · m/n.
    AC_px = 180
    BD_px = AC_px * m / n
    # Если BD больше высоты viewBox — уменьшим.
    if BD_px > 170:
        scale = 170 / BD_px
        AC_px *= scale
        BD_px *= scale
    A = (O_view[0] - AC_px / 2, O_view[1])
    C = (O_view[0] + AC_px / 2, O_view[1])
    B = (O_view[0], O_view[1] - BD_px / 2)
    D = (O_view[0], O_view[1] + BD_px / 2)
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.3)  # диагональ AC
    # Угол при A между AB и AC
    body += _angle_arc(A, C, B, R=18, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 0), offset=12)
    body += _label_direction(B, "B", direction=(0, -1), offset=12)
    body += _label_direction(C, "C", direction=(1, 0), offset=12)
    body += _label_direction(D, "D", direction=(0, 1), offset=12)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(18)
    for i in range(5):
        t = generate_task()
        print(f"[G18 #{i+1}] answer = {t['correct_answer']}")
