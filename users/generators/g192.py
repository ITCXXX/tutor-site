# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=192: OGE18: G12 — отношение площадей двух кругов
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
