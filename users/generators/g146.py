# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=146: OGE16: G14 — равносторонний треугольник: a → R, r, h
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
    """Равносторонний треугольник со стороной a = k√3 (k чётное).
    Связи: R = a/√3 = k;  r = a/(2√3) = k/2;  h = a·√3/2 = 3k/2.
    Спрашиваем одно из {R, r, h}.
    """
    target = random.choice(['a_to_R', 'a_to_r', 'a_to_h',
                            'R_to_a', 'r_to_a'])
    k = random.randint(2, 25)

    def _ks3(n):
        if n == 1:
            return "\\sqrt{3}"
        return f"{n}\\sqrt{{3}}"

    if target == 'a_to_R':
        ask_text = (
            f"Сторона равностороннего треугольника равна \\({_ks3(k)}\\). "
            f"Найдите радиус описанной около этого треугольника окружности."
        )
        answer = str(k)
        draw_radius = 'circum'
    elif target == 'a_to_r':
        if k % 2 == 1:
            k = k + 1
        ask_text = (
            f"Сторона равностороннего треугольника равна \\({_ks3(k)}\\). "
            f"Найдите радиус вписанной в этот треугольник окружности."
        )
        answer = str(k // 2)
        draw_radius = 'incircle'
    elif target == 'a_to_h':
        if k % 2 == 1:
            k = k + 1
        ask_text = (
            f"Сторона равностороннего треугольника равна \\({_ks3(k)}\\). "
            f"Найдите высоту этого треугольника."
        )
        answer = str(3 * k // 2)
        draw_radius = 'height'
    elif target == 'R_to_a':
        ask_text = (
            f"Радиус описанной около равностороннего треугольника окружности "
            f"равен \\({_ks3(k)}\\). Найдите сторону этого треугольника."
        )
        answer = str(3 * k)
        draw_radius = 'circum'
    else:  # r_to_a
        ask_text = (
            f"Радиус вписанной в равносторонний треугольник окружности равен "
            f"\\({_ks3(k)}\\). Найдите сторону этого треугольника."
        )
        answer = str(6 * k)
        draw_radius = 'incircle'

    # Картинка: равносторонний треугольник + соответствующая окружность/высота.
    O = (160, 125)
    # Стандартное расположение: A слева внизу, B справа внизу, C сверху.
    # Размер выбираем так, чтобы вершины помещались в viewBox.
    side_px = 130
    height_px = side_px * math.sqrt(3) / 2  # ≈ 112.6
    A = (O[0] - side_px / 2, O[1] + height_px / 3)
    B = (O[0] + side_px / 2, O[1] + height_px / 3)
    C = (O[0], O[1] - 2 * height_px / 3)

    body = ""
    if draw_radius == 'circum':
        # Описанная окружность: радиус = расстояние от центра до вершины
        R_px = math.hypot(C[0] - O[0], C[1] - O[1])
        body += _circle(O, R_px)
    elif draw_radius == 'incircle':
        # Вписанная: радиус = высота / 3
        r_px = height_px / 3
        body += _circle(O, r_px)
    else:  # height
        # Покажем высоту из C к середине AB
        M = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
        body += _segment(C, M, dashed=False, width=1.3)
        body += _vertex_dot(M)

    body += _segment(A, B) + _segment(B, C) + _segment(C, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(14)
    for i in range(5):
        t = generate_task()
        print(f"[G14 #{i+1}] answer = {t['correct_answer']}")
