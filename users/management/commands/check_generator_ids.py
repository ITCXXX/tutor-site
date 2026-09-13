# -*- coding: utf-8 -*-
"""Проверить, что генераторы заданий 6–19 ОГЭ стоят под своими номерами.

Только читает, ничего не пишет — её можно запускать на сервере до и после
наполнения. Зачем она нужна: сайт исполняет файл users/generators/g<id>.py по
номеру id, и генератор под чужим номером не падает, а тихо отдаёт ученику
задачи из чужого файла (подробности — в users/generator_ids.py).

    python manage.py check_generator_ids
    python manage.py check_generator_ids --strict   # код выхода 1, если что-то не так
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from users.generator_ids import ЗАКРЕПЛЁННЫЕ
from users.models import Assignment, ProblemGenerator


class Command(BaseCommand):
    help = 'Проверить, что генераторы 6–19 ОГЭ стоят под закреплёнными номерами'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict', action='store_true',
            help='Завершиться с ошибкой, если хоть один генератор не на месте.',
        )

    def handle(self, *args, **параметры):
        папка = os.path.join(settings.BASE_DIR, 'users', 'generators')
        по_имени = {г.name: г for г in
                    ProblemGenerator.objects.filter(name__in=list(ЗАКРЕПЛЁННЫЕ))}
        по_номеру = {г.id: г for г in
                     ProblemGenerator.objects.filter(id__in=list(ЗАКРЕПЛЁННЫЕ.values()))}

        на_месте = не_заведено = 0
        беды = []
        for имя, номер in sorted(ЗАКРЕПЛЁННЫЕ.items(), key=lambda пара: пара[1]):
            if not os.path.exists(os.path.join(папка, 'g%d.py' % номер)):
                беды.append('нет файла g%d.py для «%s»' % (номер, имя))

            генератор = по_имени.get(имя)
            if генератор is None:
                не_заведено += 1
            elif генератор.id == номер:
                на_месте += 1
            else:
                заданий = Assignment.objects.filter(
                    problem_generator=генератор).count()
                беды.append(
                    '«%s» стоит под id=%d, должен под %d — заданий на нём %d, '
                    'и они исполняют чужой файл g%d.py'
                    % (имя, генератор.id, номер, заданий, генератор.id))

            занявший = по_номеру.get(номер)
            if занявший and занявший.name != имя:
                беды.append('номер %d закреплён за «%s», но занят «%s»'
                            % (номер, имя, занявший.name))

        self.stdout.write('Закреплённых генераторов: %d' % len(ЗАКРЕПЛЁННЫЕ))
        self.stdout.write('  на своём номере: %d' % на_месте)
        self.stdout.write('  ещё не заведены: %d' % не_заведено)
        for беда in беды:
            self.stdout.write(self.style.ERROR('  ' + беда))

        if беды:
            self.stdout.write(self.style.WARNING(
                'Не на месте: %d. Лечится повторным запуском сид-команд — '
                'сначала seed_oge16…seed_oge19, потом 6–15.' % len(беды)))
            if параметры.get('strict'):
                raise CommandError('Генераторы не на своих номерах: %d' % len(беды))
        else:
            self.stdout.write(self.style.SUCCESS('Все заведённые генераторы на своих номерах.'))
