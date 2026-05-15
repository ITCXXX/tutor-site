# -*- coding: utf-8 -*-
"""
Management command: создаёт ProblemGenerator-ы и Assignment-ы под урок
«Задание 17» курса ОГЭ. Тема — «Четырёхугольники».

Архитектура (после анализа Школково /catalog/2524, 40 типов):
    G1.  PARALL_ONE_ANGLE      — один угол паралл. → больший/меньший (типы 1, 2)
    G2.  PARALL_DIAG_TWO_ANG   — диагональ + α, β → больший/меньший (3, 4)
    G3.  PARALL_DIAG_O         — диагонали в O → длина отрезка (5)
    G4.  PARALL_BISECTOR       — биссектриса → острый угол (6)
    G5.  PARALL_AREA_GRID      — площадь на клетке (7)
    G6.  PARALL_S_HEIGHT       — S + стороны → высоты (8, 9)
    G7.  RHOMBUS_ONE_ANGLE     — один угол ромба → больший/меньший (10, 11)
    G8.  RHOMBUS_DIAG_ANGLE    — диагональ делит угол (12)
    G9.  RHOMBUS_ANG_DIAG_HT   — углы через диагональ/высоту (13, 14, 15)
    G10. RHOMBUS_P_A_ANGLE     — P/a + угол → S/h (16, 17)
    G11. RHOMBUS_DIAG_TG       — диагональ + tg → S (18)
    G12. RECT_DIAGONAL         — прямоугольник: диагонали (19, 20)
    G13. SQUARE_SIDE_DIAG      — квадрат: сторона ↔ диагональ (21)
    G14. ISO_TRAP_ONE_ANGLE    — равнобедр. трапеция, один угол (22, 23)
    G15. ISO_TRAP_SUM_ANG      — сумма 2 углов (24, 25)
    G16. RIGHT_TRAP_ANG        — прямоуг. трапеция: углы (26, 27)
    G17. ISO_TRAP_COMPLEX_ANG  — сложные углы через диагональ/бисс. (28-31)
    G18. TRAP_MIDLINE_AREA     — основания → ср. линия / площадь (32-34)
    G19. ISO_TRAP_HEIGHT_BASE  — высота из вершины делит основание (35-38)
    G20. ISO_TRAP_BASE_ANG     — основания + угол → S/h (39, 40)

Стиль рисунков: ФИПИ-подобный.
    - viewBox 0 0 320 220
    - чёрный stroke #1f1f1f, толщина 1.5
    - шрифт Cambria/Georgia italic 16pt для вершин
    - кружочки r=2.5 на вершинах

Usage:
    python manage.py seed_oge17
    python manage.py seed_oge17 --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# PLOTTER — общие SVG-хелперы для четырёхугольников
# ──────────────────────────────────────────────────────────────────────────────

PLOTTER = r'''
import math
import random


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


def _label_direction(P, name, direction, offset=14, font_size=16, italic=True):
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


def _svg_wrap(body, w=320, h=220):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="Четырёхугольник" '
        f'style="display:block;margin:0.5em auto">{body}</svg>'
    )


def _make_parallelogram(angle_at_A_deg, AD_px=150, AB_px=85, anchor=(85, 175)):
    """Возвращает A, B, C, D — координаты паралл. (CW порядок).
    A — слева внизу, B — слева вверху, C — справа вверху, D — справа внизу.
    AD — нижнее основание (горизонтальное), AB — левая боковая.
    angle_at_A — угол при A между AD (вправо) и AB (вверх).
    """
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(angle_at_A_deg)
    Bx = A[0] + AB_px * math.cos(a)
    By = A[1] - AB_px * math.sin(a)
    B = (Bx, By)
    C = (D[0] + AB_px * math.cos(a), D[1] - AB_px * math.sin(a))
    return A, B, C, D
'''


# ──────────────────────────────────────────────────────────────────────────────
# G1: один угол параллелограмма → больший/меньший (типы 1, 2)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G1 = PLOTTER + r'''

def generate_task():
    """Один угол паралл. = α → больший / меньший."""
    target = random.choice(['larger', 'smaller'])
    alpha = random.choice([a for a in range(20, 161) if a != 90])
    other = 180 - alpha
    larger = max(alpha, other)
    smaller = min(alpha, other)
    ans_val = larger if target == 'larger' else smaller
    text_target = 'больший' if target == 'larger' else 'меньший'
    ask_text = (
        f"Один из углов параллелограмма равен \({alpha}°\). "
        f"Найдите {text_target} угол этого параллелограмма. "
        f"Ответ дайте в градусах."
    )
    answer = str(ans_val)

    # Картинка: A — низ-лево, B — верх-лево (через боковую), C — верх-право, D — низ-право.
    if alpha <= 90:
        A, B, C, D = _make_parallelogram(alpha)
    else:
        # Тупой угол при A → B будет левее A. Сместим якорь правее.
        A, B, C, D = _make_parallelogram(alpha, anchor=(135, 175))

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    # Дуга при A между AD (вправо) и AB (вверх-наклон)
    body += _angle_arc(A, D, B, label_text=f"{alpha}°", R=24, label_offset=14, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(1)
    for i in range(5):
        t = generate_task()
        print(f"[G1 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G2: диагональ паралл. + α, β со сторонами → больший/меньший (типы 3, 4)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G2 = PLOTTER + r'''

def generate_task():
    """Диагональ паралл. делит ∠A на α и β (с двумя сторонами). ∠A = α + β."""
    target = random.choice(['larger', 'smaller'])
    # α, β — острые углы (между диагональю и сторонами), α + β = ∠A.
    while True:
        alpha = random.randint(15, 75)
        beta = random.randint(15, 75)
        ang_A = alpha + beta
        if 35 <= ang_A <= 145 and ang_A != 90:
            break
    other = 180 - ang_A
    larger = max(ang_A, other)
    smaller = min(ang_A, other)
    ans_val = larger if target == 'larger' else smaller
    text_target = 'больший' if target == 'larger' else 'меньший'
    ask_text = (
        f"Диагональ параллелограмма образует с его сторонами углы, равные "
        f"\({alpha}°\) и \({beta}°\). Найдите {text_target} угол этого "
        f"параллелограмма. Ответ дайте в градусах."
    )
    answer = str(ans_val)

    # Картинка: паралл. ABCD (A низ-лево, B верх-лево, C верх-право, D низ-право).
    # Диагональ AC + дуги α (между AC и AD) и β (между AC и AB) при A.
    if ang_A <= 90:
        A, B, C, D = _make_parallelogram(ang_A)
    else:
        A, B, C, D = _make_parallelogram(ang_A, anchor=(135, 175))

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.4)  # диагональ
    # α — между AC и AD (нижний кусочек угла A)
    body += _angle_arc(A, D, C, label_text=f"{alpha}°", R=20, label_offset=12, arcs=1)
    # β — между AC и AB (верхний кусочек)
    body += _angle_arc(A, C, B, label_text=f"{beta}°", R=32, label_offset=12, arcs=2)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(2)
    for i in range(5):
        t = generate_task()
        print(f"[G2 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G3: диагонали паралл. в O → длина отрезка (тип 5)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G3 = PLOTTER + r'''

def generate_task():
    """Диагонали AC и BD паралл. ABCD пересекаются в O. Даны AC, BD, AB.
    Найти DO или AO (= половина одной из диагоналей). AB — лишняя информация.
    """
    target = random.choice(['AO', 'DO'])
    # Чётные AC, BD — чтобы половины были целыми
    AC = random.choice([n for n in range(6, 41) if n % 2 == 0])
    BD = random.choice([n for n in range(6, 41) if n % 2 == 0 and n != AC])
    AB = random.randint(3, 20)

    if target == 'AO':
        ans_val = AC // 2
        ask_text = (
            f"Диагонали \(AC\) и \(BD\) параллелограмма \(ABCD\) пересекаются "
            f"в точке \(O\), \(AC = {AC}\), \(BD = {BD}\), \(AB = {AB}\). "
            f"Найдите \(AO\)."
        )
    else:
        ans_val = BD // 2
        ask_text = (
            f"Диагонали \(AC\) и \(BD\) параллелограмма \(ABCD\) пересекаются "
            f"в точке \(O\), \(AC = {AC}\), \(BD = {BD}\), \(AB = {AB}\). "
            f"Найдите \(DO\)."
        )
    answer = str(ans_val)

    # Картинка: паралл. + обе диагонали + точка O в центре.
    A, B, C, D = _make_parallelogram(70)  # умеренный наклон
    O = (
        (A[0] + B[0] + C[0] + D[0]) / 4,
        (A[1] + B[1] + C[1] + D[1]) / 4,
    )

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.4) + _segment(B, D, width=1.4)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _vertex_dot(O)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(O, "O", direction=(0, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(3)
    for i in range(5):
        t = generate_task()
        print(f"[G3 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G4: биссектриса паралл. → острый угол (тип 6)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G4 = PLOTTER + r'''

def generate_task():
    """Биссектриса угла A паралл. пересекает сторону BC под углом α.
    Острый угол паралл. = 2α (для α < 45°).
    """
    # α ∈ [10°, 44°] чтобы острый угол = 2α оставался острым (< 90°)
    alpha = random.randint(10, 44)
    ang_A = 2 * alpha   # это и есть острый угол паралл.
    ans_val = ang_A
    ask_text = (
        f"Найдите острый угол параллелограмма \(ABCD\), если биссектриса "
        f"угла \(A\) образует со стороной \(BC\) угол, равный \({alpha}°\). "
        f"Ответ дайте в градусах."
    )
    answer = str(ans_val)

    # Картинка: паралл. ABCD + биссектриса AE из A в точку E на стороне BC.
    A, B, C, D = _make_parallelogram(ang_A)
    # Биссектриса делит угол A пополам. Луч из A под углом (ang_A / 2) к AD.
    bis_dir_rad = math.radians(ang_A / 2)
    # Длинный луч из A, найдём пересечение с прямой BC.
    # BC — это отрезок от B до C. Параметризуем: P(t) = B + t·(C - B), t ∈ [0,1].
    # Луч A + s·(cos bis, -sin bis). Найдём пересечение.
    bcx, bcy = C[0] - B[0], C[1] - B[1]
    dx_bis, dy_bis = math.cos(bis_dir_rad), -math.sin(bis_dir_rad)
    # A + s·(dx, dy) = B + t·(bcx, bcy)
    # s·dx - t·bcx = B[0] - A[0]
    # s·dy - t·bcy = B[1] - A[1]
    det = dx_bis * (-bcy) - dy_bis * (-bcx)
    if abs(det) > 1e-9:
        rhs1 = B[0] - A[0]
        rhs2 = B[1] - A[1]
        s = (rhs1 * (-bcy) - rhs2 * (-bcx)) / det
        t = (dx_bis * rhs2 - dy_bis * rhs1) / det
        E = (A[0] + s * dx_bis, A[1] + s * dy_bis)
    else:
        E = _midpoint(B, C)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, E, width=1.3)  # биссектриса
    # Равные дуги при A: углы BAE и EAD (биссектриса делит ∠A пополам)
    body += _angle_arc(A, B, E, R=16, arcs=1)
    body += _angle_arc(A, E, D, R=16, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _vertex_dot(E)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(E, "E", direction=(0, -1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(4)
    for i in range(5):
        t = generate_task()
        print(f"[G4 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G5: Площадь параллелограмма с проведённой высотой (тип 7)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G5 = PLOTTER + r'''

# (катет_основания, высота, гипотенуза-боковая) — пифагоровы тройки
_PYTH_G5 = [
    (3, 4, 5), (4, 3, 5),
    (5, 12, 13), (12, 5, 13),
    (8, 15, 17), (15, 8, 17),
    (6, 8, 10), (8, 6, 10),
    (9, 12, 15), (12, 9, 15),
    (7, 24, 25),
]


def generate_task():
    """Параллелограмм с проведённой высотой из вершины (например, C) на AD.
    Подножие H делит AD на 2 куска: AH и HD. На картинке подписаны:
      h (высота), c (боковая сторона), AH, HD.
    Используем пифагорову тройку (HD, h, c). AH — отдельный целый параметр.
    Площадь = AD · h = (AH + HD) · h.
    """
    HD_arc, h_val, c_val = random.choice(_PYTH_G5)
    AH_val = random.randint(2, 10)
    AD_val = AH_val + HD_arc
    S_val = AD_val * h_val
    ask_text = "Найдите площадь параллелограмма, изображённого на рисунке."
    answer = str(S_val)

    # Картинка
    # Параллелограмм наклонён так, что верхняя левая вершина (B) сдвинута влево
    # от A на HD_arc единиц (s = -HD_arc), высота = h_val.
    # Тогда проекция C (верхняя правая) на AD попадает в точку H = (AD - HD_arc)·scale
    # от A. AH = AD - HD_arc = AH_val ✓.
    viewbox_w, viewbox_h = 320, 220
    margin = 28
    avail_w = viewbox_w - 2 * margin
    avail_h = viewbox_h - 2 * margin
    # Габариты фигуры в логических единицах:
    #   ширина = AD_val + HD_arc (B сдвинут на HD_arc влево от A)
    #   высота = h_val
    fig_w_units = AD_val + HD_arc
    fig_h_units = h_val
    scale = min(avail_w / fig_w_units, avail_h / fig_h_units)

    # Якорь: A справа от B. Поместим всю фигуру по центру.
    # Координаты в единицах:
    #   A_u = (HD_arc, 0)      ← сдвинут вправо на HD_arc от левого края
    #   D_u = (HD_arc + AD_val, 0)
    #   B_u = (0, h_val)       ← левый верхний (sдвинут на HD_arc влево от A)
    #   C_u = (AD_val, h_val)
    #   H_u = (HD_arc + AH_val, 0) — подножие высоты из C на AD
    total_w_px = fig_w_units * scale
    total_h_px = fig_h_units * scale
    x_origin = (viewbox_w - total_w_px) / 2
    y_origin = (viewbox_h - total_h_px) / 2 + total_h_px  # SVG y инвертирован

    def _u(ux, uy):
        return (x_origin + ux * scale, y_origin - uy * scale)

    A = _u(HD_arc, 0)
    D = _u(HD_arc + AD_val, 0)
    B = _u(0, h_val)
    C = _u(AD_val, h_val)
    H = _u(HD_arc + AH_val, 0)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(C, H, dashed=False, width=1.3)  # высота
    # Маркер прямого угла при H
    sq = 9
    # AD идёт вправо (вектор +x). Перпендикуляр в H идёт ВВЕРХ (-y в SVG).
    body += (
        f'<polyline points="{H[0]-sq:.1f},{H[1]:.1f} {H[0]-sq:.1f},{H[1]-sq:.1f} '
        f'{H[0]:.1f},{H[1]-sq:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )

    # Подписи: h (высота), c (боковая CD), AH, HD
    # Высота — посередине CH, слева от линии
    mid_CH = ((C[0] + H[0]) / 2, (C[1] + H[1]) / 2)
    body += (
        f'<text x="{mid_CH[0] - 12:.1f}" y="{mid_CH[1] + 5:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="15" '
        f'fill="#1f1f1f" text-anchor="middle">{h_val}</text>'
    )
    # Боковая CD — посередине CD, справа от отрезка
    mid_CD = ((C[0] + D[0]) / 2, (C[1] + D[1]) / 2)
    body += (
        f'<text x="{mid_CD[0] + 14:.1f}" y="{mid_CD[1] + 5:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="15" '
        f'fill="#1f1f1f" text-anchor="middle">{c_val}</text>'
    )
    # AH — посередине AH, под AD
    body += (
        f'<text x="{(A[0]+H[0])/2:.1f}" y="{A[1] + 18:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="15" '
        f'fill="#1f1f1f" text-anchor="middle">{AH_val}</text>'
    )
    # HD
    body += (
        f'<text x="{(H[0]+D[0])/2:.1f}" y="{H[1] + 18:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="15" '
        f'fill="#1f1f1f" text-anchor="middle">{HD_arc}</text>'
    )

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(5)
    for i in range(5):
        t = generate_task()
        print(f"[G5 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G6: S + стороны → большая/меньшая высота (типы 8, 9)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G6 = PLOTTER + r'''

def generate_task():
    """Площадь паралл. = S, две стороны a < b. Найти большую/меньшую высоту.
    h_большая = S/a (к меньшей стороне); h_меньшая = S/b (к большей).
    """
    target = random.choice(['larger', 'smaller'])
    for _ in range(100):
        a = random.randint(2, 12)
        b = random.randint(a + 2, 22)
        h_a = random.randint(2, 12)
        S_val = a * h_a
        h_b = S_val / b
        if h_b == int(h_b) and h_b >= 1:
            h_b = int(h_b)
            break
    else:
        a, b, S_val, h_a, h_b = 5, 10, 40, 8, 4

    if target == 'larger':
        ans_val = h_a
        text_target = 'большую'
    else:
        ans_val = h_b
        text_target = 'меньшую'

    ask_text = (
        f"Площадь параллелограмма равна \({S_val}\), а две его стороны "
        f"равны \({a}\) и \({b}\). Найдите его высоты. В ответе укажите "
        f"{text_target} высоту."
    )
    answer = str(ans_val)

    # Картинка: паралл. + ДВЕ высоты из B — на AD и на продолжение CD.
    A, B, C, D = _make_parallelogram(70)
    # Высота BH1 на прямую AD (нижнюю): проекция B на AD (горизонталь через A)
    H1 = (B[0], A[1])
    # Высота BH2 на прямую CD: CD идёт от C к D. Проекция B на прямую CD.
    cdx, cdy = D[0] - C[0], D[1] - C[1]
    cdL2 = cdx * cdx + cdy * cdy
    t_proj = ((B[0] - C[0]) * cdx + (B[1] - C[1]) * cdy) / cdL2
    H2 = (C[0] + t_proj * cdx, C[1] + t_proj * cdy)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(B, H1, dashed=True, width=1.3)
    body += _segment(B, H2, dashed=True, width=1.3)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _vertex_dot(H1) + _vertex_dot(H2)
    # Маркеры прямых углов
    sq = 8
    # H1 на AD (горизонталь). Внутренняя нормаль вверх.
    body += (
        f'<polyline points="{H1[0]:.1f},{H1[1]-sq:.1f} {H1[0]+sq:.1f},{H1[1]-sq:.1f} '
        f'{H1[0]+sq:.1f},{H1[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    # H2 на CD — маркер прямого угла вдоль CD и BH2
    import math as _m
    # Нормированный CD-вектор
    cdn = _m.hypot(cdx, cdy)
    ux, uy = cdx / cdn, cdy / cdn
    # Перпендикуляр к CD (внутрь паралл., к B)
    px, py = -uy, ux
    # Проверим направление
    if (B[0] - H2[0]) * px + (B[1] - H2[1]) * py < 0:
        px, py = -px, -py
    p1 = (H2[0] + ux * sq, H2[1] + uy * sq)
    p2 = (p1[0] + px * sq, p1[1] + py * sq)
    p3 = (H2[0] + px * sq, H2[1] + py * sq)
    body += (
        f'<polyline points="{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} '
        f'{p3[0]:.1f},{p3[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )

    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(H1, "H", direction=(0, 1), offset=14)
    body += _label_direction(H2, "K", direction=(1, 0), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(6)
    for i in range(5):
        t = generate_task()
        print(f"[G6 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G7: один угол ромба → больший/меньший (типы 10, 11)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G7 = PLOTTER + r'''

def _make_rhombus(angle_at_A_deg, side_px=110, anchor=(105, 175)):
    """Ромб ABCD (CW): A низ-лево, B верх-лево, C верх-право, D низ-право.
    AD и AB — обе стороны = side_px. AD горизонтальное.
    """
    A = anchor
    D = (A[0] + side_px, A[1])
    a = math.radians(angle_at_A_deg)
    Bx = A[0] + side_px * math.cos(a)
    By = A[1] - side_px * math.sin(a)
    B = (Bx, By)
    C = (D[0] + side_px * math.cos(a), D[1] - side_px * math.sin(a))
    return A, B, C, D


def generate_task():
    """Один угол ромба = α → больший / меньший."""
    target = random.choice(['larger', 'smaller'])
    alpha = random.choice([a for a in range(20, 161) if a != 90])
    other = 180 - alpha
    larger = max(alpha, other)
    smaller = min(alpha, other)
    ans_val = larger if target == 'larger' else smaller
    text_target = 'больший' if target == 'larger' else 'меньший'
    ask_text = (
        f"Один из углов ромба равен \({alpha}°\). "
        f"Найдите {text_target} угол этого ромба. Ответ дайте в градусах."
    )
    answer = str(ans_val)

    if alpha <= 90:
        A, B, C, D = _make_rhombus(alpha)
    else:
        A, B, C, D = _make_rhombus(alpha, anchor=(155, 175))

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _angle_arc(A, D, B, label_text=f"{alpha}°", R=24, label_offset=14, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(7)
    for i in range(5):
        t = generate_task()
        print(f"[G7 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G8: В ромбе ∠ABC = α → ∠ACD (диагональ делит угол) (тип 12)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G8 = PLOTTER + r'''

def _make_rhombus(angle_at_A_deg, side_px=110, anchor=(105, 175)):
    A = anchor
    D = (A[0] + side_px, A[1])
    a = math.radians(angle_at_A_deg)
    Bx = A[0] + side_px * math.cos(a)
    By = A[1] - side_px * math.sin(a)
    B = (Bx, By)
    C = (D[0] + side_px * math.cos(a), D[1] - side_px * math.sin(a))
    return A, B, C, D


def generate_task():
    """В ромбе ∠ABC = α. Найти ∠ACD = (180° − α) / 2.
    Чтобы ответ был целым, α — чётное.
    """
    alpha = random.choice([n for n in range(20, 171) if n != 90])
    # ans может быть полуцелым при нечётном α
    ans_raw = (180 - alpha) / 2
    if ans_raw == int(ans_raw):
        ans_val = str(int(ans_raw))
    else:
        s = f"{ans_raw:.2f}".rstrip("0").rstrip(".")
        ans_val = s.replace(".", ",")
    ask_text = (
        f"В ромбе \(ABCD\) угол \(ABC\) равен \({alpha}°\). "
        f"Найдите угол \(ACD\). Ответ дайте в градусах."
    )
    answer = ans_val

    # Геометрия: ∠ABC = α (угол при B). Это угол при верхней-левой вершине B.
    # В нашей параметризации _make_rhombus задаётся ∠A. Соседние углы ромба:
    # ∠A + ∠B = 180°. Значит ∠A = 180° − α.
    ang_A = 180 - alpha
    if ang_A <= 90:
        A, B, C, D = _make_rhombus(ang_A)
    else:
        A, B, C, D = _make_rhombus(ang_A, anchor=(155, 175))

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.4)  # диагональ AC
    # Дуга ∠ABC при B
    body += _angle_arc(B, A, C, label_text=f"{alpha}°", R=22, label_offset=12, arcs=1)
    # Искомый ∠ACD при C — дуга без подписи (2 штриха для отличия)
    body += _angle_arc(C, A, D, R=22, arcs=2)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(8)
    for i in range(5):
        t = generate_task()
        print(f"[G8 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G9: ромб — угол между стороной и меньшей диагональю (тип 13)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G9 = PLOTTER + r'''

def _make_rhombus(angle_at_A_deg, side_px=110, anchor=(105, 175)):
    A = anchor
    D = (A[0] + side_px, A[1])
    a = math.radians(angle_at_A_deg)
    Bx = A[0] + side_px * math.cos(a)
    By = A[1] - side_px * math.sin(a)
    B = (Bx, By)
    C = (D[0] + side_px * math.cos(a), D[1] - side_px * math.sin(a))
    return A, B, C, D


def generate_task():
    """Острый угол ромба = α. Угол между стороной и меньшей диагональю.
    Меньшая диагональ соединяет ТУПЫЕ углы и делит каждый из них пополам.
    Угол между стороной и меньшей диагональю = (180° − α) / 2.
    """
    # α — острый, любое целое от 10° до 88°. Чтобы ответ был целым, α — чётное;
    # допустим и нечётное (тогда ответ — десятичная дробь).
    alpha = random.randint(10, 88)
    ans_raw = (180 - alpha) / 2
    if ans_raw == int(ans_raw):
        answer = str(int(ans_raw))
    else:
        s = f"{ans_raw:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"Острый угол ромба равен \({alpha}°\). "
        f"Сколько градусов составляет угол между стороной и меньшей "
        f"диагональю ромба?"
    )

    # Картинка: ромб с острым углом α при A. Меньшая диагональ — BD (соединяет
    # тупые углы B и D). Дуга при B между BA и BD (искомый угол).
    A, B, C, D = _make_rhombus(alpha)
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(B, D, width=1.4)
    body += _angle_arc(A, D, B, label_text=f"{alpha}°", R=22, label_offset=14, arcs=1)
    body += _angle_arc(B, A, D, R=20, arcs=2)  # искомый угол — 2 штриха
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(9)
    for i in range(5):
        t = generate_task()
        print(f"[G9 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G10: ромб — перпендикуляр из O на сторону + ∠ с диагональю β → острый ∠ (14)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G10 = PLOTTER + r'''

def _rhombus_crystal():
    """Статичный ромб-«кристалл»: A верх, B право, C низ, D лево.
    Большая диагональ AC — вертикальная.
    """
    return (
        (160, 30),    # A — верх
        (260, 115),   # B — право (тупой)
        (160, 200),   # C — низ
        (60, 115),    # D — лево (тупой)
    )


def _foot(P, A, B):
    ax, ay = A; bx, by = B
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = ((P[0] - ax) * dx + (P[1] - ay) * dy) / L2
    return (ax + t * dx, ay + t * dy)


def generate_task():
    """Перпендикуляр из O (центр ромба) на сторону образует с одной из
    диагоналей угол β. Острый угол ромба = 2β.
    """
    beta = random.randint(10, 44)
    ans_val = 2 * beta
    ask_text = (
        f"Перпендикуляр, проведённый из точки пересечения диагоналей ромба "
        f"к его стороне, образует с одной из его диагоналей угол \({beta}°\). "
        f"Сколько градусов составляет острый угол ромба?"
    )
    answer = str(ans_val)

    # Картинка: статичный ромб-«кристалл» (одинаковый для всех чисел).
    A, B, C, D = _rhombus_crystal()
    O = ((A[0] + C[0]) / 2, (A[1] + C[1]) / 2)
    # Перпендикуляр OP на сторону AB (правая верхняя).
    P = _foot(O, A, B)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.3) + _segment(B, D, width=1.3)  # обе диагонали
    body += _segment(O, P, dashed=True, width=1.3)
    body += _vertex_dot(O) + _vertex_dot(P)

    # Маркер прямого угла в P (между AB и OP)
    sq = 7
    abx, aby = B[0] - A[0], B[1] - A[1]
    abL = math.hypot(abx, aby)
    ux, uy = abx / abL, aby / abL
    px, py = -uy, ux
    if (O[0] - P[0]) * px + (O[1] - P[1]) * py < 0:
        px, py = -px, -py
    p1 = (P[0] + ux * sq, P[1] + uy * sq)
    p2 = (p1[0] + px * sq, p1[1] + py * sq)
    p3 = (P[0] + px * sq, P[1] + py * sq)
    body += (
        f'<polyline points="{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} '
        f'{p3[0]:.1f},{p3[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )

    # Дуга β при O между OP и OB (правая диагональ — ближайшая)
    body += _angle_arc(O, B, P, label_text=f"{beta}°", R=15, label_offset=10, arcs=1)

    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(0, -1), offset=14)
    body += _label_direction(B, "B", direction=(1, 0), offset=14)
    body += _label_direction(C, "C", direction=(0, 1), offset=14)
    body += _label_direction(D, "D", direction=(-1, 0), offset=14)
    body += _label_direction(O, "O", direction=(-1, -0.4), offset=12)
    body += _label_direction(P, "P", direction=(1, -0.4), offset=12)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(10)
    for i in range(5):
        t = generate_task()
        print(f"[G10 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G11: ромб — угол между высотой и большей диагональю (тип 15)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G11 = PLOTTER + r'''

def _rhombus_crystal():
    """Статичный ромб-«кристалл»: A верх (острый), B право (тупой), C низ (острый), D лево (тупой)."""
    return (
        (160, 30),
        (260, 115),
        (160, 200),
        (60, 115),
    )


def _foot(P, A, B):
    ax, ay = A; bx, by = B
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = ((P[0] - ax) * dx + (P[1] - ay) * dy) / L2
    return (ax + t * dx, ay + t * dy)


def generate_task():
    """Дан один угол ромба α. Угол между высотой и большей диагональю
    = 90° − острый/2, где острый = min(α, 180°−α).
    """
    alpha = random.choice([n for n in range(20, 161) if n != 90])
    acute = min(alpha, 180 - alpha)
    ans_raw = 90 - acute / 2
    if ans_raw == int(ans_raw):
        answer = str(int(ans_raw))
    else:
        s = f"{ans_raw:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"Один из углов ромба равен \({alpha}°\). "
        f"Сколько градусов составляет угол между высотой и большей "
        f"диагональю ромба?"
    )

    # Картинка: статичный ромб-«кристалл». Тупой угол при B (справа) выделен дугой.
    # Высота из D (левый тупой) на правую нижнюю сторону BC.
    # Большая диагональ AC (вертикальная).
    A, B, C, D = _rhombus_crystal()
    H = _foot(D, B, C)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.4)  # большая диагональ (сверху вниз)
    body += _segment(D, H, dashed=True, width=1.3)  # высота из D на BC
    body += _vertex_dot(H)

    # Маркер прямого угла в H
    sq = 7
    bcx, bcy = C[0] - B[0], C[1] - B[1]
    bcL = math.hypot(bcx, bcy)
    ux, uy = bcx / bcL, bcy / bcL
    # Перпендикуляр к BC — направление, в котором D
    px, py = -uy, ux
    if (D[0] - H[0]) * px + (D[1] - H[1]) * py < 0:
        px, py = -px, -py
    p1 = (H[0] + ux * sq, H[1] + uy * sq)
    p2 = (p1[0] + px * sq, p1[1] + py * sq)
    p3 = (H[0] + px * sq, H[1] + py * sq)
    body += (
        f'<polyline points="{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} '
        f'{p3[0]:.1f},{p3[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )

    # Выделяем тупой угол при B (справа) — дугой с подписью α (если α тупой)
    # или 180−α (если α острый — рисуем тогда тупой = 180-α).
    obtuse_label = alpha if alpha > 90 else (180 - alpha)
    body += _angle_arc(B, A, C, label_text=f"{obtuse_label}°", R=22, label_offset=14, arcs=1)

    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(0, -1), offset=14)
    body += _label_direction(B, "B", direction=(1, 0), offset=14)
    body += _label_direction(C, "C", direction=(0, 1), offset=14)
    body += _label_direction(D, "D", direction=(-1, 0), offset=14)
    body += _label_direction(H, "H", direction=(1, 0.5), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(11)
    for i in range(5):
        t = generate_task()
        print(f"[G11 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G12: ромб — периметр + угол → площадь (тип 16)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G12 = PLOTTER + r'''

def _make_rhombus(angle_at_A_deg, side_px=110, anchor=(105, 175)):
    A = anchor
    D = (A[0] + side_px, A[1])
    a = math.radians(angle_at_A_deg)
    Bx = A[0] + side_px * math.cos(a)
    By = A[1] - side_px * math.sin(a)
    B = (Bx, By)
    C = (D[0] + side_px * math.cos(a), D[1] - side_px * math.sin(a))
    return A, B, C, D


def generate_task():
    """Периметр ромба = P, один угол = α (30° или 150°, sin = 0,5).
    Сторона a = P/4. Площадь S = a²·sin α = a²/2.
    Чтобы ответ был чистым (целое или X,5), P должен быть кратен 4
    (тогда a — целое, S = a²/2 целое или полу-целое).
    """
    angle = random.choice([30, 150])
    P_val = random.choice(list(range(8, 81, 4)))   # P ∈ {8, 12, 16, ..., 80}
    a_val = P_val // 4                              # целое
    S_val = (a_val * a_val) / 2                     # целое или X,5
    if S_val == int(S_val):
        answer = str(int(S_val))
    else:
        # Округление до 2 знаков, обрезание нулей
        s = f"{S_val:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"Периметр ромба равен \({P_val}\), а один из углов равен "
        f"\({angle}°\). Найдите площадь этого ромба."
    )

    # Картинка: ромб с углом α при A.
    if angle <= 90:
        A, B, C, D = _make_rhombus(angle)
    else:
        A, B, C, D = _make_rhombus(angle, anchor=(155, 175))

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _angle_arc(A, D, B, label_text=f"{angle}°", R=22, label_offset=14, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(12)
    for i in range(5):
        t = generate_task()
        print(f"[G12 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G13: ромб — сторона + угол → высота (тип 17)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G13 = PLOTTER + r'''

def _make_rhombus(angle_at_A_deg, side_px=110, anchor=(105, 175)):
    A = anchor
    D = (A[0] + side_px, A[1])
    a = math.radians(angle_at_A_deg)
    Bx = A[0] + side_px * math.cos(a)
    By = A[1] - side_px * math.sin(a)
    B = (Bx, By)
    C = (D[0] + side_px * math.cos(a), D[1] - side_px * math.sin(a))
    return A, B, C, D


def _foot(P, A, B):
    ax, ay = A; bx, by = B
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = ((P[0] - ax) * dx + (P[1] - ay) * dy) / L2
    return (ax + t * dx, ay + t * dy)


def generate_task():
    """Сторона ромба = a, один угол α. Высота h = a·sin α.
       Углы (с поддержкой корней в условии для целого ответа):
         α=30°/150°: sin=1/2 → a целое → h=a/2 (X или X,5).
         α=45°/135°: sin=√2/2 → a=k√2 в условии → h=k (целое).
         α=60°/120°: sin=√3/2 → a=k√3 в условии → h=3k/2 (X или X,5).
    """
    angle = random.choice([30, 45, 60, 120, 135, 150])
    if angle in (30, 150):
        a_val = random.randint(3, 50)
        h_val = a_val / 2
        a_cond = str(a_val)
    elif angle in (45, 135):
        k = random.randint(2, 25)
        h_val = k
        a_cond = (f"\\sqrt{{2}}" if k == 1 else f"{k}\\sqrt{{2}}")
    else:  # 60 / 120
        k = random.randint(2, 20)
        h_val = 3 * k / 2
        a_cond = (f"\\sqrt{{3}}" if k == 1 else f"{k}\\sqrt{{3}}")
    if h_val == int(h_val):
        answer = str(int(h_val))
    else:
        s = f"{h_val:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"Сторона ромба равна \({a_cond}\), а один из углов этого ромба "
        f"равен \({angle}°\). Найдите высоту этого ромба."
    )

    if angle <= 90:
        A, B, C, D = _make_rhombus(angle)
    else:
        A, B, C, D = _make_rhombus(angle, anchor=(155, 175))
    H = _foot(B, A, D)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _angle_arc(A, D, B, label_text=f"{angle}°", R=22, label_offset=14, arcs=1)
    body += _segment(B, H, dashed=True, width=1.3)
    body += _vertex_dot(H)
    sq = 7
    body += (
        f'<polyline points="{H[0]:.1f},{H[1]-sq:.1f} {H[0]+sq:.1f},{H[1]-sq:.1f} '
        f'{H[0]+sq:.1f},{H[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(H, "H", direction=(0, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(13)
    for i in range(5):
        t = generate_task()
        print(f"[G13 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G14: ромб — диагональ AC + tg → S (тип 18)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G14 = PLOTTER + r'''

def _rhombus_crystal_d(d_AC=180, half_BD_ratio=0.5, center=(160, 110)):
    half_AC = d_AC / 2
    half_BD = half_AC * half_BD_ratio
    cx, cy = center
    A = (cx, cy - half_AC)
    C = (cx, cy + half_AC)
    B = (cx + half_BD, cy)
    D = (cx - half_BD, cy)
    return A, B, C, D


def generate_task():
    """Диагональ AC ромба = d, tg(∠BCA) = m/n. S = d²·m/(2n)."""
    fractions = [(1, 5), (3, 5), (1, 2), (2, 5), (3, 10), (7, 10), (4, 5)]
    for _ in range(50):
        m, n = random.choice(fractions)
        k = random.randint(1, 5)
        d_val = 2 * n * k
        if 6 <= d_val <= 60:
            break
    else:
        m, n, d_val = 1, 5, 10
    S_val = (d_val * d_val * m) / (2 * n)
    if S_val == int(S_val):
        answer = str(int(S_val))
    else:
        s = f"{S_val:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"Диагональ \(AC\) ромба \(ABCD\) равна \({d_val}\), а "
        f"\(\\operatorname{{tg}}\\angle BCA = \\dfrac{{{m}}}{{{n}}}\). "
        f"Найдите площадь ромба."
    )

    # Картинка одинаковая для всех (пропорция 1:0.5 — не зависит от m/n).
    A, B, C, D = _rhombus_crystal_d(d_AC=160, half_BD_ratio=0.5)
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.4)
    body += _angle_arc(C, B, A, R=18, label_offset=12, arcs=1)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(0, -1), offset=14)
    body += _label_direction(B, "B", direction=(1, 0), offset=14)
    body += _label_direction(C, "C", direction=(0, 1), offset=14)
    body += _label_direction(D, "D", direction=(-1, 0), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(14)
    for i in range(5):
        t = generate_task()
        print(f"[G14 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G15: прямоугольник — диагонали в O (тип 19)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G15 = PLOTTER + r'''

def _rect_static():
    """Статичный прямоугольник ABCD (CW)."""
    W, H = 200, 110
    cx, cy = 160, 115
    A = (cx - W / 2, cy + H / 2)
    B = (cx - W / 2, cy - H / 2)
    C = (cx + W / 2, cy - H / 2)
    D = (cx + W / 2, cy + H / 2)
    O = (cx, cy)
    return A, B, C, D, O


def generate_task():
    """Диагонали AC и BD прямоугольника пересекаются в O. Дано AC и AB
    (AB — отвлекающее). Найти AO/BO/CO/DO (= AC/2, т.к. в прямоугольнике
    диагонали равны и делятся пополам).
    """
    AC = random.randint(5, 40)
    AB = random.randint(2, AC - 1)  # сторона короче диагонали
    target = random.choice(['AO', 'BO', 'CO', 'DO'])
    ans_val = AC / 2
    if ans_val == int(ans_val):
        answer = str(int(ans_val))
    else:
        s = f"{ans_val:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"Диагонали \(AC\) и \(BD\) прямоугольника \(ABCD\) пересекаются "
        f"в точке \(O\), \(AC = {AC}\), \(AB = {AB}\). Найдите \({target}\)."
    )

    A, B, C, D, O = _rect_static()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.3) + _segment(B, D, width=1.3)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D) + _vertex_dot(O)
    # Маркер прямого угла в A
    sq = 8
    body += (
        f'<polyline points="{A[0]+sq:.1f},{A[1]:.1f} {A[0]+sq:.1f},{A[1]-sq:.1f} '
        f'{A[0]:.1f},{A[1]-sq:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(O, "O", direction=(0, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(15)
    for i in range(5):
        t = generate_task()
        print(f"[G15 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G16: прямоугольник — диагональ + угол со стороной → острый ∠ между диагоналями (20)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G16 = PLOTTER + r'''

def _rect_static():
    W, H = 200, 110
    cx, cy = 160, 115
    A = (cx - W / 2, cy + H / 2)
    B = (cx - W / 2, cy - H / 2)
    C = (cx + W / 2, cy - H / 2)
    D = (cx + W / 2, cy + H / 2)
    O = (cx, cy)
    return A, B, C, D, O


def generate_task():
    """Диагональ прямоугольника образует угол α с одной из сторон. Острый
    угол между диагоналями = 2·min(α, 90−α).
    """
    alpha = random.choice([n for n in range(15, 76) if n != 45])
    ans_val = 2 * min(alpha, 90 - alpha)
    answer = str(ans_val)
    ask_text = (
        f"Диагональ прямоугольника образует угол \({alpha}°\) с одной из "
        f"его сторон. Найдите острый угол между диагоналями этого "
        f"прямоугольника. Ответ дайте в градусах."
    )

    A, B, C, D, O = _rect_static()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.3) + _segment(B, D, width=1.3)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D) + _vertex_dot(O)
    sq = 8
    body += (
        f'<polyline points="{A[0]+sq:.1f},{A[1]:.1f} {A[0]+sq:.1f},{A[1]-sq:.1f} '
        f'{A[0]:.1f},{A[1]-sq:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    # Углы НЕ отмечаем — только условие задачи говорит, о каком угле речь.
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(O, "O", direction=(0, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(16)
    for i in range(5):
        t = generate_task()
        print(f"[G16 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G17: квадрат — сторона → диагональ (тип 21)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G17 = PLOTTER + r'''

def generate_task():
    """Сторона квадрата = k√2 → диагональ = 2k."""
    k = random.randint(2, 25)
    if k == 1:
        a_cond = "\\sqrt{2}"
    else:
        a_cond = f"{k}\\sqrt{{2}}"
    ans_val = 2 * k
    ask_text = (
        f"Сторона квадрата равна \({a_cond}\). Найдите диагональ этого квадрата."
    )
    answer = str(ans_val)

    side = 130
    cx, cy = 160, 115
    A = (cx - side / 2, cy + side / 2)
    B = (cx - side / 2, cy - side / 2)
    C = (cx + side / 2, cy - side / 2)
    D = (cx + side / 2, cy + side / 2)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(B, D, width=1.4)  # диагональ BD (другая)
    sq = 8
    body += (
        f'<polyline points="{A[0]+sq:.1f},{A[1]:.1f} {A[0]+sq:.1f},{A[1]-sq:.1f} '
        f'{A[0]:.1f},{A[1]-sq:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(17)
    for i in range(5):
        t = generate_task()
        print(f"[G17 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G18: равнобедр. трапеция, один угол → больший/меньший (типы 22, 23)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G18 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg, AD_px=170, BC_px=90, anchor=(75, 175)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def generate_task():
    target = random.choice(['larger', 'smaller'])
    alpha = random.choice([n for n in range(20, 161) if n != 90])
    other = 180 - alpha
    larger = max(alpha, other)
    smaller = min(alpha, other)
    ans_val = larger if target == 'larger' else smaller
    text_target = 'больший' if target == 'larger' else 'меньший'
    ask_text = (
        f"Один из углов равнобедренной трапеции равен \({alpha}°\). "
        f"Найдите {text_target} угол этой трапеции. Ответ дайте в градусах."
    )
    answer = str(ans_val)

    # Фиксированная картинка для всех вариантов (угол не отмечен).
    A, B, C, D = _iso_trapezoid(70)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(18)
    for i in range(5):
        t = generate_task()
        print(f"[G18 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G19: равнобедр. трапеция, сумма 2 углов → больший/меньший (типы 24, 25)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G19 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=170, BC_px=90, anchor=(75, 175)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def _fmt(x):
    if x == int(x):
        return str(int(x))
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def generate_task():
    """Сумма 2 углов равнобедр. трапеции = S → больший/меньший.
    Углы при одном основании равны; их сумма = S → каждый = S/2.
    Другие два угла = 180° − S/2.
    """
    target = random.choice(['larger', 'smaller'])
    # S ≠ 180° (тогда нет «больше» и «меньше»). S ∈ [40°, 340°].
    S = random.choice([n for n in range(40, 341) if n != 180])
    half = S / 2
    other = 180 - half
    larger = max(half, other)
    smaller = min(half, other)
    ans = larger if target == 'larger' else smaller
    text_target = 'больший' if target == 'larger' else 'меньший'
    ask_text = (
        f"Сумма двух углов равнобедренной трапеции равна \({S}°\). "
        f"Найдите {text_target} угол этой трапеции. Ответ дайте в градусах."
    )
    answer = _fmt(ans)

    A, B, C, D = _iso_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(19)
    for i in range(5):
        t = generate_task()
        print(f"[G19 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G20: прямоуг. трапеция, один угол → больший/меньший (типы 26, 27)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G20 = PLOTTER + r'''

def _right_trapezoid(ang_A_deg=70, AD_px=170, height=90, anchor=(75, 175)):
    """Прямоуг. трапеция ABCD: A низ-лево, B верх-лево (∠A=∠B=90°),
    C верх-право (тупой или острый), D низ-право."""
    A = anchor
    D = (A[0] + AD_px, A[1])
    B = (A[0], A[1] - height)
    # BC — горизонтальное. Длина BC зависит от угла при D.
    # Если ∠D = ang_A_deg (этот угол при D), то tan(∠D) = height / (AD - BC).
    # → AD - BC = height / tan(∠D). BC = AD - height / tan(ang_A_deg).
    a = math.radians(ang_A_deg)
    bc = AD_px - height / math.tan(a)
    C = (B[0] + bc, B[1])
    return A, B, C, D


def generate_task():
    """Один угол прямоуг. трапеции = α (не 90°). Больший/меньший."""
    target = random.choice(['larger', 'smaller'])
    alpha = random.choice([n for n in range(20, 170) if n != 90])
    other = 180 - alpha
    # Углы трапеции: 90, 90, α, 180-α.
    all_angles = [90, 90, alpha, other]
    larger = max(all_angles)
    smaller = min(all_angles)
    ans = larger if target == 'larger' else smaller
    text_target = 'больший' if target == 'larger' else 'меньший'
    ask_text = (
        f"Один из углов прямоугольной трапеции равен \({alpha}°\). "
        f"Найдите {text_target} угол этой трапеции. Ответ дайте в градусах."
    )
    answer = str(ans)

    # Картинка: статичная прямоуг. трапеция с ∠D острым (~70°).
    A, B, C, D = _right_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    # Маркеры прямых углов в A и B
    sq = 8
    body += (
        f'<polyline points="{A[0]+sq:.1f},{A[1]:.1f} {A[0]+sq:.1f},{A[1]-sq:.1f} '
        f'{A[0]:.1f},{A[1]-sq:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    body += (
        f'<polyline points="{B[0]+sq:.1f},{B[1]:.1f} {B[0]+sq:.1f},{B[1]+sq:.1f} '
        f'{B[0]:.1f},{B[1]+sq:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(20)
    for i in range(5):
        t = generate_task()
        print(f"[G20 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G21: t28 — равнобедр. трапеция, ∠D + ∠(AC, CD) → ∠(AC, BC)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G21 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=180, BC_px=80, anchor=(70, 180)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def generate_task():
    """В равнобедр. трапеции (основания AD, BC) ∠D = α. Диагональ AC
    образует со стороной CD угол β. ∠ACB = 180° − α − β.
    """
    while True:
        alpha = random.randint(45, 89)
        beta = random.randint(15, 89)
        ans_val = 180 - alpha - beta
        if 5 < ans_val < alpha:
            break
    answer = str(ans_val)
    ask_text = (
        f"В равнобедренной трапеции с основаниями \(AD\) и \(BC\) "
        f"угол \(D\) равен \({alpha}°\). Диагональ \(AC\) образует со "
        f"стороной \(CD\) угол \({beta}°\). Сколько градусов составляет "
        f"угол между этой диагональю и меньшим основанием трапеции?"
    )
    A, B, C, D = _iso_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.3)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(21)
    for i in range(5):
        t = generate_task()
        print(f"[G21 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G22: t29 — равнобедр. трапеция, ∠D + ∠(AC, AB) → ∠(AC, BC)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G22 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=180, BC_px=80, anchor=(70, 180)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def generate_task():
    """∠D = α (= ∠A в равнобедр. трапеции). Диагональ AC образует со стороной
    AB угол β. ∠ACB = ∠CAD = α − β (накрест лежащие, BC || AD).
    """
    alpha = random.randint(40, 89)
    beta = random.randint(10, alpha - 5)
    ans_val = alpha - beta
    answer = str(ans_val)
    ask_text = (
        f"В равнобедренной трапеции с основаниями \(AD\) и \(BC\) "
        f"угол \(D\) равен \({alpha}°\). Диагональ \(AC\) образует со "
        f"стороной \(AB\) угол \({beta}°\). Сколько градусов составляет "
        f"угол между этой диагональю и меньшим основанием трапеции?"
    )
    A, B, C, D = _iso_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.3)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(22)
    for i in range(5):
        t = generate_task()
        print(f"[G22 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G23: t30 — равнобедр. трапеция, биссектриса (∠ABE = ∠ABC / 2)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G23 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=180, BC_px=80, anchor=(70, 180)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def generate_task():
    """∠ABC = α в равнобедр. трапеции. BE — биссектриса. ∠ABE = α/2."""
    alpha = random.choice([n for n in range(20, 161) if n != 90])
    ans_raw = alpha / 2
    if ans_raw == int(ans_raw):
        answer = str(int(ans_raw))
    else:
        s = f"{ans_raw:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"В равнобедренной трапеции \(ABCD\) угол \(ABC\) равен "
        f"\({alpha}°\). Найдите градусную меру угла \(ABE\), если "
        f"луч \(BE\) является биссектрисой угла \(ABC\)."
    )
    A, B, C, D = _iso_trapezoid()
    # Биссектриса из B: направление = (BA/|BA|) + (BC/|BC|)
    bax, bay = A[0]-B[0], A[1]-B[1]
    bcx, bcy = C[0]-B[0], C[1]-B[1]
    bal = math.hypot(bax, bay); bcl = math.hypot(bcx, bcy)
    ux, uy = bax/bal + bcx/bcl, bay/bal + bcy/bcl
    ul = math.hypot(ux, uy)
    ux, uy = ux/ul, uy/ul
    # Пересечение с AD (y = A[1])
    if abs(uy) > 1e-9:
        t = (A[1] - B[1]) / uy
        E = (B[0] + ux*t, A[1])
    else:
        E = ((A[0] + D[0]) / 2, A[1])
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(B, E, width=1.3)
    body += _vertex_dot(E)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(E, "E", direction=(0, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(23)
    for i in range(5):
        t = generate_task()
        print(f"[G23 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G24: t31 — равнобедр. трапеция, диагональ + 2 угла → ∠ при большем
# ──────────────────────────────────────────────────────────────────────────────

GEN_G24 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=180, BC_px=80, anchor=(70, 180)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def generate_task():
    """Диагональ равнобедр. трапеции образует с боковыми сторонами углы β1, β2.
    Угол при большем основании = (180° + β1 − β2) / 2.
    """
    for _ in range(80):
        beta1 = random.randint(15, 80)
        beta2 = random.randint(15, 80)
        if beta1 != beta2 and (beta1 + beta2) < 150:
            ans_raw = (180 + beta1 - beta2) / 2
            if 30 < ans_raw < 90:
                break
    else:
        beta1, beta2 = 29, 77
        ans_raw = (180 + beta1 - beta2) / 2
    if ans_raw == int(ans_raw):
        answer = str(int(ans_raw))
    else:
        s = f"{ans_raw:.2f}".rstrip("0").rstrip(".")
        answer = s.replace(".", ",")
    ask_text = (
        f"Диагональ равнобедренной трапеции образует с боковыми сторонами "
        f"углы \({beta1}°\) и \({beta2}°\). Сколько градусов составляет "
        f"угол при большем основании трапеции?"
    )
    A, B, C, D = _iso_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(A, C, width=1.3)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(24)
    for i in range(5):
        t = generate_task()
        print(f"[G24 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G25: t32 — трапеция, основания + h → средняя линия
# ──────────────────────────────────────────────────────────────────────────────

GEN_G25 = PLOTTER + r'''

def _trap_static(a_base=170, b_base=90, h_px=90, shift=20, anchor=(75, 175)):
    A = anchor
    D = (A[0] + a_base, A[1])
    B = (A[0] + shift, A[1] - h_px)
    C = (B[0] + b_base, B[1])
    return A, B, C, D


def _fmt(x):
    if x == int(x):
        return str(int(x))
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def generate_task():
    """Ср. линия = (a+b)/2. Высота h — отвлекающее условие."""
    a = random.randint(2, 30)
    b = random.randint(2, 30)
    if a == b:
        b = a + 2
    h = random.randint(2, 20)
    ans = (a + b) / 2
    answer = _fmt(ans)
    ask_text = (
        f"Основания трапеции равны \({a}\) и \({b}\), а высота равна "
        f"\({h}\). Найдите среднюю линию этой трапеции."
    )
    A, B, C, D = _trap_static()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(25)
    for i in range(5):
        t = generate_task()
        print(f"[G25 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G26: t33 — трапеция, основания → больший отрезок ср. линии
# ──────────────────────────────────────────────────────────────────────────────

GEN_G26 = PLOTTER + r'''

def _trap_static(a_base=170, b_base=90, h_px=90, shift=20, anchor=(75, 175)):
    A = anchor
    D = (A[0] + a_base, A[1])
    B = (A[0] + shift, A[1] - h_px)
    C = (B[0] + b_base, B[1])
    return A, B, C, D


def _fmt(x):
    if x == int(x):
        return str(int(x))
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def generate_task():
    """Ср. линия делится диагональю на a/2 и b/2. Больший = max(a,b)/2."""
    a = random.randint(2, 20)
    b = random.randint(a + 2, 25)
    ans = b / 2
    answer = _fmt(ans)
    ask_text = (
        f"Основания трапеции равны \({a}\) и \({b}\). Найдите больший "
        f"из отрезков, на которые делит среднюю линию этой трапеции одна "
        f"из её диагоналей."
    )
    A, B, C, D = _trap_static()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(26)
    for i in range(5):
        t = generate_task()
        print(f"[G26 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G27: t34 — трапеция, основания + h → площадь
# ──────────────────────────────────────────────────────────────────────────────

GEN_G27 = PLOTTER + r'''

def _trap_static(a_base=170, b_base=90, h_px=90, shift=20, anchor=(75, 175)):
    A = anchor
    D = (A[0] + a_base, A[1])
    B = (A[0] + shift, A[1] - h_px)
    C = (B[0] + b_base, B[1])
    return A, B, C, D


def _fmt(x):
    if x == int(x):
        return str(int(x))
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def generate_task():
    """S = (a+b)·h / 2."""
    a = random.randint(2, 20)
    b = random.randint(2, 25)
    if a == b:
        b = a + 2
    h = random.randint(2, 20)
    S = (a + b) * h / 2
    answer = _fmt(S)
    ask_text = (
        f"Основания трапеции равны \({a}\) и \({b}\), а высота равна "
        f"\({h}\). Найдите площадь этой трапеции."
    )
    A, B, C, D = _trap_static()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(27)
    for i in range(5):
        t = generate_task()
        print(f"[G27 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G28: равнобедр. трапеция, высота делит большее основание (типы 35, 36)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G28 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=180, BC_px=80, anchor=(70, 180)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def generate_task():
    """Подтипы:
       t35: высота из вершины делит основание на p, q → основание = p+q.
       t36: высота из конца меньшего основания делит большее на p, q (p<q)
            → меньшее = q − p.
    """
    subtype = random.choice(['t35', 't36'])
    p = random.randint(1, 12)
    q = random.randint(p + 1, 20)
    if subtype == 't35':
        ans = p + q
        ask_text = (
            f"Высота равнобедренной трапеции, проведённая из вершины, делит "
            f"основание на отрезки длиной \({p}\) и \({q}\). Найдите длину "
            f"основания."
        )
    else:
        ans = q - p
        ask_text = (
            f"Высота равнобедренной трапеции, проведённая из конца её меньшего "
            f"основания, делит большее основание на отрезки длиной \({p}\) и "
            f"\({q}\). Найдите меньшее основание трапеции."
        )
    answer = str(ans)

    A, B, C, D = _iso_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(28)
    for i in range(5):
        t = generate_task()
        print(f"[G28 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G29: равнобедр. трапеция, h + 1 основание + угол → другое (типы 37, 38)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G29 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=180, BC_px=80, anchor=(70, 180)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def generate_task():
    """Подтипы:
       t37: h, меньшее a, угол α=45° → большее b = a + 2h.
       t38: h, большее b, угол α=45° → меньшее a = b − 2h.
    """
    subtype = random.choice(['t37', 't38'])
    ang = 45
    h = random.randint(2, 12)
    a_val = random.randint(3, 15)
    b_val = a_val + 2 * h
    if subtype == 't37':
        ans = b_val
        ask_text = (
            f"В равнобедренной трапеции известна высота \({h}\), меньшее "
            f"основание \({a_val}\) и угол при основании \({ang}°\). "
            f"Найдите большее основание."
        )
    else:
        ans = a_val
        ask_text = (
            f"В равнобедренной трапеции известна высота \({h}\), большее "
            f"основание \({b_val}\) и угол при основании \({ang}°\). "
            f"Найдите меньшее основание."
        )
    answer = str(ans)

    A, B, C, D = _iso_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(29)
    for i in range(5):
        t = generate_task()
        print(f"[G29 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G30: равнобедр. трапеция, основания + угол → S / h (типы 39, 40)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G30 = PLOTTER + r'''

def _iso_trapezoid(ang_A_deg=70, AD_px=180, BC_px=80, anchor=(70, 180)):
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(ang_A_deg)
    half_diff = (AD_px - BC_px) / 2
    h_px = half_diff * math.tan(a)
    B = (A[0] + half_diff, A[1] - h_px)
    C = (D[0] - half_diff, D[1] - h_px)
    return A, B, C, D


def _fmt(x):
    if x == int(x):
        return str(int(x))
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def generate_task():
    """Подтипы:
       t39: основания a, b, угол α=45° → S = (a+b)(b−a)/4.
       t40: диагональ и основание угол γ=45°, основания a, b → h = (a+b)/2.
    """
    subtype = random.choice(['t39', 't40'])
    ang = 45
    if subtype == 't39':
        a = random.randint(2, 10)
        # b и a одной чётности → (a+b)(b-a) делится на 4 → S = (a+b)(b-a)/4 целое
        b = a + random.choice([2, 4, 6, 8, 10, 12, 14])
        h = (b - a) / 2
        S = (a + b) * h / 2
        ans = S
        ask_text = (
            f"В равнобедренной трапеции основания равны \({a}\) и \({b}\), "
            f"а один из углов между боковой стороной и основанием равен "
            f"\({ang}°\). Найдите площадь этой трапеции."
        )
    else:
        a = random.randint(2, 8)
        b = random.randint(a + 2, a + 10)
        h = (a + b) / 2
        ans = h
        ask_text = (
            f"Диагональ равнобедренной трапеции образует с её основанием "
            f"угол \({ang}°\). Найдите высоту трапеции, если её основания "
            f"равны \({a}\) и \({b}\)."
        )
    answer = _fmt(ans)

    A, B, C, D = _iso_trapezoid()
    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(30)
    for i in range(5):
        t = generate_task()
        print(f"[G30 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# Регистрация
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    (1, 'OGE17: G1 — параллелограмм, один угол → больший/меньший',
        'Типы 1, 2', GEN_G1),
    (2, 'OGE17: G2 — параллелограмм, диагональ + α, β',
        'Типы 3, 4', GEN_G2),
    (3, 'OGE17: G3 — параллелограмм, диагонали в O',
        'Тип 5: половина диагонали', GEN_G3),
    (4, 'OGE17: G4 — параллелограмм, биссектриса',
        'Тип 6: острый угол = 2α', GEN_G4),
    (5, 'OGE17: G5 — площадь параллелограмма на клетке',
        'Тип 7', GEN_G5),
    (6, 'OGE17: G6 — паралл.: S + 2 стороны → большая/меньшая высота',
        'Типы 8, 9', GEN_G6),
    (7, 'OGE17: G7 — один угол ромба → больший/меньший',
        'Типы 10, 11', GEN_G7),
    (8, 'OGE17: G8 — ромб: ∠ABC → ∠ACD (диагональ делит угол)',
        'Тип 12', GEN_G8),
    (9, 'OGE17: G9 — ромб: ∠ между стороной и меньшей диагональю',
        'Тип 13', GEN_G9),
    (10, 'OGE17: G10 — ромб: перпендикуляр из O на сторону + диагональ',
        'Тип 14', GEN_G10),
    (11, 'OGE17: G11 — ромб: ∠ между высотой и большей диагональю',
        'Тип 15', GEN_G11),
    (12, 'OGE17: G12 — ромб: P + угол → S',
        'Тип 16', GEN_G12),
    (13, 'OGE17: G13 — ромб: сторона + угол → высота',
        'Тип 17', GEN_G13),
    (14, 'OGE17: G14 — ромб: диагональ + tg → S',
        'Тип 18', GEN_G14),
    (15, 'OGE17: G15 — прямоугольник: диагонали в O → AO/DO',
        'Тип 19', GEN_G15),
    (16, 'OGE17: G16 — прямоугольник: диагональ + угол → ∠ между диагоналями',
        'Тип 20', GEN_G16),
    (17, 'OGE17: G17 — квадрат: сторона → диагональ',
        'Тип 21', GEN_G17),
    (18, 'OGE17: G18 — равнобедр. трапеция, один угол → больший/меньший',
        'Типы 22, 23', GEN_G18),
    (19, 'OGE17: G19 — равнобедр. трапеция: сумма 2 углов → больший/меньший',
        'Типы 24, 25', GEN_G19),
    (20, 'OGE17: G20 — прямоуг. трапеция, один угол → больший/меньший',
        'Типы 26, 27', GEN_G20),
    (21, 'OGE17: G21 — равнобедр. трапеция: ∠D + ∠(AC,CD) → ∠(AC,BC)',
        'Тип 28', GEN_G21),
    (22, 'OGE17: G22 — равнобедр. трапеция: ∠D + ∠(AC,AB) → ∠(AC,BC)',
        'Тип 29', GEN_G22),
    (23, 'OGE17: G23 — равнобедр. трапеция: биссектриса ∠ABC',
        'Тип 30', GEN_G23),
    (24, 'OGE17: G24 — равнобедр. трапеция: диагональ + 2 угла → ∠ при большем',
        'Тип 31', GEN_G24),
    (25, 'OGE17: G25 — трапеция: основания + h → средняя линия',
        'Тип 32', GEN_G25),
    (26, 'OGE17: G26 — трапеция: основания → больший отрезок ср. линии',
        'Тип 33', GEN_G26),
    (27, 'OGE17: G27 — трапеция: основания + h → площадь',
        'Тип 34', GEN_G27),
    (28, 'OGE17: G28 — равнобедр. трапеция: высота делит большее основание',
        'Типы 35, 36', GEN_G28),
    (29, 'OGE17: G29 — равнобедр. трапеция: h + основание + угол → другое',
        'Типы 37, 38', GEN_G29),
    (30, 'OGE17: G30 — равнобедр. трапеция: основания + угол → S/h',
        'Типы 39, 40', GEN_G30),
]


class Command(BaseCommand):
    help = "Создаёт «Задание 17» (Четырёхугольники)"

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
            old = Lesson.objects.filter(module=module, title='Задание 17').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 17',
            defaults={'order': 17, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 17:
            lesson.order = 17
            lesson.save(update_fields=['order'])
        existing_by_order = {a.order: a for a in lesson.assignments.all()}
        for order, gen_name, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={'generator_type': 'python_function',
                          'python_code': code, 'config': {}},
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
