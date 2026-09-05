# -*- coding: utf-8 -*-
"""
Наполняет урок №20 курса ОГЭ генераторами всех 25 типов.

Почему генераторы, а не готовые задачи
--------------------------------------
Так устроена вся первая часть курса: задание — это прототип, числа новые при
каждом заходе, и решать его можно бесконечно. У готовых задач второй части
было бы 25 × 5 = 125 штук на весь год, и они запоминаются наизусть за неделю.
Плюс только на генераторном пути работает разбор ответов второй части: пары
для систем, промежутки для неравенств, клавиши √ и ∞ на странице.

Как это устроено
----------------
Платформа исполняет не код из базы, а файл users/generators/g<id>.py — так
сделано нарочно, чтобы не звать exec() на содержимое БД. Значит id генератора
обязан совпадать на всех машинах, иначе на сервере подтянется чужой файл.
Поэтому номера фиксированные: 900 + номер типа (901 … 925), а сама математика
живёт в users/oge20_generators.py и проверяется самотестами оттуда.

Запуск:
    python manage.py seed_oge20                 # создать/обновить 25 заданий
    python manage.py seed_oge20 --drop-static   # и убрать старые статичные задачи
    python manage.py seed_oge20 --clear         # снести всё, что создала команда
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import (
    Assignment, Course, GroupSubQuestion, Lesson, Module, ProblemGenerator,
    TaskGroup,
)

COURSE_SLUG = 'oge-maths'
MODULE_TITLE = 'Вторая часть'
GENERATOR_BASE = 900          # id генератора = GENERATOR_BASE + номер типа

# (номер типа, название задания)
TYPES = [
    (1, 'Кубическое уравнение: группировка'),
    (2, 'Кубическое уравнение: слагаемые по обе стороны'),
    (3, 'Вынесение общего множителя'),
    (4, 'x⁴ = (ax − b)²: разность квадратов'),
    (5, 'Сумма квадратов равна нулю'),
    (6, 'Иррациональное уравнение: отбор корней по ОДЗ'),
    (7, 'Замена t = 1/x'),
    (8, 'Замена t = 1/(x − a)'),
    (9, 'Замена t = (x − a)²'),
    (10, 'Система: сложение уравнений'),
    (11, 'Система: нельзя делить на скобку'),
    (12, 'Система: пропорциональные левые части'),
    (13, 'Значение выражения по пропорции'),
    (14, 'Неравенство: корень из квадрата'),
    (15, 'Неравенство: дробь с квадратом в знаменателе'),
    (16, 'Неравенство: x ≤ k²/x'),
    (17, 'Неравенство: x²/(x − a) ≤ x'),
    (18, 'Неравенство: 1/x ≥ 1/(x − a)'),
    (19, 'Неравенство: сокращение с выколотой точкой'),
    (20, 'Неравенство: полный квадрат в числителе'),
    (21, 'Неравенство: кратный корень в произведении'),
    (22, 'Неравенство: кратный корень в трёхчлене'),
    (23, 'Неравенство: замена t = x² + x'),
    (24, 'Неравенство: два трёхчлена с общим корнем'),
    (25, 'Неравенство: два трёхчлена с общим корнем, обратный знак'),
]

BACKUP_CODE = (
    '# Исполняется не этот текст, а users/generators/g{gid}.py.\n'
    '# Поле python_code оставлено как справка для админки.\n'
    'from users.oge20_generators import as_task\n'
    '\n'
    'def generate_task():\n'
    '    return as_task({num})\n'
)


class Command(BaseCommand):
    help = 'Создаёт генераторы и задания №20 (вторая часть) курса ОГЭ.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--drop-static', action='store_true',
            help='удалить статичные задачи (TaskGroup) из этого урока',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='удалить задания и генераторы, созданные этой командой',
        )

    def find_lesson(self, module):
        """
        Урок №20. Ищем существующий, а не создаём свой.

        Второй урок с тем же смыслом — худший исход: ученик видит в модуле два
        одинаковых пункта и не понимает, какой из них настоящий.
        """
        lesson = Lesson.objects.filter(module=module, title__startswith='№20').first()
        if lesson:
            return lesson, False
        lesson = Lesson.objects.filter(module=module, title__icontains='20').first()
        if lesson:
            return lesson, False
        lesson = Lesson.objects.create(
            module=module, title='№20. Алгебраические выражения, уравнения, неравенства',
            order=20, lesson_type='practice',
        )
        return lesson, True

    @transaction.atomic
    def handle(self, *args, **opts):
        course = Course.objects.filter(slug=COURSE_SLUG).first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=%s) не найден.' % COURSE_SLUG))
            return

        module, created_module = Module.objects.get_or_create(
            course=course, title=MODULE_TITLE, defaults={'order': 2, 'description': ''},
        )
        if created_module:
            self.stdout.write(self.style.SUCCESS('Модуль создан: %s' % MODULE_TITLE))

        lesson, created_lesson = self.find_lesson(module)
        self.stdout.write('Урок: «%s»%s'
                          % (lesson.title, ' (создан)' if created_lesson else ''))

        if opts['clear']:
            ids = [GENERATOR_BASE + n for n, _ in TYPES]
            удалено = Assignment.objects.filter(
                lesson=lesson, problem_generator_id__in=ids).delete()[0]
            ProblemGenerator.objects.filter(id__in=ids).delete()
            self.stdout.write(self.style.WARNING(
                'Удалено заданий: %d, генераторов: %d' % (удалено, len(ids))))
            return

        if opts['drop_static']:
            groups = TaskGroup.objects.filter(lesson=lesson)
            подзадач = GroupSubQuestion.objects.filter(group__in=groups).count()
            групп = groups.count()
            if групп:
                groups.delete()
                self.stdout.write(self.style.WARNING(
                    'Удалены статичные задачи: групп %d, задач %d'
                    % (групп, подзадач)))
            else:
                self.stdout.write('Статичных задач в уроке нет.')

        # Номера 901…925 зарезервированы за №20. Если на этой машине под таким
        # номером уже лежит чужой генератор, молча затирать его нельзя: к нему
        # привязаны чьи-то задания.
        занято = ProblemGenerator.objects.filter(
            id__gte=GENERATOR_BASE + 1, id__lte=GENERATOR_BASE + len(TYPES),
        ).exclude(name__startswith='OGE20:')
        if занято.exists():
            self.stdout.write(self.style.ERROR(
                'Номера %d…%d заняты чужими генераторами: %s. Заливка отменена.'
                % (GENERATOR_BASE + 1, GENERATOR_BASE + len(TYPES),
                   ', '.join('%d (%s)' % (g.id, g.name) for g in занято[:5]))))
            raise SystemExit(1)

        for num, title in TYPES:
            gid = GENERATOR_BASE + num
            generator, _ = ProblemGenerator.objects.update_or_create(
                id=gid,
                defaults={
                    'name': 'OGE20: Тип %d — %s' % (num, title),
                    'generator_type': 'python_function',
                    'python_code': BACKUP_CODE.format(gid=gid, num=num),
                    'config': {},
                },
            )

            assignment = Assignment.objects.filter(
                lesson=lesson, problem_generator=generator).first()
            if assignment is None:
                assignment = Assignment.objects.filter(lesson=lesson, order=num).first()

            fields = {
                'title': 'Тип %d. %s' % (num, title),
                'assignment_type': 'test',
                'answer_type': 'decimal_input',
                'required_correct': 3,
                'points': 2,
                'problem_generator': generator,
                'order': num,
            }
            if assignment:
                # Название не перезаписываем: его могли поправить руками.
                fields.pop('title')
                for key, value in fields.items():
                    setattr(assignment, key, value)
                assignment.save()
            else:
                Assignment.objects.create(lesson=lesson, description='', **fields)

        self.stdout.write(self.style.SUCCESS(
            '\nГотово: %d типов в уроке «%s».' % (len(TYPES), lesson.title)))
        self.stdout.write('Проверить: /courses/%s/ → %s → %s'
                          % (COURSE_SLUG, MODULE_TITLE, lesson.title))
