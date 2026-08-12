# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=131: OGE15: G7 — площадь треугольника
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
