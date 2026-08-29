/**
 * quoridor/bot.js — соперник для игры в одиночку.
 *
 * Никакого перебора вглубь: бот смотрит на один ход вперёд по двум числам —
 * своей длине пути до цели и чужой. Этого достаточно, чтобы он бежал по
 * кратчайшему маршруту и ставил заборы, когда отстаёт. Для тренировки хватает,
 * гроссмейстера здесь никто не обещал.
 */

import { W, RED, BLUE, other, pawnMoves, shortestPath, wallProblem,
         applyMove, applyWall } from './rules.js';

const key = (r, c) => `${r},${c}`;

/** Насколько бот отстаёт: своя длина пути минус чужая. */
function race(state, side) {
  const foe = other(side);
  return {
    mine: shortestPath(state.walls, state.pawns[side], state.goalRow[side]),
    theirs: shortestPath(state.walls, state.pawns[foe], state.goalRow[foe]),
  };
}

/** Лучший шаг фишкой: тот, после которого путь до цели короче всего. */
function bestStep(state, side) {
  let best = null;
  let bestLen = Infinity;
  for (const m of pawnMoves(state, side)) {
    const len = shortestPath(state.walls, m, state.goalRow[side]);
    if (len == null) continue;
    // при равенстве выбираем случайно, чтобы бот не был предсказуемым
    if (len < bestLen || (len === bestLen && Math.random() < 0.5)) {
      bestLen = len;
      best = m;
    }
  }
  return best;
}

/**
 * Лучший забор: сильнее всего удлиняет путь сопернику и меньше всего — себе.
 * Перебираются все 128 вариантов (8×8 якорей × две ориентации); каждый стоит
 * двух обходов поля в 81 клетку, так что это мгновенно.
 */
function bestWall(state, side) {
  const foe = other(side);
  const base = race(state, side);
  let best = null;
  let bestGain = 0;

  for (let wr = 0; wr < W; wr += 1) {
    for (let wc = 0; wc < W; wc += 1) {
      for (const kind of ['h', 'v']) {
        if (wallProblem(state, side, wr, wc, kind)) continue;
        const probe = { ...state.walls, [key(wr, wc)]: kind };
        const theirs = shortestPath(probe, state.pawns[foe], state.goalRow[foe]);
        const mine = shortestPath(probe, state.pawns[side], state.goalRow[side]);
        if (theirs == null || mine == null) continue;
        const gain = (theirs - base.theirs) - (mine - base.mine);
        if (gain > bestGain) {
          bestGain = gain;
          best = { wr, wc, kind, gain };
        }
      }
    }
  }
  return best;
}

/**
 * Ход бота. Возвращает {state, description} — описание попадает в журнал,
 * чтобы игроку было видно, что именно сделал соперник.
 */
export function botMove(state, side) {
  const { mine, theirs } = race(state, side);

  /*
   * Когда ставить забор.
   *
   * Шаг всегда сокращает мой путь на единицу, поэтому забор оправдан только
   * если он даёт больше. На открытом поле один забор длиной в две клетки
   * обходится без потерь — выигрыш 0, и бежать выгоднее. Заборы начинают
   * работать ближе к краю, где обход дорог.
   *
   * Но есть случай, когда бежать нельзя: если мой путь ДЛИННЕЕ чужого, чистая
   * гонка проиграна заранее, сколько ни беги. Тогда годится и выигрыш в один
   * шаг — он переворачивает исход. Без этой оговорки бот, ходящий вторым,
   * просто бежал бы к гарантированному поражению.
   */
  if (state.wallsLeft[side] > 0 && theirs != null && mine != null) {
    const behind = mine > theirs;
    const need = behind ? 1 : 2;
    const wall = bestWall(state, side);
    if (wall && wall.gain >= need) {
      const res = applyWall(state, side, wall.wr, wall.wc, wall.kind);
      if (!res.error) return { state: res.state, kind: 'wall', wall };
    }
  }

  const step = bestStep(state, side);
  if (step) {
    const res = applyMove(state, side, step.r, step.c);
    if (!res.error) return { state: res.state, kind: 'move', to: step };
  }

  // Бежать некуда — ставим любой допустимый забор, лишь бы не зависнуть.
  const wall = bestWall(state, side);
  if (wall) {
    const res = applyWall(state, side, wall.wr, wall.wc, wall.kind);
    if (!res.error) return { state: res.state, kind: 'wall', wall };
  }
  return { state, kind: 'stuck' };
}
