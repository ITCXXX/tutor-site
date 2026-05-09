# -*- coding: utf-8 -*-
"""
Management command: populate EGE task 6 questions into the DB.

Usage:
    python manage.py populate_ege6
    python manage.py populate_ege6 --clear

Creates (inside the existing ege-profile-math course):
  Module "Pervaya chast" (order=1) -> Lesson "Zadacha 6" (order=6)
  -> 5 Assignments (decimal_input) -> 44 TestQuestions
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ── Тип 1: Показательные уравнения — прямое основание ────────────────────────
TYPE1_EXP_DIRECT = [
    (
        r"Найдите корень уравнения \(2^{-4-x} = 16\).",
        "-8",
    ),
    (
        r"Найдите корень уравнения \(5^{2-x} = 125\).",
        "-1",
    ),
    (
        r"Найдите корень уравнения \(9^{2-x} = 81\).",
        "0",
    ),
    (
        r"Найдите корень уравнения \(5^{x-2} = 125\).",
        "5",
    ),
    (
        r"Найдите корень уравнения \(3^{x+2} = 81\).",
        "2",
    ),
    (
        r"Найдите корень уравнения \(7^{11-x} = 49\).",
        "9",
    ),
    (
        r"Найдите корень уравнения \(2^{x-3} = \dfrac{1}{16}\).",
        "-1",
    ),
    (
        r"Найдите корень уравнения \(6^{x-5} = 36\).",
        "7",
    ),
    (
        r"Найдите корень уравнения \(8^{9-x} = 64\).",
        "7",
    ),
]

# ── Тип 2: Показательные уравнения — основание 1/a ───────────────────────────
TYPE2_EXP_FRAC = [
    (
        r"Найдите корень уравнения \(\left(\dfrac{1}{7}\right)^{x+4} = 49\).",
        "-6",
    ),
    (
        r"Найдите корень уравнения \(\left(\dfrac{1}{3}\right)^{3-x} = 81\).",
        "7",
    ),
    (
        r"Найдите корень уравнения \(3^{x-8} = \dfrac{1}{81}\).",
        "4",
    ),
    (
        r"Найдите корень уравнения \(\left(\dfrac{1}{4}\right)^{x-5} = \dfrac{1}{16}\).",
        "7",
    ),
    (
        r"Найдите корень уравнения \(4^{x-7} = \dfrac{1}{64}\).",
        "4",
    ),
    (
        r"Найдите корень уравнения \(\left(\dfrac{1}{6}\right)^{x-3} = \dfrac{1}{36}\).",
        "5",
    ),
    (
        r"Найдите корень уравнения \(3^{x-5} = \dfrac{1}{27}\).",
        "2",
    ),
    (
        r"Найдите корень уравнения \(\left(\dfrac{1}{5}\right)^{x-5} = 125\).",
        "2",
    ),
    (
        r"Найдите корень уравнения \(\left(\dfrac{1}{6}\right)^{x-2} = 6^x\).",
        "1",
    ),
    (
        r"Найдите корень уравнения \(3^{x+6} = 9^{2x}\).",
        "2",
    ),
]

# ── Тип 3: Уравнения с квадратным корнем — часть 1 ───────────────────────────
TYPE3_SQRT_1 = [
    (
        r"Найдите корень уравнения \(\sqrt{9x - 47} = 4\).",
        "7",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{5x - 1} = 7\).",
        "10",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{3x + 49} = 10\).",
        "17",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{99 - 7x} = 6\).",
        "9",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{44 - 5x} = 3\).",
        "7",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{57 - 7x} = 6\).",
        "3",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{36 - 4x} = 2\).",
        "8",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{7x - 31} = 2\).",
        "5",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{6x + 57} = 9\).",
        "4",
    ),
]

# ── Тип 4: Квадратный корень II, кубический корень, степень 3 ────────────────
TYPE4_ROOTS_CUBE = [
    (
        r"Найдите корень уравнения \(\sqrt{5x + 11} = 4\).",
        "1",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{8x - 20} = 2\).",
        "3",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{63 - 9x} = 3\).",
        "6",
    ),
    (
        r"Найдите корень уравнения \(\sqrt{22 - 3x} = 2\).",
        "6",
    ),
    (
        r"Найдите корень уравнения \(\sqrt[3]{x + 3} = 3\).",
        "24",
    ),
    (
        r"Найдите корень уравнения \(\sqrt[3]{x + 6} = 4\).",
        "58",
    ),
    (
        r"Найдите корень уравнения \((x - 5)^3 = 64\).",
        "9",
    ),
    (
        r"Найдите корень уравнения \((x + 4)^3 = -125\).",
        "-9",
    ),
]

# ── Тип 5: Логарифмические уравнения + рациональное ──────────────────────────
TYPE5_LOG = [
    (
        r"Найдите корень уравнения \(\log_5 (8 - x) = \log_5 2\).",
        "6",
    ),
    (
        r"Найдите корень уравнения \(\log_7 (1 - x) = \log_7 5\).",
        "-4",
    ),
    (
        r"Найдите корень уравнения \(\log_3 (x + 4) = \log_3 16\).",
        "12",
    ),
    (
        r"Найдите корень уравнения \(\log_2 (x - 2) = \log_2 11\).",
        "13",
    ),
    (
        r"Найдите корень уравнения \(\log_3 (15 - x) = \log_3 7\).",
        "8",
    ),
    (
        r"Найдите корень уравнения \(\log_4 (x - 4) = 3\).",
        "68",
    ),
    (
        r"Найдите корень уравнения \(\log_5 (20 - x) = 2\).",
        "-5",
    ),
    (
        r"Найдите корень уравнения \(\dfrac{1}{3x - 4} = 5\).",
        "1.4",
    ),
]


ASSIGNMENTS = [
    {
        "title": "Показательные уравнения I — прямое приведение к одному основанию",
        "order": 1,
        "description": (
            r"Приводим обе части к одному основанию: \(a^{f(x)} = a^k \Rightarrow f(x) = k\). "
            r"Полезные степени: \(2^4=16\), \(3^4=81\), \(5^3=125\), \(6^2=36\), \(7^2=49\), "
            r"\(8^2=64\), \(9^2=81\). "
            r"Если правая часть — дробь: \(\frac{1}{a^k} = a^{-k}\)."
        ),
        "questions": TYPE1_EXP_DIRECT,
    },
    {
        "title": "Показательные уравнения II — основание вида 1/a",
        "order": 2,
        "description": (
            r"Ключ: \(\left(\frac{1}{a}\right)^t = a^{-t}\). "
            r"Переводим к одному основанию, затем приравниваем показатели. "
            r"Если два разных основания: сводим к одному (например, \(9 = 3^2\), "
            r"\(6^x = (1/6)^{-x}\))."
        ),
        "questions": TYPE2_EXP_FRAC,
    },
    {
        "title": "Уравнения с квадратным корнем — часть 1",
        "order": 3,
        "description": (
            r"Схема: \(\sqrt{f(x)} = c \Rightarrow f(x) = c^2\) при \(c \geq 0\). "
            r"Возводим обе части в квадрат и решаем линейное уравнение. "
            r"Проверка ОДЗ: подкоренное выражение должно быть \(\geq 0\)."
        ),
        "questions": TYPE3_SQRT_1,
    },
    {
        "title": "Уравнения с корнями и степенями — часть 2",
        "order": 4,
        "description": (
            r"Квадратный корень: \(\sqrt{f(x)} = c \Rightarrow f(x) = c^2\). "
            r"Кубический корень: \(\sqrt[3]{f(x)} = c \Rightarrow f(x) = c^3\) (работает при любом знаке). "
            r"Уравнение вида \((x+a)^3 = b \Rightarrow x = \sqrt[3]{b} - a\)."
        ),
        "questions": TYPE4_ROOTS_CUBE,
    },
    {
        "title": "Логарифмические уравнения",
        "order": 5,
        "description": (
            r"Равенство логарифмов: \(\log_a f(x) = \log_a b \Rightarrow f(x) = b\). "
            r"Логарифм числа: \(\log_a f(x) = k \Rightarrow f(x) = a^k\). "
            r"Рациональное уравнение: \(\frac{1}{f(x)} = c \Rightarrow f(x) = \frac{1}{c}\)."
        ),
        "questions": TYPE5_LOG,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 6 questions (44 items across 5 types)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing EGE-6 lesson before inserting",
        )

    def handle(self, *args, **options):
        course = Course.objects.filter(slug="ege-profile-math").first()
        if not course:
            self.stdout.write(self.style.ERROR("Course 'ege-profile-math' not found."))
            return

        module, _ = Module.objects.get_or_create(
            course=course,
            order=1,
            defaults={
                "title": "Pervaya chast",
                "description": "Zadachi pervoy chasti profil'nogo EGE.",
            },
        )

        if options["clear"]:
            deleted, _ = Lesson.objects.filter(module=module, order=6).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted existing lesson (order=6): {deleted} objects"
            ))

        lesson, created = Lesson.objects.get_or_create(
            module=module,
            order=6,
            defaults={
                "title": "Задание 6",
                "lesson_type": "practice",
            },
        )
        if not created:
            self.stdout.write(self.style.WARNING(
                "Lesson already exists (use --clear to reset)."
            ))

        total_q = 0
        for data in ASSIGNMENTS:
            assignment, created = Assignment.objects.get_or_create(
                lesson=lesson,
                order=data["order"],
                defaults={
                    "title": data["title"],
                    "description": data["description"],
                    "answer_type": "decimal_input",
                    "required_correct": 5,
                },
            )
            if not created:
                self.stdout.write(self.style.WARNING(
                    f"  Assignment already exists: {assignment.title} -- skipping"
                ))
                continue

            for idx, (q_text, answer) in enumerate(data["questions"]):
                question = TestQuestion.objects.create(
                    assignment=assignment,
                    question_text=q_text,
                    order=idx + 1,
                )
                AnswerOption.objects.create(
                    question=question,
                    text=answer,
                    is_correct=True,
                )
                total_q += 1

        self.stdout.write(self.style.SUCCESS(
            f"Gotovo! Urok: Zadacha 6, {total_q} voprosov."
        ))
