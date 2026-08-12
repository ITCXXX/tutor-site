# -*- coding: utf-8 -*-
"""SVG-рисунок форматов бумаги A0–A5 для группы B9A7F7.

Спираль (как в превью, вариант В): A0 делится пополам, половина = А1,
оставшаяся половина снова делится (А2) и т.д. до А5. Подпись «А0» —
заголовком над прямоугольником (вариант 4). Пропорции листа — ровно 1:√2.
"""

import math

H = 240.0
W = H * math.sqrt(2)     # отношение сторон A-серии = √2
PAD = 16
TH = 30                  # место сверху под заголовок «А0»


def _f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _build_bumaga_svg():
    p = []
    vbw = W + 2 * PAD
    vbh = H + 2 * PAD + TH
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_f(vbw)} {_f(vbh)}" '
        'style="max-width:360px;height:auto;display:block;margin:0.8em auto;">'
    )

    oy = PAD + TH
    # внешний прямоугольник A0
    p.append(f'<rect x="{PAD}" y="{_f(oy)}" width="{_f(W)}" height="{_f(H)}" '
             'fill="none" stroke="#000" stroke-width="2.5"/>')

    # спираль: вертик. деление → метка справа; гориз. → метка снизу
    x, y, w, h = float(PAD), float(oy), W, H
    for n in range(1, 6):
        if w >= h:
            lw = w / 2
            p.append(f'<line x1="{_f(x+lw)}" y1="{_f(y)}" x2="{_f(x+lw)}" y2="{_f(y+h)}" '
                     'stroke="#000" stroke-width="1.4"/>')
            lab = (x + lw, y, lw, h); rem = (x, y, lw, h)        # метка справа
        else:
            hh = h / 2
            p.append(f'<line x1="{_f(x)}" y1="{_f(y+hh)}" x2="{_f(x+w)}" y2="{_f(y+hh)}" '
                     'stroke="#000" stroke-width="1.4"/>')
            lab = (x, y + hh, w, hh); rem = (x, y, w, hh)        # метка снизу
        rx, ry, rw, rh = lab
        fs = max(8, min(rw, rh) * 0.42)
        p.append(f'<text x="{_f(rx+rw/2)}" y="{_f(ry+rh/2+fs*0.35)}" text-anchor="middle" '
                 f'font-family="Arial, Helvetica, sans-serif" font-size="{_f(fs)}" '
                 f'font-weight="700" fill="#000">А{n}</text>')
        x, y, w, h = rem

    # подпись А0 — заголовком над прямоугольником
    p.append(f'<text x="{_f(PAD+W/2)}" y="{_f(PAD+22)}" text-anchor="middle" '
             'font-family="Arial, Helvetica, sans-serif" font-size="24" '
             'font-weight="700" fill="#000">А0</text>')

    p.append('</svg>')
    return "".join(p)


BUMAGA_SVG = _build_bumaga_svg()
