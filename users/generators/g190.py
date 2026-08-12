# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=190: OGE18: G10 — длина отрезка AB по чертежу
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



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
