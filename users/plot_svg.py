# -*- coding: utf-8 -*-
"""
Рисование графиков функций в SVG — для разборов задания №22.

Зачем свой рисовальщик, а не matplotlib: картинка уходит внутрь HTML-разбора
и должна быть текстом, а не файлом. Инлайновый SVG уже используется в условиях
задач (см. комментарий в lesson_practice.html), масштабируется без потерь и не
требует ни статики, ни лишнего запроса. matplotlib пришлось бы ставить в venv
ради PNG, который ещё надо куда-то положить.

Что умеет:
  * кусочно-заданные функции — каждый кусок своим отрезком по x;
  * разрывы и вертикальные асимптоты — линия обрывается на краю окна,
    а не соединяется прямой через весь экран;
  * выколотые точки (белый кружок) и закрашенные точки;
  * горизонтальные прямые y = m и прямые y = kx через начало координат —
    то, про что и спрашивают в №22.

Пример:

    from users.plot_svg import graph_svg
    svg = graph_svg(
        [(lambda x: x * x - 4, -4, 4)],
        xmin=-5, xmax=5, ymin=-6, ymax=6,
        holes=[(2, 0)],
        hlines=[(-4, 'y = -4')],
    )
"""

ФОН = '#ffffff'
СЕТКА = '#e6e9f0'
ОСИ = '#5a6274'
ПОДПИСИ = '#5a6274'
КРИВАЯ = '#1f4fd8'
ПРЯМАЯ = '#d64545'

ОБРАЗЦОВ = 220           # точек на кусок; на 420 px этого хватает для гладкости


def _тики(низ, верх):
    """Шаг подписей на оси: чтобы числа не налезали друг на друга."""
    ширина = верх - низ
    for шаг in (1, 2, 5, 10, 20, 50, 100):
        if ширина / шаг <= 12:
            return шаг
    return 100


def _точки_куска(func, x0, x1, ymin, ymax):
    """
    Насэмплировать кусок и разбить его на связные ломаные.

    Разрыв — это либо ошибка вычисления (деление на ноль), либо уход графика
    за пределы окна. Во втором случае линию доводим до края окна линейной
    интерполяцией: иначе гипербола у асимптоты обрывалась бы заметно раньше,
    чем на картинке из учебника.
    """
    шаг = (x1 - x0) / float(ОБРАЗЦОВ)
    сырые = []
    for i in range(ОБРАЗЦОВ + 1):
        x = x0 + i * шаг
        try:
            y = float(func(x))
        except (ZeroDivisionError, ValueError, OverflowError):
            y = None
        if y is not None and (y != y or abs(y) == float('inf')):   # nan / inf
            y = None
        сырые.append((x, y))

    ломаные, текущая = [], []
    предыдущая = None
    for x, y in сырые:
        внутри = y is not None and ymin <= y <= ymax
        if внутри:
            if предыдущая is not None and предыдущая[1] is not None and not (
                    ymin <= предыдущая[1] <= ymax):
                край = _на_краю(предыдущая, (x, y), ymin, ymax)
                if край:
                    текущая.append(край)
            текущая.append((x, y))
        else:
            if текущая:
                if y is not None:
                    край = _на_краю((текущая[-1][0], текущая[-1][1]), (x, y), ymin, ymax)
                    if край:
                        текущая.append(край)
                ломаные.append(текущая)
                текущая = []
        предыдущая = (x, y)
    if текущая:
        ломаные.append(текущая)
    return [л for л in ломаные if len(л) > 1]


def _на_краю(внутри, снаружи, ymin, ymax):
    """Точка пересечения отрезка с горизонтальной границей окна."""
    x1, y1 = внутри
    x2, y2 = снаружи
    if y1 is None or y2 is None or y1 == y2:
        return None
    граница = ymax if y2 > ymax else ymin
    доля = (граница - y1) / (y2 - y1)
    if not (0.0 <= доля <= 1.0):
        return None
    return (x1 + доля * (x2 - x1), граница)


def graph_svg(pieces, *, xmin, xmax, ymin, ymax,
              holes=(), dots=(), hlines=(), rays=(),
              width=420, height=340, pad=26, подпись_осей=True):
    """
    Собрать SVG с графиком.

    pieces  — [(функция, x0, x1), ...]; каждый кортеж рисуется отдельно, так
              что кусочно-заданная функция задаётся несколькими кортежами.
    holes   — [(x, y), ...] выколотые точки (белый кружок с обводкой).
    dots    — [(x, y), ...] закрашенные точки.
    hlines  — [(m, подпись), ...] горизонтальные прямые y = m.
    rays    — [(k, подпись), ...] прямые y = kx через начало координат.
    """
    вш = width - 2 * pad
    вв = height - 2 * pad

    def sx(x):
        return pad + (x - xmin) / float(xmax - xmin) * вш

    def sy(y):
        return height - pad - (y - ymin) / float(ymax - ymin) * вв

    def чс(v):
        """Короткая запись координаты: 12.0 → 12, 12.345 → 12.35."""
        return ('%.1f' % v).rstrip('0').rstrip('.')

    части = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
             'width="100%%" style="max-width:%dpx;height:auto;display:block;'
             'margin:0 auto" role="img">' % (width, height, width),
             '<rect width="%d" height="%d" fill="%s"/>' % (width, height, ФОН)]

    шx = _тики(xmin, xmax)
    шy = _тики(ymin, ymax)

    # ── сетка ──
    x = int(xmin // шx) * шx
    while x <= xmax:
        if xmin <= x <= xmax:
            части.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s"/>'
                         % (чс(sx(x)), чс(pad), чс(sx(x)), чс(height - pad), СЕТКА))
        x += шx
    y = int(ymin // шy) * шy
    while y <= ymax:
        if ymin <= y <= ymax:
            части.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s"/>'
                         % (чс(pad), чс(sy(y)), чс(width - pad), чс(sy(y)), СЕТКА))
        y += шy

    # ── оси со стрелками ──
    if ymin <= 0 <= ymax:
        нy = sy(0)
        части.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
                     'stroke-width="1.4"/>'
                     % (чс(pad - 6), чс(нy), чс(width - pad + 8), чс(нy), ОСИ))
        части.append('<path d="M%s %s l-7 -3.5 l0 7 z" fill="%s"/>'
                     % (чс(width - pad + 10), чс(нy), ОСИ))
        if подпись_осей:
            части.append('<text x="%s" y="%s" font-size="11" fill="%s">x</text>'
                         % (чс(width - pad + 2), чс(нy - 7), ПОДПИСИ))
    if xmin <= 0 <= xmax:
        нx = sx(0)
        части.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
                     'stroke-width="1.4"/>'
                     % (чс(нx), чс(height - pad + 6), чс(нx), чс(pad - 8), ОСИ))
        части.append('<path d="M%s %s l-3.5 7 l7 0 z" fill="%s"/>'
                     % (чс(нx), чс(pad - 10), ОСИ))
        if подпись_осей:
            части.append('<text x="%s" y="%s" font-size="11" fill="%s">y</text>'
                         % (чс(нx + 6), чс(pad - 4), ПОДПИСИ))

    # ── подписи делений ──
    if ymin <= 0 <= ymax:
        x = int(xmin // шx) * шx
        while x <= xmax:
            if xmin <= x <= xmax and x != 0:
                части.append('<text x="%s" y="%s" font-size="10" fill="%s" '
                             'text-anchor="middle">%s</text>'
                             % (чс(sx(x)), чс(sy(0) + 13), ПОДПИСИ, чс(x)))
            x += шx
    if xmin <= 0 <= xmax:
        y = int(ymin // шy) * шy
        while y <= ymax:
            if ymin <= y <= ymax and y != 0:
                части.append('<text x="%s" y="%s" font-size="10" fill="%s" '
                             'text-anchor="end">%s</text>'
                             % (чс(sx(0) - 5), чс(sy(y) + 3.5), ПОДПИСИ, чс(y)))
            y += шy
        части.append('<text x="%s" y="%s" font-size="10" fill="%s" '
                     'text-anchor="end">0</text>'
                     % (чс(sx(0) - 5), чс(sy(0) + 13), ПОДПИСИ))

    # ── прямые, про которые спрашивают ──
    #
    # Подписи собираем в отдельный список и рисуем последними: во-первых,
    # чтобы они легли поверх кривой, во-вторых, чтобы развести те, что
    # оказались рядом. Прижимать подпись к правому краю нельзя — там стрелка
    # оси, её буква и крайнее деление, и на них уже налезали подписи «y = 0»
    # и «y = -1».
    подписи = []

    def подписать(y_пикс, текст):
        подписи.append([y_пикс, текст])

    for m, подпись in hlines:
        if not (ymin <= m <= ymax):
            continue
        части.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
                     'stroke-width="1.4" stroke-dasharray="6 4"/>'
                     % (чс(pad), чс(sy(m)), чс(width - pad), чс(sy(m)), ПРЯМАЯ))
        if подпись:
            подписать(sy(m) - 5, подпись)

    for k, подпись in rays:
        # Обрезка прямой по окну: берём её пересечения со всеми четырьмя
        # границами и оставляем те, что попали внутрь. Считать только по
        # вертикальным границам мало: при большом |k| прямая выходит через
        # верх и низ, и обе точки отбраковались бы.
        точки = [(x, k * x) for x in (xmin, xmax) if ymin <= k * x <= ymax]
        if k:
            точки += [(y / float(k), y) for y in (ymin, ymax)
                      if xmin <= y / float(k) <= xmax]
        точки = sorted(set((round(x, 9), round(y, 9)) for x, y in точки))
        if len(точки) >= 2:
            (x1, y1), (x2, y2) = точки[0], точки[-1]
            части.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
                         'stroke-width="1.4" stroke-dasharray="6 4"/>'
                         % (чс(sx(x1)), чс(sy(y1)), чс(sx(x2)), чс(sy(y2)), ПРЯМАЯ))
            if подпись:
                # У наклонной прямой подпись ставим там, где она входит в
                # окно слева, — на той же стороне, что и у горизонтальных.
                левая = точки[0] if точки[0][0] <= точки[-1][0] else точки[-1]
                подписать(sy(левая[1]) - 5, подпись)

    # Развести подписи, оказавшиеся ближе 13 px: иначе «y = -2» и «y = -2,1»
    # сливаются в пятно (зазор между прямыми бывает и в 5 px).
    подписи.sort()
    for i in range(1, len(подписи)):
        if подписи[i][0] - подписи[i - 1][0] < 13:
            подписи[i][0] = подписи[i - 1][0] + 13
    for y_пикс, текст in подписи:
        y_пикс = min(max(y_пикс, 12), height - 6)
        # Белая обводка под текстом: подпись читается и поверх сетки, и
        # поверх кривой, не пряча их.
        части.append('<text x="%s" y="%s" font-size="11" fill="%s" '
                     'stroke="%s" stroke-width="3" paint-order="stroke" '
                     'stroke-linejoin="round">%s</text>'
                     % (чс(pad + 3), чс(y_пикс), ПРЯМАЯ, ФОН, текст))

    # ── сам график ──
    for func, x0, x1 in pieces:
        for ломаная in _точки_куска(func, x0, x1, ymin, ymax):
            d = 'M' + ' L'.join('%s %s' % (чс(sx(x)), чс(sy(y))) for x, y in ломаная)
            части.append('<path d="%s" fill="none" stroke="%s" stroke-width="2" '
                         'stroke-linejoin="round" stroke-linecap="round"/>' % (d, КРИВАЯ))

    for x, y in dots:
        if xmin <= x <= xmax and ymin <= y <= ymax:
            части.append('<circle cx="%s" cy="%s" r="3.6" fill="%s"/>'
                         % (чс(sx(x)), чс(sy(y)), КРИВАЯ))
    for x, y in holes:
        if xmin <= x <= xmax and ymin <= y <= ymax:
            части.append('<circle cx="%s" cy="%s" r="3.6" fill="%s" stroke="%s" '
                         'stroke-width="2"/>' % (чс(sx(x)), чс(sy(y)), ФОН, КРИВАЯ))

    части.append('</svg>')
    return ''.join(части)
