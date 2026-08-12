# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=139: OGE16: G7 — вписанный 4-уг., углы через равные дуги
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import math
import random


# ─── Базовые геометрические хелперы ──────────────────────────────────────────

def _midpoint(P1, P2):
    return ((P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2)


def _angle_arc(vertex, P1, P2, label_text="", R=22, label_offset=16,
               arcs=1, arc_gap=4, font_size=13):
    """Дуга в углу vertex между лучами на P1 и P2 + опционально подпись.
    R адаптивно ограничен 32% длины меньшей соседней стороны."""
    vx, vy = vertex
    a1 = math.atan2(P1[1] - vy, P1[0] - vx)
    a2 = math.atan2(P2[1] - vy, P2[0] - vx)
    da = a2 - a1
    while da > math.pi:
        da -= 2 * math.pi
    while da < -math.pi:
        da += 2 * math.pi
    sweep = 1 if da > 0 else 0
    am = a1 + da / 2

    L1 = math.hypot(P1[0] - vx, P1[1] - vy)
    L2 = math.hypot(P2[0] - vx, P2[1] - vy)
    R = max(10, min(R, min(L1, L2) * 0.32))
    if abs(da) < math.radians(25):
        R = min(R, 16)

    out = []
    for i in range(arcs):
        r = R - i * arc_gap
        if r < 6:
            break
        x1 = vx + r * math.cos(a1)
        y1 = vy + r * math.sin(a1)
        x2 = vx + r * math.cos(a2)
        y2 = vy + r * math.sin(a2)
        out.append(
            f'<path d="M {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 0 {sweep} '
            f'{x2:.1f} {y2:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.1"/>'
        )
    if label_text:
        Lx = vx + (R + label_offset) * math.cos(am)
        Ly = vy + (R + label_offset) * math.sin(am) + 5
        out.append(
            f'<text x="{Lx:.1f}" y="{Ly:.1f}" font-family="Cambria, Georgia, serif" '
            f'font-size="{font_size}" fill="#1f1f1f" text-anchor="middle">{label_text}</text>'
        )
    return "".join(out)


def _vertex_dot(P, r=2.5):
    return f'<circle cx="{P[0]:.1f}" cy="{P[1]:.1f}" r="{r}" fill="#1f1f1f"/>'


def _segment(P1, P2, dashed=False, width=1.5):
    da = ' stroke-dasharray="4,3"' if dashed else ''
    return (
        f'<line x1="{P1[0]:.1f}" y1="{P1[1]:.1f}" x2="{P2[0]:.1f}" y2="{P2[1]:.1f}" '
        f'stroke="#1f1f1f" stroke-width="{width}"{da}/>'
    )


# ─── Хелперы для окружностей ─────────────────────────────────────────────────

def _circle(C, R, stroke_width=1.5):
    cx, cy = C
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R:.1f}" '
            f'fill="none" stroke="#1f1f1f" stroke-width="{stroke_width}"/>')


def _pt_on_circle(C, R, angle_deg):
    """Точка на окружности. 0° — справа, 90° — сверху (CCW в матем. смысле,
    с учётом инверсии Y в SVG)."""
    a = math.radians(angle_deg)
    return (C[0] + R * math.cos(a), C[1] - R * math.sin(a))


def _label_radial(P, name, center, offset=14, font_size=16, italic=True):
    """Подпись точки на окружности — радиально наружу от центра."""
    px, py = P
    cx, cy = center
    dx, dy = px - cx, py - cy
    L = math.hypot(dx, dy)
    if L < 1e-9:
        ox, oy = 0, -10
    else:
        ox = dx / L * offset
        oy = dy / L * offset
    style = "font-style:italic;" if italic else ""
    return (
        f'<text x="{px + ox:.1f}" y="{py + oy + 5:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="{font_size}" '
        f'fill="#1f1f1f" text-anchor="middle" style="{style}">{name}</text>'
    )


def _label_direction(P, name, direction, offset=14, font_size=15, italic=True):
    """Подпись точки в заданном направлении."""
    dl = math.hypot(direction[0], direction[1])
    if dl < 1e-9:
        dx, dy = 0, 1
    else:
        dx, dy = direction[0] / dl, direction[1] / dl
    lx = P[0] + dx * offset
    ly = P[1] + dy * offset + 5
    style = "font-style:italic;" if italic else ""
    return (
        f'<text x="{lx:.1f}" y="{ly:.1f}" '
        f'font-family="Cambria, Georgia, serif" font-size="{font_size}" '
        f'fill="#1f1f1f" text-anchor="middle" style="{style}">{name}</text>'
    )


def _ans(x):
    """Форматирует число как ответ: '7' или '7,5'."""
    if x == int(x):
        return str(int(x))
    return f"{x:.1f}".replace(".", ",")


def _svg_wrap(body, w=320, h=240):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="Окружность" '
        f'style="display:block;margin:0.5em auto">{body}</svg>'
    )


def _build_quad_g7(alpha, beta, O, R):
    """Расположить ABCD (CW порядок) так, чтобы:
    - дуга AD не через B = 2α (даёт ∠ABD = α);
    - дуга CD не через A = 2β (даёт ∠CAD = β).
    A слева, B вверху, C справа, D внизу.
    Дуги (CW от A через B,C,D к A): AB + BC + CD + DA = 360°.
    DA = 2α, CD = 2β, AB = BC = (360 - 2α - 2β) / 2.
    """
    AB_arc = (360 - 2 * alpha - 2 * beta) / 2
    # Поставим B вверху на 90°. CW от B на AB_arc = позиция A.
    # В нашем _pt_on_circle 0° — справа, CCW = увеличение угла.
    # CW = уменьшение угла. То есть A = B + AB_arc (в матем. смысле, CCW).
    a_B = 90
    a_A = 90 + AB_arc           # CCW от B на AB_arc → A слева-сверху/слева
    a_D = a_A + 2 * alpha       # CCW от A на 2α → D
    a_C = a_D + 2 * beta        # CCW от D на 2β → C
    # Замкнётся обратно: a_C + AB_arc должно ≡ a_B (mod 360°). Проверка:
    # AB_arc + 2α + 2β + AB_arc = 360 ⇒ ОК.
    rot = random.uniform(-15, 15)
    A = _pt_on_circle(O, R, a_A + rot)
    B = _pt_on_circle(O, R, a_B + rot)
    C = _pt_on_circle(O, R, a_C + rot)
    D = _pt_on_circle(O, R, a_D + rot)
    return A, B, C, D


def generate_task():
    """Вписанный 4-уг. Базовое: ∠ABD = α (на дугу AD), ∠CAD = β (на дугу CD).
    Тогда ∠DBC = ∠DAC = β (на ту же дугу DC), и ∠ABC = α + β.
    """
    alpha = random.randint(15, 60)
    beta = random.randint(15, 60)
    if alpha + beta > 130:
        alpha, beta = 30, 40
    ans = alpha + beta
    ask_text = (
        f"Четырёхугольник \\(ABCD\\) вписан в окружность. "
        f"Угол \\(ABD\\) равен \\({alpha}°\\), угол \\(CAD\\) равен \\({beta}°\\). "
        f"Найдите угол \\(ABC\\). Ответ дайте в градусах."
    )
    answer = str(ans)

    O = (160, 125)
    R = 78
    A, B, C, D = _build_quad_g7(alpha, beta, O, R)

    body = _circle(O, R)
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(B, D)  # диагональ для ∠ABD
    body += _segment(A, C)  # диагональ для ∠CAD

    # Маркер ∠ABD (при B, между BA и BD) — 1 дуга, маленький радиус
    body += _angle_arc(B, A, D, label_text=f"{alpha}°", R=16, label_offset=12, arcs=1)
    # Маркер ∠CAD (при A, между AC и AD) — 2 дуги
    body += _angle_arc(A, C, D, label_text=f"{beta}°", R=18, label_offset=14, arcs=2)
    # Искомый ∠ABC дужкой НЕ помечаем (только в условии).

    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _label_radial(A, "A", O, offset=14)
    body += _label_radial(B, "B", O, offset=14)
    body += _label_radial(C, "C", O, offset=14)
    body += _label_radial(D, "D", O, offset=14)

    svg = _svg_wrap(body)
    cond = f"{ask_text}<br><br>{svg}"
    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(7)
    for i in range(5):
        t = generate_task()
        print(f"[G7 #{i+1}] answer = {t['correct_answer']}")
