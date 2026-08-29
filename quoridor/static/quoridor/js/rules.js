/**
 * quoridor/rules.js — правила игры. Чистая логика, без DOM и без отрисовки.
 *
 * Поле 9×9. Клетки нумеруются (r, c): r = 0 сверху (это 9-я горизонталь),
 * r = 8 снизу (1-я горизонталь). Колонки слева направо a…i.
 *
 * Красный стоит на e1 (низ, r = 8) и бежит наверх, к r = 0.
 * Синий стоит на e9 (верх, r = 0) и бежит вниз, к r = 8.
 *
 * Заборы ставятся в пазы между клетками и всегда занимают ДВЕ клетки.
 * Забор с якорем (wr, wc), где wr и wc от 0 до 7:
 *   'h' — лежит в пазу между рядами wr и wr+1, накрывает колонки wc и wc+1;
 *   'v' — лежит в пазу между колонками wc и wc+1, накрывает ряды wr и wr+1.
 * Поэтому якорей ровно 8×8: забор длиной две клетки не помещается у края.
 */

export const N = 9;
export const W = N - 1;          // 8 — размер сетки якорей забора
export const WALLS_PER_PLAYER = 10;

export const RED = 'red';
export const BLUE = 'blue';

const DIRS = [[-1, 0], [1, 0], [0, -1], [0, 1]];
const PERP = { '-1,0': [[0, -1], [0, 1]], '1,0': [[0, -1], [0, 1]],
               '0,-1': [[-1, 0], [1, 0]], '0,1': [[-1, 0], [1, 0]] };

const key = (r, c) => `${r},${c}`;
const inBoard = (r, c) => r >= 0 && r < N && c >= 0 && c < N;

/* ────────────────────────── состояние ────────────────────────── */

export function initialState() {
  return {
    pawns: {
      [RED]:  { r: N - 1, c: 4 },   // e1
      [BLUE]: { r: 0,     c: 4 },   // e9
    },
    goalRow: { [RED]: 0, [BLUE]: N - 1 },
    wallsLeft: { [RED]: WALLS_PER_PLAYER, [BLUE]: WALLS_PER_PLAYER },
    walls: {},                      // "wr,wc" → 'h' | 'v'
    turn: RED,                      // красный ходит первым
    winner: null,
    moveNo: 1,
  };
}

export const other = (side) => (side === RED ? BLUE : RED);

/* ─────────────────────── проходимость ─────────────────────── */

/**
 * Мешает ли забор пройти между двумя СОСЕДНИМИ клетками.
 * Соседство не проверяется — вызывающий и так шагает на одну клетку.
 */
export function blocked(walls, r1, c1, r2, c2) {
  if (c1 === c2) {
    // движение по вертикали: паз между рядами
    const top = Math.min(r1, r2);
    return walls[key(top, c1)] === 'h' || walls[key(top, c1 - 1)] === 'h';
  }
  // движение по горизонтали: паз между колонками
  const left = Math.min(c1, c2);
  return walls[key(r1, left)] === 'v' || walls[key(r1 - 1, left)] === 'v';
}

/* ──────────────────────── ходы фишкой ──────────────────────── */

/**
 * Куда может пойти фишка. Реализованы прыжки:
 * если впереди стоит соперник — перепрыгиваем через него; если за ним стена
 * или край поля, обходим по диагонали. Это стандартное правило Quoridor.
 */
export function pawnMoves(state, side) {
  const me = state.pawns[side];
  const foe = state.pawns[other(side)];
  const out = [];
  const add = (r, c) => {
    if (!out.some((p) => p.r === r && p.c === c)) out.push({ r, c });
  };

  for (const [dr, dc] of DIRS) {
    const nr = me.r + dr;
    const nc = me.c + dc;
    if (!inBoard(nr, nc)) continue;
    if (blocked(state.walls, me.r, me.c, nr, nc)) continue;

    if (nr !== foe.r || nc !== foe.c) { add(nr, nc); continue; }

    // на пути соперник — пробуем прыгнуть прямо через него
    const jr = nr + dr;
    const jc = nc + dc;
    if (inBoard(jr, jc) && !blocked(state.walls, nr, nc, jr, jc)) {
      add(jr, jc);
      continue;
    }
    // прямо нельзя — уходим по диагонали в обход
    for (const [pr, pc] of PERP[`${dr},${dc}`]) {
      const sr = nr + pr;
      const sc = nc + pc;
      if (!inBoard(sr, sc)) continue;
      if (blocked(state.walls, nr, nc, sr, sc)) continue;
      add(sr, sc);
    }
  }
  return out;
}

/* ───────────────────── путь до своей стороны ───────────────────── */

/**
 * Длина кратчайшего пути до нужной горизонтали в шагах, или null если пути нет.
 * Соперник как препятствие НЕ учитывается: он подвижен, и правило «забор не
 * должен запирать игрока» смотрит именно на проходимость лабиринта.
 */
export function shortestPath(walls, from, goalRow) {
  const seen = new Uint8Array(N * N);
  let frontier = [from];
  seen[from.r * N + from.c] = 1;
  let dist = 0;

  while (frontier.length) {
    const next = [];
    for (const cell of frontier) {
      if (cell.r === goalRow) return dist;
      for (const [dr, dc] of DIRS) {
        const nr = cell.r + dr;
        const nc = cell.c + dc;
        if (!inBoard(nr, nc)) continue;
        if (seen[nr * N + nc]) continue;
        if (blocked(walls, cell.r, cell.c, nr, nc)) continue;
        seen[nr * N + nc] = 1;
        next.push({ r: nr, c: nc });
      }
    }
    frontier = next;
    dist += 1;
  }
  return null;
}

export const hasPath = (walls, from, goalRow) => shortestPath(walls, from, goalRow) !== null;

/* ───────────────────────── заборы ───────────────────────── */

/**
 * Можно ли поставить забор. Возвращает null если можно, иначе причину —
 * чтобы интерфейс мог объяснить игроку отказ, а не просто проигнорировать клик.
 */
export function wallProblem(state, side, wr, wc, kind) {
  if (state.winner) return 'Игра окончена.';
  if (state.turn !== side) return 'Сейчас не ваш ход.';
  if (state.wallsLeft[side] <= 0) return 'Заборы закончились.';
  if (wr < 0 || wr >= W || wc < 0 || wc >= W) return 'Забор не помещается: он занимает две клетки.';
  if (state.walls[key(wr, wc)]) return 'Здесь уже есть забор.';

  if (kind === 'h') {
    if (state.walls[key(wr, wc - 1)] === 'h' || state.walls[key(wr, wc + 1)] === 'h') {
      return 'Заборы нельзя класть внахлёст.';
    }
  } else {
    if (state.walls[key(wr - 1, wc)] === 'v' || state.walls[key(wr + 1, wc)] === 'v') {
      return 'Заборы нельзя класть внахлёст.';
    }
  }

  // главное правило: забор не имеет права запереть кого-то насмерть
  const probe = { ...state.walls, [key(wr, wc)]: kind };
  for (const p of [RED, BLUE]) {
    if (!hasPath(probe, state.pawns[p], state.goalRow[p])) {
      return 'Так нельзя: этот забор полностью отрезает путь.';
    }
  }
  return null;
}

/* ─────────────────────── применение хода ─────────────────────── */

/** Ход фишкой. Возвращает {state, error}. Исходное состояние не меняется. */
export function applyMove(state, side, r, c) {
  if (state.winner) return { state, error: 'Игра окончена.' };
  if (state.turn !== side) return { state, error: 'Сейчас не ваш ход.' };
  if (!pawnMoves(state, side).some((p) => p.r === r && p.c === c)) {
    return { state, error: 'Туда фишка пойти не может.' };
  }

  const next = cloneState(state);
  next.pawns[side] = { r, c };
  if (r === state.goalRow[side]) next.winner = side;
  else next.turn = other(side);
  next.moveNo += 1;
  return { state: next, error: null };
}

/** Постановка забора. Возвращает {state, error}. */
export function applyWall(state, side, wr, wc, kind) {
  const problem = wallProblem(state, side, wr, wc, kind);
  if (problem) return { state, error: problem };

  const next = cloneState(state);
  next.walls[key(wr, wc)] = kind;
  next.wallsLeft[side] -= 1;
  next.turn = other(side);
  next.moveNo += 1;
  return { state: next, error: null };
}

export function cloneState(s) {
  return {
    pawns: { [RED]: { ...s.pawns[RED] }, [BLUE]: { ...s.pawns[BLUE] } },
    goalRow: { ...s.goalRow },
    wallsLeft: { ...s.wallsLeft },
    walls: { ...s.walls },
    turn: s.turn,
    winner: s.winner,
    moveNo: s.moveNo,
  };
}

/* ─────────────────────────── запись ─────────────────────────── */

const FILES = 'abcdefghi';
/** Клетка в привычной шахматной записи: (r=8, c=4) → «e1». */
export const cellName = (r, c) => `${FILES[c]}${N - r}`;
/** Забор: якорь плюс ориентация, например «e5г» / «e5в». */
export const wallName = (wr, wc, kind) =>
  `${FILES[wc]}${N - wr - 1}${kind === 'h' ? 'г' : 'в'}`;
