# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=141: OGE16: G9 — описанный 4-уг.: a+c = b+d
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


def _build_circumscribed_quad(tangent_angles, O=(160, 125), R=52):
    """4-угольник, образованный касательными к окружности в точках с заданными
    углами (углы — позиции точек касания на окружности, в градусах,
    в порядке обхода 4-угольника)."""
    Ox, Oy = O
    Ts = [_pt_on_circle(O, R, a) for a in tangent_angles]

    def _intersect_tangents(T1, T2):
        n1x, n1y = T1[0] - Ox, T1[1] - Oy
        n2x, n2y = T2[0] - Ox, T2[1] - Oy
        c1 = n1x * T1[0] + n1y * T1[1]
        c2 = n2x * T2[0] + n2y * T2[1]
        det = n1x * n2y - n1y * n2x
        if abs(det) < 1e-9:
            return None
        x = (c1 * n2y - c2 * n1y) / det
        y = (n1x * c2 - n2x * c1) / det
        return (x, y)

    A = _intersect_tangents(Ts[3], Ts[0])
    B = _intersect_tangents(Ts[0], Ts[1])
    C = _intersect_tangents(Ts[1], Ts[2])
    D = _intersect_tangents(Ts[2], Ts[3])
    return A, B, C, D


def generate_task():
    """Описанный 4-уг.: AB + CD = BC + AD.
    Алгоритм:
      1. Сгенерировать полупериметр s.
      2. Разбить s = AB + CD = pair1 (одна пара противоположных).
      3. Разбить s = BC + AD = pair2 (другая пара).
      4. Случайно «спрятать» одну сторону — её и спрашиваем.
    """
    # Полупериметр s ∈ [16, 50] — чтобы стороны были разумные.
    s = random.randint(16, 50)
    AB = random.randint(3, s - 3)
    CD = s - AB
    BC = random.randint(3, s - 3)
    AD = s - BC
    # Не хотим, чтобы две пары совпадали (тогда задача тривиальна).
    for _ in range(30):
        if (AB, CD) != (BC, AD) and (AB, CD) != (AD, BC):
            break
        BC = random.randint(3, s - 3)
        AD = s - BC
    # Выбираем, какую сторону «спрятать» (= спрашиваем её в задаче).
    unknown = random.choice(['AB', 'BC', 'CD', 'AD'])
    sides_known = {'AB': AB, 'BC': BC, 'CD': CD, 'AD': AD}
    ans_val = sides_known.pop(unknown)

    shape = random.choice(['quad', 'trapezoid'])
    if shape == 'quad':
        intro = f"В четырёхугольник \\(ABCD\\) вписана окружность"
    else:
        intro = f"В трапецию \\(ABCD\\) вписана окружность"

    # Тексты сторон в условии (только известных)
    known_text = ", ".join(
        f"\\({name} = {sides_known[name]}\\)" for name in sides_known
    )
    ask_text = (
        f"{intro}, {known_text}. Найдите \\({unknown}\\)."
    )
    answer = str(ans_val)

    # Картинка — 4-уг. через касательные. Углы зависят от формы.
    if shape == 'quad':
        # «Случайные» углы в обходе ABCD. Возьмём фиксированный шаблон.
        tang_angles = random.choice([
            [200, 110, 20, 290],
            [210, 100, 350, 260],
            [195, 120, 30, 300],
        ])
    else:
        # Трапеция: основания BC (верх) и AD (низ) — точки касания на 90° и 270°.
        # Боковые: AB слева (между 90° и 270° против часовой), CD справа.
        # AB точка касания — угол между 100° и 170°. CD — симметрично или нет.
        ab_t = random.randint(135, 165)
        cd_t = 180 - ab_t  # симметрично относительно вертикальной оси
        # Порядок обхода ABCD: A слева-низ, B слева-верх, C справа-верх, D справа-низ.
        # Стороны и их точки касания (в порядке обхода ABCD):
        #   AB — между A и B = боковая левая, точка под ab_t (в верхней-левой части)
        #   BC — верх, под 90°
        #   CD — между C и D = боковая правая, под cd_t
        #   DA — низ, под 270°
        tang_angles = [ab_t, 90, cd_t, 270]

    O = (160, 125)
    R = 52
    A, B, C, D = _build_circumscribed_quad(tang_angles, O, R)

    body = _circle(O, R)
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_radial(D, "D", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(9)
    for i in range(5):
        t = generate_task()
        print(f"[G9 #{i+1}] answer = {t['correct_answer']}")
