# -*- coding: utf-8 -*-
"""SVG-планы участков для групп ОГЭ №1-5 «План домохозяйства».

Экспортирует:
  AVDEEVO_SVG  — план с. Авдеево (272C13)
  PRIBOR_SVG   — план СНТ «Прибор» (856918)

Координаты в клетках, y растёт ВВЕРХ (математическая система).
Клетка = 30 пикс, поле 25 × 13 клеток (770 × 410 пикс с отступами).
"""

CELL = 30
OFFSET = 10
COLS = 25
ROWS = 13


def _px(c):
    return OFFSET + c * CELL


def _py(c):
    return OFFSET + (ROWS - c) * CELL


def _fmt(x):
    """Форматирует число: целое без точки, иначе округление до 2 знаков."""
    if isinstance(x, int):
        return str(x)
    if x == int(x):
        return str(int(x))
    return f"{x:.2f}".rstrip("0").rstrip(".")


# ============================================================
#   Базовые элементы
# ============================================================

def _grid():
    parts = []
    for i in range(COLS + 1):
        parts.append(
            f'<line x1="{_px(i)}" y1="{_py(0)}" x2="{_px(i)}" y2="{_py(ROWS)}" '
            f'stroke="#d0d0d0" stroke-width="0.7"/>'
        )
    for i in range(ROWS + 1):
        parts.append(
            f'<line x1="{_px(0)}" y1="{_py(i)}" x2="{_px(COLS)}" y2="{_py(i)}" '
            f'stroke="#d0d0d0" stroke-width="0.7"/>'
        )
    return "".join(parts)


def _L(x1, y1, x2, y2, w=3):
    return (
        f'<line x1="{_fmt(_px(x1))}" y1="{_fmt(_py(y1))}" '
        f'x2="{_fmt(_px(x2))}" y2="{_fmt(_py(y2))}" '
        f'stroke="#000" stroke-width="{w}"/>'
    )


def _path_d(vertices):
    return " ".join(
        f"{'M' if i == 0 else 'L'} {_fmt(_px(v[0]))},{_fmt(_py(v[1]))}"
        for i, v in enumerate(vertices)
    ) + " Z"


def _building(vertices):
    return (
        f'<path d="{_path_d(vertices)}" fill="#888" stroke="#000" '
        f'stroke-width="2.5" stroke-linejoin="miter"/>'
    )


def _dashed(vertices):
    return (
        f'<path d="{_path_d(vertices)}" fill="none" stroke="#000" '
        f'stroke-width="1.2" stroke-dasharray="4,3"/>'
    )


def _num_circle(x, y, n):
    cx, cy = _px(x), _py(y)
    return (
        f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="9" fill="#fff" '
        f'stroke="#000" stroke-width="1.5"/>'
        f'<text x="{_fmt(cx)}" y="{_fmt(cy + 4.5)}" text-anchor="middle" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="13" font-weight="700" fill="#000">{n}</text>'
    )


# ============================================================
#   Плитка
# ============================================================

# Плитка через SVG-паттерн: одна плитка-шаблон тайлится по области.
# Фазы x/y подобраны так, чтобы тайлы ложились на сетку клеток:
#   _px(x)=10+30x → полуклетки кратны 15 со сдвигом 10; четвертьклетки — 7.5 со сдвигом 2.5.
_TILE_DEFS = (
    '<defs>'
    '<pattern id="ptbig" patternUnits="userSpaceOnUse" x="10" y="10" width="15" height="15">'
    '<rect x="1" y="1" width="13" height="13" fill="#6b6b6b"/></pattern>'
    '<pattern id="ptsmall" patternUnits="userSpaceOnUse" x="2.5" y="2.5" width="7.5" height="7.5">'
    '<rect x="0.5" y="0.5" width="6.5" height="6.5" fill="#6b6b6b"/></pattern>'
    '</defs>'
)


def _tiles_big(x1, x2, y1, y2):
    """Крупная плитка 0.5×0.5 клетки (Авдеево/Сосновка) — заливка паттерном."""
    left = _px(x1); top = _py(y2)
    w = (x2 - x1) * CELL; h = (y2 - y1) * CELL
    return (f'<rect x="{_fmt(left)}" y="{_fmt(top)}" '
            f'width="{_fmt(w)}" height="{_fmt(h)}" fill="url(#ptbig)"/>')


def _tiles_small(vertices):
    """Мелкая плитка 1/4 клетки в полигоне (Прибор) — заливка паттерном."""
    return f'<path d="{_path_d(vertices)}" fill="url(#ptsmall)"/>'


# ============================================================
#   Значки (вариант В для морковки/яблони, А для ёлки/цветка)
# ============================================================

def _carrot(cx_px, cy_px, s=0.5):
    top = cy_px - 18 * s
    bot = cy_px + 22 * s
    dx = 8 * s
    return (
        f'<path d="M {_fmt(cx_px)},{_fmt(top)} '
        f'C {_fmt(cx_px-dx)},{_fmt(top)} {_fmt(cx_px-dx)},{_fmt(top+15*s)} '
        f'{_fmt(cx_px-dx*0.75)},{_fmt(cy_px+8*s)} '
        f'C {_fmt(cx_px-dx*0.5)},{_fmt(bot)} {_fmt(cx_px+dx*0.5)},{_fmt(bot)} '
        f'{_fmt(cx_px+dx*0.75)},{_fmt(cy_px+8*s)} '
        f'C {_fmt(cx_px+dx)},{_fmt(top+15*s)} {_fmt(cx_px+dx)},{_fmt(top)} '
        f'{_fmt(cx_px)},{_fmt(top)} Z" fill="#000"/>'
        f'<path d="M {_fmt(cx_px)},{_fmt(top)} L {_fmt(cx_px-4*s)},{_fmt(top-14*s)} '
        f'M {_fmt(cx_px)},{_fmt(top)} L {_fmt(cx_px+2*s)},{_fmt(top-20*s)} '
        f'M {_fmt(cx_px)},{_fmt(top)} L {_fmt(cx_px+6*s)},{_fmt(top-12*s)}" '
        f'stroke="#000" stroke-width="{_fmt(2*s)}" stroke-linecap="round"/>'
    )


def _apple_tree(cx_px, cy_base_px, s=0.5):
    crop_cy = cy_base_px - 38 * s
    return (
        f'<rect x="{_fmt(cx_px - 3*s)}" y="{_fmt(cy_base_px - 22*s)}" '
        f'width="{_fmt(6*s)}" height="{_fmt(22*s)}" fill="#000"/>'
        f'<path d="M {_fmt(cx_px)},{_fmt(crop_cy - 26*s)} '
        f'C {_fmt(cx_px-18*s)},{_fmt(crop_cy-20*s)} '
        f'{_fmt(cx_px-22*s)},{_fmt(crop_cy+2*s)} '
        f'{_fmt(cx_px-12*s)},{_fmt(crop_cy+12*s)} '
        f'C {_fmt(cx_px-5*s)},{_fmt(crop_cy+18*s)} '
        f'{_fmt(cx_px+5*s)},{_fmt(crop_cy+18*s)} '
        f'{_fmt(cx_px+12*s)},{_fmt(crop_cy+12*s)} '
        f'C {_fmt(cx_px+22*s)},{_fmt(crop_cy+2*s)} '
        f'{_fmt(cx_px+18*s)},{_fmt(crop_cy-20*s)} '
        f'{_fmt(cx_px)},{_fmt(crop_cy - 26*s)} Z" fill="#000"/>'
    )


def _fir_tree(cx_px, cy_base_px, s=0.4):
    crop_top = cy_base_px - 75 * s
    crop_bot = cy_base_px - 18 * s
    w_half = 22 * s
    return (
        f'<rect x="{_fmt(cx_px - 3*s)}" y="{_fmt(cy_base_px - 18*s)}" '
        f'width="{_fmt(6*s)}" height="{_fmt(18*s)}" fill="#000"/>'
        f'<path d="M {_fmt(cx_px)},{_fmt(crop_top)} '
        f'L {_fmt(cx_px - w_half)},{_fmt(crop_bot)} '
        f'L {_fmt(cx_px + w_half)},{_fmt(crop_bot)} Z" fill="#000"/>'
    )


def _flower(cx_px, cy_px, s=0.5):
    parts = [
        f'<rect x="{_fmt(cx_px - 1*s)}" y="{_fmt(cy_px + 5*s)}" '
        f'width="{_fmt(2*s)}" height="{_fmt(22*s)}" fill="#000"/>'
    ]
    for i in range(6):
        ang = i * 60
        parts.append(
            f'<ellipse cx="{_fmt(cx_px)}" cy="{_fmt(cy_px - 10*s)}" '
            f'rx="{_fmt(4*s)}" ry="{_fmt(8*s)}" fill="#000" '
            f'transform="rotate({ang} {_fmt(cx_px)} {_fmt(cy_px)})"/>'
        )
    parts.append(
        f'<circle cx="{_fmt(cx_px)}" cy="{_fmt(cy_px)}" r="{_fmt(4*s)}" '
        f'fill="#fff" stroke="#000" stroke-width="{_fmt(1.2*s)}"/>'
    )
    return "".join(parts)


# ============================================================
#   Легенда
# ============================================================

def _legend_label(x, y, text):
    return (
        f'<text x="{_fmt(_px(x))}" y="{_fmt(_py(y) + 5)}" text-anchor="start" '
        f'font-family="Cambria, Georgia, serif" '
        f'font-size="15" fill="#000">{text}</text>'
    )


def _scale_2m(y0=4, xL=19, xR=20, sw=3, tick=1/3):
    return (
        f'<line x1="{_fmt(_px(xL))}" y1="{_fmt(_py(y0))}" '
        f'x2="{_fmt(_px(xR))}" y2="{_fmt(_py(y0))}" '
        f'stroke="#000" stroke-width="{sw}" stroke-linecap="butt"/>'
        f'<line x1="{_fmt(_px(xL))}" y1="{_fmt(_py(y0))}" '
        f'x2="{_fmt(_px(xL))}" y2="{_fmt(_py(y0 + tick))}" '
        f'stroke="#000" stroke-width="{sw}" stroke-linecap="butt"/>'
        f'<line x1="{_fmt(_px(xR))}" y1="{_fmt(_py(y0))}" '
        f'x2="{_fmt(_px(xR))}" y2="{_fmt(_py(y0 + tick))}" '
        f'stroke="#000" stroke-width="{sw}" stroke-linecap="butt"/>'
        f'<text x="{_fmt(_px(19.5))}" y="{_fmt(_py(y0) + 17)}" text-anchor="middle" '
        f'font-family="Cambria, Georgia, serif" font-size="14" fill="#000">2 м</text>'
    )


# ============================================================
#   План АВДЕЕВО (272C13)
# ============================================================

def _build_avdeevo():
    parts = [_TILE_DEFS, _grid()]

    # Забор (1,2)→(16,2)→(16,12)→(1,12) с разрывом снизу на (8,2)-(10,2)
    parts.append(_L(1, 2, 8, 2))
    parts.append(_L(10, 2, 16, 2))
    parts.append(_L(16, 2, 16, 12))
    parts.append(_L(16, 12, 1, 12))
    parts.append(_L(1, 12, 1, 2))
    # Створки наружу (вниз)
    parts.append(_L(8, 2, 8.5, 1, 1.8))
    parts.append(_L(10, 2, 9.5, 1, 1.8))

    # Дом 1 (теплица)
    parts.append(_building([(2,10),(2,11),(5,11),(5,10)]))
    parts.append(_num_circle(3.5, 10.5, 1))

    # Огород 2
    parts.append(_dashed([(1,9),(1,12),(8,12),(8,9)]))
    parts.append(_carrot(_px(7.5), _py(9.5), 0.5))
    parts.append(_carrot(_px(6.5), _py(9.5), 0.5))
    parts.append(_num_circle(7, 11, 2))

    # Дом 3 (жилой, Г-образный)
    parts.append(_building([(9,7),(9,11),(14,11),(14,8),(11,8),(11,7)]))
    parts.append(_num_circle(11.5, 9.5, 3))

    # Сарай 4
    parts.append(_building([(2,5),(2,8),(4,8),(4,5)]))
    parts.append(_num_circle(3, 6.5, 4))

    # Яблони 5
    parts.append(_apple_tree(_px(12.5), _py(5.5), 0.5))
    parts.append(_apple_tree(_px(13.5), _py(5.5), 0.5))
    parts.append(_num_circle(11, 5.5, 5))

    # Баня 6
    parts.append(_building([(14,3),(14,7),(16,7),(16,3)]))
    parts.append(_num_circle(15, 5, 6))

    # Гараж 7
    parts.append(_building([(1,2),(1,4),(5,4),(5,2)]))
    parts.append(_num_circle(3, 3, 7))

    # Плитка-площадка (5,2)-(13,4)
    parts.append(_tiles_big(5, 13, 2, 4))
    # Дорожка 1
    parts.append(_tiles_big(9.5, 10, 4, 7))
    # Дорожка 2
    parts.append(_tiles_big(6, 6.5, 4, 9))
    # Дорожка 3
    parts.append(_tiles_big(4, 10, 5.5, 6))

    # Легенда (правый край)
    parts.append(_tiles_big(19, 20, 10, 11))
    parts.append(_legend_label(20.5, 10.5, "плитка"))
    parts.append(_apple_tree(_px(19.5), _py(8) + 5, 0.55))
    parts.append(_legend_label(20.5, 8.5, "яблоня"))
    parts.append(_carrot(_px(19.5), _py(6.5), 0.6))
    parts.append(_legend_label(20.5, 6.5, "огород"))
    parts.append(_scale_2m())

    # Подпись «ворота» справа от правой створки
    parts.append(
        f'<text x="{_fmt(_px(10.5))}" y="{_fmt(_py(1.5) + 4)}" text-anchor="start" '
        f'font-family="Cambria, Georgia, serif" font-size="15" fill="#000">ворота</text>'
    )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 770 410" '
        'style="max-width:100%;height:auto;display:block;margin:0.8em auto;">'
        + "".join(parts) +
        '</svg>'
    )


# ============================================================
#   План СНТ «ПРИБОР» (856918)
# ============================================================

def _build_pribor():
    parts = [_TILE_DEFS, _grid()]

    # Забор (2,2)→(17,12) с разрывом слева на (2,4)-(2,6)
    parts.append(_L(2, 2, 17, 2))
    parts.append(_L(2, 12, 17, 12))
    parts.append(_L(17, 2, 17, 12))
    parts.append(_L(2, 2, 2, 4))
    parts.append(_L(2, 6, 2, 12))
    # Створки наружу (влево)
    parts.append(_L(2, 4, 1, 4.5, 1.8))
    parts.append(_L(2, 6, 1, 5.5, 1.8))

    # Плитка-площадка (2,4)-(7,6)
    parts.append(_tiles_small([(2,4),(2,6),(7,6),(7,4)]))
    # Дорожки
    parts.append(_tiles_small([(2,6),(2.5,6),(2.5,10),(2,10)]))
    parts.append(_tiles_small([(2,9.5),(2,10),(11,10),(11,9.5)]))
    parts.append(_tiles_small([(10.5,5),(10.5,10),(11,10),(11,5)]))
    parts.append(_tiles_small([(7,5),(7,5.5),(11,5.5),(11,5)]))
    parts.append(_tiles_small([(12.5,4),(12.5,6),(14.5,6),(14.5,4)]))
    parts.append(_tiles_small([(11,5),(11,5.5),(12.5,5.5),(12.5,5)]))
    parts.append(_tiles_small([(5.5,6),(5.5,9.5),(6,9.5),(6,6)]))

    # Постройки
    parts.append(_building([(2,10),(2,12),(5,12),(5,10)]))
    parts.append(_num_circle(3.5, 11, 1))

    parts.append(_building([(2,2),(2,4),(7,4),(7,2)]))
    parts.append(_num_circle(4.5, 3, 2))

    parts.append(_building([(9.5,2.25),(9.5,3),(11,3),(11,2.25)]))
    parts.append(_num_circle(10.25, 2.625, 3))

    # Цветник 4
    parts.append(_dashed([(8,6),(8,7),(7,7),(7,9),(10,9),(10,6)]))
    parts.append(_flower(_px(7.5), _py(8.4), 0.5))
    parts.append(_flower(_px(8.5), _py(8.4), 0.5))
    parts.append(_flower(_px(9.5), _py(8.4), 0.5))
    parts.append(_flower(_px(9), _py(6.7), 0.5))
    parts.append(_num_circle(8.5, 7.5, 4))

    parts.append(_building([(12,2),(12,4),(15,4),(15,2)]))
    parts.append(_num_circle(13.5, 3, 5))

    parts.append(_building([(12.5,6),(12.5,7),(11,7),(11,11),(16,11),(16,7),(14.5,7),(14.5,6)]))
    parts.append(_num_circle(13.5, 9, 6))

    # Ели 7
    parts.append(_fir_tree(_px(7), _py(10.5), 0.4))
    parts.append(_fir_tree(_px(9), _py(10.5), 0.4))
    parts.append(_num_circle(8, 11, 7))

    # Легенда (правый край)
    parts.append(_tiles_small([(19,10),(19,11),(20,11),(20,10)]))
    parts.append(_legend_label(20.5, 10.5, "плитка"))
    parts.append(_fir_tree(_px(19.5), _py(7.5), 0.4))
    parts.append(_legend_label(20.5, 8, "ель"))
    parts.append(_flower(_px(19.5), _py(6.5), 0.5))
    parts.append(_legend_label(20.5, 6.5, "цветник"))
    parts.append(_scale_2m())

    # Подпись «ворота» вертикально, над верхней створкой
    x_anchor = _px(1.5)
    y_anchor = _py(6.3)
    parts.append(
        f'<text x="{_fmt(x_anchor)}" y="{_fmt(y_anchor)}" text-anchor="start" '
        f'font-family="Cambria, Georgia, serif" font-size="15" fill="#000" '
        f'transform="rotate(-90 {_fmt(x_anchor)} {_fmt(y_anchor)})">ворота</text>'
    )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 770 410" '
        'style="max-width:100%;height:auto;display:block;margin:0.8em auto;">'
        + "".join(parts) +
        '</svg>'
    )


# ============================================================
#   План СОСНОВКА (5BF94C)
# ============================================================

def _build_sosnovka():
    parts = [_TILE_DEFS, _grid()]

    # Забор (2,2)→(17,12) с разрывом справа на (17,6)-(17,8)
    parts.append(_L(2, 2, 17, 2))
    parts.append(_L(2, 12, 17, 12))
    parts.append(_L(2, 2, 2, 12))
    parts.append(_L(17, 2, 17, 6))
    parts.append(_L(17, 8, 17, 12))
    # Створки наружу (вправо)
    parts.append(_L(17, 6, 18, 6.5, 1.8))
    parts.append(_L(17, 8, 18, 7.5, 1.8))

    # Постройки
    # 1 — сарай (3×2)
    parts.append(_building([(14,10),(14,12),(17,12),(17,10)]))
    parts.append(_num_circle(15.5, 11, 1))
    # 2 — гараж (4×3)
    parts.append(_building([(13,2),(13,5),(17,5),(17,2)]))
    parts.append(_num_circle(15, 3.5, 2))
    # 4 — баня (3×3)
    parts.append(_building([(2,2),(2,5),(5,5),(5,2)]))
    parts.append(_num_circle(3.5, 3.5, 4))
    # 5 — теплица (3×1)
    parts.append(_building([(3,10),(3,11),(6,11),(6,10)]))
    parts.append(_num_circle(4.5, 10.5, 5))
    # 6 — огород (5×6)
    parts.append(_dashed([(2,6),(2,12),(7,12),(7,6)]))
    parts.append(_carrot(_px(5.5), _py(6.5), 0.5))
    parts.append(_carrot(_px(6.5), _py(6.5), 0.5))
    parts.append(_num_circle(4.5, 8.5, 6))
    # 7 — жилой дом Г-образный
    parts.append(_building([(8,7),(8,11),(13,11),(13,8),(10,8),(10,7)]))
    parts.append(_num_circle(10.5, 9.5, 7))

    # Яблоневые посадки 3
    parts.append(_apple_tree(_px(11.5), _py(3.5), 0.5))
    parts.append(_apple_tree(_px(9.5), _py(3.5), 0.5))
    parts.append(_num_circle(10.5, 3.5, 3))

    # Плитка (крупная 0.5 клетки)
    # Площадка между сараем и гаражом
    parts.append(_tiles_big(15, 17, 5, 10))
    # Дорожка: второй ряд снизу площадки (y=5.5..6) идёт влево до x=4
    parts.append(_tiles_big(4, 15, 5.5, 6))
    # Опуск к бане (дом 4): 1 плитка от левого конца дорожки
    parts.append(_tiles_big(4, 4.5, 5, 5.5))
    # Отвод к дому 7: на x=8.5..9 вверх к расширению (y=6..7)
    parts.append(_tiles_big(8.5, 9, 6, 7))

    # Легенда (правый край)
    parts.append(_tiles_big(19, 20, 10, 11))
    parts.append(_legend_label(20.5, 10.5, "плитка"))
    parts.append(_apple_tree(_px(19.5), _py(8) + 5, 0.55))
    parts.append(_legend_label(20.5, 8.5, "яблоня"))
    parts.append(_carrot(_px(19.5), _py(6.5), 0.6))
    parts.append(_legend_label(20.5, 6.5, "огород"))
    parts.append(_scale_2m())

    # Подпись «ворота» — сверху от верхней створки, повёрнута на -90°
    xa = _px(17.5)
    ya = _py(8.3)
    parts.append(
        f'<text x="{_fmt(xa)}" y="{_fmt(ya)}" text-anchor="start" '
        f'font-family="Cambria, Georgia, serif" font-size="15" fill="#000" '
        f'transform="rotate(-90 {_fmt(xa)} {_fmt(ya)})">ворота</text>'
    )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 770 410" '
        'style="max-width:100%;height:auto;display:block;margin:0.8em auto;">'
        + "".join(parts) +
        '</svg>'
    )


AVDEEVO_SVG = _build_avdeevo()
PRIBOR_SVG = _build_pribor()
SOSNOVKA_SVG = _build_sosnovka()
