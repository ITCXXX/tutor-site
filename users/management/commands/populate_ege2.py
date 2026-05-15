# -*- coding: utf-8 -*-
"""
Management command: populate EGE task 2 (vectors) questions.

Usage:
    python manage.py populate_ege2
    python manage.py populate_ege2 --clear

Creates (inside the existing ege-profile-math course):
  Module "Pervaya chast" (order=1) -> Lesson "Zadacha 2" (order=2)
  -> 3 Assignments (decimal_input)

Assignments:
  1. Длина линейной комбинации (5 вопросов)
  2. Скалярное произведение по координатам (17 вопросов, 3 с SVG)
  3. Скалярное произведение через длину и угол (2 вопроса)
"""

import math as _m
from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ── SVG-генератор ────────────────────────────────────────────────────────────

def _grid_svg(vec_a, vec_b, start_a=(0, 0), start_b=(0, 0)):
    """
    Генерирует встроенный SVG координатной плоскости с двумя векторами.
    Все координаты — в математической системе (ось y вверх).
    """
    ax, ay = vec_a
    bx, by = vec_b
    sx, sy = start_a
    tx, ty = start_b

    pts_x = [sx, sx + ax, tx, tx + bx, 0]
    pts_y = [sy, sy + ay, ty, ty + by, 0]
    xmin = int(_m.floor(min(pts_x))) - 1
    xmax = int(_m.ceil(max(pts_x)))  + 1
    ymin = int(_m.floor(min(pts_y))) - 1
    ymax = int(_m.ceil(max(pts_y)))  + 1

    # viewBox: SVG y = -math_y
    vx, vy = xmin, -ymax
    vw, vh = xmax - xmin, ymax - ymin

    ppu = 30          # пикселей на клетку
    W, H = vw * ppu, vh * ppu

    uid = f"{ax}_{ay}_{bx}_{by}_{sx}_{sy}".replace('-', 'm')

    lw = 0.07         # толщина линии (в единицах сетки)
    fs = 0.48         # размер шрифта

    ms = lw * 5       # размер маркера-стрелки

    def marker(mid, color):
        return (
            f'<marker id="{mid}" markerWidth="{ms}" markerHeight="{ms}" '
            f'refX="{ms}" refY="{ms/2}" orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L0,{ms} L{ms},{ms/2} z" fill="{color}"/>'
            f'</marker>'
        )

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="{vx} {vy} {vw} {vh}" '
        f'style="max-width:{W}px;height:auto;display:block;margin:0 auto .75rem;">'
    )
    p.append('<defs>')
    p.append(marker(f'ax{uid}', '#555'))
    p.append(marker(f'va{uid}', '#1a3a8f'))
    p.append(marker(f'vb{uid}', '#8b1a1a'))
    p.append('</defs>')

    # Сетка
    for gx in range(xmin, xmax + 1):
        p.append(f'<line x1="{gx}" y1="{vy}" x2="{gx}" y2="{vy+vh}" '
                 f'stroke="#ddd" stroke-width="{lw*0.6}"/>')
    for gy in range(ymin, ymax + 1):
        p.append(f'<line x1="{vx}" y1="{-gy}" x2="{vx+vw}" y2="{-gy}" '
                 f'stroke="#ddd" stroke-width="{lw*0.6}"/>')

    # Оси
    p.append(f'<line x1="{vx}" y1="0" x2="{xmax}" y2="0" '
             f'stroke="#444" stroke-width="{lw}" marker-end="url(#ax{uid})"/>')
    p.append(f'<line x1="0" y1="{vy+vh}" x2="0" y2="{vy}" '
             f'stroke="#444" stroke-width="{lw}" marker-end="url(#ax{uid})"/>')

    # Подписи осей
    p.append(f'<text x="{xmax-0.3}" y="{fs*0.7}" font-size="{fs}" fill="#444" font-family="serif">x</text>')
    p.append(f'<text x="{lw*2}" y="{vy+fs*1.1}" font-size="{fs}" fill="#444" font-family="serif">y</text>')

    # Отметки «0», «1», «−1»
    p.append(f'<text x="{lw*2}" y="{fs*0.9}" font-size="{fs*0.85}" fill="#444" font-family="serif">0</text>')
    p.append(f'<text x="0.85" y="{fs*0.9}" font-size="{fs*0.85}" fill="#444" font-family="serif">1</text>')
    p.append(f'<text x="{-fs*1.05}" y="-0.65" font-size="{fs*0.85}" fill="#444" font-family="serif">1</text>')
    if ymin < 0:
        p.append(f'<text x="{-fs*1.5}" y="1.4" font-size="{fs*0.85}" fill="#444" font-family="serif">-1</text>')

    def draw_vector(x0, y0, dx, dy, color, label, mid):
        x1, y1 = x0 + dx, y0 + dy
        L = _m.hypot(dx, dy)
        if L > 0:
            shrink = ms * 0.95
            ux, uy = dx / L, dy / L
            x1s = x1 - ux * shrink
            y1s = y1 - uy * shrink
        else:
            x1s, y1s = x1, y1
        p.append(
            f'<line x1="{x0}" y1="{-y0}" x2="{x1s}" y2="{-y1s}" '
            f'stroke="{color}" stroke-width="{lw*1.8}" marker-end="url(#{mid})"/>'
        )
        # Подпись по середине вектора, смещённая перпендикулярно
        mx_l = (x0 + x1) / 2
        my_l = (y0 + y1) / 2
        if L > 0:
            ox = (-dy / L) * 0.4
            oy = (dx / L) * 0.4
        else:
            ox, oy = 0.3, 0
        lx = mx_l + ox
        ly = my_l + oy
        p.append(
            f'<text x="{lx - fs*0.3}" y="{-ly + fs*0.35}" font-size="{fs*1.15}" '
            f'fill="{color}" font-style="italic" font-family="serif">{label}</text>'
        )

    draw_vector(sx, sy, ax, ay, '#1a3a8f', 'a', f'va{uid}')
    draw_vector(tx, ty, bx, by, '#8b1a1a', 'b', f'vb{uid}')

    p.append('</svg>')
    return ''.join(p)


# ── Данные задач ─────────────────────────────────────────────────────────────

# Тип 1: Длина линейной комбинации
# question_text, answer
TYPE1_LENGTH = [
    (
        r"Даны векторы \(\vec{a}\,(25;\,0)\) и \(\vec{b}\,(1;\,-5)\). "
        r"Найдите длину вектора \(\vec{a} - 4\vec{b}\).",
        "29",
    ),
    (
        r"Даны векторы \(\vec{a}\,(1;\,1)\) и \(\vec{b}\,(0;\,7)\). "
        r"Найдите длину вектора \(8\vec{a} + \vec{b}\).",
        "17",
    ),
    (
        r"Даны векторы \(\vec{a}\,(31;\,0)\) и \(\vec{b}\,(1;\,-1)\). "
        r"Найдите длину вектора \(\vec{a} - 24\vec{b}\).",
        "25",
    ),
    (
        r"Даны векторы \(\vec{a}\,(2;\,0)\) и \(\vec{b}\,(1;\,4)\). "
        r"Найдите длину вектора \(\vec{a} + 3\vec{b}\).",
        "13",
    ),
    # 579B74: задача с картинкой
    (
        r"На координатной плоскости изображены векторы \(\vec{a}\) и \(\vec{b}\), "
        r"координатами которых являются целые числа. "
        r"Найдите длину вектора \(\vec{a} + 4\vec{b}\).",
        "10",
        _grid_svg((2, 4), (1, 1), start_a=(1, -1), start_b=(2, 1)),  # SVG
    ),
]

# Тип 2: Скалярное произведение по координатам
TYPE2_DOT_COORD = [
    (
        r"Даны векторы \(\vec{a}\,(-13;\,4)\) и \(\vec{b}\,(-6;\,1)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "82",
    ),
    (
        r"Даны векторы \(\vec{a}\,(2;\,1)\) и \(\vec{b}\,(2;\,-4)\). "
        r"Найдите скалярное произведение векторов \(\vec{a} + \vec{b}\) и \(7\vec{a} - \vec{b}\).",
        "15",
    ),
    (
        r"Даны векторы \(\vec{a}\,(6;\,4)\) и \(\vec{b}\,(5;\,-7)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "2",
    ),
    (
        r"Даны векторы \(\vec{a}\,(5;\,3)\) и \(\vec{b}\,(4;\,-6)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "2",
    ),
    (
        r"Даны векторы \(\vec{a}\,(14;\,-2)\) и \(\vec{b}\,(5;\,-8)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "86",
    ),
    (
        r"Даны векторы \(\vec{a}\,(-3;\,5)\) и \(\vec{b}\,(1;\,13)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "62",
    ),
    (
        r"Даны векторы \(\vec{a}\,(7;\,9)\) и \(\vec{b}\,(8;\,-6)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "2",
    ),
    (
        r"Даны векторы \(\vec{a}\,(5;\,4)\) и \(\vec{b}\,(8;\,-9)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "4",
    ),
    (
        r"Даны векторы \(\vec{a}\,(6;\,9)\) и \(\vec{b}\,(8;\,-5)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "3",
    ),
    (
        r"Даны векторы \(\vec{a}\,(5;\,-7)\) и \(\vec{b}\,(14;\,1)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "63",
    ),
    (
        r"Даны векторы \(\vec{a}\,(6;\,4)\) и \(\vec{b}\,(6;\,-8)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "4",
    ),
    (
        r"Даны векторы \(\vec{a}\,(8;\,9)\) и \(\vec{b}\,(4;\,-3)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "5",
    ),
    (
        r"Даны векторы \(\vec{a}\,(5;\,4)\) и \(\vec{b}\,(8;\,-9)\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "4",
    ),
    # A288A1: задача с картинкой (векторы перпендикулярны)
    (
        r"На координатной плоскости изображены векторы \(\vec{a}\) и \(\vec{b}\), "
        r"координатами которых являются целые числа. "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "0",
        _grid_svg((2, 4), (2, -1), start_a=(1, 0), start_b=(2, 2)),
    ),
    # E5399A: задача с картинкой
    (
        r"На координатной плоскости изображены векторы \(\vec{a}\) и \(\vec{b}\), "
        r"координатами которых являются целые числа. "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "25",
        _grid_svg((3, 5), (5, 2), start_a=(0, -1), start_b=(1, -1)),
    ),
    # 0432E9: задача с картинкой
    (
        r"На координатной плоскости изображены векторы \(\vec{a}\) и \(\vec{b}\), "
        r"координатами которых являются целые числа. "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "24",
        _grid_svg((3, 4), (4, 3), start_a=(0, -1), start_b=(2, -1)),
    ),
]

# Тип 3: Скалярное произведение через длину и угол
TYPE3_DOT_ANGLE = [
    (
        r"Длины векторов \(\vec{a}\) и \(\vec{b}\) равны 3 и 5, "
        r"а угол между ними равен \(60°\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "7.5",
    ),
    (
        r"Длины векторов \(\vec{a}\) и \(\vec{b}\) равны 3 и 7, "
        r"а угол между ними равен \(60°\). "
        r"Найдите скалярное произведение \(\vec{a} \cdot \vec{b}\).",
        "10.5",
    ),
]

ASSIGNMENTS = [
    {
        "title": "Длина линейной комбинации векторов",
        "order": 1,
        "description": (
            r"Формула: \(|\lambda\vec{a} + \mu\vec{b}| = \sqrt{(\lambda a_x + \mu b_x)^2 + (\lambda a_y + \mu b_y)^2}\). "
            r"Сначала найдите координаты линейной комбинации, затем длину по формуле. "
            r"Запоминайте пифагоровы тройки: (3,4,5), (5,12,13), (7,24,25), (8,15,17), (20,21,29)."
        ),
        "required_correct": 4,
        "questions": TYPE1_LENGTH,
    },
    {
        "title": "Скалярное произведение векторов по координатам",
        "order": 2,
        "description": (
            r"Формула: \(\vec{a} \cdot \vec{b} = a_x b_x + a_y b_y\). "
            r"Для задач с картинкой: считайте координаты по клеткам сетки, затем применяйте формулу. "
            r"Для комбинаций: сначала найдите координаты каждой комбинации, потом скалярное произведение."
        ),
        "required_correct": 10,
        "questions": TYPE2_DOT_COORD,
    },
    {
        "title": "Скалярное произведение через длину и угол",
        "order": 3,
        "description": (
            r"Формула: \(\vec{a} \cdot \vec{b} = |\vec{a}|\,|\vec{b}|\cos\varphi\). "
            r"Частный случай: при \(\varphi = 60°\) имеем \(\cos 60° = 0{,}5\), "
            r"поэтому \(\vec{a} \cdot \vec{b} = \tfrac{1}{2}|\vec{a}|\,|\vec{b}|\)."
        ),
        "required_correct": 2,
        "questions": TYPE3_DOT_ANGLE,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 2 questions — vectors (22 items, 3 types)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing EGE-2 lesson before inserting",
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
                "title": "Pervaya chast",
                "description": "Zadachi pervoy chasti profil'nogo EGE.",
            },
        )

        if options["clear"]:
            deleted, _ = Lesson.objects.filter(module=module, order=2).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted existing lesson (order=2): {deleted} objects"
            ))

        lesson, created = Lesson.objects.get_or_create(
            module=module,
            order=2,
            defaults={
                "title": "Задание 2",
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

            for idx, row in enumerate(data["questions"]):
                q_text = row[0]
                answer  = row[1]
                svg     = row[2] if len(row) > 2 else ""

                question = TestQuestion.objects.create(
                    assignment=assignment,
                    question_text=q_text,
                    image_svg=svg,
                    order=idx + 1,
                )
                AnswerOption.objects.create(
                    question=question,
                    text=answer,
                    is_correct=True,
                )
                total_q += 1

        self.stdout.write(self.style.SUCCESS(
            f"Gotovo! Urok: Zadacha 2 (Vektory), {total_q} voprosov."
        ))
