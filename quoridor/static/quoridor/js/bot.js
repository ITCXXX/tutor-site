/**
 * quoridor/bot.js — соперник для игры в одиночку. Три уровня.
 *
 * Уровни отличаются глубиной перебора: слабый смотрит на один полуход,
 * средний — на два, сильный — на четыре. Всё остальное у них общее.
 *
 * Оценка позиции простая и в «Заборах» на удивление точная: разность длин
 * кратчайших путей до своих краёв плюс небольшая надбавка за оставшиеся
 * заборы. Никаких весов за центр и прочей эзотерики — в этой игре побеждает
 * тот, кому осталось меньше шагов, а заборы это ресурс, чтобы шагов у
 * соперника стало больше.
 *
 * Полный перебор невозможен: на каждом ходу доступны 128 мест под забор плюс
 * ходы фишкой, и уже на третьем полуходе это два миллиона позиций. Поэтому
 * заборы рассматриваются не все, а только те, что перекрывают сопернику его
 * нынешний кратчайший путь, — остальные всё равно не меняют счёт. Такой отбор
 * оставляет полтора десятка вариантов вместо ста двадцати восьми.
 */

import { W, RED, BLUE, other, pawnMoves, shortestPath, pathTo, wallProblem,
         applyMove, applyWall } from './rules.js';

const key = (r, c) => `${r},${c}`;
const WIN = 10000;

export const LEVELS = {
  easy: {
    title: 'слабый',
    depth: 1,          // видит только свой ход
    candidates: 6,
    budget: 100,       // мс на весь ход — потолок, а не цель
    blunder: 0.25,     // как часто ошибается нарочно
    wallNeed: 1,
  },
  medium: {
    title: 'средний',
    depth: 2,          // свой ход и ответ соперника
    candidates: 10,
    budget: 300,
    blunder: 0.05,
    wallNeed: 1,
  },
  hard: {
    title: 'сильный',
    depth: 4,          // по два хода с каждой стороны
    candidates: 14,
    budget: 900,       // на слабом телефоне это и станет ограничителем
    blunder: 0,
    wallNeed: 1,
  },
};

export const DEFAULT_LEVEL = 'medium';

export function levelOf(name) {
  return LEVELS[name] || LEVELS[DEFAULT_LEVEL];
}

/* ────────────────────────── оценка ────────────────────────── */

function distances(state, side) {
  const foe = other(side);
  return {
    mine: shortestPath(state.walls, state.pawns[side], state.goalRow[side]),
    theirs: shortestPath(state.walls, state.pawns[foe], state.goalRow[foe]),
  };
}

/**
 * Оценка позиции глазами стороны `side`. Больше — лучше для неё.
 *
 * Шаг стоит десяти очков, забор — двух: забор ценен не сам по себе, а тем,
 * сколько шагов он отнимет, но и разбрасываться ими не стоит.
 */
function evaluate(state, side) {
  if (state.winner) return state.winner === side ? WIN : -WIN;
  const { mine, theirs } = distances(state, side);
  if (mine == null || theirs == null) return 0;      // такого быть не должно
  const foe = other(side);
  return (theirs - mine) * 10
       + (state.wallsLeft[side] - state.wallsLeft[foe]) * 2;
}

/* ────────────────────────── ходы-кандидаты ────────────────────────── */

/**
 * Заборы, которые перекрывают сопернику его нынешний кратчайший путь.
 *
 * Для каждого шага пути берутся два якоря, способные этот шаг закрыть. Всё,
 * что дальше от дороги, соперник обойдёт не заметив, — считать такие варианты
 * значит тратить перебор впустую.
 */
function wallCandidates(state, side, limit) {
  if (state.wallsLeft[side] <= 0) return [];
  const foe = other(side);
  const path = pathTo(state.walls, state.pawns[foe], state.goalRow[foe]);
  if (!path || path.length < 2) return [];

  const clamp = (x) => Math.max(0, Math.min(W - 1, x));
  const seen = new Set();
  const out = [];
  const base = distances(state, side);

  for (let i = 0; i + 1 < path.length; i += 1) {
    const a = path[i];
    const b = path[i + 1];
    const spots = [];

    if (b.r !== a.r) {                       // шаг по вертикали режет забор «—»
      const wr = Math.min(a.r, b.r);
      spots.push([wr, clamp(a.c - 1), 'h'], [wr, clamp(a.c), 'h']);
    } else {                                 // шаг вбок режет забор «|»
      const wc = Math.min(a.c, b.c);
      spots.push([clamp(a.r - 1), wc, 'v'], [clamp(a.r), wc, 'v']);
    }

    for (const [wr, wc, kind] of spots) {
      const id = `${wr},${wc},${kind}`;
      if (seen.has(id)) continue;
      seen.add(id);
      if (wallProblem(state, side, wr, wc, kind)) continue;

      const probe = { ...state.walls, [key(wr, wc)]: kind };
      const theirs = shortestPath(probe, state.pawns[foe], state.goalRow[foe]);
      const mine = shortestPath(probe, state.pawns[side], state.goalRow[side]);
      if (theirs == null || mine == null) continue;
      out.push({
        kind: 'wall', wr, wc, orient: kind,
        gain: (theirs - base.theirs) - (mine - base.mine),
      });
    }
  }

  out.sort((x, y) => y.gain - x.gain);
  return out.slice(0, limit);
}

function pawnCandidates(state, side) {
  const goal = state.goalRow[side];
  return pawnMoves(state, side)
    .map((m) => ({
      kind: 'move', r: m.r, c: m.c,
      len: shortestPath(state.walls, m, goal),
    }))
    .filter((m) => m.len != null)
    .sort((a, b) => a.len - b.len);
}

/** Ходы к перебору: сначала шаги покороче, потом заборы повреднее. */
function candidates(state, side, limit) {
  return [...pawnCandidates(state, side), ...wallCandidates(state, side, limit)];
}

function apply(state, side, mv) {
  const res = mv.kind === 'move'
    ? applyMove(state, side, mv.r, mv.c)
    : applyWall(state, side, mv.wr, mv.wc, mv.orient);
  return res.error ? null : res.state;
}

/* ────────────────────────── перебор ────────────────────────── */

/**
 * Негамакс с отсечениями. Возвращает оценку позиции для стороны, которая ходит.
 *
 * `budget` — срок, а не счётчик позиций. Считать позиции бесполезно: время
 * съедает не сам перебор, а обходы поля при отборе заборов, и на замерах
 * счётчик не срабатывал ни разу, сколько его ни занижай. Часы честнее: они
 * меряют то самое, ради чего потолок и нужен, — чтобы на слабом телефоне
 * вкладка не замирала на несколько секунд.
 */
function search(state, side, depth, alpha, beta, level, budget) {
  if (state.winner) {
    // depth — это ОСТАТОК глубины: у победы, найденной ближе к корню, он
    // больше. Поэтому близкая победа обязана стоить дороже далёкой, а близкое
    // поражение — дешевле отложенного. С обратным знаком бот, стоя в шаге от
    // выигрыша, предпочитал выигрыш «через два хода» и топтался на месте.
    return state.winner === side ? WIN + depth : -(WIN + depth);
  }
  if (depth <= 0 || budget.out()) return evaluate(state, side);

  let best = -Infinity;
  for (const mv of candidates(state, side, level.candidates)) {
    if (budget.out()) break;
    const next = apply(state, side, mv);
    if (!next) continue;

    const score = -search(next, other(side), depth - 1, -beta, -alpha, level, budget);
    if (score > best) best = score;
    if (best > alpha) alpha = best;
    if (alpha >= beta) break;               // соперник сюда не пойдёт
  }
  return best === -Infinity ? evaluate(state, side) : best;
}

/* ────────────────────────── ход бота ────────────────────────── */

/**
 * Ход бота. Возвращает {state, kind, ...} — по kind клиент пишет строку в журнал.
 *
 * @param {string} levelName 'easy' | 'medium' | 'hard'
 */
export function botMove(state, side, levelName = DEFAULT_LEVEL) {
  const level = levelOf(levelName);
  const list = candidates(state, side, level.candidates);
  if (!list.length) return { state, kind: 'stuck' };

  const worth = list.filter((mv) => mv.kind !== 'wall' || mv.gain >= level.wallNeed);
  const pool = worth.length ? worth : list;

  // Срок общий на весь ход, но истечь он может только в самых тяжёлых
  // позициях; на обычных перебор заканчивается сам задолго до него.
  const until = Date.now() + level.budget;
  const budget = { out: () => Date.now() > until };

  const scored = [];
  for (const mv of pool) {
    const next = apply(state, side, mv);
    if (!next) continue;
    const score = -search(next, other(side), level.depth - 1,
                          -Infinity, Infinity, level, budget);
    scored.push({ mv, score });
    // Срок вышел — дальше сравнивать было бы нечестно: у оставшихся вариантов
    // перебор оборвался бы на первом же узле, и они выглядели бы хуже не по делу.
    if (budget.out()) break;
  }

  if (!scored.length) {
    const step = list.find((m) => m.kind === 'move');
    if (!step) return { state, kind: 'stuck' };
    return finish(state, side, step);
  }

  scored.sort((a, b) => b.score - a.score);

  // Слабый уровень нарочно ошибается: иначе даже одноходовый бот обыгрывает
  // новичка вчистую, и играть с ним не хочется.
  let choice = scored[0];
  if (level.blunder && scored.length > 1 && Math.random() < level.blunder) {
    choice = scored[1 + Math.floor(Math.random() * (scored.length - 1))];
  } else {
    // при равенстве выбираем случайно — чтобы партии не повторялись
    const top = scored.filter((s) => s.score === scored[0].score);
    choice = top[Math.floor(Math.random() * top.length)];
  }

  return finish(state, side, choice.mv);
}

function finish(state, side, mv) {
  const next = apply(state, side, mv);
  if (!next) return { state, kind: 'stuck' };
  return mv.kind === 'move'
    ? { state: next, kind: 'move', to: { r: mv.r, c: mv.c } }
    : { state: next, kind: 'wall', wall: { wr: mv.wr, wc: mv.wc, kind: mv.orient } };
}
