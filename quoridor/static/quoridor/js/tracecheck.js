/**
 * quoridor/tracecheck.js — сверка браузерных правил с серверными.
 *
 * Правил в проекте два: `rules.js` играет локальную партию в браузере,
 * `quoridor/engine.py` судит сетевую на сервере. Разойдись они — игрок увидел бы
 * подсказку хода, который сервер потом отвергает, и понять причину было бы нечем.
 *
 * Сверка идёт по следу, который пишет `manage.py quoridor_trace`: сервер играет
 * случайные партии и сохраняет ходы, отпечатки позиций и замеры (допустимые ходы
 * фишкой, число законных заборов, длины кратчайших путей). Здесь тот же след
 * проигрывается заново — уже браузерными правилами.
 *
 * Запуск из консоли на любой странице «Заборов»:
 *
 *   const m = await import('/static/quoridor/js/tracecheck.js');
 *   await m.checkTrace();          // {ok: true, games: 6, plies: 287}
 *
 * Тот же след проверяет и `quoridor/tests/test_engine.py`.
 */

import {
  RED, BLUE, W, initialState, pawnMoves, shortestPath, wallProblem,
  applyMove, applyWall,
} from './rules.js';

const TRACE_URL = '/static/quoridor/data/rules_trace.json';

/** Каноническая строка позиции — должна совпадать с engine.state_signature. */
export function stateSignature(s) {
  const walls = Object.keys(s.walls).sort()
    .map((k) => `${k}=${s.walls[k]}`).join(';');
  const p = s.pawns;
  return [
    `r${p[RED].r},${p[RED].c}`,
    `b${p[BLUE].r},${p[BLUE].c}`,
    `l${s.wallsLeft[RED]},${s.wallsLeft[BLUE]}`,
    `t${s.turn}`,
    `w${s.winner || '-'}`,
    `n${s.moveNo}`,
    walls,
  ].join('|');
}

/** FNV-1a, 32 бита — тот же алгоритм, что в engine.state_digest. */
export function stateDigest(s) {
  const text = stateSignature(s);
  let h = 0x811C9DC5;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h;
}

function legalPawnSignature(state, side) {
  return pawnMoves(state, side)
    .map((m) => `${m.r},${m.c}`).sort().join(' ');
}

function legalWallCount(state, side) {
  if (state.wallsLeft[side] <= 0) return 0;
  let n = 0;
  for (let wr = 0; wr < W; wr += 1) {
    for (let wc = 0; wc < W; wc += 1) {
      for (const kind of ['h', 'v']) {
        if (!wallProblem(state, side, wr, wc, kind)) n += 1;
      }
    }
  }
  return n;
}

/**
 * Проиграть след и вернуть отчёт.
 * @returns {{ok: boolean, games: number, plies: number, problems: string[]}}
 */
export async function checkTrace(url = TRACE_URL) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`след не найден: ${url} → ${res.status}`);
  const trace = await res.json();

  const problems = [];
  let plies = 0;

  trace.games.forEach((game, gi) => {
    let st = initialState();

    game.moves.forEach((raw, i) => {
      if (problems.length > 8) return;              // дальше смысла нет
      const where = `партия ${gi + 1}, полуход ${i + 1} (${raw})`;
      const side = st.turn;

      const pawnSig = legalPawnSignature(st, side);
      if (pawnSig !== game.pawnMoves[i]) {
        problems.push(`ходы фишкой: ${where} — здесь «${pawnSig}», на сервере «${game.pawnMoves[i]}»`);
      }
      const walls = legalWallCount(st, side);
      if (walls !== game.wallCounts[i]) {
        problems.push(`счёт заборов: ${where} — здесь ${walls}, на сервере ${game.wallCounts[i]}`);
      }
      const paths = [
        shortestPath(st.walls, st.pawns[RED], st.goalRow[RED]),
        shortestPath(st.walls, st.pawns[BLUE], st.goalRow[BLUE]),
      ];
      if (JSON.stringify(paths) !== JSON.stringify(game.paths[i])) {
        problems.push(`кратчайшие пути: ${where} — здесь ${JSON.stringify(paths)}, на сервере ${JSON.stringify(game.paths[i])}`);
      }

      const parts = raw.split(',');
      const out = parts[0] === 'm'
        ? applyMove(st, side, Number(parts[1]), Number(parts[2]))
        : applyWall(st, side, Number(parts[1]), Number(parts[2]), parts[3]);
      if (out.error) {
        problems.push(`ход отклонён: ${where} — ${out.error}`);
        return;
      }
      st = out.state;
      plies += 1;

      const d = stateDigest(st);
      if (d !== game.digests[i]) {
        problems.push(`отпечаток позиции: ${where} — здесь ${d}, на сервере ${game.digests[i]}`);
      }
    });

    if (st.winner !== game.winner) {
      problems.push(`итог партии ${gi + 1}: здесь ${st.winner}, на сервере ${game.winner}`);
    }
  });

  return { ok: problems.length === 0, games: trace.games.length, plies, problems };
}
