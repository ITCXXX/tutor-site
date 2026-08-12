# -*- coding: utf-8 -*-
"""Хелперы для Шины-групп ОГЭ №1-5. Импортируется из populate_oge15_<GID>.py."""

import math

from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "Шины"


# ============================================================
#   Встроенный SVG (рисунок 1 — маркировка, рисунок 2 — размеры)
# ============================================================

def _herringbone_b5_path():
    """Ёлочка протектора (Б5: компенсация эллиптического искажения)."""
    cx_white_L, cx_edge_L = 182.67, 174
    cx_white_R, cx_edge_R = 191.33, 200
    length = 0.88
    n = 18
    t_min, t_max = 0.30, math.pi - 0.30
    parts = []
    for i in range(n):
        t = t_min + (t_max - t_min) * (i + 0.5) / n
        dt = -0.20 * (1.4 - 0.8 * math.sin(t))
        for cw, ce in [(cx_white_L, cx_edge_L), (cx_white_R, cx_edge_R)]:
            sx = cw - 55 * math.sin(t)
            sy = 140 - 110 * math.cos(t)
            cxe = cw + length * (ce - cw)
            ex = cxe - 55 * math.sin(t + dt)
            ey = 140 - 110 * math.cos(t + dt)
            parts.append(f"M {sx:.2f},{sy:.2f} L {ex:.2f},{ey:.2f}")
    return " ".join(parts)


def _arrow(cx, cy, dx, dy, color="#1f1f1f"):
    """Мелкий закрашенный наконечник в (cx,cy), наружу по (dx,dy)."""
    length = 5
    half = 2
    bx = cx - dx * length
    by = cy - dy * length
    perpx, perpy = -dy, dx
    p1x = bx + perpx * half
    p1y = by + perpy * half
    p2x = bx - perpx * half
    p2y = by - perpy * half
    return (
        f'<path d="M {cx},{cy} L {p1x:.1f},{p1y:.1f} L {p2x:.1f},{p2y:.1f} Z" '
        f'fill="{color}"/>'
    )


def _dim_vert(x_close, x_tip, y1, y2, label, ext_from_x=None, color="#1f1f1f"):
    """Вертикальная размерная линия со стрелками наружу и буквой в направлении xTip."""
    parts = []
    if ext_from_x is not None:
        parts.append(
            f'<line x1="{ext_from_x}" y1="{y1}" x2="{x_close}" y2="{y1}" '
            f'stroke="#aaa" stroke-width="0.7"/>'
        )
        parts.append(
            f'<line x1="{ext_from_x}" y1="{y2}" x2="{x_close}" y2="{y2}" '
            f'stroke="#aaa" stroke-width="0.7"/>'
        )
    parts.append(
        f'<line x1="{x_close}" y1="{y1}" x2="{x_close}" y2="{y2}" '
        f'stroke="{color}" stroke-width="1"/>'
    )
    parts.append(_arrow(x_close, y1, 0, -1, color))
    parts.append(_arrow(x_close, y2, 0, +1, color))
    direction = 1 if x_tip > x_close else -1
    lx = x_tip + direction * 12
    ly = (y1 + y2) / 2 + 5
    parts.append(
        f'<text x="{lx}" y="{ly}" text-anchor="middle" '
        f'font-family="Cambria, Georgia, serif" font-style="italic" '
        f'font-size="17" font-weight="700" fill="{color}">{label}</text>'
    )
    return "".join(parts)


def _dim_horiz(x1, x2, y_close, y_tip, label, color="#000"):
    """Горизонтальная размерная линия (для B) со стрелками наружу."""
    parts = []
    parts.append(
        f'<line x1="{x1}" y1="{y_close}" x2="{x2}" y2="{y_close}" '
        f'stroke="{color}" stroke-width="1"/>'
    )
    parts.append(_arrow(x1, y_close, -1, 0, color))
    parts.append(_arrow(x2, y_close, +1, 0, color))
    direction = -1 if y_tip < y_close else 1
    ly = y_tip + direction * 8
    xmid = (x1 + x2) / 2
    parts.append(
        f'<text x="{xmid}" y="{ly}" text-anchor="middle" '
        f'font-family="Cambria, Georgia, serif" font-style="italic" '
        f'font-size="17" font-weight="700" fill="{color}">{label}</text>'
    )
    return "".join(parts)


def _build_tire_svg():
    """Строит общий SVG: рисунок 1 (маркировка) слева + рисунок 2 (размеры) справа."""
    herringbone = _herringbone_b5_path()

    fig1 = (
        '<path d="M 28,171 A 343,343 0 0 1 572,171 L 471,171 '
        'A 270,270 0 0 0 129,171 L 28,171 Z" fill="#1a1a1a"/>'
        '<path d="M 99,171 A 290,290 0 0 1 501,171 L 471,171 '
        'A 270,270 0 0 0 129,171 L 99,171 Z" fill="#7a7a7a"/>'
        '<g clip-path="url(#tireSvgClipFront)">'
        '<path d="M 42,182 A 325,325 0 0 1 558,182" '
        'stroke="#7a7a7a" stroke-width="2.5" fill="none"/>'
        '<text font-family="Arial, Helvetica, sans-serif" font-size="22" '
        'fill="#c8c8c8" font-weight="600" letter-spacing="2">'
        '<textPath href="#tireSvgMarkText" startOffset="50%" '
        'text-anchor="middle">195/65 R15</textPath>'
        '</text>'
        '</g>'
        '<path d="M 26.8,170.2 A 344.5,344.5 0 0 1 573.2,170.2" '
        'stroke="#000" stroke-width="3" fill="none" '
        'stroke-dasharray="7,2" stroke-linecap="butt"/>'
    )

    fig2 = (
        # Чёрная заливка беговой дорожки
        '<path d="M 174,30 A 55,110 0 0 0 174,250 L 200,250 '
        'A 55,110 0 0 1 200,30 Z" fill="#1a1a1a"/>'
        # Ёлочка
        f'<path d="{herringbone}" fill="none" stroke="#fff" '
        'stroke-linecap="round" stroke-width="1.2"/>'
        # Две белые продольные линии
        '<path d="M 182.67,30 A 55,110 0 0 0 182.67,250" fill="none" '
        'stroke="#fff" stroke-width="1.5"/>'
        '<path d="M 191.33,30 A 55,110 0 0 0 191.33,250" fill="none" '
        'stroke="#fff" stroke-width="1.5"/>'
        # Контур задней дуги и касательные
        '<path d="M 174,30 A 55,110 0 0 0 174,250" fill="none" '
        'stroke="#1f1f1f" stroke-width="1.5"/>'
        '<line x1="174" y1="30" x2="200" y2="30" '
        'stroke="#1f1f1f" stroke-width="1.5"/>'
        '<line x1="174" y1="250" x2="200" y2="250" '
        'stroke="#1f1f1f" stroke-width="1.5"/>'
        # Боковина (чёрная заливка + серое кольцо + тонкая серая полоска)
        '<path d="M 200,30 A 55,110 0 1,1 200,250 A 55,110 0 1,1 200,30 Z '
        'M 200,70 A 35,70 0 1,1 200,210 A 35,70 0 1,1 200,70 Z" '
        'fill="#1a1a1a" fill-rule="evenodd"/>'
        '<path d="M 200,59 A 40,81 0 1,1 200,221 A 40,81 0 1,1 200,59 Z '
        'M 200,70 A 35,70 0 1,1 200,210 A 35,70 0 1,1 200,70 Z" '
        'fill="#7a7a7a" fill-rule="evenodd"/>'
        '<ellipse cx="200" cy="140" rx="50" ry="100" fill="none" '
        'stroke="#7a7a7a" stroke-width="1.5"/>'
        '<ellipse cx="200" cy="140" rx="55" ry="110" fill="none" '
        'stroke="#1f1f1f" stroke-width="1.5"/>'
        # Диск (передний и задний через clipPath)
        '<ellipse cx="200" cy="140" rx="35" ry="70" fill="none" '
        'stroke="#1f1f1f" stroke-width="1.3"/>'
        '<g clip-path="url(#tireSvgDcSide)">'
        '<ellipse cx="174" cy="140" rx="35" ry="70" fill="none" '
        'stroke="#1f1f1f" stroke-width="1.3"/>'
        '</g>'
        # Размеры B, H (сверху), d, H (снизу), D
        + _dim_horiz(174, 200, 24, 14, "B")
        + _dim_vert(275, 285, 30, 70, "H", ext_from_x=200)
        + _dim_vert(275, 285, 70, 210, "d", ext_from_x=200)
        + _dim_vert(275, 285, 210, 250, "H", ext_from_x=200)
        + _dim_vert(320, 330, 30, 250, "D", ext_from_x=200)
    )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 300" '
        'style="max-width:100%;height:auto;display:block;margin:0.8em auto;">'
        '<defs>'
        '<path id="tireSvgMarkText" d="M 56.5,193 A 307,307 0 0 1 543.5,193" '
        'fill="none"/>'
        '<clipPath id="tireSvgClipFront">'
        '<path d="M 28,171 A 343,343 0 0 1 572,171 L 471,171 '
        'A 270,270 0 0 0 129,171 L 28,171 Z"/>'
        '</clipPath>'
        '<clipPath id="tireSvgDcSide">'
        '<ellipse cx="200" cy="140" rx="35" ry="70"/>'
        '</clipPath>'
        '</defs>'
        f'<g transform="translate(0, 62)">{fig1}</g>'
        f'<g transform="translate(620, 15)">{fig2}</g>'
        '</svg>'
    )


# Готовая SVG-строка (вычисляется один раз при импорте модуля).
TIRE_SVG = _build_tire_svg()


# ============================================================
#   Контекст и хелперы для подзадач
# ============================================================

_CTX_BODY = """
<p>Автомобильное колесо представляет из себя металлический диск с установленной
на него резиновой шиной. Диаметр диска совпадает с диаметром внутреннего
отверстия в шине.</p>
<p>Для маркировки автомобильных шин применяется единая система обозначений.
Например, 195/65 R15 (рис. 1). Первое число означает ширину шины в миллиметрах
(размер <i>B</i> на рис. 2). Второе число — высота боковины шины <i>H</i>
в процентах от ширины шины. Например, шина с маркировкой 195/65 R15 имеет
ширину <i>B</i> = 195 мм и высоту боковины <i>H</i> = 195 · 0,65 = 126,75 (мм).</p>
<p>Буква <b>R</b> означает, что шина имеет радиальную конструкцию.</p>
<p>За буквой <b>R</b> следует диаметр диска <i>d</i> в дюймах (в одном дюйме
25,4 мм). Общий диаметр колеса <i>D</i> можно найти, зная диаметр диска
и высоту боковины.</p>
__SVG__
"""


def build_context_html(factory_marking):
    """Контекст с указанной заводской маркировкой."""
    return (_CTX_BODY + (
        f'<p>Завод производит легковые автомобили определённой модели и устанавливает\n'
        f'на них колёса с шинами <b>{factory_marking}</b>.</p>'
    )).strip().replace("__SVG__", TIRE_SVG)


def build_t1_table_html(diameters, rows):
    """Строит HTML-таблицу для T1.
    diameters — список значений диаметра (как строки).
    rows — список (ширина, [значения в колонках]).
    """
    th_diameters = ''.join(
        f'<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">{d}</th>'
        for d in diameters
    )
    body_rows = ''
    for w, cells in rows:
        td_cells = ''.join(
            f'<td style="border:1px solid #999;padding:0.3em 0.6em">{c}</td>' for c in cells
        )
        body_rows += (
            f'<tr><td style="border:1px solid #999;padding:0.3em 0.6em">{w}</td>'
            f'{td_cells}</tr>'
        )
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.95em">'
        '<thead><tr>'
        '<th rowspan="2" style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Ширина шины (мм)</th>'
        f'<th colspan="{len(diameters)}" style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Диаметр диска (дюймы)</th>'
        '</tr>'
        f'<tr>{th_diameters}</tr></thead>'
        f'<tbody>{body_rows}</tbody></table>'
    )


def t1_question(table_html, kind, diameter):
    """kind = 'наибольшей' или 'наименьшей'."""
    return (
        "<p>Завод допускает установку шин с другими маркировками. В таблице "
        "показаны разрешённые размеры шин.</p>"
        + table_html +
        f"<p>Шины какой <b>{kind}</b> ширины можно устанавливать на автомобиль, "
        f"если диаметр диска равен {diameter} дюймам? Ответ дайте в миллиметрах.</p>"
    )


def t2_question(marking):
    return f"<p>Сколько миллиметров составляет высота боковины шины, имеющей маркировку {marking}?</p>"


def t3_question():
    return "<p>Найдите диаметр колеса автомобиля, выходящего с завода. Ответ дайте в миллиметрах.</p>"


def t4_question(marking):
    return (
        f"<p>На сколько миллиметров увеличится диаметр колеса, если заменить "
        f"колёса, установленные на заводе, колёсами с шинами {marking}?</p>"
    )


def t5_question(marking):
    return (
        f"<p>На сколько процентов увеличится пробег автомобиля при одном обороте "
        f"колеса, если заменить колёса, установленные на заводе, колёсами с шинами "
        f"{marking}? Результат округлите до десятых.</p>"
    )


def t4_decrease_question(marking):
    return (
        f"<p>На сколько миллиметров уменьшится диаметр колеса, если заменить "
        f"колёса, установленные на заводе, колёсами с шинами {marking}?</p>"
    )


def t5_decrease_question(marking):
    return (
        f"<p>На сколько процентов уменьшится пробег автомобиля при одном обороте "
        f"колеса, если заменить колёса, установленные на заводе, колёсами с шинами "
        f"{marking}? Результат округлите до десятых.</p>"
    )


def deploy(gid, group_title, factory_marking, tasks, stdout):
    """tasks — список dict с question_html, answer, t_type, tid."""
    context_html = build_context_html(factory_marking)
    course = Course.objects.get(slug="oge-maths")
    module, _ = Module.objects.get_or_create(
        course=course, title="Задания 1-5",
        defaults={"order": 0, "description": ""},
    )
    lesson, _ = Lesson.objects.get_or_create(
        module=module, title=LESSON_TITLE,
        defaults={"lesson_type": "practice", "order": 5,
                  "content": "", "is_free": False},
    )

    existing = TaskGroup.objects.filter(lesson=lesson, fipi_ctx_id=gid).first()
    if existing:
        existing.title = group_title
        existing.context_html = context_html
        existing.save()
        existing.sub_questions.all().delete()
        group = existing
        stdout.write(f"  Группа {gid} была — пересоздаём подзадачи.")
    else:
        order = (lesson.task_groups.aggregate(Max("order"))["order__max"] or 0) + 1
        group = TaskGroup.objects.create(
            lesson=lesson, fipi_ctx_id=gid, title=group_title,
            context_html=context_html, order=order,
        )
        stdout.write(f"  Создана TaskGroup: {group}")

    for i, t in enumerate(tasks, 1):
        GroupSubQuestion.objects.create(
            group=group, question_html=t["question_html"],
            correct_answer=t["answer"], t_type=t["t_type"],
            fipi_task_id=t["tid"], order=i,
        )
        stdout.write(f"  [{i}] {t['t_type']} #{t['tid']} -> {t['answer']}")
    stdout.write(f"\nГотово: TaskGroup '{group.title}' с {len(tasks)} подзадачами.")
    return group
