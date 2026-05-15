# -*- coding: utf-8 -*-
"""Группа B9A7F7 — Форматы листов А (А0..А6). 20 задач."""

from django.core.management.base import BaseCommand
from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


GID = "B9A7F7"
TITLE = "B9A7F7 · Форматы листов бумаги (A0–A6)"
LESSON_TITLE = "Форматы листов бумаги"
IMG_PATH = "/media/oge15/oge15_B9A7F7.png"


CONTEXT_HTML = (
    "<p>Общепринятые форматы листов бумаги обозначают буквой А и цифрой: "
    "А0, А1, А2 и так далее. Лист формата А0 имеет форму прямоугольника "
    "площадью 1 кв. м. Если лист формата А0 разрезать пополам параллельно "
    "меньшей стороне, получатся два одинаковых листа формата А1. "
    "Если лист А1 разрезать пополам таким же образом, получатся два листа "
    "формата А2 и т. д.</p>"
    f'<img src="{IMG_PATH}" alt="Форматы листов бумаги А0–А5" '
    f'style="max-width:340px;display:block;margin:0.8em 0;">'
    "<p>Отношение большей стороны к меньшей стороне листа каждого формата "
    "одно и то же, поэтому листы всех форматов подобны. Это нужно, чтобы "
    "пропорции текста и его расположение на листе сохранялись при изменении "
    "формата листа.</p>"
)


def matching_html(table_rows, formats):
    """Задача на сопоставление: дана таблица номеров и размеров,
    нужно сопоставить с форматами."""
    rows_html = ''
    for n, length, width in table_rows:
        rows_html += (
            f'<tr><td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{n}</td>'
            f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{length}</td>'
            f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{width}</td></tr>'
        )
    th_formats = ''.join(
        f'<th style="border:1px solid #999;padding:0.4em 0.8em">{f}</th>' for f in formats
    )
    td_formats = ''.join(
        '<td style="border:1px solid #999;padding:0.6em;min-width:5em">&nbsp;</td>'
        for _ in formats
    )
    formats_str = ", ".join(formats)
    return (
        f"<p>В таблице даны размеры (с точностью до мм) четырёх листов, "
        f"имеющих форматы {formats_str}.</p>"
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<thead><tr>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Номер листа</th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Длина (мм)</th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Ширина (мм)</th>'
        '</tr></thead><tbody>' + rows_html + '</tbody></table>'
        "<p>Установите соответствие между форматами и номерами листов. "
        "Заполните таблицу: в ответе запишите последовательность четырёх цифр, "
        "соответствующих номерам листов, без пробелов, запятых и других символов.</p>"
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        f'<thead><tr>{th_formats}</tr></thead>'
        f'<tbody><tr>{td_formats}</tr></tbody></table>'
    )


TASKS = [
    # Сопоставления
    {"tid": "187F35", "t_type": "T1",
     "question_html": matching_html(
         [("1", 210, 148), ("2", 594, 420), ("3", 148, 105), ("4", 420, 297)],
         ["A2", "A3", "A5", "A6"]),
     "answer": "2413"},
    {"tid": "9A494F", "t_type": "T1",
     "question_html": matching_html(
         [("1", 594, 420), ("2", 420, 297), ("3", 148, 105), ("4", 297, 210)],
         ["A2", "A3", "A4", "A6"]),
     "answer": "1243"},
    {"tid": "CC9C1C", "t_type": "T1",
     "question_html": matching_html(
         [("1", 841, 594), ("2", 1189, 841), ("3", 297, 210), ("4", 594, 420)],
         ["A0", "A1", "A2", "A4"]),
     "answer": "2143"},
    {"tid": "4B0911", "t_type": "T1",
     "question_html": matching_html(
         [("1", 594, 420), ("2", 420, 297), ("3", 1189, 841), ("4", 210, 148)],
         ["A0", "A2", "A3", "A5"]),
     "answer": "3124"},

    # Сколько листов меньшего формата получается из одного большего
    {"tid": "703F88", "t_type": "T2",
     "question_html": "<p>Сколько листов формата А3 получится из одного листа формата А2?</p>",
     "answer": "2"},
    {"tid": "AFAB20", "t_type": "T2",
     "question_html": "<p>Сколько листов формата А5 получится из одного листа формата А3?</p>",
     "answer": "4"},
    {"tid": "707AE8", "t_type": "T2",
     "question_html": "<p>Сколько листов формата А4 получится из одного листа формата А2?</p>",
     "answer": "4"},
    {"tid": "1DFDCC", "t_type": "T2",
     "question_html": "<p>Сколько листов формата А4 получится из одного листа формата А1?</p>",
     "answer": "8"},

    # Площади
    {"tid": "3860EB", "t_type": "T3",
     "question_html": "<p>Найдите площадь листа формата А3. Ответ дайте в квадратных сантиметрах.</p>",
     "answer": "1250"},  # 1/8 кв.м = 1250 см²
    {"tid": "8972EA", "t_type": "T3",
     "question_html": "<p>Найдите площадь листа формата А5. Ответ дайте в квадратных сантиметрах.</p>",
     "answer": "312,5"},  # 1/32 кв.м = 312,5 см²

    # Размеры (округление до 10 мм)
    {"tid": "6C743F", "t_type": "T4",
     "question_html": "<p>Найдите ширину листа бумаги формата А0. Ответ дайте в миллиметрах и округлите до ближайшего целого числа, кратного 10.</p>",
     "answer": "840"},  # 841 → 840
    {"tid": "C8C2FC", "t_type": "T4",
     "question_html": "<p>Найдите ширину листа бумаги формата А4. Ответ дайте в миллиметрах и округлите до ближайшего целого числа, кратного 10.</p>",
     "answer": "210"},
    {"tid": "B1753A", "t_type": "T4",
     "question_html": "<p>Найдите длину листа бумаги формата А1. Ответ дайте в миллиметрах и округлите до ближайшего целого числа, кратного 10.</p>",
     "answer": "840"},  # 841 → 840
    {"tid": "637C7B", "t_type": "T4",
     "question_html": "<p>Найдите длину листа бумаги формата А6. Ответ дайте в миллиметрах и округлите до ближайшего целого числа, кратного 10.</p>",
     "answer": "150"},  # 148 → 150

    # Отношения сторон
    {"tid": "A7FCE1", "t_type": "T5",
     "question_html": "<p>Найдите отношение длины меньшей стороны листа формата А4 к большей. Ответ округлите до десятых.</p>",
     "answer": "0,7"},  # 210/297 ≈ 0,707
    {"tid": "C08FA1", "t_type": "T5",
     "question_html": "<p>Найдите отношение длины большей стороны листа формата А1 к меньшей. Ответ округлите до десятых.</p>",
     "answer": "1,4"},  # 841/594 ≈ 1,416

    # Масса пачки
    {"tid": "EA5C1C", "t_type": "T5",
     "question_html": (
         "<p>Бумагу формата А5 упаковали в пачки по 500 листов. Найдите массу пачки, "
         "если масса бумаги площадью 1 кв. м равна 80 г. Ответ дайте в граммах.</p>"
     ),
     "answer": "1250"},  # A5 = 1/32 кв.м, 80/32 = 2,5 г, ·500 = 1250
    {"tid": "CC70B9", "t_type": "T5",
     "question_html": (
         "<p>Бумагу формата А1 упаковали в пачки по 80 листов. Найдите массу пачки, "
         "если масса бумаги площадью 1 кв. м равна 120 г. Ответ дайте в граммах.</p>"
     ),
     "answer": "4800"},  # A1 = 1/2 кв.м, 60 г·80 = 4800

    # Шрифт (увеличение/уменьшение в √2 раз при переходе на ±1 формат)
    {"tid": "B8AF15", "t_type": "T5",
     "question_html": (
         "<p>Размер (высота) типографского шрифта измеряется в пунктах. Один пункт "
         "равен 1/72 дюйма, то есть 0,3528 мм. Какой высоты нужен шрифт (в пунктах), "
         "чтобы текст был расположен на листе формата А3 так же, как этот же текст, "
         "напечатанный шрифтом высотой 15 пунктов на листе формата А4? Размер шрифта "
         "округляется до целого.</p>"
     ),
     "answer": "21"},  # 15·√2 ≈ 21,21 → 21
    {"tid": "07E7B1", "t_type": "T5",
     "question_html": (
         "<p>Размер (высота) типографского шрифта измеряется в пунктах. Один пункт "
         "равен 1/72 дюйма, то есть 0,3528 мм. Какой высоты нужен шрифт (в пунктах), "
         "чтобы текст был расположен на листе формата А5 так же, как этот же текст, "
         "напечатанный шрифтом высотой 16 пунктов на листе формата А4? Размер шрифта "
         "округляется до целого.</p>"
     ),
     "answer": "11"},  # 16/√2 ≈ 11,31 → 11
]


class Command(BaseCommand):
    help = f"Группа {GID} — Форматы листов А"

    def handle(self, *args, **opts):
        course = Course.objects.get(slug="oge-maths")
        module, _ = Module.objects.get_or_create(
            course=course, title="Задания 1-5",
            defaults={"order": 0, "description": ""},
        )
        lesson, _ = Lesson.objects.get_or_create(
            module=module, title=LESSON_TITLE,
            defaults={"lesson_type": "practice", "order": 9,
                      "content": "", "is_free": False},
        )

        existing = TaskGroup.objects.filter(lesson=lesson, fipi_ctx_id=GID).first()
        if existing:
            existing.title = TITLE
            existing.context_html = CONTEXT_HTML
            existing.save()
            existing.sub_questions.all().delete()
            group = existing
            self.stdout.write(f"  Группа {GID} была — пересоздаём подзадачи.")
        else:
            order = (lesson.task_groups.aggregate(Max("order"))["order__max"] or 0) + 1
            group = TaskGroup.objects.create(
                lesson=lesson, fipi_ctx_id=GID, title=TITLE,
                context_html=CONTEXT_HTML, order=order,
            )
            self.stdout.write(f"  Создана TaskGroup: {group}")

        for i, t in enumerate(TASKS, 1):
            GroupSubQuestion.objects.create(
                group=group, question_html=t["question_html"],
                correct_answer=t["answer"], t_type=t["t_type"],
                fipi_task_id=t["tid"], order=i,
            )
            self.stdout.write(f"  [{i}] {t['t_type']} #{t['tid']} -> {t['answer']}")
        self.stdout.write(f"\nГотово: TaskGroup '{group.title}' с {len(TASKS)} подзадачами.")
