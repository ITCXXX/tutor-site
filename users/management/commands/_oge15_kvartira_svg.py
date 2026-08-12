# -*- coding: utf-8 -*-
"""SVG-план двухкомнатной квартиры для группы eF7420.

Сторона клетки = 0,4 м. Порт из _preview_kvartira.html:
  * стены — непрерывные ломаные с ровными (miter) углами, разрыв только
    в дверных проёмах (на отрезке двери стены нет, видна сетка);
  * окна — двойная линия; два полностенных окна (верх комнат 8 и 5) с
    отступом концов 1,5px, чтобы не заходить за вертикальные стены;
  * двери — реальный проём + полотно + дуга открывания (входная — внутрь);
  * номера комнат — в кружках (как на плане участка);
  * легенда справа — окно, дверь, масштаб «0,4 м».

Объекты: 1=санузел, 2=коридор, 3=кладовая, 4=спальня,
         5=лоджия(спальня), 6=гостиная, 7=кухня, 8=лоджия(кухня).
"""

import math

CELL = 18
OFFSET = 12
INSET = 1.5   # отступ концов полностенных окон (комнаты 8 и 5)

ROOMS = {
    1: [[1, 1], [1, 7], [6, 7], [6, 1]],
    2: [[6, 1], [6, 7], [11, 7], [11, 6], [30, 6], [30, 1]],
    3: [[30, 1], [30, 6], [34, 6], [34, 1]],
    4: [[23, 6], [23, 15], [34, 15], [34, 6]],
    5: [[23, 15], [23, 19], [34, 19], [34, 15]],
    6: [[11, 6], [11, 19], [23, 19], [23, 6]],
    7: [[1, 7], [1, 16], [11, 16], [11, 7]],
    8: [[1, 16], [1, 19], [11, 19], [11, 16]],
}
ROOM_LABEL = {
    1: [3.5, 4], 2: [20, 3.5], 3: [32, 3.5], 4: [28.5, 10.5],
    5: [28.5, 17], 6: [17, 12.5], 7: [6, 11.5], 8: [6, 17.5],
}
WINDOWS = [
    [[1, 19], [11, 19]], [[3, 16], [6, 16]], [[14, 19], [20, 19]],
    [[23, 19], [34, 19]], [[29, 15], [32, 15]],
]
DOORS = [
    [[25, 15], [27, 15]], [[25, 6], [27, 6]], [[30, 4], [30, 2]],
    [[7, 16], [9, 16]], [[11, 13], [11, 11]], [[7, 7], [9, 7]],
    [[6, 5], [6, 3]], [[13, 6], [15, 6]], [[10, 1], [12, 1]],
]
SPECIAL = {"1,19|11,19", "23,19|34,19"}   # верхние окна комнат 8 и 5


def _key(a, b):
    return f"{a[0]},{a[1]}|{b[0]},{b[1]}"


_xs = [p[0] for r in ROOMS for p in ROOMS[r]]
_ys = [p[1] for r in ROOMS for p in ROOMS[r]]
ORIG_MAX_X = max(_xs)
X_MIN = min(_xs) - 1
X_MAX = ORIG_MAX_X + 11          # место справа под легенду
Y_MIN = min(_ys) - 1
Y_MAX = max(_ys) + 1
W = (X_MAX - X_MIN) * CELL
H = (Y_MAX - Y_MIN) * CELL


def _f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _px(x):
    return OFFSET + (x - X_MIN) * CELL


def _py(y):
    return OFFSET + (Y_MAX - y) * CELL


def _line(x1, y1, x2, y2, stroke, sw, **extra):
    a = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in extra.items())
    return (f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" '
            f'stroke="{stroke}" stroke-width="{sw}"{a}/>')


def _door_gaps(P, Q):
    gaps = []
    for d0, d1 in DOORS:
        if P[1] == Q[1] and d0[1] == P[1] and d1[1] == P[1]:
            a, b = min(P[0], Q[0]), max(P[0], Q[0])
            g0 = max(a, min(d0[0], d1[0]))
            g1 = min(b, max(d0[0], d1[0]))
            if g1 > g0:
                L = Q[0] - P[0]
                t0, t1 = (g0 - P[0]) / L, (g1 - P[0]) / L
                if t0 > t1:
                    t0, t1 = t1, t0
                gaps.append((t0, t1))
        elif P[0] == Q[0] and d0[0] == P[0] and d1[0] == P[0]:
            a, b = min(P[1], Q[1]), max(P[1], Q[1])
            g0 = max(a, min(d0[1], d1[1]))
            g1 = min(b, max(d0[1], d1[1]))
            if g1 > g0:
                L = Q[1] - P[1]
                t0, t1 = (g0 - P[1]) / L, (g1 - P[1]) / L
                if t0 > t1:
                    t0, t1 = t1, t0
                gaps.append((t0, t1))
    gaps.sort(key=lambda u: u[0])
    return gaps


def _lp(P, Q, t):
    return (_px(P[0] + (Q[0] - P[0]) * t), _py(P[1] + (Q[1] - P[1]) * t))


def _wall_runs(v):
    segs = []
    n = len(v)
    for i in range(n):
        P, Q = v[i], v[(i + 1) % n]
        gaps = _door_gaps(P, Q)
        cuts = [0.0]
        for a, b in gaps:
            cuts += [a, b]
        cuts.append(1.0)
        for k in range(len(cuts) - 1):
            ta, tb = cuts[k], cuts[k + 1]
            if tb - ta < 1e-9:
                continue
            mid = (ta + tb) / 2
            in_gap = any(mid > a + 1e-9 and mid < b - 1e-9 for a, b in gaps)
            segs.append((_lp(P, Q, ta), _lp(P, Q, tb), not in_gap))
    m = len(segs)
    if all(s[2] for s in segs):
        pts = [s[0] for s in segs]
        pts.append(segs[0][0])
        return [pts]
    start = next(i for i, s in enumerate(segs) if not s[2])
    runs, cur = [], None
    for k in range(m):
        s = segs[(start + k) % m]
        if s[2]:
            if cur is None:
                cur = [s[0], s[1]]
            else:
                cur.append(s[1])
        else:
            if cur:
                runs.append(cur)
                cur = None
    if cur:
        runs.append(cur)
    return runs


def _win(a, b, inset):
    ax, ay, bx, by = _px(a[0]), _py(a[1]), _px(b[0]), _py(b[1])
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    ax += ux * inset; ay += uy * inset
    bx -= ux * inset; by -= uy * inset
    return (
        _line(ax, ay, bx, by, "#fff", "4.5") +
        _line(ax + nx * 1.8, ay + ny * 1.8, bx + nx * 1.8, by + ny * 1.8, "#000", "1") +
        _line(ax - nx * 1.8, ay - ny * 1.8, bx - nx * 1.8, by - ny * 1.8, "#000", "1")
    )


def _door(a, b, flip):
    ax, ay, bx, by = _px(a[0]), _py(a[1]), _px(b[0]), _py(b[1])
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    if flip:
        nx, ny = -nx, -ny
    sweep = 0 if flip else 1
    ex, ey = ax + nx * L, ay + ny * L
    return (
        _line(ax, ay, ex, ey, "#000", "1.4") +
        f'<path d="M {_f(bx)},{_f(by)} A {_f(L)},{_f(L)} 0 0 {sweep} {_f(ex)},{_f(ey)}" '
        f'fill="none" stroke="#000" stroke-width="0.8"/>'
    )


def _build():
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_f(W + 2 * OFFSET)} {_f(H + 2 * OFFSET)}" '
        f'style="max-width:680px;height:auto;display:block;margin:0.8em auto;">'
    ]
    # сетка
    import math as _m
    for x in range(_m.ceil(X_MIN), _m.floor(X_MAX) + 1):
        p.append(_line(_px(x), _py(Y_MIN), _px(x), _py(Y_MAX), "#d0d0d0", "0.7"))
    for y in range(_m.ceil(Y_MIN), _m.floor(Y_MAX) + 1):
        p.append(_line(_px(X_MIN), _py(y), _px(X_MAX), _py(y), "#d0d0d0", "0.7"))
    # стены
    for r in ROOMS:
        for run in _wall_runs(ROOMS[r]):
            d = " ".join(f'{"M" if i == 0 else "L"} {_f(pt[0])},{_f(pt[1])}'
                         for i, pt in enumerate(run))
            p.append(f'<path d="{d}" fill="none" stroke="#000" stroke-width="3" '
                     f'stroke-linejoin="miter"/>')
    # номера комнат в кружках
    for r, (x, y) in ROOM_LABEL.items():
        p.append(f'<circle cx="{_f(_px(x))}" cy="{_f(_py(y))}" r="9" fill="#fff" '
                 f'stroke="#000" stroke-width="1.5"/>')
        p.append(f'<text x="{_f(_px(x))}" y="{_f(_py(y) + 4.5)}" text-anchor="middle" '
                 f'font-family="Arial" font-size="13" font-weight="700" fill="#000">{r}</text>')
    # окна
    for a, b in WINDOWS:
        p.append(_win(a, b, INSET if _key(a, b) in SPECIAL else 0))
    # двери
    for a, b in DOORS:
        is_ent = (a[0] == 10 and a[1] == 1 and b[0] == 12 and b[1] == 1)
        p.append(_door(a, b, is_ent))
    # ---- легенда справа ----
    lx = ORIG_MAX_X + 2
    lbl = ORIG_MAX_X + 4.2

    def label(xc, yc, text):
        return (f'<text x="{_f(_px(xc))}" y="{_f(_py(yc) + 5)}" text-anchor="start" '
                f'font-family="Cambria, Georgia, serif" font-size="15" fill="#000">{text}</text>')

    p.append(_win([lx, 16], [lx + 1.6, 16], 0))
    p.append(label(lbl, 16, "окно"))
    p.append(_door([lx, 12], [lx + 1.4, 12], False))
    p.append(label(lbl, 12, "дверь"))
    y0, x1, x2, tick, sw = 8, lx, lx + 1, 1 / 3, "2.5"
    p.append(_line(_px(x1), _py(y0), _px(x2), _py(y0), "#000", sw))
    p.append(_line(_px(x1), _py(y0), _px(x1), _py(y0 + tick), "#000", sw))
    p.append(_line(_px(x2), _py(y0), _px(x2), _py(y0 + tick), "#000", sw))
    p.append(f'<text x="{_f(_px((x1 + x2) / 2))}" y="{_f(_py(y0) + 16)}" text-anchor="middle" '
             f'font-family="Cambria, Georgia, serif" font-size="14" fill="#000">0,4 м</text>')

    p.append("</svg>")
    return "".join(p)


KVARTIRA_SVG = _build()
