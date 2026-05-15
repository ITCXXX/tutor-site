# -*- coding: utf-8 -*-
"""Группа 1F235A — Шины (215/50 R16). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "1F235A"
TITLE = "1F235A · Размеры шин 215/50 R16"
FACTORY = "215/50 R16"

T1_TABLE = build_t1_table_html(
    diameters=["16", "17", "18"],
    rows=[
        ("205", ["205/55", "205/50", "—"]),
        ("215", ["215/50", "215/50; 215/45", "—"]),
        ("225", ["225/50", "225/45", "225/45; 225/40"]),
    ],
)


TASKS = [
    {"tid": "179813", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 17),
     "answer": "205"},
    {"tid": "FD288C", "t_type": "T2",
     "question_html": t2_question("205/50 R18"),
     "answer": "102,5"},
    {"tid": "0313A6", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "621,4"},
    {"tid": "039F7D", "t_type": "T4",
     "question_html": t4_question("225/45 R17"),
     "answer": "12,9"},
    {"tid": "8D7613", "t_type": "T5",
     "question_html": t5_question("225/50 R16"),
     "answer": "1,6"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
