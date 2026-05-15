# -*- coding: utf-8 -*-
"""Группа AD8FEE — Шины (205/55 R16). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "AD8FEE"
TITLE = "AD8FEE · Размеры шин 205/55 R16"
FACTORY = "205/55 R16"

T1_TABLE = build_t1_table_html(
    diameters=["16", "17", "18"],
    rows=[
        ("205", ["205/55", "—", "—"]),
        ("215", ["215/55; 215/50", "215/45", "215/40"]),
        ("225", ["225/50; 225/45", "225/45; 225/40", "225/40"]),
    ],
)

TASKS = [
    {"tid": "4C2597", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 17),
     "answer": "215"},
    {"tid": "996DFC", "t_type": "T2",
     "question_html": t2_question("215/55 R17"),
     "answer": "118,25"},
    {"tid": "DB9AA0", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "631,9"},
    {"tid": "DB23FE", "t_type": "T4",
     "question_html": t4_question("225/45 R17"),
     "answer": "2,4"},
    {"tid": "093049", "t_type": "T5",
     "question_html": t5_question("215/55 R16"),
     "answer": "1,7"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
