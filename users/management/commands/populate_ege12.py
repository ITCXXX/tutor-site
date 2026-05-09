"""
Management command: populate EGE task 12 questions into the DB.

Usage:
    python manage.py populate_ege12
    python manage.py populate_ege12 --clear   # wipe existing data first

Creates:
  Course  → Module 12 → 6 Lessons → 6 Assignments (decimal_input) → 60 TestQuestions
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ── All 60 questions. Each entry: (question_text_latex, correct_answer_str)
# Answers: for "найди точку min/max" → x-coordinate;
#          for "найди наим./наиб. значение на отрезке" → y-value.

TYPE1_CUBIC = [
    ("Найдите точку максимума функции $y = x^3 + 30x^2 + 225x + 23$.", "-15"),
    ("Найдите точку минимума функции $y = x^3 - 14x^2 + 49x + 3$.", "7"),
    ("Найдите точку максимума функции $y = x^3 - 108x + 23$.", "-6"),
    ("Найдите точку максимума функции $y = x^3 + 14x^2 + 49x + 8$.", "-7"),
    ("Найдите точку минимума функции $y = x^3 - 18x^2 + 81x + 17$.", "9"),
    ("Найдите точку максимума функции $y = x^3 - 27x + 14$.", "-3"),
    ("Найдите точку минимума функции $y = x^3 - 27x^2 + 17$.", "18"),
    ("Найдите точку минимума функции $y = x^3 - 300x + 14$.", "10"),
    ("Найдите точку максимума функции $y = x^3 + 16x^2 + 64x + 12$.", "-8"),
    ("Найдите точку минимума функции $y = x^3 - 12x^2 + 36x + 17$.", "6"),
    ("Найдите точку максимума функции $y = x^3 - 147x + 19$.", "-7"),
    ("Найдите точку минимума функции $y = x^3 - 192x + 11$.", "8"),
    ("Найдите точку максимума функции $y = x^3 - 300x + 5$.", "-10"),
    ("Найдите точку максимума функции $y = x^3 + 27x^2 + 11$.", "-18"),
    ("Найдите точку максимума функции $y = x^3 + 10x^2 + 25x + 16$.", "-5"),
    ("Найдите точку минимума функции $y = x^3 - 20x^2 + 100x + 23$.", "10"),
]

TYPE2_QUAD_LN = [
    ("Найдите точку минимума функции $y = x^2 - 28x + 96 \\cdot \\ln x + 31$.", "8"),
    ("Найдите точку максимума функции $y = 3{,}5x^2 - 29x + 30 \\cdot \\ln x + 67$.", "2"),
    ("Найдите точку минимума функции $y = 2x^2 - 23x + 33 \\cdot \\ln x - 17$.", "3"),
    ("Найдите точку максимума функции $y = 0{,}5x^2 - 21x + 110 \\cdot \\ln x + 43$.", "10"),
    ("Найдите точку максимума функции $y = x^2 - 33x + 136 \\cdot \\ln x + 74$.", "8"),
]

TYPE3_TRIG = [
    ("Найдите наименьшее значение функции $y = 10\\cos x + 14x + 9$ на отрезке $\\left[0;\\, \\dfrac{3\\pi}{2}\\right]$.", "19"),
    ("Найдите наименьшее значение функции $y = 10\\cos x - 14x + 5$ на отрезке $\\left[-\\dfrac{3\\pi}{2};\\, 0\\right]$.", "15"),
    ("Найдите наименьшее значение функции $y = 2\\cos x + 5x + 7$ на отрезке $\\left[0;\\, \\dfrac{3\\pi}{2}\\right]$.", "9"),
    ("Найдите наименьшее значение функции $y = 10\\cos x + \\dfrac{36x}{\\pi} - 6$ на отрезке $\\left[-\\dfrac{2\\pi}{3};\\, 0\\right]$.", "-35"),
    ("Найдите наибольшее значение функции $y = 10\\sin x - \\dfrac{36x}{\\pi} + 7$ на отрезке $\\left[-\\dfrac{5\\pi}{6};\\, 0\\right]$.", "32"),
    ("Найдите наименьшее значение функции $y = 12\\cos x + \\dfrac{45x}{\\pi} - 4$ на отрезке $\\left[-\\dfrac{2\\pi}{3};\\, 0\\right]$.", "-40"),
    ("Найдите наименьшее значение функции $y = 3\\cos x - 5x + 5$ на отрезке $\\left[-\\dfrac{3\\pi}{2};\\, 0\\right]$.", "8"),
    ("Найдите наибольшее значение функции $y = 10\\sin x - \\dfrac{42x}{\\pi} - 12$ на отрезке $\\left[-\\dfrac{5\\pi}{6};\\, 0\\right]$.", "18"),
]

TYPE4_LOG = [
    # segment → y-value
    ("Найдите наибольшее значение функции $y = \\ln(x+9)^5 - 5x$ на отрезке $[-8{,}5;\\, 0]$.", "40"),
    ("Найдите наименьшее значение функции $y = 9x - \\ln(x+5)^9$ на отрезке $[-4{,}5;\\, 0]$.", "-36"),
    ("Найдите наименьшее значение функции $y = 12x - \\ln(12x) + 4$ на отрезке $\\left[\\dfrac{1}{24};\\, \\dfrac{5}{24}\\right]$.", "1"),
    ("Найдите наибольшее значение функции $y = 9\\ln(x+7) - 9x + 4$ на отрезке $[-6{,}5;\\, 0]$.", "58"),
    ("Найдите наименьшее значение функции $y = 9x - 9\\ln(x+11) + 7$ на отрезке $[-10{,}5;\\, 0]$.", "-83"),
    ("Найдите наибольшее значение функции $y = \\ln(8x) - 8x + 7$ на отрезке $\\left[\\dfrac{1}{16};\\, \\dfrac{5}{16}\\right]$.", "6"),
    # no segment → x-coordinate
    ("Найдите точку минимума функции $y = 3x - 3 \\cdot \\ln(x - 7) - 8$.", "8"),
    ("Найдите точку максимума функции $y = 10 \\cdot \\ln(x - 2) - 10x + 11$.", "3"),
    ("Найдите точку максимума функции $y = \\ln(x - 7) - 2x - 3$.", "7.5"),
    ("Найдите точку минимума функции $y = 10x - \\ln(x - 5) + 3$.", "5.1"),
    ("Найдите точку минимума функции $y = 5x - \\ln(x + 3)^5 + 6$.", "-2"),
    ("Найдите точку максимума функции $y = \\ln(x + 3)^7 - 7x - 9$.", "-2"),
    ("Найдите точку максимума функции $y = \\ln(x - 2) - 5x + 13$.", "2.2"),
    ("Найдите точку максимума функции $y = 9 \\cdot \\ln(x - 4) - 9x - 7$.", "5"),
    ("Найдите точку минимума функции $y = 9x - 9 \\cdot \\ln(x + 3) + 4$.", "-2"),
    ("Найдите точку минимума функции $y = 9x - \\ln(x - 2)^9 - 8$.", "3"),
]

TYPE5_EXP = [
    ("Найдите точку минимума функции $y = (7 - x) \\cdot e^{7 - x}$.", "8"),
    ("Найдите точку максимума функции $y = (x + 3) \\cdot e^{3 - x}$.", "-2"),
    ("Найдите точку минимума функции $y = (x + 5) \\cdot e^{x - 5}$.", "-6"),
    ("Найдите точку минимума функции $y = (8x^2 - 40x + 40) \\cdot e^{x + 4}$.", "3"),
    ("Найдите точку максимума функции $y = (4 - x) \\cdot e^{x + 4}$.", "3"),
]

TYPE6_SQRT = [
    # no segment → x-coordinate
    ("Найдите точку минимума функции $y = x\\sqrt{x} - 3x + 17$.", "4"),
    ("Найдите точку максимума функции $y = 4 + 9x - x\\sqrt{x}$.", "36"),
    ("Найдите точку минимума функции $y = x^{3/2} - 3x + 9$.", "4"),
    ("Найдите точку минимума функции $y = x^{3/2} - 18x + 29$.", "144"),
    ("Найдите точку максимума функции $y = 17 + 27x - 2x^{3/2}$.", "81"),
    ("Найдите точку минимума функции $y = x^{3/2} - 21x + 11$.", "196"),
    # segment → y-value
    ("Найдите наибольшее значение функции $y = 11 + 6x - 4x\\sqrt{x}$ на отрезке $[0;\\, 21]$.", "13"),
    ("Найдите наименьшее значение функции $y = x\\sqrt{x} - 9x + 25$ на отрезке $[1;\\, 50]$.", "-83"),
    ("Найдите наибольшее значение функции $y = 7 + 12x - 4x\\sqrt{x}$ на отрезке $[0;\\, 12]$.", "23"),
    ("Найдите наименьшее значение функции $y = x\\sqrt{x} - 6x + 3$ на отрезке $[0;\\, 40]$.", "-29"),
]

LESSONS = [
    {
        "title": "Тип 1 — Кубический трёхчлен",
        "order": 1,
        "assignment_title": "Кубический трёхчлен: точка min/max",
        "description": (
            "Нахождение точки минимума или максимума функции вида "
            "$y = x^3 + ax^2 + bx + c$. Приравниваем производную к нулю, "
            "находим критические точки, проверяем знак второй производной."
        ),
        "questions": TYPE1_CUBIC,
    },
    {
        "title": "Тип 2 — Квадратичная + ln x",
        "order": 2,
        "assignment_title": "Квадратичная + логарифм: точка min/max",
        "description": (
            "Функция вида $y = ax^2 + bx + c \\cdot \\ln x$. "
            "Производная приводит к квадратному уравнению."
        ),
        "questions": TYPE2_QUAD_LN,
    },
    {
        "title": "Тип 3 — Тригонометрия на отрезке",
        "order": 3,
        "assignment_title": "Тригонометрия: наим./наиб. значение на отрезке",
        "description": (
            "Функция вида $y = A\\cos x + bx + c$ или $y = A\\sin x + bx + c$ "
            "на отрезке. Проверяем, есть ли критические точки внутри; если нет — "
            "функция монотонна, берём значение на нужном конце."
        ),
        "questions": TYPE3_TRIG,
    },
    {
        "title": "Тип 4 — Логарифмическая + линейная",
        "order": 4,
        "assignment_title": "Логарифмическая + линейная: точка min/max или значение",
        "description": (
            "Функция вида $y = ax - b\\ln(x+c)$ или $y = b\\ln(x+c) - ax$. "
            "Критическая точка находится из $y' = 0$ в явном виде."
        ),
        "questions": TYPE4_LOG,
    },
    {
        "title": "Тип 5 — Многочлен × экспонента",
        "order": 5,
        "assignment_title": "Многочлен × e^x: точка min/max",
        "description": (
            "Функция вида $y = P(x) \\cdot e^{\\alpha x + \\beta}$. "
            "Производная вычисляется по правилу произведения; "
            "$e^{\\cdot} > 0$ всегда, поэтому знак определяется только многочленом."
        ),
        "questions": TYPE5_EXP,
    },
    {
        "title": "Тип 6 — $x^{3/2}$ + линейная",
        "order": 6,
        "assignment_title": "x в степени 3/2: точка min/max или значение",
        "description": (
            "Функция вида $y = x\\sqrt{x} + ax + b$ (т.е. $x^{3/2}$). "
            "Производная $(\\tfrac{3}{2}\\sqrt{x})$ приравнивается к нулю, "
            "что даёт $\\sqrt{x} = k$, а значит $x = k^2$."
        ),
        "questions": TYPE6_SQRT,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 12 questions (60 items across 6 types)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing EGE-12 data before inserting",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            Course.objects.filter(slug="ege-profile-math").delete()
            self.stdout.write(self.style.WARNING("Existing data cleared."))

        course, _ = Course.objects.get_or_create(
            slug="ege-profile-math",
            defaults={
                "title": "ЕГЭ Профильная математика",
                "short_description": (
                    "Разбор всех задач профильного ЕГЭ по математике "
                    "с теорией и тренировочными заданиями."
                ),
                "order": 100,
                "is_active": True,
            },
        )

        module, _ = Module.objects.get_or_create(
            course=course,
            order=1,
            defaults={
                "title": "Первая часть",
                "description": "Задачи первой части профильного ЕГЭ.",
            },
        )

        lesson, _ = Lesson.objects.get_or_create(
            module=module,
            order=12,
            defaults={
                "title": "Задание 12",
                "lesson_type": "practice",
            },
        )

        total_q = 0
        for idx_l, lesson_data in enumerate(LESSONS):
            assignment, created = Assignment.objects.get_or_create(
                lesson=lesson,
                order=idx_l + 1,
                defaults={
                    "title": lesson_data["assignment_title"],
                    "description": lesson_data["description"],
                    "answer_type": "decimal_input",
                    "required_correct": 5,
                },
            )

            if not created:
                self.stdout.write(
                    self.style.WARNING(
                        f"Assignment already exists: {assignment.title} — skipping"
                    )
                )
                continue

            for idx_q, (q_text, answer) in enumerate(lesson_data["questions"]):
                question = TestQuestion.objects.create(
                    assignment=assignment,
                    question_text=q_text,
                    order=idx_q + 1,
                )
                AnswerOption.objects.create(
                    question=question,
                    text=answer,
                    is_correct=True,
                    order=1,
                )
                total_q += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"  OK {lesson_data['assignment_title']}: {len(lesson_data['questions'])} q"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nGotovo! Kurs: EGE, modul: Pervaya chast, urok: Zadacha 12, {total_q} voprosov."
            )
        )
