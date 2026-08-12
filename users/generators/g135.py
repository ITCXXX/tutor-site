# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=135: OGE16: G3 — вписанные углы через диаметр
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
    """Окружность с диаметром AB. C на одной полуокружности, D на другой.
    Прямая: дан ∠CBA, найти ∠CDB = 90° − ∠CBA.
    Обратная: дан ∠CDB, найти ∠CBA = 90° − ∠CDB.

    Доказательство: т.к. AB — диаметр, треугольник ACB прямоугольный (теорема
    Фалеса), ∠ACB = 90°. Значит дуга AC = 180° − дуга CB.
    ∠CBA — вписанный на дугу AC ⇒ дуга AC = 2·∠CBA.
    ∠CDB — вписанный на дугу CB ⇒ дуга CB = 2·∠CDB.
    дуга AC + дуга CB = 180° ⇒ 2·CBA + 2·CDB = 180° ⇒ CDB = 90° − CBA.
    """
    direction = random.choice(['forward', 'inverse'])

    O = (160, 120)
    R = 78

    if direction == 'forward':
        cba = random.randint(10, 80)
        cdb = 90 - cba
        ask_text = (
            f"В окружности с центром в точке \\(O\\) \\(AB\\) — диаметр. "
            f"Точки \\(C\\) и \\(D\\) лежат на окружности по разные стороны от "
            f"диаметра \\(AB\\). Найдите угол \\(CDB\\), если \\(\\angle CBA = {cba}°\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(cdb)
    else:
        cdb = random.randint(10, 80)
        cba = 90 - cdb
        ask_text = (
            f"В окружности с центром в точке \\(O\\) \\(AB\\) — диаметр. "
            f"Точки \\(C\\) и \\(D\\) лежат на окружности по разные стороны от "
            f"диаметра \\(AB\\). Найдите угол \\(CBA\\), если \\(\\angle CDB = {cdb}°\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(cba)

    # A слева (180°), B справа (0°).
    A = _pt_on_circle(O, R, 180)
    B = _pt_on_circle(O, R, 0)
    # C на верхней полуокружности — угол cba при B между BC и BA.
    # ∠CBA = (дуга AC) / 2. Если дуга AC (по верху от A к C) = 2·cba, то C под углом
    # 180° - 2·cba (от центра, в верхней полуокружности).
    # Проверка: при cba=45° → C под 90° (верх). При cba=10° → C под 160° (рядом с A).
    C_ang = 180 - 2 * cba
    C = _pt_on_circle(O, R, C_ang)
    # D на нижней полуокружности — произвольно, чтобы был ∠CDB на дугу CB.
    # Но для надёжной картинки разместим D приблизительно противоположно C, но снизу.
    # Например, под углом -90° (низ) — тогда дуга CB = 180° - C_ang = 2·cba? нет:
    # дуга от C (на C_ang) до B (на 0°), идя по часовой стрелке через верх:
    # C_ang - 0 = 180 - 2·cba. По часовой через низ: 360 - (180 - 2·cba) = 180 + 2·cba.
    # ∠CDB — вписанный угол с вершиной на бОльшей дуге, опирается на меньшую дугу CB.
    # ∠CDB = (180 - 2·cba) / 2 = 90 - cba. ✓
    # D должен быть на дуге CB БОЛЬШЕЙ (т.е. через A) — то есть в нижней полуокружности.
    D_ang = random.choice([-110, -90, -70])  # низ окружности
    D = _pt_on_circle(O, R, D_ang)

    body = _circle(O, R)
    # Диаметр AB
    body += _segment(A, B)
    # Хорды: BC, CD, DB — чтобы видны были треугольники CBA (с диаметром AB)
    # и CDB.
    body += _segment(B, C)
    body += _segment(D, C)
    body += _segment(D, B)

    # Дуги
    if direction == 'forward':
        body += _angle_arc(B, C, A, label_text=f"{cba}°", R=22, label_offset=14, arcs=1)
        body += _angle_arc(D, C, B, R=22, arcs=2)
    else:
        body += _angle_arc(D, C, B, label_text=f"{cdb}°", R=22, label_offset=14, arcs=1)
        body += _angle_arc(B, C, A, R=22, arcs=2)

    # Точки и подписи
    body += _vertex_dot(O)
    body += _vertex_dot(A)
    body += _vertex_dot(B)
    body += _vertex_dot(C)
    body += _vertex_dot(D)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_radial(D, "D", O, offset=14)
    # O — чуть выше горизонтальной линии диаметра (тогда подпись будет между A и B,
    # но не на самой линии). Сместим вниз чуть-чуть.
    body += _label_direction(O, "O", direction=(0, 1), offset=14, italic=True)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(3)
    for i in range(5):
        t = generate_task()
        print(f"[G3 #{i+1}] answer = {t['correct_answer']}")
