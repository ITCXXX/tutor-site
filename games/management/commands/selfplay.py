# -*- coding: utf-8 -*-
"""Набрать данные самоигрой: позиции и то, чем кончилась партия.

    manage.py selfplay --games 20000

Кладёт CSV рядом с ботом. Дальше его читает `manage.py learn_eval`.
"""

import os
import time

from django.core.management.base import BaseCommand

from games import features, selfplay

ФАЙЛ = 'games/selfplay_data.csv'


class Command(BaseCommand):
    help = 'Сыграть партии самому с собой и записать позиции с исходами.'

    def add_arguments(self, parser):
        parser.add_argument('--games', dest='партий', type=int, default=5000)
        parser.add_argument('--level', dest='уровень', default='medium',
                            help='на каком уровне играть: easy/medium/hard')
        parser.add_argument('--cores', dest='ядер', type=int, default=None)
        parser.add_argument('--seed', dest='зерно', type=int, default=0)
        parser.add_argument('--random', dest='доля', type=float,
                            default=selfplay.ДОЛЯ_СЛУЧАЙНЫХ,
                            help='доля ходов наугад — ради разнообразия партий')
        parser.add_argument('--out', dest='файл', default=ФАЙЛ)

    def handle(self, *args, **п):
        ядер = п['ядер'] or max(1, (os.cpu_count() or 2) - 1)
        self.stdout.write(
            'Самоигра: %d партий на уровне «%s», ядер %d, наугад %.0f%% ходов'
            % (п['партий'], п['уровень'], ядер, 100 * п['доля']))

        начало = time.perf_counter()
        последний = [начало]

        def показывать(сколько):
            сейчас = time.perf_counter()
            if сейчас - последний[0] < 5:
                return
            последний[0] = сейчас
            self.stdout.write('  позиций: %d (%.0f в секунду)'
                              % (сколько, сколько / (сейчас - начало)))

        строки = selfplay.набрать(
            п['партий'], п['уровень'], ядер, п['зерно'], п['доля'],
            показывать=показывать)
        selfplay.записать(строки, п['файл'])
        дт = time.perf_counter() - начало

        выиграл = sum(1 for _, y in строки if y == 1.0)
        ничья = sum(1 for _, y in строки if y == 0.5)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Готово: %d позиций из %d партий за %.1f мин -> %s'
            % (len(строки), п['партий'], дт / 60, п['файл'])))
        self.stdout.write(
            'Метки: выигрыш ходящего %.1f%%, ничья %.1f%%, поражение %.1f%%'
            % (100 * выиграл / max(1, len(строки)),
               100 * ничья / max(1, len(строки)),
               100 * (len(строки) - выиграл - ничья) / max(1, len(строки))))
        self.stdout.write('Признаков в строке: %d' % len(features.ПРИЗНАКИ))
        self.stdout.write('')
        self.stdout.write('Дальше: manage.py learn_eval --data %s' % п['файл'])
