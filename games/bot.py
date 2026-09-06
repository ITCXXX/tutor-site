# -*- coding: utf-8 -*-
"""
games/bot.py — соперник-компьютер для UTTT.

Где он считает
--------------
На сервере. В «Заборах» бот живёт в браузере, потому что там локальная партия
целиком браузерная и правила уже лежат в JS. Здесь всё наоборот: правила UTTT
есть только на сервере (engine.py), состояние партии хранится в базе, а ход
приходит запросом. Переносить правила в браузер ради бота значило бы завести
вторую реализацию — ту самую, которую в «Заборах» приходится сверять следом.
Поэтому бот отвечает прямо в том же запросе, которым игрок сделал свой ход.

Отсюда главное ограничение: время ответа — это время запроса. Воркеров на
сайте немного, и бот, думающий секунду, занимает один из них на секунду.
Поэтому у перебора не глубина, а срок: он углубляется, пока не кончился
бюджет времени, и всегда возвращает лучший ход из последнего законченного
уровня. На нехватку времени это отвечает ослаблением игры, а не задержкой.

Как он считает
--------------
Негамакс с альфа-бета отсечениями по своему, быстрому представлению доски:
81 клетка целыми числами и девять состояний малых полей. Движок из engine.py
для перебора не годится — он копирует всю доску на каждый ход, а здесь ходов
десятки тысяч; здесь ход делается и откатывается на месте.

Оценка позиции считает то же, что считает человек: выигранные малые поля
(с надбавкой за центр и углы большого поля), пары в ряд с открытым третьим —
и в большом поле, и в малых, — и отдельно тот факт, что соперника отправили
в закрытое поле, откуда он ходит куда хочет.
"""

import random
import time

from .engine import VARIANT_CLASSIC, VARIANT_LONG, WINNING_LINES
from .features import (BOARD_WEIGHT, CELL_WEIGHT, DRAW, EMPTY, LINES_THROUGH,
                       O, X, ЧИСЛО_ПРИЗНАКОВ, вектор, кортеж_весов)

LEVELS = {
    'easy': {
        'title': 'слабый',
        'depth': 1,          # видит только свой ход
        'budget': 0.05,
        'blunder': 0.35,     # и в трети ходов нарочно выбирает не лучший
    },
    'medium': {
        'title': 'средний',
        'depth': 3,          # свой ход, ответ и свой следующий
        'budget': 0.12,
        'blunder': 0.05,
    },
    'hard': {
        'title': 'сильный',
        # Глубже пятого полухода игра не улучшается. Первый замер (по 20
        # партий) показывал, что глубина 6 даже ПРОИГРЫВАЕТ, 7:13, и причиной
        # была грубость оценки: перебор находил выгоду, которой на доске нет.
        # После подбора весов самоигрой это объяснение отпало — глубина 6
        # больше не проигрывает, но и не выигрывает: 52.0% ± 4.8% на 400
        # партиях в этом же сроке и 52.7% ± 5.6% на 300 партиях со СНЯТЫМ
        # сроком (бюджет 5 с). Значит, дело не в нехватке времени: перебор
        # упёрся в потолок по существу. Прибавка, если она и есть, меньше
        # погрешности, а стоит целого срока ответа вместо 0.13 с — не берём.
        'depth': 5,
        'budget': 0.30,      # и всё равно не дольше срока: ответ идёт в запросе
        'blunder': 0.0,
    },
}

DEFAULT_LEVEL = 'medium'
ALL_LEVELS = tuple(LEVELS)


def level_title(name):
    return LEVELS.get(name, LEVELS[DEFAULT_LEVEL])['title']


WIN_SCORE = 100000


class Position:
    """
    Доска в виде, удобном для перебора: ходы делаются и откатываются на месте.

    cells   — 81 клетка, индекс big * 9 + small, значения EMPTY/X/O
    boards  — 9 малых полей: EMPTY (идёт), X, O или DRAW
    """

    __slots__ = ('cells', 'boards', 'next_local', 'turn', 'winner', 'variant')

    def __init__(self, state, variant=VARIANT_CLASSIC):
        mark = {'': EMPTY, 'X': X, 'O': O, 'D': DRAW}
        self.cells = [mark[c] for row in state['board'] for c in row]
        self.boards = [mark[v] for v in state['big_board']]
        self.next_local = state['next_local']
        self.turn = X if state['current'] == 'X' else O
        self.winner = mark.get(state['winner'] or '', EMPTY)
        self.variant = variant

    # ── ходы ──

    def moves(self):
        """Допустимые ходы (big, small). Порядок — сразу удобный для отсечений."""
        if self.next_local is not None and self.boards[self.next_local] == EMPTY:
            targets = (self.next_local,)
        else:
            targets = tuple(i for i in range(9) if self.boards[i] == EMPTY)

        out = []
        for big in targets:
            base = big * 9
            for small in range(9):
                if self.cells[base + small] == EMPTY:
                    out.append((big, small))
        # Центр и углы вперёд: они чаще оказываются лучшими, а чем раньше
        # найден хороший ход, тем больше веток альфа-бета отрежет.
        out.sort(key=lambda m: -(CELL_WEIGHT[m[1]] * 4 + BOARD_WEIGHT[m[0]]))
        return out

    def play(self, big, small):
        """Сделать ход. Возвращает запись для отката."""
        player = self.turn
        idx = big * 9 + small
        self.cells[idx] = player

        undo = (big, small, self.next_local, self.winner, None)
        base = big * 9
        won = None

        for a, b, c in LINES_THROUGH[small]:
            if self.cells[base + a] == player and self.cells[base + b] == player \
                    and self.cells[base + c] == player:
                won = player
                break
        if won is None and all(self.cells[base + i] != EMPTY for i in range(9)):
            won = DRAW

        if won is not None:
            self.boards[big] = won
            if self.variant == VARIANT_LONG:
                # «Долгая дорога» стирает все незакрытые поля — для отката
                # приходится запомнить всю доску целиком. Случается редко.
                undo = (big, small, undo[2], undo[3], list(self.cells))
                for i in range(9):
                    if i != big and self.boards[i] == EMPTY:
                        for j in range(9):
                            self.cells[i * 9 + j] = EMPTY
            self.winner = self._big_winner()

        if self.winner == EMPTY:
            if self.variant == VARIANT_LONG and won is not None:
                self.next_local = None
            else:
                self.next_local = None if self.boards[small] != EMPTY else small

        # Очередь передаётся всегда, даже когда партия кончилась. В engine.py
        # не так — там `current` замирает, чтобы страница показала, чей был
        # последний ход. Здесь важнее другое: негамакс считает оценку глазами
        # того, чья очередь, и если она не перевернётся, выигрыш вернётся
        # родителю с обратным знаком.
        self.turn = O if player == X else X
        return undo

    def undo(self, rec, won_before):
        big, small, next_local, winner, snapshot = rec
        if snapshot is not None:
            self.cells = snapshot
        else:
            self.cells[big * 9 + small] = EMPTY
        self.boards[big] = won_before
        self.next_local = next_local
        self.winner = winner
        self.turn = O if self.turn == X else X

    def _big_winner(self):
        for a, b, c in WINNING_LINES:
            v = self.boards[a]
            if v in (X, O) and v == self.boards[b] == self.boards[c]:
                return v
        if all(v != EMPTY for v in self.boards):
            # Большая ничья решается числом выигранных полей — как в engine.py.
            sx = sum(1 for v in self.boards if v == X)
            so = sum(1 for v in self.boards if v == O)
            if sx > so:
                return X
            if so > sx:
                return O
            return DRAW
        return EMPTY


# ────────────────────────── оценка ──────────────────────────

# Цена каждого признака. Ключи — имена из features.ПРИЗНАКИ; чего здесь нет,
# то стоит ноль и в оценке не участвует.
#
# Веса подобраны самоигрой: manage.py arena_tune, 8 часов, 2344 поколения,
# 6 сентября 2026. Проверка на СИЛЬНОМ уровне против прежних весов — два
# независимых матча по 400 партий: 70.8% ± 4.4% и 73.1% ± 4.3%. Подбор шёл на
# среднем уровне, а проверка на сильном, поэтому выигрыш не приклеился к
# условиям отбора. На слабом уровне разница неотличима от случайности
# (53.2% ± 3.9% на 600 партиях): там глубина 1 и намеренная ошибка в трети
# ходов, оценка почти не участвует — слабый бот остался таким же битым.
#
# Что нашёл отбор. Цена выигранного поля почти целиком переехала из плоской
# «поле» в «большая_одна», которая начисляется за КАЖДУЮ незакрытую линию
# большого поля, где это поле стоит одно. Раньше любое поле стоило 160–200
# почти одинаково; теперь центр большого поля стоит до 4 × 94 = 378, угол до
# 3 × 94 = 283, бок до 2 × 94 = 189. Важно не сколько полей выиграно, а какие.
#
# Числа оставлены ровно такими, какими их нашёл отбор: округлять их — значит
# менять то, что проверено матчами, ради вида. Перебирать заново незачем,
# прирост нашёлся в первые секунды прогона, а 8 часов добавили к нему 6.4%.
ВЕСА = {
    'поле': 1.287,           # само по себе выигранное поле почти ничего
    'поле_центр': 0.57,      # не стоит: вся его цена в линиях, см. большая_одна
    'большая_пара': 265.59,  # две в ряд в большом поле — уже угроза выиграть
    'большая_одна': 94.44,   # одна в линии — это и есть настоящая цена поля
    'малая_пара': 28.618,    # внутри малого поля почти-победа дорога,
    'малая_одна': 2.588,     # а одиночная клетка в одиннадцать раз дешевле
    'малый_центр': 0.393,    # центр малого поля сам по себе почти не важен
    'свободный_выбор': 19.2, # право ходить куда угодно (почти не изменилось)

    # Признаки, заведённые под обучение. Нули здесь не заглушка, а честная
    # начальная точка: пока веса не подобраны по данным, оценка обязана
    # совпадать с прежней до последнего знака — иначе непонятно, что мерим.
    'поле_ровно_центр': 0.0,
    'малый_угол': 0.0,
    'цель_моя_пара': 0.0,
    'цель_чужая_пара': 0.0,
    'решающая_пара': 0.0,
    'угроза_пары': 0.0,
    'ход': 0.0,
    'ничьи_в_плюс': 0.0,
}


def evaluate(pos, me, веса=None):
    """Оценка позиции глазами игрока `me`. Больше — лучше.

    Это скалярное произведение вектора признаков на веса, и ничего больше.
    Сами признаки считаются в features.вектор — там же, где их читает обучение,
    чтобы игра и подгонка весов не разъехались.
    """
    w = _веса_кортежем(веса if веса is not None else ВЕСА)
    в = вектор(pos, me)
    итог = 0.0
    for k in range(ЧИСЛО_ПРИЗНАКОВ):
        итог += в[k] * w[k]
    return итог


# Перевод весов из словаря в кортеж стоит дороже самой оценки, а словарь за
# весь перебор один и тот же. Кэш на одну запись: пара кладётся и читается
# одним присваиванием, поэтому даже из двух потоков хуже, чем лишний пересчёт,
# не будет.
_КЭШ_ВЕСОВ = (None, None)


def _веса_кортежем(веса):
    global _КЭШ_ВЕСОВ
    словарь, кортеж = _КЭШ_ВЕСОВ
    if словарь is веса:
        return кортеж
    новый = кортеж_весов(веса)
    _КЭШ_ВЕСОВ = (веса, новый)
    return новый


# ────────────────────────── перебор ──────────────────────────

class _Timeout(Exception):
    """Бюджет времени кончился — недосчитанный уровень выбрасывается целиком."""


def _search(pos, depth, alpha, beta, deadline, counter, веса=None):
    """Оценка позиции глазами того, чья сейчас очередь."""
    if pos.winner != EMPTY:
        if pos.winner == DRAW:
            return 0
        # Чем ближе выигрыш, тем он дороже: иначе бот, видя выигрыш в один ход
        # и в три, выбирает между ними случайно и тянет партию.
        return (WIN_SCORE + depth) if pos.winner == pos.turn else -(WIN_SCORE + depth)

    if depth <= 0:
        return evaluate(pos, pos.turn, веса)

    counter[0] += 1
    if counter[0] % 256 == 0 and time.monotonic() > deadline:
        raise _Timeout

    best = -WIN_SCORE * 2
    for big, small in pos.moves():
        won_before = pos.boards[big]
        rec = pos.play(big, small)
        score = -_search(pos, depth - 1, -beta, -alpha, deadline, counter, веса)
        pos.undo(rec, won_before)

        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def choose_move(state, variant=VARIANT_CLASSIC, level=DEFAULT_LEVEL, rng=None,
                веса=None):
    """
    Выбрать ход за того, чья сейчас очередь.

    Возвращает (big, small) либо None, если ходить некуда. Никогда не думает
    дольше отведённого уровню бюджета: перебор углубляется по одному уровню и
    отдаёт лучший ход последней ЗАКОНЧЕННОЙ глубины — недосчитанная выбрасывается,
    потому что её оценки сравнивать не с чем.
    """
    conf = LEVELS.get(level, LEVELS[DEFAULT_LEVEL])
    rng = rng or random
    pos = Position(state, variant)
    moves = pos.moves()
    if not moves:
        return None
    if len(moves) == 1:
        return moves[0]

    deadline = time.monotonic() + conf['budget']
    counter = [0]
    best_order = list(moves)
    chosen = moves[0]
    scored = []

    for depth in range(1, conf['depth'] + 1):
        try:
            round_scores = []
            alpha = -WIN_SCORE * 2
            for big, small in best_order:
                won_before = pos.boards[big]
                rec = pos.play(big, small)
                score = -_search(pos, depth - 1, -WIN_SCORE * 2, -alpha,
                                 deadline, counter, веса)
                pos.undo(rec, won_before)
                round_scores.append(((big, small), score))
                if score > alpha:
                    alpha = score
        except _Timeout:
            break

        round_scores.sort(key=lambda p: -p[1])
        scored = round_scores
        best_order = [m for m, _ in round_scores]
        chosen = round_scores[0][0]

        if round_scores[0][1] >= WIN_SCORE:
            break                      # выигрыш найден, глубже искать нечего

    if not scored:
        return chosen

    # Слабый уровень нарочно ошибается: одноходовый бот и так обыгрывает
    # новичка, а играть с непобедимым соперником незачем.
    if conf['blunder'] and len(scored) > 1 and rng.random() < conf['blunder']:
        return scored[1 + rng.randrange(len(scored) - 1)][0]

    top = [m for m, s in scored if s == scored[0][1]]
    return rng.choice(top)
