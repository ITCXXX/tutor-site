# -*- coding: utf-8 -*-
"""Группа 583B68 — Шины (215/60 R16). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_decrease_question, t5_decrease_question, deploy,
)


GID = "583B68"
TITLE = "583B68 · Размеры шин 215/60 R16"
FACTORY = "215/60 R16"

T1_TABLE = build_t1_table_html(
    diameters=["16", "17", "18"],
    rows=[
        ("205", ["205/60", "205/55", "—"]),
        ("215", ["215/60", "215/55", "—"]),
        ("225", ["225/55", "225/50", "225/45"]),
        ("235", ["—", "235/50", "235/45"]),
    ],
)

TASKS = [
    {"tid": "5CBD6B", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 18),
     "answer": "225"},
    {"tid": "83FCC1", "t_type": "T2",
     "question_html": t2_question("235/50 R17"),
     "answer": "117,5"},
    {"tid": "3AD4E4", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "664,4"},
    {"tid": "07E40B", "t_type": "T4",
     "question_html": t4_decrease_question("225/50 R17"),
     "answer": "7,6"},
    {"tid": "42A6F5", "t_type": "T5",
     "question_html": t5_decrease_question("225/50 R17"),
     "answer": "1,1"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
