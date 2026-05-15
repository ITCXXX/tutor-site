# -*- coding: utf-8 -*-
"""Группа BA66FC — Дороги (Осиновка → Николаево, Гриша велосипед). 10 задач."""

from django.core.management.base import BaseCommand
from ._oge15_dorogi import (
    build_context_html, t1_question, t2_question, t3_question,
    t4_question_route, t5_table_html, t5_cheapest_question, deploy,
)


GID = "BA66FC"
TITLE = "BA66FC · Осиновка → Николаево (велосипед, магазин)"
IMG_PATH = "/media/oge15/oge15_BA66FC.png"

# Геометрия (1 кл = 1 км):
#   4 = д. Осиновка (старт), 2 = д. Зябликово (на шоссе), 1 = д. Старая (поворот направо),
#   3 = с. Николаево (цель). Осин-Зяб-Стар колинеарны (вертикальная сторона).
# Triangle (8, 15, 17): Осин-Стар = 15, Стар-Никол = 8, Hyp Осин-Никол = 17.
# Зябликово: Стар-Зяб = 6, Осин-Зяб = 9 → тропинка Зяб-Никол = √(6²+8²) = 10.
SPEED_ROAD, SPEED_PATH = 15, 10

STORY = {
    "hero": "Гриша",
    "week_day": "субботу",
    "src_village": "Осиновка",
    "mid_village": "Зябликово",
    "corner_village": "Старая",
    "corner_kind": "деревня",
    "dest": "Николаево",
    "dest_purpose": "в магазин",
    "route_kind": "велосипедах",
    "road_kind": "лесной дорожке",
    "road_kind_loc": "лесной дорожке",
    "turn_dir": "направо",
    "pond_kind": "мимо пруда",
}

CONTEXT_HTML = build_context_html(STORY, IMG_PATH, SPEED_ROAD, SPEED_PATH, 1)

PRICES_HEADERS = ["д. Осиновка", "с. Николаево", "д. Зябликово", "д. Старая"]
PRICES_ALL = [
    ("Молоко (1 л)", [44, 48, 54, 60]),
    ("Хлеб (1 батон)", [26, 19, 23, 18]),
    ("Сыр «Российский» (1 кг)", [310, 330, 340, 290]),
    ("Говядина (1 кг)", [370, 320, 330, 360]),
    ("Картофель (1 кг)", [24, 26, 25, 27]),
]

# T9: 3 л молока + 2 батона хлеба + 3 кг картофеля
#   Осин: 132+52+72=256 ✓; Никол: 144+38+78=260; Зяб: 162+46+75=283; Стар: 180+36+81=297
T9_ANSWER = "256"

# T10: 5 л молока + 2 кг сыра + 2 кг говядины
#   Осин: 220+620+740=1580; Никол: 240+660+640=1540 ✓; Зяб: 270+680+660=1610; Стар: 300+580+720=1600
T10_ANSWER = "1540"

TASKS = [
    {"tid": "50AAED", "t_type": "T1",
     "question_html": t1_question(["д. Осиновка", "с. Николаево", "д. Зябликово"]),
     "answer": "432"},
    {"tid": "B54F14", "t_type": "T1",
     "question_html": t1_question(["д. Старая", "с. Николаево", "д. Зябликово"]),
     "answer": "132"},

    {"tid": "D73DC8", "t_type": "T2",
     "question_html": t2_question("деревни Осиновка", "села Николаево", "деревню Старая"),
     "answer": "23"},  # 15+8
    {"tid": "4004C7", "t_type": "T2",
     "question_html": t2_question("деревни Зябликово", "села Николаево", "деревню Старая"),
     "answer": "14"},  # 6+8

    {"tid": "8285E0", "t_type": "T3",
     "question_html": t3_question("деревни Осиновка", "села Николаево"),
     "answer": "17"},
    {"tid": "D34BA5", "t_type": "T3",
     "question_html": t3_question("деревни Зябликово", "села Николаево"),
     "answer": "10"},

    {"tid": "E9A538", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Осиновка", "село Николаево", "по прямой лесной дорожке"),
     "answer": "102"},  # 17/10·60 = 102 мин
    {"tid": "42D860", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Осиновка", "село Николаево",
         "сначала по шоссе, а затем свернут в деревне Зябликово на прямую "
         "тропинку, которая проходит мимо пруда"),
     "answer": "96"},  # 9/15·60 + 10/10·60 = 36 + 60 = 96 мин

    {"tid": "48ABB4", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Гриша с дедушкой хотят купить 3 л молока, 2 батона хлеба и 3 кг картофеля."),
     "answer": T9_ANSWER},
    {"tid": "648B0F", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Гриша с дедушкой хотят купить 5 л молока, 2 кг сыра «Российский» и 2 кг говядины."),
     "answer": T10_ANSWER},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Дороги (Осиновка → Николаево)"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, CONTEXT_HTML, TASKS, self.stdout)
