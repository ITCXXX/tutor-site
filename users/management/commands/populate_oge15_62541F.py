# -*- coding: utf-8 -*-
"""Группа 62541F — Шины (205/60 R16). 5 задач (decrease)."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_decrease_question, t5_decrease_question, deploy,
)


GID = "62541F"
TITLE = "62541F · Размеры шин 205/60 R16"
FACTORY = "205/60 R16"

T1_TABLE = build_t1_table_html(
    diameters=["15", "16", "17", "18"],
    rows=[
        ("195", ["195/65", "195/60", "195/55", "—"]),
        ("205", ["205/60", "205/55; 205/60", "205/50", "205/45"]),
        ("215", ["215/60", "215/55", "215/50", "215/40; 215/45"]),
        ("225", ["—", "225/50", "225/50; 225/45", "225/40"]),
    ],
)

TASKS = [
    {"tid": "2D1A30", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 17),
     "answer": "195"},
    {"tid": "586040", "t_type": "T2",
     "question_html": t2_question("225/45 R17"),
     "answer": "101,25"},
    {"tid": "3473AC", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "652,4"},
    {"tid": "D573A0", "t_type": "T4",
     "question_html": t4_decrease_question("225/40 R18"),
     "answer": "15,2"},
    {"tid": "3C0EC5", "t_type": "T5",
     "question_html": t5_decrease_question("225/40 R18"),
     "answer": "2,3"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
