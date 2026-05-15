# -*- coding: utf-8 -*-
"""Группа 35C016 — Дороги (Ёлочки → Кленовое, Володя на машине). 10 задач."""

from django.core.management.base import BaseCommand
from ._oge15_dorogi import (
    build_context_html, t1_question, t2_question, t3_question,
    t4_question_route, t5_table_html, t5_cheapest_question, deploy,
)


GID = "35C016"
TITLE = "35C016 · Ёлочки → Кленовое (машина, 4 км/клетка)"
IMG_PATH = "/media/oge15/oge15_35C016.png"

# Геометрия (1 клетка = 4 км):
#   4 = д. Ёлочки (старт), 3 = д. Сосенки (на шоссе), 1 = д. Жуки (поворот),
#   2 = с. Кленовое (цель). Ёл-Сос-Жук колинеарны (вертикальная сторона).
# Триангуляция (8, 15, 17): Ёл-Жук = 60, Жук-Клен = 32, Hyp Ёл-Клен = 68.
# Сос-Жук = 24, Ёл-Сос = 36; тропинка Сос-Клен = √(24² + 32²) = √1600 = 40.
SPEED_ROAD, SPEED_PATH = 80, 40

STORY = {
    "hero": "Володя",
    "week_day": "воскресенье",
    "src_village": "Ёлочки",
    "mid_village": "Сосенки",
    "corner_village": "Жуки",
    "corner_kind": "деревня",
    "dest": "Кленовое",
    "dest_purpose": "",
    "route_kind": "машине",
    "road_kind": "грунтовой дороге",
    "road_kind_loc": "грунтовой дороге",
    "turn_dir": "направо",
    "pond_kind": "мимо пруда",
}

CONTEXT_HTML = build_context_html(STORY, IMG_PATH, SPEED_ROAD, SPEED_PATH, 4)

PRICES_HEADERS = ["д. Ёлочки", "с. Кленовое", "д. Сосенки", "д. Жуки"]
PRICES_ALL = [
    ("Молоко (1 л)", [42, 45, 38, 43]),
    ("Хлеб (1 батон)", [22, 25, 23, 27]),
    ("Сыр «Российский» (1 кг)", [320, 290, 270, 280]),
    ("Говядина (1 кг)", [410, 420, 450, 430]),
    ("Картофель (1 кг)", [26, 18, 24, 16]),
]

# T9: 5 л молока + 3 кг сыра + 4 кг картофеля.
#   Ёл: 210+960+104=1274; Клен: 225+870+72=1167; Сос: 190+810+96=1096 ✓; Жук: 215+840+64=1119
T9_ANSWER = "1096"

# T10: 3 батона хлеба + 2 кг сыра + 3 кг говядины.
#   Ёл: 66+640+1230=1936; Клен: 75+580+1260=1915 ✓; Сос: 69+540+1350=1959; Жук: 81+560+1290=1931
T10_ANSWER = "1915"

TASKS = [
    {"tid": "7B221C", "t_type": "T1",
     "question_html": t1_question(["д. Ёлочки", "с. Кленовое", "д. Жуки"]),
     "answer": "421"},
    {"tid": "8B1B3C", "t_type": "T1",
     "question_html": t1_question(["с. Кленовое", "д. Ёлочки", "д. Сосенки"]),
     "answer": "243"},

    {"tid": "206A24", "t_type": "T2",
     "question_html": t2_question("деревни Ёлочки", "села Кленовое", "деревню Жуки"),
     "answer": "92"},  # 60+32
    {"tid": "267533", "t_type": "T2",
     "question_html": t2_question("деревни Сосенки", "села Кленовое", "деревню Жуки"),
     "answer": "56"},  # 24+32

    {"tid": "6F6ACD", "t_type": "T3",
     "question_html": t3_question("деревни Ёлочки", "села Кленовое"),
     "answer": "68"},  # √(60²+32²) = √4624 = 68
    {"tid": "0E979A", "t_type": "T3",
     "question_html": t3_question("деревни Сосенки", "села Кленовое"),
     "answer": "40"},  # √(24²+32²) = 40

    {"tid": "523739", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Ёлочки", "село Кленовое", "по прямой грунтовой дороге"),
     "answer": "102"},  # 68/40·60 = 102 мин
    {"tid": "40DC6F", "t_type": "T4",
     "question_html": t4_question_route(
         "деревни Ёлочки", "село Кленовое",
         "сначала по шоссе, а затем свернут в деревне Сосенки на грунтовую дорогу, "
         "которая проходит мимо пруда"),
     "answer": "87"},  # 36/80·60 + 40/40·60 = 27 + 60 = 87 мин

    {"tid": "15AB34", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Володя с дедушкой хотят купить 5 л молока, 3 кг сыра «Российский» и "
         "4 кг картофеля."),
     "answer": T9_ANSWER},
    {"tid": "80B9B5", "t_type": "T5",
     "question_html": t5_cheapest_question(
         t5_table_html(PRICES_HEADERS, PRICES_ALL),
         "Володя с дедушкой хотят купить 3 батона хлеба, 2 кг сыра «Российский» и "
         "3 кг говядины."),
     "answer": T10_ANSWER},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Дороги (Ёлочки → Кленовое)"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, CONTEXT_HTML, TASKS, self.stdout)
