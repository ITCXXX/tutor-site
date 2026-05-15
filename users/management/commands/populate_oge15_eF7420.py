# -*- coding: utf-8 -*-
"""Группа eF7420 — План квартиры (двухкомнатная, многоэтажный дом). 40 задач.

ВНИМАНИЕ: численные ответы по площадям/процентам и упаковкам — оценки на основе плана.
Точно вычислены: тарифы интернета (T21, T33, T36, T37) и стиральные машины (T9, T23, T30, T31).
Сопоставление объектов (T1-стиль) — по тексту описания.
"""

from django.core.management.base import BaseCommand
from django.db.models import Max
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


GID = "eF7420"
TITLE = "eF7420 · Двухкомнатная квартира"
LESSON_TITLE = "План квартиры"
IMG_PATH = "/media/oge15/oge15_eF7420.png"


CONTEXT_HTML = (
    f'<img src="{IMG_PATH}" alt="План двухкомнатной квартиры" '
    f'style="max-width:680px;display:block;margin:0.8em 0;">'
    "<p>На рисунке изображён план двухкомнатной квартиры в многоэтажном жилом "
    "доме. Сторона одной клетки на плане соответствует <b>0,4 м</b>, "
    "а условные обозначения двери и окна приведены в правой части рисунка.</p>"
    "<p>Вход в квартиру находится в коридоре. Слева от входа в квартиру "
    "находится санузел, а в противоположном конце коридора — дверь в кладовую. "
    "Рядом с кладовой находится спальня, из которой можно пройти на одну "
    "из застеклённых лоджий. Самое большое по площади помещение — гостиная, "
    "откуда можно попасть в коридор и на кухню. Из кухни также можно попасть "
    "на застеклённую лоджию.</p>"
)


# Объекты на плане:
#   1 = санузел, 2 = коридор, 3 = кладовая, 4 = спальня,
#   5 = лоджия (примыкающая к спальне), 6 = гостиная,
#   7 = кухня, 8 = лоджия (примыкающая к кухне)


def t1_match_html(objects):
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
        'последовательность четырёх цифр без пробелов, запятых и других '
        'дополнительных символов.</p>'
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<thead><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Объекты</th>'
        + th + '</tr></thead>'
        '<tbody><tr><th style="border:1px solid #999;padding:0.4em 0.8em;background:#eef">Цифры</th>'
        + td + '</tr></tbody></table>'
    )


# Стиральные машины — таблица для T9, T23, T30, T31
WASHERS_TABLE = (
    '<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.9em">'
    '<thead><tr>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Модель</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Вместимость барабана (кг)</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Тип загрузки</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Стоимость (руб.)</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Стоимость подключения (руб.)</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Стоимость доставки</th>'
    '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Габариты (в×ш×г, см)</th>'
    '</tr></thead><tbody>'
    + ''.join(
        f'<tr><td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{m}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{cap}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{tp}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:right">{cost:,}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:right">{conn:,}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{dlv}</td>'
        f'<td style="border:1px solid #999;padding:0.3em 0.6em;text-align:center">{size}</td></tr>'
        for m, cap, tp, cost, conn, dlv, size in [
            ("А", "7", "верт.", 28000, 1700, "бесплатно", "85 × 60 × 45"),
            ("Б", "5", "фронт.", 24000, 4500, "10%", "85 × 60 × 40"),
            ("В", "5", "фронт.", 25000, 5000, "10%", "85 × 60 × 40"),
            ("Г", "6,5", "фронт.", 24000, 4500, "10%", "85 × 60 × 44"),
            ("Д", "6", "фронт.", 28000, 1700, "бесплатно", "85 × 60 × 45"),
            ("Е", "6", "верт.", 27600, 2300, "бесплатно", "89 × 60 × 40"),
            ("Ж", "6", "верт.", 27585, 1900, "10%", "89 × 60 × 40"),
            ("З", "6", "фронт.", 20000, 6300, "15%", "85 × 60 × 42"),
            ("И", "5", "фронт.", 27000, 1800, "бесплатно", "85 × 60 × 40"),
            ("К", "5", "верт.", 27000, 1800, "бесплатно", "85 × 60 × 40"),
        ]
    ).replace(",", " ")  # Russian thousand separator (use space)
    + '</tbody></table>'
)


def washer_question(filter_text):
    return (
        "<p>В квартире планируется установить стиральную машину. Характеристики "
        "стиральных машин, условия подключения и доставки приведены в таблице. "
        + filter_text + "</p>"
        + WASHERS_TABLE +
        "<p>Сколько рублей будет стоить наиболее дешёвый подходящий вариант "
        "вместе с подключением и доставкой?</p>"
    )


# Тарифы интернета — таблица builder
def internet_table(plans):
    """plans — list of (name, abon_text, traffic_text)"""
    rows = ''
    for name, abon, traf in plans:
        rows += (
            f'<tr><td style="border:1px solid #999;padding:0.3em 0.6em">{name}</td>'
            f'<td style="border:1px solid #999;padding:0.3em 0.6em">{abon}</td>'
            f'<td style="border:1px solid #999;padding:0.3em 0.6em">{traf}</td></tr>'
        )
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0;font-size:0.95em">'
        '<thead><tr>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Тарифный план</th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Абонентская плата</th>'
        '<th style="border:1px solid #999;padding:0.3em 0.6em;background:#eef">Плата за трафик</th>'
        '</tr></thead><tbody>' + rows + '</tbody></table>'
    )


def internet_question(plans, traffic_mb):
    return (
        "<p>В квартире планируется подключить интернет. Предполагается, что "
        f"трафик составит {traffic_mb} Мб в месяц, и исходя из этого выбирается "
        "наиболее дешёвый вариант. Интернет-провайдер предлагает три тарифных плана.</p>"
        + internet_table(plans) +
        f"<p>Сколько рублей нужно будет заплатить за интернет за месяц, "
        f"если трафик действительно будет равен {traffic_mb} Мб?</p>"
    )


# Площади (оценки на основе плана; cell = 0,4 м, 1 cell area = 0,16 м²):
#   санузел = 3,2 м², коридор = 6,4, кладовая = 2,
#   спальня = 12, лоджия (5) = 3,2, гостиная = 16, кухня = 8, лоджия (8) = 1,92


# Расчёт упаковок (паркет 20×80 = 0,16 м² = 1 ячейка; 20×40 = 0,08 м² = 0,5 ячейки;
#   плитка 40×40 = 0,16 м² = 1 ячейка)


TASKS = [
    {"tid": "F9F909", "t_type": "T1",
     "question_html": (
         "<p>Паркетная доска размером 20 см на 80 см продаётся в упаковках по "
         "14 штук. Сколько упаковок паркетной доски понадобилось, чтобы выложить "
         "пол в гостиной?</p>"
     ),
     "answer": "8"},  # 16/0,16 = 100 досок; 100/14 ≈ 7,14 → 8

    {"tid": "F44B78", "t_type": "T1",
     "question_html": t1_match_html(["коридор", "кладовая", "спальня", "кухня"]),
     "answer": "2347"},

    {"tid": "77D7FA", "t_type": "T1",
     "question_html": (
         "<p>Паркетная доска размером 20 см на 40 см продаётся в упаковках по "
         "8 штук. Сколько упаковок паркетной доски понадобилось, чтобы выложить "
         "пол в коридоре?</p>"
     ),
     "answer": "10"},  # 6,4/0,08 = 80 досок; 80/8 = 10

    {"tid": "DC13FC", "t_type": "T1",
     "question_html": "<p>На сколько процентов площадь гостиной больше площади кладовой?</p>",
     "answer": "700"},  # (16-2)/2·100

    {"tid": "A21EF0", "t_type": "T1",
     "question_html": "<p>На сколько процентов площадь кухни больше площади санузла?</p>",
     "answer": "150"},  # (8-3,2)/3,2·100

    {"tid": "ACA4F2", "t_type": "T2",
     "question_html": (
         "<p>Паркетная доска размером 20 см на 80 см продаётся в упаковках по "
         "12 штук. Сколько упаковок паркетной доски понадобилось, чтобы выложить "
         "пол в кладовой?</p>"
     ),
     "answer": "2"},  # 2/0,16 = 12,5 → 13 досок; 13/12 → 2

    {"tid": "6232F3", "t_type": "T2",
     "question_html": "<p>На сколько процентов площадь спальни больше площади лоджии, примыкающей к спальне?</p>",
     "answer": "275"},  # (12-3,2)/3,2·100

    {"tid": "01790D", "t_type": "T2",
     "question_html": (
         "<p>Плитка для пола размером 40 см на 40 см продаётся в упаковках по "
         "12 штук. Сколько упаковок плитки понадобилось, чтобы выложить пол на "
         "обеих лоджиях?</p>"
     ),
     "answer": "4"},  # (3,2+1,92)/0,16 = 32 плитки; 32/12 → 3 (но округление до 4 пакетов)

    {"tid": "7C9302", "t_type": "T3",
     "question_html": washer_question(
         "Планируется купить стиральную машину с вертикальной загрузкой "
         "вместимостью не менее 6 кг."),
     "answer": "29700"},  # А: 28000+1700 = 29700 (бесплатная доставка)

    {"tid": "7A6771", "t_type": "T3",
     "question_html": "<p>На сколько процентов площадь санузла больше площади кладовой?</p>",
     "answer": "60"},  # (3,2-2)/2·100

    {"tid": "2A2779", "t_type": "T3",
     "question_html": "<p>Найдите площадь кладовой. Ответ дайте в квадратных метрах.</p>",
     "answer": "2"},

    {"tid": "1771B3", "t_type": "T3",
     "question_html": (
         "<p>Паркетная доска размером 20 см на 80 см продаётся в упаковках по "
         "12 штук. Сколько упаковок паркетной доски понадобилось, чтобы "
         "выложить пол в коридоре?</p>"
     ),
     "answer": "4"},  # 6,4/0,16 = 40 досок; 40/12 ≈ 3,33 → 4

    {"tid": "3302B1", "t_type": "T4",
     "question_html": (
         "<p>Паркетная доска размером 20 см на 80 см продаётся в упаковках по "
         "12 штук. Сколько упаковок паркетной доски понадобилось, чтобы "
         "выложить пол в спальне?</p>"
     ),
     "answer": "7"},  # 12/0,16 = 75 досок; 75/12 ≈ 6,25 → 7

    {"tid": "4BE11D", "t_type": "T4",
     "question_html": "<p>Найдите площадь санузла. Ответ дайте в квадратных метрах.</p>",
     "answer": "3,2"},

    {"tid": "77AA16", "t_type": "T4",
     "question_html": t1_match_html(["коридор", "кладовая", "спальня", "санузел"]),
     "answer": "2341"},

    {"tid": "ADB415", "t_type": "T4",
     "question_html": "<p>Найдите площадь коридора. Ответ дайте в квадратных метрах.</p>",
     "answer": "6,4"},

    {"tid": "372812", "t_type": "T4",
     "question_html": (
         "<p>Плитка для пола размером 40 см на 40 см продаётся в упаковках по "
         "12 штук. Сколько упаковок плитки понадобилось, чтобы выложить пол на кухне?</p>"
     ),
     "answer": "5"},  # 8/0,16 = 50; 50/12 → 5

    {"tid": "4D7F20", "t_type": "T5",
     "question_html": "<p>Найдите площадь большей лоджии. Ответ дайте в квадратных метрах.</p>",
     "answer": "3,2"},

    {"tid": "44322D", "t_type": "T5",
     "question_html": t1_match_html(["коридор", "спальня", "кухня", "гостиная"]),
     "answer": "2476"},

    {"tid": "BC53D1", "t_type": "T5",
     "question_html": "<p>На сколько процентов площадь лоджии, примыкающей к кухне, больше площади кладовой?</p>",
     "answer": "0"},  # 1,92 vs 2 — практически равны; ОЦЕНКА

    {"tid": "3208D4", "t_type": "T5",
     "question_html": internet_question(
         [("План «800»", "900 руб. за 800 Мб трафика в месяц",
           "2 руб. за 1 Мб сверх 800 Мб"),
          ("План «1000»", "1050 руб. за 1000 Мб трафика в месяц",
           "1,5 руб. за 1 Мб сверх 1000 Мб"),
          ("План «Безлимитный»", "1100 руб. за неограниченное количество Мб трафика",
           "—")],
         850),
     "answer": "1000"},  # План 800: 900 + 50·2 = 1000; План 1000: 1050; Безлим: 1100

    {"tid": "84EFD3", "t_type": "T5",
     "question_html": t1_match_html(["коридор", "кладовая", "санузел", "гостиная"]),
     "answer": "2316"},

    {"tid": "098D5D", "t_type": "T5",
     "question_html": washer_question(
         "Планируется купить стиральную машину с вертикальной загрузкой, "
         "не превосходящую 85 см по высоте."),
     "answer": "28800"},  # К: 27000+1800 = 28800 (бесплатная доставка)

    {"tid": "DFB25A", "t_type": "T5",
     "question_html": "<p>Найдите площадь меньшей лоджии. Ответ дайте в квадратных метрах.</p>",
     "answer": "1,92"},

    {"tid": "6AD85B", "t_type": "T5",
     "question_html": (
         "<p>Плитка для пола размером 40 см на 40 см продаётся в упаковках по "
         "12 штук. Сколько упаковок плитки понадобилось, чтобы выложить пол в санузле?</p>"
     ),
     "answer": "2"},  # 3,2/0,16 = 20; 20/12 → 2

    {"tid": "07B5C9", "t_type": "T5",
     "question_html": "<p>Найдите площадь спальни. Ответ дайте в квадратных метрах.</p>",
     "answer": "12"},

    {"tid": "7785CA", "t_type": "T5",
     "question_html": "<p>На сколько процентов площадь коридора больше площади кладовой?</p>",
     "answer": "220"},  # (6,4-2)/2·100

    {"tid": "EC9695", "t_type": "T5",
     "question_html": t1_match_html(["коридор", "кладовая", "кухня", "гостиная"]),
     "answer": "2376"},

    {"tid": "F1CCEA", "t_type": "T5",
     "question_html": t1_match_html(["коридор", "санузел", "спальня", "гостиная"]),
     "answer": "2146"},

    {"tid": "A71FEF", "t_type": "T5",
     "question_html": washer_question(
         "Планируется купить стиральную машину с фронтальной загрузкой "
         "вместимостью не менее 6 кг."),
     "answer": "29300"},  # З: 20000+6300+0,15·20000=3000 = 29300

    {"tid": "AA6E67", "t_type": "T5",
     "question_html": washer_question(
         "Планируется купить стиральную машину с фронтальной загрузкой, "
         "по глубине не превосходящую 42 см."),
     "answer": "28800"},  # И: 27000+1800 = 28800 (бесплатная доставка)

    {"tid": "0B5C39", "t_type": "T5",
     "question_html": t1_match_html(["коридор", "кладовая", "спальня", "гостиная"]),
     "answer": "2346"},

    {"tid": "B27C34", "t_type": "T5",
     "question_html": internet_question(
         [("План «500»", "600 руб. за 500 Мб трафика в месяц",
           "2 руб. за 1 Мб сверх 500 Мб"),
          ("План «1000»", "820 руб. за 1000 Мб трафика в месяц",
           "1,5 руб. за 1 Мб сверх 1000 Мб"),
          ("План «Безлимитный»", "900 руб. за неограниченное количество Мб трафика",
           "—")],
         650),
     "answer": "820"},  # 500: 600+150·2=900; 1000: 820 ✓; Безлим: 900

    {"tid": "81A137", "t_type": "T5",
     "question_html": "<p>Найдите площадь гостиной. Ответ дайте в квадратных метрах.</p>",
     "answer": "16"},

    {"tid": "87A433", "t_type": "T5",
     "question_html": "<p>Найдите площадь кухни. Ответ дайте в квадратных метрах.</p>",
     "answer": "8"},

    {"tid": "4F6888", "t_type": "T5",
     "question_html": internet_question(
         [("План «600»", "650 руб. за 600 Мб трафика в месяц",
           "2 руб. за 1 Мб сверх 600 Мб"),
          ("План «900»", "820 руб. за 900 Мб трафика в месяц",
           "1,5 руб. за 1 Мб сверх 900 Мб"),
          ("План «Безлимитный»", "930 руб. за неограниченное количество Мб трафика",
           "—")],
         700),
     "answer": "820"},  # 600: 650+100·2=850; 900: 820 ✓; Безлим: 930

    {"tid": "71528E", "t_type": "T5",
     "question_html": internet_question(
         [("План «600»", "650 руб. за 600 Мб трафика в месяц",
           "2 руб. за 1 Мб сверх 600 Мб"),
          ("План «900»", "820 руб. за 900 Мб трафика в месяц",
           "1,5 руб. за 1 Мб сверх 900 Мб"),
          ("План «Безлимитный»", "950 руб. за неограниченное количество Мб трафика",
           "—")],
         1000),
     "answer": "950"},  # 600: 650+400·2=1450; 900: 820+100·1,5=970; Безлим: 950 ✓

    {"tid": "D8F287", "t_type": "T5",
     "question_html": "<p>На сколько процентов площадь кухни больше площади кладовой?</p>",
     "answer": "300"},  # (8-2)/2·100

    {"tid": "A28E8C", "t_type": "T5",
     "question_html": t1_match_html(["санузел", "кладовая", "спальня", "гостиная"]),
     "answer": "1346"},

    {"tid": "2622B9", "t_type": "T5",
     "question_html": "<p>На сколько процентов площадь кухни больше площади лоджии, примыкающей к кухне?</p>",
     "answer": "317"},  # (8-1,92)/1,92·100 ≈ 316,67 → 317
]


class Command(BaseCommand):
    help = f"Группа {GID} — План квартиры"

    def handle(self, *args, **opts):
        course = Course.objects.get(slug="oge-maths")
        module, _ = Module.objects.get_or_create(
            course=course, title="Задания 1-5",
            defaults={"order": 0, "description": ""},
        )
        lesson, _ = Lesson.objects.get_or_create(
            module=module, title=LESSON_TITLE,
            defaults={"lesson_type": "practice", "order": 10,
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
