# -*- coding: utf-8 -*-
"""
Management command: populate EGE task 1 questions.

Usage:
    python manage.py populate_ege1
    python manage.py populate_ege1 --clear

Lesson order=1 inside module order=1 of course ege-profile-math.
Assignments are added one by one as subtypes are processed.
"""

import math

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ──────────────────────────────────────────────────────────────────────────────
# Helpers для геометрии
# ──────────────────────────────────────────────────────────────────────────────

def _equality_marks(P1, P2, count=1, length=6, gap=3):
    """Засечки равенства: count перпендикулярных штрихов на отрезке P1P2.
    Возвращает SVG-фрагмент."""
    Mx = (P1[0] + P2[0]) / 2
    My = (P1[1] + P2[1]) / 2
    dx = P2[0] - P1[0]
    dy = P2[1] - P1[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return ""
    nx, ny = dy / L, -dx / L     # перпендикуляр (по часовой)
    ux, uy = dx / L, dy / L      # вдоль отрезка
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
    return "\n  ".join(parts)


def _right_angle_marker(vertex, P1, P2, size=8):
    """Маркер прямого угла в vertex (квадратик повёрнутый по сторонам угла).
    P1, P2 — соседние точки."""
    vx, vy = vertex
    d1x = P1[0] - vx
    d1y = P1[1] - vy
    d2x = P2[0] - vx
    d2y = P2[1] - vy
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
        f'<polyline points="{a[0]:.1f},{a[1]:.1f} {b[0]:.1f},{b[1]:.1f} {c[0]:.1f},{c[1]:.1f}" '
        f'fill="none" stroke="#1f1f1f" stroke-width="1"/>'
    )


# ── Прототип 1: Высота треугольника и параллелограмма ────────────────────────
# Принцип: S = a·h_a = b·h_b  →  h_b = a·h_a / b

_SVG_VYSOTA_TRE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Треугольник ABC с высотой CH">
  <line x1="40" y1="180" x2="280" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="40" y1="180" x2="200" y2="50" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="280" y1="180" x2="200" y2="50" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="200" y1="180" x2="200" y2="50" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="4,3"/>
  <rect x="190" y="170" width="10" height="10" fill="none" stroke="#1f1f1f" stroke-width="1"/>
  <circle cx="40" cy="180" r="2.5" fill="#1f1f1f"/>
  <circle cx="280" cy="180" r="2.5" fill="#1f1f1f"/>
  <circle cx="200" cy="50" r="2.5" fill="#1f1f1f"/>
  <circle cx="200" cy="180" r="2.5" fill="#1f1f1f"/>
  <text x="28" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="285" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="195" y="42" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="195" y="197" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">H</text>
  <text x="208" y="120" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">h</text>
</svg>"""

_SVG_VYSOTA_PARAL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Параллелограмм ABCD с двумя высотами">
  <line x1="50" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="220" y1="180" x2="280" y2="60" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="280" y1="60" x2="110" y2="60" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="110" y1="60" x2="50" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="110" y1="60" x2="110" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="4,3"/>
  <rect x="100" y="170" width="10" height="10" fill="none" stroke="#1f1f1f" stroke-width="1"/>
  <line x1="220" y1="180" x2="84" y2="112" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="4,3"/>
  <polyline points="80,121 88,125 93,116" fill="none" stroke="#1f1f1f" stroke-width="1"/>
  <circle cx="50" cy="180" r="2.5" fill="#1f1f1f"/>
  <circle cx="220" cy="180" r="2.5" fill="#1f1f1f"/>
  <circle cx="280" cy="60" r="2.5" fill="#1f1f1f"/>
  <circle cx="110" cy="60" r="2.5" fill="#1f1f1f"/>
  <text x="38" y="197" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="222" y="197" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="285" y="56" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="96" y="56" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">D</text>
  <text x="115" y="125" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">h</text>
  <text x="120" y="129" font-family="Cambria, Georgia, serif" font-size="9" fill="#1f1f1f">1</text>
  <text x="155" y="158" font-family="Cambria, Georgia, serif" font-style="italic" font-size="13" fill="#1f1f1f">h</text>
  <text x="160" y="162" font-family="Cambria, Georgia, serif" font-size="9" fill="#1f1f1f">2</text>
</svg>"""

TYPE_VYSOTA = [
    (
        r"Две стороны треугольника равны 21 и 28. "
        r"Высота, опущенная на бо́льшую из этих сторон, равна 15. "
        r"Найдите высоту, опущенную на меньшую из этих сторон треугольника.",
        "20",
        _SVG_VYSOTA_TRE,
    ),
    (
        r"Стороны параллелограмма равны 24 и 27. "
        r"Высота, опущенная на меньшую из этих сторон, равна 18. "
        r"Найдите высоту, опущенную на бо́льшую сторону параллелограмма.",
        "16",
        _SVG_VYSOTA_PARAL,
    ),
]


# ── Прототип 2: Касательная и секущая через центр ────────────────────────────
# CA касается окружности в A (OA ⊥ CA), CO пересекает окружность в B.
# В треугольнике OAC: ∠OAC = 90°, ∠ACO + ∠AOC = 90°.
# Дуга AB = центральный угол ∠AOC = 90° − ∠ACO.
# Каждый SVG нарисован с реальным углом ACO в задаче.

def _svg_dug_template(theta_deg, viewbox_w=320):
    """Параметрический SVG для угла ACO=theta_deg.
    Окружность R=60 с O=(130,135), A=(130,75) (наверху).
    C справа от A на касательной, длина CA = R/tan(theta).
    """
    import math
    R = 60
    Ox, Oy = 130, 135
    Ax, Ay = Ox, Oy - R  # A над O на R
    theta = math.radians(theta_deg)
    Cx = Ax + R / math.tan(theta)
    Cy = Ay
    # B на отрезке CO, ближайший к C на окружности
    sin_t = math.sin(theta)
    Bx = Cx + (Ox - Cx) * (1 - sin_t)
    By = Cy + (Oy - Cy) * (1 - sin_t)
    # маркер прямого угла в A (CA горизонтальна, OA вертикальна)
    return Ox, Oy, Ax, Ay, Cx, Cy, Bx, By

# Координаты для 4 углов:
#   ACO=57°: C(168.96, 75), B(162.71, 84.68)
#   ACO=62°: C(161.90, 75), B(158.20, 82.03)
#   ACO=24°: C(264.78, 75), B(184.90, 110.60)
#   ACO=73°: C(148.34, 75), B(147.54, 77.62)

def _svg_duga(theta_deg):
    """SVG: окружность с центром O=(130,135), R=60, A на верху (130,75),
    касательная CA горизонтальна, секущая CO пересекает окружность в B.
    ∠ACO = theta_deg точно (по построению). Радиус OA нарисован."""
    R = 60
    Ox, Oy = 130, 135
    Ax, Ay = Ox, Oy - R
    theta = math.radians(theta_deg)
    Cx = Ax + R / math.tan(theta)
    Cy = Ay
    sin_t = math.sin(theta)
    Bx = Cx + (Ox - Cx) * (1 - sin_t)
    By = Cy + (Oy - Cy) * (1 - sin_t)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Касательная CA и секущая CO, угол ACO {theta_deg}°">
  <circle cx="{Ox}" cy="{Oy}" r="{R}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Cx:.1f}" y1="{Cy}" x2="{Ox}" y2="{Oy}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Cx:.1f}" y1="{Cy}" x2="{Ax}" y2="{Ay}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Ox}" y1="{Oy}" x2="{Ax}" y2="{Ay}" stroke="#1f1f1f" stroke-width="1.2"/>
  <circle cx="{Ox}" cy="{Oy}" r="2" fill="#1f1f1f"/>
  <circle cx="{Ax}" cy="{Ay}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Cx:.1f}" cy="{Cy}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Bx:.1f}" cy="{By:.1f}" r="2.5" fill="#1f1f1f"/>
  <text x="{Ox-15}" y="{Oy+5}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">O</text>
  <text x="{Cx+5:.1f}" y="{Cy-5}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="{Ax-15}" y="{Ay-3}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="{Bx+5:.1f}" y="{By+5:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
</svg>"""

_SVG_DUGA_57 = _svg_duga(57)
_SVG_DUGA_62 = _svg_duga(62)
_SVG_DUGA_24 = _svg_duga(24)
_SVG_DUGA_73 = _svg_duga(73)

TYPE_DUGA = [
    (
        r"Угол \(ACO\) равен \(57°\). Его сторона \(CA\) касается окружности "
        r"с центром в точке \(O\). Отрезок \(CO\) пересекает окружность в точке \(B\). "
        r"Найдите градусную меру дуги \(AB\) окружности, заключённой внутри этого угла. "
        r"Ответ дайте в градусах.",
        "33",
        _SVG_DUGA_57,
    ),
    (
        r"Угол \(ACO\) равен \(62°\). Его сторона \(CA\) касается окружности "
        r"с центром в точке \(O\). Отрезок \(CO\) пересекает окружность в точке \(B\). "
        r"Найдите градусную меру дуги \(AB\) окружности, заключённой внутри этого угла. "
        r"Ответ дайте в градусах.",
        "28",
        _SVG_DUGA_62,
    ),
    (
        r"Найдите величину угла \(ACO\), если его сторона \(CA\) касается окружности "
        r"с центром в точке \(O\), отрезок \(CO\) пересекает окружность в точке \(B\) "
        r"(см. рисунок), а дуга \(AB\) окружности, заключённая внутри этого угла, "
        r"равна \(66°\). Ответ дайте в градусах.",
        "24",
        _SVG_DUGA_24,
    ),
    (
        r"Найдите величину угла \(ACO\), если его сторона \(CA\) касается окружности "
        r"с центром в точке \(O\), отрезок \(CO\) пересекает окружность в точке \(B\) "
        r"(см. рисунок), а дуга \(AB\) окружности, заключённая внутри этого угла, "
        r"равна \(17°\). Ответ дайте в градусах.",
        "73",
        _SVG_DUGA_73,
    ),
]


# ── Прототип 3: Периметр четырёхугольника с вписанной окружностью ────────────
# Свойство: для описанного 4-угольника AB + CD = BC + DA → P = 2(AB + CD)
# 4-угольник строится через 4 касательные к окружности — соседние касательные
# пересекаются в вершинах.

def _svg_inscribed_4ug(angles_deg, R=50):
    """Возвращает SVG-строку: окружность с центром (160,110), радиуса R,
    вписана в 4-угольник через касательные в точках с заданными углами."""
    import math
    Ox, Oy = 160, 110
    Ts = [(Ox + R * math.cos(math.radians(a)),
           Oy - R * math.sin(math.radians(a))) for a in angles_deg]

    def intersect(T1, T2):
        # Касательная в T = (Tx, Ty) перпендикулярна радиусу OT.
        # Её нормаль = (Tx-Ox, Ty-Oy), уравнение n·(P-T) = 0.
        T1x, T1y = T1; T2x, T2y = T2
        n1x, n1y = T1x - Ox, T1y - Oy
        n2x, n2y = T2x - Ox, T2y - Oy
        c1 = n1x * T1x + n1y * T1y
        c2 = n2x * T2x + n2y * T2y
        det = n1x * n2y - n1y * n2x
        if abs(det) < 1e-9:
            return None
        x = (c1 * n2y - c2 * n1y) / det
        y = (n1x * c2 - n2x * c1) / det
        return (x, y)

    A = intersect(Ts[0], Ts[3])
    B = intersect(Ts[0], Ts[1])
    C = intersect(Ts[1], Ts[2])
    D = intersect(Ts[2], Ts[3])
    Ax, Ay = A; Bx, By = B; Cx, Cy = C; Dx, Dy = D

    def lbl(P):
        Px, Py = P
        vx, vy = Px - Ox, Py - Oy
        L = math.hypot(vx, vy)
        return (Px + vx / L * 14 - 5, Py + vy / L * 14 + 5)

    LA = lbl(A); LB = lbl(B); LC = lbl(C); LD = lbl(D)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Четырёхугольник ABCD с вписанной окружностью">
  <circle cx="{Ox}" cy="{Oy}" r="{R}" fill="none" stroke="#1f1f1f" stroke-width="1.3"/>
  <line x1="{Ax:.1f}" y1="{Ay:.1f}" x2="{Bx:.1f}" y2="{By:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Bx:.1f}" y1="{By:.1f}" x2="{Cx:.1f}" y2="{Cy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Cx:.1f}" y1="{Cy:.1f}" x2="{Dx:.1f}" y2="{Dy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Dx:.1f}" y1="{Dy:.1f}" x2="{Ax:.1f}" y2="{Ay:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="{Ax:.1f}" cy="{Ay:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Bx:.1f}" cy="{By:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Cx:.1f}" cy="{Cy:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Dx:.1f}" cy="{Dy:.1f}" r="2.5" fill="#1f1f1f"/>
  <text x="{LA[0]:.1f}" y="{LA[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="{LB[0]:.1f}" y="{LB[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="{LC[0]:.1f}" y="{LC[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="{LD[0]:.1f}" y="{LD[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">D</text>
</svg>"""

# Два разных 4-угольника для двух задач (разные углы касания → разная форма)
_SVG_VPISAN_4UG_1 = _svg_inscribed_4ug([260, 20, 110, 200])
_SVG_VPISAN_4UG_2 = _svg_inscribed_4ug([285, 355, 100, 215])

TYPE_PERIMETR = [
    (
        r"В четырёхугольник \(ABCD\) вписана окружность. "
        r"\(AB = 10\), \(CD = 17\). "
        r"Найдите периметр четырёхугольника \(ABCD\).",
        "54",
        _SVG_VPISAN_4UG_1,
    ),
    (
        r"В четырёхугольник \(ABCD\) вписана окружность. "
        r"\(AB = 12\), \(CD = 19\). "
        r"Найдите периметр четырёхугольника \(ABCD\).",
        "62",
        _SVG_VPISAN_4UG_2,
    ),
]


# ── Прототип 4: Радиус описанной окружности треугольника ─────────────────────
# Теорема синусов: AB / sin C = 2R  →  R = AB / (2·sin C).
# Чтобы вписанный угол ACB = θ (тупой) был на чертеже именно θ°,
# A и B ставятся симметрично относительно вертикали через O на углах 270°±(180°-θ),
# а C — на дуге, содержащей вершину угла, под углом 270°.

def _svg_opisan_okr(angle_deg, R=80, c_offset_deg=0):
    """SVG: окружность R с центром (160,110), вписанный треугольник ABC,
    ∠ACB = angle_deg. c_offset_deg сдвигает C по дуге, делая треугольник
    разносторонним (по умолчанию равнобедренный)."""
    Ox, Oy = 160, 110
    half = 180 - angle_deg  # половина дуги, на которой лежит C
    a_A = 270 - half
    a_B = 270 + half
    a_C = 270 + c_offset_deg
    def pt(deg):
        a = math.radians(deg)
        return (Ox + R * math.cos(a), Oy - R * math.sin(a))
    A = pt(a_A); B = pt(a_B); C = pt(a_C)
    Ax, Ay = A; Bx, By = B; Cx, Cy = C

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с описанной окружностью, угол C = {angle_deg}°">
  <circle cx="{Ox}" cy="{Oy}" r="{R}" fill="none" stroke="#1f1f1f" stroke-width="1.3"/>
  <line x1="{Ax:.1f}" y1="{Ay:.1f}" x2="{Bx:.1f}" y2="{By:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Ax:.1f}" y1="{Ay:.1f}" x2="{Cx:.1f}" y2="{Cy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Bx:.1f}" y1="{By:.1f}" x2="{Cx:.1f}" y2="{Cy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="{Ax:.1f}" cy="{Ay:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Bx:.1f}" cy="{By:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Cx:.1f}" cy="{Cy:.1f}" r="2.5" fill="#1f1f1f"/>
  <text x="{Ax-15:.1f}" y="{Ay+5:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="{Bx+6:.1f}" y="{By+5:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="{Cx-5:.1f}" y="{Cy+18:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""

_SVG_OPIS_135 = _svg_opisan_okr(135, c_offset_deg=22)
_SVG_OPIS_120 = _svg_opisan_okr(120, c_offset_deg=-25)

TYPE_RADIUS_TRE = [
    (
        r"В треугольнике \(ABC\) сторона \(AB = 3\sqrt{2}\), угол \(C\) равен \(135°\). "
        r"Найдите радиус описанной около этого треугольника окружности.",
        "3",
        _SVG_OPIS_135,
    ),
    (
        r"В треугольнике \(ABC\) сторона \(AB = 2\sqrt{3}\), угол \(C\) равен \(120°\). "
        r"Найдите радиус описанной около этого треугольника окружности.",
        "2",
        _SVG_OPIS_120,
    ),
]



# ── Прототип 5: Площадь части параллелограмма ────────────────────────────────
# E — середина AD: S_ABE = S/4, S_BCDE = 3S/4

def _svg_paral_e_mid(A, B, C, D, label_offsets=None):
    """Параллелограмм ABCD, E — середина AD, отрезок BE.
    Засечки равенства AE=ED перпендикулярны AD."""
    Ex = (A[0] + D[0]) / 2
    Ey = (A[1] + D[1]) / 2
    marks_AE = _equality_marks(A, (Ex, Ey))
    marks_ED = _equality_marks((Ex, Ey), D)
    if label_offsets is None:
        label_offsets = {"A": (-12, 17), "B": (4, 17), "C": (4, -2), "D": (-12, -2), "E": (-15, 5)}
    def lp(P, ch):
        ox, oy = label_offsets[ch]
        return f'<text x="{P[0] + ox:.1f}" y="{P[1] + oy:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">{ch}</text>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Параллелограмм ABCD, E — середина AD">
  <line x1="{A[0]}" y1="{A[1]}" x2="{B[0]}" y2="{B[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{B[0]}" y1="{B[1]}" x2="{C[0]}" y2="{C[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{C[0]}" y1="{C[1]}" x2="{D[0]}" y2="{D[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{D[0]}" y1="{D[1]}" x2="{A[0]}" y2="{A[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{B[0]}" y1="{B[1]}" x2="{Ex:.1f}" y2="{Ey:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  {marks_AE}
  {marks_ED}
  <circle cx="{A[0]}" cy="{A[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{B[0]}" cy="{B[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{C[0]}" cy="{C[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{D[0]}" cy="{D[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Ex:.1f}" cy="{Ey:.1f}" r="2.5" fill="#1f1f1f"/>
  {lp(A, "A")}
  {lp(B, "B")}
  {lp(C, "C")}
  {lp(D, "D")}
  {lp((Ex, Ey), "E")}
</svg>"""

# Две разные конфигурации параллелограмма
_SVG_PARAL_E_1 = _svg_paral_e_mid(
    A=(55, 180), B=(225, 180), C=(285, 60), D=(115, 60),
)
_SVG_PARAL_E_2 = _svg_paral_e_mid(
    A=(40, 180), B=(220, 180), C=(290, 80), D=(110, 80),
)

TYPE_PLOSCHAD_PARAL = [
    (
        r"Площадь параллелограмма \(ABCD\) равна 28. Точка \(E\) — середина стороны \(AD\). "
        r"Найдите площадь трапеции \(BCDE\).",
        "21",
        _SVG_PARAL_E_1,
    ),
    (
        r"Площадь параллелограмма \(ABCD\) равна 60. Точка \(E\) — середина стороны \(AD\). "
        r"Найдите площадь треугольника \(ABE\).",
        "15",
        _SVG_PARAL_E_2,
    ),
]


# ── Прототип 6: Площадь части треугольника (средняя линия) ───────────────────
# DE ∥ AB, D и E — середины AC и BC: S_CDE = S/4, S_ABED = 3S/4

def _svg_srednyaya(A, B, C, label_offsets=None):
    """Треугольник ABC, средняя линия DE: D — середина AC, E — середина BC.
    Засечки AD=DC, BE=EC перпендикулярны соответствующим сторонам."""
    D = ((A[0] + C[0]) / 2, (A[1] + C[1]) / 2)
    E = ((B[0] + C[0]) / 2, (B[1] + C[1]) / 2)
    marks_AD = _equality_marks(A, D)
    marks_DC = _equality_marks(D, C)
    marks_BE = _equality_marks(B, E, count=2)
    marks_EC = _equality_marks(E, C, count=2)
    if label_offsets is None:
        label_offsets = {"A": (-15, 17), "B": (5, 17), "C": (-5, -5), "D": (-16, 5), "E": (6, 5)}
    def lp(P, ch):
        ox, oy = label_offsets[ch]
        return f'<text x="{P[0] + ox:.1f}" y="{P[1] + oy:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">{ch}</text>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC со средней линией DE">
  <line x1="{A[0]}" y1="{A[1]}" x2="{B[0]}" y2="{B[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{A[0]}" y1="{A[1]}" x2="{C[0]}" y2="{C[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{B[0]}" y1="{B[1]}" x2="{C[0]}" y2="{C[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{D[0]:.1f}" y1="{D[1]:.1f}" x2="{E[0]:.1f}" y2="{E[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  {marks_AD}
  {marks_DC}
  {marks_BE}
  {marks_EC}
  <circle cx="{A[0]}" cy="{A[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{B[0]}" cy="{B[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{C[0]}" cy="{C[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{D[0]:.1f}" cy="{D[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{E[0]:.1f}" cy="{E[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  {lp(A, "A")}
  {lp(B, "B")}
  {lp(C, "C")}
  {lp(D, "D")}
  {lp(E, "E")}
</svg>"""

_SVG_SREDN_1 = _svg_srednyaya(A=(50, 190), B=(270, 190), C=(180, 30))
_SVG_SREDN_2 = _svg_srednyaya(A=(45, 195), B=(265, 195), C=(120, 40))

TYPE_PLOSCHAD_TRE = [
    (
        r"Площадь треугольника \(ABC\) равна 24. \(DE\) — средняя линия, "
        r"параллельная стороне \(AB\). Найдите площадь трапеции \(ABED\).",
        "18",
        _SVG_SREDN_1,
    ),
    (
        r"Площадь треугольника \(ABC\) равна 24. \(DE\) — средняя линия, "
        r"параллельная стороне \(AB\). Найдите площадь треугольника \(CDE\).",
        "6",
        _SVG_SREDN_2,
    ),
]


# ── Прототип 7: Синус и косинус в прямоугольном треугольнике ─────────────────
# ∠C = 90°, AB — гипотенуза. cos A = AC/AB, sin A = BC/AB.
# Для каждой задачи — свой треугольник с реальными пропорциями катетов.

def _svg_pryam_tre(AC, BC, target_AB_px=200):
    """Прямоугольный треугольник с катетами AC и BC (значения из условия).
    A слева внизу, B справа внизу (AB горизонтальная), C над AB."""
    AB = math.sqrt(AC ** 2 + BC ** 2)
    scale = target_AB_px / AB
    Ax, Ay = 50, 180
    Bx, By = Ax + scale * AB, Ay
    Cx = (Ax + Bx) / 2 + scale * (AC ** 2 - BC ** 2) / (2 * AB)
    Cy = Ay - math.sqrt(max(0, (scale * AC) ** 2 - (Cx - Ax) ** 2))
    A = (Ax, Ay); B = (Bx, By); C = (Cx, Cy)
    rmark = _right_angle_marker(C, A, B, size=10)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Прямоугольный треугольник ABC, угол C = 90°">
  <line x1="{Ax}" y1="{Ay}" x2="{Bx:.1f}" y2="{By}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Ax}" y1="{Ay}" x2="{Cx:.1f}" y2="{Cy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Bx:.1f}" y1="{By}" x2="{Cx:.1f}" y2="{Cy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  {rmark}
  <circle cx="{Ax}" cy="{Ay}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Bx:.1f}" cy="{By}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{Cx:.1f}" cy="{Cy:.1f}" r="2.5" fill="#1f1f1f"/>
  <text x="{Ax-15:.1f}" y="{Ay+15:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="{Bx+5:.1f}" y="{By+15:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="{Cx-5:.1f}" y="{Cy-7:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
</svg>"""

# Для каждой задачи свои катеты: AC²+BC²=AB². AB=10 → катеты подобраны под условие.
_SVG_SINCOS_1 = _svg_pryam_tre(AC=9, BC=math.sqrt(19))     # cos A = 9/10 = 0.9
_SVG_SINCOS_2 = _svg_pryam_tre(AC=math.sqrt(51), BC=7)     # sin A = 7/10 = 0.7
_SVG_SINCOS_3 = _svg_pryam_tre(AC=math.sqrt(91), BC=3)     # sin A = 3/10 = 0.3
_SVG_SINCOS_4 = _svg_pryam_tre(AC=3, BC=4)                  # cos A = 3/5 = 0.6

TYPE_SIN_COS = [
    (
        r"В треугольнике \(ABC\) угол \(C\) равен \(90°\), \(AB = 10\), \(BC = \sqrt{19}\). "
        r"Найдите \(\cos A\).",
        "0.9",
        _SVG_SINCOS_1,
    ),
    (
        r"В треугольнике \(ABC\) угол \(C\) равен \(90°\), \(AB = 10\), \(AC = \sqrt{51}\). "
        r"Найдите \(\sin A\).",
        "0.7",
        _SVG_SINCOS_2,
    ),
    (
        r"В треугольнике \(ABC\) угол \(C\) равен \(90°\), \(AB = 10\), \(AC = \sqrt{91}\). "
        r"Найдите \(\sin A\).",
        "0.3",
        _SVG_SINCOS_3,
    ),
    (
        r"В треугольнике \(ABC\) угол \(C\) равен \(90°\), \(AB = 5\), \(BC = 4\). "
        r"Найдите \(\cos A\).",
        "0.6",
        _SVG_SINCOS_4,
    ),
]


# ── Прототип 8: Два диаметра — вписанный и центральный угол ──────────────────
# AC и BD — диаметры, ∠ACB опирается на хорду AB.
# Треугольник OCB равнобедренный (OC=OB=R), поэтому ∠BOC = 180°−2·∠OCB = 180°−2·∠ACB.
# ∠AOD = ∠BOC (вертикальные), значит ∠AOD = 180°−2·∠ACB.

_SVG_DIAMETRY_VPISAN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Окружность с двумя диаметрами AC и BD">
  <circle cx="160" cy="110" r="85" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="75" y1="110" x2="245" y2="110" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="138" y1="28" x2="182" y2="192" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="138" y1="28" x2="245" y2="110" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="160" cy="110" r="2" fill="#1f1f1f"/>
  <circle cx="138" cy="28" r="2.5" fill="#1f1f1f"/>
  <circle cx="182" cy="192" r="2.5" fill="#1f1f1f"/>
  <circle cx="75" cy="110" r="2.5" fill="#1f1f1f"/>
  <circle cx="245" cy="110" r="2.5" fill="#1f1f1f"/>
  <text x="166" y="124" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">O</text>
  <text x="128" y="22" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="187" y="208" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="58" y="115" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">D</text>
  <text x="252" y="115" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
</svg>"""

_SVG_DIAMETRY_TSENTRAL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Окружность с двумя диаметрами AC и BD под малым углом">
  <circle cx="160" cy="110" r="85" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="75" y1="110" x2="245" y2="110" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="86" y1="153" x2="234" y2="67" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="234" y1="67" x2="245" y2="110" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="160" cy="110" r="2" fill="#1f1f1f"/>
  <circle cx="234" cy="67" r="2.5" fill="#1f1f1f"/>
  <circle cx="86" cy="153" r="2.5" fill="#1f1f1f"/>
  <circle cx="75" cy="110" r="2.5" fill="#1f1f1f"/>
  <circle cx="245" cy="110" r="2.5" fill="#1f1f1f"/>
  <text x="148" y="102" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">O</text>
  <text x="225" y="60" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="78" y="170" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="58" y="115" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">D</text>
  <text x="252" y="115" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
</svg>"""

TYPE_NAJTI_UGOL_DIAMETERS = [
    (
        r"Отрезки \(AC\) и \(BD\) — диаметры окружности с центром \(O\). "
        r"Угол \(ACB\) равен \(41°\). Найдите величину угла \(AOD\). "
        r"Ответ дайте в градусах.",
        "98",
        _SVG_DIAMETRY_VPISAN,
    ),
    (
        r"Отрезки \(AC\) и \(BD\) — диаметры окружности с центром \(O\). "
        r"Угол \(AOD\) равен \(16°\). Найдите вписанный угол \(ACB\). "
        r"Ответ дайте в градусах.",
        "82",
        _SVG_DIAMETRY_TSENTRAL,
    ),
]


# ── Прототип 9: Вписанный четырёхугольник с диагоналями ──────────────────────
# Вписанные углы, опирающиеся на одну дугу, равны: ∠CAD = ∠CBD (на дугу CD).
# Через это можно выразить ∠ABD = ∠ABC − ∠CBD = ∠ABC − ∠CAD.

def _svg_vpisan_4ug(angle_A_deg, R=80, with_diagonals=False, rotate=0):
    """Вписанный в окружность 4-угольник ABCD. ∠A = angle_A_deg.
    A на угле (90°+rotate), B/D симметрично от A на дугу (360°-2∠A)/2,
    C напротив. По часовой обход ABCD."""
    arc_BAD = 360 - 2 * angle_A_deg
    half = arc_BAD / 2
    Ox, Oy = 160, 110
    def pt(deg):
        a = math.radians(deg)
        return (Ox + R * math.cos(a), Oy - R * math.sin(a))
    A = pt(90 + rotate)
    B = pt(90 + rotate - half)
    C = pt(270 + rotate)
    D = pt(90 + rotate + half)

    diag = ""
    if with_diagonals:
        diag = (
            f'<line x1="{A[0]:.1f}" y1="{A[1]:.1f}" x2="{C[0]:.1f}" y2="{C[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>\n  '
            f'<line x1="{B[0]:.1f}" y1="{B[1]:.1f}" x2="{D[0]:.1f}" y2="{D[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>'
        )

    def lbl(P, ch):
        vx, vy = P[0] - Ox, P[1] - Oy
        L = math.hypot(vx, vy) or 1
        return (P[0] + vx / L * 14 - 5, P[1] + vy / L * 14 + 5, ch)
    LA = lbl(A, "A"); LB = lbl(B, "B"); LC = lbl(C, "C"); LD = lbl(D, "D")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Вписанный 4-угольник ABCD, угол A = {angle_A_deg}°">
  <circle cx="{Ox}" cy="{Oy}" r="{R}" fill="none" stroke="#1f1f1f" stroke-width="1.3"/>
  <line x1="{A[0]:.1f}" y1="{A[1]:.1f}" x2="{B[0]:.1f}" y2="{B[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{B[0]:.1f}" y1="{B[1]:.1f}" x2="{C[0]:.1f}" y2="{C[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{C[0]:.1f}" y1="{C[1]:.1f}" x2="{D[0]:.1f}" y2="{D[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{D[0]:.1f}" y1="{D[1]:.1f}" x2="{A[0]:.1f}" y2="{A[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  {diag}
  <circle cx="{A[0]:.1f}" cy="{A[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{B[0]:.1f}" cy="{B[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{C[0]:.1f}" cy="{C[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{D[0]:.1f}" cy="{D[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <text x="{LA[0]:.1f}" y="{LA[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="{LB[0]:.1f}" y="{LB[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="{LC[0]:.1f}" y="{LC[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="{LD[0]:.1f}" y="{LD[1]:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">D</text>
</svg>"""

# Прототип 9: с диагоналями. Каждой задаче — свой 4-угольник (разный ∠A).
_SVG_4UG_DIAG_1 = _svg_vpisan_4ug(angle_A_deg=72, with_diagonals=True, rotate=10)
_SVG_4UG_DIAG_2 = _svg_vpisan_4ug(angle_A_deg=98, with_diagonals=True, rotate=-15)

TYPE_VPISAN_4UG_DIAG = [
    (
        r"Четырёхугольник \(ABCD\) вписан в окружность. "
        r"Угол \(ABC\) равен \(103°\), угол \(CAD\) равен \(42°\). "
        r"Найдите угол \(ABD\). Ответ дайте в градусах.",
        "61",
        _SVG_4UG_DIAG_1,
    ),
    (
        r"Четырёхугольник \(ABCD\) вписан в окружность. "
        r"Угол \(ABC\) равен \(120°\), угол \(ABD\) равен \(43°\). "
        r"Найдите угол \(CAD\). Ответ дайте в градусах.",
        "77",
        _SVG_4UG_DIAG_2,
    ),
]


# ── Прототип 10: Вписанный четырёхугольник — противоположные углы ────────────
# Сумма противоположных углов вписанного 4-угольника: ∠A + ∠C = 180°, ∠B + ∠D = 180°.

# Прототип 10: вписанный 4-угольник (без диагоналей).
# 10.1: ∠BAD=136° (тупой) — рисунок ДОЛЖЕН отражать тупой угол при A.
# 10.2: два угла 59° и 102° — другой 4-угольник для разнообразия.
_SVG_4UG_PROT_1 = _svg_vpisan_4ug(angle_A_deg=136)
_SVG_4UG_PROT_2 = _svg_vpisan_4ug(angle_A_deg=102, rotate=20)

TYPE_VPISAN_4UG_PROTIV = [
    (
        r"Четырёхугольник \(ABCD\) вписан в окружность. Угол \(BAD\) равен \(136°\). "
        r"Найдите угол \(BCD\). Ответ дайте в градусах.",
        "44",
        _SVG_4UG_PROT_1,
    ),
    (
        r"Два угла вписанного в окружность четырёхугольника равны \(59°\) и \(102°\). "
        r"Найдите больший из оставшихся углов. Ответ дайте в градусах.",
        "121",
        _SVG_4UG_PROT_2,
    ),
]


# ── Прототип 11: Центральный и вписанный угол на одну дугу ───────────────────
# Центральный угол вдвое больше вписанного, опирающегося на ту же дугу:
# central = 2·inscribed. Если central − inscribed = d, то inscribed = d, central = 2d.

def _svg_centralnyj_vpisannyj(inscribed_deg, R=80):
    """Окружность с центром O, хорда AB, центральный ∠AOB и вписанный ∠ACB.
    inscribed_deg = ∠ACB. Тогда центральный ∠AOB = 2·inscribed_deg.
    A и B симметрично снизу, C сверху."""
    Ox, Oy = 160, 115
    a_A = 270 - inscribed_deg
    a_B = 270 + inscribed_deg
    a_C = 90
    def pt(deg):
        a = math.radians(deg)
        return (Ox + R * math.cos(a), Oy - R * math.sin(a))
    A = pt(a_A); B = pt(a_B); C = pt(a_C)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Центральный и вписанный угол на одну дугу, вписанный {inscribed_deg}°">
  <circle cx="{Ox}" cy="{Oy}" r="{R}" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{C[0]:.1f}" y1="{C[1]:.1f}" x2="{A[0]:.1f}" y2="{A[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{C[0]:.1f}" y1="{C[1]:.1f}" x2="{B[0]:.1f}" y2="{B[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Ox}" y1="{Oy}" x2="{A[0]:.1f}" y2="{A[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{Ox}" y1="{Oy}" x2="{B[0]:.1f}" y2="{B[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="{Ox}" cy="{Oy}" r="2" fill="#1f1f1f"/>
  <circle cx="{C[0]:.1f}" cy="{C[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{A[0]:.1f}" cy="{A[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{B[0]:.1f}" cy="{B[1]:.1f}" r="2.5" fill="#1f1f1f"/>
</svg>"""

# Реальные углы в задачах:
#  11.1: центральный = 56° → вписанный = 28°
#  11.2: центральный = 64° → вписанный = 32°
_SVG_CENTR_1 = _svg_centralnyj_vpisannyj(inscribed_deg=28)
_SVG_CENTR_2 = _svg_centralnyj_vpisannyj(inscribed_deg=32)

TYPE_TSENTR_VPISAN = [
    (
        r"Найдите центральный угол, если он на \(28°\) больше острого вписанного угла, "
        r"опирающегося на ту же дугу. Ответ дайте в градусах.",
        "56",
        _SVG_CENTR_1,
    ),
    (
        r"Центральный угол на \(32°\) больше острого вписанного угла, опирающегося "
        r"на ту же дугу окружности. Найдите вписанный угол. Ответ дайте в градусах.",
        "32",
        _SVG_CENTR_2,
    ),
]


# ── Прототип 12: Прямоугольный треугольник, линии из вершины прямого угла ────
# Свойства из вершины прямого угла C (∠C=90°, ∠B=β, ∠A=90°−β):
#   • Высота CH:    ∠HCB = 90°−β = ∠A,   ∠ACH = β.
#   • Биссектриса CD: ∠ACD = ∠DCB = 45°.
#   • Медиана CM:   CM = AM = MB (свойство), значит ∠MCB = ∠MBC = β, ∠ACM = 90°−β.
# Угол между биссектрисой и медианой = |45° − ∠ACM| = |45° − (90°−β)| = |β − 45°|.
# Угол между биссектрисой и высотой = |45° − ∠ACH| = |45° − β|.

def _svg_pryam_lines(beta_deg, with_median=False, with_high=False, AB_px=200):
    """Прямоугольный треугольник ABC с ∠C=90°, ∠B=beta_deg.
    Биссектриса CD из C на AB всегда. Опционально медиана CM или высота CH.
    Включает маркер прямого угла в C."""
    AC = AB_px * math.sin(math.radians(beta_deg))
    BC = AB_px * math.cos(math.radians(beta_deg))
    Ax, Ay = 50, 180
    Bx, By = Ax + AB_px, Ay
    Cx = (Ax + Bx) / 2 + (AC ** 2 - BC ** 2) / (2 * AB_px)
    Cy = Ay - math.sqrt(max(0, AC ** 2 - (Cx - Ax) ** 2))
    A = (Ax, Ay); B = (Bx, By); C = (Cx, Cy)
    AD = AB_px * AC / (AC + BC)
    D = (Ax + AD, Ay)
    M = ((Ax + Bx) / 2, Ay)
    H = (Cx, Ay)
    rmark_C = _right_angle_marker(C, A, B, size=11)

    parts = [
        f'<line x1="{Ax}" y1="{Ay}" x2="{Bx}" y2="{By}" stroke="#1f1f1f" stroke-width="1.5"/>',
        f'<line x1="{Ax}" y1="{Ay}" x2="{Cx:.1f}" y2="{Cy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>',
        f'<line x1="{Bx}" y1="{By}" x2="{Cx:.1f}" y2="{Cy:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>',
        f'<line x1="{Cx:.1f}" y1="{Cy:.1f}" x2="{D[0]:.1f}" y2="{D[1]}" stroke="#1f1f1f" stroke-width="1.5"/>',
    ]
    if with_median:
        parts.append(f'<line x1="{Cx:.1f}" y1="{Cy:.1f}" x2="{M[0]}" y2="{M[1]}" stroke="#1f1f1f" stroke-width="1.5"/>')
    if with_high:
        parts.append(f'<line x1="{Cx:.1f}" y1="{Cy:.1f}" x2="{H[0]:.1f}" y2="{H[1]}" stroke="#1f1f1f" stroke-width="1.5"/>')
        parts.append(f'<rect x="{H[0]-10:.1f}" y="{H[1]-10}" width="10" height="10" fill="none" stroke="#1f1f1f" stroke-width="1"/>')
    parts.append(rmark_C)

    points = [(A, 'A'), (B, 'B'), (C, 'C'), (D, 'D')]
    if with_median:
        points.append((M, 'M'))
    if with_high:
        points.append((H, 'H'))
    for P, _ in points:
        parts.append(f'<circle cx="{P[0]:.1f}" cy="{P[1]:.1f}" r="2.5" fill="#1f1f1f"/>')

    label_offsets = {
        'A': (-15, 17), 'B': (5, 17), 'C': (-5, -7),
        'D': (-3, 17), 'M': (-3, 17), 'H': (-3, 17),
    }
    for P, name in points:
        ox, oy = label_offsets[name]
        parts.append(f'<text x="{P[0]+ox:.1f}" y="{P[1]+oy:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">{name}</text>')

    body = "\n  ".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Прямоугольный треугольник ABC с биссектрисой из C">
  {body}
</svg>"""

_SVG_PRJM_BISS_MED = _svg_pryam_lines(beta_deg=21, with_median=True)
_SVG_PRJM_BISS_VYS = _svg_pryam_lines(beta_deg=25, with_high=True)

TYPE_PRJM_LINII = [
    (
        r"Острый угол \(B\) прямоугольного треугольника \(ABC\) равен \(21°\). "
        r"Найдите величину угла между биссектрисой \(CD\) и медианой \(CM\), "
        r"проведёнными из вершины прямого угла \(C\). Ответ дайте в градусах.",
        "24",
        _SVG_PRJM_BISS_MED,
    ),
    (
        r"Острый угол \(B\) прямоугольного треугольника \(ABC\) равен \(25°\). "
        r"Найдите величину угла между высотой \(CH\) и биссектрисой \(CD\), "
        r"проведёнными из вершины прямого угла \(C\). Ответ дайте в градусах.",
        "20",
        _SVG_PRJM_BISS_VYS,
    ),
]


# ── Прототип 13: Равнобедренный треугольник + внешний угол ───────────────────
# Если AC=BC, то ∠A=∠B (равны углы при основании AB).
# Внешний угол при B: ∠CBD = 180°−∠B.
# Сумма углов треугольника: ∠A+∠B+∠C = 180°, при AC=BC: 2∠B = 180°−∠C.

def _svg_ravnobedr(C_angle_deg, with_D=True, AC_px=110):
    """Равнобедренный треугольник с AC=BC, угол при вершине C = C_angle_deg.
    A слева, B справа, C над серединой AB. D — точка на продолжении AB за B."""
    half = math.radians(C_angle_deg / 2)
    AB_px = 2 * AC_px * math.sin(half)
    h_px = AC_px * math.cos(half)
    midX = 160
    By_px = 180
    A = (midX - AB_px / 2, By_px)
    B = (midX + AB_px / 2, By_px)
    C = (midX, By_px - h_px)
    D = (B[0] + 28, By_px) if with_D else None
    marks_AC = _equality_marks(A, C)
    marks_BC = _equality_marks(B, C)

    parts = []
    parts.append(f'<line x1="{A[0]:.1f}" y1="{A[1]}" x2="{D[0]:.1f}" y2="{D[1]}" stroke="#1f1f1f" stroke-width="1.5"/>' if with_D else
                 f'<line x1="{A[0]:.1f}" y1="{A[1]}" x2="{B[0]:.1f}" y2="{B[1]}" stroke="#1f1f1f" stroke-width="1.5"/>')
    parts.append(f'<line x1="{A[0]:.1f}" y1="{A[1]}" x2="{C[0]:.1f}" y2="{C[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>')
    parts.append(f'<line x1="{B[0]:.1f}" y1="{B[1]}" x2="{C[0]:.1f}" y2="{C[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>')
    parts.append(marks_AC)
    parts.append(marks_BC)
    parts.append(f'<circle cx="{A[0]:.1f}" cy="{A[1]}" r="2.5" fill="#1f1f1f"/>')
    parts.append(f'<circle cx="{B[0]:.1f}" cy="{B[1]}" r="2.5" fill="#1f1f1f"/>')
    parts.append(f'<circle cx="{C[0]:.1f}" cy="{C[1]:.1f}" r="2.5" fill="#1f1f1f"/>')
    if with_D:
        parts.append(f'<circle cx="{D[0]:.1f}" cy="{D[1]}" r="2.5" fill="#1f1f1f"/>')
    parts.append(f'<text x="{A[0]-15:.1f}" y="{A[1]+15}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>')
    parts.append(f'<text x="{B[0]-5:.1f}" y="{B[1]+15}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>')
    parts.append(f'<text x="{C[0]-5:.1f}" y="{C[1]-7:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>')
    if with_D:
        parts.append(f'<text x="{D[0]+4:.1f}" y="{D[1]+15}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">D</text>')

    body = "\n  ".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Равнобедренный треугольник ABC, угол C = {C_angle_deg}°">
  {body}
</svg>"""

# 13.1: ∠C=168°, плоский треугольник
_SVG_RAVNOBEDR_1 = _svg_ravnobedr(168, AC_px=105)
# 13.2: внешний при B = 107° → ∠B=73°, ∠C=34°
_SVG_RAVNOBEDR_2 = _svg_ravnobedr(34, AC_px=130)

TYPE_RAVNOBEDR_VNESHN = [
    (
        r"В треугольнике \(ABC\) стороны \(AC\) и \(BC\) равны, угол \(C\) равен \(168°\), "
        r"угол \(CBD\) внешний. Найдите величину угла \(CBD\). Ответ дайте в градусах.",
        "174",
        _SVG_RAVNOBEDR_1,
    ),
    (
        r"В треугольнике \(ABC\) стороны \(AC\) и \(BC\) равны. "
        r"Внешний угол при вершине \(B\) равен \(107°\). Найдите угол \(C\). "
        r"Ответ дайте в градусах.",
        "34",
        _SVG_RAVNOBEDR_2,
    ),
]


# ── Прототип 14: Биссектриса в треугольнике ──────────────────────────────────
# AD — биссектриса ∠A, значит ∠BAD = ∠CAD = ∠A/2. Угол ABD = 180°−∠A−∠C.
# Для угла ADB: в треугольнике ABD ∠ADB = 180°−∠B−∠BAD.

def _svg_bissekt(A, B, C):
    """Треугольник ABC с биссектрисой AD из A.
    D — точка на BC: BD/DC = AB/AC (по теореме о биссектрисе)."""
    AB = math.hypot(B[0] - A[0], B[1] - A[1])
    AC = math.hypot(C[0] - A[0], C[1] - A[1])
    t = AB / (AB + AC)  # доля от B к C
    D = (B[0] + t * (C[0] - B[0]), B[1] + t * (C[1] - B[1]))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" role="img" aria-label="Треугольник ABC с биссектрисой AD из A">
  <line x1="{A[0]}" y1="{A[1]}" x2="{B[0]}" y2="{B[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{A[0]}" y1="{A[1]}" x2="{C[0]}" y2="{C[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{B[0]}" y1="{B[1]}" x2="{C[0]}" y2="{C[1]}" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="{A[0]}" y1="{A[1]}" x2="{D[0]:.1f}" y2="{D[1]:.1f}" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="{A[0]}" cy="{A[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{B[0]}" cy="{B[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{C[0]}" cy="{C[1]}" r="2.5" fill="#1f1f1f"/>
  <circle cx="{D[0]:.1f}" cy="{D[1]:.1f}" r="2.5" fill="#1f1f1f"/>
  <text x="{A[0]-15}" y="{A[1]+15}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">A</text>
  <text x="{B[0]+5}" y="{B[1]+15}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">B</text>
  <text x="{C[0]-5}" y="{C[1]-7}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">C</text>
  <text x="{D[0]+6:.1f}" y="{D[1]+5:.1f}" font-family="Cambria, Georgia, serif" font-style="italic" font-size="15" fill="#1f1f1f">D</text>
</svg>"""

# Два разных треугольника для двух задач — разная форма.
_SVG_BISS_1 = _svg_bissekt(A=(50, 180), B=(270, 180), C=(220, 40))
_SVG_BISS_2 = _svg_bissekt(A=(60, 180), B=(280, 180), C=(160, 40))

TYPE_BISSEKTR = [
    (
        r"В треугольнике \(ABC\) угол \(C\) равен \(54°\), \(AD\) — биссектриса, "
        r"угол \(BAD\) равен \(23°\). Найдите величину угла \(ADB\). "
        r"Ответ дайте в градусах.",
        "77",
        _SVG_BISS_1,
    ),
    (
        r"В треугольнике \(ABC\) угол \(C\) равен \(55°\), \(AD\) — биссектриса, "
        r"угол \(CAD\) равен \(29°\). Найдите величину угла \(ABD\). "
        r"Ответ дайте в градусах.",
        "67",
        _SVG_BISS_2,
    ),
]


ASSIGNMENTS = [
    {
        "title": "Высота треугольника и параллелограмма",
        "order": 1,
        "description": (
            r"Ключевая формула: площадь одна и та же через любое основание. "
            r"Для треугольника: \(S = \tfrac{1}{2} a h_a = \tfrac{1}{2} b h_b\), "
            r"откуда \(h_b = \dfrac{a \cdot h_a}{b}\). "
            r"Для параллелограмма: \(S = a h_a = b h_b\) — та же зависимость."
        ),
        "required_correct": 2,
        "questions": TYPE_VYSOTA,
    },
    {
        "title": "Касательная и секущая через центр",
        "order": 2,
        "description": (
            r"Схема: \(CA\) — касательная к окружности с центром \(O\) в точке \(A\), "
            r"луч \(CO\) пересекает окружность в точке \(B\). "
            r"Так как \(OA \perp CA\), в треугольнике \(ACO\): "
            r"\(\angle AOC = 90° - \angle ACO\). "
            r"Градусная мера дуги \(AB\), заключённой внутри угла, равна центральному "
            r"углу \(\angle AOC\). Связь: \(\angle ACO + \text{дуга}\,AB = 90°\)."
        ),
        "required_correct": 2,
        "questions": TYPE_DUGA,
    },
    {
        "title": "Периметр четырёхугольника с вписанной окружностью",
        "order": 3,
        "description": (
            r"Если в четырёхугольник вписана окружность, то суммы противоположных сторон равны: "
            r"\(AB + CD = BC + DA\). "
            r"Поэтому периметр \(P = 2(AB + CD)\)."
        ),
        "required_correct": 2,
        "questions": TYPE_PERIMETR,
    },
    {
        "title": "Радиус описанной окружности треугольника",
        "order": 4,
        "description": (
            r"По теореме синусов: \(\dfrac{AB}{\sin C} = 2R\), "
            r"откуда \(R = \dfrac{AB}{2 \sin C}\). "
            r"Часто угол тупой: \(\sin 135° = \dfrac{\sqrt{2}}{2}\), \(\sin 120° = \dfrac{\sqrt{3}}{2}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_RADIUS_TRE,
    },
    {
        "title": "Площадь части параллелограмма (E — середина стороны)",
        "order": 5,
        "description": (
            r"Точка \(E\) — середина \(AD\). Треугольник \(ABE\) и треугольник \(BCE\) "
            r"имеют одинаковые основания и высоты, поэтому \(S_{ABE} = \tfrac{1}{4} S_{ABCD}\). "
            r"Трапеция \(BCDE = S_{ABCD} - S_{ABE} = \tfrac{3}{4} S_{ABCD}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_PLOSCHAD_PARAL,
    },
    {
        "title": "Площадь части треугольника (DE — средняя линия)",
        "order": 6,
        "description": (
            r"\(DE\) — средняя линия треугольника \(ABC\), параллельная \(AB\). "
            r"Треугольник \(CDE \sim\) треугольнику \(CAB\) с коэффициентом \(\tfrac{1}{2}\), "
            r"поэтому \(S_{CDE} = \tfrac{1}{4} S_{ABC}\) и \(S_{ABED} = \tfrac{3}{4} S_{ABC}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_PLOSCHAD_TRE,
    },
    {
        "title": "Синус и косинус угла в прямоугольном треугольнике",
        "order": 7,
        "description": (
            r"В прямоугольном треугольнике \(ABC\) с \(\angle C = 90°\) гипотенуза — \(AB\). "
            r"\(\cos A = \dfrac{AC}{AB}\) (прилежащий катет / гипотенуза), "
            r"\(\sin A = \dfrac{BC}{AB}\) (противолежащий катет / гипотенуза). "
            r"Неизвестный катет находится по теореме Пифагора."
        ),
        "required_correct": 2,
        "questions": TYPE_SIN_COS,
    },
    {
        "title": "Два диаметра — вписанный и центральный угол",
        "order": 8,
        "description": (
            r"\(AC\) и \(BD\) — диаметры окружности с центром \(O\). "
            r"Треугольник \(OCB\) равнобедренный (\(OC = OB = R\)), поэтому "
            r"\(\angle BOC = 180° - 2\angle OCB = 180° - 2\angle ACB\). "
            r"Углы \(AOD\) и \(BOC\) — вертикальные, значит "
            r"\(\angle AOD = 180° - 2\angle ACB\)."
        ),
        "required_correct": 2,
        "questions": TYPE_NAJTI_UGOL_DIAMETERS,
    },
    {
        "title": "Вписанный четырёхугольник с диагоналями",
        "order": 9,
        "description": (
            r"Вписанные углы, опирающиеся на одну дугу, равны: "
            r"\(\angle CAD = \angle CBD\) (оба опираются на дугу \(CD\)). "
            r"Поэтому \(\angle ABD = \angle ABC - \angle CBD = \angle ABC - \angle CAD\)."
        ),
        "required_correct": 2,
        "questions": TYPE_VPISAN_4UG_DIAG,
    },
    {
        "title": "Вписанный четырёхугольник: противоположные углы",
        "order": 10,
        "description": (
            r"Сумма противоположных углов вписанного четырёхугольника равна \(180°\): "
            r"\(\angle A + \angle C = 180°\), \(\angle B + \angle D = 180°\)."
        ),
        "required_correct": 2,
        "questions": TYPE_VPISAN_4UG_PROTIV,
    },
    {
        "title": "Центральный и вписанный угол на одну дугу",
        "order": 11,
        "description": (
            r"Центральный угол вдвое больше вписанного, опирающегося на ту же дугу: "
            r"\(\alpha_{\text{центр}} = 2\alpha_{\text{впис}}\). "
            r"Если разность \(\alpha_{\text{центр}} - \alpha_{\text{впис}} = d\), то "
            r"\(\alpha_{\text{впис}} = d\), \(\alpha_{\text{центр}} = 2d\)."
        ),
        "required_correct": 2,
        "questions": TYPE_TSENTR_VPISAN,
    },
    {
        "title": "Прямоугольный треугольник: биссектриса, медиана и высота из C",
        "order": 12,
        "description": (
            r"В прямоугольном \(\triangle ABC\) с \(\angle C = 90°\), \(\angle B = \beta\): "
            r"высота \(CH\) даёт \(\angle ACH = \beta\); "
            r"медиана \(CM\) опирается на гипотенузу: \(CM = AM = MB\), "
            r"откуда \(\angle ACM = 90° - \beta\); "
            r"биссектриса \(CD\) делит прямой угол: \(\angle ACD = 45°\). "
            r"Угол между биссектрисой и медианой: \(|\beta - 45°|\); "
            r"между биссектрисой и высотой: \(|45° - \beta|\)."
        ),
        "required_correct": 2,
        "questions": TYPE_PRJM_LINII,
    },
    {
        "title": "Равнобедренный треугольник и внешний угол",
        "order": 13,
        "description": (
            r"Если \(AC = BC\), то \(\angle A = \angle B\) (углы при основании \(AB\)). "
            r"Из суммы углов: \(2\angle B + \angle C = 180°\), откуда "
            r"\(\angle B = \dfrac{180° - \angle C}{2}\). "
            r"Внешний угол при вершине \(B\): \(\angle CBD = 180° - \angle B\)."
        ),
        "required_correct": 2,
        "questions": TYPE_RAVNOBEDR_VNESHN,
    },
    {
        "title": "Биссектриса в треугольнике",
        "order": 14,
        "description": (
            r"\(AD\) — биссектриса \(\angle A\), значит \(\angle BAC = 2\angle BAD = 2\angle CAD\). "
            r"Угол \(\angle B = 180° - \angle BAC - \angle C\). "
            r"Угол \(\angle ADB = 180° - \angle B - \angle BAD\) (из треугольника \(ABD\))."
        ),
        "required_correct": 2,
        "questions": TYPE_BISSEKTR,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 1 questions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing EGE-1 lesson before inserting",
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
            deleted, _ = Lesson.objects.filter(module=module, order=1).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted existing lesson (order=1): {deleted} objects"
            ))

        lesson, created = Lesson.objects.get_or_create(
            module=module,
            order=1,
            defaults={
                "title": "Задание 1",
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
            f"Done! Lesson: Zadacha 1, {total_q} questions added."
        ))
