# -*- coding: utf-8 -*-
"""Группа EAAB14 — Шины (265/70 R17). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "EAAB14"
TITLE = "EAAB14 · Размеры шин 265/70 R17"
FACTORY = "265/70 R17"

T1_TABLE = build_t1_table_html(
    diameters=["17", "18", "20"],
    rows=[
        ("265", ["265/70", "265/65", "—"]),
        ("275", ["275/70; 275/65", "275/65; 275/60", "275/55"]),
        ("285", ["285/65; 285/60", "285/60", "285/50"]),
    ],
)

TASKS = [
    {"tid": "DD443A", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 20),
     "answer": "275"},
    {"tid": "4768BD", "t_type": "T2",
     "question_html": t2_question("195/60 R16"),
     "answer": "117"},
    {"tid": "7A8BD3", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "802,8"},
    {"tid": "B29FC0", "t_type": "T4",
     "question_html": t4_question("275/55 R20"),
     "answer": "7,7"},
    {"tid": "A3C8CF", "t_type": "T5",
     "question_html": t5_question("275/70 R17"),
     "answer": "1,7"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
