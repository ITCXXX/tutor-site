# -*- coding: utf-8 -*-
"""
Проверка правил «Заборов» на сервере.

Две группы:

  • разбор конкретных позиций — прыжок через соперника, обход по диагонали,
    запрет запирать сопернику дорогу;
  • прогон записанного следа. Файл `static/quoridor/data/rules_trace.json`
    делает `manage.py quoridor_trace`; тот же файл читает браузерная проверка
    `js/tracecheck.js`. Пока обе стороны сходятся на нём до последнего поля,
    сетевая партия не может разойтись с локальной.
"""

import json
import os

from django.test import SimpleTestCase

from quoridor import engine

TRACE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'quoridor', 'data', 'rules_trace.json',
)


def put(state, walls):
    """Разложить заборы прямо в позицию, минуя проверки — для разбора случаев."""
    s = engine.clone_state(state)
    for wr, wc, kind in walls:
        s['walls']['%d,%d' % (wr, wc)] = kind
    return s


class RulesTests(SimpleTestCase):

    def test_start(self):
        s = engine.initial_state()
        self.assertEqual(s['pawns'][engine.RED], {'r': 8, 'c': 4})   # e1
        self.assertEqual(s['pawns'][engine.BLUE], {'r': 0, 'c': 4})  # e9
        self.assertEqual(s['turn'], engine.RED)
        self.assertEqual(engine.cell_name(8, 4), 'e1')
        self.assertEqual(engine.cell_name(0, 4), 'e9')
        # с середины пустого поля до края ровно восемь шагов
        self.assertEqual(engine.shortest_path(s['walls'], s['pawns'][engine.RED], 0), 8)

    def test_jump_over_opponent(self):
        """Фишки лоб в лоб: разрешён прыжок через соперника на клетку за ним."""
        s = engine.initial_state()
        s['pawns'][engine.RED] = {'r': 5, 'c': 4}
        s['pawns'][engine.BLUE] = {'r': 4, 'c': 4}
        moves = {(m['r'], m['c']) for m in engine.pawn_moves(s, engine.RED)}
        self.assertIn((3, 4), moves)          # перепрыгнул
        self.assertNotIn((4, 4), moves)       # встать на соперника нельзя

    def test_diagonal_when_jump_blocked(self):
        """Если за соперником стена, прыжок заменяется обходом по диагонали."""
        s = engine.initial_state()
        s['pawns'][engine.RED] = {'r': 5, 'c': 4}
        s['pawns'][engine.BLUE] = {'r': 4, 'c': 4}
        s = put(s, [(3, 3, 'h')])             # стена над синим: 3,4 ↔ 4,4 закрыт
        s['pawns'][engine.RED] = {'r': 5, 'c': 4}
        moves = {(m['r'], m['c']) for m in engine.pawn_moves(s, engine.RED)}
        self.assertNotIn((3, 4), moves)
        self.assertIn((4, 3), moves)
        self.assertIn((4, 5), moves)

    def test_wall_may_not_cut_off(self):
        """Забор, отрезающий сопернику любой путь, отклоняется с объяснением."""
        s = engine.initial_state()
        s['pawns'][engine.BLUE] = {'r': 0, 'c': 0}
        # Угловую клетку одним забором не запереть: оба её выхода держит один и
        # тот же якорь, а горизонтальный и вертикальный забор на одном якоре
        # запрещены как крест. Запираем карман из двух клеток — a9 и a8:
        # вертикальный забор режет их правые стороны, горизонтальный — низ a8.
        s = put(s, [(0, 0, 'v')])
        problem = engine.wall_problem(s, engine.RED, 1, 0, 'h')
        self.assertIsNotNone(problem)
        self.assertIn('путь', problem.lower())

        walled = put(s, [(1, 0, 'h')])
        self.assertFalse(engine.has_path(walled['walls'], {'r': 0, 'c': 0}, 8))
        self.assertIsNone(engine.shortest_path(walled['walls'], {'r': 0, 'c': 0}, 8))

    def test_wall_crossing_and_overlap(self):
        s = engine.initial_state()
        s = put(s, [(4, 4, 'h')])
        self.assertIsNotNone(engine.wall_problem(s, engine.RED, 4, 4, 'v'))  # крест
        self.assertIsNotNone(engine.wall_problem(s, engine.RED, 4, 4, 'h'))  # то же место
        self.assertIsNotNone(engine.wall_problem(s, engine.RED, 4, 5, 'h'))  # наложение
        self.assertIsNone(engine.wall_problem(s, engine.RED, 4, 6, 'h'))     # рядом можно

    def test_walls_run_out(self):
        s = engine.initial_state()
        s['wallsLeft'][engine.RED] = 0
        self.assertIsNotNone(engine.wall_problem(s, engine.RED, 0, 0, 'h'))
        self.assertEqual(engine.legal_wall_count(s, engine.RED), 0)

    def test_reaching_goal_ends_game(self):
        s = engine.initial_state()
        s['pawns'][engine.RED] = {'r': 1, 'c': 4}
        s['pawns'][engine.BLUE] = {'r': 0, 'c': 0}   # чтобы не загораживал целевую клетку
        s, err = engine.apply_move(s, engine.RED, 0, 4)
        self.assertIsNone(err)
        self.assertEqual(s['winner'], engine.RED)
        # после победы ходов нет ни у кого
        s2, err2 = engine.apply_move(s, engine.BLUE, 1, 4)
        self.assertIsNotNone(err2)

    def test_move_out_of_turn_rejected(self):
        s = engine.initial_state()
        _, err = engine.apply_move(s, engine.BLUE, 1, 4)
        self.assertIsNotNone(err)


class TraceTests(SimpleTestCase):
    """
    Прогон записанного следа.

    Тест намеренно ничего не «пересчитывает по-своему»: он повторяет ровно те
    ходы, что записаны, и сверяет отпечаток позиции после каждого. Если правила
    здесь поедут, первый же расхождённый полуход назовёт себя по номеру.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(TRACE, encoding='utf-8') as fh:
            cls.trace = json.load(fh)

    def test_trace_replays(self):
        self.assertTrue(self.trace['games'], 'след пуст — перегенерируйте его')

        for gi, game in enumerate(self.trace['games']):
            st = engine.initial_state()
            for i, raw in enumerate(game['moves']):
                where = 'партия %d, полуход %d (%s)' % (gi + 1, i + 1, raw)
                side = st['turn']

                self.assertEqual(engine.legal_pawn_signature(st, side),
                                 game['pawnMoves'][i], 'ходы фишкой: ' + where)
                self.assertEqual(engine.legal_wall_count(st, side),
                                 game['wallCounts'][i], 'счёт заборов: ' + where)
                self.assertEqual(
                    [engine.shortest_path(st['walls'], st['pawns'][engine.RED],
                                          st['goalRow'][engine.RED]),
                     engine.shortest_path(st['walls'], st['pawns'][engine.BLUE],
                                          st['goalRow'][engine.BLUE])],
                    game['paths'][i], 'кратчайшие пути: ' + where)

                parts = raw.split(',')
                if parts[0] == 'm':
                    st, err = engine.apply_move(st, side, int(parts[1]), int(parts[2]))
                else:
                    st, err = engine.apply_wall(st, side, int(parts[1]),
                                                int(parts[2]), parts[3])
                self.assertIsNone(err, 'ход отклонён: %s — %s' % (where, err))
                self.assertEqual(engine.state_digest(st), game['digests'][i],
                                 'отпечаток позиции: ' + where)

            self.assertEqual(st['winner'], game['winner'], 'итог партии %d' % (gi + 1))

    def test_trace_is_substantial(self):
        """Страховка от следа, который «проходит», потому что в нём три хода."""
        plies = sum(len(g['moves']) for g in self.trace['games'])
        walls = sum(1 for g in self.trace['games'] for m in g['moves'] if m[0] == 'w')
        self.assertGreater(plies, 100, 'слишком короткий след')
        self.assertGreater(walls, 20, 'в следе почти нет заборов — правила стен не проверены')
