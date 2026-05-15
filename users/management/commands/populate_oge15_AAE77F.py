# -*- coding: utf-8 -*-
"""Группа AAE77F — Шины (175/60 R15). 5 задач. T4 уменьшится; T5 увеличится."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_decrease_question, t5_question, deploy,
)


GID = "AAE77F"
TITLE = "AAE77F · Размеры шин 175/60 R15"
FACTORY = "175/60 R15"

T1_TABLE = build_t1_table_html(
    diameters=["14", "15", "16"],
    rows=[
        ("165", ["165/70", "165/60; 165/65", "—"]),
        ("175", ["175/65", "175/60", "—"]),
        ("185", ["185/60", "185/55", "185/50"]),
        ("195", ["195/60", "195/55", "195/45"]),
        ("205", ["—", "—", "205/45"]),
    ],
)

TASKS = [
    {"tid": "9731EF", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 16),
     "answer": "185"},
    {"tid": "8CD3B6", "t_type": "T2",
     "question_html": t2_question("165/70 R14"),
     "answer": "115,5"},
    {"tid": "F26915", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "591"},
    {"tid": "18BC88", "t_type": "T4",
     "question_html": t4_decrease_question("195/45 R16"),
     "answer": "9,1"},
    {"tid": "8FEFA6", "t_type": "T5",
     "question_html": t5_question("195/55 R15"),
     "answer": "0,8"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
