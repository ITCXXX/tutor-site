# -*- coding: utf-8 -*-
"""
quoridor/engine.py — правила «Заборов» на Python. Без Django, чистые функции.

Зачем второй экземпляр правил, если они уже есть в JS
-----------------------------------------------------
Локальная игра и бот работают целиком в браузере: гонять каждый шаг на сервер
ради игры вдвоём за одним экраном незачем. Сетевая партия, наоборот, обязана
проверяться на сервере — иначе любой участник сможет прислать любой ход.
Поэтому правил два: `static/quoridor/js/rules.js` для локальной игры и этот
модуль для сетевой. Так же устроен и УТТТ: `games/engine.py` — авторитет.

Две реализации одних правил рано или поздно расходятся. Чтобы это не случилось
молча, есть перекрёстная проверка. `manage.py quoridor_trace` играет случайные
партии этим движком и пишет след — ходы, отпечатки позиций, наборы допустимых
ходов, число законных заборов, длины кратчайших путей — в файл
`static/quoridor/data/rules_trace.json`. Тот же след проигрывают обе стороны:
`quoridor/tests/test_engine.py` — здесь, `js/tracecheck.js` — в браузере поверх
`rules.js`. Любое расхождение хоть в одном поле валит проверку.

Система координат совпадает с JS: r = 0 сверху (9-я горизонталь), r = 8 снизу.
Красный стартует на e1 (r = 8) и бежит к r = 0, синий — на e9 к r = 8.
"""

from collections import deque

N = 9
W = N - 1                    # 8 — размер сетки якорей забора
WALLS_PER_PLAYER = 10

RED = 'red'
BLUE = 'blue'

DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))
PERP = {
    (-1, 0): ((0, -1), (0, 1)),
    (1, 0): ((0, -1), (0, 1)),
    (0, -1): ((-1, 0), (1, 0)),
    (0, 1): ((-1, 0), (1, 0)),
}
FILES = 'abcdefghi'


def _key(r, c):
    return f'{r},{c}'


def _in_board(r, c):
    return 0 <= r < N and 0 <= c < N


def other(side):
    return BLUE if side == RED else RED


# ─────────────────────────── состояние ───────────────────────────

def initial_state():
    return {
        'pawns': {RED: {'r': N - 1, 'c': 4}, BLUE: {'r': 0, 'c': 4}},
        'goalRow': {RED: 0, BLUE: N - 1},
        'wallsLeft': {RED: WALLS_PER_PLAYER, BLUE: WALLS_PER_PLAYER},
        'walls': {},
        'turn': RED,
        'winner': None,
        'moveNo': 1,
    }


def clone_state(s):
    return {
        'pawns': {RED: dict(s['pawns'][RED]), BLUE: dict(s['pawns'][BLUE])},
        'goalRow': dict(s['goalRow']),
        'wallsLeft': dict(s['wallsLeft']),
        'walls': dict(s['walls']),
        'turn': s['turn'],
        'winner': s['winner'],
        'moveNo': s['moveNo'],
    }


# ──────────────────────── проходимость ────────────────────────

def blocked(walls, r1, c1, r2, c2):
    """Мешает ли забор пройти между двумя соседними клетками."""
    if c1 == c2:
        top = min(r1, r2)
        return walls.get(_key(top, c1)) == 'h' or walls.get(_key(top, c1 - 1)) == 'h'
    left = min(c1, c2)
    return walls.get(_key(r1, left)) == 'v' or walls.get(_key(r1 - 1, left)) == 'v'


# ───────────────────────── ходы фишкой ─────────────────────────

def pawn_moves(state, side):
    """
    Куда может пойти фишка, с прыжками: через соперника прямо, а если за ним
    стена или край поля — по диагонали в обход. Порядок совпадает с JS:
    направления перебираются в том же порядке, дубликаты не добавляются.
    """
    me = state['pawns'][side]
    foe = state['pawns'][other(side)]
    walls = state['walls']
    out = []

    def add(r, c):
        if not any(p['r'] == r and p['c'] == c for p in out):
            out.append({'r': r, 'c': c})

    for dr, dc in DIRS:
        nr, nc = me['r'] + dr, me['c'] + dc
        if not _in_board(nr, nc):
            continue
        if blocked(walls, me['r'], me['c'], nr, nc):
            continue

        if nr != foe['r'] or nc != foe['c']:
            add(nr, nc)
            continue

        jr, jc = nr + dr, nc + dc
        if _in_board(jr, jc) and not blocked(walls, nr, nc, jr, jc):
            add(jr, jc)
            continue

        for pr, pc in PERP[(dr, dc)]:
            sr, sc = nr + pr, nc + pc
            if not _in_board(sr, sc):
                continue
            if blocked(walls, nr, nc, sr, sc):
                continue
            add(sr, sc)
    return out


# ─────────────────── путь до своей стороны ───────────────────

def shortest_path(walls, frm, goal_row):
    """Длина кратчайшего пути в шагах или None, если пути нет."""
    start = (frm['r'], frm['c'])
    seen = {start}
    frontier = [start]
    dist = 0
    while frontier:
        nxt = []
        for (r, c) in frontier:
            if r == goal_row:
                return dist
            for dr, dc in DIRS:
                nr, nc = r + dr, c + dc
                if not _in_board(nr, nc) or (nr, nc) in seen:
                    continue
                if blocked(walls, r, c, nr, nc):
                    continue
                seen.add((nr, nc))
                nxt.append((nr, nc))
        frontier = nxt
        dist += 1
    return None


def has_path(walls, frm, goal_row):
    return shortest_path(walls, frm, goal_row) is not None


# ───────────────────────── заборы ─────────────────────────

def wall_problem(state, side, wr, wc, kind):
    """None — забор поставить можно; иначе причина отказа для игрока."""
    if state['winner']:
        return 'Игра окончена.'
    if state['turn'] != side:
        return 'Сейчас не ваш ход.'
    if state['wallsLeft'][side] <= 0:
        return 'Заборы закончились.'
    if kind not in ('h', 'v'):
        return 'Неизвестный вид забора.'
    if wr < 0 or wr >= W or wc < 0 or wc >= W:
        return 'Забор не помещается: он занимает две клетки.'
    if state['walls'].get(_key(wr, wc)):
        return 'Здесь уже есть забор.'

    walls = state['walls']
    if kind == 'h':
        if walls.get(_key(wr, wc - 1)) == 'h' or walls.get(_key(wr, wc + 1)) == 'h':
            return 'Заборы нельзя класть внахлёст.'
    else:
        if walls.get(_key(wr - 1, wc)) == 'v' or walls.get(_key(wr + 1, wc)) == 'v':
            return 'Заборы нельзя класть внахлёст.'

    probe = dict(walls)
    probe[_key(wr, wc)] = kind
    for p in (RED, BLUE):
        if not has_path(probe, state['pawns'][p], state['goalRow'][p]):
            return 'Так нельзя: этот забор полностью отрезает путь.'
    return None


# ─────────────────── применение хода ───────────────────

def apply_move(state, side, r, c):
    """Ход фишкой. Возвращает (new_state, error). Исходное состояние не меняется."""
    if state['winner']:
        return state, 'Игра окончена.'
    if state['turn'] != side:
        return state, 'Сейчас не ваш ход.'
    if not any(p['r'] == r and p['c'] == c for p in pawn_moves(state, side)):
        return state, 'Туда фишка пойти не может.'

    nxt = clone_state(state)
    nxt['pawns'][side] = {'r': r, 'c': c}
    if r == state['goalRow'][side]:
        nxt['winner'] = side
    else:
        nxt['turn'] = other(side)
    nxt['moveNo'] += 1
    return nxt, None


def apply_wall(state, side, wr, wc, kind):
    """Постановка забора. Возвращает (new_state, error)."""
    problem = wall_problem(state, side, wr, wc, kind)
    if problem:
        return state, problem

    nxt = clone_state(state)
    nxt['walls'][_key(wr, wc)] = kind
    nxt['wallsLeft'][side] -= 1
    nxt['turn'] = other(side)
    nxt['moveNo'] += 1
    return nxt, None


# ─────────────────────────── запись ───────────────────────────

def cell_name(r, c):
    return f'{FILES[c]}{N - r}'


def wall_name(wr, wc, kind):
    return f"{FILES[wc]}{N - wr - 1}{'г' if kind == 'h' else 'в'}"


# ────────────────── отпечаток позиции для перекрёстной проверки ──────────────────

def state_signature(state):
    """
    Каноническая строка позиции: все поля партии в фиксированном порядке.

    Заборы сортируются по ключу, потому что в словаре они лежат в порядке
    добавления, а он у двух реализаций совпадать не обязан.
    """
    walls = ';'.join('%s=%s' % (k, state['walls'][k]) for k in sorted(state['walls']))
    p = state['pawns']
    return '|'.join([
        'r%d,%d' % (p[RED]['r'], p[RED]['c']),
        'b%d,%d' % (p[BLUE]['r'], p[BLUE]['c']),
        'l%d,%d' % (state['wallsLeft'][RED], state['wallsLeft'][BLUE]),
        't%s' % state['turn'],
        'w%s' % (state['winner'] or '-'),
        'n%d' % state['moveNo'],
        walls,
    ])


def state_digest(state):
    """
    32-битный отпечаток позиции — якорь сверки с браузерной реализацией.

    Считается по строке, где перечислены все поля, поэтому расхождение хоть
    в очереди хода, хоть в одном заборе меняет число. Алгоритм — FNV-1a:
    он повторяется в JS тремя строками и не тянет зависимостей.
    """
    h = 0x811C9DC5
    for ch in state_signature(state):
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def legal_pawn_signature(state, side):
    """Отсортированный список ходов фишкой строкой — сравнивать удобнее, чем счётчик."""
    return ' '.join(sorted('%d,%d' % (m['r'], m['c']) for m in pawn_moves(state, side)))


def legal_wall_count(state, side):
    """Сколько заборов сторона вправе поставить прямо сейчас."""
    if state['wallsLeft'][side] <= 0:
        return 0
    n = 0
    for wr in range(W):
        for wc in range(W):
            for kind in ('h', 'v'):
                if wall_problem(state, side, wr, wc, kind) is None:
                    n += 1
    return n
