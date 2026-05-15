# -*- coding: utf-8 -*-
"""Группа DB5DF7 — Шины (185/60 R15). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "DB5DF7"
TITLE = "DB5DF7 · Размеры шин 185/60 R15"
FACTORY = "185/60 R15"

T1_TABLE = build_t1_table_html(
    diameters=["14", "15", "16", "17"],
    rows=[
        ("175", ["175/70", "175/65", "—", "—"]),
        ("185", ["185/70", "185/60", "185/55", "—"]),
        ("195", ["195/65", "195/60", "195/50; 195/55", "195/45"]),
        ("205", ["205/60", "205/55", "205/50", "205/45"]),
        ("215", ["—", "—", "215/45", "215/40"]),
    ],
)

TASKS = [
    {"tid": "F6E670", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 16),
     "answer": "185"},
    {"tid": "9939C7", "t_type": "T2",
     "question_html": t2_question("205/55 R15"),
     "answer": "112,75"},
    {"tid": "C8F8C2", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "603"},
    {"tid": "29662A", "t_type": "T4",
     "question_html": t4_question("205/45 R17"),
     "answer": "13,3"},
    {"tid": "40A221", "t_type": "T5",
     "question_html": t5_question("205/45 R17"),
     "answer": "2,2"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
