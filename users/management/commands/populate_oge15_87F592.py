# -*- coding: utf-8 -*-
"""Группа 87F592 — Шины (245/45 R18). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "87F592"
TITLE = "87F592 · Размеры шин 245/45 R18"
FACTORY = "245/45 R18"

T1_TABLE = build_t1_table_html(
    diameters=["18", "19", "20"],
    rows=[
        ("245", ["245/45", "245/40", "—"]),
        ("265", ["265/45; 265/40", "265/30", "265/35; 265/30"]),
        ("275", ["275/40", "275/35; 275/30", "275/30"]),
    ],
)

TASKS = [
    {"tid": "01FD9F", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 20),
     "answer": "265"},
    {"tid": "697817", "t_type": "T2",
     "question_html": t2_question("265/50 R17"),
     "answer": "132,5"},
    {"tid": "B206B6", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "677,7"},
    {"tid": "8BA9C6", "t_type": "T4",
     "question_html": t4_question("265/35 R20"),
     "answer": "15,8"},
    {"tid": "6CF394", "t_type": "T5",
     "question_html": t5_question("265/45 R18"),
     "answer": "2,7"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
