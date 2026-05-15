# -*- coding: utf-8 -*-
"""Группа B64540 — Сложные дороги (Антоновка → Богданово). 20 задач."""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "Сложные дороги"
GROUP_TITLE = "B64540 · Антоновка → Богданово"
FIPI_GROUP_ID = "B64540"
FIPI_CTX_ID = "0420D8E1695786E54006DFC4A57D76CB"
IMG_PATH = "/media/oge15/slozhnye_dorogi_ctx.png"


CONTEXT_HTML = """
<p>На рисунке изображён план сельской местности.</p>
<p>Таня на летних каникулах приезжает в гости к дедушке в деревню
<b>Антоновка</b> (на плане обозначена цифрой 1). В конце каникул дедушка
на машине собирается отвезти Таню на автобусную станцию, которая
находится в деревне <b>Богданово</b>.</p>
<p>Из Антоновки в Богданово можно проехать по просёлочной дороге вдоль
реки. Есть другой путь — по шоссе до деревни <b>Ванютино</b>, где нужно
повернуть под прямым углом налево на другое шоссе, ведущее в Богданово.
Третий маршрут проходит по просёлочной дороге мимо пруда до деревни
<b>Горюново</b>, где можно свернуть на шоссе до Богданово. Четвёртый
маршрут пролегает по шоссе до деревни <b>Доломино</b>, от Доломино до
Горюново по просёлочной дороге мимо конюшни и от Горюново до Богданово
по шоссе. Ещё один маршрут проходит по шоссе до деревни <b>Егорка</b>,
по просёлочной дороге мимо конюшни от Егорки до <b>Жилино</b> и по шоссе
от Жилино до Богданово.</p>
<p>Шоссе и просёлочные дороги образуют прямоугольные треугольники.</p>
<img src="__IMG_PATH__" alt="План сельской местности"
     style="max-width:480px;display:block;margin:0.8em auto;">
<p>По шоссе Таня с дедушкой едут со скоростью 50 км/ч, а по просёлочным
дорогам — со скоростью 30 км/ч. Расстояние от Антоновки до Доломино равно
12 км, от Доломино до Егорки — 4 км, от Егорки до Ванютино — 12 км,
от Горюново до Ванютино — 15 км, от Ванютино до Жилино — 9 км, а от
Жилино до Богданово — 12 км.</p>
""".strip().replace("__IMG_PATH__", IMG_PATH)


def _t1_table(villages):
    head = ''.join(
        '<th style="border:1px solid #999;padding:0.4em 0.8em">{}</th>'.format(v)
        for v in villages
    )
    body = ''.join(
        '<td style="border:1px solid #999;padding:0.6em;min-width:5em">&nbsp;</td>'
        for _ in villages
    )
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<thead><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Деревни</th>'
        + head + '</tr></thead>'
        '<tbody><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Цифры</th>'
        + body + '</tr></tbody>'
        '</table>'
    )


def _t1_q(villages):
    return (
        '<p>Пользуясь описанием, определите, какими цифрами на плане '
        'обозначены деревни. Заполните таблицу, в ответе запишите '
        'последовательность четырёх цифр без пробелов и запятых.</p>'
        + _t1_table(villages)
    )


TASKS = [
    {"no": 1, "tid": "EABF12", "t_type": "T1",
     "question_html": _t1_q(["Ванютино", "Горюново", "Егорка", "Жилино"]),
     "answer": "4625"},
    {"no": 2, "tid": "1DAE55", "t_type": "T1",
     "question_html": _t1_q(["Егорка", "Ванютино", "Доломино", "Жилино"]),
     "answer": "2435"},
    {"no": 3, "tid": "D7DA06", "t_type": "T1",
     "question_html": _t1_q(["Богданово", "Горюново", "Доломино", "Егорка"]),
     "answer": "7632"},
    {"no": 4, "tid": "40373A", "t_type": "T1",
     "question_html": _t1_q(["Богданово", "Ванютино", "Егорка", "Жилино"]),
     "answer": "7425"},

    {"no": 5, "tid": "E30C8F", "t_type": "T2",
     "question_html": "<p>Найдите расстояние от Антоновки до Егорки по шоссе. Ответ дайте в километрах.</p>",
     "answer": "8"},
    {"no": 6, "tid": "093985", "t_type": "T2",
     "question_html": "<p>Найдите расстояние от Доломино до Ванютино по шоссе. Ответ дайте в километрах.</p>",
     "answer": "8"},
    {"no": 7, "tid": "ACE7E1", "t_type": "T2",
     "question_html": "<p>Найдите расстояние от Горюново до Жилино по шоссе. Ответ дайте в километрах.</p>",
     "answer": "6"},
    {"no": 8, "tid": "1DD53B", "t_type": "T2",
     "question_html": "<p>Найдите расстояние от Ванютино до Богданово по шоссе. Ответ дайте в километрах.</p>",
     "answer": "21"},

    {"no": 9, "tid": "B8F7D9", "t_type": "T3",
     "question_html": "<p>Найдите расстояние от Егорки до Жилино по прямой. Ответ дайте в километрах.</p>",
     "answer": "15"},
    {"no": 10, "tid": "BD19A3", "t_type": "T3",
     "question_html": "<p>Найдите расстояние от Доломино до Горюново по прямой. Ответ дайте в километрах.</p>",
     "answer": "17"},
    {"no": 11, "tid": "95B15C", "t_type": "T3",
     "question_html": "<p>Найдите расстояние от Антоновки до Горюново по прямой. Ответ дайте в километрах.</p>",
     "answer": "25"},
    {"no": 12, "tid": "14EF59", "t_type": "T3",
     "question_html": "<p>Найдите расстояние от Антоновки до Богданово по прямой. Ответ дайте в километрах.</p>",
     "answer": "29"},

    {"no": 13, "tid": "FCA4C5", "t_type": "T4",
     "question_html": "<p>Сколько минут затратят на дорогу Таня с дедушкой из Антоновки в Богданово, если поедут мимо пруда через Горюново?</p>",
     "answer": "57,2"},
    {"no": 14, "tid": "44E538", "t_type": "T4",
     "question_html": "<p>Сколько минут затратят на дорогу Таня с дедушкой из Антоновки в Богданово, если поедут через Доломино и Горюново мимо конюшни?</p>",
     "answer": "55,6"},
    {"no": 15, "tid": "211095", "t_type": "T4",
     "question_html": "<p>Сколько минут затратят на дорогу Таня с дедушкой из Антоновки в Богданово, если поедут через Егорку и Жилино мимо конюшни?</p>",
     "answer": "54"},
    {"no": 16, "tid": "C23492", "t_type": "T4",
     "question_html": "<p>Сколько минут затратят на дорогу Таня с дедушкой из Антоновки в Богданово, если поедут напрямик?</p>",
     "answer": "58"},

    {"no": 17, "tid": "DAD553", "t_type": "T5",
     "question_html": "<p>На шоссе машина дедушки расходует <b>6,8 литра</b> бензина на 100 км. Известно, что на путь из Антоновки до Богданово через Ванютино и путь через Доломино и Горюново мимо конюшни ей необходим один и тот же объём бензина. Сколько литров бензина на 100 км машина дедушки расходует на просёлочных дорогах?</p>",
     "answer": "9,2"},
    {"no": 18, "tid": "D02C75", "t_type": "T5",
     "question_html": "<p>На шоссе машина дедушки расходует <b>5,8 литра</b> бензина на 100 км. Известно, что на путь из Антоновки до Богданово через Ванютино и путь напрямик ей необходим один и тот же объём бензина. Сколько литров бензина на 100 км машина дедушки расходует на просёлочных дорогах?</p>",
     "answer": "8,2"},
    {"no": 19, "tid": "3DE30E", "t_type": "T5",
     "question_html": "<p>На шоссе машина дедушки расходует <b>6,5 литра</b> бензина на 100 км. Известно, что на путь из Антоновки до Богданово через Ванютино и путь через Горюново мимо пруда ей необходим один и тот же объём бензина. Сколько литров бензина на 100 км машина дедушки расходует на просёлочных дорогах?</p>",
     "answer": "9,1"},
    {"no": 20, "tid": "339932", "t_type": "T5",
     "question_html": "<p>На шоссе машина дедушки расходует <b>5,5 литра</b> бензина на 100 км. Известно, что на путь из Антоновки до Богданово через Ванютино и путь через Егорку и Жилино мимо конюшни ей необходим один и тот же объём бензина. Сколько литров бензина на 100 км машина дедушки расходует на просёлочных дорогах?</p>",
     "answer": "7,7"},
]


class Command(BaseCommand):
    help = "Создаёт TaskGroup B64540 (Сложные дороги) — 20 подзадач"

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
            defaults={"order": 1, "description": ""},
        )

        lesson, _ = Lesson.objects.get_or_create(
            module=module, title=LESSON_TITLE,
            defaults={"lesson_type": "practice", "order": 8, "content": "", "is_free": False},
        )

        if opts["clear"]:
            n, _ = TaskGroup.objects.filter(
                lesson=lesson, fipi_ctx_id=FIPI_CTX_ID
            ).delete()
            if n:
                self.stdout.write(self.style.WARNING("  Удалено {} объектов".format(n)))

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
            self.stdout.write(self.style.SUCCESS("  Создана TaskGroup: {}".format(group)))

        for i, t in enumerate(TASKS, 1):
            GroupSubQuestion.objects.create(
                group=group,
                question_html=t["question_html"],
                correct_answer=t["answer"],
                t_type=t["t_type"],
                fipi_task_id=t["tid"],
                order=i,
            )
            self.stdout.write("  [{:2d}] {} #{} -> {}".format(i, t["t_type"], t["tid"], t["answer"]))

        self.stdout.write(self.style.SUCCESS(
            "\nГотово: TaskGroup '{}' с {} подзадачами.".format(group.title, len(TASKS))
        ))
