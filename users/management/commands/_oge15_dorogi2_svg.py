# -*- coding: utf-8 -*-
"""SVG-план «сложных дорог» (группа B64540, Антоновка → Богданово).

Порт из _preview_dorogi2.html + мост варианта Д (двойные перила-скобки вдоль шоссе).
Элементы: Г-образное шоссе (серая полоса, вариант В), просёлочные дороги (пунктир,
вариант Г), извилистая река (вариант Б), мосты в местах пересечения реки с дорогами,
конюшня, пруд, 7 каплевидных меток с номерами.

Деревни: 1=Антоновка, 2=Егорка, 3=Доломино, 4=Ванютино,
         5=Жилино, 6=Горюново, 7=Богданово.
"""

import math

CELL = 28
OFFSET = 12

# Точки (y растёт ВВЕРХ)
P = {
    7: (2, 4), 6: (2, 6), 5: (2, 10), 4: (2, 14),
    3: (8, 14), 2: (14, 14), 1: (17, 14),
}
# Г-образное шоссе (две ветки, продлены за крайние пункты)
HIGHWAYS = [
    (2, 1, 2, 18),     # вертикальная (7-6-5-4)
    (-2, 14, 22, 14),  # горизонтальная (4-3-2-1)
]
COUNTRY = [(2, 5), (3, 6), (1, 6), (1, 7)]   # просёлочные дороги (пунктир)
RIVER = [
    (0, 1), (2, 2), (5, 3.4), (8, 5), (11, 7),
    (14, 9.4), (17, 11.8), (20, 14), (22, 15.8),
]
STABLE = (4.5, 12)
POND = (7, 10)

PAD_L, PAD_R, PAD_T, PAD_B = 0.3, 1.5, 0.3, 1.5

_allX = ([p[0] for p in P.values()] + [r[0] for r in RIVER] +
         [STABLE[0], POND[0]] + [h[0] for h in HIGHWAYS] + [h[2] for h in HIGHWAYS])
_allY = ([p[1] for p in P.values()] + [r[1] for r in RIVER] +
         [STABLE[1], POND[1]] + [h[1] for h in HIGHWAYS] + [h[3] for h in HIGHWAYS])
X_MIN = min(_allX) - PAD_L
X_MAX = max(_allX) + PAD_R
Y_MIN = min(_allY) - PAD_B
Y_MAX = max(_allY) + PAD_T
W = (X_MAX - X_MIN) * CELL
H = (Y_MAX - Y_MIN) * CELL


def _f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _px(x):
    return OFFSET + (x - X_MIN) * CELL


def _py(y):
    return OFFSET + (Y_MAX - y) * CELL


def _line(x1, y1, x2, y2, stroke, sw, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')


def _smooth_river(pts_cell):
    pts = [(_px(p[0]), _py(p[1])) for p in pts_cell]
    n = len(pts)
    d = f"M {_f(pts[0][0])},{_f(pts[0][1])}"
    sampled = [pts[0]]
    for i in range(n - 1):
        p0 = pts[i - 1] if i - 1 >= 0 else pts[i]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[i + 1]
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        d += f" C {_f(c1x)},{_f(c1y)} {_f(c2x)},{_f(c2y)} {_f(p2[0])},{_f(p2[1])}"
        steps = 12
        for s in range(1, steps + 1):
            t = s / steps
            mt = 1 - t
            x = (mt**3 * p1[0] + 3 * mt**2 * t * c1x +
                 3 * mt * t**2 * c2x + t**3 * p2[0])
            y = (mt**3 * p1[1] + 3 * mt**2 * t * c1y +
                 3 * mt * t**2 * c2y + t**3 * p2[1])
            sampled.append((x, y))
    return d, sampled


def _highway(x1, y1, x2, y2):
    ax, ay, bx, by = _px(x1), _py(y1), _px(x2), _py(y2)
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    half = 7
    return (
        _line(ax, ay, bx, by, "#888", half * 2) +
        _line(ax + nx * half, ay + ny * half, bx + nx * half, by + ny * half, "#000", "1") +
        _line(ax - nx * half, ay - ny * half, bx - nx * half, by - ny * half, "#000", "1") +
        _line(ax, ay, bx, by, "#fff", "1.4", dash="8,5")
    )


def _seg_int(p1, p2, p3, p4):
    d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
    if abs(d) < 1e-9:
        return None
    t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
    u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
    if t < 0 or t > 1 or u < 0 or u > 1:
        return None
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


def _bridge(cx, cy, ux, uy):
    """Мост Д: двойные перила-скобки вдоль дороги по обеим сторонам + засечки."""
    nx, ny = -uy, ux
    half = 7           # полуширина шоссе
    L = 13             # длина моста вдоль дороги (в каждую сторону)
    r_in, r_out = half + 3, half + 6
    out = []
    for s in (1, -1):
        for r, sw in ((r_in, "1.4"), (r_out, "1.6")):
            ox, oy = nx * s * r, ny * s * r
            out.append(_line(cx + ox - ux * L, cy + oy - uy * L,
                             cx + ox + ux * L, cy + oy + uy * L, "#000", sw))
        for e in (1, -1):
            ex, ey = cx + ux * L * e, cy + uy * L * e
            out.append(_line(ex + nx * s * half, ey + ny * s * half,
                             ex + nx * s * r_out, ey + ny * s * r_out, "#000", "1.6"))
    return "".join(out)


def _pin(cx, cy_tip, n, scale=0.42):
    return (
        f'<g transform="translate({_f(cx)} {_f(cy_tip)}) scale({scale}) translate(-40 -82)">'
        '<path d="M 40,10 C 22,10 14,26 18,42 C 22,55 32,68 40,82 '
        'C 48,68 58,55 62,42 C 66,26 58,10 40,10 Z" '
        'fill="#fff" stroke="#000" stroke-width="3" stroke-linejoin="round"/>'
        '<text x="40" y="50" text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif" font-size="26" '
        f'font-weight="700" fill="#000">{n}</text></g>'
    )


def _build():
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_f(W + 2 * OFFSET)} {_f(H + 2 * OFFSET)}" '
        f'style="max-width:560px;height:auto;display:block;margin:0.8em auto;background:#fff;">'
    ]

    # река — первой, под шоссе
    river_d, sampled = _smooth_river(RIVER)
    p.append(f'<path d="{river_d}" fill="none" stroke="#000" stroke-width="4" '
             f'stroke-linecap="round" stroke-linejoin="round"/>')

    # шоссе (вариант В)
    for h in HIGHWAYS:
        p.append(_highway(*h))

    # просёлочные дороги (вариант Г)
    for a, b in COUNTRY:
        p.append(_line(_px(P[a][0]), _py(P[a][1]), _px(P[b][0]), _py(P[b][1]),
                       "#000", "2", dash="3,2"))

    # мосты (вариант Д) в местах пересечения реки с дорогами
    roads_px = (
        [((_px(h[0]), _py(h[1])), (_px(h[2]), _py(h[3]))) for h in HIGHWAYS] +
        [((_px(P[a][0]), _py(P[a][1])), (_px(P[b][0]), _py(P[b][1]))) for a, b in COUNTRY]
    )
    for a, b in roads_px:
        for i in range(len(sampled) - 1):
            ip = _seg_int(a, b, sampled[i], sampled[i + 1])
            if ip:
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy)
                p.append(_bridge(ip[0], ip[1], dx / L, dy / L))
                break

    # конюшня
    scx, scy, sw_, sh_ = _px(STABLE[0]), _py(STABLE[1]), 64, 36
    p.append(f'<rect x="{_f(scx - sw_ / 2)}" y="{_f(scy - sh_ / 2)}" width="{sw_}" '
             f'height="{sh_}" fill="#fff" stroke="#000" stroke-width="2.2"/>')
    p.append(f'<text x="{_f(scx)}" y="{_f(scy + 4)}" text-anchor="middle" '
             f'font-family="Cambria, Georgia, serif" font-style="italic" '
             f'font-size="11" fill="#000">конюшня</text>')

    # пруд
    pcx, pcy, pw, ph = _px(POND[0]), _py(POND[1]), 3 * CELL, 2 * CELL
    p.append(f'<g transform="translate({_f(pcx - pw / 2)} {_f(pcy - ph / 2)}) '
             f'scale({_f(pw / 140)} {_f(ph / 100)})">'
             '<path d="M 30,40 C 20,30 25,15 45,18 C 60,20 70,12 90,18 '
             'C 110,24 122,40 118,58 C 114,75 95,82 75,80 C 55,78 35,80 25,68 '
             'C 15,55 22,48 30,40 Z" fill="#c4e0f5" stroke="#3b82a6" '
             'stroke-width="1.8" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></g>')

    # метки
    for num, pt in P.items():
        p.append(_pin(_px(pt[0]), _py(pt[1]), num))

    p.append("</svg>")
    return "".join(p)


DOROGI2_SVG = _build()
