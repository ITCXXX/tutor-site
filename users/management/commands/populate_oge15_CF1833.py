# -*- coding: utf-8 -*-
"""Группа CF1833 — Шины (225/60 R18). 5 задач. T4/T5: уменьшится."""

from django.core.management.base import BaseCommand
from ._oge15_shiny import (
    build_t1_table_html, t1_question, t2_question, t3_question,
    t4_decrease_question, t5_decrease_question, deploy,
)


GID = "CF1833"
TITLE = "CF1833 · Размеры шин 225/60 R18"
FACTORY = "225/60 R18"

T1_TABLE = build_t1_table_html(
    diameters=["17", "18", "19", "20"],
    rows=[
        ("215", ["215/65", "215/60", "—", "—"]),
        ("225", ["225/60", "225/55; 225/60", "225/50", "—"]),
        ("235", ["—", "235/55", "235/50", "235/45"]),
    ],
)

TASKS = [
    {"tid": "89A022", "t_type": "T1",
     "question_html": t1_question(T1_TABLE, "наименьшей", 19),
     "answer": "225"},
    {"tid": "A76E51", "t_type": "T2",
     "question_html": t2_question("235/55 R18"),
     "answer": "129,25"},
    {"tid": "BA9B66", "t_type": "T3",
     "question_html": t3_question(),
     "answer": "727,2"},
    {"tid": "47E492", "t_type": "T4",
     "question_html": t4_decrease_question("235/45 R20"),
     "answer": "7,7"},
    {"tid": "46C72B", "t_type": "T5",
     "question_html": t5_decrease_question("235/45 R20"),
     "answer": "1,1"},
]


class Command(BaseCommand):
    help = f"Группа {GID} — Шины"
    def handle(self, *args, **opts):
        deploy(GID, TITLE, FACTORY, TASKS, self.stdout)
