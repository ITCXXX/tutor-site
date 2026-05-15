# -*- coding: utf-8 -*-
"""Группа 6312CF — Шины (185/70 R14). 5 задач (T4 increase, T5 decrease)."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_question, t5_decrease_question, deploy,
)


GID = "6312CF"
TITLE = "6312CF · Размеры шин 185/70 R14"
FACTORY = "185/70 R14"

T1_TABLE = build_t1_table_html(
    diameters=["14", "15", "16"],
    rows=[
        ("185", ["185/70", "185/65", "—"]),
        ("195", ["195/65", "195/65; 195/60", "—"]),
        ("205", ["205/60", "205/60; 205/55", "205/55; 205/50"]),
        ("215", ["215/60", "215/55", "215/50"]),
        ("225", ["—", "225/50", "225/50"]),
    ],
)

TASKS = [
    {"tid": "09FCAD", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наибольшей", 15),
     "answer": "225"},
    {"tid": "1CA6CA", "t_type": "T2",
     "question_html": t2_question("185/65 R15"),
     "answer": "120,25"},
    {"tid": "6F5EF4", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "614,6"},
    {"tid": "238193", "t_type": "T4",
     "question_html": t4_question("215/50 R16"),
     "answer": "6,8"},
    {"tid": "3C3091", "t_type": "T5",
     "question_html": t5_decrease_question("205/55 R15"),
     "answer": "1,3"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
