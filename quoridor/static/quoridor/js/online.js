/**
 * quoridor/online.js — клиент сетевой партии.
 *
 * Правила здесь НЕ решают ничего: они нужны только для подсказок — куда можно
 * пойти и ляжет ли забор. Решение принимает сервер (quoridor/engine.py), и
 * после каждого хода состояние берётся оттуда, а не достраивается на месте.
 * Так двое игроков не смогут разойтись в том, что произошло на доске.
 *
 * Обмен — опросом, как в УТТТ: партия пошаговая, задержка в пару секунд ей
 * не мешает, а WebSocket ради этого поднимать незачем.
 */

import { RED, BLUE } from './rules.js';
import { hitTest, setupCanvas, drawBoard } from './render.js';

const POLL_IDLE = 2500;      // как часто спрашивать сервер, пока ждём соперника
const POLL_ACTIVE = 1800;    // ...и пока идёт партия

const ui = {
  urls: null,
  csrf: '',
  mySide: '',
  state: null,
  status: 'waiting',
  winner: '',
  lastMove: null,
  labels: { red: '', blue: '' },
  paths: { red: null, blue: null },
  hover: null,
  lastOrient: 'h',
  busy: false,
  stamp: '',
};

let canvas, ctx, dpr = 1, timer = null;

const $ = (sel) => document.querySelector(sel);
const sideName = (s) => (s === RED ? 'Красный' : 'Синий');
const myTurn = () => ui.status === 'active' && ui.state && ui.state.turn === ui.mySide;

/* ───────────────────────── отрисовка ───────────────────────── */

function draw() {
  if (!ui.state) return;
  drawBoard(ctx, dpr, {
    state: ui.state,
    hover: ui.hover,
    canPlay: myTurn(),
    mySide: ui.mySide || null,
    lastMove: ui.lastMove,
  });
}

function renderPanel() {
  const s = ui.state;
  if (!s) return;

  $('#qRedName').textContent = ui.labels.red;
  $('#qBlueName').textContent = ui.labels.blue;
  $('#qRedWalls').textContent = s.wallsLeft[RED];
  $('#qBlueWalls').textContent = s.wallsLeft[BLUE];
  $('#qRedPath').textContent = ui.paths.red == null ? '—' : ui.paths.red;
  $('#qBluePath').textContent = ui.paths.blue == null ? '—' : ui.paths.blue;

  document.querySelectorAll('.q-player').forEach((el) => {
    el.classList.toggle('is-me', el.dataset.side === ui.mySide);
    el.classList.toggle('is-turn', ui.status === 'active' && s.turn === el.dataset.side);
  });

  const turnEl = $('#qTurn');
  if (ui.status === 'waiting') {
    turnEl.textContent = 'Ждём соперника — отправьте ему ссылку';
    turnEl.className = 'q-turn wait';
  } else if (ui.winner) {
    const mine = ui.winner === ui.mySide;
    turnEl.textContent = ui.mySide
      ? (mine ? 'Вы победили!' : 'Вы проиграли')
      : `Победил ${sideName(ui.winner).toLowerCase()}`;
    turnEl.className = 'q-turn win ' + ui.winner;
  } else if (!ui.mySide) {
    turnEl.textContent = `Ход: ${sideName(s.turn).toLowerCase()} (вы наблюдаете)`;
    turnEl.className = 'q-turn ' + s.turn;
  } else {
    turnEl.textContent = myTurn() ? 'Ваш ход' : 'Ход соперника…';
    turnEl.className = 'q-turn ' + s.turn;
  }
}

function say(msg) {
  const el = $('#qMsg');
  el.textContent = msg || '';
  el.style.opacity = msg ? '1' : '0';
  if (msg) {
    clearTimeout(say._t);
    say._t = setTimeout(() => { el.style.opacity = '0'; }, 3000);
  }
}

function pushLog(move) {
  if (!move) return;
  const box = $('#qLog');
  const text = move.kind === 'wall'
    ? `${sideName(move.side)}: забор ${move.name}`
    : `${sideName(move.side)}: ${move.name}`;
  if (box.firstChild && box.firstChild.dataset.stamp === ui.stamp) return;
  const row = document.createElement('div');
  row.className = 'q-log-row ' + move.side;
  row.dataset.stamp = ui.stamp;
  row.textContent = text;
  box.prepend(row);
}

/* ───────────────────────── обмен ───────────────────────── */

function absorb(data) {
  const changed = data.updated_at !== ui.stamp;
  ui.state = data.state;
  ui.status = data.status;
  ui.winner = data.winner || '';
  ui.mySide = data.my_side || '';
  ui.labels = { red: data.red_label, blue: data.blue_label };
  ui.paths = { red: data.paths[RED], blue: data.paths[BLUE] };
  if (changed) {
    ui.stamp = data.updated_at;
    ui.lastMove = data.last_move;
    pushLog(data.last_move);
  }
  draw();
  renderPanel();
  return changed;
}

async function poll() {
  try {
    const res = await fetch(ui.urls.state, { headers: { 'X-Requested-With': 'fetch' } });
    if (res.ok) absorb(await res.json());
  } catch (e) {
    // связь пропала — молча ждём следующего круга, партия не теряется
  }
  schedule();
}

function schedule() {
  clearTimeout(timer);
  if (ui.winner) return;                       // партия окончена, опрашивать нечего
  timer = setTimeout(poll, ui.status === 'active' ? POLL_ACTIVE : POLL_IDLE);
}

async function send(body) {
  if (ui.busy) return;
  ui.busy = true;
  try {
    const res = await fetch(ui.urls.move, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ui.csrf },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) { say(data.error || 'Ход не принят.'); return; }
    absorb(data);
    schedule();
  } catch (e) {
    say('Нет связи с сервером. Ход не отправлен.');
  } finally {
    ui.busy = false;
  }
}

/* ───────────────────────── запуск ───────────────────────── */

export function boot(urls, csrf) {
  ui.urls = urls;
  ui.csrf = csrf;

  canvas = $('#qBoard');
  ctx = canvas.getContext('2d');
  dpr = setupCanvas(canvas);

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top, ui.lastOrient);
    if (JSON.stringify(hit) === JSON.stringify(ui.hover)) return;
    ui.hover = hit;
    canvas.style.cursor = hit && myTurn() ? 'pointer' : 'default';
    draw();
  });
  canvas.addEventListener('mouseleave', () => { ui.hover = null; draw(); });

  canvas.addEventListener('click', (e) => {
    if (!myTurn()) { say(ui.mySide ? 'Сейчас ход соперника.' : 'Вы наблюдаете за партией.'); return; }
    const rect = canvas.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top, ui.lastOrient);
    if (!hit) return;
    if (hit.type === 'cell') send({ kind: 'move', r: hit.r, c: hit.c });
    else { ui.lastOrient = hit.kind; send({ kind: 'wall', wr: hit.wr, wc: hit.wc, orient: hit.kind }); }
  });

  canvas.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    ui.lastOrient = ui.lastOrient === 'h' ? 'v' : 'h';
    if (ui.hover && ui.hover.type === 'wall') ui.hover.kind = ui.lastOrient;
    draw();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'r' || e.key === 'R' || e.key === 'к' || e.key === 'К') {
      ui.lastOrient = ui.lastOrient === 'h' ? 'v' : 'h';
      if (ui.hover && ui.hover.type === 'wall') ui.hover.kind = ui.lastOrient;
      draw();
    }
  });

  const copyBtn = $('#qCopy');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(window.location.href);
        say('Ссылка скопирована — отправьте её сопернику.');
      } catch (err) {
        say('Скопируйте ссылку из адресной строки.');
      }
    });
  }

  poll();
}
