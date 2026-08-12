# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=156: OGE17: G6 — паралл.: S + 2 стороны → большая/меньшая высота
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import math
import random


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


def _label_direction(P, name, direction, offset=14, font_size=16, italic=True):
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


def _svg_wrap(body, w=320, h=220):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="Четырёхугольник" '
        f'style="display:block;margin:0.5em auto">{body}</svg>'
    )


def _make_parallelogram(angle_at_A_deg, AD_px=150, AB_px=85, anchor=(85, 175)):
    """Возвращает A, B, C, D — координаты паралл. (CW порядок).
    A — слева внизу, B — слева вверху, C — справа вверху, D — справа внизу.
    AD — нижнее основание (горизонтальное), AB — левая боковая.
    angle_at_A — угол при A между AD (вправо) и AB (вверх).
    """
    A = anchor
    D = (A[0] + AD_px, A[1])
    a = math.radians(angle_at_A_deg)
    Bx = A[0] + AB_px * math.cos(a)
    By = A[1] - AB_px * math.sin(a)
    B = (Bx, By)
    C = (D[0] + AB_px * math.cos(a), D[1] - AB_px * math.sin(a))
    return A, B, C, D


def generate_task():
    """Площадь паралл. = S, две стороны a < b. Найти большую/меньшую высоту.
    h_большая = S/a (к меньшей стороне); h_меньшая = S/b (к большей).
    """
    target = random.choice(['larger', 'smaller'])
    for _ in range(100):
        a = random.randint(2, 12)
        b = random.randint(a + 2, 22)
        h_a = random.randint(2, 12)
        S_val = a * h_a
        h_b = S_val / b
        if h_b == int(h_b) and h_b >= 1:
            h_b = int(h_b)
            break
    else:
        a, b, S_val, h_a, h_b = 5, 10, 40, 8, 4

    if target == 'larger':
        ans_val = h_a
        text_target = 'большую'
    else:
        ans_val = h_b
        text_target = 'меньшую'

    ask_text = (
        f"Площадь параллелограмма равна \({S_val}\), а две его стороны "
        f"равны \({a}\) и \({b}\). Найдите его высоты. В ответе укажите "
        f"{text_target} высоту."
    )
    answer = str(ans_val)

    # Картинка: паралл. + ДВЕ высоты из B — на AD и на продолжение CD.
    A, B, C, D = _make_parallelogram(70)
    # Высота BH1 на прямую AD (нижнюю): проекция B на AD (горизонталь через A)
    H1 = (B[0], A[1])
    # Высота BH2 на прямую CD: CD идёт от C к D. Проекция B на прямую CD.
    cdx, cdy = D[0] - C[0], D[1] - C[1]
    cdL2 = cdx * cdx + cdy * cdy
    t_proj = ((B[0] - C[0]) * cdx + (B[1] - C[1]) * cdy) / cdL2
    H2 = (C[0] + t_proj * cdx, C[1] + t_proj * cdy)

    body = ""
    body += _segment(A, B) + _segment(B, C) + _segment(C, D) + _segment(D, A)
    body += _segment(B, H1, dashed=True, width=1.3)
    body += _segment(B, H2, dashed=True, width=1.3)
    body += _vertex_dot(A) + _vertex_dot(B) + _vertex_dot(C) + _vertex_dot(D)
    body += _vertex_dot(H1) + _vertex_dot(H2)
    # Маркеры прямых углов
    sq = 8
    # H1 на AD (горизонталь). Внутренняя нормаль вверх.
    body += (
        f'<polyline points="{H1[0]:.1f},{H1[1]-sq:.1f} {H1[0]+sq:.1f},{H1[1]-sq:.1f} '
        f'{H1[0]+sq:.1f},{H1[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )
    # H2 на CD — маркер прямого угла вдоль CD и BH2
    import math as _m
    # Нормированный CD-вектор
    cdn = _m.hypot(cdx, cdy)
    ux, uy = cdx / cdn, cdy / cdn
    # Перпендикуляр к CD (внутрь паралл., к B)
    px, py = -uy, ux
    # Проверим направление
    if (B[0] - H2[0]) * px + (B[1] - H2[1]) * py < 0:
        px, py = -px, -py
    p1 = (H2[0] + ux * sq, H2[1] + uy * sq)
    p2 = (p1[0] + px * sq, p1[1] + py * sq)
    p3 = (H2[0] + px * sq, H2[1] + py * sq)
    body += (
        f'<polyline points="{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} '
        f'{p3[0]:.1f},{p3[1]:.1f}" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>'
    )

    body += _label_direction(A, "A", direction=(-1, 1), offset=14)
    body += _label_direction(B, "B", direction=(-1, -1), offset=14)
    body += _label_direction(C, "C", direction=(1, -1), offset=14)
    body += _label_direction(D, "D", direction=(1, 1), offset=14)
    body += _label_direction(H1, "H", direction=(0, 1), offset=14)
    body += _label_direction(H2, "K", direction=(1, 0), offset=14)

    svg = _svg_wrap(body)
    return {"condition_text": f"{ask_text}<br><br>{svg}", "correct_answer": answer}


if __name__ == "__main__":
    random.seed(6)
    for i in range(5):
        t = generate_task()
        print(f"[G6 #{i+1}] answer = {t['correct_answer']}")
