# -*- coding: utf-8 -*-
"""Убрать с диска файлы досок, на которые уже никто не ссылается.

ОТКУДА БЕРЁТСЯ МУСОР. Удаление картинки с доски убирает объект, но не файл — и
это правильно: отмена (Ctrl+Z) возвращает объект вместе с прежним адресом, и
если файл убрать сразу, отменённая картинка окажется битой. Значит файл должен
пережить отмену — но не полгода.

СРОК. По умолчанию трогаем только то, что старше семи дней. За неделю отменять
уже некому: занятие давно кончилось, вкладку закрыли, история отмены живёт лишь
в памяти открытой страницы.

БЕЗ ФЛАГА КОМАНДА НИЧЕГО НЕ УДАЛЯЕТ — только показывает. Чтобы правда убрать,
нужен --применить.

    venv/bin/python manage.py убрать_ненужные_файлы
    venv/bin/python manage.py убрать_ненужные_файлы --применить
    venv/bin/python manage.py убрать_ненужные_файлы --дней 30 --применить
"""

import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from board.models import Board
from board.views import _файлы_в_ходу


class Command(BaseCommand):
    help = 'Убрать файлы досок, на которые не ссылается ни один объект'

    def add_arguments(self, parser):
        parser.add_argument('--применить', action='store_true',
                            help='действительно удалить файлы')
        parser.add_argument('--дней', type=int, default=7,
                            help='не трогать файлы моложе стольких дней (по умолчанию 7)')

    def handle(self, *args, **опции):
        корень = os.path.join(settings.MEDIA_ROOT, 'board')
        if not os.path.isdir(корень):
            self.stdout.write('Папки с файлами досок нет — нечего делать.')
            return

        применить = опции['применить']
        порог = time.time() - опции['дней'] * 86400
        коды_досок = set(Board.objects.values_list('code', flat=True))

        всего_файлов = всего_байт = 0
        молодых = 0

        for доска in sorted(os.listdir(корень)):
            папка = os.path.join(корень, доска)
            if not os.path.isdir(папка):
                continue

            если_доски_нет = доска not in коды_досок
            в_ходу = set() if если_доски_нет else _файлы_в_ходу(доска)

            лишние = []
            for имя in sorted(os.listdir(папка)):
                путь = os.path.join(папка, имя)
                if not os.path.isfile(путь) or имя in в_ходу:
                    continue
                if os.path.getmtime(путь) > порог:
                    молодых += 1        # ещё может понадобиться для отмены
                    continue
                лишние.append((имя, os.path.getsize(путь)))

            if not лишние:
                continue

            подпись = доска + (' (доски уже нет)' if если_доски_нет else '')
            вес = sum(b for _, b in лишние)
            self.stdout.write('  %-28s %d файлов, %.1f МБ' %
                              (подпись, len(лишние), вес / 1048576.0))
            всего_файлов += len(лишние)
            всего_байт += вес

            if применить:
                for имя, _ in лишние:
                    try:
                        os.remove(os.path.join(папка, имя))
                    except OSError as e:
                        self.stderr.write('    не удалось убрать %s: %s' % (имя, e))

        self.stdout.write('')
        if молодых:
            self.stdout.write('Пропущено как слишком свежих (моложе %d дней): %d'
                              % (опции['дней'], молодых))
        if not всего_файлов:
            self.stdout.write('Лишних файлов нет.')
            return
        if применить:
            self.stdout.write('Убрано файлов: %d, освобождено %.1f МБ.'
                              % (всего_файлов, всего_байт / 1048576.0))
        else:
            self.stdout.write('Нашлось лишних: %d файлов на %.1f МБ.'
                              % (всего_файлов, всего_байт / 1048576.0))
            self.stdout.write('Ничего не удалено. Чтобы убрать — добавьте --применить')
