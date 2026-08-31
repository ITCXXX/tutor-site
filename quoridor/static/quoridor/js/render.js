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

/** Насколько далеко от центра клетки палец ещё считается ходом фишки. */
export const MOVE_RADIUS = 26;

/**
 * Куда попал палец.
 *
 * Расширять паз допуском нельзя: паз и так занимает 12 px из 64, и стоит дать
 * ему запас с обеих сторон, как от клетки остаётся четверть — пойти фишкой
 * становится труднее, чем поставить забор, хотя ходят чаще.
 *
 * Поэтому решают не полосы, а расстояния, и первыми спрашивают ходы фишкой:
 * их всегда единицы, они подсвечены зелёными точками, и попадание по такой
 * точке однозначно. Всё остальное на доске — намерение поставить забор, и
 * забор липнет к ближайшему пазу. Промах здесь ничего не стоит: забор сперва
 * примеряется и ждёт подтверждения.
 */
export function touchHit(mx, my, moves, lastOrient = 'h') {
  const span = N * CELL + (N - 1) * GAP;
  if (mx < PAD - MOVE_RADIUS || my < PAD - MOVE_RADIUS
      || mx > PAD + span + MOVE_RADIUS || my > PAD + span + MOVE_RADIUS) return null;

  let near = null;
  let nearDist = MOVE_RADIUS;
  for (const m of moves || []) {
    const dx = mx - (cellX(m.c) + CELL / 2);
    const dy = my - (cellY(m.r) + CELL / 2);
    const d = Math.hypot(dx, dy);
    if (d <= nearDist) { nearDist = d; near = m; }
  }
  if (near) return { type: 'cell', r: near.r, c: near.c };

  // Середины пазов: между колонками i и i+1 линия идёт по x = ...
  const line = (i) => PAD + i * STEP + CELL + GAP / 2;
  const clamp = (x) => Math.max(0, Math.min(W - 1, x));
  const band = (v) => clamp(Math.floor((v - PAD) / STEP));

  let bestV = 0;
  let bestH = 0;
  for (let i = 1; i < W; i += 1) {
    if (Math.abs(mx - line(i)) < Math.abs(mx - line(bestV))) bestV = i;
    if (Math.abs(my - line(i)) < Math.abs(my - line(bestH))) bestH = i;
  }
  const dv = Math.abs(mx - line(bestV));
  const dh = Math.abs(my - line(bestH));

  // Почти на пересечении — берём ту ориентацию, которой играли в прошлый раз:
  // переключать её лишний раз пальцем неудобно.
  const kind = Math.abs(dv - dh) < 6 ? lastOrient : (dh < dv ? 'h' : 'v');
  return kind === 'h'
    ? { type: 'wall', wr: bestH, wc: band(mx), kind }
    : { type: 'wall', wr: band(my), wc: bestV, kind };
}

/** Точка события в координатах доски: канва на экране может быть меньше. */
export function boardPoint(canvas, clientX, clientY) {
  const rect = canvas.getBoundingClientRect();
  // Схлопнутая (ещё не разложенная или скрытая) страница даёт ширину в пару
  // пикселей, и множитель улетает в сотни — тогда честнее считать один к одному.
  const k = rect.width > 120 ? SIZE / rect.width : 1;
  return { x: (clientX - rect.left) * k, y: (clientY - rect.top) * k };
}

/**
 * Подогнать канву под место на экране и вернуть масштаб отрисовки.
 *
 * Рисуем всегда в своих координатах — 624 px по стороне, — а на экран кладём
 * столько, сколько влезло: на телефоне шириной 360 px доска в натуральную
 * величину просто уезжает за край, и половину поля не видно. Масштаб уходит
 * в drawBoard, а обратный пересчёт координат касания делает boardPoint.
 */
export function setupCanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  // Ширину на экране задаёт CSS (width: 100%, max-width: 624px, квадрат), а не
  // этот код. Так надо: если размер холста выставлять отсюда, сетка страницы
  // подстраивается под холст, холст — под сетку, и ширина схлопывается в
  // случайное число. JS остаётся только подогнать разрешение картинки.
  // Пока страница не разложена (или вкладка свёрнута), ширина приходит нулевой
  // или крохотной — тогда честнее нарисовать в полный размер и пересчитать
  // позже по resize, чем показать доску в два пикселя.
  const measured = canvas.clientWidth;
  const css = measured > 120 ? measured : SIZE;
  const scale = (css / SIZE) * dpr;

  canvas.width = Math.round(SIZE * scale);
  canvas.height = Math.round(SIZE * scale);
  return scale;
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
 * @param {object}  o.pending   забор, ожидающий подтверждения (палец)
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

  const ghost = o.pending || (o.canPlay && o.hover && o.hover.type === 'wall' ? o.hover : null);
  if (ghost && !s.winner) {
    const { wr, wc, kind } = ghost;
    const bad = wallProblem(s, s.turn, wr, wc, kind);
    const { x, y, w, h } = wallRect(wr, wc, kind);
    ctx.fillStyle = bad ? COLOR.ghostBad : COLOR.ghostOk;
    roundRect(ctx, x, y, w, h, 4);
    ctx.fill();
    // Забор, который ждёт подтверждения пальцем, обводим: призрак под пальцем
    // не виден, и без контура непонятно, что именно сейчас поставится.
    if (o.pending) {
      ctx.strokeStyle = bad ? COLOR.red : COLOR.wallEdge;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  drawPawn(ctx, s.pawns[RED], COLOR.red, o.mySide === RED);
  drawPawn(ctx, s.pawns[BLUE], COLOR.blue, o.mySide === BLUE);
}
