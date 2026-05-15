# -*- coding: utf-8 -*-
"""Группа E4DF9C — Дороги (Васильково → Иваново, Саша велосипед, магазин). 10 задач."""

from django.core.management.base import BaseCommand
from ._oge15_dorogi import (
    build_context_html, t1_question, t2_question, t3_question,
    t4_question_route, t5_table_html, t5_cheapest_question, deploy,
)


GID = "E4DF9C"
TITLE = "E4DF9C · Васильково → Иваново (велосипед, магазин)"
IMG_PATH = "/media/oge15/oge15_E4DF9C.png"

# Геометрия (1 кл = 1 км):
#   4 = д. Васильково (старт), 3 = д. Камышино (на шоссе), 1 = д. Журавушка (поворот направо),
#   2 = с. Иваново (цель). Вас-Кам-Жур колинеарны (вертикальная сторона).
# Triangle (8, 15, 17): Вас-Жур = 15, Жур-Иван = 8, Hyp Вас-Иван = 17.
# Камышино: Кам-Жур = 6, Вас-Кам = 9 → тропинка Кам-Иван = √(6²+8²) = 10.
SPEED_ROAD, SPEED_PATH = 20, 15

STORY = {
    "hero": "Саша",
    "week_day": "субботу",
    "src_village": "Васильково",
    "mid_village": "Камышино",
    "corner_village": "Журавушка",
    "corner_kind": "деревня",
    "dest": "Иваново",
    "dest_purpose": "в магазин",
    "route_kind": "велосипедах",
    "road_kind": "лесной дорожке",
    "road_kind_loc": "лесной дорожке",
    "turn_dir": "направо",
    "pond_kind": "мимо пруда",
}

CONTEXT_HTML = build_context_html(STORY, IMG_PATH, SPEED_ROAD, SPEED_PATH, 1)

PRICES_HEADERS = ["д. Васильково", "с. Иваново", "д. Камышино", "д. Журавушка"]
PRICES_ALL = [
    ("Молоко (1 л)", [35, 34, 33, 31]),
    ("Хлеб (1 батон)", [28, 25, 30, 24]),
    ("Сыр «Российский» (1 кг)", [270, 260, 310, 220]),
    ("Говядина (1 кг)", [390, 420, 400, 380]),
    ("Картофель (1 кг)", [16, 24, 20, 22]),
]

# T9: 2 л молока + 3 кг говядины + 2 кг картофеля
#   Вас: 70+1170+32=1272; Иван: 68+1260+48=1376; Кам: 66+1200+40=1306; Жур: 62+1140+44=1246 ✓
T9_ANSWER = "1246"

# T10: 3 батона + 2 кг сыра + 2 кг говядины
#   Вас: 84+540+780=1404; Иван: 75+520+840=1435; Кам: 90+620+800=1510; Жур: 72+440+760=1272 ✓
T10_ANSWER = "1272"

TASKS = [
    {"tid": "0822A3", "t_type": "T1",
     "question_html": t1_question(["д. Васильково", "с. Иваново", "д. Камышино"]),
     "answer": "423"},
    {"tid": "E579DF", "t_type": "T1",
     "question_html": t1_question(["д. Журавушка", "д. Камышино", "с. Иваново"]),
     "answer": "132"},

    {"tid": "C94FAE", "t_type": "T2",
     "question_html": t2_question("деревни Васильково", "села Иваново", "деревню Журавушка"),
     "answer": "23"},
    {"tid": "552351", "t_type": "T2",
     "question_html": t2_question("деревни Камышино", "села Иваново", "деревню Журавушка"),
     "answer": "14"},

    {"tid": "F5292D", "t_type": "T3",
     "question_html": t3_question("деревни Васильково", "села Иваново"),
     "answer": "17"},
    {"tid": "37226A", "t_type": "T3",
     "question_html": t3_question("деревни Камышино", "села Иваново"),
     "answer": "10"},

    {"tid": "E64C0D", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Васильково", "село Иваново", "по прямой лесной дорожке"),
     "answer": "68"},  # 17/15·60 = 68 мин
    {"tid": "26AFA2", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Васильково", "село Иваново",
         "сначала по шоссе, а затем свернут в Камышино на прямую тропинку, "
         "которая проходит мимо пруда"),
     "answer": "67"},  # 9/20·60 + 10/15·60 = 27 + 40 = 67 мин

    {"tid": "FD71FF", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Саша с дедушкой хотят купить 2 л молока, 3 кг говядины и 2 кг картофеля."),
     "answer": T9_ANSWER},
    {"tid": "CA483A", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Саша с дедушкой хотят купить 3 батона хлеба, 2 кг сыра «Российский» и 2 кг говядины."),
     "answer": T10_ANSWER},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Дороги (Васильково → Иваново)"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, CONTEXT_HTML, TASKS, self.stdout)
