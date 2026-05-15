# -*- coding: utf-8 -*-
"""Группа 9E5B99 — Шины (165/70 R13). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "9E5B99"
TITLE = "9E5B99 · Размеры шин 165/70 R13"
FACTORY = "165/70 R13"

T1_TABLE = build_t1_table_html(
    diameters=["13", "14", "15"],
    rows=[
        ("165", ["165/70", "165/65", "—"]),
        ("175", ["175/65", "175/65; 175/60", "—"]),
        ("185", ["185/65; 185/60", "185/60", "185/55"]),
        ("195", ["195/60", "195/55", "195/55; 195/50"]),
    ],
)

TASKS = [
    {"tid": "F06545", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 15),
     "answer": "185"},
    {"tid": "CF7B0F", "t_type": "T2",
     "question_html": t2_question("165/65 R14"),
     "answer": "107,25"},
    {"tid": "0EA1B6", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "561,2"},
    {"tid": "E1451B", "t_type": "T4",
     "question_html": t4_question("195/50 R15"),
     "answer": "14,8"},
    {"tid": "2AA2FF", "t_type": "T5",
     "question_html": t5_question("175/60 R14"),
     "answer": "0,8"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
