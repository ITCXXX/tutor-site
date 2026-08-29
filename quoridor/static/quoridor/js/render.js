/**
 * quoridor/render.js — геометрия и отрисовка доски.
 *
 * Вынесено отдельно, потому что доску рисуют две страницы: локальная игра
 * и сетевая. Будь у каждой своя копия — они бы разъехались после первой же
 * правки внешнего вида.
 *
 * Модуль ничего не знает про ходы и очередь: ему дают готовое состояние
 * и говорят, что подсветить.
 */

import { N, W, RED, BLUE, pawnMoves, wallProblem } from './rules.js';

export const CELL = 52;
export const GAP = 12;                 // толщина забора и ширина паза
export const PAD = 30;                 // поле под подписи координат
export const STEP = CELL + GAP;
export const SIZE = N * CELL + (N - 1) * GAP + PAD * 2;

const FILES = 'abcdefghi';

const COLOR = {
  boardBg: '#f8fafc',
  cell: '#ffffff',
  cellAlt: '#f1f5f9',
  line: '#cbd5e1',
  label: '#94a3b8',
  red: '#dc2626',
  redSoft: '#fecaca',
  blue: '#2563eb',
  blueSoft: '#bfdbfe',
  wall: '#7c4a21',
  wallEdge: '#5b3517',
  wallFresh: '#b45309',
  ghostOk: 'rgba(124, 74, 33, .45)',
  ghostBad: 'rgba(220, 38, 38, .35)',
  hint: '#0d9488',
};

export const cellX = (c) => PAD + c * STEP;
export const cellY = (r) => PAD + r * STEP;

export function wallRect(wr, wc, kind) {
  return kind === 'h'
    ? { x: cellX(wc), y: cellY(wr) + CELL, w: 2 * CELL + GAP, h: GAP }
    : { x: cellX(wc) + CELL, y: cellY(wr), w: GAP, h: 2 * CELL + GAP };
}

/**
 * Что под курсором: клетка, паз для забора или ничего.
 * Ориентация берётся из паза; ровно на пересечении — из lastOrient,
 * чтобы не заставлять игрока переключать режим лишний раз.
 */
export function hitTest(mx, my, lastOrient = 'h') {
  const gx = mx - PAD;
  const gy = my - PAD;
  if (gx < 0 || gy < 0) return null;

  const ci = Math.floor(gx / STEP);
  const ri = Math.floor(gy / STEP);
  if (ci < 0 || ci >= N || ri < 0 || ri >= N) return null;

  const inVGroove = gx - ci * STEP > CELL;
  const inHGroove = gy - ri * STEP > CELL;
  if (!inVGroove && !inHGroove) return { type: 'cell', r: ri, c: ci };

  const clamp = (x) => Math.max(0, Math.min(W - 1, x));
  const kind = (inHGroove && inVGroove) ? lastOrient : (inHGroove ? 'h' : 'v');
  return { type: 'wall', wr: clamp(ri), wc: clamp(ci), kind };
}

/** Подгоняет размер канвы под экран и возвращает множитель плотности. */
export function setupCanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = SIZE * dpr;
  canvas.height = SIZE * dpr;
  canvas.style.width = SIZE + 'px';
  canvas.style.height = SIZE + 'px';
  return dpr;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawPawn(ctx, p, color, ring) {
  const x = cellX(p.c) + CELL / 2;
  const y = cellY(p.r) + CELL / 2;
  ctx.beginPath();
  ctx.arc(x, y + 2, 17, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(15,23,42,.18)';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x, y, 17, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  if (ring) {
    ctx.beginPath();
    ctx.arc(x, y, 22, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.beginPath();
  ctx.arc(x - 5, y - 6, 5, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,255,255,.35)';
  ctx.fill();
}

/**
 * Отрисовать доску.
 *
 * @param {object} o.state      состояние партии
 * @param {object} o.hover      что под курсором (или null)
 * @param {boolean} o.canPlay   показывать ли подсказки ходов и призрак забора
 * @param {string}  o.mySide    чью фишку обвести пунктиром (сетевая партия)
 * @param {object}  o.lastMove  последний ход соперника — подсветить забор
 */
export function drawBoard(ctx, dpr, o) {
  const s = o.state;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, SIZE, SIZE);
  ctx.fillStyle = COLOR.boardBg;
  ctx.fillRect(0, 0, SIZE, SIZE);

  ctx.fillStyle = COLOR.label;
  ctx.font = '600 12px "Golos Text", system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (let c = 0; c < N; c += 1) {
    ctx.fillText(FILES[c], cellX(c) + CELL / 2, PAD / 2);
    ctx.fillText(FILES[c], cellX(c) + CELL / 2, SIZE - PAD / 2);
  }
  for (let r = 0; r < N; r += 1) {
    ctx.fillText(String(N - r), PAD / 2, cellY(r) + CELL / 2);
    ctx.fillText(String(N - r), SIZE - PAD / 2, cellY(r) + CELL / 2);
  }

  for (let r = 0; r < N; r += 1) {
    for (let c = 0; c < N; c += 1) {
      ctx.fillStyle = (r + c) % 2 ? COLOR.cellAlt : COLOR.cell;
      roundRect(ctx, cellX(c), cellY(r), CELL, CELL, 6);
      ctx.fill();
      ctx.strokeStyle = COLOR.line;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  // целевые горизонтали
  ctx.globalAlpha = 0.5;
  for (let c = 0; c < N; c += 1) {
    ctx.fillStyle = COLOR.redSoft;
    roundRect(ctx, cellX(c), cellY(0), CELL, CELL, 6); ctx.fill();
    ctx.fillStyle = COLOR.blueSoft;
    roundRect(ctx, cellX(c), cellY(N - 1), CELL, CELL, 6); ctx.fill();
  }
  ctx.globalAlpha = 1;

  if (o.canPlay && !s.winner) {
    ctx.fillStyle = COLOR.hint;
    for (const m of pawnMoves(s, s.turn)) {
      ctx.globalAlpha = o.hover && o.hover.type === 'cell'
        && o.hover.r === m.r && o.hover.c === m.c ? 0.85 : 0.35;
      ctx.beginPath();
      ctx.arc(cellX(m.c) + CELL / 2, cellY(m.r) + CELL / 2, 9, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  const fresh = o.lastMove && o.lastMove.kind === 'wall'
    ? `${o.lastMove.wr},${o.lastMove.wc}` : null;
  for (const [k, kind] of Object.entries(s.walls)) {
    const [wr, wc] = k.split(',').map(Number);
    const { x, y, w, h } = wallRect(wr, wc, kind);
    ctx.fillStyle = k === fresh ? COLOR.wallFresh : COLOR.wall;
    roundRect(ctx, x, y, w, h, 4); ctx.fill();
    ctx.strokeStyle = COLOR.wallEdge;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  if (o.canPlay && !s.winner && o.hover && o.hover.type === 'wall') {
    const { wr, wc, kind } = o.hover;
    const bad = wallProblem(s, s.turn, wr, wc, kind);
    const { x, y, w, h } = wallRect(wr, wc, kind);
    ctx.fillStyle = bad ? COLOR.ghostBad : COLOR.ghostOk;
    roundRect(ctx, x, y, w, h, 4); ctx.fill();
  }

  drawPawn(ctx, s.pawns[RED], COLOR.red, o.mySide === RED);
  drawPawn(ctx, s.pawns[BLUE], COLOR.blue, o.mySide === BLUE);
}
