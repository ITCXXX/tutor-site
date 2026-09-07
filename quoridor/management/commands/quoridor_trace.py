# -*- coding: utf-8 -*-
"""
Генерирует след случайных партий для сверки двух реализаций правил.

След пишет питоновский движок, а проверяют его обе стороны: тест
`quoridor/tests/test_engine.py` — здесь, модуль `js/tracecheck.js` — в браузере.
Файл лежит в статике именно затем, чтобы браузер мог его забрать.

    python manage.py quoridor_trace            # 6 партий, зерно по умолчанию
    python manage.py quoridor_trace --games 20 --seed 7
"""

import json
import os
import random

from django.core.management.base import BaseCommand

from quoridor import bot, engine

TRACE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'static', 'quoridor', 'data', 'rules_trace.json',
)

WALL_CHANCE = 0.35      # как часто случайный игрок предпочтёт забор шагу
MAX_PLIES = 400         # страховка от зацикливания: партия обязана кончаться

# Глубина, на которой сверяются боты. Не боевая: у настоящих уровней есть СРОК,
# а он в браузере и на сервере истекает в разных местах — сравнивать ход в ход
# было бы нечем. Двух полуходов достаточно, чтобы задействовать весь тракт:
# отбор ходов, оценку заборов, перебор и разрешение ничьих.
BOT_DEPTH = 2
BOT_CANDIDATES = 14


def _move_name(mv):
    """Имя хода в той же записи, что и ходы следа."""
    if mv['kind'] == 'move':
        return 'm,%d,%d' % (mv['r'], mv['c'])
    return 'w,%d,%d,%s' % (mv['wr'], mv['wc'], mv['orient'])


def _bot_view(st, side):
    """Как бот видит позицию: оценка каждого хода и что остаётся после ничьих.

    Срок снят намеренно (см. BOT_DEPTH): сравнивается устройство, а не то,
    чей процессор быстрее.
    """
    level = dict(bot.LEVELS['medium'])
    level['depth'] = BOT_DEPTH
    level['candidates'] = BOT_CANDIDATES
    level['budget'] = 10 ** 6
    срок = bot._Срок(level['budget'])

    оценки = []
    for mv in bot.candidates(st, side, level['candidates']):
        следом = bot._применить(st, side, mv)
        if следом is None:
            continue
        очки = -bot.search(следом, engine.other(side), level['depth'] - 1,
                           -float('inf'), float('inf'), level, срок, None)
        оценки.append((mv, int(round(очки))))

    if not оценки:
        return [], []
    лучшая = max(о for _, о in оценки)
    верхние = [mv for mv, о in оценки if о == лучшая]
    if len(верхние) > 1:
        верхние = bot._ближе_к_цели(st, side, верхние)
    return ([('%s=%d' % (_move_name(mv), о)) for mv, о in оценки],
            sorted(_move_name(mv) for mv in верхние))


def play_one(rng):
    """Одна случайная партия. Возвращает след: ходы, отпечатки и замеры."""
    st = engine.initial_state()
    moves, digests = [], []
    pawn_sigs, wall_counts, paths = [], [], []
    bot_scores, bot_tops = [], []

    while st['winner'] is None and len(moves) < MAX_PLIES:
        side = st['turn']

        # Замеры снимаются ДО хода — тогда расхождение видно на той позиции,
        # где оно возникло, а не на следующей.
        pawn_sigs.append(engine.legal_pawn_signature(st, side))
        wall_counts.append(engine.legal_wall_count(st, side))
        paths.append([
            engine.shortest_path(st['walls'], st['pawns'][engine.RED],
                                 st['goalRow'][engine.RED]),
            engine.shortest_path(st['walls'], st['pawns'][engine.BLUE],
                                 st['goalRow'][engine.BLUE]),
        ])

        оценки, верхние = _bot_view(st, side)
        bot_scores.append(оценки)
        bot_tops.append(верхние)

        want_wall = st['wallsLeft'][side] > 0 and rng.random() < WALL_CHANCE
        picked = None

        if want_wall:
            # Тычемся в случайные пазы, а не перебираем все допустимые:
            # так в след попадают и заведомо неудачные попытки соседних клеток.
            for _ in range(30):
                wr, wc = rng.randrange(engine.W), rng.randrange(engine.W)
                kind = rng.choice(('h', 'v'))
                if engine.wall_problem(st, side, wr, wc, kind) is None:
                    picked = ('w', wr, wc, kind)
                    break

        if picked is None:
            opts = engine.pawn_moves(st, side)
            # Совсем случайный шаг бродит по доске и партия не кончается,
            # поэтому в трёх случаях из четырёх идём к своему краю.
            if rng.random() < 0.75:
                goal = st['goalRow'][side]
                best = min(engine.shortest_path(st['walls'], m, goal) or 99 for m in opts)
                opts = [m for m in opts
                        if (engine.shortest_path(st['walls'], m, goal) or 99) == best]
            m = rng.choice(opts)
            picked = ('m', m['r'], m['c'])

        if picked[0] == 'm':
            st, err = engine.apply_move(st, side, picked[1], picked[2])
        else:
            st, err = engine.apply_wall(st, side, picked[1], picked[2], picked[3])
        assert err is None, err

        moves.append(','.join(str(x) for x in picked))
        digests.append(engine.state_digest(st))

    assert st['winner'] is not None, 'партия не завершилась за %d полуходов' % MAX_PLIES
    return {
        'moves': moves,
        'digests': digests,
        'pawnMoves': pawn_sigs,
        'wallCounts': wall_counts,
        'paths': paths,
        'botScores': bot_scores,
        'botTop': bot_tops,
        'winner': st['winner'],
    }


class Command(BaseCommand):
    help = 'Записать след случайных партий «Заборов» для сверки JS и Python'

    def add_arguments(self, parser):
        parser.add_argument('--games', type=int, default=6)
        parser.add_argument('--seed', type=int, default=20260829)

    def handle(self, *args, **opts):
        rng = random.Random(opts['seed'])
        games = [play_one(rng) for _ in range(opts['games'])]

        trace = {
            'seed': opts['seed'],
            'wallChance': WALL_CHANCE,
            'botDepth': BOT_DEPTH,
            'botCandidates': BOT_CANDIDATES,
            'games': games,
        }
        os.makedirs(os.path.dirname(TRACE_PATH), exist_ok=True)
        with open(TRACE_PATH, 'w', encoding='utf-8') as fh:
            json.dump(trace, fh, ensure_ascii=False, separators=(',', ':'))

        plies = sum(len(g['moves']) for g in games)
        self.stdout.write(self.style.SUCCESS(
            'след записан: %d партий, %d полуходов, %.0f КБ, файл %s' % (
                len(games), plies, os.path.getsize(TRACE_PATH) / 1024, TRACE_PATH)))
