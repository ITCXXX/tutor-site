# -*- coding: utf-8 -*-
"""
Management command: создаёт ProblemGenerator-ы и Assignment-ы под урок
«Задание 16» курса ОГЭ. Тема — «Окружность и круг».

Архитектура (после анализа ФИПИ /bank/ + Школково /catalog/, 34 типа):
    БЛОК 1 — Вписанный/центральный угол:
        G1. INSC_CENTRAL_SAME_SIDE  — ∠AOB ↔ ∠ACB (прямая + обратная)
        G2. TWO_DIAMETERS           — два диаметра: ∠AOD ↔ ∠ACB
        G3. INSC_VIA_DIAMETER       — точка через диаметр: ∠CBA ↔ ∠CDB
    (далее G4-... — дописывается)

Стиль рисунков: ФИПИ-подобный.
    - viewBox 0 0 320 240
    - чёрный stroke #1f1f1f, толщина 1.5
    - шрифт Cambria/Georgia italic 16pt для вершин
    - кружочки r=2.5 на вершинах и центре

Usage:
    python manage.py seed_oge16
    python manage.py seed_oge16 --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# PLOTTER — общие SVG-хелперы для окружностей
# ──────────────────────────────────────────────────────────────────────────────

PLOTTER = r'''
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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G1: INSC_CENTRAL_SAME_SIDE — ∠AOB ↔ ∠ACB
# ──────────────────────────────────────────────────────────────────────────────

GEN_G1 = PLOTTER + r'''

def generate_task():
    """Вписанный + центральный угол, опирающиеся на одну и ту же дугу AB.
    Прямая: дан ∠AOB → ∠ACB = AOB/2.
    Обратная: дан ∠ACB → ∠AOB = 2·ACB.
    """
    direction = random.choice(['forward', 'inverse'])

    O = (160, 125)
    R = 78

    if direction == 'forward':
        # Дан центральный ∠AOB, найти вписанный ∠ACB
        aob = random.randint(30, 170)
        acb = aob / 2
        given_label = f"{aob}°"
        ask_var = "ACB"
        ask_text = (
            f"Центральный угол \\(AOB\\) равен \\({aob}°\\). "
            f"Найдите вписанный угол \\(ACB\\), опирающийся на ту же дугу \\(AB\\). "
            f"Ответ дайте в градусах."
        )
        answer = _ans(acb)
        gamma = aob
    else:
        # Дан вписанный ∠ACB, найти центральный ∠AOB
        acb = random.randint(15, 85)
        aob = 2 * acb
        given_label = f"{acb}°"
        ask_var = "AOB"
        ask_text = (
            f"Вписанный угол \\(ACB\\) равен \\({acb}°\\). "
            f"Найдите центральный угол \\(AOB\\), опирающийся на ту же дугу \\(AB\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(aob)
        gamma = aob

    # Размещение: A и B симметрично сверху, центральный угол при O = gamma.
    # A под (90 + gamma/2), B под (90 - gamma/2).
    A = _pt_on_circle(O, R, 90 + gamma / 2)
    B = _pt_on_circle(O, R, 90 - gamma / 2)
    # C — на противоположной дуге, внизу. Для симметрии — на 270°,
    # либо чуть смещаем, чтобы выглядело живо.
    C_angle = random.choice([255, 270, 285])
    C = _pt_on_circle(O, R, C_angle)

    body = _circle(O, R)
    # Радиусы OA, OB (для центрального угла)
    body += _segment(O, A)
    body += _segment(O, B)
    # Хорды CA, CB (для вписанного угла)
    body += _segment(C, A)
    body += _segment(C, B)
    # Дуги-маркеры
    if direction == 'forward':
        body += _angle_arc(O, A, B, label_text=given_label, R=22, label_offset=14, arcs=1)
        body += _angle_arc(C, A, B, R=24, arcs=2)
    else:
        body += _angle_arc(C, A, B, label_text=given_label, R=24, label_offset=14, arcs=1)
        body += _angle_arc(O, A, B, R=22, arcs=2)
    # Подписи + точки
    body += _vertex_dot(O)
    body += _vertex_dot(A)
    body += _vertex_dot(B)
    body += _vertex_dot(C)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    # Подпись O — снизу-слева от центра, не мешая радиусам
    body += _label_direction(O, "O", direction=(-1, 0.6), offset=14, italic=True)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(1)
    for i in range(5):
        t = generate_task()
        print(f"[G1 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G2: TWO_DIAMETERS — два диаметра, ∠AOD ↔ ∠ACB
# ──────────────────────────────────────────────────────────────────────────────

GEN_G2 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G3: INSC_VIA_DIAMETER — AB диаметр, C и D на разных полуокружностях
# ──────────────────────────────────────────────────────────────────────────────

GEN_G3 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G4: AB — диаметр описанной окружности, ∠A ↔ ∠B (тип 4)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G4 = PLOTTER + r'''

def generate_task():
    """Центр описанной около ABC окружности лежит на AB ⇒ AB — диаметр ⇒
    ∠ACB = 90° ⇒ ∠A + ∠B = 90°.
    """
    given_vertex = random.choice(['A', 'B'])
    given_angle = random.randint(10, 80)
    other = 90 - given_angle

    if given_vertex == 'A':
        ask_text = (
            f"Центр окружности, описанной около треугольника \\(ABC\\), лежит "
            f"на стороне \\(AB\\). Найдите угол \\(B\\), если угол \\(A\\) "
            f"равен \\({given_angle}°\\). Ответ дайте в градусах."
        )
        angA, angB = given_angle, other
    else:
        ask_text = (
            f"Центр окружности, описанной около треугольника \\(ABC\\), лежит "
            f"на стороне \\(AB\\). Найдите угол \\(A\\), если угол \\(B\\) "
            f"равен \\({given_angle}°\\). Ответ дайте в градусах."
        )
        angA, angB = other, given_angle
    answer = str(other)

    O = (160, 130)
    R = 78
    A = _pt_on_circle(O, R, 180)
    B = _pt_on_circle(O, R, 0)
    # ∠A = (дуга BC не через A) / 2 ⇒ дуга BC = 2·angA ⇒ C под углом (2·angA)
    # от центра, измеренным от положит. направления (на B). Тогда AC от A=180°
    # поднимается на angA градусов над AB.
    C = _pt_on_circle(O, R, 2 * angA)

    body = _circle(O, R)
    body += _segment(A, B) + _segment(A, C) + _segment(B, C)
    if given_vertex == 'A':
        body += _angle_arc(A, B, C, label_text=f"{angA}°", R=22, label_offset=14, arcs=1)
        body += _angle_arc(B, A, C, R=20, arcs=2)
    else:
        body += _angle_arc(B, A, C, label_text=f"{angB}°", R=22, label_offset=14, arcs=1)
        body += _angle_arc(A, B, C, R=20, arcs=2)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(O)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_direction(O, "O", direction=(0, 1), offset=14, italic=True)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(4)
    for i in range(5):
        t = generate_task()
        print(f"[G4 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G5: AB — диаметр описанной, катеты через Пифагор (типы 5, 6)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G5 = PLOTTER + r'''

_PYTH = []
for _m in range(2, 15):
    for _n in range(1, _m):
        if (_m - _n) % 2 == 1 and math.gcd(_m, _n) == 1:
            _a0 = _m * _m - _n * _n
            _b0 = 2 * _m * _n
            _c0 = _m * _m + _n * _n
            for _k in range(1, 101):
                if _c0 * _k > 100:
                    break
                _PYTH.append((sorted([_a0 * _k, _b0 * _k])[0],
                              sorted([_a0 * _k, _b0 * _k])[1],
                              _c0 * _k))


def _label_inside_segment(P1, P2, towards, text, offset=12, font_size=13):
    """Подпись посередине отрезка P1P2 — со стороны точки `towards`
    (внутрь треугольника, если towards — третья вершина)."""
    mx = (P1[0] + P2[0]) / 2
    my = (P1[1] + P2[1]) / 2
    dx = P2[0] - P1[0]; dy = P2[1] - P1[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    # Хотим нормаль, направленную К towards
    if nx * (towards[0] - mx) + ny * (towards[1] - my) < 0:
        nx, ny = -nx, -ny
    lx = mx + nx * offset
    ly = my + ny * offset + 5
    return (f'<text x="{lx:.1f}" y="{ly:.1f}" font-family="Cambria, Georgia, serif" '
            f'font-size="{font_size}" fill="#1f1f1f" text-anchor="middle">{text}</text>')


def generate_task():
    """Центр описанной около ABC лежит на AB ⇒ AB — диаметр ⇒ ∠C = 90°.
    Подтипы: дано AB+катет → другой; дано R+катет → другой.
    """
    subtype = random.choice(['AB_BC', 'AB_AC', 'R_BC', 'R_AC'])

    if subtype.startswith('R_'):
        even = [t for t in _PYTH if t[2] % 2 == 0]
        a, b, c = random.choice(even)
    else:
        a, b, c = random.choice(_PYTH)

    if random.random() < 0.5:
        AC, BC = a, b
    else:
        AC, BC = b, a
    AB = c

    if subtype == 'AB_BC':
        ask_text = (
            f"Центр окружности, описанной около треугольника \\(ABC\\), лежит "
            f"на стороне \\(AB\\), причём \\(AB = {AB}\\), \\(BC = {BC}\\). "
            f"Найдите \\(AC\\)."
        )
        answer = str(AC)
    elif subtype == 'AB_AC':
        ask_text = (
            f"Центр окружности, описанной около треугольника \\(ABC\\), лежит "
            f"на стороне \\(AB\\), причём \\(AB = {AB}\\), \\(AC = {AC}\\). "
            f"Найдите \\(BC\\)."
        )
        answer = str(BC)
    elif subtype == 'R_BC':
        R_val = AB // 2
        ask_text = (
            f"Центр окружности, описанной около треугольника \\(ABC\\), лежит "
            f"на стороне \\(AB\\). Радиус окружности равен \\({R_val}\\), "
            f"\\(BC = {BC}\\). Найдите \\(AC\\)."
        )
        answer = str(AC)
    else:
        R_val = AB // 2
        ask_text = (
            f"Центр окружности, описанной около треугольника \\(ABC\\), лежит "
            f"на стороне \\(AB\\). Радиус окружности равен \\({R_val}\\), "
            f"\\(AC = {AC}\\). Найдите \\(BC\\)."
        )
        answer = str(BC)

    O = (160, 130)
    R_px = 78
    A = _pt_on_circle(O, R_px, 180)
    B = _pt_on_circle(O, R_px, 0)
    # ∠A = arctan(BC/AC). C под (2·∠A) от центра, в верхней полуокружности.
    angA_deg = math.degrees(math.atan2(BC, AC))
    C = _pt_on_circle(O, R_px, 2 * angA_deg)

    body = _circle(O, R_px)
    body += _segment(A, B) + _segment(A, C) + _segment(B, C)

    # Длины НЕ подписываем на картинке — они есть в условии.

    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(O)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_direction(O, "O", direction=(0, 1), offset=14, italic=True)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(5)
    for i in range(5):
        t = generate_task()
        print(f"[G5 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G6: Вписанный 4-уг., противоположные углы (тип 13)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G6 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G7: Вписанный 4-уг., углы через равные дуги (типы 7, 8)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G7 = PLOTTER + r'''

def _build_quad_g7(alpha, beta, O, R):
    """Расположить ABCD (CW порядок) так, чтобы:
    - дуга AD не через B = 2α (даёт ∠ABD = α);
    - дуга CD не через A = 2β (даёт ∠CAD = β).
    A слева, B вверху, C справа, D внизу.
    Дуги (CW от A через B,C,D к A): AB + BC + CD + DA = 360°.
    DA = 2α, CD = 2β, AB = BC = (360 - 2α - 2β) / 2.
    """
    AB_arc = (360 - 2 * alpha - 2 * beta) / 2
    # Поставим B вверху на 90°. CW от B на AB_arc = позиция A.
    # В нашем _pt_on_circle 0° — справа, CCW = увеличение угла.
    # CW = уменьшение угла. То есть A = B + AB_arc (в матем. смысле, CCW).
    a_B = 90
    a_A = 90 + AB_arc           # CCW от B на AB_arc → A слева-сверху/слева
    a_D = a_A + 2 * alpha       # CCW от A на 2α → D
    a_C = a_D + 2 * beta        # CCW от D на 2β → C
    # Замкнётся обратно: a_C + AB_arc должно ≡ a_B (mod 360°). Проверка:
    # AB_arc + 2α + 2β + AB_arc = 360 ⇒ ОК.
    rot = random.uniform(-15, 15)
    A = _pt_on_circle(O, R, a_A + rot)
    B = _pt_on_circle(O, R, a_B + rot)
    C = _pt_on_circle(O, R, a_C + rot)
    D = _pt_on_circle(O, R, a_D + rot)
    return A, B, C, D


def generate_task():
    """Вписанный 4-уг. Базовое: ∠ABD = α (на дугу AD), ∠CAD = β (на дугу CD).
    Тогда ∠DBC = ∠DAC = β (на ту же дугу DC), и ∠ABC = α + β.
    """
    alpha = random.randint(15, 60)
    beta = random.randint(15, 60)
    if alpha + beta > 130:
        alpha, beta = 30, 40
    ans = alpha + beta
    ask_text = (
        f"Четырёхугольник \\(ABCD\\) вписан в окружность. "
        f"Угол \\(ABD\\) равен \\({alpha}°\\), угол \\(CAD\\) равен \\({beta}°\\). "
        f"Найдите угол \\(ABC\\). Ответ дайте в градусах."
    )
    answer = str(ans)

    O = (160, 125)
    R = 78
    A, B, C, D = _build_quad_g7(alpha, beta, O, R)

    body = _circle(O, R)
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(B, D)  # диагональ для ∠ABD
    body += _segment(A, C)  # диагональ для ∠CAD

    # Маркер ∠ABD (при B, между BA и BD) — 1 дуга, маленький радиус
    body += _angle_arc(B, A, D, label_text=f"{alpha}°", R=16, label_offset=12, arcs=1)
    # Маркер ∠CAD (при A, между AC и AD) — 2 дуги
    body += _angle_arc(A, C, D, label_text=f"{beta}°", R=18, label_offset=14, arcs=2)
    # Искомый ∠ABC дужкой НЕ помечаем (только в условии).

    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_radial(D, "D", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(7)
    for i in range(5):
        t = generate_task()
        print(f"[G7 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G8: Вписанная (равнобедренная) трапеция, углы (типы 11, 12)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G8 = PLOTTER + r'''

def generate_task():
    """Трапеция ABCD вписана в окружность ⇒ равнобедренная.
    Основания: BC (верх) и AD (низ). ∠A = ∠D, ∠B = ∠C, ∠A + ∠B = 180°.
    """
    subtype = random.choice(['A_to_B', 'A_to_D', 'B_to_A', 'B_to_C'])

    if subtype == 'A_to_B':
        angA = random.randint(45, 80)
        given_v, given_a, ask_v, ans = 'A', angA, 'B', 180 - angA
    elif subtype == 'A_to_D':
        angA = random.randint(45, 80)
        given_v, given_a, ask_v, ans = 'A', angA, 'D', angA
    elif subtype == 'B_to_A':
        angB = random.randint(100, 135)
        given_v, given_a, ask_v, ans = 'B', angB, 'A', 180 - angB
    else:
        angB = random.randint(100, 135)
        given_v, given_a, ask_v, ans = 'B', angB, 'C', angB

    ask_text = (
        f"Четырёхугольник \\(ABCD\\) с вершинами на окружности — трапеция "
        f"с основаниями \\(BC\\) и \\(AD\\). "
        f"Угол \\({given_v}\\) равен \\({given_a}°\\). "
        f"Найдите угол \\(ask_v\\). Ответ дайте в градусах."
    ).replace('ask_v', ask_v)
    answer = str(ans)

    # Построим равнобедренную трапецию вписанную: AD внизу горизонт., BC сверху.
    # Угол при основании = angA. Дуги:
    #   ∠A = (дуга BCD не через A) / 2 ⇒ дуга BCD = 2·angA.
    #   Симметрия: дуга AD внизу = δ, дуга BC сверху = 360 - 2·angA - δ.
    #   Распределение по симметрии: пусть AD = δ, BC = 360 - 2·angA - δ.
    #   Делаем AD длиннее BC: δ > BC ⇒ δ > (360 - 2·angA)/2 = 180 - angA.
    #   Возьмём δ = 180 - angA + 30 (фиксированная разница оснований).
    if subtype.startswith('A_'):
        angA_val = angA
    else:
        angA_val = 180 - angB

    # Равнобедренная вписанная трапеция:
    #   AB = CD (равны), ∠A = (BC + CD) / 2.
    # Хотим: все дуги ≥ 55° (чтобы буквы не наезжали), AD > BC.
    # CD = 2·angA_val - BC ; AB = CD ; DA = 360 - 2·CD - BC.
    bc_min = max(55, 4 * angA_val - 295)
    bc_max = 2 * angA_val - 55
    if bc_min > bc_max:
        bc_min = bc_max = max(55, bc_min - 5)
    bc_arc = random.randint(int(bc_min), int(bc_max))
    cd_arc = 2 * angA_val - bc_arc
    ab_arc = cd_arc
    da_arc = 360 - 2 * cd_arc - bc_arc
    # Симметричное расположение: AD центрировано вокруг 270°, BC вокруг 90°.
    O = (160, 125)
    R = 78
    a_A = 270 - da_arc / 2
    a_D = 270 + da_arc / 2
    a_B = 90 + bc_arc / 2
    a_C = 90 - bc_arc / 2
    A = _pt_on_circle(O, R, a_A)
    D = _pt_on_circle(O, R, a_D)
    B = _pt_on_circle(O, R, a_B)
    C = _pt_on_circle(O, R, a_C)

    body = _circle(O, R)
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)

    pts = {'A': A, 'B': B, 'C': C, 'D': D}
    neighbors = {'A': ('D', 'B'), 'B': ('A', 'C'), 'C': ('B', 'D'), 'D': ('C', 'A')}
    n1, n2 = neighbors[given_v]
    body += _angle_arc(pts[given_v], pts[n1], pts[n2],
                       label_text=f"{given_a}°", R=22, label_offset=14, arcs=1)
    on1, on2 = neighbors[ask_v]
    body += _angle_arc(pts[ask_v], pts[on1], pts[on2], R=22, arcs=2)

    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_radial(D, "D", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(8)
    for i in range(5):
        t = generate_task()
        print(f"[G8 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G9: Описанный 4-угольник, a + c = b + d (типы 23, 24)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G9 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G10: Вписанная окружность в трапецию, h = 2r (типы 25, 26, 27)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G10 = PLOTTER + r'''

def _build_circumscribed_quad(tangent_angles, O=(160, 125), R=52):
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
    """Трапеция, описанная около окружности ⇒ окружность касается обоих
    оснований ⇒ высота h = 2·r.
    Подтипы:
      - shape = 'any' | 'right' | 'iso' — вид трапеции (для разнообразия картинок)
      - direction = 'forward' (дан r → h) | 'inverse' (дан h → r)
    """
    shape = random.choice(['any', 'right', 'iso'])
    direction = random.choice(['forward', 'inverse'])

    # Берём числа с допустимыми десятичными результатами (X или X,5).
    if direction == 'forward':
        # r → h = 2r. r может быть целым или X,5.
        r_options = list(range(1, 21)) + [x + 0.5 for x in range(1, 20)]
        r_val = random.choice(r_options)
        h_val = 2 * r_val
        if shape == 'any':
            shape_text = "трапецию"
        elif shape == 'right':
            shape_text = "прямоугольную трапецию"
        else:
            shape_text = "равнобедренную трапецию"
        ask_text = (
            f"В {shape_text} вписана окружность радиуса \\({_ans(r_val)}\\). "
            f"Найдите высоту этой трапеции."
        )
        answer = _ans(h_val)
    else:
        # h → r = h/2. Берём чётное h или h, для которого r = X или X,5.
        h_options = list(range(2, 40))
        h_val = random.choice(h_options)
        r_val = h_val / 2
        # Родительный падеж: «Высота (чего?) трапеции/прямоугольной трапеции/...»
        if shape == 'any':
            shape_text = "трапеции"
        elif shape == 'right':
            shape_text = "прямоугольной трапеции"
        else:
            shape_text = "равнобедренной трапеции"
        ask_text = (
            f"Высота {shape_text}, описанной около окружности, равна \\({h_val}\\). "
            f"Найдите радиус этой окружности."
        )
        answer = _ans(r_val)

    # Картинка: выбираем углы точек касания под форму.
    if shape == 'any':
        # Несимметричная трапеция: точки касания боковых на разных углах.
        ab_t = random.randint(130, 160)
        cd_t = random.randint(20, 50)
        tang_angles = [ab_t, 90, cd_t, 270]
    elif shape == 'right':
        # Прямоугольная: одна боковая вертикальная.
        # Точка касания AB — на горизонтали через центр (180°), т.е. AB слева вертик.
        tang_angles = [180, 90, random.randint(20, 50), 270]
    else:
        # Равнобедренная: симметричные углы относительно вертикальной оси.
        t = random.randint(135, 160)
        tang_angles = [t, 90, 180 - t, 270]

    O = (160, 125)
    R_px = 55
    A, B, C, D = _build_circumscribed_quad(tang_angles, O, R_px)

    body = _circle(O, R_px)
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
    random.seed(10)
    for i in range(5):
        t = generate_task()
        print(f"[G10 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G11: R описанной около прямоугольного треугольника = c/2 (тип 14)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G11 = PLOTTER + r'''

_PYTH_G11 = []
for _m in range(2, 15):
    for _n in range(1, _m):
        if (_m - _n) % 2 == 1 and math.gcd(_m, _n) == 1:
            _a0 = _m * _m - _n * _n
            _b0 = 2 * _m * _n
            _c0 = _m * _m + _n * _n
            for _k in range(1, 101):
                if _c0 * _k > 100:
                    break
                _PYTH_G11.append((sorted([_a0 * _k, _b0 * _k])[0],
                                  sorted([_a0 * _k, _b0 * _k])[1],
                                  _c0 * _k))


def generate_task():
    """R описанной около прямоугольного треугольника = c/2.
    Подтипы:
      - 'legs': даны два катета (пифагорова тройка) → R
      - 'leg_hyp': дан катет и гипотенуза (катет < c, произвольные) → R
      - 'hyp_only': дана только гипотенуза → R = c/2
      - 'inverse': дан R → c = 2R
    """
    subtype = random.choice(['legs', 'leg_hyp', 'hyp_only', 'inverse'])

    if subtype == 'legs':
        a, b, c = random.choice(_PYTH_G11)
        if random.random() < 0.5:
            AC, BC = a, b
        else:
            AC, BC = b, a
        ask_text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AC = {AC}\\), \\(BC = {BC}\\). Найдите радиус описанной "
            f"около этого треугольника окружности."
        )
        R_val = c / 2
        answer = _ans(R_val)

    elif subtype == 'leg_hyp':
        # Произвольные: c ∈ [6, 50] (чётное чтобы R целое), катет < c.
        c = random.choice([n for n in range(6, 51) if n % 2 == 0])
        leg = random.randint(2, c - 1)
        AC, BC = c, leg  # неважно, какой именно катет упомянут (катет = leg)
        which_leg = random.choice(['AC', 'BC'])
        if which_leg == 'AC':
            ask_text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(AC = {leg}\\), \\(AB = {c}\\). Найдите радиус описанной "
                f"около этого треугольника окружности."
            )
        else:
            ask_text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {leg}\\), \\(AB = {c}\\). Найдите радиус описанной "
                f"около этого треугольника окружности."
            )
        answer = _ans(c / 2)
        AC, BC = leg, math.sqrt(c * c - leg * leg)  # для рисунка

    elif subtype == 'hyp_only':
        c = random.choice([n for n in range(4, 51) if n % 2 == 0])
        ask_text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AB = {c}\\). Найдите радиус описанной около этого "
            f"треугольника окружности."
        )
        answer = _ans(c / 2)
        # Для рисунка — произвольный острый угол
        ang = random.randint(25, 65)
        AC = c * math.cos(math.radians(ang))
        BC = c * math.sin(math.radians(ang))

    else:  # inverse
        R_val = random.randint(2, 30)
        ask_text = (
            f"Радиус описанной около прямоугольного треугольника окружности "
            f"равен \\({R_val}\\). Найдите гипотенузу этого треугольника."
        )
        answer = str(2 * R_val)
        # Для рисунка
        c = 2 * R_val
        ang = random.randint(25, 65)
        AC = c * math.cos(math.radians(ang))
        BC = c * math.sin(math.radians(ang))

    # Картинка: окружность с диаметром AB, C на верхней полуокружности.
    # Центр O НЕ показываем.
    O = (160, 130)
    R_px = 78
    A = _pt_on_circle(O, R_px, 180)
    B = _pt_on_circle(O, R_px, 0)
    angA_deg = math.degrees(math.atan2(BC, AC)) if AC > 0 else 45
    C = _pt_on_circle(O, R_px, 2 * angA_deg)

    body = _circle(O, R_px)
    body += _segment(A, B) + _segment(A, C) + _segment(B, C)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(11)
    for i in range(5):
        t = generate_task()
        print(f"[G11 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G12: Теорема синусов R = AB / (2 sin C) (типы 18, 19)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G12 = PLOTTER + r'''

def _fmt_sqrt(coef, rad):
    """Форматирует k·√n. rad ∈ {2, 3} (или None для просто числа).
    Если coef == 0 → "0". Если rad is None → str(coef).
    """
    if rad is None or rad == 1:
        return str(coef) if coef == int(coef) else _ans(coef)
    # coef·√rad
    if coef == int(coef):
        coef = int(coef)
    if coef == 1:
        return f"√{rad}"
    return f"{coef}√{rad}"


def _fmt_in_cond(k, rad):
    """Форматирует k·√rad для условия задачи. rad ∈ {1,2,3}."""
    if rad == 1 or rad is None:
        return str(k)
    if k == 1:
        return f"\sqrt{{{rad}}}"
    return f"{k}\sqrt{{{rad}}}"


def generate_task():
    """Теорема синусов: AB / sin C = 2R ⇒ R = AB / (2 sin C).
    В ОГЭ ответ ВСЕГДА целый/конечная десятичная дробь, поэтому корни — в
    условии, а не в ответе.
      - Прямая (AB, ∠C → R): для C ∈ {30°, 150°} AB и R оба целые;
        для C ∈ {45°, 135°} AB = k√2 (в условии), R = k (целое);
        для C ∈ {60°, 120°} AB = k√3 (в условии), R = k (целое).
      - Обратная (R, ∠C → AB): только C ∈ {30°, 150°}, где AB = R (целое).
    """
    direction = random.choice(['forward', 'inverse'])

    if direction == 'forward':
        angle_C = random.choice([30, 45, 60, 120, 135, 150])
        k = random.randint(2, 20)
        if angle_C in (30, 150):
            AB_cond = str(k)
            AB_val = k
        elif angle_C in (45, 135):
            AB_cond = _fmt_in_cond(k, 2)
            AB_val = k * math.sqrt(2)
        else:  # 60, 120
            AB_cond = _fmt_in_cond(k, 3)
            AB_val = k * math.sqrt(3)
        R_val = k
        ask_text = (
            f"В треугольнике \(ABC\) сторона \(AB = {AB_cond}\), "
            f"угол \(C\) равен \({angle_C}°\). Найдите радиус "
            f"описанной около этого треугольника окружности."
        )
        answer = str(R_val)

    else:  # inverse: только 30°/150° (чтобы AB = R было целым)
        angle_C = random.choice([30, 150])
        R_val = random.randint(2, 25)
        AB_val = R_val
        ask_text = (
            f"В треугольнике \(ABC\) угол \(C\) равен \({angle_C}°\), "
            f"радиус описанной около этого треугольника окружности равен "
            f"\({R_val}\). Найдите \(AB\)."
        )
        answer = str(R_val)


    # Картинка: треугольник ABC, вписанный в окружность.
    # AB — хорда, ∠C опирается на дугу AB.
    O = (160, 125)
    R_px = 78
    # Угол ∠C = θ. Дуга AB, на которую опирается ∠C = 2θ.
    # Размещаем A и B симметрично сверху, по углам (90 ± θ) от центра.
    A = _pt_on_circle(O, R_px, 90 + angle_C)
    B = _pt_on_circle(O, R_px, 90 - angle_C)
    # C — на бОльшей дуге (внизу), произвольно.
    C = _pt_on_circle(O, R_px, 270 + random.choice([-15, 0, 15]))

    body = _circle(O, R_px)
    body += _segment(A, B) + _segment(A, C) + _segment(B, C)
    body += _angle_arc(C, A, B, label_text=f"{angle_C}°", R=22, label_offset=14, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(12)
    for i in range(5):
        t = generate_task()
        print(f"[G12 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G13: Формула S = pr (тип 22)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G13 = PLOTTER + r'''

def _build_inscribed_tri(tangent_angles, O=(160, 125), R=45):
    """Треугольник, образованный касательными к окружности в 3 точках."""
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
    A = _intersect_tangents(Ts[2], Ts[0])
    B = _intersect_tangents(Ts[0], Ts[1])
    C = _intersect_tangents(Ts[1], Ts[2])
    return A, B, C


def generate_task():
    """S = p·r, где p — полупериметр.
    Подтипы:
      - P_r: даны P и r → S = (P/2)·r
      - S_P: даны S и P → r = 2S/P
      - S_r: даны S и r → P = 2S/r
    """
    subtype = random.choice(['P_r', 'S_P', 'S_r'])

    if subtype == 'P_r':
        P = random.randint(8, 60)
        r = random.randint(1, 12)
        S = (P / 2) * r
        ask_text = (
            f"В треугольник вписана окружность радиуса \\({r}\\). "
            f"Периметр треугольника равен \\({P}\\). "
            f"Найдите площадь этого треугольника."
        )
        answer = _ans(S)

    elif subtype == 'S_P':
        # Хотим r целое: r = 2S/P, выбираем P чётное и S = P·r/2.
        r = random.randint(2, 12)
        P = random.choice([n for n in range(8, 61) if n % 2 == 0])
        S = (P // 2) * r
        ask_text = (
            f"Площадь треугольника равна \\({S}\\), периметр равен \\({P}\\). "
            f"Найдите радиус вписанной в этот треугольник окружности."
        )
        answer = str(r)

    else:  # S_r
        r = random.randint(2, 12)
        P = random.choice([n for n in range(8, 61)])
        S = (P / 2) * r
        if S != int(S):
            P = random.choice([n for n in range(8, 61) if n % 2 == 0])
            S = (P // 2) * r
        ask_text = (
            f"Площадь треугольника равна \\({_ans(S)}\\), радиус вписанной "
            f"в него окружности равен \\({r}\\). Найдите периметр этого "
            f"треугольника."
        )
        answer = str(P)

    # Картинка: треугольник с вписанной окружностью.
    # Три точки касания: возьмём разные углы для разнообразия.
    tang_angles = random.choice([
        [90, 210, 330],   # «правильный» треугольник
        [80, 200, 320],
        [100, 220, 340],
        [110, 200, 330],
    ])
    O = (160, 125)
    R_px = 45
    A, B, C = _build_inscribed_tri(tang_angles, O, R_px)

    body = _circle(O, R_px)
    body += _segment(A, B) + _segment(B, C) + _segment(C, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(13)
    for i in range(5):
        t = generate_task()
        print(f"[G13 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G14: Равносторонний треугольник, сторона → R / r / h (типы 15, 17, 20)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G14 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G15: Квадрат, связи a / R / r / d / S (типы 28, 29, 30, 31, 32)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G15 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G16: Квадрат, центр окружности на стороне (тип 10)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G16 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# G17: Прямоугольник через диагональ + sin угла → площадь (тип 33)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G17 = PLOTTER + r'''

# Пифагоровы тройки (a, b, c), c — диагональ
_PYTH_RECT = [
    (3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29),
    (9, 40, 41), (12, 35, 37), (11, 60, 61), (6, 8, 10), (10, 24, 26),
    (16, 30, 34), (15, 20, 25),
]


def generate_task():
    """Прямоугольник со сторонами a, b и диагональю d = √(a²+b²).
    sin (угол между диагональю и стороной a) = b/d.
    S = a·b.
    Условие: даны d и sin α = p/q (дробь). Найти S.
    """
    a, b, c = random.choice(_PYTH_RECT)
    # Выбираем, какая из сторон в знаменателе sin: sin = b/c (между диагональю и a).
    # Можно поменять роли a и b случайно.
    if random.random() < 0.5:
        a, b = b, a
    d = c
    sin_p, sin_q = b, c
    # Сократим дробь
    g = math.gcd(sin_p, sin_q)
    sin_p //= g
    sin_q //= g
    S_val = a * b
    ask_text = (
        f"Диагональ прямоугольника равна \\({d}\\), синус угла между диагональю "
        f"и одной из сторон равен \\(\\dfrac{{{sin_p}}}{{{sin_q}}}\\). "
        f"Найдите площадь этого прямоугольника."
    )
    answer = str(S_val)

    # Картинка: прямоугольник с диагональю и подписанным углом.
    # Масштабируем стороны так, чтобы помещалось в viewBox.
    max_side = max(a, b)
    scale = 140 / max_side
    w_px = a * scale
    h_px = b * scale
    O_view = (160, 125)
    A = (O_view[0] - w_px / 2, O_view[1] + h_px / 2)
    B = (O_view[0] + w_px / 2, O_view[1] + h_px / 2)
    C = (O_view[0] + w_px / 2, O_view[1] - h_px / 2)
    D = (O_view[0] - w_px / 2, O_view[1] - h_px / 2)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    # Диагональ AC
    body += _segment(A, C, width=1.4)
    # Угол при A между AB и AC: показываем дугу
    body += _angle_arc(A, B, C, R=18, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=12)
    body += _label_direction(B, "B", direction=(1, 1), offset=12)
    body += _label_direction(C, "C", direction=(1, -1), offset=12)
    body += _label_direction(D, "D", direction=(-1, -1), offset=12)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(17)
    for i in range(5):
        t = generate_task()
        print(f"[G17 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G18: Ромб через диагональ + tg угла → r вписанной (тип 34)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G18 = PLOTTER + r'''

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
'''


# ──────────────────────────────────────────────────────────────────────────────
# Регистрация
# ──────────────────────────────────────────────────────────────────────────────

# Группы (для раскрывающихся секций в UI):
GROUP_ANGLES        = 'Углы вписанные и центральные'
GROUP_RIGHT_INSC    = 'Прямоугольный треугольник и описанная окружность'
GROUP_QUAD_INSC     = 'Вписанный четырёхугольник'
GROUP_QUAD_DESC     = 'Описанный 4-угольник и вписанная окружность'
GROUP_R_S_FORMULAS  = 'Формулы радиусов и площадей'
GROUP_REGULAR_POLY  = 'Правильные четырёхугольники и связи'

# (order, gen_name, group, asg_title, code)
PROTOTYPES = [
    (1,  'OGE16: G1 — вписанный и центральный углы',           GROUP_ANGLES,       '∠AOB ↔ ∠ACB (одна дуга)',                       GEN_G1),
    (2,  'OGE16: G2 — два диаметра',                           GROUP_ANGLES,       'Два диаметра + вписанный угол',                 GEN_G2),
    (3,  'OGE16: G3 — вписанные углы через диаметр',           GROUP_ANGLES,       'Точки по разные стороны диаметра',              GEN_G3),
    (4,  'OGE16: G4 — центр описанной на стороне (углы)',      GROUP_RIGHT_INSC,   'AB — диаметр, ∠A ↔ ∠B',                         GEN_G4),
    (5,  'OGE16: G5 — центр описанной на стороне (катеты)',    GROUP_RIGHT_INSC,   'AB — диаметр, катеты через Пифагор',            GEN_G5),
    (6,  'OGE16: G6 — вписанный 4-уг., противоположные углы',  GROUP_QUAD_INSC,    '∠A + ∠C = 180°',                                GEN_G6),
    (7,  'OGE16: G7 — вписанный 4-уг., углы через равные дуги',GROUP_QUAD_INSC,    '∠ABD + ∠CAD → ∠ABC',                            GEN_G7),
    (8,  'OGE16: G8 — вписанная трапеция, углы',               GROUP_QUAD_INSC,    'Равнобедренная: ∠A = ∠D, ∠A + ∠B = 180°',       GEN_G8),
    (9,  'OGE16: G9 — описанный 4-уг.: a+c = b+d',             GROUP_QUAD_DESC,    'Три стороны → 4-я',                             GEN_G9),
    (10, 'OGE16: G10 — вписанная окружность в трапецию: h = 2r', GROUP_QUAD_DESC,  'r ↔ h',                                         GEN_G10),
    (11, 'OGE16: G11 — R описанной около прямоуг. треугольника', GROUP_RIGHT_INSC, 'R = c/2',                                       GEN_G11),
    (12, 'OGE16: G12 — теорема синусов R = AB/(2 sin C)',      GROUP_R_S_FORMULAS, 'C = 30/45/60/120/135/150°',                     GEN_G12),
    (13, 'OGE16: G13 — формула S = pr',                        GROUP_R_S_FORMULAS, 'P, r → S и обратно',                            GEN_G13),
    (14, 'OGE16: G14 — равносторонний треугольник: a → R, r, h',GROUP_R_S_FORMULAS,'a = k√3 → R = k, r = k/2, h = 3k/2',             GEN_G14),
    (15, 'OGE16: G15 — квадрат: a, R, r, d, S',                GROUP_REGULAR_POLY, 'Связи a — R — r — d — S',                       GEN_G15),
    (16, 'OGE16: G16 — квадрат + окружность с центром на стороне', GROUP_REGULAR_POLY, 'R = a√5/2',                                  GEN_G16),
    (17, 'OGE16: G17 — прямоугольник: диагональ + sin → S',    GROUP_REGULAR_POLY, 'Площадь через диагональ',                       GEN_G17),
    (18, 'OGE16: G18 — ромб: диагональ + tg → r',              GROUP_REGULAR_POLY, 'Вписанная окружность в ромб',                   GEN_G18),
]


class Command(BaseCommand):
    help = "Создаёт «Задание 16» (Окружность и круг)"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true')

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            course = Course.objects.get(slug='oge-maths')
        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR('Курс oge-maths не найден'))
            return
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )
        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 16').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 16',
            defaults={'order': 16, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 16:
            lesson.order = 16
            lesson.save(update_fields=['order'])
        existing_by_order = {a.order: a for a in lesson.assignments.all()}
        for order, gen_name, group, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={'generator_type': 'python_function',
                          'python_code': code, 'config': {}},
            )
            # Группу храним в description — UI группирует по этому полю.
            description = f'group: {group}'
            assign = existing_by_order.get(order)
            if assign:
                # title не перезаписываем — мог быть переименован вручную.
                assign.description = description
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'text_input'
                assign.required_correct = 3
                assign.save()
                shown_title = assign.title
            else:
                Assignment.objects.create(
                    lesson=lesson, order=order, title=asg_title, description=description,
                    assignment_type='test', answer_type='text_input',
                    required_correct=3, problem_generator=generator,
                )
                shown_title = asg_title
            self.stdout.write(self.style.SUCCESS(f'  + [{order}] {shown_title}'))
        self.stdout.write(self.style.SUCCESS(f'\nГотово: {len(PROTOTYPES)} прототипов.'))
