# -*- coding: utf-8 -*-
"""
Management command: populate EGE task 11 questions (графики функций).

Usage:
    python manage.py populate_ege11
    python manage.py populate_ege11 --clear

Lesson order=11 inside module order=1 of course ege-profile-math.

Все задачи — чтение графика: даны точки на графике (чёрные жирные кружки),
по ним определяется коэффициент функции. SVG генерируется через matplotlib
(требует requirements-dev.txt: matplotlib + numpy).

Workflow обновления:
    1) править этот файл
    2) python manage.py populate_ege11 --clear
    3) python manage.py dumpdata users.Lesson users.Assignment users.TestQuestion
       users.AnswerOption --indent 2 > fixtures/lesson_11.json
    4) git commit fixtures/lesson_11.json
    5) на Railway: python manage.py loaddata lesson_11
"""

import math

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ──────────────────────────────────────────────────────────────────────────────
# SVG-генератор графика через matplotlib
# ──────────────────────────────────────────────────────────────────────────────

def make_graph_svg(
    curves,            # [(f, x_range_local, label, label_pos), ...] — кривые
    x_range, y_range,
    *,
    points=(),         # [(x, y), ...] — чёрные жирные точки (узловые)
    x_marks=(),        # [(x, "−3"), ...]
    y_marks=(),        # [(y, "5"), ...]
    figsize=(5.2, 5.2),
):
    """Возвращает inline SVG-строку: оси, сетка, кривые и чёрные узлы."""
    import io
    import re
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize)
    xmin, xmax = x_range
    ymin, ymax = y_range

    # сетка
    ax.set_xticks(np.arange(int(xmin), int(xmax) + 1, 1))
    ax.set_yticks(np.arange(int(ymin), int(ymax) + 1, 1))
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

    # стрелочки
    ax.plot(1, 0, ">k", transform=ax.get_yaxis_transform(), clip_on=False, markersize=6)
    ax.plot(0, 1, "^k", transform=ax.get_xaxis_transform(), clip_on=False, markersize=6)

    # подписи "x" и "y"
    ax.text(xmax, -0.06 * (ymax - ymin), "x", ha="left", va="top",
            fontsize=11, style="italic")
    ax.text(-0.04 * (xmax - xmin), ymax, "y", ha="right", va="top",
            fontsize=11, style="italic")

    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.tick_params(axis="both", length=0)

    # "0" в начале
    if xmin <= 0 <= xmax and ymin <= 0 <= ymax:
        ax.text(0.12, -0.12, "0", ha="left", va="top", fontsize=10)

    for x, label in x_marks:
        ax.text(x, -0.12, label, ha="center", va="top", fontsize=10)
    for y, label in y_marks:
        ax.text(-0.12, y, label, ha="right", va="center", fontsize=10)

    # кривые
    for f, x_local, label, label_pos in curves:
        a, b = x_local
        xs = np.linspace(a, b, 400)
        ys = np.array([f(x) for x in xs])
        # обрезаем по y_range
        mask = np.isfinite(ys)
        ax.plot(xs[mask], ys[mask], color="#1f1f1f", linewidth=1.8)
        if label and label_pos:
            ax.text(*label_pos, label, fontsize=10, style="italic")

    # чёрные жирные точки
    for px, py in points:
        ax.plot([px], [py], "o", color="#1f1f1f", markersize=7, zorder=10)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")

    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    svg = buf.getvalue()
    svg = re.sub(r"^<\?xml[^>]*\?>\s*", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg)
    return svg


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

# ── 1. f(x) = log_a(x), найти f(N) ───────────────────────────────────────────
def _svg_loga(a, marker_x, marker_y, x_range=(-1, 9), y_range=(-3, 2)):
    f = lambda x: math.log(x, a) if x > 0 else float("nan")
    return make_graph_svg(
        curves=[(f, (0.05, x_range[1] - 0.1), "y=f(x)", (x_range[1] * 0.45, marker_y * 1.6 if marker_y > 0 else 0.7))],
        x_range=x_range, y_range=y_range,
        points=[(marker_x, marker_y)],
        x_marks=[(1, "1"), (marker_x, str(marker_x))] if marker_x != 1 else [(1, "1")],
        y_marks=[(marker_y, str(marker_y))] if marker_y != 0 else [],
    )

TYPE_LOG_A = [
    (
        r"На рисунке изображён график функции вида \(f(x) = \log_a x\). "
        r"Найдите значение \(f(8)\).",
        "-3",
        _svg_loga(a=0.5, marker_x=2, marker_y=-1, x_range=(-1, 10), y_range=(-3, 2)),
    ),
    (
        r"На рисунке изображён график функции вида \(f(x) = \log_a x\). "
        r"Найдите значение \(f(8)\).",
        "3",
        _svg_loga(a=2, marker_x=2, marker_y=1, x_range=(-1, 10), y_range=(-2, 4)),
    ),
]


# ── 2. f(x) = a^x, найти f(N) ────────────────────────────────────────────────
def _svg_ax(a, marker_x, marker_y, x_range=(-3, 3), y_range=(-1, 6)):
    f = lambda x: a ** x
    return make_graph_svg(
        curves=[(f, x_range, "y=f(x)", (x_range[1] * 0.3, y_range[1] * 0.7))],
        x_range=x_range, y_range=y_range,
        points=[(marker_x, marker_y)],
        x_marks=[(marker_x, str(marker_x))] if marker_x != 0 else [],
        y_marks=[(marker_y, str(marker_y))] if marker_y not in (0, 1) else [],
    )

TYPE_A_X = [
    (
        r"На рисунке изображён график функции вида \(f(x) = a^x\). "
        r"Найдите значение \(f(-3)\).",
        "64",
        _svg_ax(a=0.25, marker_x=-1, marker_y=4, x_range=(-3, 3), y_range=(-1, 8)),
    ),
    (
        r"На рисунке изображён график функции вида \(f(x) = a^x\). "
        r"Найдите значение \(f(5)\).",
        "32",
        _svg_ax(a=2, marker_x=1, marker_y=2, x_range=(-2, 6), y_range=(-1, 8)),
    ),
]


# ── 3. f(x) = k/x, найти f(N) ────────────────────────────────────────────────
def _svg_kx(k, marker_x, marker_y, x_range=(-7, 7), y_range=(-5, 5)):
    f = lambda x: k / x if abs(x) > 1e-9 else float("nan")
    # Две ветви
    eps = 0.05
    return make_graph_svg(
        curves=[
            (f, (x_range[0], -eps), "", None),
            (f, (eps, x_range[1]), "y=f(x)", (x_range[1] * 0.4, marker_y * 1.7 if marker_y else 1.5)),
        ],
        x_range=x_range, y_range=y_range,
        points=[(marker_x, marker_y)],
        x_marks=[(marker_x, str(marker_x))],
        y_marks=[(marker_y, str(marker_y))] if marker_y != 0 else [],
    )

TYPE_K_X = [
    (
        r"На рисунке изображён график функции вида \(f(x) = \dfrac{k}{x}\). "
        r"Найдите значение \(f(10)\).",
        "0.2",
        _svg_kx(k=2, marker_x=2, marker_y=1, x_range=(-6, 6), y_range=(-4, 4)),
    ),
    (
        r"На рисунке изображён график функции вида \(f(x) = \dfrac{k}{x}\). "
        r"Найдите значение \(f(30)\).",
        "0.1",
        _svg_kx(k=3, marker_x=3, marker_y=1, x_range=(-6, 6), y_range=(-4, 4)),
    ),
]


# ── 4. f(x) = ax² + bx + c, найти f(N) ───────────────────────────────────────
def _svg_parabola(a, b, c, x_range=(-3, 5), y_range=(-2, 8)):
    f = lambda x: a * x * x + b * x + c
    # Корни через дискриминант (если они есть)
    D = b * b - 4 * a * c
    points = []
    if D >= 0:
        r1 = (-b - math.sqrt(D)) / (2 * a)
        r2 = (-b + math.sqrt(D)) / (2 * a)
        if r1.is_integer():
            points.append((int(r1), 0))
        if r2.is_integer() and r2 != r1:
            points.append((int(r2), 0))
    return make_graph_svg(
        curves=[(f, x_range, "y=f(x)", (x_range[1] * 0.5, y_range[1] * 0.6))],
        x_range=x_range, y_range=y_range,
        points=points,
        x_marks=[(int(p[0]), str(int(p[0]))) for p in points],
    )

TYPE_PARABOLA = [
    (
        r"На рисунке изображён график функции вида \(f(x) = ax^2 + bx + c\). "
        r"Найдите значение \(f(-2)\).",
        "12",
        _svg_parabola(a=1, b=-3, c=2, x_range=(-3, 5), y_range=(-2, 14)),
    ),
    (
        r"На рисунке изображён график функции вида \(f(x) = ax^2 + bx + c\). "
        r"Найдите значение \(f(-3)\).",
        "24",
        _svg_parabola(a=1, b=-4, c=3, x_range=(-4, 5), y_range=(-2, 25)),
    ),
]


# ── 5. f=k/x ∩ g=ax+b, найти абсциссу B ──────────────────────────────────────
def _svg_kx_line(k, a_lin, b_lin, A_x, B_x, x_range=(-8, 8), y_range=(-6, 6)):
    f = lambda x: k / x if abs(x) > 1e-9 else float("nan")
    g = lambda x: a_lin * x + b_lin
    eps = 0.05
    return make_graph_svg(
        curves=[
            (f, (x_range[0], -eps), "", None),
            (f, (eps, x_range[1]), "y=f(x)", (x_range[1] * 0.4, k / (x_range[1] * 0.4) + 1)),
            (g, x_range, "y=g(x)", (x_range[1] * 0.5, a_lin * x_range[1] * 0.5 + b_lin - 1)),
        ],
        x_range=x_range, y_range=y_range,
        points=[(A_x, k / A_x), (B_x, k / B_x)],
        x_marks=[(A_x, str(A_x)), (B_x, str(B_x))],
    )

TYPE_KX_LINE = [
    (
        r"На рисунке изображены графики функций вида \(f(x) = \dfrac{k}{x}\) "
        r"и \(g(x) = ax + b\), пересекающиеся в точках \(A\) и \(B\). "
        r"Найдите абсциссу точки \(B\).",
        "6",
        # f=12/x, g=0.5x-1: пересечения x=-4 (A) и x=6 (B)
        _svg_kx_line(k=12, a_lin=0.5, b_lin=-1, A_x=-4, B_x=6,
                     x_range=(-7, 8), y_range=(-5, 5)),
    ),
    (
        r"На рисунке изображены графики функций вида \(f(x) = \dfrac{k}{x}\) "
        r"и \(g(x) = ax + b\), пересекающиеся в точках \(A\) и \(B\). "
        r"Найдите абсциссу точки \(B\).",
        "10",
        # f=10/x, g=0.2x-1: пересечения x=-5 (A) и x=10 (B)
        _svg_kx_line(k=10, a_lin=0.2, b_lin=-1, A_x=-5, B_x=10,
                     x_range=(-8, 12), y_range=(-4, 4)),
    ),
]


# ── 6. f=ax²+bx+c ∩ g=kx, найти абсциссу B ───────────────────────────────────
def _svg_parabola_line(a, b, c, k, A_x, B_x, x_range=(-2, 6), y_range=(-2, 10)):
    f = lambda x: a * x * x + b * x + c
    g = lambda x: k * x
    return make_graph_svg(
        curves=[
            (f, x_range, "y=f(x)", (x_range[1] * 0.55, f(x_range[1] * 0.55) + 0.5)),
            (g, x_range, "y=g(x)", (x_range[1] * 0.4, k * x_range[1] * 0.4 - 1)),
        ],
        x_range=x_range, y_range=y_range,
        points=[(A_x, f(A_x)), (B_x, f(B_x))],
        x_marks=[(B_x, str(B_x))],
    )

TYPE_PARABOLA_LINE = [
    (
        r"На рисунке изображены графики функций \(f(x) = ax^2 + bx + c\) "
        r"и \(g(x) = kx\), пересекающиеся в точках \(A\) и \(B\). "
        r"Найдите абсциссу точки \(B\).",
        "3",
        # f=x²-2x, g=x: пересечения x=0 (A) и x=3 (B)
        _svg_parabola_line(a=1, b=-2, c=0, k=1, A_x=0, B_x=3,
                           x_range=(-2, 5), y_range=(-2, 6)),
    ),
    (
        r"На рисунке изображены графики функций \(f(x) = ax^2 + bx + c\) "
        r"и \(g(x) = kx\), пересекающиеся в точках \(A\) и \(B\). "
        r"Найдите абсциссу точки \(B\).",
        "4",
        # f=x²-x, g=3x: пересечения x=0 (A) и x=4 (B)
        _svg_parabola_line(a=1, b=-1, c=0, k=3, A_x=0, B_x=4,
                           x_range=(-2, 6), y_range=(-2, 14)),
    ),
]


# ── 7. f=a√x ∩ g=kx, найти абсциссу B ────────────────────────────────────────
def _svg_sqrt_line(a, k, A_x, B_x, x_range=(-1, 12), y_range=(-2, 7)):
    f = lambda x: a * math.sqrt(x) if x >= 0 else float("nan")
    g = lambda x: k * x
    return make_graph_svg(
        curves=[
            (f, (0, x_range[1]), "y=f(x)", (x_range[1] * 0.6, a * math.sqrt(x_range[1] * 0.6) + 0.5)),
            (g, x_range, "y=g(x)", (x_range[1] * 0.7, k * x_range[1] * 0.7 - 0.8)),
        ],
        x_range=x_range, y_range=y_range,
        points=[(A_x, f(A_x)), (B_x, f(B_x))],
        x_marks=[(B_x, str(B_x))],
    )

TYPE_SQRT_LINE = [
    (
        r"На рисунке изображены графики функций вида \(f(x) = a\sqrt{x}\) "
        r"и \(g(x) = kx\), пересекающиеся в точках \(A\) и \(B\). "
        r"Найдите абсциссу точки \(B\).",
        "4",
        # f=2√x, g=x: пересечения x=0 (A), x=4 (B)
        _svg_sqrt_line(a=2, k=1, A_x=0, B_x=4, x_range=(-1, 7), y_range=(-2, 7)),
    ),
    (
        r"На рисунке изображены графики функций вида \(f(x) = a\sqrt{x}\) "
        r"и \(g(x) = kx\), пересекающиеся в точках \(A\) и \(B\). "
        r"Найдите абсциссу точки \(B\).",
        "9",
        # f=3√x, g=x: пересечения x=0 (A), x=9 (B)
        _svg_sqrt_line(a=3, k=1, A_x=0, B_x=9, x_range=(-1, 12), y_range=(-2, 11)),
    ),
]


# ── 8. f(x) = kx + b, найти f(N) ─────────────────────────────────────────────
def _svg_linear(k, b, x_range=(-3, 6), y_range=(-3, 8)):
    f = lambda x: k * x + b
    # Точки пересечения с целыми узлами
    points = []
    for x in range(int(x_range[0]) + 1, int(x_range[1])):
        y = k * x + b
        if abs(y - round(y)) < 1e-9 and y_range[0] < y < y_range[1]:
            points.append((x, round(y)))
            if len(points) >= 2:
                break
    return make_graph_svg(
        curves=[(f, x_range, "y=f(x)", (x_range[1] * 0.6, k * x_range[1] * 0.6 + b + 0.5))],
        x_range=x_range, y_range=y_range,
        points=points,
        x_marks=[(p[0], str(p[0])) for p in points],
        y_marks=[(p[1], str(p[1])) for p in points if p[1] != 0],
    )

TYPE_LINEAR = [
    (
        r"На рисунке изображён график функции вида \(f(x) = kx + b\). "
        r"Найдите значение \(f(7)\).",
        "15",
        # k=2, b=1
        _svg_linear(k=2, b=1, x_range=(-3, 5), y_range=(-3, 9)),
    ),
    (
        r"На рисунке изображён график функции вида \(f(x) = kx + b\). "
        r"Найдите значение \(f(5)\).",
        "9",
        # k=2, b=-1
        _svg_linear(k=2, b=-1, x_range=(-3, 5), y_range=(-3, 9)),
    ),
]


# ── 9. Две линейные, найти точку пересечения ─────────────────────────────────
def _svg_two_linear(k1, b1, k2, b2, x_range=(-5, 5), y_range=(-5, 8)):
    f = lambda x: k1 * x + b1
    g = lambda x: k2 * x + b2
    # точка пересечения
    x_int = (b2 - b1) / (k1 - k2)
    y_int = k1 * x_int + b1
    return make_graph_svg(
        curves=[
            (f, x_range, "", None),
            (g, x_range, "", None),
        ],
        x_range=x_range, y_range=y_range,
        points=[(x_int, y_int)],
        x_marks=[(x_int, str(int(x_int)))] if x_int.is_integer() else [],
        y_marks=[(y_int, str(int(y_int)))] if y_int == int(y_int) else [],
    )

TYPE_TWO_LINEAR = [
    (
        r"На рисунке изображены графики двух линейных функций, пересекающиеся "
        r"в точке \(A\). Найдите абсциссу точки \(A\).",
        "3",
        # y=x+3, y=2x → пересечение x=3, y=6
        _svg_two_linear(k1=1, b1=3, k2=2, b2=0, x_range=(-4, 6), y_range=(-2, 8)),
    ),
    (
        r"На рисунке изображены графики двух линейных функций, пересекающиеся "
        r"в точке \(A\). Найдите абсциссу точки \(A\).",
        "2",
        # y=x+4, y=3x → пересечение x=2, y=6
        _svg_two_linear(k1=1, b1=4, k2=3, b2=0, x_range=(-4, 6), y_range=(-2, 8)),
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
ASSIGNMENTS = [
    {
        "title": "Логарифмическая f(x) = logₐ x",
        "order": 1,
        "description": (
            r"По двум точкам на графике определяем основание \(a\): "
            r"если \(f(x_0) = y_0\), то \(a^{y_0} = x_0\). Затем подставляем нужное "
            r"значение в формулу \(f(N) = \log_a N\)."
        ),
        "required_correct": 2,
        "questions": TYPE_LOG_A,
    },
    {
        "title": "Показательная f(x) = aˣ",
        "order": 2,
        "description": (
            r"По отмеченной точке определяем \(a\): \(a^{x_0} = y_0 \Rightarrow a = y_0^{1/x_0}\). "
            r"Затем считаем \(f(N) = a^N\)."
        ),
        "required_correct": 2,
        "questions": TYPE_A_X,
    },
    {
        "title": "Обратная пропорциональность f(x) = k/x",
        "order": 3,
        "description": (
            r"По отмеченной точке: \(k = x_0 \cdot y_0\). Затем \(f(N) = \dfrac{k}{N}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_K_X,
    },
    {
        "title": "Парабола f(x) = ax² + bx + c",
        "order": 4,
        "description": (
            r"По двум корням и одной дополнительной точке восстанавливаем коэффициенты: "
            r"\(f(x) = a(x - x_1)(x - x_2)\). Затем подставляем \(N\) и считаем \(f(N)\)."
        ),
        "required_correct": 2,
        "questions": TYPE_PARABOLA,
    },
    {
        "title": "Пересечение гиперболы и прямой: f = k/x и g = ax + b",
        "order": 5,
        "description": (
            r"Уравнение \(\dfrac{k}{x} = ax + b\) сводится к квадратному "
            r"\(ax^2 + bx - k = 0\). По известной точке \(A\) находим вторую "
            r"точку пересечения по теореме Виета: \(x_A \cdot x_B = -\dfrac{k}{a}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_KX_LINE,
    },
    {
        "title": "Пересечение параболы и прямой: f = ax² + bx + c и g = kx",
        "order": 6,
        "description": (
            r"Уравнение \(ax^2 + bx + c = kx\) сводится к "
            r"\(ax^2 + (b - k)x + c = 0\). Решаем относительно \(x\) и выбираем "
            r"абсциссу нужной точки пересечения."
        ),
        "required_correct": 2,
        "questions": TYPE_PARABOLA_LINE,
    },
    {
        "title": "Пересечение y = a√x и прямой y = kx",
        "order": 7,
        "description": (
            r"Возводим в квадрат: \(a^2 x = k^2 x^2 \Rightarrow x(k^2 x - a^2) = 0\). "
            r"Отсюда \(x = 0\) (точка \(A\)) или \(x = \dfrac{a^2}{k^2}\) (точка \(B\))."
        ),
        "required_correct": 2,
        "questions": TYPE_SQRT_LINE,
    },
    {
        "title": "Линейная f(x) = kx + b",
        "order": 8,
        "description": (
            r"По двум отмеченным точкам \((x_1, y_1)\) и \((x_2, y_2)\) находим: "
            r"\(k = \dfrac{y_2 - y_1}{x_2 - x_1}\), \(b = y_1 - k \cdot x_1\). "
            r"Затем \(f(N) = kN + b\)."
        ),
        "required_correct": 2,
        "questions": TYPE_LINEAR,
    },
    {
        "title": "Пересечение двух линейных функций",
        "order": 9,
        "description": (
            r"Из каждой прямой определяем коэффициенты по двум точкам. "
            r"Пересечение: \(k_1 x + b_1 = k_2 x + b_2 \Rightarrow x = \dfrac{b_2 - b_1}{k_1 - k_2}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_TWO_LINEAR,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 11 questions (графики функций)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete existing EGE-11 lesson before inserting",
        )

    def handle(self, *args, **options):
        course = Course.objects.filter(slug="ege-profile-math").first()
        if not course:
            self.stdout.write(self.style.ERROR("Course 'ege-profile-math' not found."))
            return
        module, _ = Module.objects.get_or_create(
            course=course, order=1,
            defaults={"title": "Первая часть", "description": "Задачи первой части профильного ЕГЭ."},
        )
        if options["clear"]:
            deleted, _ = Lesson.objects.filter(module=module, order=11).delete()
            self.stdout.write(self.style.WARNING(f"Deleted lesson order=11: {deleted} objects"))
        lesson, created = Lesson.objects.get_or_create(
            module=module, order=11,
            defaults={"title": "Задание 11", "lesson_type": "practice"},
        )
        if not created:
            self.stdout.write(self.style.WARNING("Lesson exists (use --clear to reset)."))

        total_q = 0
        for data in ASSIGNMENTS:
            assignment, created = Assignment.objects.get_or_create(
                lesson=lesson, order=data["order"],
                defaults={
                    "title": data["title"],
                    "description": data["description"],
                    "answer_type": "decimal_input",
                    "required_correct": data["required_correct"],
                },
            )
            if not created:
                self.stdout.write(self.style.WARNING(f"  Skip: {assignment.title}"))
                continue
            for idx, item in enumerate(data["questions"]):
                if len(item) == 3:
                    q_text, answer, image_svg = item
                else:
                    q_text, answer = item
                    image_svg = ""
                question = TestQuestion.objects.create(
                    assignment=assignment, question_text=q_text,
                    order=idx + 1, image_svg=image_svg,
                )
                AnswerOption.objects.create(question=question, text=answer, is_correct=True)
                total_q += 1

        self.stdout.write(self.style.SUCCESS(f"Done! Lesson: Zadacha 11, {total_q} questions added."))
