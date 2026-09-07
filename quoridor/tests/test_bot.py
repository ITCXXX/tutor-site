# -*- coding: utf-8 -*-
"""
Проверка серверного бота «Заборов» и стенда.

Бот здесь не для игры — играет браузерный (static/quoridor/js/bot.js). Этот
нужен, чтобы силу можно было ИЗМЕРЯТЬ: стенд играет сотни партий и говорит,
значима ли разница. Отсюда и предмет проверки: не «хорошо ли он играет», а
«законны ли его ходы, кончаются ли партии, считает ли стенд то, что обещает».

Отдельная и самая важная группа — страховка боевого сайта. Размер поля стал
параметром ради разбора игры на маленьких досках, и надо быть уверенным, что
стандартная девятка от этого не сдвинулась ни на бит: её состояние, её
отпечаток, её число заборов.
"""

import random

from django.test import SimpleTestCase

from quoridor import arena, bot, engine


class РазмерПоля(SimpleTestCase):
    """Девятка обязана остаться ровно такой, какой была.

    Состояния лежат в базе и приходят из браузера, а отпечаток позиции — якорь
    сверки с браузерными правилами. Сдвинься тут что-нибудь, и сетевая партия
    разошлась бы с локальной, причём не сразу и не очевидно.
    """

    def test_стандартное_поле_не_изменилось(self):
        s = engine.initial_state()
        self.assertEqual(engine.размер(s), 9)
        self.assertEqual(s['pawns'][engine.RED], {'r': 8, 'c': 4})
        self.assertEqual(s['pawns'][engine.BLUE], {'r': 0, 'c': 4})
        self.assertEqual(s['goalRow'], {engine.RED: 0, engine.BLUE: 8})
        self.assertEqual(s['wallsLeft'], {engine.RED: 10, engine.BLUE: 10})

    def test_отпечаток_не_включает_размер(self):
        """Иначе сверка с браузером сломалась бы вся разом: там размера нет."""
        s = engine.initial_state()
        без_размера = {к: в for к, в in s.items() if к != 'n'}
        self.assertEqual(engine.state_signature(s),
                         engine.state_signature(без_размера))
        self.assertNotIn('n9', engine.state_signature(s).split('|')[0])

    def test_старое_состояние_без_размера_считается_девяткой(self):
        """Так приходят партии из базы и из браузера."""
        s = engine.initial_state()
        del s['n']
        self.assertEqual(engine.размер(s), 9)
        self.assertEqual(len(engine.pawn_moves(s, engine.RED)), 3)

    def test_маленькое_поле_меньше_и_заборов_меньше(self):
        s = engine.initial_state(5)
        self.assertEqual(engine.размер(s), 5)
        self.assertEqual(s['pawns'][engine.RED], {'r': 4, 'c': 2})
        self.assertEqual(s['wallsLeft'][engine.RED], 3)
        self.assertEqual(engine.сетка_заборов(5), 4)

    def test_за_краем_маленького_поля_забор_не_ставится(self):
        """Сетка якорей меньше вместе с полем; проверка должна это знать."""
        s = engine.initial_state(5)
        self.assertIsNone(engine.wall_problem(s, engine.RED, 3, 3, 'h'))
        self.assertIsNotNone(engine.wall_problem(s, engine.RED, 4, 4, 'h'))


class Путь(SimpleTestCase):

    def test_путь_и_его_длина_согласованы(self):
        s = engine.initial_state()
        for сторона in (engine.RED, engine.BLUE):
            длина = engine.shortest_path(s['walls'], s['pawns'][сторона],
                                         s['goalRow'][сторона])
            путь = engine.path_to(s['walls'], s['pawns'][сторона],
                                  s['goalRow'][сторона])
            self.assertEqual(len(путь) - 1, длина)
            self.assertEqual(путь[0], s['pawns'][сторона])
            self.assertEqual(путь[-1]['r'], s['goalRow'][сторона])

    def test_соседние_клетки_пути_рядом(self):
        s = engine.initial_state(7)
        путь = engine.path_to(s['walls'], s['pawns'][engine.RED],
                              s['goalRow'][engine.RED], 7)
        for a, b in zip(путь, путь[1:]):
            self.assertEqual(abs(a['r'] - b['r']) + abs(a['c'] - b['c']), 1)


class ХодыБота(SimpleTestCase):

    def _партия(self, уровень, n=9, seed=1, предел=400):
        rng = random.Random(seed)
        s = engine.initial_state(n)
        ходов = 0
        while not s['winner'] and ходов < предел:
            сторона = s['turn']
            ход = bot.choose_move(s, сторона, уровень, rng)
            self.assertIsNotNone(ход, 'бот не нашёл хода на %s' % уровень)
            s, ошибка = bot.apply_choice(s, сторона, ход)
            self.assertIsNone(ошибка, 'недопустимый ход бота: %s' % ошибка)
            ходов += 1
        return s, ходов

    def test_ходы_законны_и_партия_кончается(self):
        for уровень in bot.ALL_LEVELS:
            s, ходов = self._партия(уровень, n=5)
            self.assertIsNotNone(s['winner'],
                                 'партия на %s не кончилась за %d полуходов'
                                 % (уровень, ходов))

    def test_играет_на_поле_любого_размера(self):
        for n in (5, 7, 9):
            s, _ = self._партия('easy', n=n, seed=n)
            self.assertIsNotNone(s['winner'])

    def test_берёт_выигрыш_в_один_ход(self):
        """Фишка в шаге от своего края обязана этот шаг сделать."""
        s = engine.initial_state(5)
        s['pawns'][engine.RED] = {'r': 1, 'c': 2}
        ход = bot.choose_move(s, engine.RED, 'medium', random.Random(3))
        self.assertEqual(ход['kind'], 'move')
        self.assertEqual(ход['r'], 0)

    def test_ничьи_разрешаются_в_пользу_продвижения(self):
        """Лечение буриданова осла: из равных по оценке ходов берутся те, что
        ближе подводят к цели. Замер показывал, что на среднем уровне в 2-6%
        решений первое место делят ходы в разные стороны, и бот бросал монетку —
        со стороны это выглядело метанием."""
        s = engine.initial_state(7)
        s['pawns'][engine.RED] = {'r': 3, 'c': 3}
        вперёд = {'kind': 'move', 'r': 2, 'c': 3}
        назад = {'kind': 'move', 'r': 4, 'c': 3}
        оставшиеся = bot._ближе_к_цели(s, engine.RED, [назад, вперёд])
        self.assertEqual(оставшиеся, [вперёд])

    def test_свои_веса_доезжают_до_оценки(self):
        """Иначе стенд сравнивал бы одно и то же под разными именами."""
        s = engine.initial_state()
        s['wallsLeft'][engine.RED] = 3
        обычная = bot.evaluate(s, engine.RED)
        дорогие = bot.evaluate(s, engine.RED, {'шаг': 10.0, 'забор': 100.0})
        self.assertNotEqual(обычная, дорогие)


class Стенд(SimpleTestCase):

    def test_дебют_случайный_но_воспроизводимый(self):
        первый = arena._случайный_дебют(5)
        второй = arena._случайный_дебют(5)
        другой = arena._случайный_дебют(6)
        self.assertEqual(engine.state_signature(первый),
                         engine.state_signature(второй))
        self.assertNotEqual(engine.state_signature(первый),
                            engine.state_signature(другой))
        self.assertIsNone(первый['winner'])

    def test_дебют_на_маленьком_поле_остаётся_маленьким(self):
        поз = arena._случайный_дебют(4, n=5)
        self.assertEqual(engine.размер(поз), 5)

    def test_матч_идёт_парами_туда_и_обратно(self):
        слабый = arena.Игрок('слабый', 'easy')
        итог = arena.матч(слабый, слабый, партий=6, ядер=1, seed=3, n=5)
        self.assertEqual(итог.партий, 6)
        self.assertEqual(итог.партий % 2, 0)

    def test_сильный_обыгрывает_слабого(self):
        итог = arena.матч(arena.Игрок('средний', 'medium'),
                          arena.Игрок('слабый', 'easy'),
                          партий=30, ядер=1, seed=5, n=5)
        self.assertGreater(итог.доля, 0.5)
