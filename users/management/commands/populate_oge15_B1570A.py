# -*- coding: utf-8 -*-
"""Группа B1570A — Шины (205/60 R16). 5 задач. T4: уменьшится; T5: увеличится."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_decrease_question, t5_question, deploy,
)


GID = "B1570A"
TITLE = "B1570A · Размеры шин 205/60 R16"
FACTORY = "205/60 R16"

T1_TABLE = build_t1_table_html(
    diameters=["16", "17", "18"],
    rows=[
        ("205", ["205/60", "205/55", "—"]),
        ("215", ["215/60; 215/55", "215/50", "215/45"]),
        ("225", ["—", "225/45; 225/40", "225/40"]),
    ],
)

TASKS = [
    {"tid": "82FAFF", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 18),
     "answer": "215"},
    {"tid": "3D7CF2", "t_type": "T2",
     "question_html": t2_question("275/50 R17"),
     "answer": "137,5"},
    {"tid": "736242", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "652,4"},
    {"tid": "FECD7D", "t_type": "T4",
     "question_html": t4_decrease_question("215/45 R18"),
     "answer": "1,7"},
    {"tid": "E0E9AB", "t_type": "T5",
     "question_html": t5_question("215/60 R16"),
     "answer": "1,8"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
