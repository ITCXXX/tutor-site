# -*- coding: utf-8 -*-
"""Матч ботов «Заборов»: измерить, стало ли сильнее.

    manage.py quoridor_arena --a hard --b medium --games 200
    manage.py quoridor_arena --a-weights веса.json --a hard --b hard --games 400
    manage.py quoridor_arena --gauntlet --a-weights веса.json

Без этого «стало сильнее» проверяется на глаз, а на глаз оно проверяется плохо:
у крестиков-ноликов так уже был сделан неверный вывод про глубину перебора.
"""

import json
import os
import time

from django.core.management.base import BaseCommand, CommandError

from quoridor import arena, bot


class Command(BaseCommand):
    help = 'Матч ботов «Заборов» с доверительным интервалом.'

    def add_arguments(self, parser):
        parser.add_argument('--a', default='hard', help='уровень первого игрока')
        parser.add_argument('--b', default='medium', help='уровень второго')
        parser.add_argument('--a-weights', dest='веса_a', default=None,
                            help='JSON с весами оценки первого игрока')
        parser.add_argument('--b-weights', dest='веса_b', default=None,
                            help='то же для второго')
        parser.add_argument('--games', dest='партий', type=int, default=200)
        parser.add_argument('--cores', dest='ядер', type=int, default=None)
        parser.add_argument('--seed', dest='зерно', type=int, default=0)
        parser.add_argument('--gauntlet', dest='перчатка', action='store_true',
                            help='матчи против всех неподвижных уровней')

    def _уровень(self, значение, откуда):
        """Неизвестное имя уровня bot.level_of молча подменяет средним — для
        игры это верно, для замера губительно: опечатка в «--a hrad» дала бы
        правдоподобные числа не про то."""
        if значение not in bot.ALL_LEVELS:
            raise CommandError('неизвестный уровень «%s» в %s. Есть: %s'
                               % (значение, откуда, ', '.join(bot.ALL_LEVELS)))
        return значение

    def _игрок(self, метка, уровень, путь_к_весам):
        if not путь_к_весам:
            return arena.Игрок('%s (%s)' % (метка, уровень), уровень)
        try:
            with open(путь_к_весам, encoding='utf-8') as файл:
                свои = json.load(файл)
        except (OSError, ValueError) as беда:
            raise CommandError('не читается файл весов %s: %s'
                               % (путь_к_весам, беда))
        лишние = set(свои) - set(bot.ВЕСА)
        if лишние:
            raise CommandError('в файле весов лишние ключи: %s. Допустимые: %s'
                               % (', '.join(sorted(лишние)),
                                  ', '.join(sorted(bot.ВЕСА))))
        полные = dict(bot.ВЕСА)
        полные.update(свои)
        имя = '%s (%s, %s)' % (метка, уровень, os.path.basename(путь_к_весам))
        return arena.игрок_из_весов(имя, полные, уровень)

    def handle(self, *args, **п):
        ядер = п['ядер'] or max(1, (os.cpu_count() or 2) - 1)
        первый = self._игрок('A', self._уровень(п['a'], '--a'), п['веса_a'])
        начало = time.perf_counter()

        if п['перчатка']:
            соперники = [arena.Игрок('сильный', 'hard'),
                         arena.Игрок('средний', 'medium'),
                         arena.Игрок('слабый', 'easy')]
            self.stdout.write('Перчатка: %s против %d соперников, по %d партий, '
                              'ядер %d'
                              % (первый.имя, len(соперники), п['партий'], ядер))
            итоги, общая = arena.перчатка(первый, соперники, п['партий'], ядер,
                                          п['зерно'])
            self.stdout.write('')
            for соперник, итог in итоги:
                self.stdout.write('  ' + итог.словами(первый.имя, соперник.имя))
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                'Общая доля очков: %.1f%%' % (100 * общая)))
        else:
            второй = self._игрок('B', self._уровень(п['b'], '--b'), п['веса_b'])
            self.stdout.write('Матч: %s против %s, %d партий, ядер %d'
                              % (первый.имя, второй.имя, п['партий'], ядер))
            итог = arena.матч(первый, второй, п['партий'], ядер, п['зерно'])
            self.stdout.write('')
            self.stdout.write(итог.словами(первый.имя, второй.имя))
            if not итог.значимо:
                self.stdout.write(
                    'Чтобы различить такую разницу, партий нужно больше: '
                    'погрешность падает вчетверо медленнее, чем растёт их число.')

        self.stdout.write('')
        self.stdout.write('Заняло %.1f мин' % ((time.perf_counter() - начало) / 60))
