# -*- coding: utf-8 -*-
"""
Management command: создаёт ProblemGenerator-ы и Assignment-ы под урок
«Задание 15» курса ОГЭ. Тема — «Треугольники».

Архитектура (после второй итерации, по каталогу Школково /catalog/7154):
    01. Углы. Сумма (180° / 90° / внешний)               — Типы 1, 2, 4
    02. Углы. Равнобедренный треугольник                  — Тип 3
    03. Углы через чевиану (простые)                       — Типы 5, 6
    04. Углы через чевиану (многоходовая)                  — Тип 8
    05. Медиана: определение и признак прямого угла        — Типы 7, 9
    06. Теорема Пифагора                                   — Типы 10, 11
    07. Равносторонний треугольник. Сторона → чевиана      — Типы 12-14
    08. Равносторонний треугольник. Чевиана → сторона      — Типы 15-17
    09. Тригонометрия в прямоугольном (определение)        — Типы 18-20
    10. Тригонометрия. Найти сторону (обратные задачи)     — Типы 21-23
    11. Площадь треугольника                               — Типы 24, 25, 26
    12. Средняя линия треугольника                         — Тип 27

Ключевое отличие от первой итерации: рисунки СТАТИЧНЫЕ.
В каждом подтипе фиксированная SVG-картинка с буквами вершин и нужными
вспомогательными элементами (медианы, высоты, маркеры равенства,
маркер прямого угла). Никакие числа в SVG не подставляются — конкретные
данные задачи живут только в тексте условия. Это убирает «прыгающие»
рисунки при экстремальных значениях параметров.

Стиль SVG (общий для всех типов):
    - viewBox 0 0 320 220
    - чёрный stroke #1f1f1f, толщина 1.5
    - шрифт Cambria/Georgia italic 15pt для подписей
    - кружочки r=2.5 на вершинах
    - засечки равенства — штрихи перпендикулярно отрезку
    - маркер прямого угла — небольшой квадратик в углу

Usage:
    python manage.py seed_oge15
    python manage.py seed_oge15 --clear
"""

import math
from string import Template

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Утилита для построения «засечек равенства» — небольших чёрточек,
# перпендикулярных отрезку и проходящих через его середину.
#
#     tick(P1, P2)            — одна засечка через середину.
#     tick(P1, P2, count=2)   — две параллельные засечки, симметрично смещённые
#                               вдоль отрезка на ±gap/2 от середины.
#
# Возвращает строку с одним или несколькими SVG-элементами <line ... />,
# которые можно вставить прямо в SVG-картинку.
# ──────────────────────────────────────────────────────────────────────────────


def tick(P1, P2, count=1, length=12, gap=4):
    Mx = (P1[0] + P2[0]) / 2
    My = (P1[1] + P2[1]) / 2
    dx, dy = P2[0] - P1[0], P2[1] - P1[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return ''
    # единичный вектор вдоль отрезка
    ux, uy = dx / L, dy / L
    # единичный вектор перпендикулярно отрезку
    nx, ny = -dy / L, dx / L
    h = length / 2
    if count == 1:
        offsets = [0]
    else:
        offsets = [gap * (i - (count - 1) / 2) for i in range(count)]
    parts = []
    for off in offsets:
        cx = Mx + off * ux
        cy = My + off * uy
        parts.append(
            f'<line x1="{cx - nx*h:.1f}" y1="{cy - ny*h:.1f}" '
            f'x2="{cx + nx*h:.1f}" y2="{cy + ny*h:.1f}" '
            f'stroke="#1f1f1f" stroke-width="1.4"/>'
        )
    return ''.join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Утилита для построения дуги в углу треугольника.
#
#     arc(vertex, P1, P2)                    — простая одиночная дуга от
#                                              направления к P1 до направления
#                                              к P2 («меньшая» дуга).
#     arc(vertex, P1, P2, marks=2)           — две концентрические дуги
#                                              (символ двойного угла).
#     arc(vertex, P1, P2, label='α')         — подпись в биссектрисе угла.
#
# Возвращает строку с <path>…</path> и (опционально) <text>…</text>,
# готовую к вставке в SVG.
# ──────────────────────────────────────────────────────────────────────────────


def midpoint(P1, P2):
    """Середина отрезка."""
    return ((P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2)


def foot_of_perp(P, A, B):
    """Основание перпендикуляра из точки P на прямую AB."""
    ax, ay = A
    bx, by = B
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return A
    t = ((P[0] - ax) * dx + (P[1] - ay) * dy) / L2
    return (ax + t * dx, ay + t * dy)


def bisector_foot(A, B, C):
    """Точка пересечения биссектрисы из A со стороной BC.

    По теореме о биссектрисе BD:DC = AB:AC.
    Возвращает (x, y).
    """
    AB = math.hypot(A[0] - B[0], A[1] - B[1])
    AC = math.hypot(A[0] - C[0], A[1] - C[1])
    t = AB / (AB + AC)
    return (B[0] + (C[0] - B[0]) * t, B[1] + (C[1] - B[1]) * t)


def equilateral_apex(A, C, above=True):
    """Третья вершина равностороннего треугольника, построенного на основании AC.

    above=True — апекс выше AC (с меньшим y в системе SVG).
    """
    Mx, My = midpoint(A, C)
    dx, dy = C[0] - A[0], C[1] - A[1]
    L = math.hypot(dx, dy)
    # Перпендикуляр к AC длиной L*sin(60°) = L·√3/2
    h = L * math.sqrt(3) / 2
    nx, ny = -dy / L, dx / L
    sign = -1 if above else 1   # в SVG y растёт вниз
    return (Mx + sign * nx * h, My + sign * ny * h)


def right_angle_marker(vertex, P1, P2, size=10):
    """SVG-маркер прямого угла в вершине между сторонами на P1 и P2.

    Рисует маленький квадратик «полилинией» по двум сторонам угла.
    """
    vx, vy = vertex
    d1x, d1y = P1[0] - vx, P1[1] - vy
    d2x, d2y = P2[0] - vx, P2[1] - vy
    L1 = math.hypot(d1x, d1y)
    L2 = math.hypot(d2x, d2y)
    if L1 < 1e-9 or L2 < 1e-9:
        return ""
    u1x, u1y = d1x / L1 * size, d1y / L1 * size
    u2x, u2y = d2x / L2 * size, d2y / L2 * size
    a = (vx + u1x, vy + u1y)
    b = (vx + u1x + u2x, vy + u1y + u2y)
    c = (vx + u2x, vy + u2y)
    return (
        f'<polyline points="{a[0]:.1f},{a[1]:.1f} '
        f'{b[0]:.1f},{b[1]:.1f} {c[0]:.1f},{c[1]:.1f}" '
        f'fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )


def extend(P_from, P_to, length):
    """Точка на луче из P_from через P_to, продолженная на 'length' за P_to."""
    dx, dy = P_to[0] - P_from[0], P_to[1] - P_from[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return P_to
    return (P_to[0] + dx / L * length, P_to[1] + dy / L * length)


def arc(vertex, P1, P2, radius=22, marks=1, mark_gap=4,
        label="", label_offset=14):
    vx, vy = vertex
    a1 = math.atan2(P1[1] - vy, P1[0] - vx)
    a2 = math.atan2(P2[1] - vy, P2[0] - vx)
    # Берём «меньший» угол между сторонами: нормализуем разность в [-π, π].
    da = a2 - a1
    while da > math.pi:
        da -= 2 * math.pi
    while da < -math.pi:
        da += 2 * math.pi
    sweep = 1 if da > 0 else 0      # направление обхода для SVG path
    am = a1 + da / 2                # биссектриса (направление подписи)

    parts = []
    for i in range(marks):
        R = radius + i * mark_gap
        x1 = vx + R * math.cos(a1)
        y1 = vy + R * math.sin(a1)
        x2 = vx + R * math.cos(a2)
        y2 = vy + R * math.sin(a2)
        parts.append(
            f'<path d="M {x1:.1f},{y1:.1f} A {R},{R} 0 0 {sweep} '
            f'{x2:.1f},{y2:.1f}" fill="none" '
            f'stroke="#1f1f1f" stroke-width="1.1"/>'
        )

    if label:
        R_label = radius + (marks - 1) * mark_gap + label_offset
        lx = vx + R_label * math.cos(am)
        ly = vy + R_label * math.sin(am)
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" '
            f'font-family="Cambria, Georgia, serif" font-style="italic" '
            f'font-size="13" fill="#1f1f1f" text-anchor="middle" '
            f'dominant-baseline="middle">{label}</text>'
        )

    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Статичные SVG-картинки. Каждая — каноническая иллюстрация подтипа задачи.
# Координаты подобраны вручную, никаких пересчётов.
# ──────────────────────────────────────────────────────────────────────────────

# Каноническая треугольная база, переиспользуется во многих SVG.
# Остроугольный, не прямоугольный, A слева внизу, B вверху, C справа внизу.
_TRI_A = (40, 180)
_TRI_B = (200, 50)
_TRI_C = (280, 180)


def _vertex(P):
    return f'<circle cx="{P[0]:.2f}" cy="{P[1]:.2f}" r="2.5" fill="#1f1f1f"/>'


def _label(P, letter, dx=0, dy=0, size=15):
    return (f'<text x="{P[0]+dx:.2f}" y="{P[1]+dy:.2f}" '
            f'font-family="Cambria, Georgia, serif" font-style="italic" '
            f'font-size="{size}" fill="#1f1f1f">{letter}</text>')


# 1. Остроугольный треугольник ABC.
SVG_BASIC = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=8, dy=20)}
</svg>'''

# 2. Прямоугольный треугольник, прямой угол в C.
# A — слева внизу, C — слева вверху (прямой угол), B — справа вверху.
# Катеты: AC вертикальный (длина 120), CB горизонтальный (длина 240).
_RC_A = (40, 180)
_RC_C = (40, 60)
_RC_B = (280, 60)
SVG_RIGHT_C = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Прямоугольный треугольник ABC, угол C равен 90°">
  <polygon points="{_RC_A[0]},{_RC_A[1]} {_RC_B[0]},{_RC_B[1]} {_RC_C[0]},{_RC_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  {right_angle_marker(_RC_C, _RC_A, _RC_B, size=10)}
  {_vertex(_RC_A)}{_vertex(_RC_B)}{_vertex(_RC_C)}
  {_label(_RC_A, 'A', dx=-18, dy=20)}
  {_label(_RC_B, 'B', dx=8, dy=-4)}
  {_label(_RC_C, 'C', dx=-18, dy=-4)}
</svg>'''

# 3. Треугольник с продолжением стороны AC за вершину C (для внешнего угла).
_EXT_END = extend(_TRI_A, _TRI_C, 30)
SVG_EXTERNAL_C = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с продолжением стороны AC за C">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_TRI_C[0]}" y1="{_TRI_C[1]}" x2="{_EXT_END[0]:.2f}" y2="{_EXT_END[1]:.2f}" stroke="#1f1f1f" stroke-width="1.3" stroke-dasharray="5,3"/>
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=-12, dy=20)}
</svg>'''

# 4. Равнобедренный треугольник, AB = BC, апекс в B сверху по симметрии.
_ISO_A = (60, 180)
_ISO_C = (260, 180)
_ISO_B = (midpoint(_ISO_A, _ISO_C)[0], 50)    # на оси симметрии
SVG_ISOSCELES = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равнобедренный треугольник ABC, AB равно BC">
  <polygon points="{_ISO_A[0]},{_ISO_A[1]} {_ISO_B[0]},{_ISO_B[1]} {_ISO_C[0]},{_ISO_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  {tick(_ISO_A, _ISO_B)}
  {tick(_ISO_B, _ISO_C)}
  {_vertex(_ISO_A)}{_vertex(_ISO_B)}{_vertex(_ISO_C)}
  {_label(_ISO_A, 'A', dx=-18, dy=20)}
  {_label(_ISO_B, 'B', dx=-5, dy=-8)}
  {_label(_ISO_C, 'C', dx=8, dy=20)}
</svg>'''

# 5. Треугольник с высотой BH из вершины B на сторону AC.
# H — основание перпендикуляра, вычислено через foot_of_perp.
# Маркер прямого угла НЕ рисуем — слово «высота» в условии уже подразумевает
# перпендикулярность; пусть ученик это сам сообразит.
_H_BH = foot_of_perp(_TRI_B, _TRI_A, _TRI_C)
SVG_HEIGHT_BH = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с высотой BH">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_TRI_B[0]}" y1="{_TRI_B[1]}" x2="{_H_BH[0]:.2f}" y2="{_H_BH[1]:.2f}" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="4,3"/>
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}{_vertex(_H_BH)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=8, dy=20)}
  {_label(_H_BH, 'H', dx=4, dy=18, size=13)}
</svg>'''

# 6. Треугольник с биссектрисой AD из вершины A.
# D — точка пересечения биссектрисы со стороной BC (BD:DC = AB:AC).
# Парные дуги в углах A имеют разные радиусы (18 и 30), чтобы не сливались.
_BIS_AD_D = bisector_foot(_TRI_A, _TRI_B, _TRI_C)
SVG_BISECTOR_AD = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с биссектрисой AD">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_TRI_A[0]}" y1="{_TRI_A[1]}" x2="{_BIS_AD_D[0]:.2f}" y2="{_BIS_AD_D[1]:.2f}" stroke="#1f1f1f" stroke-width="1.3"/>
  {arc(_TRI_A, _TRI_B, _BIS_AD_D, radius=18)}
  {arc(_TRI_A, _BIS_AD_D, _TRI_C, radius=30)}
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}{_vertex(_BIS_AD_D)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=8, dy=20)}
  {_label(_BIS_AD_D, 'D', dx=6, dy=-4, size=13)}
</svg>'''

# 7. Треугольник с медианой BM (M — середина AC). Маркеры равенства AM=MC.
_MED_M = midpoint(_TRI_A, _TRI_C)
SVG_MEDIAN_BM = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с медианой BM">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_TRI_B[0]}" y1="{_TRI_B[1]}" x2="{_MED_M[0]:.2f}" y2="{_MED_M[1]:.2f}" stroke="#1f1f1f" stroke-width="1.3"/>
  {tick(_TRI_A, _MED_M)}
  {tick(_MED_M, _TRI_C)}
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}{_vertex(_MED_M)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=8, dy=20)}
  {_label(_MED_M, 'M', dx=-4, dy=18, size=13)}
</svg>'''

# 8. Биссектриса AK + маркеры равенства AK = KC (для многоходовки Тип 8).
# Используем 30-60-90 треугольник (∠C=30°, ∠A=60°, ∠B=90°) как геометрически
# корректную иллюстрацию: только в нём AK биссектриса И AK=KC одновременно.
# A=(40,180), C=(280,180), B=(100,76), K=(160,111).
# Дуги в углах ∠BAK и ∠KAC имеют разные радиусы — чтобы не сливались.
# Координаты B и K заданы точно через тригонометрию 30-60-90:
#   B = A + 120·(cos 60°, −sin 60°),  K = B + (C−B)/3,  откуда K делит BC в 1:2.
_AK_A = (40, 180)
_AK_C = (280, 180)
_AK_B = (40 + 120 * math.cos(math.radians(60)),
         180 - 120 * math.sin(math.radians(60)))
_AK_K = (_AK_B[0] + (_AK_C[0] - _AK_B[0]) / 3,
         _AK_B[1] + (_AK_C[1] - _AK_B[1]) / 3)

SVG_BISECTOR_AK_EQ = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с биссектрисой AK, AK равно KC">
  <polygon points="{_AK_A[0]},{_AK_A[1]} {_AK_B[0]:.2f},{_AK_B[1]:.2f} {_AK_C[0]},{_AK_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_AK_A[0]}" y1="{_AK_A[1]}" x2="{_AK_K[0]:.2f}" y2="{_AK_K[1]:.2f}" stroke="#1f1f1f" stroke-width="1.3"/>
  {arc(_AK_A, _AK_B, _AK_K, radius=18)}
  {arc(_AK_A, _AK_K, _AK_C, radius=30)}
  {tick(_AK_A, _AK_K)}
  {tick(_AK_K, _AK_C)}
  <circle cx="{_AK_A[0]}" cy="{_AK_A[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{_AK_B[0]:.2f}" cy="{_AK_B[1]:.2f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{_AK_C[0]}" cy="{_AK_C[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{_AK_K[0]:.2f}" cy="{_AK_K[1]:.2f}" r="2.5" fill="#1f1f1f"/>
  <text x="22" y="200" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="{_AK_B[0]-14:.2f}" y="{_AK_B[1]-4:.2f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="288" y="200" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="{_AK_K[0]+6:.2f}" y="{_AK_K[1]-5:.2f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">K</text>
</svg>'''

# 9. Прямоугольный треугольник с медианой BM, BM = AM = MC (для Тип 9).
# По обратной теореме о медиане: если BM = AC/2 = AM = MC, то ∠B = 90°.
# Берём 30-60-90 как геометрически корректный пример, но маркер прямого угла
# НЕ рисуем — ученик должен сам вывести ∠B = 90° из условия BM=AM=MC.
_MR_A = (40, 180)
_MR_C = (280, 180)
_MR_B = (40 + 120 * math.cos(math.radians(60)),
         180 - 120 * math.sin(math.radians(60)))
_MR_M = midpoint(_MR_A, _MR_C)
SVG_MEDIAN_BM_RIGHT = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с медианой BM, BM равно AM равно MC">
  <polygon points="{_MR_A[0]},{_MR_A[1]} {_MR_B[0]:.2f},{_MR_B[1]:.2f} {_MR_C[0]},{_MR_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_MR_B[0]:.2f}" y1="{_MR_B[1]:.2f}" x2="{_MR_M[0]:.2f}" y2="{_MR_M[1]:.2f}" stroke="#1f1f1f" stroke-width="1.3"/>
  {tick(_MR_A, _MR_M, count=2)}
  {tick(_MR_M, _MR_C, count=2)}
  {tick(_MR_B, _MR_M, count=2)}
  {_vertex(_MR_A)}{_vertex(_MR_B)}{_vertex(_MR_C)}{_vertex(_MR_M)}
  {_label(_MR_A, 'A', dx=-18, dy=20)}
  {_label(_MR_B, 'B', dx=-14, dy=-4)}
  {_label(_MR_C, 'C', dx=8, dy=20)}
  {_label(_MR_M, 'M', dx=-4, dy=18, size=13)}
</svg>'''

# Равносторонний треугольник: основание AC длиной 160, апекс B сверху.
# Высота 160·√3/2 ≈ 138.6. Чтобы рисунок был сбалансированным и подпись B
# не упиралась в верх viewBox: A=(80,190), C=(240,190), B≈(160, 51.4).
_EQ_A = (80, 190)
_EQ_C = (240, 190)
_EQ_B = equilateral_apex(_EQ_A, _EQ_C, above=True)
_EQ_M = midpoint(_EQ_A, _EQ_B)

_EQ_POLYGON = (
    f'<polygon points="{_EQ_A[0]},{_EQ_A[1]} '
    f'{_EQ_B[0]:.2f},{_EQ_B[1]:.2f} '
    f'{_EQ_C[0]},{_EQ_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>'
)
_EQ_CEVIAN = (
    f'<line x1="{_EQ_C[0]}" y1="{_EQ_C[1]}" '
    f'x2="{_EQ_M[0]:.2f}" y2="{_EQ_M[1]:.2f}" '
    f'stroke="#1f1f1f" stroke-width="1.3"/>'
)
_EQ_CEVIAN_DASHED = (
    f'<line x1="{_EQ_C[0]}" y1="{_EQ_C[1]}" '
    f'x2="{_EQ_M[0]:.2f}" y2="{_EQ_M[1]:.2f}" '
    f'stroke="#1f1f1f" stroke-width="1.3" stroke-dasharray="4,3"/>'
)
_EQ_DOTS = (_vertex(_EQ_A) + _vertex(_EQ_B) + _vertex(_EQ_C) + _vertex(_EQ_M))
_EQ_VERTEX_LABELS = (
    _label(_EQ_A, 'A', dx=-18, dy=20) +
    _label(_EQ_B, 'B', dx=-5, dy=-8) +
    _label(_EQ_C, 'C', dx=8, dy=20)
)


# 10. Равностор. треугольник с медианой CM, M — середина AB.
# AM=MB обозначены двойными засечками; одинарные на BC и CA — равенство сторон.
SVG_EQ_MEDIAN = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равносторонний треугольник ABC с медианой CM">
  {_EQ_POLYGON}
  {_EQ_CEVIAN}
  {tick(_EQ_A, _EQ_M, count=2)}
  {tick(_EQ_M, _EQ_B, count=2)}
  {tick(_EQ_B, _EQ_C)}
  {tick(_EQ_A, _EQ_C)}
  {_EQ_DOTS}
  {_EQ_VERTEX_LABELS}
  {_label(_EQ_M, 'M', dx=-16, dy=2, size=13)}
</svg>'''

# 11. Равностор. треугольник с высотой CH. H = середина AB.
# Маркер прямого угла НЕ рисуем — «высота» уже задана в условии.
SVG_EQ_HEIGHT = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равносторонний треугольник ABC с высотой CH">
  {_EQ_POLYGON}
  {_EQ_CEVIAN_DASHED}
  {tick(_EQ_A, _EQ_B)}
  {tick(_EQ_B, _EQ_C)}
  {tick(_EQ_A, _EQ_C)}
  {_EQ_DOTS}
  {_EQ_VERTEX_LABELS}
  {_label(_EQ_M, 'H', dx=-16, dy=2, size=13)}
</svg>'''

# 12. Равностор. треугольник с биссектрисой CD. D = середина AB (в равностор.
# биссектриса совпадает с медианой и высотой). Парные дуги разных радиусов.
SVG_EQ_BISECTOR = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равносторонний треугольник ABC с биссектрисой CD">
  {_EQ_POLYGON}
  {_EQ_CEVIAN}
  {arc(_EQ_C, _EQ_B, _EQ_M, radius=18)}
  {arc(_EQ_C, _EQ_M, _EQ_A, radius=30)}
  {tick(_EQ_A, _EQ_B)}
  {tick(_EQ_B, _EQ_C)}
  {tick(_EQ_A, _EQ_C)}
  {_EQ_DOTS}
  {_EQ_VERTEX_LABELS}
  {_label(_EQ_M, 'D', dx=-16, dy=2, size=13)}
</svg>'''

# 13. Треугольник с высотой CH к стороне AB (для площади S = ah/2).
# H — основание перпендикуляра из C на AB, вычислено через foot_of_perp.
# Маркер прямого угла НЕ рисуем — слово «высота» уже подразумевает перпендикуляр.
_AH_H = foot_of_perp(_TRI_C, _TRI_A, _TRI_B)
SVG_AREA_AH = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с высотой CH к стороне AB">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_TRI_C[0]}" y1="{_TRI_C[1]}" x2="{_AH_H[0]:.2f}" y2="{_AH_H[1]:.2f}" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="4,3"/>
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}{_vertex(_AH_H)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=8, dy=20)}
  {_label(_AH_H, 'H', dx=-14, dy=2, size=13)}
</svg>'''

# 14. Треугольник с дугой при вершине B (для площади S = ½ ab sin B).
SVG_AREA_SIN = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с углом при B">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  {arc(_TRI_B, _TRI_A, _TRI_C, radius=26)}
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=8, dy=20)}
</svg>'''

# 15. Треугольник со средней линией MN, M — середина AB, N — середина BC.
# AM=MB обозначены одинарной засечкой, BN=NC — двойной (чтобы пары не перепутать).
_ML_M = midpoint(_TRI_A, _TRI_B)
_ML_N = midpoint(_TRI_B, _TRI_C)
SVG_MIDLINE = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC со средней линией MN">
  <polygon points="{_TRI_A[0]},{_TRI_A[1]} {_TRI_B[0]},{_TRI_B[1]} {_TRI_C[0]},{_TRI_C[1]}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{_ML_M[0]:.2f}" y1="{_ML_M[1]:.2f}" x2="{_ML_N[0]:.2f}" y2="{_ML_N[1]:.2f}" stroke="#1f1f1f" stroke-width="1.4"/>
  {tick(_TRI_A, _ML_M)}
  {tick(_ML_M, _TRI_B)}
  {tick(_TRI_B, _ML_N, count=2)}
  {tick(_ML_N, _TRI_C, count=2)}
  {_vertex(_TRI_A)}{_vertex(_TRI_B)}{_vertex(_TRI_C)}{_vertex(_ML_M)}{_vertex(_ML_N)}
  {_label(_TRI_A, 'A', dx=-18, dy=20)}
  {_label(_TRI_B, 'B', dx=-5, dy=-8)}
  {_label(_TRI_C, 'C', dx=8, dy=20)}
  {_label(_ML_M, 'M', dx=-16, dy=2, size=13)}
  {_label(_ML_N, 'N', dx=6, dy=2, size=13)}
</svg>'''


# ──────────────────────────────────────────────────────────────────────────────
# Маленький вспомогательный код, который вставляется в каждый GEN_* —
# округление числа до десятых для строки ответа.
# ──────────────────────────────────────────────────────────────────────────────

_HELPERS = r'''
def _ans(x):
    """Превращает число в строку: целое без ',0', дробное — с запятой."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    rounded = round(x, 1)
    return f"{rounded:.1f}".replace(".", ",")
'''


# ──────────────────────────────────────────────────────────────────────────────
# 12 генераторов. Каждый — самостоятельный Python-код, который будет
# exec'нут внутри ProblemGenerator.execute_generator. Передаём SVG-картинки
# через Template.substitute() — это избегает конфликта f-строк и {…} в SVG.
# ──────────────────────────────────────────────────────────────────────────────


def _build(template_text, **svgs):
    return Template(template_text).safe_substitute(HELPERS=_HELPERS, **svgs)


# ── 01. Углы. Сумма (180° / 90° / внешний) — Типы 1, 2, 4 ─────────────────────

_TMPL_01 = r'''
import random
$HELPERS

SVG_BASIC = """$SVG_BASIC"""
SVG_RIGHT_C = """$SVG_RIGHT_C"""
SVG_EXTERNAL_C = """$SVG_EXTERNAL_C"""

def generate_task():
    subtype = random.choice(["third", "right_other", "external"])
    if subtype == "third":
        while True:
            a = random.randint(15, 150)
            b = random.randint(15, 150)
            c = 180 - a - b
            if 10 <= c <= 160:
                break
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(\\angle A = {a}°\\), "
            f"\\(\\angle B = {b}°\\). Найдите \\(\\angle C\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(c)
        svg = SVG_BASIC
    elif subtype == "right_other":
        a = random.choice([n for n in range(5, 86) if n != 45])
        b = 90 - a
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(\\angle A = {a}°\\). Найдите \\(\\angle B\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(b)
        svg = SVG_RIGHT_C
    else:
        c = random.randint(15, 170)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\({c}°\\). "
            f"Найдите внешний угол при вершине \\(C\\). "
            f"Ответ дайте в градусах."
        )
        answer = str(180 - c)
        svg = SVG_EXTERNAL_C
    return {"condition_text": f"{text}<br><br>{svg}", "correct_answer": answer}
'''

GEN_GROUP_01 = _build(
    _TMPL_01,
    SVG_BASIC=SVG_BASIC,
    SVG_RIGHT_C=SVG_RIGHT_C,
    SVG_EXTERNAL_C=SVG_EXTERNAL_C,
)


# ── 02. Углы. Равнобедренный — Тип 3 ──────────────────────────────────────────

_TMPL_02 = r'''
import random
$HELPERS

SVG_ISOSCELES = """$SVG_ISOSCELES"""

def generate_task():
    # Тип 3: AB = BC, известен угол при вершине B, найти угол при основании.
    # Чтобы базовый угол был целым, апекс берём чётным от 10 до 170.
    apex = random.choice([n for n in range(10, 171) if n % 2 == 0])
    base = (180 - apex) // 2
    text = (
        f"В равнобедренном треугольнике \\(ABC\\) известно, что \\(AB = BC\\), "
        f"\\(\\angle B = {apex}°\\). Найдите \\(\\angle A\\). "
        f"Ответ дайте в градусах."
    )
    return {"condition_text": f"{text}<br><br>{SVG_ISOSCELES}", "correct_answer": str(base)}
'''

GEN_GROUP_02 = _build(_TMPL_02, SVG_ISOSCELES=SVG_ISOSCELES)


# ── 03. Углы через чевиану (простые) — Типы 5, 6 ──────────────────────────────

_TMPL_03 = r'''
import random
$HELPERS

SVG_HEIGHT_BH = """$SVG_HEIGHT_BH"""
SVG_BISECTOR_AD = """$SVG_BISECTOR_AD"""

def generate_task():
    subtype = random.choice(["height", "bisector"])
    if subtype == "height":
        # Тип 5: BH высота, ∠BAC = α → ∠ABH = 90° − α.
        a = random.randint(5, 85)
        text = (
            f"В остроугольном треугольнике \\(ABC\\) проведена высота \\(BH\\), "
            f"\\(\\angle A = {a}°\\). Найдите угол \\(ABH\\). "
            f"Ответ дайте в градусах."
        )
        return {"condition_text": f"{text}<br><br>{SVG_HEIGHT_BH}", "correct_answer": str(90 - a)}
    else:
        # Тип 6: AD биссектриса, ∠BAC = α → ∠BAD = α/2.
        # Чтобы ∠BAD было целым, берём чётный угол.
        a = random.choice([n for n in range(10, 161) if n % 2 == 0])
        text = (
            f"В треугольнике \\(ABC\\) проведена биссектриса \\(AD\\), "
            f"\\(\\angle A = {a}°\\). Найдите угол \\(BAD\\). "
            f"Ответ дайте в градусах."
        )
        return {"condition_text": f"{text}<br><br>{SVG_BISECTOR_AD}", "correct_answer": str(a // 2)}
'''

GEN_GROUP_03 = _build(
    _TMPL_03,
    SVG_HEIGHT_BH=SVG_HEIGHT_BH,
    SVG_BISECTOR_AD=SVG_BISECTOR_AD,
)


# ── 04. Углы через чевиану (многоходовая) — Тип 8 ─────────────────────────────

_TMPL_04 = r'''
import random
$HELPERS

SVG_BISECTOR_AK_EQ = """$SVG_BISECTOR_AK_EQ"""

def generate_task():
    # Тип 8: AK — биссектриса ∠BAC, AK = CK.
    # AK=KC ⇒ △AKC равнобедр. ⇒ ∠KAC = ∠C.
    # AK биссектриса ⇒ ∠BAC = 2·∠KAC = 2·∠C.
    # Сумма углов: ∠B = 180 − 3·∠C.
    # Берём ∠C так, чтобы 3·∠C < 180 и не давал тривиальных значений.
    angC = random.randint(10, 59)
    angB = 180 - 3 * angC
    text = (
        f"В треугольнике \\(ABC\\) проведена биссектриса \\(AK\\), причём "
        f"\\(AK = CK\\), \\(\\angle C = {angC}°\\). "
        f"Найдите угол \\(B\\). Ответ дайте в градусах."
    )
    return {"condition_text": f"{text}<br><br>{SVG_BISECTOR_AK_EQ}", "correct_answer": str(angB)}
'''

GEN_GROUP_04 = _build(_TMPL_04, SVG_BISECTOR_AK_EQ=SVG_BISECTOR_AK_EQ)


# ── 05. Медиана: определение и признак прямого угла — Типы 7, 9 ───────────────

_TMPL_05 = r'''
import random
$HELPERS

SVG_MEDIAN_BM = """$SVG_MEDIAN_BM"""
SVG_MEDIAN_BM_RIGHT = """$SVG_MEDIAN_BM_RIGHT"""

def generate_task():
    subtype = random.choice(["definition", "right_sign"])
    if subtype == "definition":
        # Тип 7: BM медиана, AC задан, AM = AC/2.
        # Берём чётное AC, чтобы AM было целым.
        AC = random.choice([n for n in range(2, 201) if n % 2 == 0])
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(BM\\) — медиана, "
            f"\\(AC = {AC}\\). Найдите \\(AM\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_MEDIAN_BM}", "correct_answer": str(AC // 2)}
    else:
        # Тип 9: BM медиана, BM = AM = MC ⇒ ∠B = 90° ⇒ ∠A = 90° − ∠C.
        angC = random.randint(5, 85)
        text = (
            f"В треугольнике \\(ABC\\) проведена медиана \\(BM\\), причём "
            f"\\(BM = AM = MC\\), \\(\\angle C = {angC}°\\). "
            f"Найдите угол \\(A\\). Ответ дайте в градусах."
        )
        return {"condition_text": f"{text}<br><br>{SVG_MEDIAN_BM_RIGHT}", "correct_answer": str(90 - angC)}
'''

GEN_GROUP_05 = _build(
    _TMPL_05,
    SVG_MEDIAN_BM=SVG_MEDIAN_BM,
    SVG_MEDIAN_BM_RIGHT=SVG_MEDIAN_BM_RIGHT,
)


# ── 06. Теорема Пифагора — Типы 10, 11 ────────────────────────────────────────

_TMPL_06 = r'''
import random
$HELPERS

SVG_RIGHT_C = """$SVG_RIGHT_C"""

PYTH_TRIPLES = [
    (3, 4, 5), (5, 12, 13), (6, 8, 10), (7, 24, 25), (8, 15, 17),
    (9, 12, 15), (9, 40, 41), (10, 24, 26), (12, 16, 20), (12, 35, 37),
    (15, 20, 25), (15, 36, 39), (16, 30, 34), (18, 24, 30), (20, 21, 29),
    (20, 48, 52), (21, 28, 35), (24, 32, 40), (28, 45, 53), (30, 40, 50),
    (33, 44, 55), (36, 48, 60), (40, 42, 58), (45, 60, 75), (48, 55, 73),
    (60, 80, 100),
]

def generate_task():
    a, b, c = sorted(random.choice(PYTH_TRIPLES))   # a < b < c, c — гипотенуза
    direction = random.choice(["forward", "inverse"])
    if direction == "forward":
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AC = {b}\\), \\(BC = {a}\\). Найдите \\(AB\\)."
        )
        answer = str(c)
    else:
        which = random.choice(["hide_BC", "hide_AC"])
        if which == "hide_BC":
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(AC = {b}\\), \\(AB = {c}\\). Найдите \\(BC\\)."
            )
            answer = str(a)
        else:
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {a}\\), \\(AB = {c}\\). Найдите \\(AC\\)."
            )
            answer = str(b)
    return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": answer}
'''

GEN_GROUP_06 = _build(_TMPL_06, SVG_RIGHT_C=SVG_RIGHT_C)


# ── 07. Равносторонний. Сторона → чевиана — Типы 12, 13, 14 ───────────────────

_TMPL_07 = r'''
import random
$HELPERS

SVG_EQ_MEDIAN = """$SVG_EQ_MEDIAN"""
SVG_EQ_HEIGHT = """$SVG_EQ_HEIGHT"""
SVG_EQ_BISECTOR = """$SVG_EQ_BISECTOR"""

def generate_task():
    # Сторона равностороннего равна k·√3 → чевиана = 3k/2.
    # Берём чётное k, чтобы ответ был целым.
    k = random.choice([n for n in range(2, 61) if n % 2 == 0])
    side_text = f"{k}\\sqrt{{3}}"
    answer = str(3 * k // 2)

    element = random.choice(["median", "height", "bisector"])
    if element == "median":
        elem_acc = "медиану"     # винительный падеж — «Найдите медиану …»
        elem_seg = "CM"
        svg = SVG_EQ_MEDIAN
    elif element == "height":
        elem_acc = "высоту"
        elem_seg = "CH"
        svg = SVG_EQ_HEIGHT
    else:
        elem_acc = "биссектрису"
        elem_seg = "CD"
        svg = SVG_EQ_BISECTOR
    text = (
        f"Сторона равностороннего треугольника \\(ABC\\) равна "
        f"\\({side_text}\\). Найдите {elem_acc} \\({elem_seg}\\) "
        f"этого треугольника."
    )
    return {"condition_text": f"{text}<br><br>{svg}", "correct_answer": answer}
'''

GEN_GROUP_07 = _build(
    _TMPL_07,
    SVG_EQ_MEDIAN=SVG_EQ_MEDIAN,
    SVG_EQ_HEIGHT=SVG_EQ_HEIGHT,
    SVG_EQ_BISECTOR=SVG_EQ_BISECTOR,
)


# ── 08. Равносторонний. Чевиана → сторона — Типы 15, 16, 17 ───────────────────

_TMPL_08 = r'''
import random
$HELPERS

SVG_EQ_MEDIAN = """$SVG_EQ_MEDIAN"""
SVG_EQ_HEIGHT = """$SVG_EQ_HEIGHT"""
SVG_EQ_BISECTOR = """$SVG_EQ_BISECTOR"""

def generate_task():
    # Чевиана = k·√3 → сторона = 2k.
    k = random.randint(2, 60)
    h_text = f"{k}\\sqrt{{3}}"
    answer = str(2 * k)

    element = random.choice(["median", "height", "bisector"])
    if element == "median":
        elem_name = "медиана"
        elem_seg = "CM"
        svg = SVG_EQ_MEDIAN
    elif element == "height":
        elem_name = "высота"
        elem_seg = "CH"
        svg = SVG_EQ_HEIGHT
    else:
        elem_name = "биссектриса"
        elem_seg = "CD"
        svg = SVG_EQ_BISECTOR
    text = (
        f"В равностороннем треугольнике \\(ABC\\) проведена {elem_name} "
        f"\\({elem_seg}\\), равная \\({h_text}\\). Найдите сторону этого "
        f"треугольника."
    )
    return {"condition_text": f"{text}<br><br>{svg}", "correct_answer": answer}
'''

GEN_GROUP_08 = _build(
    _TMPL_08,
    SVG_EQ_MEDIAN=SVG_EQ_MEDIAN,
    SVG_EQ_HEIGHT=SVG_EQ_HEIGHT,
    SVG_EQ_BISECTOR=SVG_EQ_BISECTOR,
)


# ── 09. Тригонометрия. Определение (sin/cos/tg) — Типы 18, 19, 20 ─────────────

_TMPL_09 = r'''
import random
from math import gcd
$HELPERS

SVG_RIGHT_C = """$SVG_RIGHT_C"""


def _ratio_str(p, q):
    # Возвращает строку либо "X" либо "X,Y" если деление даёт ≤ 1 знака после запятой.
    if q == 0:
        return None
    if (p * 10) % q != 0:
        return None
    v = round(p / q, 1)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}".replace(".", ",")


def generate_task():
    func = random.choice(["sin", "cos", "tg"])
    for _ in range(400):
        if func == "tg":
            ac = random.randint(1, 60)
            bc = random.randint(1, 60)
            if ac == bc:
                continue
            ans = _ratio_str(ac, bc)
            if ans is None:
                continue
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(BC = {bc}\\), \\(AC = {ac}\\). "
                f"Найдите \\(\\operatorname{{tg}}\\angle B\\)."
            )
            return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": ans}
        else:
            ab = random.randint(2, 100)
            leg = random.randint(1, ab - 1)
            ans = _ratio_str(leg, ab)
            if ans is None:
                continue
            if func == "sin":
                text = (
                    f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                    f"\\(AC = {leg}\\), \\(AB = {ab}\\). Найдите \\(\\sin\\angle B\\)."
                )
            else:
                text = (
                    f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                    f"\\(BC = {leg}\\), \\(AB = {ab}\\). Найдите \\(\\cos\\angle B\\)."
                )
            return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": ans}
    # запасной вариант
    return {"condition_text": f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                              f"\\(AC = 3\\), \\(AB = 5\\). Найдите \\(\\sin\\angle B\\)."
                              f"<br><br>{SVG_RIGHT_C}",
            "correct_answer": "0,6"}
'''

GEN_GROUP_09 = _build(_TMPL_09, SVG_RIGHT_C=SVG_RIGHT_C)


# ── 10. Тригонометрия. Найти сторону (обратные) — Типы 21, 22, 23 ─────────────

_TMPL_10 = r'''
import random
from math import gcd
$HELPERS

SVG_RIGHT_C = """$SVG_RIGHT_C"""


def _ratio_str(p, q):
    if q == 0:
        return None
    if (p * 10) % q != 0:
        return None
    v = round(p / q, 1)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}".replace(".", ",")


def generate_task():
    func = random.choice(["sin", "cos", "tg"])
    for _ in range(400):
        if func == "tg":
            p_raw = random.randint(1, 15)
            q_raw = random.randint(1, 15)
        else:
            q_raw = random.randint(2, 12)
            p_raw = random.randint(1, q_raw - 1)
        g = gcd(p_raw, q_raw)
        p, q = p_raw // g, q_raw // g
        if p == q:
            continue
        step = q // gcd(10, q)
        candidates = [m * step for m in range(1, 21) if 2 <= m * step <= 80]
        if not candidates:
            continue
        K = random.choice(candidates)
        target = _ratio_str(K * p, q)
        if target is None:
            continue
        if func == "sin":
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\sin\\angle B = \\dfrac{{{p}}}{{{q}}}\\), \\(AB = {K}\\). "
                f"Найдите \\(AC\\)."
            )
        elif func == "cos":
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\cos\\angle B = \\dfrac{{{p}}}{{{q}}}\\), \\(AB = {K}\\). "
                f"Найдите \\(BC\\)."
            )
        else:
            text = (
                f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                f"\\(\\operatorname{{tg}}\\angle B = \\dfrac{{{p}}}{{{q}}}\\), "
                f"\\(BC = {K}\\). Найдите \\(AC\\)."
            )
        return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": target}
    return {"condition_text": f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
                              f"\\(\\sin\\angle B = \\dfrac{{3}}{{5}}\\), \\(AB = 25\\). "
                              f"Найдите \\(AC\\).<br><br>{SVG_RIGHT_C}",
            "correct_answer": "15"}
'''

GEN_GROUP_10 = _build(_TMPL_10, SVG_RIGHT_C=SVG_RIGHT_C)


# ── 11. Площадь треугольника — Типы 24, 25, 26 ────────────────────────────────

_TMPL_11 = r'''
import random
$HELPERS

SVG_RIGHT_C = """$SVG_RIGHT_C"""
SVG_AREA_AH = """$SVG_AREA_AH"""
SVG_AREA_SIN = """$SVG_AREA_SIN"""

# Допустимые значения sin (даёт ≤1 знак после запятой при произведении).
SIN_RATIOS = [(3,5),(4,5),(5,13),(12,13),(8,17),(15,17),(24,25),(7,25),
              (20,29),(21,29),(1,2),(1,4),(3,4),(1,5),(2,5),(3,10),(7,10),(9,10)]


def generate_task():
    subtype = random.choice(["legs", "side_height", "two_sides_sin"])
    if subtype == "legs":
        # Тип 24: S = a·b/2 в прямоугольном треугольнике.
        a = random.randint(2, 50)
        b = random.randint(2, 50)
        text = (
            f"В треугольнике \\(ABC\\) угол \\(C\\) равен \\(90°\\), "
            f"\\(AC = {b}\\), \\(BC = {a}\\). Найдите площадь треугольника \\(ABC\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_RIGHT_C}", "correct_answer": _ans(a * b / 2)}
    elif subtype == "side_height":
        # Тип 25: S = a·h/2. Сторона a — это AB, высота h — CH.
        a = random.randint(2, 100)
        h = random.randint(1, 50)
        text = (
            f"В треугольнике \\(ABC\\) сторона \\(AB\\) равна \\({a}\\), "
            f"а высота \\(CH\\), проведённая к этой стороне, равна \\({h}\\). "
            f"Найдите площадь треугольника \\(ABC\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_AREA_AH}", "correct_answer": _ans(a * h / 2)}
    else:
        # Тип 26: S = ½·AB·BC·sin∠B.
        for _ in range(80):
            a = random.randint(3, 50)
            b = random.randint(3, 50)
            p, q = random.choice(SIN_RATIOS)
            num = a * b * p
            den = 2 * q
            if (num * 10) % den != 0:
                continue
            v = round(num / den, 1)
            S_str = (str(int(round(v))) if abs(v - round(v)) < 1e-9
                     else f"{v:.1f}".replace(".", ","))
            text = (
                f"В треугольнике \\(ABC\\) известно, что \\(AB = {a}\\), \\(BC = {b}\\), "
                f"\\(\\sin\\angle ABC = \\dfrac{{{p}}}{{{q}}}\\). "
                f"Найдите площадь треугольника \\(ABC\\)."
            )
            return {"condition_text": f"{text}<br><br>{SVG_AREA_SIN}", "correct_answer": S_str}
        # запасной вариант
        text = (
            f"В треугольнике \\(ABC\\) известно, что \\(AB = 14\\), \\(BC = 5\\), "
            f"\\(\\sin\\angle ABC = \\dfrac{{6}}{{7}}\\). "
            f"Найдите площадь треугольника \\(ABC\\)."
        )
        return {"condition_text": f"{text}<br><br>{SVG_AREA_SIN}", "correct_answer": "30"}
'''

GEN_GROUP_11 = _build(
    _TMPL_11,
    SVG_RIGHT_C=SVG_RIGHT_C,
    SVG_AREA_AH=SVG_AREA_AH,
    SVG_AREA_SIN=SVG_AREA_SIN,
)


# ── 12. Средняя линия треугольника — Тип 27 ───────────────────────────────────

_TMPL_12 = r'''
import random
$HELPERS

SVG_MIDLINE = """$SVG_MIDLINE"""

def generate_task():
    # MN = AC/2. Берём чётное AC.
    AC = random.choice([n for n in range(4, 201) if n % 2 == 0])
    text = (
        f"Точки \\(M\\) и \\(N\\) — середины сторон \\(AB\\) и \\(BC\\) "
        f"треугольника \\(ABC\\). Сторона \\(AC\\) равна \\({AC}\\). "
        f"Найдите \\(MN\\)."
    )
    return {"condition_text": f"{text}<br><br>{SVG_MIDLINE}", "correct_answer": str(AC // 2)}
'''

GEN_GROUP_12 = _build(_TMPL_12, SVG_MIDLINE=SVG_MIDLINE)


# ──────────────────────────────────────────────────────────────────────────────
# PROTOTYPES — список (order, имя генератора в БД, заголовок Assignment, code).
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    (1,  'OGE15: 01 — Углы. Сумма и смежный',                 'Тип 1',  GEN_GROUP_01),
    (2,  'OGE15: 02 — Углы. Равнобедренный',                  'Тип 2',  GEN_GROUP_02),
    (3,  'OGE15: 03 — Углы через чевиану (простые)',          'Тип 3',  GEN_GROUP_03),
    (4,  'OGE15: 04 — Углы через чевиану (многоходовая)',     'Тип 4',  GEN_GROUP_04),
    (5,  'OGE15: 05 — Медиана: определение и признак',        'Тип 5',  GEN_GROUP_05),
    (6,  'OGE15: 06 — Теорема Пифагора',                      'Тип 6',  GEN_GROUP_06),
    (7,  'OGE15: 07 — Равносторонний. Сторона → чевиана',     'Тип 7',  GEN_GROUP_07),
    (8,  'OGE15: 08 — Равносторонний. Чевиана → сторона',     'Тип 8',  GEN_GROUP_08),
    (9,  'OGE15: 09 — Тригонометрия. Определение',            'Тип 9',  GEN_GROUP_09),
    (10, 'OGE15: 10 — Тригонометрия. Найти сторону',          'Тип 10', GEN_GROUP_10),
    (11, 'OGE15: 11 — Площадь треугольника',                  'Тип 11', GEN_GROUP_11),
    (12, 'OGE15: 12 — Средняя линия',                         'Тип 12', GEN_GROUP_12),
]


# ──────────────────────────────────────────────────────────────────────────────
# Management command — почти неизменён по сравнению с прежней версией.
# ──────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Создаёт «Задание 15» (Треугольники, 12 групп со статичными SVG)"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Удалить урок «Задание 15» и его генераторы целиком.')

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            course = Course.objects.get(slug='oge-maths')
        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR('Курс oge-maths не найден'))
            return

        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 15').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 15',
            defaults={'order': 15, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 15:
            lesson.order = 15
            lesson.save(update_fields=['order'])

        # Удалить лишние Assignment-ы, если на уроке остались с прежней
        # 8-групповой раскладки (order >= 9 в новой версии всё ещё валидны:
        # мы расширились до 12, но кто-то мог иметь order >= 13 — выкосим).
        Assignment.objects.filter(lesson=lesson, order__gt=len(PROTOTYPES)).delete()

        existing_by_order = {a.order: a for a in lesson.assignments.all()}

        for order, gen_name, asg_title, code in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                    'config': {},
                },
            )
            assign = existing_by_order.get(order)
            if assign:
                assign.title = asg_title
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'text_input'
                assign.required_correct = 3
                assign.save()
                self.stdout.write(self.style.SUCCESS(f'  · [{order}] обновлён {asg_title}'))
            else:
                Assignment.objects.create(
                    lesson=lesson, order=order, title=asg_title, description='',
                    assignment_type='test', answer_type='text_input',
                    required_correct=3, problem_generator=generator,
                )
                self.stdout.write(self.style.SUCCESS(f'  + [{order}] создан {asg_title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: {len(PROTOTYPES)} прототипов.'
        ))
