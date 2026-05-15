# -*- coding: utf-8 -*-
"""Группа 3482E5 — Шины (185/60 R14). 5 задач."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_question, deploy,
)


GID = "3482E5"
TITLE = "3482E5 · Размеры шин 185/60 R14"
FACTORY = "185/60 R14"

T1_TABLE = build_t1_table_html(
    diameters=["14", "15", "16"],
    rows=[
        ("185", ["185/60", "185/55", "—"]),
        ("195", ["195/55", "195/55; 195/50", "—"]),
        ("205", ["—", "205/50", "205/50"]),
        ("215", ["—", "—", "215/45"]),
    ],
)

TASKS = [
    {"tid": "922A2F", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 16),
     "answer": "205"},
    {"tid": "EF8F74", "t_type": "T2",
     "question_html": t2_question("205/55 R15"),
     "answer": "112,75"},
    {"tid": "1394A1", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "577,6"},
    {"tid": "FCA745", "t_type": "T4",
     "question_html": t4_question("195/55 R15"),
     "answer": "17,9"},
    {"tid": "E32B27", "t_type": "T5",
     "question_html": t5_question("205/50 R16"),
     "answer": "5,9"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
