# -*- coding: utf-8 -*-
"""Группа 47E80B — Шины (195/65 R15 → 285/50 R20). 5 задач."""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "Шины"
GROUP_TITLE = "47E80B · Размеры шин и колёс"
FIPI_CTX_ID = "47E80B"
IMG_PATH = "/media/oge15/oge15_47E80B.png"


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
нити каркаса в боковине шины расположены вдоль радиусов колеса. Такие шины
применяются на всех легковых автомобилях.</p>

<p>За буквой <b>R</b> следует диаметр диска <i>d</i> в дюймах (в одном дюйме
25,4 мм). Таким образом, общий диаметр колеса <i>D</i> можно найти, зная
диаметр диска и высоту боковины.</p>

<img src="__IMG__" alt="Шины: маркировка и размеры"
     style="max-width:560px;display:block;margin:0.8em 0;">

<p>Завод производит легковые автомобили определённой модели и устанавливает
на них колёса с шинами <b>265/60 R18</b>.</p>
""").strip().replace("__IMG__", IMG_PATH)


T1_TABLE_HTML = """
<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.95em">
<thead>
  <tr>
    <th rowspan="2" style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Ширина шины (мм)</th>
    <th colspan="4" style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Диаметр диска (дюймы)</th>
  </tr>
  <tr>
    <th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">17</th>
    <th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">18</th>
    <th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">19</th>
    <th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">20</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">245</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">245/70</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
  </tr>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">255</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">255/70</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">255/65</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
  </tr>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">265</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">265/65</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">265/60; 265/65</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
  </tr>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">275</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">275/65</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">275/60</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">275/55</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">275/50</td>
  </tr>
  <tr>
    <td style="border:1px solid #999;padding:0.3em 0.6em">285</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">—</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">285/60</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">285/55</td>
    <td style="border:1px solid #999;padding:0.3em 0.6em">285/50</td>
  </tr>
</tbody>
</table>
""".strip()


TASKS = [
    {"no": 1, "tid": "16B444", "t_type": "T1",
     "question_html": (
        "<p>Завод допускает установку шин с другими маркировками. В таблице "
        "показаны разрешённые размеры шин.</p>"
        + T1_TABLE_HTML +
        "<p>Шины какой <b>наибольшей</b> ширины можно устанавливать на автомобиль, "
        "если диаметр диска равен 17 дюймам? Ответ дайте в миллиметрах.</p>"
     ),
     "answer": "275"},

    {"no": 2, "tid": "D61C70", "t_type": "T2",
     "question_html": (
        "<p>Сколько миллиметров составляет высота боковины шины, "
        "имеющей маркировку 275/65 R17?</p>"
     ),
     "answer": "178,75"},

    {"no": 3, "tid": "4200CB", "t_type": "T3",
     "question_html": (
        "<p>Найдите диаметр колеса автомобиля, выходящего с завода. "
        "Ответ дайте в миллиметрах.</p>"
     ),
     "answer": "775,2"},

    {"no": 4, "tid": "3F6D10", "t_type": "T4",
     "question_html": (
        "<p>На сколько миллиметров увеличится диаметр колеса, если заменить "
        "колёса, установленные на заводе, колёсами с шинами 285/50 R20?</p>"
     ),
     "answer": "17,8"},

    {"no": 5, "tid": "291F89", "t_type": "T5",
     "question_html": (
        "<p>На сколько процентов увеличится пробег автомобиля при одном "
        "обороте колеса, если заменить колёса, установленные на заводе, "
        "колёсами с шинами 285/50 R20? Результат округлите до десятых.</p>"
     ),
     "answer": "2,3"},
]


class Command(BaseCommand):
    help = "Группа 47E80B — Шины (5 задач)"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, **opts):
        try:
            course = Course.objects.get(slug="oge-maths")
        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR("Курс oge-maths не найден"))
            return

        module, _ = Module.objects.get_or_create(
            course=course, title="Задания 1-5",
            defaults={"order": 0, "description": ""},
        )

        lesson, _ = Lesson.objects.get_or_create(
            module=module, title=LESSON_TITLE,
            defaults={"lesson_type": "practice", "order": 5, "content": "", "is_free": False},
        )

        if opts["clear"]:
            n, _ = TaskGroup.objects.filter(
                lesson=lesson, fipi_ctx_id=FIPI_CTX_ID
            ).delete()
            if n:
                self.stdout.write(self.style.WARNING(f"  Удалено {n} объектов"))

        group, g_created = TaskGroup.objects.get_or_create(
            lesson=lesson, fipi_ctx_id=FIPI_CTX_ID,
            defaults={
                "title": GROUP_TITLE,
                "context_html": CONTEXT_HTML,
                "order": 1,
            },
        )
        if not g_created:
            group.title = GROUP_TITLE
            group.context_html = CONTEXT_HTML
            group.save()
            group.sub_questions.all().delete()
            self.stdout.write(self.style.WARNING("  Группа уже была — подзадачи пересоздаются."))
        else:
            self.stdout.write(self.style.SUCCESS(f"  Создана TaskGroup: {group}"))

        for i, t in enumerate(TASKS, 1):
            GroupSubQuestion.objects.create(
                group=group,
                question_html=t["question_html"],
                correct_answer=t["answer"],
                t_type=t["t_type"],
                fipi_task_id=t["tid"],
                order=i,
            )
            self.stdout.write(f"  [{i}] {t['t_type']} #{t['tid']} -> {t['answer']}")

        self.stdout.write(self.style.SUCCESS(
            f"\nГотово: TaskGroup '{group.title}' с {len(TASKS)} подзадачами."
        ))
