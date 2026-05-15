# -*- coding: utf-8 -*-
"""Группа 77CC6F — Шины (175/70 R12 → 175/65 R13). 4 задачи."""

from django.core.management.base import BaseCommand
from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "Шины"
GROUP_TITLE = "77CC6F · Размеры шин 175/70 R12"
FIPI_CTX_ID = "77CC6F"
IMG_PATH = "/media/oge15/oge15_47E80B.png"  # переиспользуем общую картинку шин


CONTEXT_HTML = ("""
<p>Автомобильное колесо представляет из себя металлический диск с установленной
на него резиновой шиной. Диаметр диска совпадает с диаметром внутреннего
отверстия в шине.</p>

<p>Для маркировки автомобильных шин применяется единая система обозначений.
Например, 195/65 R15 (рис. 1). Первое число означает ширину шины в миллиметрах
(размер <i>B</i> на рис. 2). Второе число — высота боковины шины <i>H</i>
в процентах от ширины шины. Например, шина с маркировкой 195/65 R15 имеет
ширину <i>B</i> = 195 мм и высоту боковины <i>H</i> = 195 · 0,65 = 126,75 (мм).</p>

<p>Буква <b>R</b> означает, что шина имеет радиальную конструкцию, то есть
нити каркаса в боковине шины расположены вдоль радиусов колеса.</p>

<p>За буквой <b>R</b> следует диаметр диска <i>d</i> в дюймах (в одном дюйме
25,4 мм). Таким образом, общий диаметр колеса <i>D</i> можно найти, зная
диаметр диска и высоту боковины.</p>

<img src="__IMG__" alt="Шины: маркировка и размеры"
     style="max-width:560px;display:block;margin:0.8em 0;">

<p>Завод производит легковые автомобили определённой модели и устанавливает
на них колёса с шинами <b>175/70 R12</b>.</p>
""").strip().replace("__IMG__", IMG_PATH)


T1_TABLE_HTML = """
<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.95em">
<thead>
  <tr>
    <th rowspan="2" style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Ширина шины (мм)</th>
    <th colspan="3" style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Диаметр диска (дюймы)</th>
  </tr>
  <tr>
    <th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">12</th>
    <th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">13</th>
    <th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">14</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">175</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">175/70</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">175/65</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
  </tr>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">185</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">185/60</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
  </tr>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">195</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">195/60</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
  </tr>
</tbody>
</table>
""".strip()


TASKS = [
    {"no": 1, "tid": "565F8F", "t_type": "T1",
     "question_html": (
        "<p>Завод допускает установку шин с другими маркировками. В таблице "
        "показаны разрешённые размеры шин.</p>"
        + T1_TABLE_HTML +
        "<p>Шины какой <b>наибольшей</b> ширины можно устанавливать на автомобиль, "
        "если диаметр диска равен 13 дюймам? Ответ дайте в миллиметрах.</p>"
     ),
     "answer": "195"},
    {"no": 2, "tid": "4A86C8", "t_type": "T2",
     "question_html": "<p>Сколько миллиметров составляет высота боковины шины, имеющей маркировку 175/65 R13?</p>",
     "answer": "113,75"},
    {"no": 3, "tid": "A01377", "t_type": "T3",
     "question_html": "<p>Найдите диаметр колеса автомобиля, выходящего с завода. Ответ дайте в миллиметрах.</p>",
     "answer": "549,8"},
    {"no": 4, "tid": "DBE024", "t_type": "T5",
     "question_html": (
        "<p>На сколько процентов увеличится пробег автомобиля при одном обороте "
        "колеса, если заменить колёса, установленные на заводе, колёсами с шинами "
        "175/65 R13? Результат округлите до десятых.</p>"
     ),
     "answer": "1,4"},
]


class Command(BaseCommand):
    help = "Группа 77CC6F — Шины (4 задачи)"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, **opts):
        course = Course.objects.get(slug="oge-maths")
        module, _ = Module.objects.get_or_create(
            course=course, title="Задания 1-5",
            defaults={"order": 0, "description": ""},
        )
        lesson, _ = Lesson.objects.get_or_create(
            module=module, title=LESSON_TITLE,
            defaults={"lesson_type": "practice", "order": 5, "content": "", "is_free": False},
        )

        if opts["clear"]:
            TaskGroup.objects.filter(lesson=lesson, fipi_ctx_id=FIPI_CTX_ID).delete()

        existing = TaskGroup.objects.filter(lesson=lesson, fipi_ctx_id=FIPI_CTX_ID).first()
        if existing:
            existing.title = GROUP_TITLE
            existing.context_html = CONTEXT_HTML
            existing.save()
            existing.sub_questions.all().delete()
            group = existing
            self.stdout.write(self.style.WARNING("  Группа была — подзадачи пересоздаются."))
        else:
            order = (lesson.task_groups.aggregate(Max("order"))["order__max"] or 0) + 1
            group = TaskGroup.objects.create(
                lesson=lesson, fipi_ctx_id=FIPI_CTX_ID,
                title=GROUP_TITLE, context_html=CONTEXT_HTML, order=order,
            )
            self.stdout.write(self.style.SUCCESS(f"  Создана TaskGroup: {group}"))

        for i, t in enumerate(TASKS, 1):
            GroupSubQuestion.objects.create(
                group=group, question_html=t["question_html"],
                correct_answer=t["answer"], t_type=t["t_type"],
                fipi_task_id=t["tid"], order=i,
            )
            self.stdout.write(f"  [{i}] {t['t_type']} #{t['tid']} -> {t['answer']}")

        self.stdout.write(self.style.SUCCESS(
            f"\nГотово: TaskGroup '{group.title}' с {len(TASKS)} подзадачами."
        ))
