# -*- coding: utf-8 -*-
"""Smoke-тесты engine. Запускается как: python -m games._test_engine."""

from games.engine import (
    initial_state, apply_move, check_big_winner, score,
    VARIANT_CLASSIC, VARIANT_LONG,
)

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [OK] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name}")


# ── 1. Classic: старый поведение сохранено ────────────────────────────────
s = initial_state()
s, _ = apply_move(s, 'X', 4, 0)
s, _ = apply_move(s, 'O', 0, 4)
check("classic: current=X после двух ходов", s['current'] == 'X')
check("classic: next_local=4", s['next_local'] == 4)

# Default variant работает
s = initial_state()
s, _ = apply_move(s, 'X', 4, 0)
check("classic: default variant", s['next_local'] == 0)

# ── 2. Long: при выигрыше малого поля чистятся остальные открытые ─────────
s = initial_state()
s['board'][1] = ['X', 'O', '', '', '', '', '', '', '']
s['board'][3] = ['', '', '', 'O', 'X', '', '', '', '']
s['board'][0] = ['X', 'X', '', '', '', '', '', '', '']
s['next_local'] = 0
res, err = apply_move(s, 'X', 0, 2, variant=VARIANT_LONG)
check("long: ход легален", err is None)
check("long: big_board[0]=X", res['big_board'][0] == 'X')
check("long: поле 1 очищено", all(c == '' for c in res['board'][1]))
check("long: поле 3 очищено", all(c == '' for c in res['board'][3]))
check("long: выигранное поле 0 не очищено",
      res['board'][0] == ['X', 'X', 'X', '', '', '', '', '', ''])
check("long: next_local свободный", res['next_local'] is None)
check("long: current=O", res['current'] == 'O')

# ── 3. Long: ранее закрытое поле не трогается ─────────────────────────────
s = initial_state()
s['board'][2] = ['X', 'X', '', '', '', '', '', '', '']
s['big_board'][5] = 'X'
s['board'][5] = ['X', '', 'X', '', '', '', 'X', '', '']
s['next_local'] = 2
res, err = apply_move(s, 'X', 2, 2, variant=VARIANT_LONG)
check("long-closed: ход легален", err is None)
check("long-closed: поле 5 сохранено",
      res['board'][5] == ['X', '', 'X', '', '', '', 'X', '', ''])
check("long-closed: big_board[5] остался X", res['big_board'][5] == 'X')

# ── 4. Победа партии: 3 в ряд в big_board ─────────────────────────────────
s = initial_state()
s['big_board'] = ['X', 'X', '', '', '', '', '', '', '']
s['board'][2] = ['X', 'X', '', '', '', '', '', '', '']
s['next_local'] = 2
res, err = apply_move(s, 'X', 2, 2, variant=VARIANT_LONG)
check("long-bigwin: finished", res['status'] == 'finished')
check("long-bigwin: winner=X", res['winner'] == 'X')

# ── 5. Тиебрейк по счёту: X=4, O=1 ────────────────────────────────────────
s = initial_state()
s['big_board'] = ['X', 'D', 'X', 'D', 'X', 'D', 'O', 'X', '']
s['board'][8] = ['X', 'O', 'X', 'O', 'X', 'O', 'O', 'X', '']
s['next_local'] = 8
s['current'] = 'O'
res, err = apply_move(s, 'O', 8, 8, variant=VARIANT_CLASSIC)
sx, so = score(res['big_board'])
check("tiebreak: легален", err is None)
check("tiebreak: finished", res['status'] == 'finished')
print(f"  [info] tiebreak big_board={res['big_board']}, score X={sx}, O={so}, winner={res['winner']!r}")
# Проверим, что после хода в (8,8) поле 8 становится D (ничья малого).
# Расстановка ['X','O','X','O','X','O','O','X','O'] = (0,1,2)=X,O,X; (3,4,5)=O,X,O;
# (6,7,8)=O,X,O; (0,3,6)=X,O,O; (1,4,7)=O,X,X; (2,5,8)=X,O,O; (0,4,8)=X,X,O;
# (2,4,6)=X,X,O — ни одной 3 в ряд. Малое поле 8 ничья.
check("tiebreak: малое поле 8 D", res['big_board'][8] == 'D')
check("tiebreak: winner X по тиебрейку", res['winner'] == 'X')

# ── 6. Реальная ничья (равный счёт): сценарий конструируем точно ─────────
# big_board перед последним ходом: ['','X','O','O','X','X','X','O','O'] — не годится для
# демонстрации (X=4 O=4 после доп. ничьей малого). Сделаем теоретически:
test_bb = ['X', 'X', 'O', 'O', 'D', 'D', 'D', 'D', 'D']
# X=2, O=2, D=5. Нет линии X или O. → check_big_winner вернёт D, score (2,2) → ничья.
check("draw-tiebreak: check_big_winner=D", check_big_winner(test_bb) == 'D')
check("draw-tiebreak: score (2,2)", score(test_bb) == (2, 2))

# ── 7. Большая ничья + неравный счёт через явный test_bb ──────────────────
test_bb = ['D', 'X', 'D', 'D', 'X', 'D', 'D', 'O', 'X']
# X=3, O=1, D=5. Линии: (0,4,8)=D,X,X; (1,4,7)=X,X,O; (2,5,8)=D,D,X; (2,4,6)=D,X,D
# (0,1,2)=D,X,D; (3,4,5)=D,X,D; (6,7,8)=D,O,X; (0,3,6)=D,D,D — все D в столбце!
# Это даёт ничейный «ряд» из D — но check_big_winner проверяет только X и O.
# all(big_board) True → check_big_winner возвращает 'D' (большая ничья).
check("tiebreak-2: check_big_winner=D", check_big_winner(test_bb) == 'D')
check("tiebreak-2: score (3,1)", score(test_bb) == (3, 1))


print(f"\nИтого: {ok} OK, {fail} FAIL")
