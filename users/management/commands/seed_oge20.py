# -*- coding: utf-8 -*-
"""
Management command: создаёт ProblemGenerator-ы и Assignment-ы под урок
«Задание 20» (вторая часть) курса ОГЭ. Типы задач — по каталогу Школково
(3.shkolkovo.online/catalog/7230), который повторяет открытый банк ФИПИ.
Справочник всех 25 типов: OGE_PART2_NO20_TYPES.md в корне проекта.

Особенность второй части: у уравнения несколько корней, поэтому генераторы
возвращают correct_answer вида "-5;-2;2" и флаг multi_answer=True.
Проверку набора корней делает answer_check._check_answer_multi (порядок
ввода не важен), фронтенд lesson_practice.html показывает кнопку «+ корень».

Usage:
    python manage.py seed_oge20
    python manage.py seed_oge20 --clear   # снести и пересоздать
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Генераторы
# ──────────────────────────────────────────────────────────────────────────────

GEN_T1 = r'''
def generate_task():
    """
    №20 ОГЭ, Тип 1 (по Школково/ФИПИ): кубическое уравнение, решаемое
    группировкой.

    Все задачи банка ФИПИ этого типа имеют вид

        x^3 + a*x^2 - b*x - a*b = 0,   b = k^2 (полный квадрат)

    (примеры ФИПИ: a=5,b=4; a=4,b=1; a=3,b=4; a=2,b=1).

    Решение: x^2(x + a) - b(x + a) = (x + a)(x^2 - b) = 0
        → корни: -a, -k, k — все целые.

    Ограничения генерации:
        a ∈ [2..10];
        k ∈ {1,2,3,4,5}, k ≠ a — чтобы все три корня были различны.
    """
    a = random.randint(2, 10)
    k = random.choice([kk for kk in (1, 2, 3, 4, 5) if kk != a])
    b = k * k
    ab = a * b

    bx = "x" if b == 1 else f"{b}x"
    equation = f"x^{{3}} + {a}x^{{2}} - {bx} - {ab} = 0"

    roots = sorted([-a, -k, k])
    return {
        "condition_text": (
            rf"Решите уравнение $ {equation} $. "
            "Если корней несколько, укажите все."
        ),
        "correct_answer": ";".join(str(r) for r in roots),
        "multi_answer": True,
    }
'''


PROTOTYPES = [
    # (order, code, gen_name, assignment_title)
    (1, GEN_T1, 'OGE20: Тип 1 — кубическое, группировка',
     'Кубическое уравнение (группировка)'),
]


# ──────────────────────────────────────────────────────────────────────────────
# Команда
# ──────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = 'Создаёт ProblemGenerator-ы и Assignment-ы под урок «Задание 20» (вторая часть) курса ОГЭ.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 20» и пересоздать.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден.'
            ))
            return

        module, mod_created = Module.objects.get_or_create(
            course=course, title='Вторая часть',
            defaults={'order': 2, 'description': ''},
        )
        if mod_created:
            self.stdout.write(self.style.SUCCESS('Модуль создан: Вторая часть'))

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 20').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 20» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 20',
            defaults={'order': 20, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 20:
            lesson.order = 20
            lesson.save(update_fields=['order'])
        if created:
            self.stdout.write(self.style.SUCCESS(f'Урок создан: {lesson.title}'))

        # Поиск Assignment по (lesson, order) — title мог быть переименован
        # вручную, поэтому по нему искать нельзя (иначе плодим дубли).
        existing_by_order = {a.order: a for a in lesson.assignments.all()}

        for order, code, gen_name, asg_title in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                    'config': {},
                },
            )

            assign = existing_by_order.get(order)
            if assign:
                # title не перезаписываем — мог быть переименован.
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'decimal_input'
                assign.required_correct = 3
                assign.points = 2
                assign.save()
                shown_title = assign.title
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=order,
                    title=asg_title,
                    description='',
                    assignment_type='test',
                    answer_type='decimal_input',
                    required_correct=3,
                    points=2,
                    problem_generator=generator,
                )
                shown_title = asg_title

            self.stdout.write(self.style.SUCCESS(f'  [{order}] {shown_title} → {gen_name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: «Задание 20» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
