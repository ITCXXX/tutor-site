# -*- coding: utf-8 -*-
"""Группа 8889B9 — Печи для бани (парное отделение). 10 задач."""

from django.core.management.base import BaseCommand
from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


GID = "8889B9"
TITLE = "8889B9 · Печи для парного отделения бани"
LESSON_TITLE = "Печи для бани"


CONTEXT_HTML = (
    "<p>Хозяин дачного участка строит баню с парным отделением. "
    "Парное отделение имеет размеры: длина <b>3,5 м</b>, ширина <b>2,2 м</b>, "
    "высота <b>2 м</b>. Окон в парном отделении нет, для доступа внутрь "
    "планируется дверь шириной 60 см, высота дверного проёма 1,8 м. "
    "Для прогрева парного отделения можно использовать электрическую "
    "или дровяную печь. В таблице представлены характеристики трёх печей.</p>"
    '<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.95em">'
    '<thead><tr>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Номер печи</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Тип</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Объём помещения (куб. м)</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Масса (кг)</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Стоимость (руб.)</th>'
    '</tr></thead><tbody>'
    '<tr><td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">1</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em">дровяная</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">8–12</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">40</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:right">18 000</td></tr>'
    '<tr><td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">2</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em">дровяная</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">10–16</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">48</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:right">19 500</td></tr>'
    '<tr><td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">3</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em">электрическая</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">9–15,5</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">15</td>'
    '<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:right">15 000</td></tr>'
    '</tbody></table>'
    "<p>Для установки дровяной печи дополнительных затрат не потребуется. "
    "Установка электрической печи потребует подведения специального кабеля, "
    "что обойдётся в <b>6500 руб.</b></p>"
)


def arch_question_html(width_cm, height_cm):
    """Задача про радиус арки кожуха печи."""
    return (
        "<p>Хозяин выбрал дровяную печь. Печь снабжена кожухом вокруг дверцы топки. "
        "Верхняя часть кожуха выполнена в виде арки, приваренной к передней стенке "
        "печки по дуге окружности с центром в середине нижней части кожуха. "
        f"Размеры кожуха в сантиметрах: <b>ширина {width_cm} см, высота {height_cm} см</b>.</p>"
        "<p>Для установки печки хозяину понадобилось узнать радиус закругления арки <i>R</i>. "
        "Найдите радиус закругления арки в сантиметрах.</p>"
    )


def matching_html(header, values, label):
    """Задача на соответствие между значениями и номерами печей."""
    th = ''.join(
        f'<th style="border:1px solid #999;padding:0.4em 0.8em">{v}</th>' for v in values
    )
    td = ''.join(
        '<td style="border:1px solid #999;padding:0.6em;min-width:5em">&nbsp;</td>'
        for _ in values
    )
    return (
        '<p>Установите соответствие между ' + header + ' и номерами печей. '
        'Заполните таблицу: в ответе запишите последовательность трёх цифр без '
        'пробелов, запятых и других дополнительных символов.</p>'
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        f'<thead><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">{label}</th>'
        + th + '</tr></thead>'
        '<tbody><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Номер печи</th>'
        + td + '</tr></tbody></table>'
    )


# Объём парного 3,5·2,2·2 = 15,4 куб.м.
# Подходящие печи (объём ≥ 15,4): печь 2 (10-16) ✓ и печь 3 (9-15,5) ✓ (15,5 ≥ 15,4).
# Подходящая дровяная — печь 2 (19 500 руб., без установки).
# Электрическая — печь 3 (15 000 + 6500 = 21 500 руб.).

TASKS = [
    {"tid": "BE99C7", "t_type": "T1",
     "question_html": arch_question_html(50, 60),
     "answer": "65"},  # √(25² + 60²) = √4225 = 65
    {"tid": "30DDBA", "t_type": "T1",
     "question_html": matching_html(
         "массами", ["15", "40", "48"], "Масса (кг)"),
     "answer": "312"},  # 15→3, 40→1, 48→2
    {"tid": "59DCD0", "t_type": "T1",
     "question_html": arch_question_html(60, 40),
     "answer": "50"},  # √(30² + 40²) = 50
    {"tid": "74CB1E", "t_type": "T1",
     "question_html": matching_html(
         "стоимостями", ["15 000", "19 500", "18 000"], "Стоимость (руб.)"),
     "answer": "321"},  # 15000→3, 19500→2, 18000→1

    {"tid": "CD3CFF", "t_type": "T2",
     "question_html": "<p>Найдите объём парного отделения строящейся бани. Ответ дайте в кубических метрах.</p>",
     "answer": "15,4"},  # 3,5·2,2·2 = 15,4
    {"tid": "2789BB", "t_type": "T2",
     "question_html": "<p>Найдите площадь пола парного отделения строящейся бани. Ответ дайте в квадратных метрах.</p>",
     "answer": "7,7"},  # 3,5·2,2 = 7,7

    {"tid": "888F31", "t_type": "T3",
     "question_html": (
         "<p>На сколько рублей покупка дровяной печи, подходящей по объёму "
         "парного отделения, обойдётся <b>дешевле</b> электрической с учётом установки?</p>"
     ),
     "answer": "2000"},  # 21 500 - 19 500
    {"tid": "908015", "t_type": "T3",
     "question_html": (
         "<p>На сколько рублей покупка дровяной печи, подходящей по объёму "
         "парного отделения, обойдётся <b>дороже</b> электрической без учёта установки?</p>"
     ),
     "answer": "4500"},  # 19 500 - 15 000

    {"tid": "8A06F1", "t_type": "T4",
     "question_html": "<p>На дровяную печь, масса которой 40 кг, сделали скидку 10%. Сколько рублей стала стоить печь?</p>",
     "answer": "16200"},  # 18 000 · 0,9
    {"tid": "FEDFE6", "t_type": "T4",
     "question_html": "<p>На дровяную печь, масса которой 48 кг, сделали скидку 10%. Сколько рублей стала стоить печь?</p>",
     "answer": "17550"},  # 19 500 · 0,9
]


class Command(BaseCommand):
    help = f"Группа {GID} — Печи для бани"

    def handle(self, *args, **opts):
        course = Course.objects.get(slug="oge-maths")
        module, _ = Module.objects.get_or_create(
            course=course, title="Задания 1-5",
            defaults={"order": 0, "description": ""},
        )
        lesson, _ = Lesson.objects.get_or_create(
            module=module, title=LESSON_TITLE,
            defaults={"lesson_type": "practice", "order": 8,
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
