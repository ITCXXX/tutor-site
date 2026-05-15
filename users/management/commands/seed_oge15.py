# -*- coding: utf-8 -*-
"""
Management command: создаёт ProblemGenerator-ы и Assignment-ы под урок
«Задание 15» курса ОГЭ. Тема — «Треугольники».

Архитектура (после анализа Школково /catalog/7154, 27 типов):
    G1. ANGLES_SUM       — сумма углов (Типы 1, 2, 4)
    G2. ANGLES_SPECIAL   — равнобедр. / высота / биссектриса (Типы 3, 5, 6)
    G3. MEDIAN_SPECIAL   — медиана и спец. комбинации (Типы 7, 8, 9)
    (далее G4-G8 — будет добавлено после проверки)

Стиль рисунков: ФИПИ-подобный.
    - viewBox 0 0 320 220
    - чёрный stroke #1f1f1f, толщина 1.5
    - шрифт Cambria/Georgia italic 15pt для подписей
    - кружочки r=2.5 на вершинах
    - засечки равенства, маркеры прямого угла, дуги для углов

Usage:
    python manage.py seed_oge15
    python manage.py seed_oge15 --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# PLOTTER — общие SVG-хелперы для треугольников
# ──────────────────────────────────────────────────────────────────────────────

PLOTTER = r'''
import math
import random


# ─── Базовые геометрические хелперы ──────────────────────────────────────────

def _midpoint(P1, P2):
    return ((P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2)


def _foot_of_perp(P, A, B):
    """Проекция точки P на прямую AB."""
    ax, ay = A; bx, by = B
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return A
    t = ((P[0] - ax) * dx + (P[1] - ay) * dy) / L2
    return (ax + t * dx, ay + t * dy)


def _equality_marks(P1, P2, count=1, length=8, gap=4):
    """count перпендикулярных штрихов на середине отрезка P1P2."""
    Mx = (P1[0] + P2[0]) / 2
    My = (P1[1] + P2[1]) / 2
    dx, dy = P2[0] - P1[0], P2[1] - P1[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return ""
    nx, ny = dy / L, -dx / L
    ux, uy = dx / L, dy / L
    h = length / 2
    if count == 1:
        offsets = [0]
    else:
        offsets = [gap * (i - (count - 1) / 2) for i in range(count)]
    parts = []
    for off in offsets:
        cx = Mx + off * ux
        cy = My + off * uy
        parts.append(
            f'<line x1="{cx - nx*h:.1f}" y1="{cy - ny*h:.1f}" '
            f'x2="{cx + nx*h:.1f}" y2="{cy + ny*h:.1f}" '
            f'stroke="#1f1f1f" stroke-width="1.4"/>'
        )
    return "".join(parts)


def _right_angle_marker(vertex, P1, P2, size=10):
    """Маркер прямого угла в vertex (квадратик по сторонам угла)."""
    vx, vy = vertex
    d1x, d1y = P1[0] - vx, P1[1] - vy
    d2x, d2y = P2[0] - vx, P2[1] - vy
    L1 = math.hypot(d1x, d1y)
    L2 = math.hypot(d2x, d2y)
    if L1 < 1e-9 or L2 < 1e-9:
        return ""
    u1x, u1y = d1x / L1 * size, d1y / L1 * size
    u2x, u2y = d2x / L2 * size, d2y / L2 * size
    a = (vx + u1x, vy + u1y)
    b = (vx + u1x + u2x, vy + u1y + u2y)
    c = (vx + u2x, vy + u2y)
    return (
        f'<polyline points="{a[0]:.1f},{a[1]:.1f} {b[0]:.1f},{b[1]:.1f} '
        f'{c[0]:.1f},{c[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )


def _angle_arc(vertex, P1, P2, label_text="", R=22, label_offset=16, arcs=1, arc_gap=4):
    """Дуга в углу vertex между лучами на P1 и P2 + опционально подпись.
    Подпись на биссектрисе короткой дуги. R адаптивно уменьшается до 32%
    меньшей соседней стороны."""
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
            f'font-size="13" fill="#1f1f1f" text-anchor="middle">{label_text}</text>'
        )
    return "".join(out)


def _vertex_label(P, name, P1, P2, offset=14):
    """Подпись вершины P снаружи (противоположно центру треугольника)."""
    vx, vy = P
    cx = (P1[0] + P2[0]) / 2
    cy = (P1[1] + P2[1]) / 2
    dx = vx - cx
    dy = vy - cy
    L = math.hypot(dx, dy)
    if L < 1e-9:
        ox, oy = 0, -10
    else:
        ox = dx / L * offset
        oy = dy / L * offset
    return (
        f'<text x="{vx + ox:.1f}" y="{vy + oy + 5:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-style="italic" font-size="16" '
        f'fill="#1f1f1f" text-anchor="middle">{name}</text>'
    )


def _vertex_dot(P, r=2.5):
    return f'<circle cx="{P[0]:.1f}" cy="{P[1]:.1f}" r="{r}" fill="#1f1f1f"/>'


def _side(P1, P2, dashed=False, width=1.5):
    da = ' stroke-dasharray="4,3"' if dashed else ''
    return (
        f'<line x1="{P1[0]:.1f}" y1="{P1[1]:.1f}" x2="{P2[0]:.1f}" y2="{P2[1]:.1f}" '
        f'stroke="#1f1f1f" stroke-width="{width}"{da}/>'
    )


def _dashed_segment(P1, P2, width=1.3):
    """Штриховой отрезок."""
    return (
        f'<line x1="{P1[0]:.1f}" y1="{P1[1]:.1f}" x2="{P2[0]:.1f}" y2="{P2[1]:.1f}" '
        f'stroke="#1f1f1f" stroke-width="{width}" stroke-dasharray="5,3"/>'
    )


def _side_label(P1, P2, text, away_from=None, offset=14, font_size=13, italic=False):
    """Подпись посередине отрезка P1P2 снаружи (нормаль прочь от away_from)."""
    Mx = (P1[0] + P2[0]) / 2
    My = (P1[1] + P2[1]) / 2
    dx, dy = P2[0] - P1[0], P2[1] - P1[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return ""
    nx, ny = -dy / L, dx / L
    if away_from is not None:
        if nx * (away_from[0] - Mx) + ny * (away_from[1] - My) > 0:
            nx, ny = -nx, -ny
    lx = Mx + nx * offset
    ly = My + ny * offset + 5
    style = "font-style:italic;" if italic else ""
    return (
        f'<text x="{lx:.1f}" y="{ly:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="{font_size}" '
        f'fill="#1f1f1f" text-anchor="middle" style="{style}">{text}</text>'
    )


def _point_label(P, name, direction=(0, 1), offset=16, font_size=15):
    """Подпись точки в заданном направлении (по умолчанию — вниз)."""
    dl = math.hypot(direction[0], direction[1])
    if dl < 1e-9:
        dx, dy = 0, 1
    else:
        dx, dy = direction[0] / dl, direction[1] / dl
    lx = P[0] + dx * offset
    ly = P[1] + dy * offset + 5
    return (
        f'<text x="{lx:.1f}" y="{ly:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-style="italic" '
        f'font-size="{font_size}" fill="#1f1f1f" text-anchor="middle">{name}</text>'
    )


def _ans(x):
    """Форматирует число как ответ: '7' или '7,5'."""
    if x == int(x):
        return str(int(x))
    return f"{x:.1f}".replace(".", ",")


def _ratio_1dp(num, den):
    """Преобразует num/den в строку с ≤1 знаком после запятой.
    Возвращает None, если число не может быть точно представлено в этом виде
    (например, 3/4 = 0,75 — два знака → None)."""
    from fractions import Fraction
    f = Fraction(num, den)
    n, d = f.numerator, f.denominator
    if d == 1:
        return str(n)
    if 10 % d != 0:
        return None
    scaled = n * (10 // d)
    sign = '-' if scaled < 0 else ''
    s = abs(scaled)
    ip, dp = divmod(s, 10)
    return f"{sign}{ip},{dp}" if dp else f"{sign}{ip}"


# ─── Расчёт координат треугольника ───────────────────────────────────────────

def triangle_by_angles(angle_A_deg, angle_B_deg, AB_px=200, A=(60, 180)):
    """A=левый низ, B=правый низ, C=вершина."""
    aA = math.radians(angle_A_deg)
    aB = math.radians(angle_B_deg)
    aC = math.pi - aA - aB
    Ax, Ay = A
    Bx = Ax + AB_px
    By = Ay
    AC = AB_px * math.sin(aB) / math.sin(aC)
    Cx = Ax + AC * math.cos(aA)
    Cy = Ay - AC * math.sin(aA)
    return (Ax, Ay), (Bx, By), (Cx, Cy)


def fit_triangle(angle_A_deg, angle_B_deg, viewport=(320, 220),
                 margin_top=28, margin_bot=32, margin_lr=42):
    """Возвращает (A, B, C) с гарантией что треугольник помещается в viewport.
    AB горизонтально снизу, C — вершина."""
    aA = math.radians(angle_A_deg)
    aB = math.radians(angle_B_deg)
    aC = math.pi - aA - aB
    if aC <= 0.01:
        raise ValueError(f"invalid triangle angles: A={angle_A_deg}, B={angle_B_deg}")
    AC_u = math.sin(aB) / math.sin(aC)
    Cx_u = AC_u * math.cos(aA)
    Cy_u = AC_u * math.sin(aA)
    minx_u = min(0.0, Cx_u)
    maxx_u = max(1.0, Cx_u)
    w_u = maxx_u - minx_u
    h_u = Cy_u
    avail_w = viewport[0] - 2 * margin_lr
    avail_h = viewport[1] - margin_top - margin_bot
    scale = min(avail_w / w_u, avail_h / h_u)
    AB_screen_y = viewport[1] - margin_bot
    left_screen = (viewport[0] - w_u * scale) / 2
    Ax = left_screen + (0 - minx_u) * scale
    Bx = Ax + scale
    Cx_s = Ax + Cx_u * scale
    Cy_s = AB_screen_y - Cy_u * scale
    return (Ax, AB_screen_y), (Bx, AB_screen_y), (Cx_s, Cy_s)


def fit_right_triangle(AC_units, BC_units, viewport=(320, 220),
                       margin_top=28, margin_bot=32, margin_lr=42):
    """Прямоугольный треугольник с прямым углом при C, заданным соотношением катетов."""
    angA = math.degrees(math.atan2(BC_units, AC_units))
    angB = 90 - angA
    return fit_triangle(angA, angB, viewport=viewport,
                        margin_top=margin_top, margin_bot=margin_bot, margin_lr=margin_lr)


def fit_equilateral(viewport=(320, 220), margin_top=28, margin_bot=32, margin_lr=50):
    """Равносторонний треугольник."""
    return fit_triangle(60, 60, viewport=viewport,
                        margin_top=margin_top, margin_bot=margin_bot, margin_lr=margin_lr)


# ─── Базовый SVG-обёртка ─────────────────────────────────────────────────────

def _svg_wrap(body, w=320, h=220):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="Треугольник" '
        f'style="display:block;margin:0.5em auto">{body}</svg>'
    )


def render_triangle(A, B, C, labels=("A", "B", "C"), extras="", w=320, h=220):
    """3 стороны + вершины + подписи + extras."""
    return _svg_wrap(
        _side(A, B) + _side(B, C) + _side(A, C) +
        _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) +
        _vertex_label(A, labels[0], B, C) +
        _vertex_label(B, labels[1], A, C) +
        _vertex_label(C, labels[2], A, B) +
        extras,
        w, h,
    )
'''


# ──────────────────────────────────────────────────────────────────────────────
# G1: ANGLES_SUM — сумма углов треугольника (Типы 1, 2, 4)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G1 = PLOTTER + r'''

def generate_task():
    """Сумма углов: 3-й угол / прямоуг. треуг. (другой острый) / внешний угол."""
    subtype = random.choice(['third_angle', 'right_other', 'external'])

    if subtype == 'third_angle':
        # Тип 1: два угла известны, найти третий
        while True:
            a = random.randint(10, 160)
            b = random.randint(10, 160)
            c = 180 - a - b
            if 10 <= c <= 160:
                break
        A, B, C = fit_triangle(a, b)
        extras = (
            _angle_arc(A, B, C, label_text=f"{a}°", R=26) +
            _angle_arc(B, A, C, label_text=f"{b}°", R=26)
        )
        svg = render_triangle(A, B, C, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(\\angle A = {a}°\\), "
            f"\\(\\angle B = {b}°\\). Найдите \\(\\angle C\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(c)

    elif subtype == 'right_other':
        # Тип 2: прямоугольный треугольник, известен один острый угол
        a = random.choice([n for n in range(5, 86) if n != 45])
        b = 90 - a
        A, B, C = fit_triangle(a, 90)
        extras = (
            _angle_arc(A, B, C, label_text=f"{a}°", R=24) +
            _right_angle_marker(B, A, C, size=11)
        )
        svg = render_triangle(A, B, C, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(B\\) равен \\(90°\\), "
            f"\\(\\angle A = {a}°\\). Найдите \\(\\angle C\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(b)

    else:
        # Тип 4: внешний угол при C = 180° − ∠C
        c = random.randint(10, 170)
        rem = 180 - c
        if rem >= 20:
            a = random.randint(10, rem - 10)
        else:
            a = rem // 2
        b = rem - a
        if a < 5 or b < 5:
            a = rem // 2
            b = rem - a
        A, B, C = fit_triangle(a, b)
        ax, ay = A; cx, cy = C
        dx, dy = cx - ax, cy - ay
        L = math.hypot(dx, dy)
        ext_len = min(60, L * 0.40)
        ex = cx + dx / L * ext_len
        ey = cy + dy / L * ext_len
        ext_line = (
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="#1f1f1f" stroke-width="1.3" stroke-dasharray="5,3"/>'
        )
        arc_internal = _angle_arc(C, A, B, label_text=f"{c}°", R=22)
        arc_external = _angle_arc(C, B, (ex, ey), R=20)
        extras = arc_internal + ext_line + arc_external
        svg = render_triangle(A, B, C, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\({c}°\\). "
            f"Найдите внешний угол при вершине \\(C\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(180 - c)

    cond = f"{text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(1)
    for i in range(3):
        t = generate_task()
        print(f"[G1 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G2: ANGLES_SPECIAL — равнобедр. / высота / биссектриса (Типы 3, 5, 6)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G2 = PLOTTER + r'''

def generate_task():
    """Равнобедр. / высота / биссектриса."""
    subtype = random.choice(['isosceles', 'height', 'bisector'])

    if subtype == 'isosceles':
        # Тип 3: AB=BC, известен ∠B (apex), найти ∠A = (180−∠B)/2
        apex = random.randint(10, 170)
        base_ang = (180 - apex) / 2
        Av, Cv, Bv = fit_triangle(base_ang, base_ang)
        marks = _equality_marks(Av, Bv) + _equality_marks(Bv, Cv)
        arc = _angle_arc(Bv, Av, Cv, label_text=f"{apex}°", R=26)
        svg = render_triangle(Av, Bv, Cv, labels=("A", "B", "C"), extras=marks + arc)
        text = (
            f"В треугольнике \\(ABC\\) \\(AB = BC\\), \\(\\angle B = {apex}°\\). "
            f"Найдите \\(\\angle A\\). Ответ дайте в градусах."
        )
        answer = _ans(base_ang)

    elif subtype == 'height':
        # Тип 5: BH высота из B на AC, ∠BAC задан, ∠ABH = 90° − ∠BAC
        angBAC = random.randint(5, 85)
        # angC выбираем так, чтобы треугольник был остроугольным
        # (angB ∈ (0, 90), angC ∈ (0, 90))
        max_C = min(89, 180 - angBAC - 5)
        min_C = max(5, 90 - angBAC + 5)
        if min_C > max_C:
            angC = (180 - angBAC) // 2
        else:
            angC = random.randint(min_C, max_C)
        angB = 180 - angBAC - angC
        Av, Cv, Bv = fit_triangle(angBAC, angC)
        H = _foot_of_perp(Bv, Av, Cv)
        height_line = _side(Bv, H, width=1.3)
        right_mark = _right_angle_marker(H, Av, Bv, size=9)
        arc_A = _angle_arc(Av, Bv, Cv, label_text=f"{angBAC}°", R=22)
        H_dot = _vertex_dot(H)
        ac_dx = Cv[0] - Av[0]
        ac_dy = Cv[1] - Av[1]
        ac_L = math.hypot(ac_dx, ac_dy)
        nx, ny = -ac_dy / ac_L, ac_dx / ac_L
        if nx * (Bv[0] - H[0]) + ny * (Bv[1] - H[1]) > 0:
            nx, ny = -nx, -ny
        H_lab = _point_label(H, "H", direction=(nx, ny), offset=16)
        extras = height_line + right_mark + arc_A + H_dot + H_lab
        svg = render_triangle(Av, Bv, Cv, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В остроугольном треугольнике \\(ABC\\) проведена высота \\(BH\\), "
            f"\\(\\angle BAC = {angBAC}°\\). Найдите \\(\\angle ABH\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(90 - angBAC)

    else:
        # Тип 6: AD биссектриса, ∠BAC задан, ∠BAD = ∠BAC/2
        angA = random.randint(10, 170)
        remaining = 180 - angA
        if remaining < 20:
            angC = remaining // 2
        else:
            angC = random.randint(10, remaining - 10)
        angB = remaining - angC
        Av, Cv, Bv = fit_triangle(angA, angC)
        AB_len = math.hypot(Bv[0] - Av[0], Bv[1] - Av[1])
        AC_len = math.hypot(Cv[0] - Av[0], Cv[1] - Av[1])
        t_d = AB_len / (AB_len + AC_len)
        D = (Bv[0] + (Cv[0] - Bv[0]) * t_d, Bv[1] + (Cv[1] - Bv[1]) * t_d)
        bis_line = _side(Av, D, width=1.3)
        arc_BAD = _angle_arc(Av, Bv, D, R=16, label_text="")
        arc_DAC = _angle_arc(Av, D, Cv, R=16, label_text="")
        # Подпись общего ∠BAC снаружи через биссектрису
        mx, my = (Bv[0] + Cv[0]) / 2, (Bv[1] + Cv[1]) / 2
        bisdx, bisdy = mx - Av[0], my - Av[1]
        bisL = math.hypot(bisdx, bisdy)
        Lx = Av[0] + bisdx / bisL * 38
        Ly = Av[1] + bisdy / bisL * 38 + 5
        label_BAC = (
            f'<text x="{Lx:.1f}" y="{Ly:.1f}" font-family="Cambria, Georgia, serif" '
            f'font-size="13" fill="#1f1f1f" text-anchor="middle">{angA}°</text>'
        )
        bc_dx = Cv[0] - Bv[0]
        bc_dy = Cv[1] - Bv[1]
        bc_L = math.hypot(bc_dx, bc_dy)
        nx_d, ny_d = -bc_dy / bc_L, bc_dx / bc_L
        if nx_d * (Av[0] - D[0]) + ny_d * (Av[1] - D[1]) > 0:
            nx_d, ny_d = -nx_d, -ny_d
        D_dot = _vertex_dot(D)
        D_lab = _point_label(D, "D", direction=(nx_d, ny_d), offset=14)
        extras = bis_line + arc_BAD + arc_DAC + label_BAC + D_dot + D_lab
        svg = render_triangle(Av, Bv, Cv, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(\\angle BAC = {angA}°\\), "
            f"\\(AD\\) — биссектриса. Найдите \\(\\angle BAD\\). "
            f"Ответ дайте в градусах."
        )
        answer = _ans(angA / 2)

    cond = f"{text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(2)
    for i in range(3):
        t = generate_task()
        print(f"[G2 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G3: MEDIAN + SPECIAL_ANGLES (Типы 7, 8, 9)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G3 = PLOTTER + r'''

def generate_task():
    """G3: медиана и спец. комбинации (Типы 7, 8, 9)."""
    subtype = random.choice(['median_half', 'bisector_isosceles', 'median_circumcenter'])

    if subtype == 'median_half':
        # Тип 7: BM — медиана, AC задан, AM = AC/2
        AC_val = random.randint(2, 200)
        angA = random.randint(25, 80)
        angB = random.randint(25, 80)
        if angA + angB > 150:
            angA, angB = 50, 60
        A, B, C = fit_triangle(angA, angB)
        M = _midpoint(A, C)
        BM_line = _side(B, M, width=1.3)
        marks_AM = _equality_marks(A, M, count=1)
        marks_MC = _equality_marks(M, C, count=1)
        ac_label = _side_label(A, C, str(AC_val), away_from=B, offset=14)
        ac_dx = C[0] - A[0]; ac_dy = C[1] - A[1]
        ac_L = math.hypot(ac_dx, ac_dy)
        nx, ny = -ac_dy / ac_L, ac_dx / ac_L
        if nx * (B[0] - M[0]) + ny * (B[1] - M[1]) > 0:
            nx, ny = -nx, -ny
        M_dot = _vertex_dot(M)
        M_lab = _point_label(M, "M", direction=(nx, ny), offset=15)
        extras = BM_line + marks_AM + marks_MC + ac_label + M_dot + M_lab
        svg = render_triangle(A, B, C, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(BM\\) — медиана, "
            f"\\(AC = {AC_val}\\). Найдите \\(AM\\)."
        )
        answer = _ans(AC_val / 2)

    elif subtype == 'bisector_isosceles':
        # Тип 8: AK биссектриса, AK=CK, ∠C задан, ∠B = 180 − 3∠C
        angC = random.randint(2, 59)
        angBAC = 2 * angC
        angB = 180 - angBAC - angC
        Av, Cv, Bv = fit_triangle(angBAC, angC)
        AB_len = math.hypot(Bv[0] - Av[0], Bv[1] - Av[1])
        AC_len = math.hypot(Cv[0] - Av[0], Cv[1] - Av[1])
        t_k = AB_len / (AB_len + AC_len)
        K = (Bv[0] + (Cv[0] - Bv[0]) * t_k, Bv[1] + (Cv[1] - Bv[1]) * t_k)
        AK_line = _side(Av, K, width=1.3)
        marks_AK = _equality_marks(Av, K, count=1)
        marks_KC = _equality_marks(K, Cv, count=1)
        arc_BAK = _angle_arc(Av, Bv, K, R=16, label_text="")
        arc_KAC = _angle_arc(Av, K, Cv, R=16, label_text="")
        arc_C = _angle_arc(Cv, Bv, Av, R=22, label_text=f"{angC}°")
        bc_dx = Cv[0] - Bv[0]; bc_dy = Cv[1] - Bv[1]
        bc_L = math.hypot(bc_dx, bc_dy)
        nx, ny = -bc_dy / bc_L, bc_dx / bc_L
        if nx * (Av[0] - K[0]) + ny * (Av[1] - K[1]) > 0:
            nx, ny = -nx, -ny
        K_dot = _vertex_dot(K)
        K_lab = _point_label(K, "K", direction=(nx, ny), offset=15)
        extras = AK_line + marks_AK + marks_KC + arc_BAK + arc_KAC + arc_C + K_dot + K_lab
        svg = render_triangle(Av, Bv, Cv, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) проведена биссектриса \\(AK\\), при этом "
            f"\\(AK = CK\\), \\(\\angle C = {angC}°\\). "
            f"Найдите градусную меру угла \\(B\\). Ответ дайте в градусах."
        )
        answer = str(angB)

    else:
        # Тип 9: BM медиана, BM=AM=MC, ∠C задан → треугольник прямоуг. при B, ∠A=90°−∠C
        angC = random.randint(1, 89)
        angA = 90 - angC
        Av, Cv, Bv = fit_triangle(angA, angC)
        M = _midpoint(Av, Cv)
        BM_line = _side(Bv, M, width=1.3)
        marks_AM = _equality_marks(Av, M, count=2)
        marks_MC = _equality_marks(M, Cv, count=2)
        marks_BM = _equality_marks(Bv, M, count=2)
        arc_C = _angle_arc(Cv, Av, Bv, R=22, label_text=f"{angC}°")
        ac_dx = Cv[0] - Av[0]; ac_dy = Cv[1] - Av[1]
        ac_L = math.hypot(ac_dx, ac_dy)
        nx, ny = -ac_dy / ac_L, ac_dx / ac_L
        if nx * (Bv[0] - M[0]) + ny * (Bv[1] - M[1]) > 0:
            nx, ny = -nx, -ny
        M_dot = _vertex_dot(M)
        M_lab = _point_label(M, "M", direction=(nx, ny), offset=15)
        extras = BM_line + marks_AM + marks_MC + marks_BM + arc_C + M_dot + M_lab
        svg = render_triangle(Av, Bv, Cv, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) проведена медиана \\(BM\\), при этом "
            f"\\(BM = AM = MC\\), \\(\\angle C = {angC}°\\). "
            f"Найдите градусную меру угла \\(A\\). Ответ дайте в градусах."
        )
        answer = str(angA)

    cond = f"{text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(3)
    for i in range(3):
        t = generate_task()
        print(f"[G3 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G4: PYTHAGORAS (Типы 10, 11)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G4 = PLOTTER + r'''

PYTH_TRIPLES = [
    (3, 4, 5),
    (5, 12, 13),
    (6, 8, 10),
    (7, 24, 25),
    (8, 15, 17),
    (9, 12, 15),
    (9, 40, 41),
    (10, 24, 26),
    (11, 60, 61),
    (12, 16, 20),
    (12, 35, 37),
    (13, 84, 85),
    (14, 48, 50),
    (15, 20, 25),
    (15, 36, 39),
    (16, 30, 34),
    (16, 63, 65),
    (18, 24, 30),
    (18, 80, 82),
    (20, 21, 29),
    (20, 48, 52),
    (21, 28, 35),
    (21, 72, 75),
    (24, 32, 40),
    (24, 45, 51),
    (24, 70, 74),
    (25, 60, 65),
    (27, 36, 45),
    (28, 45, 53),
    (28, 96, 100),
    (30, 40, 50),
    (30, 72, 78),
    (32, 60, 68),
    (33, 44, 55),
    (33, 56, 65),
    (35, 84, 91),
    (36, 48, 60),
    (36, 77, 85),
    (39, 52, 65),
    (39, 80, 89),
    (40, 42, 58),
    (40, 75, 85),
    (42, 56, 70),
    (45, 60, 75),
    (48, 55, 73),
    (48, 64, 80),
    (51, 68, 85),
    (54, 72, 90),
    (57, 76, 95),
    (60, 63, 87),
    (60, 80, 100),
    (65, 72, 97),
]


def generate_task():
    """Пифагор: по двум сторонам прямоуг. треуг. найти третью.
    Прямой угол при C, A левый низ, B правый низ."""
    a, b, c = sorted(random.choice(PYTH_TRIPLES))  # a<b<c, c=гипотенуза
    subtype = random.choice(['forward', 'inverse'])

    # AC=b (длинный катет), BC=a (короткий катет)
    A, B, C = fit_right_triangle(b, a)
    rmark = _right_angle_marker(C, A, B, size=11)
    extras = rmark

    if subtype == 'forward':
        leg_AC = _side_label(A, C, str(b), away_from=B, offset=14)
        leg_BC = _side_label(B, C, str(a), away_from=A, offset=14)
        extras += leg_AC + leg_BC
        svg = render_triangle(A, B, C, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AC = {b}\\), \\(BC = {a}\\). Найдите \\(AB\\)."
        )
        answer = str(c)
    else:
        which = random.choice(['hide_BC', 'hide_AC'])
        if which == 'hide_BC':
            leg_AC = _side_label(A, C, str(b), away_from=B, offset=14)
            hyp = _side_label(A, B, str(c), away_from=C, offset=16)
            extras += leg_AC + hyp
            given_a, given_av, given_b, given_bv = 'AC', b, 'AB', c
            ask, ask_v = 'BC', a
        else:
            leg_BC = _side_label(B, C, str(a), away_from=A, offset=14)
            hyp = _side_label(A, B, str(c), away_from=C, offset=16)
            extras += leg_BC + hyp
            given_a, given_av, given_b, given_bv = 'BC', a, 'AB', c
            ask, ask_v = 'AC', b
        svg = render_triangle(A, B, C, labels=("A", "B", "C"), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\({given_a} = {given_av}\\), \\({given_b} = {given_bv}\\). "
            f"Найдите \\({ask}\\)."
        )
        answer = str(ask_v)

    cond = f"{text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(4)
    for i in range(3):
        t = generate_task()
        print(f"[G4 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G5: EQUILATERAL (Типы 12-17)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G5 = PLOTTER + r'''

def generate_task():
    """G5: равносторонний треугольник. В равностор. высота = медиана = биссектриса = a·√3/2."""
    direction = random.choice(['side_to_h', 'h_to_side'])
    element = random.choice(['медиана', 'высота', 'биссектриса'])

    if direction == 'side_to_h':
        k = random.randint(1, 60)
        side_text = f"{k}\\sqrt{{3}}"
        answer = _ans(3 * k / 2)
    else:
        k = random.randint(1, 50)
        h_text = f"{k}\\sqrt{{3}}"
        answer = str(2 * k)

    A, B, C = fit_equilateral()
    M = _midpoint(A, B)
    cevian_line = _side(C, M, width=1.3)
    marks_AB = _equality_marks(A, B, count=1)
    marks_BC = _equality_marks(B, C, count=1)
    marks_AC = _equality_marks(A, C, count=1)
    extras = cevian_line + marks_AB + marks_BC + marks_AC

    if element == 'высота':
        extras += _right_angle_marker(M, A, C, size=10)
        elem_letter = 'H'
    elif element == 'медиана':
        extras += _equality_marks(A, M, count=2) + _equality_marks(M, B, count=2)
        elem_letter = 'M'
    else:
        extras += _angle_arc(C, A, M, R=16, label_text='') + _angle_arc(C, M, B, R=16, label_text='')
        elem_letter = 'D'

    M_dot = _vertex_dot(M)
    M_lab = _point_label(M, elem_letter, direction=(0, 1), offset=15)
    extras += M_dot + M_lab
    svg = render_triangle(A, B, C, labels=('A', 'B', 'C'), extras=extras)
    elem_segment = 'C' + elem_letter

    if direction == 'side_to_h':
        text = (
            f"Сторона равностороннего треугольника \\(ABC\\) равна \\({side_text}\\). "
            f"Найдите {element} \\({elem_segment}\\) этого треугольника."
        )
    else:
        text = (
            f"В равностороннем треугольнике \\(ABC\\) проведена {element} \\({elem_segment}\\), "
            f"равная \\({h_text}\\). Найдите сторону этого треугольника."
        )

    cond = f"{text}<br><br>{svg}"
    return {'condition_text': cond, 'correct_answer': answer}


if __name__ == '__main__':
    random.seed(5)
    for i in range(3):
        t = generate_task()
        print(f"[G5 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G6: TRIG_RIGHT (Типы 18-23)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G6 = PLOTTER + r'''

def generate_task():
    """G6: sin/cos/tg в прямоуг. треугольнике, прямо или обратно.

    Двусторонняя постановка:
    • forward — даны две стороны (целые), найти sin/cos/tg угла (десятичная).
    • inverse — дано отношение (дробью p/q) и одна сторона, найти другую
      сторону (целое или X,5/X,Y — ≤1 знак после запятой).

    Стороны и ответы не привязаны к пифагоровым тройкам — третья сторона
    треугольника может быть иррациональной и просто не подписывается.
    """
    from math import gcd as _gcd, sqrt as _sqrt
    func = random.choice(['sin', 'cos', 'tg'])
    direction = random.choice(['forward', 'inverse'])

    if direction == 'forward':
        # Подбираем целые стороны так, чтобы отношение давало ≤1 знак.
        for _ in range(400):
            if func == 'tg':
                # tg∠B = AC/BC (отношение двух катетов)
                ac_int = random.randint(1, 60)
                bc_int = random.randint(1, 60)
                if ac_int == bc_int:
                    continue  # tg = 1
                ans = _ratio_1dp(ac_int, bc_int)
                if ans is None:
                    continue
                ab_geom = _sqrt(ac_int * ac_int + bc_int * bc_int)
                ac_geom, bc_geom = ac_int, bc_int
                break
            else:
                # sin∠B = AC/AB, cos∠B = BC/AB (катет/гипотенуза)
                ab_int = random.randint(2, 100)
                leg = random.randint(1, ab_int - 1)
                ans = _ratio_1dp(leg, ab_int)
                if ans is None:
                    continue
                hidden = _sqrt(ab_int * ab_int - leg * leg)
                if hidden < 0.5:
                    continue
                if func == 'sin':
                    ac_int = leg
                    ac_geom, bc_geom = leg, hidden
                else:
                    bc_int = leg
                    ac_geom, bc_geom = hidden, leg
                ab_geom = ab_int
                break
        else:
            # Запасной вариант
            ac_int = 3; bc_int_ = 4
            ac_geom, bc_geom, ab_geom = 3, 4, 5
            func = 'sin'
            ans = '0,6'
            ab_int = 5
            leg = 3

        A, B, C = fit_right_triangle(ac_geom, bc_geom)
        rmark = _right_angle_marker(C, A, B, size=11)
        extras = rmark

        if func == 'sin':
            extras += _side_label(A, C, str(ac_int), away_from=B, offset=14)
            extras += _side_label(A, B, str(ab_int), away_from=C, offset=16)
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(AC = {ac_int}\\), \\(AB = {ab_int}\\). Найдите \\(\\sin\\angle B\\)."
            )
        elif func == 'cos':
            extras += _side_label(B, C, str(bc_int), away_from=A, offset=14)
            extras += _side_label(A, B, str(ab_int), away_from=C, offset=16)
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {bc_int}\\), \\(AB = {ab_int}\\). Найдите \\(\\cos\\angle B\\)."
            )
        else:
            extras += _side_label(B, C, str(bc_int), away_from=A, offset=14)
            extras += _side_label(A, C, str(ac_int), away_from=B, offset=14)
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {bc_int}\\), \\(AC = {ac_int}\\). Найдите \\(\\operatorname{{tg}}\\angle B\\)."
            )
        answer = ans

    else:
        # inverse: дано отношение p/q и одна сторона K, найти другую.
        # sin∠B = AC/AB,  cos∠B = BC/AB,  tg∠B = AC/BC.
        for _ in range(400):
            if func == 'tg':
                p_raw = random.randint(1, 15)
                q_raw = random.randint(1, 15)
            else:
                q_raw = random.randint(2, 12)
                p_raw = random.randint(1, q_raw - 1)
            g = _gcd(p_raw, q_raw)
            p = p_raw // g
            q = q_raw // g
            if p == q:
                continue  # тривиально (sin/cos = 1 или tg = 1)
            # K должно быть кратным q // gcd(10, q), чтобы K·p/q было ≤1 dp.
            step = q // _gcd(10, q)
            candidates = [m * step for m in range(1, 21) if 2 <= m * step <= 80]
            if not candidates:
                continue
            K = random.choice(candidates)
            target = _ratio_1dp(K * p, q)
            if target is None:
                continue  # на всякий случай
            # Не хотим тривиального ответа = K (бывает при p/q = 1, но мы это уже отсеяли)
            break
        else:
            p, q, K = 3, 5, 25
            target = '15'

        # Геометрия и подписи
        if func == 'sin':
            ac_geom = K * p / q
            bc_geom = _sqrt(K * K - ac_geom * ac_geom)
            A, B, C = fit_right_triangle(ac_geom, bc_geom)
            rmark = _right_angle_marker(C, A, B, size=11)
            extras = rmark + _side_label(A, B, str(K), away_from=C, offset=16)
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\sin\\angle B = \\dfrac{{{p}}}{{{q}}}\\), "
                f"\\(AB = {K}\\). Найдите \\(AC\\)."
            )
        elif func == 'cos':
            bc_geom = K * p / q
            ac_geom = _sqrt(K * K - bc_geom * bc_geom)
            A, B, C = fit_right_triangle(ac_geom, bc_geom)
            rmark = _right_angle_marker(C, A, B, size=11)
            extras = rmark + _side_label(A, B, str(K), away_from=C, offset=16)
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\cos\\angle B = \\dfrac{{{p}}}{{{q}}}\\), "
                f"\\(AB = {K}\\). Найдите \\(BC\\)."
            )
        else:
            bc_geom = K
            ac_geom = K * p / q
            A, B, C = fit_right_triangle(ac_geom, bc_geom)
            rmark = _right_angle_marker(C, A, B, size=11)
            extras = rmark + _side_label(B, C, str(K), away_from=A, offset=14)
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\operatorname{{tg}}\\angle B = \\dfrac{{{p}}}{{{q}}}\\), "
                f"\\(BC = {K}\\). Найдите \\(AC\\)."
            )
        answer = target

    svg = render_triangle(A, B, C, labels=('A', 'B', 'C'), extras=extras)
    cond = f"{text}<br><br>{svg}"
    return {'condition_text': cond, 'correct_answer': answer}


if __name__ == '__main__':
    random.seed(6)
    for i in range(3):
        t = generate_task()
        print(f"[G6 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G7: AREA (Типы 24, 25, 26)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G7 = PLOTTER + r'''

def generate_task():
    """G7: площадь треугольника."""
    subtype = random.choice(['legs', 'side_height', 'two_sides_sin'])

    if subtype == 'legs':
        # Прямоуг. треуг., катеты a, b → S = a·b/2
        a = random.randint(1, 50)
        b = random.randint(1, 50)
        A, B, C = fit_right_triangle(b, a)
        rmark = _right_angle_marker(C, A, B, size=11)
        lbl_AC = _side_label(A, C, str(b), away_from=B, offset=14)
        lbl_BC = _side_label(B, C, str(a), away_from=A, offset=14)
        svg = render_triangle(A, B, C, labels=('A', 'B', 'C'),
                              extras=rmark + lbl_AC + lbl_BC)
        text = (
            f"Два катета прямоугольного треугольника равны \\({b}\\) и \\({a}\\). "
            f"Найдите площадь этого треугольника."
        )
        answer = _ans(a * b / 2)

    elif subtype == 'side_height':
        # Сторона a и высота h к ней → S = a·h/2 (всегда X или X,5)
        a_val = random.randint(2, 100)
        h_val = random.randint(1, 50)
        angA = random.randint(35, 70)
        angB = random.randint(35, 70)
        if angA + angB > 140:
            angA, angB = 55, 55
        A, B, C = fit_triangle(angA, angB)
        H = _foot_of_perp(C, A, B)
        height_line = _dashed_segment(C, H)
        right_mark = _right_angle_marker(H, A, C, size=9)
        lbl_AB = _side_label(A, B, str(a_val), away_from=C, offset=16)
        # Подпись высоты — посередине отрезка CH, наружу (вправо от средней линии)
        Mh = _midpoint(C, H)
        dx = H[0] - C[0]; dy = H[1] - C[1]
        L = math.hypot(dx, dy)
        nx, ny = -dy / L, dx / L
        # Положим подпись справа от отрезка
        lh_x = Mh[0] + nx * 12
        lh_y = Mh[1] + ny * 12 + 5
        lbl_h = (
            f'<text x="{lh_x:.1f}" y="{lh_y:.1f}" font-family="Cambria, Georgia, serif" '
            f'font-size="13" fill="#1f1f1f" text-anchor="middle">{h_val}</text>'
        )
        H_dot = _vertex_dot(H)
        H_lab = _point_label(H, 'H', direction=(0, 1), offset=15)
        extras = height_line + right_mark + lbl_AB + lbl_h + H_dot + H_lab
        svg = render_triangle(A, B, C, labels=('A', 'B', 'C'), extras=extras)
        text = (
            f"Сторона треугольника равна \\({a_val}\\), а высота, проведённая к этой стороне, "
            f"равна \\({h_val}\\). Найдите площадь этого треугольника."
        )
        answer = _ans(a_val * h_val / 2)

    else:
        # Две стороны и sin угла между ними → S = ½·a·b·sin.
        # Допускаем ответы X или X,5 (≤ 1 знак после запятой).
        sin_choices = [
            (3, 5), (4, 5), (5, 13), (12, 13), (8, 17), (15, 17),
            (24, 25), (7, 25), (20, 29), (21, 29), (5, 7), (6, 7),
            (1, 3), (2, 3), (1, 4), (3, 4), (1, 2),
            (1, 5), (2, 5), (3, 10), (7, 10), (9, 10),
        ]
        S_str = None
        for _ in range(80):
            a_val = random.randint(3, 50)
            b_val = random.randint(3, 50)
            sin_p, sin_q = random.choice(sin_choices)
            S_str = _ratio_1dp(a_val * b_val * sin_p, 2 * sin_q)
            if S_str is not None:
                break
        if S_str is None:
            a_val, b_val = 14, 5
            sin_p, sin_q = 6, 7
            S_str = _ratio_1dp(a_val * b_val * sin_p, 2 * sin_q)
        angA = random.randint(35, 70)
        angB = random.randint(35, 70)
        if angA + angB > 140:
            angA, angB = 55, 55
        A, B, C = fit_triangle(angA, angB)
        # В нашей задаче ∠ABC — угол при B (нижняя правая вершина), между сторонами AB и BC
        lbl_AB = _side_label(A, B, str(a_val), away_from=C, offset=16)
        lbl_BC = _side_label(B, C, str(b_val), away_from=A, offset=14)
        # Дуга при B с подписью sin
        arc_B = _angle_arc(B, A, C, R=22, label_text='')
        extras = lbl_AB + lbl_BC + arc_B
        svg = render_triangle(A, B, C, labels=('A', 'B', 'C'), extras=extras)
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(AB = {a_val}\\), \\(BC = {b_val}\\), "
            f"\\(\\sin\\angle ABC = \\dfrac{{{sin_p}}}{{{sin_q}}}\\). "
            f"Найдите площадь треугольника \\(ABC\\)."
        )
        answer = S_str

    cond = f"{text}<br><br>{svg}"
    return {'condition_text': cond, 'correct_answer': answer}


if __name__ == '__main__':
    random.seed(7)
    for i in range(3):
        t = generate_task()
        print(f"[G7 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G8: MIDLINE (Тип 27)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G8 = PLOTTER + r'''

def generate_task():
    """G8: средняя линия треугольника. M, N — середины двух сторон; MN = AC/2."""
    AC_val = random.randint(2, 200)
    # Случайные углы для аккуратного рисунка
    angA = random.randint(35, 75)
    angB = random.randint(35, 75)
    if angA + angB > 140:
        angA, angB = 55, 55
    A, B, C = fit_triangle(angA, angB)
    # M — середина AB, N — середина BC
    M = _midpoint(A, B)
    N = _midpoint(B, C)
    MN_line = _side(M, N, width=1.5)
    # Засечки на AM=MB и BN=NC
    marks_AM = _equality_marks(A, M, count=1)
    marks_MB = _equality_marks(M, B, count=1)
    marks_BN = _equality_marks(B, N, count=2)
    marks_NC = _equality_marks(N, C, count=2)
    # Подпись AC (длина)
    lbl_AC = _side_label(A, C, str(AC_val), away_from=B, offset=14)
    # Метки M (на AB, наружу = вниз) и N (на BC, наружу)
    M_dot = _vertex_dot(M)
    M_lab = _point_label(M, 'M', direction=(0, 1), offset=15)
    # N снаружи BC
    bc_dx = C[0] - B[0]; bc_dy = C[1] - B[1]
    bc_L = math.hypot(bc_dx, bc_dy)
    nx, ny = -bc_dy / bc_L, bc_dx / bc_L
    if nx * (A[0] - N[0]) + ny * (A[1] - N[1]) > 0:
        nx, ny = -nx, -ny
    N_dot = _vertex_dot(N)
    N_lab = _point_label(N, 'N', direction=(nx, ny), offset=15)
    extras = (MN_line + marks_AM + marks_MB + marks_BN + marks_NC
              + lbl_AC + M_dot + M_lab + N_dot + N_lab)
    svg = render_triangle(A, B, C, labels=('A', 'B', 'C'), extras=extras)
    text = (
        f"Точки \\(M\\) и \\(N\\) являются серединами сторон \\(AB\\) и \\(BC\\) "
        f"треугольника \\(ABC\\), сторона \\(AC\\) равна \\({AC_val}\\). "
        f"Найдите \\(MN\\)."
    )
    answer = _ans(AC_val / 2)
    cond = f"{text}<br><br>{svg}"
    return {'condition_text': cond, 'correct_answer': answer}


if __name__ == '__main__':
    random.seed(8)
    for i in range(3):
        t = generate_task()
        print(f"[G8 #{i+1}] answer = {t['correct_answer']}")
'''


PROTOTYPES = [
    (1, 'OGE15: G1 — сумма углов треугольника',
        'Сумма углов / прямоуг. / внешний угол', GEN_G1),
    (2, 'OGE15: G2 — равнобедренный / высота / биссектриса',
        'Равнобедр., высота, биссектриса', GEN_G2),
    (3, 'OGE15: G3 — медиана и спец. комбинации',
        'Медиана / биссектр.+равенство / медиана к гипотенузе', GEN_G3),
    (4, 'OGE15: G4 — теорема Пифагора',
        'Прямоуг. треуг.: Пифагор', GEN_G4),
    (5, 'OGE15: G5 — равносторонний треугольник',
        'Сторона ↔ высота/медиана/биссектриса', GEN_G5),
    (6, 'OGE15: G6 — тригонометрия в прямоуг. треугольнике',
        'sin/cos/tg — прямо и обратно', GEN_G6),
    (7, 'OGE15: G7 — площадь треугольника',
        'Катеты / сторона+высота / две стороны+sin', GEN_G7),
    (8, 'OGE15: G8 — средняя линия треугольника',
        'MN = AC/2', GEN_G8),
]


class Command(BaseCommand):
    help = "Создаёт «Задание 15» (Треугольники)"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true')

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            course = Course.objects.get(slug='oge-maths')
        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR('Курс oge-maths не найден'))
            return
        # Ищем 'Первая часть' по имени — не по order=1 (есть и order=0 модуль).
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )
        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 15').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 15',
            defaults={'order': 15, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 15:
            lesson.order = 15
            lesson.save(update_fields=['order'])
        existing_by_order = {a.order: a for a in lesson.assignments.all()}
        for order, gen_name, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={'generator_type': 'python_function', 'python_code': code, 'config': {}},
            )
            assign = existing_by_order.get(order)
            if assign:
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'text_input'
                assign.required_correct = 3
                assign.save()
                shown_title = assign.title
            else:
                Assignment.objects.create(
                    lesson=lesson, order=order, title=asg_title, description='',
                    assignment_type='test', answer_type='text_input',
                    required_correct=3, problem_generator=generator,
                )
                shown_title = asg_title
            self.stdout.write(self.style.SUCCESS(f'  + [{order}] {shown_title}'))
        self.stdout.write(self.style.SUCCESS(f'\nГотово: {len(PROTOTYPES)} прототипов.'))
