# -*- coding: utf-8 -*-
"""Хелперы для Дороги-групп ОГЭ №1-5 (4-точечные планы).
Используется populate_oge15_<GID>.py.

Структура каждой группы:
- 4 деревни/села: дом дедушки → промежуточная1 → промежуточная2 (где 90°-поворот) → пункт назначения
- L-образное шоссе: пункт A → промежуточная1 → промежуточная2 → 90° → пункт Z
- Лесная дорожка / тропинка: гипотенузы прямоугольного треугольника
- Каждая группа: 10 подзадач (T1-T5 ×2 варианта)
- T5 — таблица цен товаров в 4-х магазинах, дешевле/дороже всего
"""

from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "Дороги (4-точечный план)"


def build_context_html(story, plan_img, speed_road, speed_path, cell_km):
    """story — словарь с именами и описанием маршрутов.
    Поля: hero, week_day, dest, dest_purpose, src_village, mid_village, corner_village,
    final_village, route_kind (велосипеды/машина), road_kind (лесная дорожка/грунтовая дорога),
    turn_dir (направо/налево), pond_kind (мимо пруда).
    """
    s = story
    intro = (
        f"<p>{s['hero']} летом отдыхает у дедушки в деревне <b>{s['src_village']}</b>. "
        f"В {s['week_day']} они собираются съездить на {s['route_kind']} в село "
        f"<b>{s['dest']}</b> {s['dest_purpose']}.</p>"
    )
    routes = (
        f"<p>Из деревни {s['src_village']} в село {s['dest']} можно проехать "
        f"по прямой {s['road_kind']}. Есть более длинный путь: "
        f"по прямолинейному шоссе через деревню <b>{s['mid_village']}</b> "
        f"до {'села' if s['corner_kind'] == 'село' else 'деревни'} "
        f"<b>{s['corner_village']}</b>, где нужно повернуть под прямым углом "
        f"{s['turn_dir']} на другое шоссе, ведущее в село {s['dest']}. "
        f"Есть и третий маршрут: в деревне {s['mid_village']} можно свернуть "
        f"на прямую тропинку в село {s['dest']}, которая идёт {s['pond_kind']}.</p>"
        f"<p>{s['road_kind'].capitalize()} и тропинка образуют с шоссе "
        f"прямоугольные треугольники.</p>"
    )
    img = (
        f'<img src="{plan_img}" alt="План населённых пунктов" '
        f'style="max-width:520px;display:block;margin:0.8em 0;">'
    )
    finale = (
        f"<p>По шоссе {s['hero']} с дедушкой едут со скоростью "
        f"<b>{speed_road} км/ч</b>, а по {s['road_kind_loc']} и тропинке — "
        f"со скоростью <b>{speed_path} км/ч</b>. На плане изображено взаимное "
        f"расположение населённых пунктов, длина стороны каждой клетки равна "
        f"<b>{cell_km} км</b>.</p>"
    )
    return intro + routes + img + finale


def t1_question(villages):
    """villages — список 3 названий с приставкой (например, ['с. Ольгино', 'д. Дивная', 'с. Ровное'])."""
    th = ''.join(
        f'<th style="border:1px solid #999;padding:0.4em 0.8em">{v}</th>' for v in villages
    )
    td = ''.join(
        '<td style="border:1px solid #999;padding:0.6em;min-width:5em">&nbsp;</td>'
        for _ in villages
    )
    return (
        '<p>Пользуясь описанием, определите, какими цифрами на плане '
        'обозначены населённые пункты. Заполните таблицу: в ответе запишите '
        'последовательность цифр без пробелов, запятых и других символов.</p>'
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<thead><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Насел. пункты</th>'
        + th + '</tr></thead>'
        '<tbody><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Цифры</th>'
        + td + '</tr></tbody></table>'
    )


def t2_question(src, dst, via):
    return (
        f"<p>Сколько километров проедут по шоссе от {src} до {dst}, "
        f"если поедут через {via}?</p>"
    )


def t3_question(src, dst):
    return (
        f"<p>Найдите расстояние от {src} до {dst} по прямой. "
        f"Ответ дайте в километрах.</p>"
    )


def t4_question_route(src, dst, route_desc):
    return (
        f"<p>Сколько минут затратят на дорогу из {src} в {dst}, "
        f"если поедут {route_desc}?</p>"
    )


def t5_table_html(headers, rows):
    """Таблица товаров и цен.
    headers — ['с. Ольгино', 'д. Дивная', ...] (4 магазина)
    rows — [(name, [p1, p2, p3, p4]), ...]
    """
    th = ''.join(
        f'<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">{h}</th>'
        for h in headers
    )
    body = ''
    for name, prices in rows:
        cells = ''.join(
            f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:right">{p}</td>'
            for p in prices
        )
        body += (
            f'<tr><td style="border:1px solid #999;padding:0.3em 0.6em">{name}</td>'
            f'{cells}</tr>'
        )
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.95em">'
        '<thead><tr>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Наименование продукта</th>'
        + th + '</tr></thead>'
        f'<tbody>{body}</tbody></table>'
    )


def t5_cheapest_question(table_html, products_text):
    return (
        "<p>В таблице указана стоимость (в рублях) некоторых продуктов в четырёх "
        "магазинах, расположенных в указанных населённых пунктах.</p>"
        + table_html +
        f"<p>{products_text} В каком магазине такой набор продуктов будет стоить "
        f"<b>дешевле всего</b>? В ответ запишите стоимость данного набора в этом магазине.</p>"
    )


def deploy(gid, group_title, context_html, tasks, stdout):
    """tasks — список dict с question_html, answer, t_type, tid."""
    course = Course.objects.get(slug="oge-maths")
    module, _ = Module.objects.get_or_create(
        course=course, title="Задания 1-5",
        defaults={"order": 0, "description": ""},
    )
    lesson, _ = Lesson.objects.get_or_create(
        module=module, title=LESSON_TITLE,
        defaults={"lesson_type": "practice", "order": 7,
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
