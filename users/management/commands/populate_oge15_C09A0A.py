# -*- coding: utf-8 -*-
"""Группа C09A0A — Дороги (Грушёвка → Абрамово, Гриша велосипед, ярмарка). 10 задач."""

from django.core.management.base import BaseCommand
from ._oge15_dorogi import (
    build_context_html, t1_question, t2_question, t3_question,
    t4_question_route, t5_table_html, t5_cheapest_question, deploy,
)


GID = "C09A0A"
TITLE = "C09A0A · Грушёвка → Абрамово (велосипед, ярмарка, 2 км/клетка)"
IMG_PATH = "/media/oge15/oge15_C09A0A.png"

# Геометрия (1 кл = 2 км):
#   3 = д. Грушёвка (старт), 2 = д. Таловка (на шоссе), 1 = д. Новая (поворот направо),
#   4 = с. Абрамово (цель). Груш-Тал-Нов колинеарны (вертикальная сторона).
# Triangle (9, 12, 15) × 2 км = (18, 24, 30):
#   Груш-Нов = 18, Нов-Абр = 24, Hyp Груш-Абр = 30.
# Таловка: Тал-Нов = 10 (5 кл), Груш-Тал = 8 (4 кл).
#   Тропинка Тал-Абр = √(10² + 24²) = √676 = 26 (5,12,13 × 2).
SPEED_ROAD, SPEED_PATH = 15, 12

STORY = {
    "hero": "Гриша",
    "week_day": "понедельник",
    "src_village": "Грушёвка",
    "mid_village": "Таловка",
    "corner_village": "Новая",
    "corner_kind": "деревня",
    "dest": "Абрамово",
    "dest_purpose": "на ярмарку",
    "route_kind": "велосипедах",
    "road_kind": "лесной дорожке",
    "road_kind_loc": "лесной дорожке",
    "turn_dir": "направо",
    "pond_kind": "мимо пруда",
}

CONTEXT_HTML = build_context_html(STORY, IMG_PATH, SPEED_ROAD, SPEED_PATH, 2)

PRICES_HEADERS = ["д. Грушёвка", "с. Абрамово", "д. Таловка", "д. Новая"]
PRICES_ALL = [
    ("Молоко (1 л)", [32, 33, 31, 34]),
    ("Хлеб (1 батон)", [24, 21, 26, 20]),
    ("Сыр «Российский» (1 кг)", [320, 310, 330, 300]),
    ("Говядина (1 кг)", [390, 360, 370, 420]),
    ("Картофель (1 кг)", [10, 18, 15, 12]),
]

# T9: 3 батона + 1,5 кг сыра + 5 кг картофеля
#   Груш: 72+480+50=602; Абр: 63+465+90=618; Тал: 78+495+75=648; Нов: 60+450+60=570 ✓
T9_ANSWER = "570"

# T10: 4 л молока + 5 батонов + 2 кг говядины
#   Груш: 128+120+780=1028; Абр: 132+105+720=957 ✓; Тал: 124+130+740=994; Нов: 136+100+840=1076
T10_ANSWER = "957"

TASKS = [
    {"tid": "9DA1CD", "t_type": "T1",
     "question_html": t1_question(["д. Новая", "с. Абрамово", "д. Грушёвка"]),
     "answer": "143"},
    {"tid": "A595D8", "t_type": "T1",
     "question_html": t1_question(["д. Таловка", "д. Грушёвка", "с. Абрамово"]),
     "answer": "234"},

    {"tid": "279B0A", "t_type": "T2",
     "question_html": t2_question("деревни Грушёвка", "села Абрамово", "деревню Новая"),
     "answer": "42"},  # 18+24
    {"tid": "815F15", "t_type": "T2",
     "question_html": t2_question("деревни Таловка", "села Абрамово", "деревню Новая"),
     "answer": "34"},  # 10+24

    {"tid": "68D6B8", "t_type": "T3",
     "question_html": t3_question("деревни Грушёвка", "села Абрамово"),
     "answer": "30"},
    {"tid": "C9FB8A", "t_type": "T3",
     "question_html": t3_question("деревни Таловка", "села Абрамово"),
     "answer": "26"},

    {"tid": "D46403", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Грушёвка", "село Абрамово", "через деревню Новая"),
     "answer": "168"},  # 42/15·60 = 168 мин
    {"tid": "344753", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Грушёвка", "село Абрамово",
         "сначала по шоссе, а затем свернут в Таловке на прямую тропинку, "
         "которая проходит мимо пруда"),
     "answer": "162"},  # 8/15·60 + 26/12·60 = 32 + 130 = 162 мин

    {"tid": "60CCFB", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Гриша с дедушкой хотят купить 3 батона хлеба, 1,5 кг сыра «Российский» и 5 кг картофеля."),
     "answer": T9_ANSWER},
    {"tid": "5B5F1D", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Гриша с дедушкой хотят купить 4 л молока, 5 батонов хлеба и 2 кг говядины."),
     "answer": T10_ANSWER},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Дороги (Грушёвка → Абрамово)"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, CONTEXT_HTML, TASKS, self.stdout)
