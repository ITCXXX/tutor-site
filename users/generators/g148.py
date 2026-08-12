# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=148: OGE16: G16 — квадрат + окружность с центром на стороне
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


def generate_task():
    """Около квадрата ABCD проведена окружность с центром на середине стороны
    AB, проходящая через C и D. Тогда R = a√5/2 (a — сторона квадрата).
    Берём R = k√5, a = 2k, S = 4k².
    """
    k = random.randint(2, 12)
    R_cond = f"{k}\\sqrt{{5}}" if k != 1 else r"\sqrt{5}"
    a_val = 2 * k
    S_val = 4 * k * k
    ask_text = (
        f"Около квадрата \\(ABCD\\) проведена окружность с центром на середине "
        f"стороны \\(AB\\), проходящая через вершины \\(C\\) и \\(D\\). "
        f"Радиус окружности равен \\({R_cond}\\). Найдите площадь квадрата."
    )
    answer = str(S_val)

    # Картинка: квадрат A слева-низ, B справа-низ, C справа-верх, D слева-верх.
    # Центр окружности M — середина AB. R = side·√5/2 ≈ 1,118·side.
    # Bounding box по вертикали: [M.y - side ; M.y + R]. Чтобы вписаться в
    # viewBox 320×240 с центром (160, 120), считаем M.y так, чтобы bbox
    # был центрирован вертикально.
    side_px = 80
    R_px = side_px * math.sqrt(5) / 2  # ≈ 89,4
    My = 120 + (side_px - R_px) / 2  # центрируем bbox: top=My-side, bot=My+R
    A = (160 - side_px / 2, My)
    B = (160 + side_px / 2, My)
    C = (160 + side_px / 2, My - side_px)
    D = (160 - side_px / 2, My - side_px)
    M = (160, My)

    body = _circle(M, R_px)
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _vertex_dot(M)
    body += _label_direction(A, "A", direction=(-1, 1), offset=12)
    body += _label_direction(B, "B", direction=(1, 1), offset=12)
    body += _label_direction(C, "C", direction=(1, -1), offset=12)
    body += _label_direction(D, "D", direction=(-1, -1), offset=12)
    body += _label_direction(M, "M", direction=(0, 1), offset=14, italic=True)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(16)
    for i in range(5):
        t = generate_task()
        print(f"[G16 #{i+1}] answer = {t['correct_answer']}")
