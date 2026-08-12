# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=186: OGE18: G6 — ромб на клетке: площадь
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
