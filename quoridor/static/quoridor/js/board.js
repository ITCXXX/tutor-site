/**
 * quoridor/board.js — доска и управление.
 *
 * Отрисовка на canvas: сетка клеток с пазами между ними, в пазы кладутся
 * заборы. Клик по клетке — ход фишкой, клик по пазу — забор. Ориентация
 * забора определяется тем, в каком пазу курсор: в горизонтальном или
 * вертикальном. На пересечении берётся последняя использованная — чтобы
 * не заставлять игрока лишний раз переключать режим.
 */

import { N, W, RED, BLUE, other, initialState, pawnMoves, applyMove, applyWall,
         wallProblem, shortestPath, cellName, wallName, WALLS_PER_PLAYER } from './rules.js';
import { botMove } from './bot.js';

const CELL = 52;
const GAP = 12;                       // толщина забора и ширина паза
const PAD = 30;                       // поле под подписи координат
const STEP = CELL + GAP;
const SIZE = N * CELL + (N - 1) * GAP + PAD * 2;

const COLOR = {
  boardBg: '#f8fafc',
  cell: '#ffffff',
  cellAlt: '#f1f5f9',
  groove: '#e2e8f0',
  line: '#cbd5e1',
  label: '#94a3b8',
  red: '#dc2626',
  redSoft: '#fecaca',
  blue: '#2563eb',
  blueSoft: '#bfdbfe',
  wall: '#7c4a21',
  wallEdge: '#5b3517',
  ghostOk: 'rgba(124, 74, 33, .45)',
  ghostBad: 'rgba(220, 38, 38, .35)',
  hint: '#0d9488',
};

const FILES = 'abcdefghi';

/* ────────────────────────── состояние экрана ────────────────────────── */

const ui = {
  state: initialState(),
  history: [],
  mode: 'hotseat',                    // 'hotseat' | 'bot'
  botSide: BLUE,
  lastOrient: 'h',
  hover: null,                        // {type:'cell'|'wall', ...}
  log: [],
  busy: false,
};

let canvas, ctx, dpr = 1;

/* ─────────────────────────── геометрия ─────────────────────────── */

const cellX = (c) => PAD + c * STEP;
const cellY = (r) => PAD + r * STEP;

function wallRect(wr, wc, kind) {
  return kind === 'h'
    ? { x: cellX(wc), y: cellY(wr) + CELL, w: 2 * CELL + GAP, h: GAP }
    : { x: cellX(wc) + CELL, y: cellY(wr), w: GAP, h: 2 * CELL + GAP };
}

/** Что находится под курсором: клетка, паз для забора или ничего. */
function hitTest(mx, my) {
  const gx = mx - PAD;
  const gy = my - PAD;
  if (gx < 0 || gy < 0) return null;

  const ci = Math.floor(gx / STEP);
  const ri = Math.floor(gy / STEP);
  const cOff = gx - ci * STEP;
  const rOff = gy - ri * STEP;
  if (ci < 0 || ci >= N || ri < 0 || ri >= N) return null;

  const inVGroove = cOff > CELL;      // паз между колонками ci и ci+1
  const inHGroove = rOff > CELL;      // паз между рядами ri и ri+1

  if (!inVGroove && !inHGroove) return { type: 'cell', r: ri, c: ci };

  const clamp = (x) => Math.max(0, Math.min(W - 1, x));
  if (inHGroove && inVGroove) {
    // ровно на пересечении — берём ориентацию, которой играли в прошлый раз
    return ui.lastOrient === 'h'
      ? { type: 'wall', wr: clamp(ri), wc: clamp(ci), kind: 'h' }
      : { type: 'wall', wr: clamp(ri), wc: clamp(ci), kind: 'v' };
  }
  if (inHGroove) return { type: 'wall', wr: clamp(ri), wc: clamp(ci), kind: 'h' };
  return { type: 'wall', wr: clamp(ri), wc: clamp(ci), kind: 'v' };
}

/* ─────────────────────────── отрисовка ─────────────────────────── */

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function draw() {
  const s = ui.state;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, SIZE, SIZE);

  ctx.fillStyle = COLOR.boardBg;
  ctx.fillRect(0, 0, SIZE, SIZE);

  // подписи координат
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

  // клетки
  for (let r = 0; r < N; r += 1) {
    for (let c = 0; c < N; c += 1) {
      ctx.fillStyle = (r + c) % 2 ? COLOR.cellAlt : COLOR.cell;
      roundRect(cellX(c), cellY(r), CELL, CELL, 6);
      ctx.fill();
      ctx.strokeStyle = COLOR.line;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  // целевые горизонтали — куда кому бежать
  ctx.globalAlpha = 0.5;
  for (let c = 0; c < N; c += 1) {
    ctx.fillStyle = COLOR.redSoft;
    roundRect(cellX(c), cellY(0), CELL, CELL, 6); ctx.fill();
    ctx.fillStyle = COLOR.blueSoft;
    roundRect(cellX(c), cellY(N - 1), CELL, CELL, 6); ctx.fill();
  }
  ctx.globalAlpha = 1;

  // подсказка: куда может пойти тот, чей сейчас ход
  const canPlay = !s.winner && !(ui.mode === 'bot' && s.turn === ui.botSide);
  if (canPlay) {
    ctx.fillStyle = COLOR.hint;
    for (const m of pawnMoves(s, s.turn)) {
      ctx.globalAlpha = ui.hover && ui.hover.type === 'cell'
        && ui.hover.r === m.r && ui.hover.c === m.c ? 0.85 : 0.35;
      ctx.beginPath();
      ctx.arc(cellX(m.c) + CELL / 2, cellY(m.r) + CELL / 2, 9, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  // поставленные заборы
  for (const [k, kind] of Object.entries(s.walls)) {
    const [wr, wc] = k.split(',').map(Number);
    const { x, y, w, h } = wallRect(wr, wc, kind);
    ctx.fillStyle = COLOR.wall;
    roundRect(x, y, w, h, 4); ctx.fill();
    ctx.strokeStyle = COLOR.wallEdge;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // призрак забора под курсором
  if (canPlay && ui.hover && ui.hover.type === 'wall') {
    const { wr, wc, kind } = ui.hover;
    const bad = wallProblem(s, s.turn, wr, wc, kind);
    const { x, y, w, h } = wallRect(wr, wc, kind);
    ctx.fillStyle = bad ? COLOR.ghostBad : COLOR.ghostOk;
    roundRect(x, y, w, h, 4); ctx.fill();
  }

  // фишки
  drawPawn(s.pawns[RED], COLOR.red);
  drawPawn(s.pawns[BLUE], COLOR.blue);
}

function drawPawn(p, color) {
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
  ctx.beginPath();
  ctx.arc(x - 5, y - 6, 5, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,255,255,.35)';
  ctx.fill();
}

/* ─────────────────────────── интерфейс ─────────────────────────── */

const $ = (sel) => document.querySelector(sel);

function sideName(side) { return side === RED ? 'Красный' : 'Синий'; }

function pushLog(text, side) {
  ui.log.unshift({ text, side, no: ui.state.moveNo });
  const box = $('#qLog');
  const row = document.createElement('div');
  row.className = 'q-log-row ' + (side || '');
  row.textContent = text;
  box.prepend(row);
}

function renderPanel() {
  const s = ui.state;
  $('#qRedWalls').textContent = s.wallsLeft[RED];
  $('#qBlueWalls').textContent = s.wallsLeft[BLUE];

  const pathR = shortestPath(s.walls, s.pawns[RED], s.goalRow[RED]);
  const pathB = shortestPath(s.walls, s.pawns[BLUE], s.goalRow[BLUE]);
  $('#qRedPath').textContent = pathR == null ? '—' : pathR;
  $('#qBluePath').textContent = pathB == null ? '—' : pathB;

  const turnEl = $('#qTurn');
  if (s.winner) {
    turnEl.textContent = `Победил ${sideName(s.winner).toLowerCase()}!`;
    turnEl.className = 'q-turn win ' + s.winner;
  } else {
    const waiting = ui.mode === 'bot' && s.turn === ui.botSide;
    turnEl.textContent = waiting ? 'Ход компьютера…' : `Ход: ${sideName(s.turn).toLowerCase()}`;
    turnEl.className = 'q-turn ' + s.turn;
  }
  $('#qUndo').disabled = ui.history.length === 0 || ui.busy;
}

function say(msg) {
  const el = $('#qMsg');
  el.textContent = msg || '';
  el.style.opacity = msg ? '1' : '0';
  if (msg) {
    clearTimeout(say._t);
    say._t = setTimeout(() => { el.style.opacity = '0'; }, 2600);
  }
}

/* ─────────────────────────── ходы ─────────────────────────── */

function remember() {
  ui.history.push(JSON.parse(JSON.stringify(ui.state)));
  if (ui.history.length > 200) ui.history.shift();
}

function afterTurn() {
  draw();
  renderPanel();
  if (ui.state.winner) { say(`Победил ${sideName(ui.state.winner).toLowerCase()}!`); return; }
  if (ui.mode === 'bot' && ui.state.turn === ui.botSide) {
    ui.busy = true;
    renderPanel();
    setTimeout(runBot, 350);
  }
}

function runBot() {
  const side = ui.botSide;
  const res = botMove(ui.state, side);
  if (res.kind === 'stuck') { say('Компьютер не нашёл хода.'); ui.busy = false; renderPanel(); return; }
  ui.state = res.state;
  pushLog(res.kind === 'move'
    ? `${sideName(side)}: ${cellName(res.to.r, res.to.c)}`
    : `${sideName(side)}: забор ${wallName(res.wall.wr, res.wall.wc, res.wall.kind)}`, side);
  ui.busy = false;
  draw();
  renderPanel();
  if (ui.state.winner) say(`Победил ${sideName(ui.state.winner).toLowerCase()}!`);
}

function tryMove(r, c) {
  const side = ui.state.turn;
  remember();
  const res = applyMove(ui.state, side, r, c);
  if (res.error) { ui.history.pop(); say(res.error); return; }
  ui.state = res.state;
  pushLog(`${sideName(side)}: ${cellName(r, c)}`, side);
  afterTurn();
}

function tryWall(wr, wc, kind) {
  const side = ui.state.turn;
  remember();
  const res = applyWall(ui.state, side, wr, wc, kind);
  if (res.error) { ui.history.pop(); say(res.error); return; }
  ui.lastOrient = kind;
  ui.state = res.state;
  pushLog(`${sideName(side)}: забор ${wallName(wr, wc, kind)}`, side);
  afterTurn();
}

function undo() {
  if (!ui.history.length || ui.busy) return;
  // в игре с компьютером откатываем пару ходов, иначе ход снова окажется его
  const steps = ui.mode === 'bot' && ui.history.length >= 2 ? 2 : 1;
  for (let i = 0; i < steps; i += 1) ui.state = ui.history.pop();
  const box = $('#qLog');
  for (let i = 0; i < steps && box.firstChild; i += 1) box.removeChild(box.firstChild);
  draw(); renderPanel(); say('Ход отменён.');
}

function newGame() {
  ui.state = initialState();
  ui.history = [];
  ui.log = [];
  ui.busy = false;
  $('#qLog').innerHTML = '';
  draw(); renderPanel(); say('');
  if (ui.mode === 'bot' && ui.state.turn === ui.botSide) setTimeout(runBot, 400);
}

/* ─────────────────────────── запуск ─────────────────────────── */

export function boot() {
  canvas = $('#qBoard');
  ctx = canvas.getContext('2d');
  dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = SIZE * dpr;
  canvas.height = SIZE * dpr;
  canvas.style.width = SIZE + 'px';
  canvas.style.height = SIZE + 'px';

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    const same = JSON.stringify(hit) === JSON.stringify(ui.hover);
    ui.hover = hit;
    canvas.style.cursor = hit ? 'pointer' : 'default';
    if (!same) draw();
  });
  canvas.addEventListener('mouseleave', () => { ui.hover = null; draw(); });

  canvas.addEventListener('click', (e) => {
    if (ui.busy || ui.state.winner) return;
    if (ui.mode === 'bot' && ui.state.turn === ui.botSide) return;
    const rect = canvas.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (!hit) return;
    if (hit.type === 'cell') tryMove(hit.r, hit.c);
    else tryWall(hit.wr, hit.wc, hit.kind);
  });

  // колесо и правая кнопка переключают ориентацию забора под курсором
  canvas.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    ui.lastOrient = ui.lastOrient === 'h' ? 'v' : 'h';
    if (ui.hover && ui.hover.type === 'wall') ui.hover.kind = ui.lastOrient;
    draw();
  });

  document.addEventListener('keydown', (e) => {
    if (ui.busy || ui.state.winner) return;
    if (ui.mode === 'bot' && ui.state.turn === ui.botSide) return;
    const p = ui.state.pawns[ui.state.turn];
    const d = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key];
    if (d) {
      e.preventDefault();
      const target = pawnMoves(ui.state, ui.state.turn)
        .find((m) => m.r === p.r + d[0] && m.c === p.c + d[1])
        // прыжок через соперника: цель на две клетки в ту же сторону
        || pawnMoves(ui.state, ui.state.turn)
          .find((m) => m.r === p.r + d[0] * 2 && m.c === p.c + d[1] * 2);
      if (target) tryMove(target.r, target.c);
      else say('Туда фишка пойти не может.');
    }
    if (e.key === 'r' || e.key === 'R' || e.key === 'к' || e.key === 'К') {
      ui.lastOrient = ui.lastOrient === 'h' ? 'v' : 'h';
      if (ui.hover && ui.hover.type === 'wall') ui.hover.kind = ui.lastOrient;
      draw();
    }
    if (e.key === 'z' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); undo(); }
  });

  document.querySelectorAll('[name=qMode]').forEach((r) => {
    r.addEventListener('change', () => { ui.mode = r.value; newGame(); });
  });
  $('#qNew').addEventListener('click', newGame);
  $('#qUndo').addEventListener('click', undo);

  draw();
  renderPanel();
}
