# -*- coding: utf-8 -*-
"""Группа 89CE07 — Шины (235/65 R17). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "89CE07"
TITLE = "89CE07 · Размеры шин 235/65 R17"
FACTORY = "235/65 R17"

T1_TABLE = build_t1_table_html(
    diameters=["17", "18", "19"],
    rows=[
        ("235", ["235/65", "235/60", "—"]),
        ("245", ["245/65", "245/60; 245/55", "245/50"]),
        ("255", ["—", "255/55", "255/50; 255/45"]),
    ],
)

TASKS = [
    {"tid": "F38BF0", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 19),
     "answer": "245"},
    {"tid": "EEAE6D", "t_type": "T2",
     "question_html": t2_question("220/60 R16"),
     "answer": "132"},
    {"tid": "B2FE7B", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "737,3"},
    {"tid": "6F6F28", "t_type": "T4",
     "question_html": t4_question("255/50 R19"),
     "answer": "0,3"},
    {"tid": "BFB595", "t_type": "T5",
     "question_html": t5_question("245/65 R17"),
     "answer": "1,8"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
