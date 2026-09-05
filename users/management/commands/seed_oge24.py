# -*- coding: utf-8 -*-
"""
Создаёт урок №24 курса ОГЭ и наполняет его генераторами всех 25 сюжетов.

Устройство то же, что у seed_oge20: платформа исполняет файл
users/generators/g<id>.py, поэтому id фиксированные — 950 + номер типа
(1101 … 1125; ниже заняты №20-№22). Математика живёт в
users/oge24_generators.py и проверяется oge24_setup/verify_oge24.py.

Запуск:
    python manage.py seed_oge24            # создать/обновить 20 заданий
    python manage.py seed_oge24 --clear    # снести всё, что создала команда
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Assignment, Course, Lesson, Module, ProblemGenerator

COURSE_SLUG = 'oge-maths'
MODULE_TITLE = 'Вторая часть'
LESSON_TITLE = '№24. Геометрические задачи на доказательство'
GENERATOR_BASE = 1100

TYPES = [
    (1, 'Трапеция: BD² = BC·AD, подобие'),
    (2, 'Точка на средней линии: треугольники на основаниях'),
    (3, 'Точка на средней линии: боковые треугольники'),
    (4, 'Середина боковой стороны: половина трапеции'),
    (5, 'Диагонали трапеции: равновеликие треугольники'),
    (6, 'Биссектрисы при боковой стороне: равноудалённая точка'),
    (7, 'Середина боковой стороны: трапеция прямоугольная'),
    (8, 'Равнобедренная трапеция: точка на основании'),
    (9, 'Диагонали: AO = OD, трапеция равнобедренная'),
    (10, 'Прямая через центр параллелограмма'),
    (11, 'Прямая через центр и теорема Фалеса'),
    (12, 'Биссектрисы параллелограмма: середина стороны'),
    (13, 'Сторона вдвое больше смежной: биссектриса'),
    (14, 'Точка внутри параллелограмма: сумма площадей'),
    (15, 'Диагонали параллелограмма: четверть площади'),
    (16, 'Середина стороны: прямоугольник'),
    (17, 'Равные высоты: ромб'),
    (18, 'Две высоты остроугольного треугольника'),
    (19, 'Две высоты тупоугольного треугольника'),
    (20, 'AD = CE, BD = BE: равнобедренный треугольник'),
    (21, 'Середины сторон равностороннего треугольника'),
    (22, 'Вписанный четырёхугольник: продолжения сторон'),
    (23, 'Равные углы на одну сторону: вписанность'),
    (24, 'Две окружности: линия центров и общая хорда'),
    (25, 'Внутренняя общая касательная'),
]

BACKUP_CODE = (
    '# Исполняется не этот текст, а users/generators/g{gid}.py.\n'
    '# Поле python_code оставлено как справка для админки.\n'
    'from users.oge24_generators import as_task\n'
    '\n'
    'def generate_task():\n'
    '    return as_task({num})\n'
)


class Command(BaseCommand):
    help = 'Создаёт генераторы и задания №24 (задачи на доказательство) курса ОГЭ.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='удалить задания и генераторы, созданные этой командой',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        course = Course.objects.filter(slug=COURSE_SLUG).first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=%s) не найден.' % COURSE_SLUG))
            return

        module, _ = Module.objects.get_or_create(
            course=course, title=MODULE_TITLE, defaults={'order': 2, 'description': ''},
        )

        lesson = Lesson.objects.filter(module=module, title__startswith='№24').first()
        created_lesson = False
        if lesson is None:
            lesson = Lesson.objects.create(
                module=module, title=LESSON_TITLE, order=24, lesson_type='practice',
            )
            created_lesson = True
        self.stdout.write('Урок: «%s»%s'
                          % (lesson.title, ' (создан)' if created_lesson else ''))

        ids = [GENERATOR_BASE + n for n, _ in TYPES]

        if opts['clear']:
            удалено = Assignment.objects.filter(
                lesson=lesson, problem_generator_id__in=ids).delete()[0]
            ProblemGenerator.objects.filter(id__in=ids).delete()
            self.stdout.write(self.style.WARNING(
                'Удалено заданий: %d, генераторов: %d' % (удалено, len(ids))))
            return

        # Номера 1101…1125 зарезервированы за №24: чужой генератор под таким
        # номером затирать нельзя, к нему привязаны чьи-то задания.
        занято = ProblemGenerator.objects.filter(
            id__in=ids).exclude(name__startswith='OGE24:')
        if занято.exists():
            self.stdout.write(self.style.ERROR(
                'Номера %d…%d заняты чужими генераторами: %s. Заливка отменена.'
                % (ids[0], ids[-1],
                   ', '.join('%d (%s)' % (g.id, g.name) for g in занято[:5]))))
            raise SystemExit(1)

        for num, title in TYPES:
            gid = GENERATOR_BASE + num
            generator, _ = ProblemGenerator.objects.update_or_create(
                id=gid,
                defaults={
                    'name': 'OGE24: Сюжет %d — %s' % (num, title),
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
                'title': 'Сюжет %d. %s' % (num, title),
                'assignment_type': 'test',
                'answer_type': 'text_input',
                'required_correct': 1,
                'points': 2,
                'problem_generator': generator,
                'order': num,
            }
            if assignment:
                fields.pop('title')          # название могли поправить руками
                for key, value in fields.items():
                    setattr(assignment, key, value)
                assignment.save()
            else:
                Assignment.objects.create(lesson=lesson, description='', **fields)

        self.stdout.write(self.style.SUCCESS(
            '\nГотово: %d типов в уроке «%s».' % (len(TYPES), lesson.title)))
