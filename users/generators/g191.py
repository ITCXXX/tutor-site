# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=191: OGE18: G11 — треугольник: отношение длин 2 отрезков
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
