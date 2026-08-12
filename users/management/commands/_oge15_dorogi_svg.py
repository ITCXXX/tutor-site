# -*- coding: utf-8 -*-
"""SVG-фигуры 4-точечных планов дорог (порт из _preview_dorogi.html).

Для каждой группы строится план: сетка, пруд (клякса), рёбра (жирные/пунктир),
4 метки-пина с номерами. Координаты — в клетках, ось y вверх.
DOROGI_SVG[gid] = строка <svg> для вставки в context_html вместо <img>.
"""

import math

CELL = 22
PAD = 2
POND_W = 4
POND_H = 3
POND_OFFSET = 3.5

# Каждая группа: points = [(x,y)×4]; edges = [(i,j,dashed)];
# pond = {"edge": (i,j), "side": ..., "size": ?, "offset": (dx,dy)?} | None
GROUPS = {
    "34E199": {
        "points": [(30, 2), (22, 2), (2, 2), (2, 23)],
        "edges": [(0, 1, 0), (1, 2, 0), (2, 3, 0), (3, 0, 1), (3, 1, 1)],
        "pond": {"edge": (3, 1), "side": "left"},
    },
    "35C016": {
        "points": [(2, 17), (10, 17), (2, 11), (2, 2)],
        "edges": [(0, 1, 0), (2, 3, 0), (3, 0, 0), (1, 2, 1), (1, 3, 1)],
        "pond": {"edge": (1, 2), "side": "top", "size": 0.7, "offset": (-2, -3)},
    },
    "650747": {
        "points": [(1, 2), (1, 8), (1, 23), (21, 23)],
        "edges": [(0, 1, 0), (1, 2, 0), (2, 3, 0), (3, 0, 1), (3, 1, 1)],
        "pond": {"edge": (3, 1), "side": "top", "offset": (0, -1.5)},
    },
    "79233F": {
        "points": [(10, 2), (16, 10), (16, 2), (1, 2)],
        "edges": [(1, 2, 0), (2, 3, 0), (3, 0, 0), (0, 1, 1), (3, 1, 1)],
        "pond": {"edge": (1, 0), "side": "right", "size": 0.7, "offset": (-2, 0)},
    },
    "8C173F": {
        "points": [(7, 10), (1, 2), (1, 10), (16, 10)],
        "edges": [(1, 2, 0), (2, 3, 0), (3, 0, 0), (0, 1, 1), (3, 1, 1)],
        "pond": {"edge": (1, 0), "side": "left", "size": 0.7, "offset": (2.5, 1.5)},
    },
    "BA66FC": {
        "points": [(2, 19), (2, 11), (17, 19), (2, -1)],
        "edges": [(0, 1, 0), (3, 0, 0), (2, 0, 0), (1, 2, 1), (2, 3, 1)],
        "pond": {"edge": (2, 1), "side": "top", "offset": (-2, -2)},
    },
    "C09A0A": {
        "points": [(2, 11), (2, 6), (2, 2), (14, 11)],
        "edges": [(0, 1, 0), (1, 2, 0), (3, 0, 0), (3, 1, 1), (2, 3, 1)],
        "pond": {"edge": (3, 1), "side": "top", "size": 0.7, "offset": (-3, -3)},
    },
    "E4DF9C": {
        "points": [(1, 18), (13, 18), (1, 13), (1, 2)],
        "edges": [(0, 1, 0), (2, 3, 0), (3, 0, 0), (1, 2, 1), (1, 3, 1)],
        "pond": {"edge": (2, 1), "side": "top", "size": 0.7, "offset": (-3, -3)},
    },
    "EAE764": {
        "points": [(11, 2), (2, 14), (6, 14), (11, 14)],
        "edges": [(1, 2, 0), (2, 3, 0), (3, 0, 0), (0, 1, 1), (0, 2, 1)],
        "pond": {"edge": (2, 0), "side": "right", "size": 0.7, "offset": (-4, 4)},
    },
    "F6B6DD": {
        "points": [(2, 2), (13, 2), (18, 2), (18, 14)],
        "edges": [(0, 1, 0), (1, 2, 0), (3, 0, 0), (3, 1, 1), (2, 3, 1)],
        "pond": {"edge": (3, 1), "side": "left", "offset": (0, -2)},
    },
}

# Масштаб: сколько километров в одной клетке (для масштабной линейки на рисунке)
CELL_KM = {
    "34E199": 1, "35C016": 4, "650747": 1, "79233F": 1, "8C173F": 2,
    "BA66FC": 1, "C09A0A": 2, "E4DF9C": 1, "EAE764": 3, "F6B6DD": 2,
}


def _f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _pond_center(p1, p2, side):
    cx = (p1[0] + p2[0]) / 2
    cy = (p1[1] + p2[1]) / 2
    dx = dy = 0.0
    if side == "left":
        dx = -POND_OFFSET
    elif side == "right":
        dx = POND_OFFSET
    elif side == "top":
        dy = POND_OFFSET
    elif side == "bottom":
        dy = -POND_OFFSET
    return [cx + dx, cy + dy]


def _pin(cx, cy_tip, n, scale=0.38):
    return (
        f'<g transform="translate({_f(cx)} {_f(cy_tip)}) scale({scale}) translate(-40 -82)">'
        '<path d="M 40,10 C 22,10 14,26 18,42 C 22,55 32,68 40,82 '
        'C 48,68 58,55 62,42 C 66,26 58,10 40,10 Z" '
        'fill="#fff" stroke="#000" stroke-width="3" stroke-linejoin="round"/>'
        '<text x="40" y="50" text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif" font-size="26" '
        f'font-weight="700" fill="#000">{n}</text></g>'
    )


def _pond(cx, cy, size_mul=1):
    w = POND_W * CELL * size_mul
    h = POND_H * CELL * size_mul
    return (
        f'<g transform="translate({_f(cx - w / 2)} {_f(cy - h / 2)}) '
        f'scale({_f(w / 140)} {_f(h / 100)})">'
        '<path d="M 30,40 C 20,30 25,15 45,18 C 60,20 70,12 90,18 '
        'C 110,24 122,40 118,58 C 114,75 95,82 75,80 C 55,78 35,80 25,68 '
        'C 15,55 22,48 30,40 Z" fill="#c4e0f5" stroke="#3b82a6" '
        'stroke-width="1.8" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></g>'
    )


def _build(group, cell_km=1):
    points = group["points"]
    edges = group["edges"]
    pond = group.get("pond")

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    pond_center = None
    pond_size = 1
    if pond:
        i, j = pond["edge"]
        pond_center = _pond_center(points[i], points[j], pond["side"])
        off = pond.get("offset")
        if off:
            pond_center[0] += off[0]
            pond_center[1] += off[1]
        pond_size = pond.get("size", 1)
        half_w = (POND_W * pond_size) / 2
        half_h = (POND_H * pond_size) / 2
        xs += [pond_center[0] - half_w, pond_center[0] + half_w]
        ys += [pond_center[1] - half_h, pond_center[1] + half_h]

    x_min = min(xs) - PAD
    x_max = max(xs) + PAD
    y_min = min(ys) - 2          # снизу всегда 2 ряда клеток
    y_max = max(ys) + PAD

    W = (x_max - x_min) * CELL
    H = (y_max - y_min) * CELL

    def px(x):
        return (x - x_min) * CELL

    def py(y):
        return (y_max - y) * CELL

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_f(W)} {_f(H)}" '
        f'style="max-width:520px;height:auto;display:block;margin:0.8em 0;background:#fff;">'
    ]

    # сетка
    x = x_min
    while x <= x_max + 1e-9:
        p.append(f'<line x1="{_f(px(x))}" y1="{_f(py(y_min))}" x2="{_f(px(x))}" '
                 f'y2="{_f(py(y_max))}" stroke="#d0d0d0" stroke-width="0.6"/>')
        x += 1
    y = y_min
    while y <= y_max + 1e-9:
        p.append(f'<line x1="{_f(px(x_min))}" y1="{_f(py(y))}" x2="{_f(px(x_max))}" '
                 f'y2="{_f(py(y))}" stroke="#d0d0d0" stroke-width="0.6"/>')
        y += 1

    # пруд — под рёбрами и метками
    if pond_center:
        p.append(_pond(px(pond_center[0]), py(pond_center[1]), pond_size))

    # рёбра
    for i, j, dashed in edges:
        p1, p2 = points[i], points[j]
        if dashed:
            p.append(f'<line x1="{_f(px(p1[0]))}" y1="{_f(py(p1[1]))}" '
                     f'x2="{_f(px(p2[0]))}" y2="{_f(py(p2[1]))}" stroke="#000" '
                     f'stroke-width="1.5" stroke-dasharray="5,3"/>')
        else:
            p.append(f'<line x1="{_f(px(p1[0]))}" y1="{_f(py(p1[1]))}" '
                     f'x2="{_f(px(p2[0]))}" y2="{_f(py(p2[1]))}" stroke="#000" '
                     f'stroke-width="2.8"/>')

    # метки-пины
    for idx, pt in enumerate(points):
        p.append(_pin(px(pt[0]), py(pt[1]), idx + 1))

    # масштабная линейка — одна клетка в левом-нижнем поле + подпись «N км»
    sx1, sx2 = x_min + 1, x_min + 2          # ровно одна клетка, по линиям сетки
    sy = y_min + 1
    tick = 0.28
    p.append(f'<line x1="{_f(px(sx1))}" y1="{_f(py(sy))}" x2="{_f(px(sx2))}" '
             f'y2="{_f(py(sy))}" stroke="#000" stroke-width="2.5"/>')
    p.append(f'<line x1="{_f(px(sx1))}" y1="{_f(py(sy))}" x2="{_f(px(sx1))}" '
             f'y2="{_f(py(sy + tick))}" stroke="#000" stroke-width="2.5"/>')
    p.append(f'<line x1="{_f(px(sx2))}" y1="{_f(py(sy))}" x2="{_f(px(sx2))}" '
             f'y2="{_f(py(sy + tick))}" stroke="#000" stroke-width="2.5"/>')
    km = str(cell_km).replace(".", ",")
    p.append(f'<text x="{_f(px((sx1 + sx2) / 2))}" y="{_f(py(sy) + 16)}" '
             f'text-anchor="middle" font-family="Cambria, Georgia, serif" '
             f'font-size="14" fill="#000">{km} км</text>')

    p.append("</svg>")
    return "".join(p)


DOROGI_SVG = {gid: _build(g, CELL_KM.get(gid, 1)) for gid, g in GROUPS.items()}
