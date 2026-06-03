# -*- coding: utf-8 -*-
"""
games/engine.py

Чистый Python-движок Ultimate Tic Tac Toe (UTTT).
Без зависимости от Django — можно тестировать отдельно.

Состояние партии хранится как словарь со следующими полями:

    {
        "board":        [9 малых полей × 9 клеток],   # каждая клетка: ''/'X'/'O'
        "big_board":    [9 значений],                 # ''/'X'/'O'/'D'  (D = ничья в малом поле)
        "next_local":   int|None,                     # 0..8 или None (свободный выбор)
        "current":      'X' или 'O',                  # чей сейчас ход
        "status":       'active'/'finished',          # завершена ли партия
        "winner":       ''/'X'/'O'/'D',               # итог: пусто пока идёт, или X/O/D
        "last_move":    {"big": .., "small": ..} | None,
    }

Индексы big и small — целые числа 0..8, где 0..2 — верхний ряд,
3..5 — средний, 6..8 — нижний.

Главные функции:
    initial_state()              — стартовое состояние партии
    apply_move(state, player, big, small) -> (new_state, error_or_None)
    check_small_winner(cells9)   — кто выиграл малое поле (или D/ничью, или None)
    check_big_winner(big_board)  — кто выиграл партию (или D, или None)
"""

# Все 8 выигрышных линий в формате (a, b, c) — индексы 0..8 для поля 3×3.
WINNING_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),    # строки
    (0, 3, 6), (1, 4, 7), (2, 5, 8),    # столбцы
    (0, 4, 8), (2, 4, 6),               # диагонали
)

# Поддерживаемые варианты правил.
VARIANT_CLASSIC = "classic"
VARIANT_LONG = "long"
ALL_VARIANTS = (VARIANT_CLASSIC, VARIANT_LONG)


def initial_state():
    """Стартовое состояние пустой партии. X ходит первым, в любое поле."""
    return {
        "board": [[""] * 9 for _ in range(9)],
        "big_board": [""] * 9,
        "next_local": None,         # X имеет свободный выбор на старте
        "current": "X",
        "status": "active",
        "winner": "",
        "last_move": None,
    }


def score(big_board):
    """Возвращает (score_x, score_o) — количество малых полей, выигранных X и O."""
    sx = sum(1 for v in big_board if v == "X")
    so = sum(1 for v in big_board if v == "O")
    return sx, so


def _opponent(player):
    return "O" if player == "X" else "X"


def check_small_winner(cells9):
    """Кто выиграл малое поле из 9 клеток.

    Возвращает 'X', 'O', 'D' (ничья — все клетки заняты, нет 3 в ряд), либо None
    (партия в малом поле продолжается).
    """
    for a, b, c in WINNING_LINES:
        v = cells9[a]
        if v and v == cells9[b] == cells9[c]:
            return v
    if all(cells9):
        return "D"
    return None


def check_big_winner(big_board):
    """Кто выиграл партию по большому полю.

    big_board[i] хранит 'X', 'O', 'D' или ''. Только 'X'/'O' учитываются как
    выигрыш ряда; 'D' и '' блокируют ряд (нельзя выиграть через ничью).
    Возвращает 'X', 'O', 'D' или None.
    """
    for a, b, c in WINNING_LINES:
        v = big_board[a]
        if v in ("X", "O") and v == big_board[b] == big_board[c]:
            return v
    # Большая ничья: все малые поля завершены (X/O/D), но никто не собрал ряд.
    if all(v for v in big_board):
        return "D"
    return None


def _board_resolved(big_board, idx):
    """Малое поле уже закрыто (выиграно или ничья)?"""
    return big_board[idx] in ("X", "O", "D")


def apply_move(state, player, big, small, variant=VARIANT_CLASSIC):
    """Применить ход и вернуть (new_state, error).

    Не мутирует входной state — возвращает новый словарь. При ошибке
    возвращает (state, "сообщение об ошибке").

    variant:
      - "classic": стандартный UTTT.
      - "long":   при выигрыше малого поля в нём как обычно закрепляется
                  победитель, а все остальные ещё-не-закрытые малые поля
                  очищаются. Партия идёт до 3 в ряд в большом поле.

    Тиебрейк при большой ничьей (применяется в обоих вариантах): если общее
    количество малых побед у X и O различается — побеждает тот, у кого больше.
    Если поровну — настоящая ничья (winner = "D").
    """
    # 0. Партия уже завершена?
    if state["status"] != "active":
        return state, "Партия уже завершена"

    # 1. Чей ход?
    if player != state["current"]:
        return state, f"Сейчас ходит {state['current']}, а не {player}"

    # 2. Корректные индексы?
    if not (isinstance(big, int) and 0 <= big <= 8):
        return state, "Неверный индекс большого поля"
    if not (isinstance(small, int) and 0 <= small <= 8):
        return state, "Неверный индекс клетки"

    if variant not in ALL_VARIANTS:
        return state, f"Неизвестный вариант правил: {variant}"

    big_board = list(state["big_board"])
    next_local = state["next_local"]

    # 3. Разрешено ли играть в этом большом поле?
    if next_local is not None and big != next_local:
        return state, f"Сейчас обязательный ход в поле {next_local + 1}"

    # 4. Малое поле уже выиграно/ничья?
    if _board_resolved(big_board, big):
        return state, "Это малое поле уже закрыто"

    # 5. Клетка пуста?
    board = [row[:] for row in state["board"]]
    if board[big][small]:
        return state, "Эта клетка уже занята"

    # ── Все проверки пройдены, ход легален ─────────────────────────────────
    board[big][small] = player

    # 6. Проверить выигрыш малого поля.
    small_winner = check_small_winner(board[big])
    if small_winner is not None:
        big_board[big] = small_winner

        # «Долгая дорога»: при выигрыше малого поля все остальные ещё-не-закрытые
        # малые поля очищаются. Закрытые (X/O/D в big_board) трогать нельзя.
        if variant == VARIANT_LONG:
            for i in range(9):
                if i == big:
                    continue
                if _board_resolved(big_board, i):
                    continue
                board[i] = [""] * 9

    # 7. Проверить выигрыш партии (по большому полю).
    big_outcome = check_big_winner(big_board)

    # 8. Определить итог и обязательное малое поле для следующего хода.
    if big_outcome is None:
        status = "active"
        winner = ""
        # Если в long после общего очищения — следующий ход свободный.
        if variant == VARIANT_LONG and small_winner is not None:
            new_next_local = None
        else:
            target = small
            new_next_local = (
                None if _board_resolved(big_board, target) else target
            )
    elif big_outcome in ("X", "O"):
        status = "finished"
        winner = big_outcome
        new_next_local = None
    else:
        # Большая ничья по доске: смотрим тиебрейк по числу малых побед.
        sx, so = score(big_board)
        status = "finished"
        if sx > so:
            winner = "X"
        elif so > sx:
            winner = "O"
        else:
            winner = "D"
        new_next_local = None

    return {
        "board": board,
        "big_board": big_board,
        "next_local": new_next_local,
        "current": _opponent(player) if status == "active" else state["current"],
        "status": status,
        "winner": winner,
        "last_move": {"big": big, "small": small, "by": player},
    }, None


def legal_moves(state):
    """Список (big, small) допустимых ходов в текущем состоянии. Для тестов."""
    if state["status"] != "active":
        return []
    moves = []
    bb = state["big_board"]
    targets = (
        [state["next_local"]] if state["next_local"] is not None
        else [i for i in range(9) if not _board_resolved(bb, i)]
    )
    for big in targets:
        if _board_resolved(bb, big):
            continue
        for small in range(9):
            if not state["board"][big][small]:
                moves.append((big, small))
    return moves


__all__ = [
    "initial_state",
    "apply_move",
    "check_small_winner",
    "check_big_winner",
    "legal_moves",
    "score",
    "WINNING_LINES",
    "VARIANT_CLASSIC", "VARIANT_LONG", "ALL_VARIANTS",
]
