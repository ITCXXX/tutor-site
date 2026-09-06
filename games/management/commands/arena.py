# -*- coding: utf-8 -*-
"""Турнир между ботами УТТТ — чтобы «стало сильнее» было измеримым.

Примеры:

    manage.py arena --a hard --b medium
    manage.py arena --a hard --b hard --games 400 --cores 12
    manage.py arena --a-weights веса.json --b hard --games 300
    manage.py arena --gauntlet --a-weights веса.json

Файл весов — обычный JSON с теми ключами, что в games.bot.ВЕСА; указывать можно
не все, недостающие берутся из стандартных.

Про «перчатку» (--gauntlet). Это матчи против НЕПОДВИЖНОГО набора соперников:
сильного, среднего и слабого уровней. Она нужна затем, что бот, которого
отбирали против его же потомков, становится мастером по обыгрыванию родни и
может при этом ослабеть против всех прочих. Проверять надо на тех, кто не
менялся.
"""

import json
import os
import time

from django.core.management.base import BaseCommand, CommandError

from games import arena, bot, features


class Command(BaseCommand):
    help = 'Матч между настройками бота УТТТ с оценкой погрешности'

    def add_arguments(self, parser):
        parser.add_argument('--a', default='hard', help='уровень первого игрока')
        parser.add_argument('--b', default='medium', help='уровень второго игрока')
        parser.add_argument('--a-weights', dest='веса_a', default=None,
                            help='JSON-файл с весами первого игрока')
        parser.add_argument('--b-weights', dest='веса_b', default=None,
                            help='JSON-файл с весами второго игрока')
        parser.add_argument('--games', dest='партий', type=int, default=200)
        parser.add_argument('--cores', dest='ядер', type=int, default=None,
                            help='по умолчанию — все, кроме одного')
        parser.add_argument('--seed', dest='зерно', type=int, default=0)
        parser.add_argument('--gauntlet', dest='перчатка', action='store_true',
                            help='матчи против неподвижного набора соперников')

    def handle(self, *args, **п):
        ядер = п['ядер'] or max(1, (os.cpu_count() or 2) - 1)

        первый = self._игрок('A', self._уровень(п['a'], '--a'), п['веса_a'])
        начало = time.perf_counter()

        if п['перчатка']:
            соперники = [
                arena.Игрок('сильный', 'hard'),
                arena.Игрок('средний', 'medium'),
                arena.Игрок('слабый', 'easy'),
            ]
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
            второй = self._игрок('B', self._уровень(п['b'], '--b'),
                                 п['веса_b'])
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

    def _уровень(self, значение, откуда):
        """Проверить имя уровня.

        bot.choose_move на незнакомое имя молча берёт средний уровень — для
        боевого сайта это верно (кривое значение в базе не должно ронять
        страницу), а для стенда губительно: опечатка в «--a hrad» дала бы
        правдоподобные числа не про то. Один раз это чуть не случилось.
        """
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

        # Имя признака можно снабдить суффиксом «@номер» — это его вес на
        # соответствующей стадии партии. Проверяем основу имени, а не всё
        # целиком: иначе набор весов по стадиям стенд бы не принял.
        лишние = {имя for имя in свои
                  if имя.rsplit('@', 1)[0] not in features.ПРИЗНАКИ}
        if лишние:
            raise CommandError('в файле весов лишние ключи: %s. Допустимые: %s'
                               % (', '.join(sorted(лишние)),
                                  ', '.join(features.ПРИЗНАКИ)))
        полные = dict(bot.ВЕСА)
        полные.update(свои)
        имя = '%s (%s, %s)' % (метка, уровень, os.path.basename(путь_к_весам))
        return arena.игрок_из_весов(имя, полные, уровень)
