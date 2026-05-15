# -*- coding: utf-8 -*-
"""Группа 4FD630 — Шины (225/60 R17). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "4FD630"
TITLE = "4FD630 · Размеры шин 225/60 R17"
FACTORY = "225/60 R17"

T1_TABLE = build_t1_table_html(
    diameters=["17", "18", "19"],
    rows=[
        ("225", ["225/60", "225/55", "—"]),
        ("245", ["245/55", "245/50; 245/45", "245/45"]),
        ("275", ["275/50", "275/45", "275/40"]),
    ],
)

TASKS = [
    {"tid": "DF02B2", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 19),
     "answer": "245"},
    {"tid": "1BE266", "t_type": "T2",
     "question_html": t2_question("245/60 R18"),
     "answer": "147"},
    {"tid": "5CC470", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "701,8"},
    {"tid": "19C115", "t_type": "T4",
     "question_html": t4_question("275/40 R19"),
     "answer": "0,8"},
    {"tid": "BEF8D1", "t_type": "T5",
     "question_html": t5_question("275/50 R17"),
     "answer": "0,7"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
