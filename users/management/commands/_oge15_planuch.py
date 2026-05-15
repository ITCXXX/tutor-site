# -*- coding: utf-8 -*-
"""Хелпер для групп ОГЭ №1-5 «План участка/Домохозяйство»."""

from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "План домохозяйства"


def t1_question(objects):
    """objects — список названий объектов (4 шт)."""
    th = ''.join(
        f'<th style="border:1px solid #999;padding:0.4em 0.8em">{o}</th>' for o in objects
    )
    td = ''.join(
        '<td style="border:1px solid #999;padding:0.6em;min-width:5em">&nbsp;</td>'
        for _ in objects
    )
    return (
        '<p>Для объектов, указанных в таблице, определите, какими цифрами они '
        'обозначены на плане. Заполните таблицу: в ответе запишите '
        'последовательность цифр без пробелов, запятых и других дополнительных '
        'символов.</p>'
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<thead><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Объекты</th>'
        + th + '</tr></thead>'
        '<tbody><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Цифры</th>'
        + td + '</tr></tbody></table>'
    )


def heating_table_html(gas_data, electric_data):
    """Таблица для задачи об отоплении.
    *_data — dict с ключами: heater, other, rate, rate_unit, cost
    Например, {"heater": "24 000 руб.", "other": "18 280 руб.",
                "rate": "1,2 куб. м/ч", "cost": "5,6 руб./куб. м"}
    """
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.95em">'
        '<thead><tr>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef"></th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Нагреватель (котёл)</th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Прочее оборудование и монтаж</th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Средн. расход газа / средн. потребл. мощность</th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Стоимость газа / электроэнергии</th>'
        '</tr></thead><tbody>'
        '<tr><td style="border:1px solid #999;padding:0.3em 0.6em">Газовое отопление</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{gas_data["heater"]}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{gas_data["other"]}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{gas_data["rate"]}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{gas_data["cost"]}</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.3em 0.6em">Электр. отопление</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{electric_data["heater"]}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{electric_data["other"]}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{electric_data["rate"]}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em">{electric_data["cost"]}</td></tr>'
        '</tbody></table>'
    )


def heating_question(table_html, choice="газовое"):
    return (
        "<p>Хозяин участка планирует устроить в жилом доме систему отопления. "
        "Он рассматривает два варианта: электрическое или газовое отопление. "
        "Цены на оборудование и стоимость его установки, данные о расходе газа, "
        "электроэнергии и их стоимости даны в таблице.</p>"
        + table_html +
        f"<p>Обдумав оба варианта, хозяин решил установить <b>{choice}</b> "
        "отопление. Через сколько часов непрерывной работы отопления экономия "
        "от использования газа вместо электричества компенсирует разность в "
        "стоимости покупки и установки газового и электрического оборудования?</p>"
    )


def deploy(gid, group_title, context_html, tasks, stdout):
    course = Course.objects.get(slug="oge-maths")
    module, _ = Module.objects.get_or_create(
        course=course, title="Задания 1-5",
        defaults={"order": 0, "description": ""},
    )
    lesson, _ = Lesson.objects.get_or_create(
        module=module, title=LESSON_TITLE,
        defaults={"lesson_type": "practice", "order": 6,
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
