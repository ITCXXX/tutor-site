# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=147: OGE16: G15 — квадрат: a, R, r, d, S
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


def _fmt_k_sqrt2(k):
    """Возвращает строку 'k\\sqrt{2}' (или просто '\\sqrt{2}' при k=1)."""
    if k == 1:
        return r"\sqrt{2}"
    return f"{k}\\sqrt{{2}}"


def generate_task():
    """Связи в квадрате со стороной a:
        R (описанной)  = a·√2/2
        r (вписанной)  = a/2
        d (диагональ)  = a·√2
        S (площадь)    = a²
    Все 5 «классических» подтипов ОГЭ (28–32). Корни — в условии,
    ответ всегда целый.
    """
    subtype = random.choice(['t28', 't29', 't30', 't31', 't32'])
    k = random.randint(2, 25)  # базовый коэффициент

    if subtype == 't28':
        # a = k√2 → R = k
        a_cond = _fmt_k_sqrt2(k)
        ask_text = (
            f"Сторона квадрата равна \\({a_cond}\\). Найдите радиус "
            f"описанной около этого квадрата окружности."
        )
        answer = str(k)
        # для рисунка
        a_geom = k  # будем использовать пиксельную сторону отдельно
        draw = 'R'

    elif subtype == 't29':
        # R = k√2 → a = 2k
        R_cond = _fmt_k_sqrt2(k)
        ask_text = (
            f"Радиус описанной около квадрата окружности равен \\({R_cond}\\). "
            f"Найдите сторону этого квадрата."
        )
        answer = str(2 * k)
        draw = 'R'

    elif subtype == 't30':
        # a = 2k → r = k (a чётное, чтобы r целое)
        a_val = 2 * k
        ask_text = (
            f"Сторона квадрата равна \\({a_val}\\). Найдите радиус "
            f"вписанной в этот квадрат окружности."
        )
        answer = str(k)
        draw = 'r'

    elif subtype == 't31':
        # r = k → S = 4k²
        ask_text = (
            f"Радиус вписанной в квадрат окружности равен \\({k}\\). "
            f"Найдите площадь этого квадрата."
        )
        answer = str(4 * k * k)
        draw = 'r'

    else:  # t32
        # r = k√2 → d = 4k
        r_cond = _fmt_k_sqrt2(k)
        ask_text = (
            f"Радиус вписанной в квадрат окружности равен \\({r_cond}\\). "
            f"Найдите диагональ этого квадрата."
        )
        answer = str(4 * k)
        draw = 'r'

    # Картинка: квадрат + описанная или вписанная окружность.
    side_px = 110
    O = (160, 125)
    # Вершины: A слева-верх, B справа-верх, C справа-низ, D слева-низ
    # (CW порядок, как обычно для квадратов на ОГЭ).
    A = (O[0] - side_px / 2, O[1] - side_px / 2)
    B = (O[0] + side_px / 2, O[1] - side_px / 2)
    C = (O[0] + side_px / 2, O[1] + side_px / 2)
    D = (O[0] - side_px / 2, O[1] + side_px / 2)

    body = ""
    if draw == 'R':
        # Описанная окружность: радиус = расстояние от центра до вершины
        R_px = side_px * math.sqrt(2) / 2
        body += _circle(O, R_px)
    else:
        # Вписанная: радиус = side_px / 2
        r_px = side_px / 2
        body += _circle(O, r_px)

    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(15)
    for i in range(5):
        t = generate_task()
        print(f"[G15 #{i+1}] answer = {t['correct_answer']}")
