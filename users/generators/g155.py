# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=155: OGE17: G5 — площадь параллелограмма на клетке
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



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
