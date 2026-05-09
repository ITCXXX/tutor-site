# -*- coding: utf-8 -*-
"""
Management command: populate EGE task 7 questions into the DB.

Usage:
    python manage.py populate_ege7
    python manage.py populate_ege7 --clear

Creates (inside the existing ege-profile-math course):
  Module "Pervaya chast" (order=1) -> Lesson "Zadacha 7" (order=7)
  -> 7 Assignments (decimal_input) -> 51 TestQuestions
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ── Тип 1: Логарифмы — свойства (сумма и разность) ─────────────────────────
TYPE1_LOG_PROPS = [
    (
        r"Найдите значение выражения \(\log_3 162 - \log_3 2\).",
        "4",
    ),
    (
        r"Найдите значение выражения \(\log_2 6{,}4 + \log_2 10\).",
        "6",
    ),
    (
        r"Найдите значение выражения \(\log_2 6{,}4 + \log_2 5\).",
        "5",
    ),
    (
        r"Найдите значение выражения \(\log_{0{,}7} 10 - \log_{0{,}7} 7\).",
        "-1",
    ),
    (
        r"Найдите значение выражения \(\log_{0{,}6} 50 - \log_{0{,}6} 18\).",
        "-2",
    ),
    (
        r"Найдите значение выражения \(\log_2 96 - \log_2 3\).",
        "5",
    ),
    (
        r"Найдите значение выражения \(\log_2 56 - \log_2 7\).",
        "3",
    ),
]

# ── Тип 2: Логарифмы — степени основания и смена основания ──────────────────
TYPE2_LOG_CHANGE = [
    (
        r"Найдите значение выражения \(6\log_{\sqrt{13}} 13\).",
        "12",
    ),
    (
        r"Найдите значение выражения \(6\log_7 \sqrt[3]{7}\).",
        "2",
    ),
    (
        r"Найдите значение выражения \(8\log_5 \sqrt{5}\).",
        "4",
    ),
    (
        r"Найдите значение выражения \(\dfrac{\log_6 17}{\log_{36} 17}\).",
        "2",
    ),
    (
        r"Найдите значение выражения \(\dfrac{\log_7 32}{\log_7 2}\).",
        "5",
    ),
    (
        r"Найдите значение выражения \(\dfrac{\log_9 28}{\log_9 7} + \log_7 \dfrac{7}{4}\).",
        "2",
    ),
]

# ── Тип 3: Степени ──────────────────────────────────────────────────────────
TYPE3_POWERS = [
    (
        r"Найдите значение выражения \(\dfrac{14^{6{,}4} \cdot 7^{-5{,}4}}{2^{4{,}4}}\).",
        "28",
    ),
    (
        r"Найдите значение выражения \((64^9)^3 : (16^5)^8\).",
        "4",
    ),
    (
        r"Найдите значение выражения \((4^{15})^5 : 4^{73}\).",
        "16",
    ),
    (
        r"Найдите значение выражения \(5^{0{,}06} \cdot 25^{0{,}97}\).",
        "25",
    ),
    (
        r"Найдите значение выражения \(\dfrac{81^{2{,}6}}{9^{3{,}7}}\).",
        "27",
    ),
    (
        r"Найдите значение выражения \(4^{\frac{1}{5}} \cdot 16^{\frac{9}{10}}\).",
        "16",
    ),
    (
        r"Найдите значение выражения \((2^{16})^5 : 2^{74}\).",
        "64",
    ),
    (
        r"Найдите значение выражения \(\dfrac{3^{9{,}2}}{9^{2{,}6}}\).",
        "81",
    ),
]

# ── Тип 4: Корни ─────────────────────────────────────────────────────────────
TYPE4_ROOTS = [
    (
        r"Найдите значение выражения \(\dfrac{(3\sqrt{8})^2}{6}\).",
        "12",
    ),
    (
        r"Найдите значение выражения \(\dfrac{\sqrt[3]{36} \cdot \sqrt[5]{36}}{\sqrt[30]{36}}\).",
        "6",
    ),
    (
        r"Найдите значение выражения \((\sqrt{96} - \sqrt{24}) \cdot \sqrt{6}\).",
        "12",
    ),
    (
        r"Найдите значение выражения \(\dfrac{\sqrt[3]{121} \cdot \sqrt[4]{121}}{\sqrt[12]{121}}\).",
        "11",
    ),
    (
        r"Найдите значение выражения \(\dfrac{(5\sqrt{6})^2}{10}\).",
        "15",
    ),
    (
        r"Найдите значение выражения \(\dfrac{\sqrt{8} \cdot \sqrt{48}}{\sqrt{24}}\).",
        "4",
    ),
    (
        r"Найдите значение выражения \(\dfrac{\sqrt[3]{400} \cdot \sqrt[3]{25}}{\sqrt[3]{80}}\).",
        "5",
    ),
]

# ── Тип 5: Тригонометрия — двойной угол (радианы) ───────────────────────────
TYPE5_TRIG_RAD = [
    (
        r"Найдите значение выражения \(2\sqrt{3}\cos^2\dfrac{13\pi}{12} - \sqrt{3}\).",
        "1.5",
    ),
    (
        r"Найдите значение выражения \(4\sqrt{2} - 8\sqrt{2}\sin^2\dfrac{7\pi}{8}\).",
        "4",
    ),
    (
        r"Найдите значение выражения \(6\sqrt{3}\cos^2\dfrac{11\pi}{12} - 3\sqrt{3}\).",
        "4.5",
    ),
    (
        r"Найдите значение выражения \(4\sqrt{3}\cos^2\dfrac{23\pi}{12} - 4\sqrt{3}\sin^2\dfrac{23\pi}{12}\).",
        "6",
    ),
    (
        r"Найдите значение выражения \(5\sqrt{2}\sin\dfrac{3\pi}{8} \cdot \cos\dfrac{3\pi}{8}\).",
        "2.5",
    ),
    (
        r"Найдите значение выражения \(3\sqrt{3} - 6\sqrt{3}\sin^2\dfrac{13\pi}{12}\).",
        "4.5",
    ),
    (
        r"Найдите значение выражения \(3\sin\dfrac{13\pi}{12} \cdot \cos\dfrac{13\pi}{12}\).",
        "0.75",
    ),
    (
        r"Найдите значение выражения \(5\sqrt{2}\cos^2\dfrac{7\pi}{8} - 5\sqrt{2}\sin^2\dfrac{7\pi}{8}\).",
        "5",
    ),
    (
        r"Найдите значение выражения \(\sqrt{2}\sin\dfrac{7\pi}{8} \cdot \cos\dfrac{7\pi}{8}\).",
        "-0.5",
    ),
    (
        r"Найдите значение выражения \(\sqrt{2} - 2\sqrt{2}\sin^2\dfrac{15\pi}{8}\).",
        "1",
    ),
    (
        r"Найдите значение выражения \(3\sqrt{2}\cos^2\dfrac{9\pi}{8} - 3\sqrt{2}\sin^2\dfrac{9\pi}{8}\).",
        "3",
    ),
]

# ── Тип 6: Тригонометрия — градусы и числовые выражения ──────────────────────
TYPE6_TRIG_DEG = [
    (
        r"Найдите значение выражения \(\dfrac{2\sin 136°}{\sin 68° \cdot \sin 22°}\).",
        "4",
    ),
    (
        r"Найдите значение выражения \(\dfrac{8\sin 64° \cdot \cos 64°}{\sin 128°}\).",
        "4",
    ),
    (
        r"Найдите значение выражения \(\dfrac{3\sin 68°}{\cos 34° \cdot \cos 56°}\).",
        "6",
    ),
    (
        r"Найдите значение выражения \(26\sqrt{2}\cos\dfrac{\pi}{4} \cdot \cos\dfrac{4\pi}{3}\).",
        "-13",
    ),
    (
        r"Найдите значение выражения \(18\sqrt{2}\,\mathrm{tg}\,\dfrac{\pi}{4} \cdot \sin\dfrac{\pi}{4}\).",
        "18",
    ),
]

# ── Тип 7: Тригонометрия — вычисление sin, cos, tg по условию ────────────────
TYPE7_TRIG_COND = [
    (
        r"Найдите значение выражения \(6\cos 2\alpha\), если \(\sin\alpha = {-}0{,}8\).",
        "-1.68",
    ),
    (
        r"Найдите значение выражения \(3\cos 2\alpha\), если \(\sin\alpha = 0{,}2\).",
        "2.76",
    ),
    (
        r"Найдите значение выражения \(3\cos 2\alpha\), если \(\cos\alpha = {-}0{,}8\).",
        "0.84",
    ),
    (
        r"Найдите \(\mathrm{tg}\,\alpha\), если \(\sin\alpha = \dfrac{\sqrt{26}}{26}\) и \(\alpha \in \left(0;\,\dfrac{\pi}{2}\right)\).",
        "0.2",
    ),
    (
        r"Найдите \(\sin\alpha\), если \(\cos\alpha = {-}\dfrac{\sqrt{21}}{5}\) и \(\alpha \in \left(\dfrac{\pi}{2};\,\pi\right)\).",
        "0.4",
    ),
    (
        r"Найдите значение выражения \(3\cos 2\alpha\), если \(\sin\alpha = 0{,}6\).",
        "0.84",
    ),
    (
        r"Найдите \(\mathrm{tg}\,\alpha\), если \(\cos\alpha = {-}\dfrac{\sqrt{26}}{26}\) и \(\alpha \in \left(\dfrac{\pi}{2};\,\pi\right)\).",
        "-5",
    ),
]


ASSIGNMENTS = [
    {
        "title": "Логарифмы: свойства",
        "order": 1,
        "description": (
            r"Используем свойства логарифмов: "
            r"\(\log_a b + \log_a c = \log_a(bc)\), \quad "
            r"\(\log_a b - \log_a c = \log_a\dfrac{b}{c}\). "
            r"Результат должен быть степенью основания."
        ),
        "questions": TYPE1_LOG_PROPS,
    },
    {
        "title": "Логарифмы: степени и смена основания",
        "order": 2,
        "description": (
            r"Логарифм степени: \(\log_{a^k} b = \dfrac{1}{k}\log_a b\). "
            r"Логарифм корня: \(\log_a \sqrt[k]{b} = \dfrac{1}{k}\). "
            r"Смена основания: \(\dfrac{\log_a b}{\log_a c} = \log_c b\)."
        ),
        "questions": TYPE2_LOG_CHANGE,
    },
    {
        "title": "Степени",
        "order": 3,
        "description": (
            r"Приводим всё к одному основанию, используя \(a^m \cdot a^n = a^{m+n}\), "
            r"\(\dfrac{a^m}{a^n} = a^{m-n}\), \((a^m)^n = a^{mn}\). "
            r"Дробные показатели: \(a^{p/q} = \sqrt[q]{a^p}\)."
        ),
        "questions": TYPE3_POWERS,
    },
    {
        "title": "Корни",
        "order": 4,
        "description": (
            r"Корень — это степень: \(\sqrt[n]{a} = a^{1/n}\). "
            r"При умножении/делении корней одного показателя: "
            r"\(\sqrt[n]{a} \cdot \sqrt[n]{b} = \sqrt[n]{ab}\). "
            r"Разные показатели — переводим в дроби и складываем/вычитаем."
        ),
        "questions": TYPE4_ROOTS,
    },
    {
        "title": "Тригонометрия: двойной угол (радианы)",
        "order": 5,
        "description": (
            r"Формулы двойного угла: \(\cos 2x = \cos^2 x - \sin^2 x = 1 - 2\sin^2 x = 2\cos^2 x - 1\), "
            r"\(\sin 2x = 2\sin x \cos x\). "
            r"Приводим аргумент к виду \(2\alpha\), затем используем таблицу значений."
        ),
        "questions": TYPE5_TRIG_RAD,
    },
    {
        "title": "Тригонометрия: градусы и прямое вычисление",
        "order": 6,
        "description": (
            r"Формула двойного угла в градусах: \(\sin 2\alpha = 2\sin\alpha\cos\alpha\). "
            r"Дополнение до 90°: \(\sin\alpha = \cos(90° - \alpha)\). "
            r"Точные значения: \(\cos\dfrac{\pi}{4} = \dfrac{\sqrt{2}}{2}\), "
            r"\(\cos\dfrac{\pi}{3} = \dfrac{1}{2}\), \(\mathrm{tg}\dfrac{\pi}{4} = 1\)."
        ),
        "questions": TYPE6_TRIG_DEG,
    },
    {
        "title": "Тригонометрия: нахождение sin, cos, tg",
        "order": 7,
        "description": (
            r"Основное тождество: \(\sin^2\alpha + \cos^2\alpha = 1\). "
            r"Формула двойного угла: \(\cos 2\alpha = 1 - 2\sin^2\alpha = 2\cos^2\alpha - 1\). "
            r"Знак определяется по четверти. "
            r"\(\mathrm{tg}\,\alpha = \dfrac{\sin\alpha}{\cos\alpha}\)."
        ),
        "questions": TYPE7_TRIG_COND,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 7 questions (51 items across 7 types)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing EGE-7 lesson before inserting",
        )

    def handle(self, *args, **options):
        course = Course.objects.filter(slug="ege-profile-math").first()
        if not course:
            self.stdout.write(self.style.ERROR(
                "Course 'ege-profile-math' not found."
            ))
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
            deleted, _ = Lesson.objects.filter(module=module, order=7).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted existing lesson (order=7): {deleted} objects"
            ))

        lesson, created = Lesson.objects.get_or_create(
            module=module,
            order=7,
            defaults={
                "title": "Задание 7",
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
                    order=1,
                )
                total_q += 1

            self.stdout.write(self.style.SUCCESS(
                f"  OK {data['title']}: {len(data['questions'])} q"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nGotovo! Urok: Zadacha 7, {total_q} voprosov."
        ))
