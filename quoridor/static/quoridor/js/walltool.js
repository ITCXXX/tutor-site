/**
 * quoridor/walltool.js — ход пальцем: шаг фишкой и постановка забора.
 *
 * На мыши забор ставится в один клик: курсор заранее показывает призрак, паз
 * под ним видно, промахнуться трудно. На телефоне не работает ничего из этого:
 * паза шириной 12 px не видно из-под пальца, наведения не существует, а правой
 * кнопки, которой переключают ориентацию, на сенсоре нет вовсе.
 *
 * Поэтому у касания свой порядок: первое касание не ставит забор, а примеряет
 * его — призрак липнет к ближайшему пазу, под доской появляются «Повернуть» и
 * «Поставить». Второе касание по призраку подтверждает. Тап рядом с зелёной
 * точкой остаётся ходом фишки (см. touchHit в render.js).
 *
 * Три вещи, без которых это ломается на настоящем телефоне:
 *
 *   • жест отличается от тапа. Доска занимает пол-экрана, и страницу листают
 *     пальцем прямо по ней; если считать началом касания любое касание, при
 *     каждой прокрутке выскакивал бы призрак забора. Поэтому решение
 *     принимается на отпускании и только если палец почти не двигался;
 *   • пальцев бывает несколько. Телефон держат рукой, и край ладони вполне
 *     может лежать на доске — работаем только с тем указателем, который начал
 *     касание первым;
 *   • после касания браузер шлёт ещё и click. Он пришёл бы в обработчик мыши
 *     и поставил забор сразу, мимо подтверждения, — поэтому клик, случившийся
 *     сразу после касания, игнорируется (`justTouched`).
 *
 * Мышь через этот модуль не ходит — у неё свой, прямой путь в board.js и
 * online.js.
 */

import { wallName } from './rules.js';
import { touchHit, boardPoint, wallRect } from './render.js';

const TAP_SLOP_PX = 12;      // сдвиг больше этого — это прокрутка, а не тап
const TAP_MS = 1500;         // по пазу целятся не спеша, торопить незачем
const GHOST_CLICK_MS = 700;  // столько после касания клики считаем эхом

/**
 * @param {object} o.canvas    холст доски
 * @param {function} o.canAct  можно ли сейчас ходить (не чужой ход, не конец)
 * @param {function} o.moves   допустимые ходы фишкой для того, кто ходит
 * @param {function} o.wallsLeft сколько заборов осталось у того, кто ходит
 * @param {function} o.onMove  (r, c) — тап по клетке
 * @param {function} o.onWall  (wr, wc, kind) — подтверждённый забор
 * @param {function} o.onChange перерисовать доску
 * @param {function} o.say     показать подсказку игроку
 */
export function createWallTool(o) {
  const strip = document.querySelector('#qWallTool');
  const label = document.querySelector('#qWallWhere');
  const state = { pending: null, orient: 'h', hinted: false, touchedAt: 0 };
  let down = null;

  function renderStrip() {
    if (!strip) return;
    strip.hidden = !state.pending;
    if (state.pending && label) {
      const { wr, wc, kind } = state.pending;
      label.textContent = wallName(wr, wc, kind);
    }
  }

  function clear() {
    if (!state.pending) return;
    state.pending = null;
    renderStrip();
    o.onChange();
  }

  function place() {
    if (!state.pending) return;
    const { wr, wc, kind } = state.pending;
    state.pending = null;
    renderStrip();
    o.onWall(wr, wc, kind);
  }

  function rotate() {
    if (!state.pending) return;
    state.orient = state.orient === 'h' ? 'v' : 'h';
    state.pending = { ...state.pending, kind: state.orient };
    renderStrip();
    o.onChange();
  }

  /** Палец попал в сам призрак — значит подтверждает его, а не метит заново. */
  function onGhost(x, y) {
    if (!state.pending) return false;
    const { wr, wc, kind } = state.pending;
    const r = wallRect(wr, wc, kind);
    const pad = 10;
    return x >= r.x - pad && x <= r.x + r.w + pad
        && y >= r.y - pad && y <= r.y + r.h + pad;
  }

  function onDown(e) {
    if (e.pointerType !== 'touch') return;
    state.touchedAt = Date.now();
    if (down) return;                          // ведём только первый палец
    down = { id: e.pointerId, x: e.clientX, y: e.clientY, t: Date.now() };
  }

  function onUp(e) {
    if (e.pointerType !== 'touch') return;
    state.touchedAt = Date.now();
    if (!down || down.id !== e.pointerId) return;
    const start = down;
    down = null;

    const moved = Math.hypot(e.clientX - start.x, e.clientY - start.y);
    if (moved > TAP_SLOP_PX || Date.now() - start.t > TAP_MS) return;  // листали
    if (!o.canAct()) return;

    const { x, y } = boardPoint(o.canvas, e.clientX, e.clientY);

    // Подтверждение проверяем раньше всего.
    if (onGhost(x, y)) { place(); return; }

    const hit = touchHit(x, y, o.moves ? o.moves() : [], state.orient);
    if (!hit) return;

    // Второе касание того же места — это «ставь», даже если призрак успели
    // повернуть: при повороте забор уходит с точки, куда целились, и без этой
    // проверки касание молча вернуло бы прежнюю ориентацию.
    if (state.pending && hit.type === 'wall'
        && hit.wr === state.pending.wr && hit.wc === state.pending.wc) {
      place();
      return;
    }

    if (hit.type === 'cell') {
      state.pending = null;
      renderStrip();
      o.onChange();
      o.onMove(hit.r, hit.c);
      return;
    }

    if (o.wallsLeft && o.wallsLeft() <= 0) {
      clear();
      o.say('Заборы кончились — остаётся ходить фишкой.');
      return;
    }

    state.orient = hit.kind;
    state.pending = { wr: hit.wr, wc: hit.wc, kind: hit.kind };
    renderStrip();
    o.onChange();

    if (!state.hinted) {
      state.hinted = true;
      o.say('Коснитесь забора ещё раз, чтобы поставить. Или кнопками под доской.');
    }
  }

  o.canvas.addEventListener('pointerdown', onDown);
  o.canvas.addEventListener('pointerup', onUp);
  o.canvas.addEventListener('pointercancel', (e) => {
    if (down && down.id === e.pointerId) down = null;
  });

  const bind = (sel, fn) => {
    const el = document.querySelector(sel);
    if (el) el.addEventListener('click', fn);
  };
  bind('#qWallRotate', rotate);
  bind('#qWallPlace', place);
  bind('#qWallCancel', clear);

  return {
    get pending() { return state.pending; },
    /** Клик пришёл эхом недавнего касания — обработчику мыши его брать нельзя. */
    justTouched() { return Date.now() - state.touchedAt < GHOST_CLICK_MS; },
    clear,
  };
}
