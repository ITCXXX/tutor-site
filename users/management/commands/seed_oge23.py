# -*- coding: utf-8 -*-
"""
Создаёт урок №23 курса ОГЭ и наполняет его генераторами всех 20 типов.

Устройство то же, что у seed_oge20: платформа исполняет файл
users/generators/g<id>.py, поэтому id фиксированные — 950 + номер типа
(1201 … 1220). Математика живёт в
users/oge23_generators.py и проверяется oge23_setup/verify_geom.py --task 23.

Запуск:
    python manage.py seed_oge23            # создать/обновить 20 заданий
    python manage.py seed_oge23 --clear    # снести всё, что создала команда
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Assignment, Course, Lesson, Module, ProblemGenerator

COURSE_SLUG = 'oge-maths'
MODULE_TITLE = 'Вторая часть'
LESSON_TITLE = '№23. Геометрические задачи на вычисление'
GENERATOR_BASE = 1200

TYPES = [
    (1, 'Трапеция: отрезок диагонали через подобие'),
    (2, 'Прямая, параллельная стороне треугольника'),
    (3, 'Высота к гипотенузе по двум катетам'),
    (4, 'Высота к гипотенузе по катету и гипотенузе'),
    (5, 'Катет через проекцию на гипотенузу'),
    (6, 'Биссектриса угла параллелограмма: периметр'),
    (7, 'Ромб: высота делит сторону'),
    (8, 'Ромб: расстояние от центра до стороны, углы'),
    (9, 'Трапеция: биссектрисы при боковой стороне'),
    (10, 'Трапеция: боковая сторона по углам'),
    (11, 'Трапеция: отрезок, параллельный основаниям'),
    (12, 'Две хорды: расстояние до второй'),
    (13, 'Две хорды: длина второй'),
    (14, 'Сторона через радиус описанной окружности'),
    (15, 'Окружность на высоте: хорда'),
    (16, 'Окружность на высоте: сама высота'),
    (17, 'Антипараллель: KP через AK'),
    (18, 'Антипараллель: KP через AP'),
    (19, 'Касание в вершине: сторона AC'),
    (20, 'Касание в вершине: диаметр'),
]

BACKUP_CODE = (
    '# Исполняется не этот текст, а users/generators/g{gid}.py.\n'
    '# Поле python_code оставлено как справка для админки.\n'
    'from users.oge23_generators import as_task\n'
    '\n'
    'def generate_task():\n'
    '    return as_task({num})\n'
)


class Command(BaseCommand):
    help = 'Создаёт генераторы и задания №23 (геометрия) курса ОГЭ.'

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

        lesson = Lesson.objects.filter(module=module, title__startswith='№23').first()
        created_lesson = False
        if lesson is None:
            lesson = Lesson.objects.create(
                module=module, title=LESSON_TITLE, order=23, lesson_type='practice',
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

        # Номера 1201…1220 зарезервированы за №23: чужой генератор под таким
        # номером затирать нельзя, к нему привязаны чьи-то задания.
        занято = ProblemGenerator.objects.filter(
            id__in=ids).exclude(name__startswith='OGE23:')
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
                    'name': 'OGE23: Тип %d — %s' % (num, title),
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
                'answer_type': 'text_input',
                'required_correct': 3,
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
