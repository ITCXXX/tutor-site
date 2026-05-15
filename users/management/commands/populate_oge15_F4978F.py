# -*- coding: utf-8 -*-
"""Группа F4978F — Тарифы мобильной связи (новый топик). 30 задач."""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


LESSON_TITLE = "Тарифы"
GROUP_TITLE = "F4978F · Мобильная связь (Стандартный)"
FIPI_GROUP_ID = "F4978F"
FIPI_CTX_ID = "F11B03C0C0F5A4F143C07E4B1019ADF8"
IMG_PATH = "/media/oge15/oge15_F4978F.png"


# ===== КОНТЕКСТ =====
CONTEXT_HTML = """
<p>На рисунке точками показано количество минут исходящих вызовов
и трафик мобильного интернета в гигабайтах, израсходованных абонентом
в процессе пользования смартфоном, за каждый месяц 2019 года.
Для удобства точки, соответствующие минутам и гигабайтам, соединены
сплошными и пунктирными линиями соответственно.</p>

<img src="__IMG_PATH__" alt="График минут и трафика по месяцам 2019 года"
     style="max-width:560px;display:block;margin:0.8em auto;">

<p>В течение года абонент пользовался тарифом <b>«Стандартный»</b>,
абонентская плата по которому составляла <b>350 рублей в месяц</b>.
При условии нахождения абонента на территории РФ в абонентскую плату
тарифа «Стандартный» входит:</p>
<ul>
  <li>пакет минут, включающий <b>300 минут</b> исходящих вызовов на номера,
      зарегистрированные на территории РФ;</li>
  <li>пакет интернета, включающий <b>3 гигабайта</b> мобильного интернета;</li>
  <li>пакет SMS, включающий <b>120 SMS</b> в месяц;</li>
  <li>безлимитные бесплатные входящие вызовы.</li>
</ul>

<p>Стоимость минут, интернета и SMS сверх пакета тарифа указана в таблице.</p>

<table style="border-collapse:collapse;margin:0.5em 0">
  <tr><td style="border:1px solid #999;padding:0.4em 0.7em">Исходящие вызовы</td>
      <td style="border:1px solid #999;padding:0.4em 0.7em">3 руб./мин.</td></tr>
  <tr><td style="border:1px solid #999;padding:0.4em 0.7em">Мобильный интернет (пакет)</td>
      <td style="border:1px solid #999;padding:0.4em 0.7em">90 руб. за 0,5 ГБ</td></tr>
  <tr><td style="border:1px solid #999;padding:0.4em 0.7em">SMS</td>
      <td style="border:1px solid #999;padding:0.4em 0.7em">2 руб./шт.</td></tr>
</table>

<p>Абонент не пользовался услугами связи в роуминге.
За весь год абонент отправил <b>110 SMS</b>.</p>
""".strip().replace("__IMG_PATH__", IMG_PATH)


# ===== ХЕЛПЕРЫ =====
def _match_table(header_label, values, unit_label="Номер месяца"):
    """Таблица для задач 1-6: верх — значения трафика/минут, низ — пустые ячейки."""
    head_cells = "".join(
        '<th style="border:1px solid #999;padding:0.4em 0.7em">{}</th>'.format(v)
        for v in values
    )
    body_cells = "".join(
        '<td style="border:1px solid #999;padding:0.6em;min-width:4em">&nbsp;</td>'
        for _ in values
    )
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<thead><tr><th style="border:1px solid #999;padding:0.4em 0.7em;background:#eef">{0}</th>'
        '{1}</tr></thead>'
        '<tbody><tr><th style="border:1px solid #999;padding:0.4em 0.7em;background:#eef">{2}</th>'
        '{3}</tr></tbody>'
        '</table>'
    ).format(header_label, head_cells, unit_label, body_cells)


def _match_q(kind, values):
    """Текст задачи 1-6."""
    if kind == "internet":
        title = ("Определите, какие месяцы соответствуют указанному в таблице "
                 "трафику мобильного интернета.")
        head = "Мобильный интернет"
    else:
        title = ("Определите, какие месяцы соответствуют указанному в таблице "
                 "количеству минут исходящих вызовов.")
        head = "Исходящие вызовы"
    return (
        '<p>{0}</p>'
        '<p>Заполните таблицу, в бланк ответов перенесите числа, соответствующие '
        'номерам месяцев, без пробелов, запятых и других дополнительных символов '
        '(например, для месяцев май, январь, ноябрь, август в ответ нужно записать '
        'число <b>51118</b>).</p>'
        + _match_table(head, values)
    ).format(title)


def _tariff_table(price, sms_pack, internet_per):
    """Таблица для задач 25-28 (новый тариф)."""
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Стоимость перехода на тариф</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">0 руб.</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Абонентская плата в месяц</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em"><b>{price} руб.</b></td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Пакет исходящих вызовов</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">400 минут</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Пакет мобильного интернета</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">4 ГБ</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Пакет SMS</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">{sms} SMS</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Входящие вызовы</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">0 руб./мин.</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Исходящие вызовы (сверх пакета)</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">4 руб./мин.</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">Мобильный интернет (сверх пакета)</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">{per} руб. за 0,5 ГБ</td></tr>'
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">SMS (сверх пакета)</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">2 руб./шт.</td></tr>'
        '</table>'
    ).format(price=price, sms=sms_pack, per=internet_per)


def _tariff_q(price, sms_pack, internet_per):
    return (
        '<p>В конце 2019 года оператор связи предложил абоненту перейти '
        'на новый тариф, условия которого приведены в таблице.</p>'
        + _tariff_table(price, sms_pack, internet_per) +
        '<p>Абонент решает, перейти ли ему на новый тариф, посчитав, '
        'сколько бы он потратил на услуги связи за 2019&nbsp;г., если бы '
        'пользовался им. Если получится меньше, чем он потратил фактически '
        'за 2019&nbsp;г., то абонент примет решение сменить тариф.</p>'
        '<p><b>Перейдёт ли абонент на новый тариф?</b> В ответе запишите '
        'ежемесячную абонентскую плату по тарифу, который выберет абонент '
        'на 2020 год.</p>'
    )


def _home_internet_table(plans):
    """plans = list of (name, fee, per_mb)."""
    rows = "".join(
        '<tr><td style="border:1px solid #999;padding:0.4em 0.7em">«{0}»</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">{1}</td>'
        '<td style="border:1px solid #999;padding:0.4em 0.7em">{2}</td></tr>'.format(n, f, p)
        for n, f, p in plans
    )
    return (
        '<table style="border-collapse:collapse;margin:0.5em 0">'
        '<thead><tr>'
        '<th style="border:1px solid #999;padding:0.4em 0.7em;background:#eef">Тарифный план</th>'
        '<th style="border:1px solid #999;padding:0.4em 0.7em;background:#eef">Абонентская плата</th>'
        '<th style="border:1px solid #999;padding:0.4em 0.7em;background:#eef">Плата за трафик</th>'
        '</tr></thead><tbody>'
        + rows + '</tbody></table>'
    )


def _home_q(plans, traffic_mb):
    return (
        '<p>Помимо мобильного интернета, абонент использует домашний интернет '
        'от провайдера «Омега». Этот интернет-провайдер предлагает три тарифных '
        'плана. Условия приведены в таблице.</p>'
        + _home_internet_table(plans) +
        '<p>Абонент предполагает, что трафик составит <b>{0}&nbsp;Мб</b> в месяц, '
        'и выбирает наиболее дешёвый тарифный план. Сколько рублей должен будет '
        'заплатить абонент за месяц, если трафик действительно будет равен {0}&nbsp;Мб?</p>'
    ).format(traffic_mb)


# ===== ЗАДАЧИ =====
TASKS = [
    # --- Задачи 1-3: соответствие месяцев — трафик интернета ---
    {"no": 1, "tid": "061534", "t_type": "T1",
     "question_html": _match_q("internet", ["1 ГБ", "3 ГБ", "3,25 ГБ", "1,5 ГБ"]),
     "answer": "76108"},
    {"no": 2, "tid": "B86331", "t_type": "T1",
     "question_html": _match_q("internet", ["1,5 ГБ", "2 ГБ", "3,75 ГБ", "1 ГБ"]),
     "answer": "83117"},
    {"no": 3, "tid": "E4697C", "t_type": "T1",
     "question_html": _match_q("internet", ["2 ГБ", "2,25 ГБ", "4 ГБ", "3,5 ГБ"]),
     "answer": "31242"},

    # --- Задачи 4-6: соответствие месяцев — минуты исходящих ---
    {"no": 4, "tid": "936D7F", "t_type": "T1",
     "question_html": _match_q("minutes", ["150 мин.", "300 мин.", "175 мин.", "375 мин."]),
     "answer": "3517"},
    {"no": 5, "tid": "9CC7A4", "t_type": "T1",
     "question_html": _match_q("minutes", ["175 мин.", "300 мин.", "275 мин.", "150 мин."]),
     "answer": "1523"},
    {"no": 6, "tid": "F83A90", "t_type": "T1",
     "question_html": _match_q("minutes", ["375 мин.", "150 мин.", "275 мин.", "300 мин."]),
     "answer": "7325"},

    # --- Задачи 7-12: сколько потратил в месяц (рубли) ---
    {"no": 7, "tid": "BBE7E8", "t_type": "T2",
     "question_html": "<p>Сколько рублей потратил абонент на услуги связи в <b>феврале</b>?</p>",
     "answer": "440"},
    {"no": 8, "tid": "ED661A", "t_type": "T2",
     "question_html": "<p>Сколько рублей потратил абонент на услуги связи в <b>июне</b>?</p>",
     "answer": "425"},
    {"no": 9, "tid": "230DD7", "t_type": "T2",
     "question_html": "<p>Сколько рублей потратил абонент на услуги связи в <b>июле</b>?</p>",
     "answer": "575"},
    {"no": 10, "tid": "AF4CEB", "t_type": "T2",
     "question_html": "<p>Сколько рублей потратил абонент на услуги связи в <b>августе</b>?</p>",
     "answer": "425"},
    {"no": 11, "tid": "1A9F7F", "t_type": "T2",
     "question_html": "<p>Сколько рублей потратил абонент на услуги связи в <b>апреле</b>?</p>",
     "answer": "680"},
    {"no": 12, "tid": "0CA240", "t_type": "T2",
     "question_html": "<p>Сколько рублей потратил абонент на услуги связи в <b>декабре</b>?</p>",
     "answer": "500"},

    # --- Задачи 13-16: подсчёт месяцев по условию ---
    {"no": 13, "tid": "5BD1CC", "t_type": "T3",
     "question_html": "<p>Сколько месяцев в 2019 году абонент превысил лимит по пакету мобильного интернета?</p>",
     "answer": "4"},
    {"no": 14, "tid": "1FE758", "t_type": "T3",
     "question_html": "<p>Сколько месяцев в 2019 году абонент не превышал лимит ни по пакету минут, ни по пакету мобильного интернета?</p>",
     "answer": "4"},
    {"no": 15, "tid": "11F08D", "t_type": "T3",
     "question_html": "<p>Сколько месяцев в 2019 году абонент превысил лимит и по пакету минут, и по пакету мобильного интернета?</p>",
     "answer": "2"},
    {"no": 16, "tid": "2C48EC", "t_type": "T3",
     "question_html": "<p>Сколько месяцев в 2019 году расходы по тарифу составили ровно 350 рублей?</p>",
     "answer": "4"},

    # --- Задачи 17-18: минимумы ---
    {"no": 17, "tid": "E8BE80", "t_type": "T3",
     "question_html": "<p>Какое наименьшее количество минут исходящих вызовов за месяц было в 2019 году?</p>",
     "answer": "150"},
    {"no": 18, "tid": "0563D8", "t_type": "T3",
     "question_html": "<p>Какой наименьший трафик мобильного интернета в гигабайтах за месяц был в 2019 году?</p>",
     "answer": "1"},

    # --- Задачи 19-20: % увеличение трафика ---
    {"no": 19, "tid": "001035", "t_type": "T4",
     "question_html": "<p>На сколько процентов увеличился трафик мобильного интернета в <b>феврале</b> по сравнению с <b>январём</b> 2019 года?</p>",
     "answer": "40"},
    {"no": 20, "tid": "0F3538", "t_type": "T4",
     "question_html": "<p>На сколько процентов увеличился трафик мобильного интернета в <b>августе</b> по сравнению с <b>июлем</b> 2019 года?</p>",
     "answer": "50"},

    # --- Задачи 21-24: проценты на абонентскую плату ---
    {"no": 21, "tid": "DFCA35", "t_type": "T4",
     "question_html": "<p>Известно, что в 2018 году абонентская плата по тарифу «Стандартный» составляла <b>200 рублей</b>. На сколько процентов выросла абонентская плата в 2019 году по сравнению с 2018 годом?</p>",
     "answer": "75"},
    {"no": 22, "tid": "1CDEF9", "t_type": "T4",
     "question_html": "<p>Известно, что в 2019 году абонентская плата по тарифу «Стандартный» выросла на <b>75%</b> по сравнению с 2018 годом. Сколько рублей составляла абонентская плата в 2018 году?</p>",
     "answer": "200"},
    {"no": 23, "tid": "D80073", "t_type": "T4",
     "question_html": "<p>Известно, что в 2019 году абонентская плата по тарифу «Стандартный» снизилась на <b>30%</b> по сравнению с 2018 годом. Сколько рублей составляла абонентская плата в 2018 году?</p>",
     "answer": "500"},
    {"no": 24, "tid": "E3AFA5", "t_type": "T4",
     "question_html": "<p>В январе 2020 года абонентская плата по тарифу «Стандартный» повысилась и составила <b>490 рублей</b>. На сколько процентов повысилась абонентская плата?</p>",
     "answer": "40"},

    # --- Задачи 25-28: выбор тарифа ---
    {"no": 25, "tid": "47661F", "t_type": "T5",
     "question_html": _tariff_q(440, 120, 180),
     "answer": "440"},
    {"no": 26, "tid": "800087", "t_type": "T5",
     "question_html": _tariff_q(460, 130, 160),
     "answer": "350"},
    {"no": 27, "tid": "077973", "t_type": "T5",
     "question_html": _tariff_q(430, 120, 180),
     "answer": "430"},
    {"no": 28, "tid": "680B76", "t_type": "T5",
     "question_html": _tariff_q(470, 120, 160),
     "answer": "350"},

    # --- Задачи 29-30: домашний интернет «Омега» ---
    {"no": 29, "tid": "8DDF65", "t_type": "T5",
     "question_html": _home_q(
         plans=[("0", "Нет", "1,5 руб. за 1 Мб"),
                ("200", "204 руб. за 200 Мб трафика в месяц", "1,2 руб. за 1 Мб сверх 200 Мб"),
                ("700", "672 руб. за 700 Мб трафика в месяц", "0,5 руб. за 1 Мб сверх 700 Мб")],
         traffic_mb=700),
     "answer": "672"},
    {"no": 30, "tid": "9A1C92", "t_type": "T5",
     "question_html": _home_q(
         plans=[("0", "Нет", "1,1 руб. за 1 Мб"),
                ("300", "290 руб. за 300 Мб трафика в месяц", "1,2 руб. за 1 Мб сверх 300 Мб"),
                ("800", "930 руб. за 800 Мб трафика в месяц", "0,5 руб. за 1 Мб сверх 800 Мб")],
         traffic_mb=800),
     "answer": "880"},
]


class Command(BaseCommand):
    help = "Создаёт TaskGroup F4978F (Тарифы) — 30 подзадач"

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
            defaults={"lesson_type": "practice", "order": 9, "content": "", "is_free": False},
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
