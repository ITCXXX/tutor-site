/**
 * quoridor/board.js — доска и управление.
 *
 * Отрисовка на canvas: сетка клеток с пазами между ними, в пазы кладутся
 * заборы. Клик по клетке — ход фишкой, клик по пазу — забор. Ориентация
 * забора определяется тем, в каком пазу курсор: в горизонтальном или
 * вертикальном. На пересечении берётся последняя использованная — чтобы
 * не заставлять игрока лишний раз переключать режим.
 */

import { RED, BLUE, initialState, pawnMoves, applyMove, applyWall,
         shortestPath, cellName, wallName } from './rules.js';
import { botMove, LEVELS, DEFAULT_LEVEL, levelOf } from './bot.js';
import { hitTest, setupCanvas, drawBoard, boardPoint } from './render.js';
import { createWallTool } from './walltool.js';

/* ────────────────────────── состояние экрана ────────────────────────── */

const ui = {
  state: initialState(),
  history: [],
  mode: 'hotseat',                    // 'hotseat' | 'bot'
  level: DEFAULT_LEVEL,               // 'easy' | 'medium' | 'hard'
  botSide: BLUE,
  lastOrient: 'h',
  hover: null,
  log: [],
  busy: false,
};

let canvas, ctx, scale = 1, tool = null;

/** Может ли человек сейчас ходить: не конец партии и не очередь компьютера. */
function canAct() {
  return !ui.busy && !ui.state.winner
      && !(ui.mode === 'bot' && ui.state.turn === ui.botSide);
}

/** Перерисовать доску. Вся геометрия и стиль — в render.js. */
function draw() {
  drawBoard(ctx, scale, {
    state: ui.state,
    hover: ui.hover,
    canPlay: canAct(),
    mySide: null,
    lastMove: null,
    pending: tool ? tool.pending : null,
  });
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
    turnEl.textContent = waiting
      ? `Ход компьютера (${levelOf(ui.level).title})…`
      : `Ход: ${sideName(s.turn).toLowerCase()}`;
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
  if (tool) tool.clear();
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
  const res = botMove(ui.state, side, ui.level);
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
  if (tool) tool.clear();          // позиция уехала — примерка больше не про неё
  // в игре с компьютером откатываем пару ходов, иначе ход снова окажется его
  const steps = ui.mode === 'bot' && ui.history.length >= 2 ? 2 : 1;
  for (let i = 0; i < steps; i += 1) ui.state = ui.history.pop();
  const box = $('#qLog');
  for (let i = 0; i < steps && box.firstChild; i += 1) box.removeChild(box.firstChild);
  draw(); renderPanel(); say('Ход отменён.');
}

function newGame() {
  if (tool) tool.clear();
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
  // Режим приходит из лобби ссылкой ?mode=bot — иначе кнопка «против
  // компьютера» открывала бы обычную игру вдвоём и выбирать пришлось бы заново.
  const params = new URLSearchParams(window.location.search);
  const wanted = params.get('mode');
  if (wanted === 'bot' || wanted === 'hotseat') {
    ui.mode = wanted;
    const radio = document.querySelector(`[name=qMode][value="${wanted}"]`);
    if (radio) radio.checked = true;
  }
  const level = params.get('level');
  if (level && LEVELS[level]) ui.level = level;

  canvas = $('#qBoard');
  ctx = canvas.getContext('2d');
  scale = setupCanvas(canvas);

  // Палец ставит забор в два касания — примеряет и подтверждает. Почему так,
  // объяснено в walltool.js; мышь ходит мимо этого модуля, ей хватает клика.
  tool = createWallTool({
    canvas,
    canAct,
    moves: () => pawnMoves(ui.state, ui.state.turn),
    wallsLeft: () => ui.state.wallsLeft[ui.state.turn],
    onMove: tryMove,
    onWall: tryWall,
    onChange: draw,
    say,
  });

  // Доска подстраивается под ширину экрана, значит и при повороте телефона
  // её надо пересчитать — иначе останется размер прежней ориентации.
  window.addEventListener('resize', () => { scale = setupCanvas(canvas); draw(); });

  canvas.addEventListener('mousemove', (e) => {
    const { x, y } = boardPoint(canvas, e.clientX, e.clientY);
    const hit = hitTest(x, y, ui.lastOrient);
    const same = JSON.stringify(hit) === JSON.stringify(ui.hover);
    ui.hover = hit;
    canvas.style.cursor = hit ? 'pointer' : 'default';
    if (!same) draw();
  });
  canvas.addEventListener('mouseleave', () => { ui.hover = null; draw(); });

  canvas.addEventListener('click', (e) => {
    if (!canAct()) return;
    if (tool && tool.justTouched()) return;   // это эхо касания, его уже обработали
    const { x, y } = boardPoint(canvas, e.clientX, e.clientY);
    const hit = hitTest(x, y, ui.lastOrient);
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
    r.addEventListener('change', () => { ui.mode = r.value; syncLevelBox(); newGame(); });
  });

  const levelBox = $('#qLevel');
  if (levelBox) {
    levelBox.value = ui.level;
    levelBox.addEventListener('change', () => { ui.level = levelBox.value; newGame(); });
  }
  syncLevelBox();
  $('#qNew').addEventListener('click', newGame);
  $('#qUndo').addEventListener('click', undo);

  draw();
  renderPanel();
}

/** Выбор уровня нужен только против компьютера — вдвоём он бессмыслен. */
function syncLevelBox() {
  const wrap = $('#qLevelWrap');
  if (wrap) wrap.hidden = ui.mode !== 'bot';
}
