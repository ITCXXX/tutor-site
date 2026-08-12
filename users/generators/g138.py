# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=138: OGE16: G6 — вписанный 4-уг., противоположные углы
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


def _build_quad_with_angle(given_v, given_angle, O, R):
    """Расположить ABCD на окружности (CW порядок, чтобы привычно: A слева, B
    вверху, C справа, D снизу) так, чтобы угол при given_v = given_angle.
    Для вписанного 4-уг.: дуга от соседа CCW к соседу CW (не через given_v) =
    2·given_angle. Распределяем равномерно: каждая боковая дуга = given_angle,
    дальние = (180 − given_angle). Затем небольшой джиттер.
    """
    cycle = ['A', 'B', 'C', 'D']
    i = cycle.index(given_v)
    # Назначаем угловые позиции на окружности (в SVG-смысле, для _pt_on_circle):
    # given_v вверху (90°), соседи симметрично, противоположный внизу.
    half_far = 180 - given_angle  # дуга от given_v до соседа (любого) по CW/CCW
    a_given = 90
    a_neigh_ccw = 90 + half_far
    a_opposite = 270  # = 90 + 180
    a_neigh_cw = 90 - half_far
    # Соответствие: cycle[(i+1)%4] — следующий в ABCD; для CW порядка это
    # сосед CW. cycle[(i+3)%4] = пред. в ABCD = сосед CCW.
    v_to_angle = {
        cycle[i]:           a_given,
        cycle[(i + 1) % 4]: a_neigh_cw,
        cycle[(i + 2) % 4]: a_opposite,
        cycle[(i + 3) % 4]: a_neigh_ccw,
    }
    # Джиттер: вращаем всю фигуру и слегка двигаем "не-given" вершины,
    # сохраняя сумму смещений = 0 у соседей given_v (чтобы не сдвинуть угол).
    rot = random.uniform(-25, 25)
    delta = random.uniform(-7, 7)
    pts = {}
    for v, ang in v_to_angle.items():
        a = ang + rot
        if v == cycle[(i + 1) % 4]:
            a += delta
        elif v == cycle[(i + 3) % 4]:
            a -= delta
        pts[v] = _pt_on_circle(O, R, a)
    return pts


def generate_task():
    """Вписанный 4-уг.: ∠A + ∠C = 180°, ∠B + ∠D = 180°."""
    given_v = random.choice(['A', 'B', 'C', 'D'])
    given_angle = random.randint(40, 140)
    other = 180 - given_angle
    other_v = {'A': 'C', 'B': 'D', 'C': 'A', 'D': 'B'}[given_v]
    ask_text = (
        f"Четырёхугольник \\(ABCD\\) вписан в окружность. "
        f"Угол \\({given_v}\\) равен \\({given_angle}°\\). "
        f"Найдите угол \\({other_v}\\). Ответ дайте в градусах."
    )
    answer = str(other)

    O = (160, 125)
    R = 78
    pts = _build_quad_with_angle(given_v, given_angle, O, R)
    A, B, C, D = pts['A'], pts['B'], pts['C'], pts['D']

    body = _circle(O, R)
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)

    neighbors = {'A': ('D', 'B'), 'B': ('A', 'C'), 'C': ('B', 'D'), 'D': ('C', 'A')}
    n1, n2 = neighbors[given_v]
    body += _angle_arc(pts[given_v], pts[n1], pts[n2],
                       label_text=f"{given_angle}°", R=24, label_offset=14, arcs=1)
    on1, on2 = neighbors[other_v]
    body += _angle_arc(pts[other_v], pts[on1], pts[on2], R=24, arcs=2)

    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_radial(D, "D", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(6)
    for i in range(5):
        t = generate_task()
        print(f"[G6 #{i+1}] answer = {t['correct_answer']}")
