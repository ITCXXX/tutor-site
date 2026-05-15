# -*- coding: utf-8 -*-
"""
Management command: создаёт ProblemGenerator-ы и Assignment-ы под урок
«Задание 18» курса ОГЭ. Тема — «Фигуры на клетчатой плоскости».

Архитектура (после анализа Школково /catalog/7157, 15 типов):
    G1.  TRIANGLE_AREA     — треугольник → площадь (тип 1)
    G2.  RIGHT_TRI_LEG     — прямоуг. треугольник → больший катет (тип 2)
    G3.  TRI_MIDLINE       — треугольник → ср. линия (тип 3)
    G4.  PARALL_AREA       — параллелограмм → площадь (тип 4)
    G5.  RHOMBUS_DIAG      — ромб → большая диагональ (тип 5)
    G6.  RHOMBUS_AREA      — ромб → площадь (тип 6)
    G7.  TRAP_MIDLINE      — трапеция → ср. линия (тип 7)
    G8.  TRAP_AREA         — трапеция → площадь (тип 8)
    G9.  DISTANCE_2PTS     — расстояние между 2 точками (тип 9)
    G10. SEGMENT_LENGTH    — длина отрезка по чертежу (типы 10, 11)
    G11. TRI_RATIO         — треугольник: отношение длин 2 отрезков (типы 12, 13)
    G12. TWO_CIRCLES_RATIO — отношение площадей 2 кругов (типы 14, 15)

Стиль рисунков:
    - Клетчатая сетка 14×10 клеток (cell = 22 px).
    - Рабочая зона: 2 клетки декора по краям.
    - Фигура — чёрные линии (stroke 1.8).
    - Подписи — Cambria/Georgia, italic 13pt.

Usage:
    python manage.py seed_oge18
    python manage.py seed_oge18 --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# PLOTTER — общие SVG-хелперы для клетчатой плоскости
# ──────────────────────────────────────────────────────────────────────────────

PLOTTER = r'''
import math
import random


# ─── Параметры сетки ─────────────────────────────────────────────────────────
GRID_COLS = 14
GRID_ROWS = 10
GRID_CELL = 22          # пикс. на клетку
GRID_X0 = 12            # отступ слева
GRID_Y0 = 12            # отступ сверху
DECO_MARGIN = 2         # декоративные клетки по краям


def _cell_to_px(cx, cy):
    """Координаты клетки (cx, cy) → SVG-пиксели.
    cx идёт вправо от 0, cy идёт вверх от 0. Происхождение — левый нижний угол.
    """
    px = GRID_X0 + cx * GRID_CELL
    py = GRID_Y0 + (GRID_ROWS - cy) * GRID_CELL
    return (px, py)


def _work_zone():
    """Возвращает (x_min, x_max, y_min, y_max) — границы рабочей зоны
    в клетках (без декоративных краёв).
    """
    return (DECO_MARGIN, GRID_COLS - DECO_MARGIN,
            DECO_MARGIN, GRID_ROWS - DECO_MARGIN)


def _grid_bg():
    """SVG-фон: клетчатая сетка."""
    out = []
    # Фон-прямоугольник
    w = GRID_COLS * GRID_CELL
    h = GRID_ROWS * GRID_CELL
    out.append(
        f'<rect x="{GRID_X0}" y="{GRID_Y0}" width="{w}" height="{h}" '
        f'fill="#ffffff" stroke="none"/>'
    )
    # Вертикальные линии
    for i in range(GRID_COLS + 1):
        x = GRID_X0 + i * GRID_CELL
        out.append(
            f'<line x1="{x}" y1="{GRID_Y0}" x2="{x}" y2="{GRID_Y0 + h}" '
            f'stroke="#c8c8c8" stroke-width="0.8"/>'
        )
    # Горизонтальные линии
    for j in range(GRID_ROWS + 1):
        y = GRID_Y0 + j * GRID_CELL
        out.append(
            f'<line x1="{GRID_X0}" y1="{y}" x2="{GRID_X0 + w}" y2="{y}" '
            f'stroke="#c8c8c8" stroke-width="0.8"/>'
        )
    return "".join(out)


def _segment(P1, P2, dashed=False, width=1.8):
    da = ' stroke-dasharray="5,3"' if dashed else ''
    return (
        f'<line x1="{P1[0]:.1f}" y1="{P1[1]:.1f}" x2="{P2[0]:.1f}" y2="{P2[1]:.1f}" '
        f'stroke="#1f1f1f" stroke-width="{width}"{da}/>'
    )


def _vertex_dot(P, r=2.5):
    return f'<circle cx="{P[0]:.1f}" cy="{P[1]:.1f}" r="{r}" fill="#1f1f1f"/>'


def _polygon(points_px, fill="none", stroke="#1f1f1f", stroke_width=1.8):
    """Многоугольник по списку точек (в SVG-пикселях)."""
    pts_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in points_px)
    return (
        f'<polygon points="{pts_str}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{stroke_width}"/>'
    )


def _svg_wrap_grid(body, w=None, h=None):
    if w is None:
        w = GRID_X0 * 2 + GRID_COLS * GRID_CELL
    if h is None:
        h = GRID_Y0 * 2 + GRID_ROWS * GRID_CELL
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" '
        f'aria-label="Фигура на клетчатой бумаге" '
        f'style="display:block;margin:0.5em auto">{body}</svg>'
    )


def _ans(x):
    """Форматирует число: целое или X,5 / X,25 / etc. (до 2 знаков)."""
    if x == int(x):
        return str(int(x))
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _tri_area_units(p1, p2, p3):
    """Площадь треугольника в клеточных единицах (формула Гаусса)."""
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3
    return abs(x1*(y2 - y3) + x2*(y3 - y1) + x3*(y1 - y2)) / 2


def _label(P_px, text, dx=0, dy=0, font_size=14, font_style='italic'):
    """Подпись (буквенная метка вершины) рядом с точкой P_px.
    dx, dy — смещение в пикселях относительно P_px.
    """
    x = P_px[0] + dx
    y = P_px[1] + dy
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Cambria, Georgia, serif" '
        f'font-style="{font_style}" font-size="{font_size}" '
        f'text-anchor="middle" fill="#1f1f1f">{text}</text>'
    )


def _vertex_label_offset(P_cell, centroid_cell, gap_px=11):
    """Считает смещение метки относительно вершины так, чтобы подпись
    «отходила» от центра треугольника наружу.
    P_cell, centroid_cell — координаты в клетках. Возвращает (dx, dy) в пикселях.
    """
    vx = P_cell[0] - centroid_cell[0]
    vy = P_cell[1] - centroid_cell[1]
    n = (vx * vx + vy * vy) ** 0.5
    if n < 1e-6:
        return (0, -gap_px)
    # В SVG y растёт вниз, в клетках y растёт вверх → инвертируем vy
    dx = gap_px * vx / n
    dy = -gap_px * vy / n
    # Доп. сдвиг по вертикали для читаемости текста
    if dy < 0:
        dy -= 2   # метка над вершиной — приподнимем
    else:
        dy += 11  # метка под вершиной — опустим
    return (dx, dy)
'''


# ──────────────────────────────────────────────────────────────────────────────
# G1: треугольник на клетке → площадь (тип 1)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G1 = PLOTTER + r'''

def generate_task():
    """Треугольник на сетке: ОДНА СТОРОНА идёт по клеткам (горизонтально или
    вертикально). Длина основания b и высота h — целые числа клеток.
    Площадь S = b·h/2.
    """
    x_min, x_max, y_min, y_max = _work_zone()

    orientation = random.choice(['horizontal', 'vertical'])
    # Рабочая зона: x ∈ [x_min, x_max] (ширина), y ∈ [y_min, y_max] (высота).
    W = x_max - x_min  # макс. ширина в клетках
    H = y_max - y_min  # макс. высота в клетках
    if orientation == 'horizontal':
        # Основание горизонт. → b ≤ W, высота вверх ≤ H
        b = random.randint(3, W)
        h = random.randint(2, H)
    else:
        # Основание вертик. → b ≤ H, высота вбок ≤ W
        b = random.randint(3, H)
        h = random.randint(2, W)

    if orientation == 'horizontal':
        # Основание AB горизонтально
        ax = random.randint(x_min, x_max - b)
        ay = random.randint(y_min, y_max - h)
        A = (ax, ay)
        B = (ax + b, ay)
        # Третья вершина — выше основания, в пределах рабочей зоны
        cx = random.randint(x_min, x_max)
        cy = ay + h   # высота = h
        if cy > y_max:
            cy = ay - h  # если выше не помещается, опускаем вниз
        C = (cx, cy)
    else:
        # Основание AB вертикально
        ax = random.randint(x_min, x_max - h)
        ay = random.randint(y_min, y_max - b)
        A = (ax, ay)
        B = (ax, ay + b)
        # Третья вершина — справа или слева от основания, высота = h
        cx = ax + h
        if cx > x_max:
            cx = ax - h
        cy = random.randint(y_min, y_max)
        C = (cx, cy)

    area = b * h / 2

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\times 1\) изображён "
        "треугольник. Найдите его площадь."
    )
    answer = _ans(area)

    pts_px = [_cell_to_px(*v) for v in (A, B, C)]
    body = _grid_bg()
    body += _polygon(pts_px)
    for P in pts_px:
        body += _vertex_dot(P)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(1)
    for i in range(5):
        t = generate_task()
        print(f"[G1 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G2: прямоугольный треугольник на клетке → больший катет (тип 2)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G2 = PLOTTER + r'''

def generate_task():
    """Прямоугольный треугольник на клетчатой бумаге: ОБА КАТЕТА идут
    по клеткам (один горизонтально, другой вертикально). Прямой угол —
    в одной из вершин-сеток. Длины катетов a и b — целые, a ≠ b.
    Ответ — длина большего катета = max(a, b).
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min   # макс. ширина рабочей зоны (в клетках)
    H = y_max - y_min   # макс. высота рабочей зоны (в клетках)

    # Случайные катеты: разные, оба ≥ 2 (чтобы треугольник был отчётливым)
    while True:
        leg_h = random.randint(3, min(W, 10))   # горизонт. катет
        leg_v = random.randint(3, min(H, 8))    # вертик. катет
        if leg_h != leg_v:
            break

    # Прямой угол — в одной из 4 «угловых» позиций треугольника
    # (квадранты): catetus_h уходит вправо/влево, catetus_v уходит вверх/вниз
    quadrant = random.choice(['NE', 'NW', 'SE', 'SW'])

    # Позиционируем вершину прямого угла так, чтобы оба катета влезли
    if 'E' in quadrant:
        rx = random.randint(x_min, x_max - leg_h)
    else:
        rx = random.randint(x_min + leg_h, x_max)
    if 'N' in quadrant:
        ry = random.randint(y_min, y_max - leg_v)
    else:
        ry = random.randint(y_min + leg_v, y_max)

    R = (rx, ry)                                                    # прямой угол
    H_end = (rx + leg_h, ry) if 'E' in quadrant else (rx - leg_h, ry)   # конец горизонт. катета
    V_end = (rx, ry + leg_v) if 'N' in quadrant else (rx, ry - leg_v)   # конец вертик. катета

    answer = max(leg_h, leg_v)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\times 1\) изображён "
        "прямоугольный треугольник. Найдите длину его большего катета."
    )

    pts_px = [_cell_to_px(*v) for v in (R, H_end, V_end)]
    body = _grid_bg()
    body += _polygon(pts_px)
    for P in pts_px:
        body += _vertex_dot(P)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": _ans(answer)}


if __name__ == "__main__":
    random.seed(2)
    for i in range(5):
        t = generate_task()
        print(f"[G2 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G3: треугольник на клетке → средняя линия (тип 3)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G3 = PLOTTER + r'''

def generate_task():
    """Треугольник ABC на клетчатой бумаге. Одна из сторон идёт вдоль клеток
    (горизонтально или вертикально); её длина k — целое число клеток (3…10).
    Третья вершина — произвольная точка-сетки выше (для горизонт. основания)
    или сбоку (для вертик. основания). Вершины подписаны буквами A, B, C
    (в случайной перестановке). Вопрос: длина средней линии, параллельной
    стороне-основанию. Ответ = k/2 (целое или X,5).
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    orientation = random.choice(['horizontal', 'vertical'])
    if orientation == 'horizontal':
        k = random.randint(3, min(W, 10))
        bx0 = random.randint(x_min, x_max - k)
        by0 = random.randint(y_min, y_max - 2)   # оставим место под третью вершину
        P1 = (bx0, by0)
        P2 = (bx0 + k, by0)
        # Третья вершина: где-то выше основания, в пределах рабочей зоны
        # И не на линии основания
        h_up = random.randint(2, min(H - (by0 - y_min), 5))
        qy = by0 + h_up
        if qy > y_max:
            qy = by0 - h_up   # если выше нет места — опустим
        qx = random.randint(x_min, x_max)
        # Не допустим, чтобы Q лежала точно между P1 и P2 на основании
        if qy == by0:
            qy += 2
        Q = (qx, qy)
    else:
        k = random.randint(3, min(H, 8))
        bx0 = random.randint(x_min, x_max - 2)
        by0 = random.randint(y_min, y_max - k)
        P1 = (bx0, by0)
        P2 = (bx0, by0 + k)
        side_off = random.randint(2, min(W - (bx0 - x_min), 5))
        qx = bx0 + side_off
        if qx > x_max:
            qx = bx0 - side_off
        qy = random.randint(y_min, y_max)
        if qx == bx0:
            qx += 2
        Q = (qx, qy)

    # Случайная перестановка букв A, B, C по вершинам (P1, P2, Q)
    letters = ['A', 'B', 'C']
    random.shuffle(letters)
    lab_P1, lab_P2, lab_Q = letters

    # Названная сторона = две буквы, стоящие на P1 и P2 (в алфавитном порядке)
    side_name = "".join(sorted([lab_P1, lab_P2]))

    answer = _ans(k / 2)

    # Центроид (в клетках) для смещения подписей наружу
    cx = (P1[0] + P2[0] + Q[0]) / 3
    cy = (P1[1] + P2[1] + Q[1]) / 3
    centroid_cell = (cx, cy)

    body = _grid_bg()
    pts_px = [_cell_to_px(*v) for v in (P1, P2, Q)]
    body += _polygon(pts_px)
    for P_cell, P_px, lab in zip([P1, P2, Q], pts_px, [lab_P1, lab_P2, lab_Q]):
        body += _vertex_dot(P_px)
        dx, dy = _vertex_label_offset(P_cell, centroid_cell)
        body += _label(P_px, lab, dx=dx, dy=dy)

    svg = _svg_wrap_grid(body)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображён "
        f"треугольник \(ABC\). Найдите длину его средней линии, "
        f"параллельной стороне \({side_name}\)."
    )
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(3)
    for i in range(8):
        t = generate_task()
        print(f"[G3 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G4: параллелограмм на клетке → площадь (тип 4)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G4 = PLOTTER + r'''

def generate_task():
    """Параллелограмм на клетчатой бумаге: ДВЕ ПАРАЛЛЕЛЬНЫЕ СТОРОНЫ идут вдоль
    клеток (обе горизонтальны или обе вертикальны), длина каждой b — целое
    число клеток. Они смещены друг от друга на h клеток (высота — перпенд.
    расстояние) и на s клеток (наклон) вдоль направления основания.
    Площадь = b * h.
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    orientation = random.choice(['horizontal', 'vertical'])
    # b — длина основания; h — высота (расстояние между парал. сторонами);
    # s — наклон (вдоль направления основания)
    if orientation == 'horizontal':
        b = random.randint(3, min(W - 1, 7))
        h = random.randint(2, min(H - 1, 4))
        s_max = min(W - b, 4)
        if s_max < 1:
            return generate_task()
        s = random.randint(1, s_max) * random.choice([1, -1])
        # Позиционируем нижнюю левую вершину
        # Нужно, чтобы все 4 точки попали в [x_min, x_max] × [y_min, y_max]
        x_lo = max(x_min, x_min - s)      # нижние x в [x0, x0+b], верхние — [x0+s, x0+s+b]
        x_hi = min(x_max - b, x_max - b - s)
        if x_lo > x_hi:
            return generate_task()
        x0 = random.randint(x_lo, x_hi)
        y0 = random.randint(y_min, y_max - h)
        A = (x0, y0)                        # нижний-левый
        B = (x0 + b, y0)                    # нижний-правый
        C = (x0 + b + s, y0 + h)            # верхний-правый
        D = (x0 + s, y0 + h)                # верхний-левый
    else:
        b = random.randint(3, min(H - 1, 6))
        h = random.randint(2, min(W - 1, 4))
        s_max = min(H - b, 4)
        if s_max < 1:
            return generate_task()
        s = random.randint(1, s_max) * random.choice([1, -1])
        y_lo = max(y_min, y_min - s)
        y_hi = min(y_max - b, y_max - b - s)
        if y_lo > y_hi:
            return generate_task()
        y0 = random.randint(y_lo, y_hi)
        x0 = random.randint(x_min, x_max - h)
        A = (x0, y0)                        # лево-низ
        B = (x0, y0 + b)                    # лево-верх
        C = (x0 + h, y0 + b + s)            # право-верх
        D = (x0 + h, y0 + s)                # право-низ

    area = b * h
    answer = _ans(area)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображён "
        "параллелограмм. Найдите его площадь."
    )

    pts_px = [_cell_to_px(*v) for v in (A, B, C, D)]
    body = _grid_bg()
    body += _polygon(pts_px)
    for P in pts_px:
        body += _vertex_dot(P)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(4)
    for i in range(8):
        t = generate_task()
        print(f"[G4 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G5: ромб на клетке → большая диагональ (тип 5)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G5 = PLOTTER + r'''

def generate_task():
    """Ромб на клетчатой бумаге: ДИАГОНАЛИ ИДУТ ВДОЛЬ КЛЕТОК (одна
    горизонтально, другая вертикально). Чтобы вершины попали в узлы сетки,
    обе диагонали — чётные целые числа клеток. Полудиагонали: a (горизонт.),
    b (вертик.). Полные диагонали: d1=2a, d2=2b. Ответ = max(d1, d2).
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    # Полудиагонали (a — горизонт., b — вертик.); должны быть разными.
    while True:
        a = random.randint(2, W // 2)        # горизонт. полудиагональ
        b = random.randint(2, H // 2)        # вертик. полудиагональ
        if a != b:
            break

    # Центр ромба
    ox = random.randint(x_min + a, x_max - a)
    oy = random.randint(y_min + b, y_max - b)

    # 4 вершины
    L = (ox - a, oy)        # лево
    R = (ox + a, oy)        # право
    T = (ox, oy + b)        # верх
    B = (ox, oy - b)        # низ

    d1 = 2 * a
    d2 = 2 * b
    answer = _ans(max(d1, d2))

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображён "
        "ромб. Найдите длину его большей диагонали."
    )

    pts_px = [_cell_to_px(*v) for v in (L, T, R, B)]
    body = _grid_bg()
    body += _polygon(pts_px)
    for P in pts_px:
        body += _vertex_dot(P)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(5)
    for i in range(8):
        t = generate_task()
        print(f"[G5 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G6: ромб на клетке → площадь (тип 6)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G6 = PLOTTER + r'''

def generate_task():
    """Ромб с диагоналями вдоль клеток (как в G5). Спрашивается площадь:
    S = d1 * d2 / 2 = 2 * a * b (всегда целое).
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    # Не требуем a != b — ромб может быть «квадратным», для площади неважно.
    a = random.randint(2, W // 2)
    b = random.randint(2, H // 2)

    ox = random.randint(x_min + a, x_max - a)
    oy = random.randint(y_min + b, y_max - b)

    L = (ox - a, oy)
    R = (ox + a, oy)
    T = (ox, oy + b)
    Bv = (ox, oy - b)

    d1 = 2 * a
    d2 = 2 * b
    area = d1 * d2 / 2          # = 2 * a * b
    answer = _ans(area)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображён "
        "ромб. Найдите площадь этого ромба."
    )

    pts_px = [_cell_to_px(*v) for v in (L, T, R, Bv)]
    body = _grid_bg()
    body += _polygon(pts_px)
    for P in pts_px:
        body += _vertex_dot(P)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(6)
    for i in range(8):
        t = generate_task()
        print(f"[G6 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G7: трапеция на клетке → средняя линия (тип 7)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G7 = PLOTTER + r'''

def generate_task():
    """Трапеция: оба основания идут вдоль клеток (горизонт. или вертик.),
    разные целые длины a и b. Высота h — целое расстояние между ними.
    Средняя линия = (a + b) / 2.
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    orientation = random.choice(['horizontal', 'vertical'])
    if orientation == 'horizontal':
        # a — нижнее основание, b — верхнее (длиннее/короче — случайно)
        while True:
            a = random.randint(3, W)
            b = random.randint(3, W)
            if a != b:
                break
        h = random.randint(2, H)
        # Размещаем нижнее основание
        x_a = random.randint(x_min, x_max - a)
        y_a = random.randint(y_min, y_max - h)
        # Верхнее основание — со сдвигом, чтобы влезло
        x_b = random.randint(x_min, x_max - b)
        y_b = y_a + h
        A = (x_a, y_a)
        B = (x_a + a, y_a)
        C = (x_b + b, y_b)
        D = (x_b, y_b)
    else:
        while True:
            a = random.randint(3, H)
            b = random.randint(3, H)
            if a != b:
                break
        h = random.randint(2, W)
        y_a = random.randint(y_min, y_max - a)
        x_a = random.randint(x_min, x_max - h)
        y_b = random.randint(y_min, y_max - b)
        x_b = x_a + h
        A = (x_a, y_a)
        B = (x_a, y_a + a)
        C = (x_b, y_b + b)
        D = (x_b, y_b)

    mid = (a + b) / 2
    answer = _ans(mid)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображена "
        "трапеция. Найдите длину её средней линии."
    )

    pts_px = [_cell_to_px(*v) for v in (A, B, C, D)]
    body = _grid_bg()
    body += _polygon(pts_px)
    for P in pts_px:
        body += _vertex_dot(P)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(7)
    for i in range(8):
        t = generate_task()
        print(f"[G7 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G8: трапеция на клетке → площадь (тип 8)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G8 = PLOTTER + r'''

def generate_task():
    """Трапеция: оба основания вдоль клеток (горизонт. или вертик.),
    длины a, b — целые, a ≠ b. Высота h — целое. Площадь = (a+b)*h/2.
    Для красивых ответов добиваемся чётности (a+b) ИЛИ h.
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    orientation = random.choice(['horizontal', 'vertical'])
    if orientation == 'horizontal':
        while True:
            a = random.randint(3, W)
            b = random.randint(3, W)
            h = random.randint(2, H)
            if a != b and ((a + b) * h) % 2 == 0:
                break
        x_a = random.randint(x_min, x_max - a)
        y_a = random.randint(y_min, y_max - h)
        x_b = random.randint(x_min, x_max - b)
        y_b = y_a + h
        A = (x_a, y_a)
        B = (x_a + a, y_a)
        C = (x_b + b, y_b)
        D = (x_b, y_b)
    else:
        while True:
            a = random.randint(3, H)
            b = random.randint(3, H)
            h = random.randint(2, W)
            if a != b and ((a + b) * h) % 2 == 0:
                break
        y_a = random.randint(y_min, y_max - a)
        x_a = random.randint(x_min, x_max - h)
        y_b = random.randint(y_min, y_max - b)
        x_b = x_a + h
        A = (x_a, y_a)
        B = (x_a, y_a + a)
        C = (x_b, y_b + b)
        D = (x_b, y_b)

    area = (a + b) * h / 2
    answer = _ans(area)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображена "
        "трапеция. Найдите её площадь."
    )

    pts_px = [_cell_to_px(*v) for v in (A, B, C, D)]
    body = _grid_bg()
    body += _polygon(pts_px)
    for P in pts_px:
        body += _vertex_dot(P)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(8)
    for i in range(8):
        t = generate_task()
        print(f"[G8 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G9: расстояние между двумя точками (тип 9)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G9 = PLOTTER + r'''

def generate_task():
    """На сетке отмечены две точки. Найти расстояние.
    Используем пифагоровы тройки, чтобы ответ был целым.
    Доступные dx, dy (в клетках, без учёта знака):
        (3,4) → 5      (4,3) → 5
        (6,8) → 10     (8,6) → 10
        (5,12) → 13    (12,5) → 13
    """
    # Только пифагоровы тройки, влезающие в рабочую зону 10×6 (W=10, H=6):
    triples = [
        ((3, 4), 5), ((4, 3), 5),
        ((8, 6), 10),
    ]
    (dx_abs, dy_abs), dist = random.choice(triples)

    x_min, x_max, y_min, y_max = _work_zone()
    # Знаки сдвига
    sx = random.choice([1, -1])
    sy = random.choice([1, -1])
    dx = sx * dx_abs
    dy = sy * dy_abs

    # Подбираем положение P1 так, чтобы P2 = P1 + (dx, dy) тоже было в зоне.
    x_lo = max(x_min, x_min - dx)
    x_hi = min(x_max, x_max - dx)
    y_lo = max(y_min, y_min - dy)
    y_hi = min(y_max, y_max - dy)
    if x_lo > x_hi or y_lo > y_hi:
        return generate_task()
    p1x = random.randint(x_lo, x_hi)
    p1y = random.randint(y_lo, y_hi)
    P1 = (p1x, p1y)
    P2 = (p1x + dx, p1y + dy)

    answer = _ans(dist)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображены "
        "две точки. Найдите расстояние между ними."
    )

    body = _grid_bg()
    P1_px = _cell_to_px(*P1)
    P2_px = _cell_to_px(*P2)
    # Только точки — никаких отрезков!
    body += _vertex_dot(P1_px, r=3.5)
    body += _vertex_dot(P2_px, r=3.5)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(9)
    for i in range(8):
        t = generate_task()
        print(f"[G9 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G10: длина отрезка по чертежу (тип 10, 11)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G10 = PLOTTER + r'''

def generate_task():
    """В треугольнике с вершиной T и основанием PQ (длиной 2k) проведена
    средняя линия AB — она соединяет середины боковых сторон TP и TQ.
    По теореме о средней линии: AB параллельна PQ и |AB| = |PQ|/2 = k.

    На чертеже изображены ТОЛЬКО две боковые стороны TP, TQ и средняя
    линия AB. Основание PQ НЕ нарисовано (студент видит «букву Л
    с перекладиной»). Найти длину AB.
    """
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    orientation = random.choice(['horizontal', 'vertical'])
    if orientation == 'horizontal':
        # PQ горизонтально снизу, AB горизонтально посередине, T сверху.
        k = random.choice([2, 3, 4, 5])         # длина AB
        PQ_len = 2 * k                          # длина основания
        if PQ_len > W:
            return generate_task()
        h = random.choice([2, 4])               # высота треугольника (чётная)
        if h > H:
            return generate_task()
        px = random.randint(x_min, x_max - PQ_len)
        qx = px + PQ_len
        py = qy = random.randint(y_min, y_max - h)
        ty = py + h
        # T_x должен иметь ту же чётность, что и px (тогда midpoints целые)
        # и желательно лежать в пределах основания, чтобы фигура была «Λ»-формы.
        possible_tx = [x for x in range(px, qx + 1)
                       if (x - px) % 2 == 0 and x != px and x != qx]
        if not possible_tx:
            possible_tx = [x for x in range(x_min, x_max + 1)
                           if (x - px) % 2 == 0]
        tx = random.choice(possible_tx)
        T = (tx, ty)
        P = (px, py)
        Q = (qx, qy)
    else:
        # PQ вертикально слева, AB вертикально, T справа.
        k = random.choice([2, 3])
        PQ_len = 2 * k
        if PQ_len > H:
            return generate_task()
        h = random.choice([2, 4])
        if h > W:
            return generate_task()
        py = random.randint(y_min, y_max - PQ_len)
        qy = py + PQ_len
        px = qx = random.randint(x_min, x_max - h)
        tx = px + h
        # T_y строго между py и qy (исключаем py и qy), чтобы T был «остриём».
        possible_ty = [y for y in range(py + 1, qy)
                       if (y - py) % 2 == 0]
        if not possible_ty:
            possible_ty = [y for y in range(y_min, y_max + 1)
                           if (y - py) % 2 == 0 and y != py and y != qy]
        ty = random.choice(possible_ty)
        T = (tx, ty)
        P = (px, py)
        Q = (qx, qy)

    # Середины боковых сторон → концы средней линии
    A = ((T[0] + P[0]) // 2, (T[1] + P[1]) // 2)
    B = ((T[0] + Q[0]) // 2, (T[1] + Q[1]) // 2)
    answer = _ans(k)

    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображена "
        "фигура. Найдите длину отрезка \(AB\) по данным чертежа."
    )

    body = _grid_bg()
    T_px = _cell_to_px(*T)
    P_px = _cell_to_px(*P)
    Q_px = _cell_to_px(*Q)
    A_px = _cell_to_px(*A)
    B_px = _cell_to_px(*B)
    # Рисуем: TP, TQ и среднюю линию AB. PQ не рисуется!
    body += _segment(T_px, P_px)
    body += _segment(T_px, Q_px)
    body += _segment(A_px, B_px)
    # Точки A и B
    body += _vertex_dot(A_px, r=3.5)
    body += _vertex_dot(B_px, r=3.5)
    # Подписи A, B
    if orientation == 'horizontal':
        body += _label(A_px, 'A', dx=-2, dy=16)
        body += _label(B_px, 'B', dx=2,  dy=16)
    else:
        body += _label(A_px, 'A', dx=-14, dy=4)
        body += _label(B_px, 'B', dx=-14, dy=4)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(10)
    for i in range(8):
        t = generate_task()
        print(f"[G10 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G11: треугольник, отношение длин 2 отрезков (типы 12, 13)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G11 = PLOTTER + r'''

def generate_task():
    """Треугольник ABC. Через точку M на стороне AB проведена прямая MN,
    параллельная стороне BC; N лежит на AC. По теореме о пропорциональных
    отрезках (общий вид): AM / MB = AN / NC.

    Чтобы все 5 точек (A, B, C, M, N) попали в узлы сетки, AB и AC
    задаём как k_total · (направление с gcd=1), где k_total = ratio + 1.
    M делит AB на доли AM = m_units, MB = k_total - m_units; точно так же
    N делит AC. Тогда MN автоматически параллельна BC.

    Ответ — целое отношение AM/MB или MB/AM (∈ {2, 3}).
    """
    ratio = random.choice([2, 3])
    k_total = ratio + 1
    # m_units — позиция M на AB (число «шагов» от A).
    # m_units == ratio  → AM длиннее MB в ratio раз;
    # m_units == 1      → MB длиннее AM в ratio раз.
    m_units = random.choice([1, ratio])
    if m_units == ratio:
        long_name, short_name = 'AM', 'MB'
    else:
        long_name, short_name = 'MB', 'AM'

    # Направления AB и AC (gcd(p,q)=1, разные)
    candidates = [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (3, 1), (1, 3)]
    x_min, x_max, y_min, y_max = _work_zone()
    W = x_max - x_min
    H = y_max - y_min

    valid_pairs = []
    for v_ab in candidates:
        for v_ac in candidates:
            if v_ab == v_ac:
                continue
            cross = v_ab[0]*v_ac[1] - v_ab[1]*v_ac[0]
            if cross == 0:
                continue
            mx = k_total * max(v_ab[0], v_ac[0])
            my = k_total * max(v_ab[1], v_ac[1])
            if mx <= W and my <= H:
                valid_pairs.append((v_ab, v_ac))
    if not valid_pairs:
        return generate_task()
    v_ab, v_ac = random.choice(valid_pairs)

    # Случайные знаки осей
    sx_ab = random.choice([1, -1])
    sy_ab = random.choice([1, -1]) if v_ab[1] != 0 else 1
    sx_ac = random.choice([1, -1])
    sy_ac = random.choice([1, -1]) if v_ac[1] != 0 else 1
    dx_ab, dy_ab = sx_ab * v_ab[0], sy_ab * v_ab[1]
    dx_ac, dy_ac = sx_ac * v_ac[0], sy_ac * v_ac[1]

    # Чтобы B и C были по разные стороны (треугольник был «нетривиальным»)
    cross_signed = dx_ab * dy_ac - dy_ab * dx_ac
    if cross_signed == 0:
        return generate_task()

    AB_x = k_total * dx_ab
    AB_y = k_total * dy_ab
    AC_x = k_total * dx_ac
    AC_y = k_total * dy_ac

    # Подбираем A так, чтобы B и C тоже попали в зону
    min_x = min(0, AB_x, AC_x)
    max_x = max(0, AB_x, AC_x)
    min_y = min(0, AB_y, AC_y)
    max_y = max(0, AB_y, AC_y)
    x_lo = x_min - min_x
    x_hi = x_max - max_x
    y_lo = y_min - min_y
    y_hi = y_max - max_y
    if x_lo > x_hi or y_lo > y_hi:
        return generate_task()
    ax = random.randint(x_lo, x_hi)
    ay = random.randint(y_lo, y_hi)
    A = (ax, ay)
    B = (ax + AB_x, ay + AB_y)
    C = (ax + AC_x, ay + AC_y)
    M = (ax + m_units * dx_ab, ay + m_units * dy_ab)
    N = (ax + m_units * dx_ac, ay + m_units * dy_ac)

    answer = _ans(ratio)
    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображён "
        "треугольник \(ABC\). Точка \(M\) лежит на стороне \(AB\), точка "
        "\(N\) — на стороне \(AC\), прямая \(MN\) параллельна стороне "
        "\(BC\). Во сколько раз отрезок "
        f"\({long_name}\) длиннее отрезка \({short_name}\)?"
    )

    body = _grid_bg()
    A_px = _cell_to_px(*A)
    B_px = _cell_to_px(*B)
    C_px = _cell_to_px(*C)
    M_px = _cell_to_px(*M)
    N_px = _cell_to_px(*N)
    # Стороны AB и AC (без BC — оставляем «угол» с разомкнутой третьей стороной)
    body += _segment(A_px, B_px)
    body += _segment(A_px, C_px)
    # Прямая MN (параллельная BC)
    body += _segment(M_px, N_px)
    # Все пять точек
    for P_px in (A_px, B_px, C_px, M_px, N_px):
        body += _vertex_dot(P_px, r=3.5)
    # Подписи
    cent = ((A[0]+B[0]+C[0])/3, (A[1]+B[1]+C[1])/3)
    for P_cell, P_px, lab in [(A, A_px, 'A'), (B, B_px, 'B'), (C, C_px, 'C'),
                              (M, M_px, 'M'), (N, N_px, 'N')]:
        dxl, dyl = _vertex_label_offset(P_cell, cent)
        body += _label(P_px, lab, dx=dxl, dy=dyl)
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(11)
    for i in range(8):
        t = generate_task()
        print(f"[G11 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G12: отношение площадей двух кругов (типы 14, 15)
# ──────────────────────────────────────────────────────────────────────────────

GEN_G12 = PLOTTER + r'''

def generate_task():
    """На сетке два круга с центрами в узлах. Каждый круг проходит через
    хотя бы один узел сетки на векторе (dx, dy) от центра, поэтому
    R² = dx² + dy² — целое число (R может быть иррациональным:
    √2, √5, 2√2, √10, …). Отношение площадей S₁/S₂ = R₁²/R₂².

    Чтобы радиус «читался» по чертежу, отмечаем на каждом круге
    жирной точкой одну узловую точку — она показывает R по теореме
    Пифагора (от центра до этой точки).
    """
    # (R²_value, anchor_vector (dx, dy))
    options = [
        (1,  (1, 0)),     # R = 1
        (2,  (1, 1)),     # R = √2
        (4,  (2, 0)),     # R = 2
        (5,  (2, 1)),     # R = √5
        (8,  (2, 2)),     # R = 2√2
        (9,  (3, 0)),     # R = 3
        (10, (3, 1)),     # R = √10
    ]
    # Подходящие пары: R1² > R2², R1²/R2² ∈ ℤ
    nice_pairs = []
    for i, (r1_sq, a1) in enumerate(options):
        for j, (r2_sq, a2) in enumerate(options):
            if r1_sq > r2_sq and r1_sq % r2_sq == 0:
                nice_pairs.append((r1_sq, a1, r2_sq, a2))

    import math
    for _attempt in range(80):
        r1_sq, anchor1, r2_sq, anchor2 = random.choice(nice_pairs)
        R1 = math.sqrt(r1_sq)
        R2 = math.sqrt(r2_sq)
        ratio = r1_sq // r2_sq
        # Габариты в клетках, нужные под каждый круг (целая «обводка»)
        m1 = math.ceil(R1)
        m2 = math.ceil(R2)

        x_min, x_max, y_min, y_max = _work_zone()
        # Большой круг — слева
        if x_min + m1 > x_min + m1 + 1:
            continue
        # Проверяем, что круг помещается по y
        if y_min + m1 > y_max - m1:
            continue
        if y_min + m2 > y_max - m2:
            continue
        # Проверяем, что оба круга помещаются по ширине
        if (x_min + m1) + (R1 + R2 + 0.5) >= (x_max - m2):
            # Большой и малый «впритык» не помещаются
            continue

        cx1 = random.randint(x_min + m1, x_min + m1 + 1)
        cy1 = random.randint(y_min + m1, y_max - m1)
        # Малый — справа, не пересекая большой
        placed = False
        for _ in range(40):
            cx2 = random.randint(x_max - m2 - 1, x_max - m2)
            cy2 = random.randint(y_min + m2, y_max - m2)
            d = math.sqrt((cx2 - cx1)**2 + (cy2 - cy1)**2)
            if d > R1 + R2 + 0.3:
                placed = True
                break
        if not placed:
            continue

        # Якорные точки (узлы сетки на круге, по которым считается R)
        # Выбираем направление anchor так, чтобы точка лежала внутри
        # рабочей зоны.
        def _pick_anchor(cx, cy, base_anchor):
            dx0, dy0 = base_anchor
            for sx in (1, -1):
                for sy in (1, -1):
                    for swap in (False, True):
                        ddx, ddy = (dx0, dy0) if not swap else (dy0, dx0)
                        ax_ = cx + sx * ddx
                        ay_ = cy + sy * ddy
                        if x_min <= ax_ <= x_max and y_min <= ay_ <= y_max:
                            return (ax_, ay_)
            return None
        a1 = _pick_anchor(cx1, cy1, anchor1)
        a2 = _pick_anchor(cx2, cy2, anchor2)
        if a1 is None or a2 is None:
            continue
        break
    else:
        return generate_task()

    answer = _ans(ratio)
    ask_text = (
        "На клетчатой бумаге с размером клетки \(1\\times 1\) изображены "
        "два круга. Во сколько раз площадь большего круга больше площади "
        "меньшего?"
    )

    body = _grid_bg()
    C1_px = _cell_to_px(cx1, cy1)
    C2_px = _cell_to_px(cx2, cy2)
    R_px = GRID_CELL
    body += (
        f'<circle cx="{C1_px[0]:.1f}" cy="{C1_px[1]:.1f}" '
        f'r="{R1 * R_px:.1f}" fill="none" stroke="#1f1f1f" '
        f'stroke-width="1.8"/>'
    )
    body += (
        f'<circle cx="{C2_px[0]:.1f}" cy="{C2_px[1]:.1f}" '
        f'r="{R2 * R_px:.1f}" fill="none" stroke="#1f1f1f" '
        f'stroke-width="1.8"/>'
    )
    # Точки не рисуются — студент определяет радиус по узлам сетки,
    # через которые проходит окружность.
    svg = _svg_wrap_grid(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}",
            "correct_answer": answer}


if __name__ == "__main__":
    random.seed(12)
    for i in range(8):
        t = generate_task()
        print(f"[G12 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# Регистрация
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    (1, 'OGE18: G1 — треугольник на клетке: площадь',
        'Тип 1', GEN_G1),
    (2, 'OGE18: G2 — прямоугольный треугольник на клетке: больший катет',
        'Тип 2', GEN_G2),
    (3, 'OGE18: G3 — треугольник на клетке: средняя линия',
        'Тип 3', GEN_G3),
    (4, 'OGE18: G4 — параллелограмм на клетке: площадь',
        'Тип 4', GEN_G4),
    (5, 'OGE18: G5 — ромб на клетке: большая диагональ',
        'Тип 5', GEN_G5),
    (6, 'OGE18: G6 — ромб на клетке: площадь',
        'Тип 6', GEN_G6),
    (7, 'OGE18: G7 — трапеция на клетке: средняя линия',
        'Тип 7', GEN_G7),
    (8, 'OGE18: G8 — трапеция на клетке: площадь',
        'Тип 8', GEN_G8),
    (9, 'OGE18: G9 — расстояние между двумя точками',
        'Тип 9', GEN_G9),
    (10, 'OGE18: G10 — длина отрезка AB по чертежу',
        'Типы 10, 11', GEN_G10),
    (11, 'OGE18: G11 — треугольник: отношение длин 2 отрезков',
        'Типы 12, 13', GEN_G11),
    (12, 'OGE18: G12 — отношение площадей двух кругов',
        'Типы 14, 15', GEN_G12),
]


class Command(BaseCommand):
    help = "Создаёт «Задание 18» (Фигуры на клетчатой плоскости)"

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
            old = Lesson.objects.filter(module=module, title='Задание 18').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 18',
            defaults={'order': 18, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 18:
            lesson.order = 18
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
