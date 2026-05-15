# -*- coding: utf-8 -*-
"""Хелперы для Шины-групп ОГЭ №1-5. Импортируется из populate_oge15_<GID>.py."""

from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "Шины"
IMG_PATH = "/media/oge15/oge15_47E80B.png"

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
<img src="__IMG__" alt="Шины: маркировка и размеры"
     style="max-width:560px;display:block;margin:0.8em 0;">
"""


def build_context_html(factory_marking):
    """Контекст с указанной заводской маркировкой."""
    return (_CTX_BODY + (
        f'<p>Завод производит легковые автомобили определённой модели и устанавливает\n'
        f'на них колёса с шинами <b>{factory_marking}</b>.</p>'
    )).strip().replace("__IMG__", IMG_PATH)


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
