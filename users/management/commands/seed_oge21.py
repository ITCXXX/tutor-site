# -*- coding: utf-8 -*-
"""
Создаёт урок №21 курса ОГЭ и наполняет его генераторами всех 20 типов.

Устройство то же, что у seed_oge20: платформа исполняет файл
users/generators/g<id>.py, поэтому id фиксированные — 950 + номер типа
(951 … 970; 901 … 925 занял №20). Математика живёт в
users/oge21_generators.py и проверяется oge21_setup/verify_oge21.py.

Запуск:
    python manage.py seed_oge21            # создать/обновить 20 заданий
    python manage.py seed_oge21 --clear    # снести всё, что создала команда
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Assignment, Course, Lesson, Module, ProblemGenerator

COURSE_SLUG = 'oge-maths'
MODULE_TITLE = 'Вторая часть'
LESSON_TITLE = '№21. Текстовые задачи'
GENERATOR_BASE = 950

TYPES = [
    (1, 'Велосипедист туда и обратно'),
    (2, 'Два велосипедиста на дистанции'),
    (3, 'Два автомобиля на дистанции'),
    (4, 'Встречное движение с остановкой'),
    (5, 'Половины пути с разными скоростями'),
    (6, 'Средняя скорость: три участка'),
    (7, 'Средняя скорость: две половины'),
    (8, 'Теплоход: найти скорость течения'),
    (9, 'Теплоход: найти собственную скорость'),
    (10, 'Лодка против течения и обратно'),
    (11, 'Баржа: разные расстояния туда и обратно'),
    (12, 'Плот и моторная лодка'),
    (13, 'Круговая трасса'),
    (14, 'Поезд навстречу пешеходу'),
    (15, 'Поезд вдогон пешеходу'),
    (16, 'Два рабочих'),
    (17, 'Две трубы'),
    (18, 'Сухофрукты: сколько получится'),
    (19, 'Сухофрукты: сколько нужно'),
    (20, 'Два сосуда с раствором'),
]

BACKUP_CODE = (
    '# Исполняется не этот текст, а users/generators/g{gid}.py.\n'
    '# Поле python_code оставлено как справка для админки.\n'
    'from users.oge21_generators import as_task\n'
    '\n'
    'def generate_task():\n'
    '    return as_task({num})\n'
)


class Command(BaseCommand):
    help = 'Создаёт генераторы и задания №21 (текстовые задачи) курса ОГЭ.'

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

        lesson = Lesson.objects.filter(module=module, title__startswith='№21').first()
        created_lesson = False
        if lesson is None:
            lesson = Lesson.objects.create(
                module=module, title=LESSON_TITLE, order=21, lesson_type='practice',
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

        # Номера 951…970 зарезервированы за №21: чужой генератор под таким
        # номером затирать нельзя, к нему привязаны чьи-то задания.
        занято = ProblemGenerator.objects.filter(
            id__in=ids).exclude(name__startswith='OGE21:')
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
                    'name': 'OGE21: Тип %d — %s' % (num, title),
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
                fields.pop('title')          # название могли поправить руками
                for key, value in fields.items():
                    setattr(assignment, key, value)
                assignment.save()
            else:
                Assignment.objects.create(lesson=lesson, description='', **fields)

        self.stdout.write(self.style.SUCCESS(
            '\nГотово: %d типов в уроке «%s».' % (len(TYPES), lesson.title)))
