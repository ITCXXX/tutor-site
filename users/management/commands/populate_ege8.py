# -*- coding: utf-8 -*-
"""
Management command: populate EGE task 8 questions (производная и графики).

Usage:
    python manage.py populate_ege8
    python manage.py populate_ege8 --clear

Lesson order=8 inside module order=1 of course ege-profile-math.
Картинки — оригиналы из ФИПИ, скопированы в media/ege8/.
В поле image_svg помещаем <img>-тег, ссылающийся на эти файлы.

ВАЖНО: ответы для задач этого урока — предположения по виду графика.
Репетитор должен проверить и при необходимости поправить через
`python manage.py populate_ege8 --clear` после редактирования ответов в этом файле.
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ──────────────────────────────────────────────────────────────────────────────
# «Волнистая» функция через список экстремумов
# ──────────────────────────────────────────────────────────────────────────────
# Эрмитов кусочно-кубический сплайн: между соседними экстремумами строится
# полином с условиями p(x_i)=y_i, p'(x_i)=0. Формула на отрезке [a,b]:
#     t = (x-a)/(b-a),  p(x) = y_a + (y_b - y_a) · (3t² - 2t³)
# В узлах гарантировано p'=0 — это точки экстремума.

def wavy_from_extrema(extrema):
    """
    Шорткат: точки заданы только как (x, y) — все считаются экстремумами (slope=0).
    Использует общий wavy_from_points.
    """
    return wavy_from_points([(x, y) for x, y in extrema])


def wavy_from_points(points):
    """
    Кусочно-Hermite кубическая функция через указанные точки.

    points: список из элементов (x, y) [экстремум, slope=0] или (x, y, slope).
            На каждом сегменте [a, b] полином имеет f(a)=ya, f(b)=yb,
            f'(a)=ma, f'(b)=mb и потому гладко стыкуется (C¹).

    Промежуточные точки с ненулевым slope позволяют сделать сегмент
    асимметричным — где-то круче, где-то более пологим. Это устраняет
    «слишком одинаковый» вид соседних подъёмов/спусков.

    За пределами заданного x-диапазона функция продолжается зеркально.
    """
    norm = []
    for p in points:
        if len(p) == 2:
            x, y = p
            slope = 0.0
        else:
            x, y, slope = p
        norm.append((x, y, slope))
    norm.sort(key=lambda p: p[0])
    if len(norm) < 2:
        raise ValueError("Нужно как минимум две точки.")

    # виртуальные продолжения, чтобы крайние оставались экстремумами
    x0, y0, m0 = norm[0]
    x1, y1, m1 = norm[1]
    left_v = (2 * x0 - x1, y1, -m1)
    xn, yn, mn = norm[-1]
    xn1, yn1, mn1 = norm[-2]
    right_v = (2 * xn - xn1, yn1, -mn1)
    pts = [left_v] + norm + [right_v]

    def _segment(x):
        if x <= pts[0][0]:
            return 0
        if x >= pts[-1][0]:
            return len(pts) - 2
        for i in range(len(pts) - 1):
            if pts[i][0] <= x <= pts[i + 1][0]:
                return i
        return len(pts) - 2

    # Базис Эрмита для f(t) с t∈[0,1]:
    #   h00 = 1 - 3t² + 2t³,    h10 = t - 2t² + t³
    #   h01 = 3t² - 2t³,        h11 = -t² + t³
    # f(x) = ya·h00 + ma·h·h10 + yb·h01 + mb·h·h11   где h = b-a
    def f(x):
        i = _segment(x)
        a, ya, ma = pts[i]
        b, yb, mb = pts[i + 1]
        h = b - a
        t = (x - a) / h
        h00 = 1 - 3*t*t + 2*t**3
        h10 = t - 2*t*t + t**3
        h01 = 3*t*t - 2*t**3
        h11 = -t*t + t**3
        return ya*h00 + ma*h*h10 + yb*h01 + mb*h*h11

    def fprime(x):
        i = _segment(x)
        a, ya, ma = pts[i]
        b, yb, mb = pts[i + 1]
        h = b - a
        t = (x - a) / h
        # производные базисов по t
        dh00 = -6*t + 6*t*t
        dh10 = 1 - 4*t + 3*t*t
        dh01 = 6*t - 6*t*t
        dh11 = -2*t + 3*t*t
        return (ya*dh00 + ma*h*dh10 + yb*dh01 + mb*h*dh11) / h

    return f, fprime


# ──────────────────────────────────────────────────────────────────────────────
# Генератор SVG-графиков через matplotlib
# (требует pip install -r requirements-dev.txt)
# ──────────────────────────────────────────────────────────────────────────────

def make_graph_svg(
    f,
    x_range,
    y_range,
    *,
    fprime=None,
    x0=None,
    x_marks=(),       # [(x, "−3"), (x, "1"), ...] — что подписать на оси X
    y_marks=(),       # [(y, "5"), ...] — что подписать на оси Y
    f_label=None,     # "y=f(x)" или "y=f'(x)"
    f_label_pos=None, # (x, y) для подписи функции
    marked_points=(), # [(x, "x_1"), ...] — отмеченные на оси X точки с подписью
    extra_paths=(),   # дополнительные кривые: [(np_x, np_y, kwargs), ...]
    tangent_nodes=(), # [(x, y), ...] — жирные точки на касательной (узлы сетки)
    x0_color="#d12b3a",  # цвет пунктира от оси X до точки касания
    marked_color="#1f1f1f",  # цвет точек/пунктиров для marked_points
    domain=None,      # (a, b) — интервал определения функции; концы рисуются как выколотые точки
    figsize=(4.5, 3.5),
    grid=True,
):
    """
    Возвращает строку SVG (<svg>...</svg>) с графиком функции.
    Касательная (если задана через fprime + x0) гарантированно касается f в точке x0.
    """
    import io
    import re
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize)

    xmin, xmax = x_range
    ymin, ymax = y_range

    if grid:
        ax.set_xticks(np.arange(int(xmin), int(xmax) + 1, 1), minor=False)
        ax.set_yticks(np.arange(int(ymin), int(ymax) + 1, 1), minor=False)
        ax.grid(True, linestyle="-", linewidth=0.5, color="#c8c8c8", alpha=0.9)

    # оси через 0
    ax.spines["left"].set_position("zero")
    ax.spines["bottom"].set_position("zero")
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_color("#1f1f1f")
    ax.spines["bottom"].set_color("#1f1f1f")
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)

    # стрелочки на концах осей
    ax.plot(1, 0, ">k", transform=ax.get_yaxis_transform(), clip_on=False, markersize=6)
    ax.plot(0, 1, "^k", transform=ax.get_xaxis_transform(), clip_on=False, markersize=6)

    # подписи "x" и "y" у концов осей
    ax.text(xmax, -0.06 * (ymax - ymin), "x", ha="left", va="top",
            fontsize=11, style="italic", transform=ax.transData)
    ax.text(-0.04 * (xmax - xmin), ymax, "y", ha="right", va="top",
            fontsize=11, style="italic", transform=ax.transData)

    # убрать стандартные числа осей
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.tick_params(axis="both", which="both", length=0)

    # подписи "0" в начале координат (если в зоне)
    if xmin <= 0 <= xmax and ymin <= 0 <= ymax:
        ax.text(0.12, -0.12, "0", ha="left", va="top", fontsize=10)

    # подписи нужных чисел на осях
    for x, label in x_marks:
        ax.text(x, -0.12, label, ha="center", va="top", fontsize=10)
    for y, label in y_marks:
        ax.text(-0.12, y, label, ha="right", va="center", fontsize=10)

    # график функции (только в области определения, если задана)
    if domain is not None:
        a, b = domain
        xs = np.linspace(a, b, 400)
    else:
        xs = np.linspace(xmin, xmax, 400)
    ys = np.array([f(x) for x in xs])
    ax.plot(xs, ys, color="#1f1f1f", linewidth=1.8)

    # выколотые точки на концах интервала определения
    if domain is not None:
        a, b = domain
        ax.plot([a, b], [f(a), f(b)], "o",
                markerfacecolor="white", markeredgecolor="#1f1f1f",
                markersize=7, markeredgewidth=1.5, zorder=10)

    # касательная — настоящая, через (x0, f(x0)) с наклоном fprime(x0)
    if fprime is not None and x0 is not None:
        slope = fprime(x0)
        y0v = f(x0)
        ts = np.array([xmin, xmax])
        ax.plot(ts, y0v + slope * (ts - x0), color="#1f1f1f", linewidth=1.2)

        # вертикальная цветная пунктирная линия от оси X до точки касания
        ax.plot([x0, x0], [0, y0v], linestyle=(0, (4, 3)),
                color=x0_color, linewidth=1.4)
        # точка касания на графике (маленькая)
        ax.plot([x0], [y0v], "o", color=x0_color, markersize=4.5, zorder=5)
        # метка x_0 под осью
        ax.text(x0, -0.12, r"$x_0$", ha="center", va="top",
                fontsize=10, color=x0_color)

    # жирные узловые точки на касательной (для подсчёта наклона)
    for nx, ny in tangent_nodes:
        ax.plot([nx], [ny], "o", color="#1f1f1f", markersize=7, zorder=6)

    # отмеченные точки на оси X (x1, x2, ...)
    for x, label in marked_points:
        ax.plot([x, x], [0, f(x)], linestyle=(0, (3, 3)),
                color=marked_color, linewidth=1.2, alpha=0.85)
        ax.plot(x, 0, "o", color=marked_color, markersize=5, zorder=5)
        if label:
            ax.text(x, -0.22, label, ha="center", va="top",
                    fontsize=10, color=marked_color)

    # дополнительные кривые
    for arr_x, arr_y, kwargs in extra_paths:
        ax.plot(arr_x, arr_y, **kwargs)

    # подпись y=f(x)
    if f_label and f_label_pos:
        ax.text(*f_label_pos, f_label, fontsize=10, style="italic")

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")

    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    svg = buf.getvalue()
    # Убрать XML-декларацию и DOCTYPE, оставить только <svg>...</svg>
    svg = re.sub(r"^<\?xml[^>]*\?>\s*", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg)
    return svg


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

# ── Прототип 1: По графику f — точки положительной/отрицательной f' ──────────

def _format_indices(n):
    """'x_1, x_2, ..., x_n' с фигурными скобками для двузначных индексов."""
    return ", ".join(f"x_{i+1}" if i + 1 < 10 else f"x_{{{i+1}}}" for i in range(n))


_NUM_WORDS = {
    7: "семь", 8: "восемь", 9: "девять", 10: "десять", 11: "одиннадцать", 12: "двенадцать",
}


def _znaki_task(extrema, points_x, sign, x_range, y_range, label_pos, figsize=(7.5, 4.0)):
    """
    Возвращает (text, answer, svg) для задачи прототипа 1.
    Ответ считается автоматически: сколько отмеченных точек попадает
    в зону f' нужного знака.
    sign: '+' (положительна) или '-' (отрицательна).
    """
    f, fprime = wavy_from_points(extrema)
    n = len(points_x)

    answer = sum(
        1 for x in points_x
        if (sign == '+' and fprime(x) > 0) or (sign == '-' and fprime(x) < 0)
    )

    sign_word = "положительна" if sign == '+' else "отрицательна"
    text = (
        rf"На рисунке изображён график функции \(y = f(x)\). На оси абсцисс "
        rf"отмечено {_NUM_WORDS[n]} точек: \({_format_indices(n)}\). "
        rf"Найдите количество отмеченных точек, в которых производная функции "
        rf"\(f(x)\) {sign_word}."
    )

    marked = [
        (x, rf"$x_{{{i+1}}}$") for i, x in enumerate(points_x)
    ]

    svg = make_graph_svg(
        f, x_range=x_range, y_range=y_range,
        marked_points=marked,
        f_label="y=f(x)", f_label_pos=label_pos,
        figsize=figsize,
        grid=False,
    )
    return (text, str(answer), svg)


def _svg_znaki_pos():
    # Извилистая волна: 6 экстремумов разной амплитуды + промежуточные
    # точки с наклоном задают асимметрию подъёмов и спусков.
    # Зоны f'>0: (-∞,-5), (-3,-1), (1.2,3.5), (5,+∞)
    f, fprime = wavy_from_points([
        (-5, 1.8),                  # max
        (-4.0, 0.6, -2.4),          # промежуточная: крутой спуск
        (-3, -2.2),                 # min
        (-2.0, -0.8, 2.0),          # промежуточная: пологий подъём
        (-1, 1.6),                  # max
        (-0.2, 0.5, -1.8),          # перегиб на спуске
        (1.2, -1.2),                # min
        (2.0, 0.0, 1.6),            # промежуточная
        (3.5, 1.2),                 # max
        (4.2, 0.4, -1.4),           # промежуточная
        (5, -1.8),                  # min
    ])
    points = [
        (-5.7, r"$x_1$"),
        (-4.0, r"$x_2$"),
        (-2.5, r"$x_3$"),
        (-0.4, r"$x_4$"),
        ( 0.5, r"$x_5$"),
        ( 2.2, r"$x_6$"),
        ( 3.6, r"$x_7$"),
        ( 4.4, r"$x_8$"),
        ( 4.8, r"$x_9$"),
        ( 5.7, r"$x_{10}$"),
    ]
    return make_graph_svg(
        f, x_range=(-7, 7), y_range=(-3, 3),
        marked_points=points,
        f_label="y=f(x)", f_label_pos=(2, 2.4),
        figsize=(7.5, 4.0),
        grid=False,
    )

def _svg_znaki_neg():
    # Другая извилистая волна с асимметричными скоростями.
    f, fprime = wavy_from_points([
        (-4, 2.4),
        (-3.2, 1.6, -1.2),
        (-2, -1),
        (-1.0, 0.6, 2.5),
        (0, 2.8),
        (0.8, 1.6, -2.0),
        (2, -0.6),
        (2.7, 0.5, 1.8),
        (4, 1.8),
    ])
    points = [
        (-4.4, r"$x_1$"),
        (-3.0, r"$x_2$"),
        (-2.5, r"$x_3$"),
        (-1.0, r"$x_4$"),
        ( 0.7, r"$x_5$"),
        ( 1.5, r"$x_6$"),
        ( 2.6, r"$x_7$"),
        ( 4.5, r"$x_8$"),
        ( 5.0, r"$x_9$"),
    ]
    return make_graph_svg(
        f, x_range=(-6, 6), y_range=(-3, 4),
        marked_points=points,
        f_label="y=f(x)", f_label_pos=(-5.5, 3.0),
        figsize=(7.2, 4.2),
        grid=False,
    )

TYPE_F_ZNAKI = [
    # 1. Старая задача (10 точек, f'>0). Оставляем сложную волну.
    _znaki_task(
        extrema=[
            (-5, 1.8), (-4.0, 0.6, -2.4), (-3, -2.2), (-2.0, -0.8, 2.0),
            (-1, 1.6), (-0.2, 0.5, -1.8), (1.2, -1.2),
            (2.0, 0.0, 1.6), (3.5, 1.2), (4.2, 0.4, -1.4), (5, -1.8),
        ],
        points_x=[-5.7, -4.0, -2.5, -0.4, 0.5, 2.2, 3.6, 4.4, 4.8, 5.7],
        sign='+',
        x_range=(-7, 7), y_range=(-3, 3), label_pos=(2, 2.4),
    ),
    # 2. Старая задача (9 точек, f'<0).
    _znaki_task(
        extrema=[
            (-4, 2.4), (-3.2, 1.6, -1.2), (-2, -1), (-1.0, 0.6, 2.5),
            (0, 2.8), (0.8, 1.6, -2.0), (2, -0.6),
            (2.7, 0.5, 1.8), (4, 1.8),
        ],
        points_x=[-4.4, -3.0, -2.5, -1.0, 0.7, 1.5, 2.6, 4.5, 5.0],
        sign='-',
        x_range=(-6, 6), y_range=(-3, 4), label_pos=(-5.5, 3.0),
        figsize=(7.2, 4.2),
    ),
    # 3. 8 точек, f'>0.
    _znaki_task(
        extrema=[
            (-4, -1.5), (-2.5, 0.8, 2.0), (-1, 2.2),
            (0.5, 0.5, -1.8), (2, -1.8), (3, 0.6, 1.6), (4, 2.0),
        ],
        points_x=[-3.5, -2.0, -1.6, 0.0, 1.0, 1.8, 3.5, 4.5],
        sign='+',
        x_range=(-5.5, 5.5), y_range=(-3, 3), label_pos=(-5, 2.4),
        figsize=(7.0, 4.0),
    ),
    # 4. 11 точек, f'<0.
    _znaki_task(
        extrema=[
            (-6, 1.5), (-4.5, -0.5, -1.5), (-3, -2),
            (-1.5, 0.5, 1.6), (0, 2), (1, 0.8, -1.8), (2.5, -1.5),
            (4, 1.2), (5, 0, -1.5),
        ],
        points_x=[-5.5, -5.0, -3.5, -2.0, -1.0, 0.5, 1.5, 2.0, 3.5, 4.5, 5.5],
        sign='-',
        x_range=(-7, 7), y_range=(-3, 3), label_pos=(-6.5, 2.4),
        figsize=(8.0, 4.0),
    ),
    # 5. 10 точек, f'<0.
    _znaki_task(
        extrema=[
            (-5, -1.5), (-3.5, 0.8, 1.5), (-2, 2),
            (-0.5, 0.5, -1.8), (1, -1.5), (2.5, 0.5, 1.4), (4, 1.8),
        ],
        points_x=[-5.5, -4.5, -3.0, -1.5, -0.7, 0.0, 1.5, 2.0, 3.5, 5.0],
        sign='-',
        x_range=(-7, 6), y_range=(-3, 3), label_pos=(-6.5, 2.4),
        figsize=(7.5, 4.0),
    ),
    # 6. 7 точек, f'>0.
    _znaki_task(
        extrema=[
            (-3, 2), (-1.5, 0.5, -1.6), (0, -1.8),
            (1.5, 0.5, 1.6), (3, 2.2),
        ],
        points_x=[-3.5, -2.5, -1.0, 0.5, 1.0, 2.0, 3.5],
        sign='+',
        x_range=(-5, 5), y_range=(-3, 3), label_pos=(-4.5, 2.4),
        figsize=(6.5, 4.0),
    ),
    # 7. 9 точек, f'>0.
    _znaki_task(
        extrema=[
            (-5, 1), (-3.5, -0.5, -1.4), (-2, -2),
            (-0.5, 0, 1.7), (1, 1.8), (2, 0.8, -1.5), (3.5, -1.5),
            (4.5, 0, 1.2), (5.5, 1.4),
        ],
        points_x=[-4.5, -3.0, -2.5, -1.5, -0.5, 0.5, 2.5, 4.0, 5.5],
        sign='+',
        x_range=(-6.5, 7), y_range=(-3, 3), label_pos=(5, 2.4),
        figsize=(7.5, 4.0),
    ),
    # 8. 12 точек, f'>0.
    _znaki_task(
        extrema=[
            (-6, -2), (-4.5, 0, 1.6), (-3, 1.8),
            (-1.5, 0, -1.6), (0, -2), (1.5, 0.5, 1.4), (3, 2),
            (4.5, 0.5, -1.5), (6, -1.8),
        ],
        points_x=[-6.5, -5.5, -4.0, -2.5, -2.0, -0.7, 0.5, 1.0, 2.5, 4.0, 5.0, 6.5],
        sign='+',
        x_range=(-8, 8), y_range=(-3, 3), label_pos=(-7, 2.4),
        figsize=(8.5, 4.0),
    ),
    # 9. 8 точек, f'<0.
    _znaki_task(
        extrema=[
            (-3, 1.8), (-2, 0.5, -1.5), (-1, -1.8),
            (0.5, 0, 1.6), (2, 1.5), (3, 0.5, -1.4), (4, -1.8),
        ],
        points_x=[-2.5, -1.5, -1.2, -0.4, 0.8, 1.5, 2.5, 3.5],
        sign='-',
        x_range=(-4.5, 5), y_range=(-3, 3), label_pos=(-4, 2.4),
        figsize=(6.5, 4.0),
    ),
    # 10. 10 точек, f'>0.
    _znaki_task(
        extrema=[
            (-5, 2), (-4, 0.5, -1.7), (-3, -1.8),
            (-1, 1.8), (0.5, 0, -1.5), (2, -2),
            (3, 0.5, 1.5), (4.5, 2),
        ],
        points_x=[-4.5, -4.0, -3.5, -2.0, -1.0, -0.5, 1.0, 2.5, 3.5, 5.0],
        sign='+',
        x_range=(-6, 6), y_range=(-3, 3), label_pos=(-5.5, 2.4),
        figsize=(7.0, 4.0),
    ),
]

# ── Прототип 2: По графику f — точка с наибольшей/наименьшей f' ──────────────

def _svg_naib_proizv():
    # В точке -1 функция круто растёт (max f'). В точках 2, 3, 4 — экстремум/малый наклон.
    f, fprime = wavy_from_points([
        (-2, -2), (-1, 0.5, 4.0), (0, 3), (2, 1), (3, 1.6, 0.8), (4, 2),
    ])
    return make_graph_svg(
        f, x_range=(-3.5, 5.5), y_range=(-3, 4),
        x_marks=[(-1, "−1"), (2, "2"), (3, "3"), (4, "4")],
        marked_points=[(-1, ""), (2, ""), (3, ""), (4, "")],
        marked_color="#d12b3a",
        f_label="y=f(x)", f_label_pos=(2.5, 3.4),
        figsize=(6.5, 4.5),
    )

def _svg_naim_proizv():
    # В точке -2 крутой спад (min f'). Точки -1, 3, 4 — экстремум/малый наклон.
    f, fprime = wavy_from_points([
        (-3, 2), (-2, 0, -3.5), (-1, -2), (1, 1), (3, -1), (4, -0.4, 1.0), (5, 0.5),
    ])
    return make_graph_svg(
        f, x_range=(-4.5, 5.5), y_range=(-3, 3),
        x_marks=[(-2, "−2"), (-1, "−1"), (3, "3"), (4, "4")],
        marked_points=[(-2, ""), (-1, ""), (3, ""), (4, "")],
        marked_color="#d12b3a",
        f_label="y=f(x)", f_label_pos=(2.5, 2.4),
        figsize=(6.5, 4.5),
    )

TYPE_F_NAIB_NAIM = [
    (
        r"На рисунке изображён график функции \(y = f(x)\). На оси абсцисс "
        r"отмечены точки \(-1\), \(2\), \(3\), \(4\). В какой из этих точек "
        r"значение производной наибольшее? В ответе укажите эту точку.",
        "-1",
        _svg_naib_proizv(),
    ),
    (
        r"На рисунке изображён график функции \(y = f(x)\). На оси абсцисс "
        r"отмечены точки \(-2\), \(-1\), \(3\), \(4\). В какой из этих точек "
        r"значение производной наименьшее? В ответе укажите эту точку.",
        "-2",
        _svg_naim_proizv(),
    ),
]

# ── Прототип 3: Корни уравнения f'(x)=0 по графику f ─────────────────────────

def _svg_korni_count():
    # 5 экстремумов на [-7; 2]. Слева добавлены экстремумы (-9, 1) и (-7.7, -1)
    # — чтобы значение f(-9) попадало в видимую область (для выколотой точки),
    # и при этом на отрезке [-7; 2] корней f'=0 ровно 5.
    f, _ = wavy_from_points([
        (-9, 1),                  # левая граница domain (выколотая точка тут)
        (-7.7, -1),               # min — лежит ВНЕ отрезка [-7; 2]
        (-6, 2.4),                # max
        (-5.0, 1.2, -2.5),        # промежуточная
        (-4, -1.6),               # min
        (-3.0, -0.4, 1.8),        # промежуточная
        (-2, 2.0),                # max
        (-1.2, 1.0, -2.2),        # перегиб
        (0, -2.2),                # min
        (1.0, -0.5, 1.6),         # промежуточная
        (2, 1.4),                 # max
    ])
    return make_graph_svg(
        f, x_range=(-11, 6), y_range=(-3, 3),
        x_marks=[(-7, "−7"), (2, "2")],
        y_marks=[(1, "1"), (-2, "−2")],
        f_label="y=f(x)", f_label_pos=(-10, 2.4),
        domain=(-9, 4),
        figsize=(8.0, 4.0),
        grid=True,
    )

def _svg_korni_one():
    # Один экстремум (минимум) на интервале (-5; 4) при x=1
    f, _ = wavy_from_extrema([
        (-7, 2), (1, -3), (8, 2),
    ])
    return make_graph_svg(
        f, x_range=(-7, 6), y_range=(-4, 4),
        x_marks=[(-3, "−3"), (1, "1")],
        y_marks=[(1, "1"), (-3, "−3")],
        f_label="y=f(x)", f_label_pos=(-6.5, 3.0),
        domain=(-5, 4),
        figsize=(6.5, 5.0),
    )

TYPE_F_KORNI = [
    (
        r"На рисунке изображён график функции \(y = f(x)\), определённой "
        r"на интервале \((-9;\,4)\). Найдите количество корней уравнения "
        r"\(f'(x) = 0\), принадлежащих отрезку \([-7;\,2]\).",
        "5",
        _svg_korni_count(),
    ),
    (
        r"На рисунке изображён график функции \(y = f(x)\), определённой "
        r"на интервале \((-5;\,4)\). Найдите корень уравнения \(f'(x) = 0\).",
        "1",
        _svg_korni_one(),
    ),
]

# ── Прототип 4: По графику f и касательной — значение f'(x_0) ────────────────
# f'(x_0) = тангенс угла наклона касательной = (Δy)/(Δx) по двум точкам сетки.
# Здесь функция f и её производная заданы аналитически — касательная
# гарантированно касается графика в точке x0.

def _svg_kasat_220():
    # Кубическая с горбом и спадом. Точка касания нецелая (x_0 = 0.7).
    # Касательная: y = 2x + 4 (через узлы (-2, 0) и (1, 6)), наклон k=2.
    # f(x) = касательная + (x-x_0)² * α + (x-x_0)³ * β — гарантирует f(x_0)=2x_0+4 и f'(x_0)=2.
    x0 = 0.7
    k = 2
    intercept = 4  # касательная y = kx + intercept
    f = lambda x: k * x + intercept + 0.55 * (x - x0) ** 2 - 0.18 * (x - x0) ** 3
    fprime = lambda x: k + 1.10 * (x - x0) - 0.54 * (x - x0) ** 2
    return make_graph_svg(
        f, x_range=(-4, 4), y_range=(-3, 8),
        fprime=fprime, x0=x0,
        x_marks=[(-3, "−3"), (-2, "−2"), (1, "1"), (2, "2")],
        y_marks=[(2, "2"), (4, "4"), (6, "6")],
        f_label="y=f(x)", f_label_pos=(-3.6, 6.2),
        tangent_nodes=[(-2, 0), (1, 6)],
        figsize=(5.0, 5.5),
    )

def _svg_kasat_276():
    # Кубическая с локальным максимумом и минимумом. Точка касания x_0 = -1.3.
    # Касательная: y = -2x - 1 (через узлы (-1, 1) и (1, -3)), наклон k=-2.
    x0 = -1.3
    k = -2
    intercept = -1
    f = lambda x: k * x + intercept + 0.6 * (x - x0) ** 2 + 0.16 * (x - x0) ** 3
    fprime = lambda x: k + 1.20 * (x - x0) + 0.48 * (x - x0) ** 2
    return make_graph_svg(
        f, x_range=(-5, 4), y_range=(-5, 7),
        fprime=fprime, x0=x0,
        x_marks=[(-3, "−3"), (-1, "−1"), (1, "1"), (3, "3")],
        y_marks=[(-3, "−3"), (1, "1"), (5, "5")],
        f_label="y=f(x)", f_label_pos=(-4.5, 5.0),
        tangent_nodes=[(-1, 1), (1, -3)],
        figsize=(5.0, 5.8),
    )

TYPE_F_KASATELNAYA = [
    (
        r"На рисунке изображены график функции \(y = f(x)\) и касательная "
        r"к нему в точке с абсциссой \(x_0\). Найдите значение производной "
        r"функции \(f(x)\) в точке \(x_0\).",
        "2",
        _svg_kasat_220(),
    ),
    (
        r"На рисунке изображены график функции \(y = f(x)\) и касательная "
        r"к нему в точке с абсциссой \(x_0\). Найдите значение производной "
        r"функции \(f(x)\) в точке \(x_0\).",
        "-2",
        _svg_kasat_276(),
    ),
]

# ── Прототип 5 (объединённый): По графику f' — точки экстремума, max, min ────
# Точки экстремума f = пересечения графика f' с осью X.
# Точки max f = пересечения сверху вниз (с + на −).
# Точки min f = пересечения снизу вверх (с − на +).

def _svg_fprime_extr_count():
    # f' определена на (-19; 3). На отрезке [-17, -4] — 5 точек экстремума f
    # (5 пересечений графика f' с осью X).
    f, _ = wavy_from_points([
        (-17.5, -2),
        (-16, 3),
        (-14, -1.5),
        (-12, 2),
        (-10, -2.5),
        (-8, 1.8),
        (-6, -1),
        (-4, 2.2),
        (-2, -1.5),
        (1, 2),
    ])
    return make_graph_svg(
        f, x_range=(-21, 5), y_range=(-4, 4),
        x_marks=[(-17, "−17"), (-4, "−4"), (1, "1")],
        y_marks=[(1, "1"), (-3, "−3")],
        f_label="y=f'(x)", f_label_pos=(-9, 3.2),
        domain=(-19, 3),
        figsize=(8.8, 4.0),
    )

def _svg_fprime_min_count():
    # f' определена на (-10; 7). На отрезке [-2, 6] — 2 точки минимума f
    # (2 перехода f' с минуса на плюс).
    f, _ = wavy_from_points([
        (-9, 2),
        (-7, -2),
        (-5, 2.5),
        (-3, -1),
        (-1, 2),
        (1, -1.5),    # min f здесь (между точками − и + на отрезке)
        (3, 1.5),
        (5, -1.5),    # min f здесь
        (6.5, 2),
    ])
    return make_graph_svg(
        f, x_range=(-12, 9), y_range=(-3, 3),
        x_marks=[(-2, "−2"), (6, "6")],
        y_marks=[(1, "1"), (-3, "−3")],
        f_label="y=f'(x)", f_label_pos=(-11, 2.4),
        domain=(-10, 7),
        figsize=(8.5, 3.8),
    )

TYPE_FPRIME_EXTR = [
    (
        r"На рисунке изображён график \(y = f'(x)\) — производной функции "
        r"\(f(x)\), определённой на интервале \((-19;\,3)\). Найдите количество "
        r"точек экстремума функции \(f(x)\), принадлежащих отрезку \([-17;\,-4]\).",
        "5",
        _svg_fprime_extr_count(),
    ),
    (
        r"На рисунке изображён график \(y = f'(x)\) — производной функции "
        r"\(f(x)\), определённой на интервале \((-10;\,7)\). Найдите количество "
        r"точек минимума функции \(f(x)\), принадлежащих отрезку \([-2;\,6]\).",
        "2",
        _svg_fprime_min_count(),
    ),
]

# ── Прототип 6 (бывший 7): возрастание/убывание f по графику f' ──────────────

def _svg_fprime_inc_points():
    # Волна f' с экстремумами; 8 точек на оси X, 3 в зоне f'>0
    f, _ = wavy_from_points([
        (-5, 1.5),
        (-4, -1, -1.8),
        (-3, -2),
        (-1, 3),
        (0.5, 0.5, -2.5),
        (2, -2),
        (4, 1.5),
    ])
    points = [
        (-4.6, r"$x_1$"),  # >0 (виртуальное продолжение)
        (-4.2, r"$x_2$"),  # <0
        (-3.4, r"$x_3$"),  # <0
        (-2.6, r"$x_4$"),  # >0  (между min(-3) и max(-1))
        (-2.0, r"$x_5$"),  # >0
        (-1.4, r"$x_6$"),  # >0
        ( 2.5, r"$x_7$"),  # >0  (между min(2) и max(4))
        ( 4.5, r"$x_8$"),  # <0 (виртуальное продолжение)
    ]
    return make_graph_svg(
        f, x_range=(-6, 6), y_range=(-3, 4),
        marked_points=points,
        f_label="y=f'(x)", f_label_pos=(-5.5, 3.2),
        figsize=(7.5, 4.2),
        grid=False,
    )

def _svg_fprime_dec_points():
    # 9 точек, 5 в зоне f'<0
    f, _ = wavy_from_points([
        (-5, -2),
        (-3, 2),
        (-1, -2),
        (1, 2),
        (3, -2),
        (5, 2),
    ])
    points = [
        (-4.5, r"$x_1$"),  # <0
        (-3.8, r"$x_2$"),  # <0
        (-2.0, r"$x_3$"),  # >0
        (-0.5, r"$x_4$"),  # <0
        ( 0.2, r"$x_5$"),  # <0
        ( 1.8, r"$x_6$"),  # >0
        ( 2.4, r"$x_7$"),  # >0
        ( 3.6, r"$x_8$"),  # <0
        ( 4.5, r"$x_9$"),  # <0
    ]
    return make_graph_svg(
        f, x_range=(-6, 6), y_range=(-3, 3),
        marked_points=points,
        f_label="y=f'(x)", f_label_pos=(-5.5, 2.4),
        figsize=(7.5, 4.0),
        grid=False,
    )

TYPE_FPRIME_INC_DEC = [
    (
        r"На рисунке изображён график \(y = f'(x)\) — производной функции "
        r"\(f(x)\). На оси абсцисс отмечено восемь точек: "
        r"\(x_1, x_2, x_3, x_4, x_5, x_6, x_7, x_8\). "
        r"Сколько из этих точек принадлежит промежуткам возрастания функции \(f(x)\)?",
        "4",
        _svg_fprime_inc_points(),
    ),
    (
        r"На рисунке изображён график \(y = f'(x)\) — производной функции "
        r"\(f(x)\). На оси абсцисс отмечено девять точек: "
        r"\(x_1, x_2, x_3, x_4, x_5, x_6, x_7, x_8, x_9\). "
        r"Сколько из этих точек принадлежит промежуткам убывания функции \(f(x)\)?",
        "5",
        _svg_fprime_dec_points(),
    ),
]

# ── Прототип 7 (бывший 8): наиб/наим значение f на отрезке по графику f' ─────

def _svg_fprime_max_value():
    # f' определена на (-5; 5). На отрезке [-2; 3] f' меняет знак с + на - в x=1
    # → max f в точке x=1.
    f, _ = wavy_from_points([
        (-4, -2),
        (-1, 3),
        (3, -2),
    ])
    return make_graph_svg(
        f, x_range=(-7, 7), y_range=(-3, 4),
        x_marks=[(-2, "−2"), (1, "1"), (3, "3")],
        y_marks=[(1, "1"), (-2, "−2")],
        f_label="y=f'(x)", f_label_pos=(-6.5, 3.2),
        domain=(-5, 5),
        figsize=(7.5, 5.0),
        grid=True,
    )

def _svg_fprime_min_value():
    # f' определена на (-6; 3). На отрезке [-5; -2] f' меняет знак с - на + в x=-3
    # → min f в точке x=-3.
    f, _ = wavy_from_points([
        (-6, 2),
        (-4, -3),
        (-2, 2),
        (1, -2),
    ])
    return make_graph_svg(
        f, x_range=(-8, 5), y_range=(-4, 3),
        x_marks=[(-5, "−5"), (-3, "−3"), (-2, "−2")],
        y_marks=[(1, "1"), (-3, "−3")],
        f_label="y=f'(x)", f_label_pos=(-7.5, 2.4),
        domain=(-6, 3),
        figsize=(7.5, 4.5),
        grid=True,
    )

TYPE_FPRIME_MIN_MAX_SEGMENT = [
    (
        r"На рисунке изображён график \(y = f'(x)\) — производной функции "
        r"\(f(x)\), определённой на интервале \((-5;\,5)\). В какой точке отрезка "
        r"\([-2;\,3]\) функция \(f(x)\) принимает наибольшее значение?",
        "1",
        _svg_fprime_max_value(),
    ),
    (
        r"На рисунке изображён график \(y = f'(x)\) — производной функции "
        r"\(f(x)\), определённой на интервале \((-6;\,3)\). В какой точке отрезка "
        r"\([-5;\,-2]\) функция \(f(x)\) принимает наименьшее значение?",
        "-3",
        _svg_fprime_min_value(),
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Список прототипов
# ──────────────────────────────────────────────────────────────────────────────

ASSIGNMENTS = [
    {
        "title": "Знаки производной по графику функции",
        "order": 1,
        "description": (
            r"Если функция \(f(x)\) возрастает в точке \(x_0\) — то \(f'(x_0) > 0\); "
            r"если убывает — то \(f'(x_0) < 0\). "
            r"Считаем количество отмеченных точек, попадающих на промежутки нужного знака."
        ),
        "required_correct": 2,
        "questions": TYPE_F_ZNAKI,
    },
    {
        "title": "Точка с наибольшей/наименьшей производной",
        "order": 2,
        "description": (
            r"Сравниваем угол наклона касательной в каждой из отмеченных точек: "
            r"производная больше там, где график круче поднимается; "
            r"производная меньше там, где график круче спускается."
        ),
        "required_correct": 2,
        "questions": TYPE_F_NAIB_NAIM,
    },
    {
        "title": "Корни уравнения f'(x) = 0",
        "order": 3,
        "description": (
            r"\(f'(x_0) = 0\) — это точки, где касательная горизонтальна. "
            r"Считаем точки локальных максимумов и минимумов на отрезке."
        ),
        "required_correct": 2,
        "questions": TYPE_F_KORNI,
    },
    {
        "title": "Производная по касательной к графику",
        "order": 4,
        "description": (
            r"Производная \(f'(x_0)\) равна угловому коэффициенту касательной "
            r"в точке \(x_0\): \(f'(x_0) = \tan\alpha = \dfrac{\Delta y}{\Delta x}\). "
            r"Берём две точки касательной на узлах сетки и считаем отношение."
        ),
        "required_correct": 2,
        "questions": TYPE_F_KASATELNAYA,
    },
    {
        "title": "Точки экстремума, максимума и минимума по графику f'",
        "order": 5,
        "description": (
            r"Точка экстремума функции \(f\) — точка, где её производная \(f'(x)\) меняет знак. "
            r"На графике \(y = f'(x)\) это точки пересечения оси \(Ox\) с переменой знака. "
            r"Точка максимума \(f\): \(f'\) меняет знак с \(+\) на \(-\). "
            r"Точка минимума \(f\): \(f'\) меняет знак с \(-\) на \(+\)."
        ),
        "required_correct": 2,
        "questions": TYPE_FPRIME_EXTR,
    },
    {
        "title": "Точки возрастания/убывания функции по графику f'",
        "order": 6,
        "description": (
            r"Функция \(f\) возрастает там, где \(f'(x) > 0\) (график \(f'\) выше оси), "
            r"и убывает там, где \(f'(x) < 0\) (график \(f'\) ниже оси). "
            r"Считаем отмеченные точки, попадающие в нужную зону."
        ),
        "required_correct": 2,
        "questions": TYPE_FPRIME_INC_DEC,
    },
    {
        "title": "Наибольшее/наименьшее значение функции на отрезке",
        "order": 7,
        "description": (
            r"На отрезке функция достигает экстремума либо во внутренней точке, где \(f'\) меняет знак "
            r"(\(+ \to -\) — максимум, \(- \to +\) — минимум), либо на границе отрезка. "
            r"Сравниваем значения и выбираем нужное."
        ),
        "required_correct": 2,
        "questions": TYPE_FPRIME_MIN_MAX_SEGMENT,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 8 questions (производная и графики)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing EGE-8 lesson before inserting",
        )

    def handle(self, *args, **options):
        course = Course.objects.filter(slug="ege-profile-math").first()
        if not course:
            self.stdout.write(self.style.ERROR("Course 'ege-profile-math' not found."))
            return

        module, _ = Module.objects.get_or_create(
            course=course,
            order=1,
            defaults={
                "title": "Первая часть",
                "description": "Задачи первой части профильного ЕГЭ.",
            },
        )

        if options["clear"]:
            deleted, _ = Lesson.objects.filter(module=module, order=8).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted existing lesson (order=8): {deleted} objects"
            ))

        lesson, created = Lesson.objects.get_or_create(
            module=module,
            order=8,
            defaults={
                "title": "Задание 8",
                "lesson_type": "practice",
            },
        )
        if not created:
            self.stdout.write(self.style.WARNING(
                "Lesson already exists (use --clear to reset)."
            ))

        total_q = 0
        for data in ASSIGNMENTS:
            assignment, created = Assignment.objects.get_or_create(
                lesson=lesson,
                order=data["order"],
                defaults={
                    "title": data["title"],
                    "description": data["description"],
                    "answer_type": "decimal_input",
                    "required_correct": data["required_correct"],
                },
            )
            if not created:
                self.stdout.write(self.style.WARNING(
                    f"  Assignment already exists: {assignment.title} -- skipping"
                ))
                continue

            for idx, item in enumerate(data["questions"]):
                if len(item) == 3:
                    q_text, answer, image_svg = item
                else:
                    q_text, answer = item
                    image_svg = ""
                question = TestQuestion.objects.create(
                    assignment=assignment,
                    question_text=q_text,
                    order=idx + 1,
                    image_svg=image_svg,
                )
                AnswerOption.objects.create(
                    question=question,
                    text=answer,
                    is_correct=True,
                )
                total_q += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done! Lesson: Zadacha 8, {total_q} questions added."
        ))
