# -*- coding: utf-8 -*-
"""Группа 650747 — Дороги (Масловка → Захарово, Саша велосипед). 10 задач."""

from django.core.management.base import BaseCommand
from ._oge15_dorogi import (
    build_context_html, t1_question, t2_question, t3_question,
    t4_question_route, t5_table_html, t5_cheapest_question, deploy,
)


GID = "650747"
TITLE = "650747 · Масловка → Захарово (велосипед, магазин)"
IMG_PATH = "/media/oge15/oge15_650747.png"

# Геометрия (1 кл = 1 км):
#   1 = д. Масловка (старт), 2 = д. Вёсенка (на шоссе), 3 = д. Полянка (поворот),
#   4 = с. Захарово (цель). Масл-Вёс-Пол колинеарны (вертикальная сторона).
# Triangle (9, 12, 15): Масл-Пол = 9, Пол-Зах = 12, Hyp Масл-Зах = 15.
# Вёсенка: Вёс-Пол = 5, Масл-Вёс = 4 → тропинка Вёс-Зах = √(5²+12²) = 13 (5,12,13).
SPEED_ROAD, SPEED_PATH = 20, 15

STORY = {
    "hero": "Саша",
    "week_day": "субботу",
    "src_village": "Масловка",
    "mid_village": "Вёсенка",
    "corner_village": "Полянка",
    "corner_kind": "деревня",
    "dest": "Захарово",
    "dest_purpose": "в магазин",
    "route_kind": "велосипедах",
    "road_kind": "лесной дорожке",
    "road_kind_loc": "лесной дорожке",
    "turn_dir": "направо",
    "pond_kind": "мимо пруда",
}

CONTEXT_HTML = build_context_html(STORY, IMG_PATH, SPEED_ROAD, SPEED_PATH, 1)

PRICES_HEADERS = ["д. Масловка", "с. Захарово", "д. Вёсенка", "д. Полянка"]
PRICES_ALL = [
    ("Молоко (1 л)", [45, 40, 42, 52]),
    ("Хлеб (1 батон)", [29, 28, 31, 22]),
    ("Сыр «Российский» (1 кг)", [250, 270, 290, 280]),
    ("Говядина (1 кг)", [350, 380, 360, 390]),
    ("Картофель (1 кг)", [35, 25, 32, 24]),
]

# T9: 2 л молока + 2 кг говядины + 4 кг картофеля.
#   Масл: 90+700+140=930 ✓; Зах: 80+760+100=940; Вёс: 84+720+128=932; Пол: 104+780+96=980
T9_ANSWER = "930"

# T10: 3 батона хлеба + 2 кг сыра + 5 кг картофеля.
#   Масл: 87+500+175=762; Зах: 84+540+125=749; Вёс: 93+580+160=833; Пол: 66+560+120=746 ✓
T10_ANSWER = "746"

TASKS = [
    {"tid": "C9CC62", "t_type": "T1",
     "question_html": t1_question(["д. Масловка", "с. Захарово", "д. Вёсенка"]),
     "answer": "142"},
    {"tid": "AFAE7D", "t_type": "T1",
     "question_html": t1_question(["д. Полянка", "с. Захарово", "д. Вёсенка"]),
     "answer": "342"},

    {"tid": "47CB29", "t_type": "T2",
     "question_html": t2_question("деревни Масловка", "села Захарово", "деревню Полянка"),
     "answer": "21"},  # 9+12
    {"tid": "256E4B", "t_type": "T2",
     "question_html": t2_question("деревни Вёсенка", "села Захарово", "деревню Полянка"),
     "answer": "17"},  # 5+12

    {"tid": "0F3619", "t_type": "T3",
     "question_html": t3_question("деревни Масловка", "села Захарово"),
     "answer": "15"},  # √(9²+12²) = 15
    {"tid": "00194F", "t_type": "T3",
     "question_html": t3_question("деревни Вёсенка", "села Захарово"),
     "answer": "13"},  # √(5²+12²) = 13

    {"tid": "0B1AFD", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Масловка", "село Захарово", "по прямой лесной дорожке"),
     "answer": "60"},  # 15/15·60 = 60 мин
    {"tid": "F5D8CA", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Масловка", "село Захарово",
         "сначала по шоссе, а затем свернут в деревне Вёсенка на прямую тропинку, "
         "которая проходит мимо пруда"),
     "answer": "64"},  # 4/20·60 + 13/15·60 = 12 + 52 = 64 мин

    {"tid": "EFAD85", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Саша с дедушкой хотят купить 2 л молока, 2 кг говядины и 4 кг картофеля."),
     "answer": T9_ANSWER},
    {"tid": "8061BC", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Саша с дедушкой хотят купить 3 батона хлеба, 2 кг сыра «Российский» и "
         "5 кг картофеля."),
     "answer": T10_ANSWER},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Дороги (Масловка → Захарово)"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, CONTEXT_HTML, TASKS, self.stdout)
