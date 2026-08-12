# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=134: OGE16: G2 — два диаметра
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
    """Два диаметра AC и BD проведены через центр O.
    Прямая: дан ∠AOD (между диаметрами), найти ∠ACB = 90° − ∠AOD/2.
    Обратная: дан ∠ACB, найти ∠AOD = 180° − 2·∠ACB.

    Геометрия: AC и BD — диаметры. ∠AOB = 180° − ∠AOD (смежные углы).
    ∠ACB — вписанный, опирается на дугу AB, центральный угол на ту же
    дугу = ∠AOB. ⇒ ∠ACB = (180° − ∠AOD) / 2 = 90° − ∠AOD/2.
    """
    direction = random.choice(['forward', 'inverse'])

    O = (160, 125)
    R = 78

    if direction == 'forward':
        # Дан ∠AOD, найти ∠ACB
        aod = random.randint(20, 160)
        acb = 90 - aod / 2
        if acb <= 0:
            aod = 60
            acb = 60
        given_label = f"{aod}°"
        ask_text = (
            f"В окружности с центром в точке \\(O\\) проведены диаметры "
            f"\\(AC\\) и \\(BD\\), угол \\(AOD\\) равен \\({aod}°\\). "
            f"Найдите вписанный угол \\(ACB\\). Ответ дайте в градусах."
        )
        answer = _ans(acb)
        gamma_AOD = aod
    else:
        # Дан ∠ACB, найти ∠AOD
        acb = random.randint(15, 85)
        aod = 180 - 2 * acb
        given_label = f"{acb}°"
        ask_text = (
            f"В окружности с центром в точке \\(O\\) проведены диаметры "
            f"\\(AC\\) и \\(BD\\), вписанный угол \\(ACB\\) равен \\({acb}°\\). "
            f"Найдите угол \\(AOD\\). Ответ дайте в градусах."
        )
        answer = str(aod)
        gamma_AOD = aod

    # Размещение точек:
    # Диаметр AC: A — верхнее-левое, C — нижнее-правое.
    # Диаметр BD: B — верхнее-правое, D — нижнее-левое.
    # ∠AOD — между лучами OA (вверх-влево) и OD (вниз-влево) с одной (левой) стороны.
    # Если положить A под углом α (верх-лево, α в [110°, 160°]),
    # то D под (180° + α) mod 360 = α - 180° (это диаметрально противоположно B).
    # ∠AOD = α - (α - δ_AOD)? проще:
    # положим OA под (180° - aod/2) - небольшой наклон вверх влево,
    # OD под (180° + aod/2)... но тогда D будет ниже OX слева.

    # Стандартная картинка: ∠AOD — левый сектор, ∠BOC — правый сектор,
    # ∠AOB — верхний сектор (между диаметрами сверху).
    # OA под углом (180° - aod/2)? Нет, проще через 90°:
    # OA под углом (90° + (180° − aod)/2), OB под (90° − (180° − aod)/2).
    # Тогда ∠AOB = 180° − aod (сверху), ∠AOD = aod (слева, по другую сторону).

    aob = 180 - gamma_AOD
    A = _pt_on_circle(O, R, 90 + aob / 2)        # верх-лево
    B = _pt_on_circle(O, R, 90 - aob / 2)        # верх-право
    C = _pt_on_circle(O, R, 90 - aob / 2 + 180)  # низ-лево
    D = _pt_on_circle(O, R, 90 + aob / 2 + 180)  # низ-право
    # Хм, C должен быть диаметрально A, D — диаметрально B.
    # A под (90 + aob/2), C диам. → под (90 + aob/2) + 180 = 270 + aob/2 (низ-право)
    # B под (90 - aob/2), D диам. → под (90 - aob/2) + 180 = 270 - aob/2 (низ-лево)
    C = _pt_on_circle(O, R, 90 + aob / 2 + 180)
    D = _pt_on_circle(O, R, 90 - aob / 2 + 180)

    body = _circle(O, R)
    # Диаметры
    body += _segment(A, C)
    body += _segment(B, D)
    # Хорды для вписанного угла ACB: CA уже есть как диаметр AC,
    # CB — отдельная хорда.
    body += _segment(C, B)
    # Дуги-маркеры
    # ∠AOD при O между лучами OA и OD
    if direction == 'forward':
        body += _angle_arc(O, A, D, label_text=given_label, R=22, label_offset=14, arcs=1)
        body += _angle_arc(C, A, B, R=22, arcs=2)
    else:
        body += _angle_arc(C, A, B, label_text=given_label, R=22, label_offset=14, arcs=1)
        body += _angle_arc(O, A, D, R=22, arcs=2)
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
    # O — справа от центра, чтобы не мешать дугам слева
    body += _label_direction(O, "O", direction=(1, 0), offset=12, italic=True)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(2)
    for i in range(5):
        t = generate_task()
        print(f"[G2 #{i+1}] answer = {t['correct_answer']}")
