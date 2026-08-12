# -*- coding: utf-8 -*-
"""SVG-график потребления для группы Тарифы (F4978F).

Строит тот же график, что в превью _preview_tarif.html:
  • чёрная сплошная линия — минуты исходящих вызовов (левая ось),
  • пунктирная линия — трафик в ГБ (правая ось),
  • жирная линия уровня пакета (300 мин = 3 ГБ),
  • подписи осей и легенда.
"""

# Данные по месяцам 2019 г.
SOLID = [175, 275, 150, 350, 300, 325, 375, 325, 200, 200, 325, 350]   # минуты
DASHED_GB = [2.5, 3.5, 2, 4, 2.75, 3, 1, 1.5, 2.75, 3.25, 3.75, 2.25]  # гигабайты

W, H = 600, 360
PL, PR, PT, PB = 60, 60, 30, 50
PW, PH = W - PL - PR, H - PT - PB
Y_MAX_MIN = 400
Y_MAX_GB = 4
X_COUNT = 12
X_INSET = 0.5


def _xpx(month):
    return PL + (X_INSET + (month - 1)) / (X_COUNT - 1 + 2 * X_INSET) * PW


def _ypx_min(v):
    return PT + PH - (v / Y_MAX_MIN) * PH


def _ypx_gb(v):
    return PT + PH - (v / Y_MAX_GB) * PH


def _f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _build_tariff_svg():
    p = []
    p.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" '
        'style="max-width:100%;height:auto;display:block;margin:0.8em auto;">'
    )

    # Сетка
    v = 0
    while v <= Y_MAX_MIN:
        y = _ypx_min(v)
        p.append(f'<line x1="{PL}" y1="{_f(y)}" x2="{PL+PW}" y2="{_f(y)}" stroke="#d6d6d6" stroke-width="0.6"/>')
        v += 25
    for m in range(1, X_COUNT + 1):
        x = _xpx(m)
        p.append(f'<line x1="{_f(x)}" y1="{PT}" x2="{_f(x)}" y2="{PT+PH}" stroke="#d6d6d6" stroke-width="0.6"/>')

    # Левая ось — минуты
    p.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+PH}" stroke="#000" stroke-width="1.2"/>')
    v = 0
    while v <= Y_MAX_MIN:
        y = _ypx_min(v)
        p.append(f'<line x1="{PL-5}" y1="{_f(y)}" x2="{PL}" y2="{_f(y)}" stroke="#000" stroke-width="1"/>')
        p.append(f'<text x="{PL-8}" y="{_f(y+4)}" text-anchor="end" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#000">{v}</text>')
        v += 50
    p.append(f'<text x="{PL-50}" y="{_f(PT+PH/2)}" text-anchor="middle" transform="rotate(-90 {PL-50} {_f(PT+PH/2)})" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#000">мин</text>')

    # Правая ось — гигабайты
    p.append(f'<line x1="{PL+PW}" y1="{PT}" x2="{PL+PW}" y2="{PT+PH}" stroke="#000" stroke-width="1.2"/>')
    v = 0.0
    while v <= Y_MAX_GB + 1e-9:
        y = _ypx_gb(v)
        p.append(f'<line x1="{PL+PW}" y1="{_f(y)}" x2="{PL+PW+5}" y2="{_f(y)}" stroke="#000" stroke-width="1"/>')
        label = str(int(v)) if abs(v - round(v)) < 1e-9 else str(v).replace(".", ",")
        p.append(f'<text x="{PL+PW+8}" y="{_f(y+4)}" text-anchor="start" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#000">{label}</text>')
        v += 0.5
    p.append(f'<text x="{PL+PW+38}" y="{_f(PT+PH/2)}" text-anchor="middle" transform="rotate(-90 {PL+PW+38} {_f(PT+PH/2)})" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#000">ГБ</text>')

    # Нижняя ось — месяцы
    p.append(f'<line x1="{PL}" y1="{PT+PH}" x2="{PL+PW}" y2="{PT+PH}" stroke="#000" stroke-width="1.2"/>')
    for m in range(1, X_COUNT + 1):
        x = _xpx(m)
        p.append(f'<text x="{_f(x)}" y="{PT+PH+14}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#000">{m}</text>')
    p.append(f'<text x="{_f(PL+PW/2)}" y="{H-8}" text-anchor="middle" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#000">месяц</text>')

    # Уровень пакета 300 мин = 3 ГБ
    limit_y = _ypx_min(300)
    p.append(f'<line x1="{PL}" y1="{_f(limit_y)}" x2="{PL+PW}" y2="{_f(limit_y)}" stroke="#000" stroke-width="2.5"/>')

    # Легенда над осями
    tx, ty = PL - 4, PT - 14
    p.append(f'<text x="{tx}" y="{ty}" text-anchor="end" font-family="Cambria, Georgia, serif" font-size="13" fill="#000">минуты</text>')
    p.append(f'<line x1="{tx-46}" y1="{ty+4}" x2="{tx}" y2="{ty+4}" stroke="#000" stroke-width="1.6"/>')
    tx2 = PL + PW + 4
    p.append(f'<text x="{tx2}" y="{ty}" text-anchor="start" font-family="Cambria, Georgia, serif" font-size="13" fill="#000">гигабайты</text>')
    p.append(f'<line x1="{tx2}" y1="{ty+4}" x2="{tx2+64}" y2="{ty+4}" stroke="#000" stroke-width="1.4" stroke-dasharray="5,3"/>')

    # Сплошная линия (минуты) + точки
    solid = " ".join(f"{'M' if i==0 else 'L'} {_f(_xpx(i+1))},{_f(_ypx_min(v))}" for i, v in enumerate(SOLID))
    p.append(f'<path d="{solid}" fill="none" stroke="#000" stroke-width="1.6"/>')
    for i, v in enumerate(SOLID):
        p.append(f'<circle cx="{_f(_xpx(i+1))}" cy="{_f(_ypx_min(v))}" r="3" fill="#000"/>')

    # Пунктирная линия (ГБ) + пустые точки
    dashed = " ".join(f"{'M' if i==0 else 'L'} {_f(_xpx(i+1))},{_f(_ypx_gb(v))}" for i, v in enumerate(DASHED_GB))
    p.append(f'<path d="{dashed}" fill="none" stroke="#000" stroke-width="1.4" stroke-dasharray="5,3"/>')
    for i, v in enumerate(DASHED_GB):
        p.append(f'<circle cx="{_f(_xpx(i+1))}" cy="{_f(_ypx_gb(v))}" r="3" fill="#fff" stroke="#000" stroke-width="1.2"/>')

    p.append('</svg>')
    return "".join(p)


TARIFF_SVG = _build_tariff_svg()
