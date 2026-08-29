/**
 * quoridor/online.js — клиент сетевой партии.
 *
 * Правила здесь НЕ решают ничего: они нужны только для подсказок — куда можно
 * пойти и ляжет ли забор. Решение принимает сервер (quoridor/engine.py), и
 * после каждого хода состояние берётся оттуда, а не достраивается на месте.
 * Так двое игроков не смогут разойтись в том, что произошло на доске.
 *
 * Обмен — опросом, как в УТТТ: партия пошаговая, задержка в пару секунд ей
 * не мешает, а WebSocket ради этого поднимать незачем. Но у опроса есть
 * ловушка: браузер придерживает таймеры в фоновых вкладках, а создатель партии
 * как раз уходит в мессенджер отправлять ссылку. Поэтому мы спрашиваем сервер
 * сразу, как только вкладка снова на виду, — и не ждём своей очереди по
 * таймеру, который всё это время стоял.
 */

import { RED, BLUE } from './rules.js';
import { hitTest, setupCanvas, drawBoard } from './render.js';

const POLL_ACTIVE = 1500;    // идёт партия — ждём хода соперника
const POLL_IDLE = 1500;      // ждём, пока соперник откроет ссылку
const POLL_HIDDEN = 15000;   // вкладка не на виду: браузер всё равно придержит

const CONFIRM_MS = 5000;     // сколько кнопка «сдаться» ждёт подтверждения
const ARM_GUARD_MS = 400;    // столько после взвода клик не считается подтверждением

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
  seating: false,          // посадка прямо сейчас в полёте
  seatTries: 0,            // сколько раз пробовали сесть — чтобы не долбиться вечно
  polling: false,
  stamp: '',
  resignArmed: false,
  armedAt: 0,
  armedFor: '',
  stalled: false,          // сервер ответил не тем — дальше опрашивать бессмысленно
};

let canvas, ctx, dpr = 1, timer = null, resignTimer = null;

const $ = (sel) => document.querySelector(sel);
const sideName = (s) => (s === RED ? 'Красный' : 'Синий');
const sideWord = (s) => (s === RED ? 'красными' : 'синими');
const isOver = () => ui.status === 'finished' || ui.status === 'cancelled' || !!ui.winner;
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

function turnText() {
  const s = ui.state;
  if (ui.status === 'cancelled') return { text: 'Партия отменена', cls: 'wait' };

  if (isOver()) {
    const byResign = ui.lastMove && ui.lastMove.kind === 'resign';
    if (!ui.mySide) {
      return {
        text: byResign
          ? `${sideName(ui.lastMove.side)} сдался — победил ${sideName(ui.winner).toLowerCase()}`
          : `Победил ${sideName(ui.winner).toLowerCase()}`,
        cls: 'win ' + ui.winner,
      };
    }
    const mine = ui.winner === ui.mySide;
    let text;
    if (byResign) text = mine ? 'Соперник сдался — вы победили' : 'Вы сдались';
    else text = mine ? 'Вы победили!' : 'Вы проиграли';
    return { text, cls: 'win ' + ui.winner };
  }

  if (ui.status === 'waiting') {
    return {
      text: ui.mySide ? 'Ждём соперника — отправьте ему ссылку' : 'Партия ждёт второго игрока',
      cls: 'wait',
    };
  }
  if (!ui.mySide) {
    return { text: `Ход: ${sideName(s.turn).toLowerCase()} (вы наблюдаете)`, cls: s.turn };
  }
  return { text: myTurn() ? 'Ваш ход' : 'Ход соперника…', cls: s.turn };
}

function renderRole() {
  const el = $('#qRole');
  if (!el) return;
  if (ui.mySide) {
    el.textContent = ui.mySide === RED
      ? 'Вы играете красными и ходите первым.'
      : 'Вы играете синими.';
  } else if (!ui.seating) {
    el.textContent = ui.status === 'waiting' && ui.seatTries >= 3
      ? 'Сесть за доску не удалось — нажмите кнопку в шапке.'
      : 'Вы смотрите за партией со стороны.';
  }
}

/**
 * Что означает уход прямо сейчас — от этого зависит и подпись кнопки.
 *
 * Пока ходов нет, поражения быть не может: человек просто встаёт из-за стола.
 * Это важно как раз потому, что место занимается автоматически: заглянул на
 * чужую партию — и уже игрок; выйти должно быть так же легко, как войти.
 */
function started() {
  return !!(ui.state && ui.state.moveNo > 1);
}

function leaveLabel() {
  if (started()) return 'Сдаться';
  return ui.status === 'waiting' ? 'Отменить партию' : 'Выйти из партии';
}

function renderResign() {
  const btn = $('#qResign');
  if (!btn) return;
  if (!ui.mySide || isOver()) {
    btn.hidden = true;
    disarmResign();
    return;
  }
  btn.hidden = false;
  if (!ui.resignArmed) btn.textContent = leaveLabel();
}

function renderInvite() {
  const box = $('#qInvite');
  if (!box) return;

  // Ссылка «отправьте сопернику» — ровно то место, куда смотрит создатель,
  // пока ждёт. Если её не убрать после начала партии, человек читает старую
  // подсказку и считает, что соперник так и не зашёл.
  box.hidden = ui.status !== 'waiting';
  if (ui.mySide && $('#qJoinForm')) box.innerHTML = '';
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

  const { text, cls } = turnText();
  const turnEl = $('#qTurn');
  turnEl.textContent = text;
  turnEl.className = 'q-turn ' + cls;

  renderRole();
  renderResign();
  renderInvite();
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
  let text;
  if (move.kind === 'wall') text = `${sideName(move.side)}: забор ${move.name}`;
  else if (move.kind === 'resign') text = `${sideName(move.side)} сдался`;
  else if (move.kind === 'cancel') text = 'Партия отменена';
  else text = `${sideName(move.side)}: ${move.name}`;

  if (box.firstChild && box.firstChild.dataset.stamp === ui.stamp) return;

  const row = document.createElement('div');
  row.className = 'q-log-row ' + (move.side || '');
  row.dataset.stamp = ui.stamp;
  row.textContent = text;
  box.prepend(row);
}

/* ───────────────────────── обмен ───────────────────────── */

function absorb(data) {
  // Ответы приходят из двух источников — опрос и собственный ход — и обгоняют
  // друг друга. Без этой проверки доска после своего же хода на мгновение
  // откатывалась бы к позиции, которую опрос запросил чуть раньше.
  // Сравнение строковое: сервер шлёт время в ISO, а такие строки сравниваются
  // как даты, если формат один — а он один.
  if (ui.stamp && data.updated_at < ui.stamp) return false;

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

  // Гость, открывший ссылку, садится сам: пока он ищет кнопку, создатель
  // смотрит на «ждём соперника» и думает, что сломалось.
  if (data.can_seat && !ui.seating && ui.seatTries < 3) takeSeat();

  return changed;
}

/**
 * Запрос к серверу партии.
 *
 * Три вещи, которых не даёт голый fetch:
 *   • таймаут — иначе одно зависшее соединение молча останавливает весь опрос,
 *     и доска замирает без единого сообщения;
 *   • cache: 'no-store' — состояние партии кэшировать нельзя ни секунды;
 *   • распознавание входа — если сессия истекла, сервер отвечает редиректом на
 *     страницу логина, fetch послушно её скачивает, и разбор JSON падает
 *     каждые полторы секунды. Лучше сказать это вслух один раз.
 */
async function ask(url, options = {}) {
  const res = await fetch(url, {
    cache: 'no-store',
    credentials: 'same-origin',
    signal: AbortSignal.timeout(8000),
    ...options,
    headers: { 'X-Requested-With': 'fetch', ...(options.headers || {}) },
  });

  const isJson = (res.headers.get('content-type') || '').includes('application/json');
  if (!isJson) {
    // Редирект на страницу входа — это конец: опрашивать дальше нечего, пока
    // человек не войдёт заново. А вот HTML от упавшего прокси (502 на время
    // выкладки) — беда временная, и бросать из-за неё партию не надо.
    if (res.redirected || res.status === 401 || res.status === 403) ui.stalled = true;
    throw new Error(ui.stalled ? 'signed-out' : 'not-json');
  }
  return { res, data: await res.json() };
}

async function poll() {
  if (ui.polling) return;
  ui.polling = true;
  try {
    const { res, data } = await ask(ui.urls.state);
    if (res.ok) absorb(data);
  } catch (e) {
    if (ui.stalled) say('Сессия закончилась — обновите страницу.');
    // иначе связь пропала: молча ждём следующего круга, партия не теряется
  } finally {
    ui.polling = false;
    schedule();
  }
}

function schedule() {
  clearTimeout(timer);
  if (isOver() || ui.stalled) return;           // партия окончена или нас разлогинило
  const delay = document.hidden ? POLL_HIDDEN
    : (ui.status === 'active' ? POLL_ACTIVE : POLL_IDLE);
  timer = setTimeout(poll, delay);
}

/** Спросить сервер немедленно, не дожидаясь таймера. */
function pollNow() {
  if (isOver() || ui.stalled) return;
  if (ui.polling) return;        // запрос уже в пути, его хвост сам перезапустит счёт
  clearTimeout(timer);
  poll();
}

async function takeSeat() {
  ui.seating = true;
  ui.seatTries += 1;
  const el = $('#qRole');
  if (el) el.textContent = 'Занимаем свободное место…';
  try {
    const { res, data } = await ask(ui.urls.join, {
      method: 'POST',
      headers: { 'X-CSRFToken': ui.csrf },
    });
    if (res.ok) {
      absorb(data);
      // Второе окно той же партии получает took='', хотя игрок за доской сидит:
      // место занято им же. Говорить ему «место занято» было бы враньём.
      if (data.took) say(`Вы играете ${sideWord(data.took)}.`);
      else if (!data.my_side) say('Место уже занято — вы наблюдаете за партией.');
    }
  } catch (e) {
    say(ui.seatTries >= 3
      ? 'Не удалось занять место — нажмите кнопку в шапке.'
      : 'Не удалось занять место, пробуем ещё раз…');
  } finally {
    // Флаг снимается в любом случае: иначе после неудачи строка роли навсегда
    // застревала бы на «Занимаем свободное место…», а повтора бы не было.
    ui.seating = false;
    renderRole();
  }
}

async function send(body) {
  if (ui.busy) return;
  ui.busy = true;
  try {
    const { res, data } = await ask(ui.urls.move, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ui.csrf },
      body: JSON.stringify(body),
    });
    if (!res.ok) say(data.error || 'Ход не принят.');
    else absorb(data);
  } catch (e) {
    say(ui.stalled ? 'Сессия закончилась — обновите страницу.'
                   : 'Нет связи с сервером. Ход не отправлен.');
  } finally {
    // Ритм опроса перезапускается в любом случае. Раньше отказ сервера
    // выходил из функции раньше времени, и доска переставала обновляться
    // вовсе — до следующего возвращения во вкладку.
    ui.busy = false;
    schedule();
  }
}

/* ───────────────────────── сдача ───────────────────────── */

function disarmResign() {
  clearTimeout(resignTimer);
  ui.resignArmed = false;
  ui.armedFor = '';
  const btn = $('#qResign');
  if (btn) btn.classList.remove('armed');
}

/**
 * Уход в два клика.
 *
 * Первый клик превращает кнопку в вопрос, второй отправляет. Модальное окно
 * тут было бы честнее по смыслу, но кнопка стоит вплотную к доске, и случайно
 * задеть её проще, чем кажется, — а отменить сдачу уже нельзя.
 *
 * Две тонкости, без которых два клика не защищают:
 *   • обычный двойной щелчок мышью — это те же два клика подряд, поэтому
 *     подтверждение не принимается первые ARM_GUARD_MS;
 *   • пока кнопка взведена, соперник может сесть и сходить, и «выйти из
 *     партии» на глазах превращается в «сдаться». Такой клик не отправляем:
 *     кнопка перевзводится с новой подписью, и человек решает заново.
 */
function onResignClick() {
  const btn = $('#qResign');
  if (!ui.mySide || isOver()) return;

  const meaning = started() ? 'resign' : 'leave';

  if (!ui.resignArmed) {
    ui.resignArmed = true;
    ui.armedAt = Date.now();
    ui.armedFor = meaning;
    btn.classList.add('armed');
    btn.textContent = meaning === 'resign' ? 'Точно сдаться?' : 'Точно выйти?';
    resignTimer = setTimeout(() => { disarmResign(); renderResign(); }, CONFIRM_MS);
    return;
  }

  if (Date.now() - ui.armedAt < ARM_GUARD_MS) return;      // это был двойной щелчок

  if (meaning !== ui.armedFor) {
    disarmResign();
    renderResign();
    say(meaning === 'resign'
      ? 'Партия уже началась — теперь это сдача. Нажмите ещё раз, если решились.'
      : 'Партия ещё не началась — теперь это просто выход.');
    onResignClick();                                        // взводим заново, уже с новым смыслом
    return;
  }

  if (ui.busy) { say('Секунду, отправляем предыдущий ход…'); return; }

  disarmResign();
  sendResign();
}

async function sendResign() {
  if (ui.busy) return;
  ui.busy = true;
  try {
    const { res, data } = await ask(ui.urls.resign, {
      method: 'POST',
      headers: { 'X-CSRFToken': ui.csrf },
    });
    if (!res.ok) {
      say(data.error || 'Не получилось.');
    } else if (data.outcome === 'left') {
      // Место освобождено. Остаться на странице нельзя: она тут же посадила бы
      // нас обратно, ведь место снова свободно.
      window.location = ui.urls.lobby;
      return;
    } else {
      absorb(data);
    }
  } catch (e) {
    say('Нет связи с сервером.');
  } finally {
    ui.busy = false;
    renderResign();
    schedule();
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
    if (!myTurn()) {
      if (isOver()) say('Партия закончена.');
      else if (ui.status === 'waiting') say('Партия ещё не началась — ждём соперника.');
      else say(ui.mySide ? 'Сейчас ход соперника.' : 'Вы наблюдаете за партией.');
      return;
    }
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
    if (e.key === 'Escape') { disarmResign(); renderResign(); }
  });

  const resignBtn = $('#qResign');
  if (resignBtn) resignBtn.addEventListener('click', onResignClick);

  const copyBtn = $('#qCopy');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      const field = $('#qLink');
      const link = field ? field.value : window.location.href;
      try {
        await navigator.clipboard.writeText(link);
        say('Ссылка скопирована — отправьте её сопернику.');
      } catch (err) {
        if (field) { field.focus(); field.select(); }
        say('Скопируйте ссылку из поля выше.');
      }
    });
  }

  // Таймер в фоновой вкладке браузер придерживает — от минуты и дольше.
  // Поэтому спрашиваем сервер сразу, как только на страницу снова смотрят.
  document.addEventListener('visibilitychange', () => { if (!document.hidden) pollNow(); });
  window.addEventListener('focus', pollNow);
  window.addEventListener('online', pollNow);
  // Возврат «назад» отдаёт страницу из bfcache со всеми замороженными таймерами.
  window.addEventListener('pageshow', (e) => { if (e.persisted) pollNow(); });

  poll();
}
