/* board/board.js — бесконечный совместный холст на Konva.
 *
 * Единая модель элемента:
 *   { id, type, data: { x, y, ...геометрия относительно (x,y)..., stroke, strokeWidth }, z }
 * Позиция элемента — всегда data.x / data.y; геометрия (points/width/height/радиусы)
 * задаётся ОТНОСИТЕЛЬНО этой позиции. Тогда перемещение = изменение x/y, а
 * Konva-узел рисуется как node.x = data.x, node.y = data.y. Это делает рисование,
 * перетаскивание и синхронизацию по сети единообразными.
 */
(function () {
  'use strict';

  const cfg = window.BOARD_CONFIG;
  const stageEl = document.getElementById('board-stage');
  const cursorLayerEl = document.getElementById('cursor-layer');
  const frameExitBtn = document.getElementById('frame-exit-btn');
  // Верх контейнера холста в окне. Был 56 (высота навбара над холстом); навбар
  // на странице доски убран, холст идёт от самого верха — 0. Единая точка правды
  // для перевода координат окна → экранные (раньше «56» было зашито в 8 местах).
  const STAGE_TOP = 0;

  // ── Konva: сцена и слой ───────────────────────────────────────────────
  const stage = new Konva.Stage({
    container: 'board-stage',
    width: stageEl.clientWidth,
    height: stageEl.clientHeight,
    draggable: false, // включаем только в режиме «select» (панорама)
  });
  const layer = new Konva.Layer();
  stage.add(layer);

  // ── Координатная сетка (фон) ───────────────────────────────────────────
  // Отдельный слой под рисованием. Рисуется один Shape с кастомным sceneFunc,
  // который перерисовывает видимую часть бесконечной сетки при зуме/панораме.
  const GRID_STEP = 40; // базовый шаг клетки в мировых единицах (при 100%)
  // Мельче этого мелкая клетка на ЭКРАНЕ не показывается: иначе линии сливаются
  // в серую заливку. Для точек порог выше — их рисовать дороже, чем линии.
  // 20 подобрано так, чтобы 100% попадало ровно в СЕРЕДИНУ уровня: там оба
  // слоя видны, клетка 40 пикселей и крупная 160 — привычный вид по умолчанию.
  // Края уровня (где слой один) приходятся на 50% и 200%.
  const GRID_MIN_PX = 20, GRID_MIN_PX_DOTS = 26;
  // Насколько видны мелкие и крупные линии.
  const GRID_A_MINOR = 0.38, GRID_A_MAJOR = 1;
  // Шаг клетчатого фона растёт и убывает ВЧЕТВЕРО (40 → 160 → 640…): именно
  // вчетверо, потому что крупная клетка делится мелкой на 4×4, и при смене
  // уровня бывшая крупная обязана в точности встать на место новой мелкой.
  function gridStep4For(scale) {
    let step = GRID_STEP;
    for (let i = 0; step * scale < GRID_MIN_PX && i < 20; i++) step *= 4;
    for (let i = 0; step * scale >= GRID_MIN_PX * 4 && step > 0.7 && i < 20; i++) step /= 4;
    return step;
  }
  // Яркость «мелкого» класса — тех трёх четвертей линий, что не кратны четырём.
  // Экранный шаг гуляет от порога до четырёх порогов, и по нему же:
  //   у верхнего края — как у крупных: виден ОДИН ровный слой;
  //   в середине      — вполсилы: ДВА уровня с делением 4×4;
  //   у нижнего края  — ноль: снова один слой, из одних крупных.
  // В момент смены шага бывшие крупные становятся мелкими верхнего края и
  // сохраняют ту же яркость — поэтому картинка до и после совпадает.
  function gridMinorAlpha(px) {
    const u = px / GRID_MIN_PX;                 // 1 у нижнего края, 4 у верхнего
    if (u <= 1) return 0;
    if (u >= 4) return GRID_A_MAJOR;
    if (u < 2) return GRID_A_MINOR * (u - 1);   // гаснет к нижнему краю
    return GRID_A_MINOR + (GRID_A_MAJOR - GRID_A_MINOR) * (u - 2) / 2;  // сливается с крупными
  }
  // Шаг мелкой клетки под текущий масштаб. Ряд ×2 (40 → 80 → 160 → 320 → 640):
  // при делении на 4 каждый следующий крупный шаг кратен предыдущему, поэтому
  // при переходе линии не съезжают вбок, а просто прореживаются вдвое.
  // Мельче базового шага не идём — это клетка тетради при 100%.
  function gridStepFor(scale, minPx) {
    let step = GRID_STEP;
    for (let i = 0; step * scale < minPx && i < 40; i++) step *= 2;
    return step;
  }
  const BOARD_CFG_ID = '__boardcfg__'; // singleton-элемент настроек доски (фон)
  let boardBg = 'grid'; // grid | dots | lines | blank — общий фон полотна
  let boardBgColor = ''; // цвет полотна ('' = по умолчанию из CSS)
  let boardGridColor = ''; // цвет рисунка фона (линии/точки), '' = по умолчанию
  const gridLayer = new Konva.Layer({ listening: false });
  stage.add(gridLayer);
  gridLayer.moveToBottom();
  const gridShape = new Konva.Shape({ sceneFunc: drawGrid });
  gridLayer.add(gridShape);

  // Слой активного штриха. Пока человек ведёт линию, меняется ровно один
  // объект — и перерисовывать из-за него тысячи чужих незачем. Замер: одна
  // перерисовка слоя с 2000 штрихов стоит 25.6 мс при бюджете кадра 16.7,
  // а звалась она на каждую принятую точку.
  const drawLayer = new Konva.Layer({ listening: false });
  stage.add(drawLayer);

  // Слой умных направляющих (поверх всего): при перетаскивании показывает линии
  // выравнивания к соседним объектам. Разделяет трансформацию сцены (мир. коорд.).
  const guideLayer = new Konva.Layer({ listening: false });
  stage.add(guideLayer);

  function drawGrid(ctx) {
    if (boardBg === 'blank') return; // пустое полотно
    const scale = stage.scaleX();
    const x0 = -stage.x() / scale;
    const y0 = -stage.y() / scale;
    const x1 = x0 + stage.width() / scale;
    const y1 = y0 + stage.height() / scale;
    const lw = 1 / scale; // тонкие линии независимо от зума

    const GRID = gridStepFor(scale, boardBg === 'dots' ? GRID_MIN_PX_DOTS : GRID_MIN_PX);
    const startX = Math.floor(x0 / GRID) * GRID;
    const startY = Math.floor(y0 / GRID) * GRID;

    const gc = boardGridColor || '#e2e2ea'; // цвет рисунка фона
    if (boardBg === 'dots') {
      // Точки в узлах клетки.
      ctx.fillStyle = gc;
      const r = 1.1 / scale;
      for (let x = startX; x <= x1; x += GRID) {
        for (let y = startY; y <= y1; y += GRID) { ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill(); }
      }
      return;
    }
    if (boardBg === 'lines') {
      // Тетрадная линейка — только горизонтальные линии.
      ctx.beginPath(); ctx.lineWidth = lw; ctx.strokeStyle = gc;
      for (let y = startY; y <= y1; y += GRID) { ctx.moveTo(x0, y); ctx.lineTo(x1, y); }
      ctx.stroke();
      return;
    }

    // boardBg === 'grid': четыре ряда линий с разной прозрачностью. Осей нет —
    // доска не координатная. Идём от частого к редкому, чтобы сильные линии
    // ложились поверх слабых в тех же местах.
    ctx.lineWidth = lw;
    ctx.strokeStyle = gc;
    // Все линии стоят через один шаг G4. Класс определяется НОМЕРОМ линии и
    // не меняется: кратные четырём — крупные, остальные — мелкие. Меняется
    // только яркость мелких, поэтому при смене шага ничего не перерисовывается
    // заново: бывшие крупные просто становятся мелкими следующего уровня.
    const G4 = gridStep4For(scale);
    const aМелкой = gridMinorAlpha(G4 * scale);
    ctx.save();
    const классы = [
      { a: GRID_A_MAJOR, крупные: true },
      { a: aМелкой,      крупные: false },
    ];
    for (let k = 0; k < классы.length; k++) {
      const C = классы[k];
      if (C.a < 0.02) continue;                 // мелкие погасли — остался один слой
      ctx.globalAlpha = C.a;
      ctx.beginPath();
      for (let i = Math.floor(x0 / G4); i * G4 <= x1; i++) {
        if ((i % 4 === 0) !== C.крупные) continue;
        const x = i * G4; ctx.moveTo(x, y0); ctx.lineTo(x, y1);
      }
      for (let j = Math.floor(y0 / G4); j * G4 <= y1; j++) {
        if ((j % 4 === 0) !== C.крупные) continue;
        const y = j * G4; ctx.moveTo(x0, y); ctx.lineTo(x1, y);
      }
      ctx.stroke();
    }
    ctx.restore();
  }
  // Общий фон доски хранится синглтон-элементом (синхронизируется как любой
  // элемент, переживает перезагрузку). Здесь — только применение и рассылка.
  function applyBoardBgColor() { if (stageEl) stageEl.style.background = boardBgColor || ''; }
  function pushBoardCfg() {
    const el = { id: BOARD_CFG_ID, type: 'boardconfig', z: 0, data: { bg: boardBg, color: boardBgColor, gridColor: boardGridColor } };
    elements.set(el.id, el); send({ action: 'element_add', element: el });
  }
  function setBoardBg(style) { boardBg = style; redrawGrid(); pushBoardCfg(); if (typeof syncBgUI === 'function') syncBgUI(); }
  function setBoardBgColor(color) { boardBgColor = color || ''; applyBoardBgColor(); pushBoardCfg(); if (typeof syncBgUI === 'function') syncBgUI(); }
  function setBoardGridColor(color) { boardGridColor = color || ''; redrawGrid(); pushBoardCfg(); if (typeof syncBgUI === 'function') syncBgUI(); }

  // draw() (синхронно), а не batchDraw(): сетка перерисовывается только при
  // зуме/панораме/resize — это редко, зато надёжно прокрашивается и на старте
  // (batchDraw на инициализации попадал в RAF-гонку и не рисовался).
  function redrawGrid() { gridLayer.draw(); }

  // Дросселированная перерисовка вида (сетка + чужие курсоры) — не чаще раза в
  // кадр. Нужна для жестов тачпада: во время инерции wheel-события сыплются
  // очень часто, и синхронная перерисовка на каждом забивала поток, из-за чего
  // новый жест (смена направления) применялся с задержкой.
  let viewRAF = null;
  // Konva на каждую перерисовку рисует ВТОРОЙ, невидимый холст — для
  // определения попаданий. Во время панорамы и зума попадания не нужны никому,
  // а стоят они столько же, сколько видимая отрисовка. Выключаем на время
  // жеста и обязательно возвращаем: без хит-графа не работают ни выделение,
  // ни ластик, ни перетаскивание.
  let _hitPaused = false, _hitTimer = null;
  function pauseHitDuringGesture() {
    if (!_hitPaused) { _hitPaused = true; layer.hitGraphEnabled(false); }
    clearTimeout(_hitTimer);
    _hitTimer = setTimeout(() => {
      _hitPaused = false;
      layer.hitGraphEnabled(true);
      layer.batchDraw();          // хит-граф строится при следующей отрисовке
    }, 180);
  }

  // ── Отсечение невидимого ───────────────────────────────────────────────
  // Панорама перерисовывала всё содержимое, включая то, что за краем экрана:
  // 2023 объекта — 21 мс на кадр при бюджете 16.7.
  let cullingOn = true;
  const CULL_MARGIN = 200;   // запас в экранных пикселях, чтобы не «выпрыгивало»

  function setNodeShown(n) {
    if (!n || typeof n.visible !== 'function') return;
    const хочетПриложение = (n._appVisible !== false);
    const заКадром = cullingOn && n._culled === true;
    n.visible(хочетПриложение && !заКадром);
  }

  // Рамка узла в МИРОВЫХ координатах. Слои не двигаются (двигается сцена),
  // поэтому она не зависит от панорамы и зума — можно держать в кэше и не
  // пересчитывать на каждый кадр: пересчёт стоил бы дороже самой отрисовки.
  function nodeBBox(n) {
    if (n._bbox) return n._bbox;
    try { n._bbox = n.getClientRect({ relativeTo: layer, skipShadow: true }); }
    catch (e) { return null; }
    return n._bbox;
  }

  function applyCull() {
    if (!cullingOn) return;
    const s = stage.scaleX() || 1;
    const m = CULL_MARGIN / s;
    const x0 = -stage.x() / s - m, y0 = -stage.y() / s - m;
    const x1 = x0 + stage.width() / s + 2 * m, y1 = y0 + stage.height() / s + 2 * m;
    let менялось = false;
    nodes.forEach((n) => {
      const b = nodeBBox(n); if (!b) return;
      const вне = (b.x > x1 || b.y > y1 || b.x + b.width < x0 || b.y + b.height < y0);
      if (!!n._culled !== вне) { n._culled = вне; setNodeShown(n); менялось = true; }
    });
    if (менялось) layer.batchDraw();
  }

  // Показать всё и не отсекать: нужно экспорту, который двигает сцену по
  // плиткам и рисует каждую СИНХРОННО — отсечение к тому моменту отражало бы
  // предыдущий вид, и часть объектов не попала бы в файл.
  function setCulling(on) {
    cullingOn = !!on;
    if (!cullingOn) nodes.forEach((n) => { n._culled = false; setNodeShown(n); });
    else applyCull();
    layer.batchDraw();
  }

  function scheduleViewRedraw() {
    // Вид меняется — значит идёт панорама или зум. Хит-граф на это время не
    // нужен никому, а строится он на каждой перерисовке и стоит столько же,
    // сколько видимая картинка.
    pauseHitDuringGesture();
    if (viewRAF != null) return;
    viewRAF = requestAnimationFrame(() => {
      viewRAF = null;
      applyCull();
      redrawGrid();
      repositionCursors();
      positionHandles();
      renderAnchors();
    });
  }

  function syncStageSize() {
    stage.width(stageEl.clientWidth);
    stage.height(stageEl.clientHeight);
    redrawGrid();
    repositionCursors();
    if (typeof renderAnchors === 'function') renderAnchors();
  }
  window.addEventListener('resize', syncStageSize);
  // ResizeObserver срабатывает сразу, как только #board-stage получает реальный
  // размер (layout мог быть не готов на момент инициализации скрипта) — это
  // гарантирует, что сетка и размеры сцены верны с первого кадра.
  if (window.ResizeObserver) {
    new ResizeObserver(syncStageSize).observe(stageEl);
  }

  // ── Состояние редактора ───────────────────────────────────────────────
  let tool = 'pen';
  let strokeColor = '#1f2937';
  // Начальное значение. Общего ползунка толщины больше нет — как только берут
  // инструмент, applyDrawPreset подставляет толщину из его набора.
  let strokeWidth = 3;
  // Дефолты по типам: новые объекты создаются с настройками, заданными в панели
  // «для типа» (режим «все …»). Пусто = базовые значения. point: size/shape/
  // labelMode/labelSize/labelHidden; line/circle: strokeWidth/style/color.
  const typeDefaults = { point: {}, line: {}, circle: {}, polygon: {}, segment: {}, angle: {} };
  function applyTypeDefaults(data, kind) { const d = typeDefaults[kind]; for (const k in d) if (d[k] !== undefined) data[k] = d[k]; return data; }

  const nodes = new Map();    // element.id → Konva node
  const elements = new Map(); // element.id → element object (последнее состояние)
  let myId = null;            // мой user id (с сервера, из init)
  let myLabel = '';           // как меня видят соседи (ник или логин)

  function uuid() {
    return 'e' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  // ── История (шаг назад / вперёд) ───────────────────────────────────────
  const undoStack = [], redoStack = [];
  const TYPE_NAMES = { frame: 'окно', point: 'точка', segment: 'отрезок', ray: 'луч', gline: 'прямая', perp: 'перпендикуляр', parallel: 'параллель', perpbis: 'сер. перпендикуляр', bisector: 'биссектриса', circ: 'окружность', circle: 'окружность', angle: 'угол', func: 'функция', implicit: 'кривая', region: 'область', ftangent: 'касательная', farea: 'площадь', fintersect: 'пересечение', vector: 'вектор', rect: 'прямоугольник', ellipse: 'эллипс', line: 'линия', arrow: 'стрелка', freehand: 'рисунок', text: 'текст', latex: 'формула', shape: 'фигура', comment: 'комментарий', image: 'картинка', pdf: 'PDF', measure: 'измерение', polygon: 'многоугольник', regpoly: 'многоугольник', table: 'таблица', kanban: 'канбан', timer: 'таймер', wheel: 'колесо', slider: 'ползунок', sticky: 'стикер', geogebra: 'ГеоГебра' };
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function histAdd(el) { undoStack.push({ kind: 'add', el: clone(el) }); redoStack.length = 0; trimHist(); syncAlgebra(); }
  function histDel(el) { undoStack.push({ kind: 'del', el: clone(el) }); redoStack.length = 0; trimHist(); syncAlgebra(); }
  function histUpd(before, after) {
    if (JSON.stringify(before) === JSON.stringify(after)) return;
    undoStack.push({ kind: 'upd', before: clone(before), after: clone(after) }); redoStack.length = 0; trimHist();
  }
  // Пакет правок как ОДИН шаг отмены (например, стирание ластиком: удалить штрих
  // и добавить его уцелевшие куски). ops — массив обычных записей add/del/upd.
  function histBatch(ops) { if (!ops || !ops.length) return; undoStack.push({ kind: 'batch', ops: ops.map((o) => clone(o)) }); redoStack.length = 0; trimHist(); syncAlgebra(); }
  function trimHist() { if (undoStack.length > 200) undoStack.shift(); }
  function reAdd(el) { const c = clone(el); upsertNode(c); send({ action: 'element_add', element: stripPrivate(c) }); }
  function reUpd(el) { const c = clone(el); upsertNode(c); send({ action: 'element_update', element: stripPrivate(c) }); }
  function reDel(id) { removeNode(id); send({ action: 'element_delete', id }); }
  function undoOp(e) {
    if (e.kind === 'add') reDel(e.el.id);
    else if (e.kind === 'del') reAdd(e.el);
    else if (e.kind === 'upd') reUpd(e.before);
  }
  function redoOp(e) {
    if (e.kind === 'add') reAdd(e.el);
    else if (e.kind === 'del') reDel(e.el.id);
    else if (e.kind === 'upd') reUpd(e.after);
  }
  function doUndo() {
    // Во время просмотра кадров отменять нечего: история относится к
    // отложенной работе, и применять её к показанному кадру — мешать разное.
    if (typeof sbView !== 'undefined' && sbView) { boardHint('Идёт просмотр кадров — сначала «К работе» или «Оставить»'); return; }
    const e = undoStack.pop(); if (!e) return; redoStack.push(e);
    if (e.kind === 'batch') { for (let i = e.ops.length - 1; i >= 0; i--) undoOp(e.ops[i]); }
    else undoOp(e);
  }
  function doRedo() {
    if (typeof sbView !== 'undefined' && sbView) { boardHint('Идёт просмотр кадров — сначала «К работе» или «Оставить»'); return; }
    const e = redoStack.pop(); if (!e) return; undoStack.push(e);
    if (e.kind === 'batch') { e.ops.forEach(redoOp); }
    else redoOp(e);
  }

  // ── Построение / обновление узлов ─────────────────────────────────────
  function buildNode(el) {
    const d = el.data || {};
    const common = {
      id: el.id,
      x: d.x || 0,
      y: d.y || 0,
      stroke: d.stroke || '#1f2937',
      strokeWidth: d.strokeWidth || 2,
      draggable: false,
    };
    let node;
    if (el.type === 'freehand') {
      node = new Konva.Line({
        ...common,
        // Буфер под каждую фигуру Konva заводит ради аккуратных стыков
        // полупрозрачной заливки с обводкой. У штриха заливки нет — платить
        // за отдельный холст на каждый штрих не за что.
        perfectDrawEnabled: false,
        points: d.points || [0, 0],
        lineCap: 'round',
        lineJoin: 'round',
        tension: !d.marker ? 0.4 : 0,
        hitStrokeWidth: Math.max(12, common.strokeWidth + 8),
        opacity: d.marker ? (d.opacity != null ? d.opacity : 0.4) : 1,
      });
    } else if (el.type === 'line' || el.type === 'arrow') {
      // Линия/стрелка: единый рендер (прямая/кривая/уступ, наконечники, сужение).
      node = new Konva.Shape({ id: el.id, x: d.x || 0, y: d.y || 0, stroke: '#000', strokeWidth: 16, sceneFunc: drawConnector, hitFunc: hitConnector, draggable: false });
      node.getSelfRect = function () { const e = elements.get(el.id); return e ? connBounds(e.data) : { x: 0, y: 0, width: 0, height: 0 }; };
    } else if (el.type === 'rect') {
      node = new Konva.Rect({
        ...common,
        width: d.width || 0,
        height: d.height || 0,
        fill: shapeFillStyle(d, null) || undefined,
      });
    } else if (el.type === 'ellipse') {
      node = new Konva.Ellipse({
        ...common,
        radiusX: d.radiusX || 0,
        radiusY: d.radiusY || 0,
        fill: shapeFillStyle(d, null) || undefined,
      });
    } else if (el.type === 'venn') {
      // Диаграмма Венна — обычный объект холста: значит, экспорт в PDF, якоря
      // для стрелок, выравнивание и группировка достаются бесплатно.
      node = new Konva.Shape({ id: el.id, x: d.x || 0, y: d.y || 0, sceneFunc: drawVenn, draggable: false });
      node.hitFunc((ctx, sh) => {
        const e = elements.get(el.id); const dd = e ? e.data : {};
        ctx.beginPath(); ctx.rect(0, 0, dd.width || 0, dd.height || 0); ctx.closePath(); ctx.fillStrokeShape(sh);
      });
      node.getSelfRect = function () { const e = elements.get(el.id); return { x: 0, y: 0, width: (e && e.data.width) || 0, height: (e && e.data.height) || 0 }; };
    } else if (el.type === 'shape') {
      // Базовая фигура (по рамке): рисуется sceneFunc'ом; заливка для клика — в hitFunc.
      node = new Konva.Shape({ id: el.id, x: d.x || 0, y: d.y || 0, sceneFunc: drawBasicShape, fill: 'rgba(0,0,0,0.01)', draggable: false });
      node.hitFunc(hitBasicShape);
      node.getSelfRect = function () { const e = elements.get(el.id); return { x: 0, y: 0, width: (e && e.data.width) || 0, height: (e && e.data.height) || 0 }; };
    } else if (el.type === 'latex') {
      node = new Konva.Image({
        id: el.id, x: d.x || 0, y: d.y || 0,
        width: d.width || 10, height: d.height || 10,
        draggable: false, image: undefined,
      });
      node._latex = ''; // для отслеживания изменений
      renderLatexInto(node, el);
    } else if (el.type === 'text') {
      node = new Konva.Image({
        id: el.id, x: d.x || 0, y: d.y || 0,
        width: d.width || 10, height: d.height || 10,
        draggable: false, image: undefined,
      });
      node._textKey = '';
      renderTextInto(node, el);
    } else if (el.type === 'image' || el.type === 'pdf') {
      // Импортированная картинка / страница PDF — Konva.Image, картинку грузим асинхронно.
      node = new Konva.Image({ id: el.id, x: d.x || 0, y: d.y || 0, width: d.width || 10, height: d.height || 10, draggable: false, image: undefined, stroke: el.type === 'pdf' ? '#d9d9e0' : undefined, strokeWidth: el.type === 'pdf' ? 1 : 0 });
      if (el.type === 'image') loadImageInto(node, el); else renderPdfInto(node, el);
    } else if (el.type === 'point') {
      // Точка = группа: видимая точка + подпись. Крупная hit-зона для захвата.
      let px = d.x || 0, py = d.y || 0;
      if (d.frame) { const fr = elements.get(d.frame); if (fr) { const L = frameMathToLocal(fr, d.mx || 0, d.my || 0); px = L.x; py = L.y; } }
      node = new Konva.Group({ id: el.id, x: px, y: py, draggable: false });
      const glyph = new Konva.Shape({ name: 'pglyph', sceneFunc: drawPointGlyph, hitFunc: pointHitFunc });
      const _fs = labelFontOf(d);
      const _lo = d.labelOff || { x: 0, y: 0 };
      const label = new Konva.Text({ name: 'plabel', text: pointLabelText(el),
        x: 8 + (_lo.x || 0), y: -(_fs + 3) + (_lo.y || 0), fontSize: _fs, fontStyle: 'italic',
        fill: d.color || '#1f2937', visible: !d.labelHidden && !!d.frame });
      node.add(glyph); node.add(label);
      label.moveToTop(); // буква поверх кружка, чтобы её не прятал маркер точки
      node._plabel = d.label || '';
    } else if (el.type === 'circle') {
      node = new Konva.Circle({
        id: el.id, x: d.x || 0, y: d.y || 0,
        radius: d.r || 0,
        stroke: d.stroke || '#1f2937', strokeWidth: d.strokeWidth || 2,
        draggable: false, hitStrokeWidth: 14,
      });
    } else if (CONSTRUCT_LINES.indexOf(el.type) >= 0) {
      // Построение-линия: рисуется sceneFunc'ом (линия + декорации: шевроны/засечки/длина).
      node = new Konva.Shape({
        id: el.id, x: 0, y: 0, sceneFunc: drawLineShape,
        stroke: d.color || d.stroke || '#1f2937', strokeWidth: d.strokeWidth || 2,
        dash: figureDash(d.style, d.strokeWidth || 2),
        lineCap: 'round', hitStrokeWidth: 14, draggable: false,
      });
      node.getSelfRect = lineSelfRect(el);
    } else if (el.type === 'conic') {
      // Коника по 5 точкам — неявная кривая F(x,y)=0, marching-squares в коорд. окна.
      node = new Konva.Shape({ id: el.id, x: 0, y: 0, sceneFunc: drawConicShape, hitFunc: hitConicShape, stroke: d.color || d.stroke || '#c0392b', strokeWidth: d.strokeWidth || 2, hitStrokeWidth: 12, draggable: false });
    } else if (el.type === 'vector') {
      // Вектор AB — стрелка, следует за точками.
      const vc = d.color || d.stroke || '#1f2937';
      node = new Konva.Arrow({ id: el.id, x: 0, y: 0, points: vecEnds(el) || [0, 0, 0, 0], stroke: vc, fill: vc, strokeWidth: d.strokeWidth || 2, pointerLength: 11, pointerWidth: 10, lineCap: 'round', lineJoin: 'round', hitStrokeWidth: 14, draggable: false });
    } else if (el.type === 'ftangent' || el.type === 'farea' || el.type === 'fintersect' || el.type === 'region' || el.type === 'implicit' || el.type === 'xcurve') {
      // Анализ функций / неявная кривая / образ при инверсии — sceneFunc по окну;
      // живёт в группе окна.
      const sf = el.type === 'ftangent' ? drawTangent : (el.type === 'farea' ? drawArea : (el.type === 'fintersect' ? drawFIntersect : (el.type === 'region' ? drawRegion : (el.type === 'xcurve' ? drawXformCurve : drawImplicit))));
      node = new Konva.Shape({ id: el.id, x: 0, y: 0, listening: false, sceneFunc: sf,
        stroke: el.data.color || '#1f2937', strokeWidth: el.data.strokeWidth || 2 });
    } else if (isFilledPoly(el.type)) {
      // Многоугольник (обычный по вершинам / правильный n-угольник): замкнутая
      // линия с полупрозрачной заливкой; контур — shapeOutline.
      const col = d.color || d.stroke || '#1f2937';
      node = new Konva.Line({
        id: el.id, x: 0, y: 0, points: shapeOutline(el) || [], closed: true,
        stroke: col, strokeWidth: d.strokeWidth || 2, dash: figureDash(d.style, d.strokeWidth || 2),
        fill: hexToRgba(col, 0.10), lineJoin: 'round', lineCap: 'round', hitStrokeWidth: 14, draggable: false,
      });
    } else if (el.type === 'circ') {
      // Окружность/полукруг по точкам: центр и радиус — из circleGeom. Полукруг
      // рисуем sceneFunc'ом (дуга), полную — Konva.Circle (проще обновлять).
      const _dash = figureDash(d.style, d.strokeWidth || 2);
      if (d.kind === 'semi') {
        node = new Konva.Shape({ id: el.id, sceneFunc: drawSemiShape, stroke: d.color || d.stroke || '#1f2937', strokeWidth: d.strokeWidth || 2, dash: _dash, lineCap: 'round', hitStrokeWidth: 14, draggable: false });
      } else {
        const C = circleGeom(el) || { cx: 0, cy: 0, r: 0 };
        node = new Konva.Circle({ id: el.id, x: C.cx, y: C.cy, radius: C.r, stroke: d.color || d.stroke || '#1f2937', strokeWidth: d.strokeWidth || 2, dash: _dash, lineCap: 'round', draggable: false, hitStrokeWidth: 14 });
      }
    } else if (el.type === 'mark') {
      // Пометка (засечки/дуги/прямой угол/параллельность) — рисуется по опорам.
      node = new Konva.Shape({ id: el.id, listening: false, sceneFunc: drawMarkShape });
    } else if (el.type === 'measure') {
      // Подпись-измерение: белая «пилюля» с текстом; позиция считается в recomputeGeometry.
      node = new Konva.Label({ id: el.id, x: d.x || 0, y: d.y || 0, draggable: false });
      node.add(new Konva.Tag({ fill: 'rgba(255,255,255,0.9)', stroke: '#d9d9e0', strokeWidth: 1, cornerRadius: 4 }));
      node.add(new Konva.Text({ name: 'mtext', text: '', fontSize: 13, padding: 4, fill: d.color || '#1f2937' }));
    } else if (el.type === 'angle') {
      node = new Konva.Shape({ id: el.id, listening: false, sceneFunc: drawAngleShape });
    } else if (el.type === 'frame') {
      // Математическое окно: своя система координат (cx,cy,unit), оси/сетка,
      // отсечение содержимого по прямоугольнику.
      const W = d.width || 0, H = d.height || 0;
      node = new Konva.Group({ id: el.id, x: d.x || 0, y: d.y || 0, draggable: false,
        clipX: 0, clipY: 0, clipWidth: W, clipHeight: H });
      node.add(new Konva.Rect({ name: 'fbg', x: 0, y: 0, width: W, height: H, fill: d.bgColor || '#ffffff', stroke: '#d9d9e0', strokeWidth: 1 }));
      node.add(new Konva.Shape({ name: 'fgrid', sceneFunc: (ctx) => drawFrameGrid(ctx, elements.get(el.id)) }));
      // Невидимая полоса-ручка сверху: за неё окно двигают, и она — Z-якорь,
      // под который кладётся вся геометрия окна. Серой заливки больше нет
      // (график заполняет всё окно), полоса ничего не закрывает. Заливка
      // прозрачная, но НЕ пустая: без fill Konva не считает прямоугольник
      // закрашенным и не ловит по нему нажатие.
      node.add(new Konva.Rect({ name: 'fheader', x: 0, y: 0, width: W, height: FRAME_GRAB, fill: 'rgba(0,0,0,0)' }));
      node.add(new Konva.Text({ name: 'fdel', text: '×', x: W - 16, y: 3, fontSize: 16, fill: '#9a9aa4', opacity: 0 }));
      attachFrameHandlers(node, el.id);
    } else {
      return null;
    }
    // Hit-зона на всю площадь объекта. Иначе по незакрашенным фигурам и по
    // прозрачным местам формулы/текста (картинка почти пустая) клик промахивается.
    if (el.type === 'rect' || el.type === 'latex' || el.type === 'text') {
      node.hitFunc((ctx, shape) => {
        ctx.beginPath();
        ctx.rect(0, 0, shape.width(), shape.height());
        ctx.closePath();
        ctx.fillStrokeShape(shape);
      });
    } else if (el.type === 'ellipse') {
      node.hitFunc((ctx, shape) => {
        ctx.beginPath();
        ctx.ellipse(0, 0, shape.radiusX(), shape.radiusY(), 0, 0, Math.PI * 2);
        ctx.closePath();
        ctx.fillStrokeShape(shape);
      });
    }
    if (el.type === 'point' || el.type === 'circle') {
      node.on('dragmove', () => onGeoDragMove(el.id, node));
      node.on('dragend', () => onGeoDragEnd(el.id, node));
    } else if (el.type === 'measure') {
      node.on('dragmove', () => moveDragFollowers(el.id, node)); // не замораживать группу, если тащат за измерение
      node.on('dragend', () => onMeasureDragEnd(el.id, node));
    } else {
      node.on('dragmove', () => onNodeDragMove(el.id, node));
      node.on('dragend', () => onNodeDragEnd(el.id, node));
    }
    return node;
  }

  // ── Линии и стрелки: единый рендер ─────────────────────────────────────
  // Точки в data.points относительны data.x/y. Кривизну задают ПУТЕВЫЕ ТОЧКИ,
  // через которые кривая ПРОХОДИТ (лежат НА ней → влияют локально и независимо):
  // data.wl (левая), data.wm (центр), data.wr (правая) — относит. data.x/y. Кривая —
  // центростремительный сплайн Catmull-Rom через [A, wl?, wm?, wr?, B] (гладкий,
  // не «деревянный»). elbow — уступ (L), taper — сужение. Наконечники: startCap/endCap.
  // Старое data.c1/c2 (кубика) и data.ctrl (квадратичная вершина) читаем для миграции.
  function connEnds(d) { const p = d.points || [0, 0, 0, 0]; return { A: { x: p[0], y: p[1] }, B: { x: p[2], y: p[3] } }; }
  function bezPoint(A, C1, C2, B, t) { const u = 1 - t; return { x: u * u * u * A.x + 3 * u * u * t * C1.x + 3 * u * t * t * C2.x + t * t * t * B.x, y: u * u * u * A.y + 3 * u * u * t * C1.y + 3 * u * t * t * C2.y + t * t * t * B.y }; }
  // Список точек, через которые проходит кривая: [A, (путевые точки), B].
  function connWaypoints(d) {
    const e = connEnds(d), A = e.A, B = e.B, P = (a) => ({ x: a[0], y: a[1] }), list = [A];
    if (d.wl || d.wm || d.wr) {
      if (d.wl) list.push(P(d.wl)); if (d.wm) list.push(P(d.wm)); if (d.wr) list.push(P(d.wr));
    } else if (d.c1 && d.c2) { // миграция старой кубики → 3 точки на ней
      const C1 = P(d.c1), C2 = P(d.c2);
      list.push(bezPoint(A, C1, C2, B, 0.25), bezPoint(A, C1, C2, B, 0.5), bezPoint(A, C1, C2, B, 0.75));
    } else if (d.ctrl && d.ctrl.length === 2) { // миграция квадратичной вершины → центр кривой
      const Q = P(d.ctrl); list.push({ x: 0.25 * A.x + 0.5 * Q.x + 0.25 * B.x, y: 0.25 * A.y + 0.5 * Q.y + 0.25 * B.y });
    }
    list.push(B);
    return list;
  }
  // Кривая, если хоть одна путевая точка заметно отходит от хорды AB.
  function connIsCurved(d) {
    const wp = connWaypoints(d); if (wp.length <= 2) return false;
    const A = wp[0], B = wp[wp.length - 1], vx = B.x - A.x, vy = B.y - A.y, L2 = vx * vx + vy * vy || 1;
    const dev = (Pt) => { const t = ((Pt.x - A.x) * vx + (Pt.y - A.y) * vy) / L2, px = A.x + t * vx, py = A.y + t * vy; return Math.hypot(Pt.x - px, Pt.y - py); };
    for (let i = 1; i < wp.length - 1; i++) if (dev(wp[i]) > 1.5) return true;
    return false;
  }
  // НАТУРАЛЬНЫЙ КУБИЧЕСКИЙ СПЛАЙН через точки P → гладкая ломаная. C²-непрерывен
  // (кривизна без скачков → нет «виляния» между узлами, в отличие от Catmull-Rom).
  // Параметр — центростремительная длина (^0.5) — меньше выбросов на неравных
  // промежутках. Натуральные краевые условия (2-я производная=0) → концы «расслаблены».
  function naturalSpline(P, seg) {
    const n = P.length; if (n <= 2) return P.slice();
    seg = seg || 16;
    const t = [0];
    for (let i = 1; i < n; i++) t.push(t[i - 1] + Math.max(1e-3, Math.pow(Math.hypot(P[i].x - P[i - 1].x, P[i].y - P[i - 1].y), 0.5)));
    const h = []; for (let i = 0; i < n - 1; i++) h.push(t[i + 1] - t[i]);
    // Вторые производные M сплайна для одной координаты (трёхдиагональная прогонка).
    function solveM(y) {
      const M = new Array(n).fill(0);
      if (n < 3) return M;
      const b = new Array(n).fill(0), c = new Array(n).fill(0), d = new Array(n).fill(0);
      for (let i = 1; i < n - 1; i++) { b[i] = 2 * (h[i - 1] + h[i]); c[i] = h[i]; d[i] = 6 * ((y[i + 1] - y[i]) / h[i] - (y[i] - y[i - 1]) / h[i - 1]); }
      for (let i = 2; i < n - 1; i++) { const w = h[i - 1] / b[i - 1]; b[i] -= w * c[i - 1]; d[i] -= w * d[i - 1]; }
      for (let i = n - 2; i >= 1; i--) M[i] = (d[i] - c[i] * M[i + 1]) / b[i];
      return M;
    }
    const xs = P.map((p) => p.x), ys = P.map((p) => p.y), Mx = solveM(xs), My = solveM(ys);
    const pts = [P[0]];
    for (let i = 0; i < n - 1; i++) {
      for (let s = 1; s <= seg; s++) {
        const tt = t[i] + h[i] * (s / seg), a = (t[i + 1] - tt) / h[i], b = (tt - t[i]) / h[i];
        const ev = (y, M) => a * y[i] + b * y[i + 1] + ((a * a * a - a) * M[i] + (b * b * b - b) * M[i + 1]) * h[i] * h[i] / 6;
        pts.push({ x: ev(xs, Mx), y: ev(ys, My) });
      }
    }
    return pts;
  }
  // Ортогональный маршрут «уступа»: A→B тремя сегментами (Z-шаг). elbowT∈[0,1] —
  // доля, где происходит поворот вдоль ГЛАВНОЙ оси (по большей разнице координат).
  // t=0 и t=1 вырождают Z в L, 0.5 — симметричный шаг. Совпавшие точки убираем.
  function elbowRoute(d) {
    const e = connEnds(d), A = e.A, B = e.B, dx = B.x - A.x, dy = B.y - A.y;
    const horiz = Math.abs(dx) >= Math.abs(dy);
    let t = (d.elbowT == null ? 0.5 : d.elbowT);
    // Если излом подводят вплотную к концу, «схлопываем» Z в чистую Г-образную линию
    // (короткий сегмент у наконечника → он бы ломался; вместо этого наконечник повернётся).
    const mainLen = Math.abs(horiz ? dx : dy);
    if (mainLen > 0) { const frac = Math.min(0.45, (connArrowLen(d.strokeWidth || 2) + 6) / mainLen); if (t < frac) t = 0; else if (t > 1 - frac) t = 1; }
    let pts;
    if (horiz) { const sx = A.x + dx * t; pts = [A, { x: sx, y: A.y }, { x: sx, y: B.y }, B]; }
    else { const sy = A.y + dy * t; pts = [A, { x: A.x, y: sy }, { x: B.x, y: sy }, B]; }
    const out = [pts[0]];
    for (let i = 1; i < pts.length; i++) if (Math.hypot(pts[i].x - out[out.length - 1].x, pts[i].y - out[out.length - 1].y) > 0.01) out.push(pts[i]);
    return out;
  }
  // Середина среднего сегмента уступа — там сидит ручка излома.
  function elbowMidHandle(d) {
    const rt = elbowRoute(d);
    if (rt.length >= 4) return { x: (rt[1].x + rt[2].x) / 2, y: (rt[1].y + rt[2].y) / 2 };
    if (rt.length === 3) return rt[1];
    return { x: (rt[0].x + rt[rt.length - 1].x) / 2, y: (rt[0].y + rt[rt.length - 1].y) / 2 };
  }
  // Скруглить углы ломаной дугами радиуса r (квадратичная в каждом углу).
  function roundCorners(pts, r) {
    if (pts.length < 3 || r <= 0) return pts;
    const out = [pts[0]];
    for (let i = 1; i < pts.length - 1; i++) {
      const p0 = pts[i - 1], p1 = pts[i], p2 = pts[i + 1];
      const d1 = Math.hypot(p0.x - p1.x, p0.y - p1.y) || 1, d2 = Math.hypot(p2.x - p1.x, p2.y - p1.y) || 1;
      const rr = Math.min(r, d1 / 2, d2 / 2);
      const a = { x: p1.x + (p0.x - p1.x) / d1 * rr, y: p1.y + (p0.y - p1.y) / d1 * rr };
      const b = { x: p1.x + (p2.x - p1.x) / d2 * rr, y: p1.y + (p2.y - p1.y) / d2 * rr };
      out.push(a);
      for (let s = 1; s <= 6; s++) { const t = s / 7, u = 1 - t; out.push({ x: u * u * a.x + 2 * u * t * p1.x + t * t * b.x, y: u * u * a.y + 2 * u * t * p1.y + t * t * b.y }); }
      out.push(b);
    }
    out.push(pts[pts.length - 1]);
    return out;
  }
  function connSample(d) {
    const e = connEnds(d);
    if (d.elbow) return roundCorners(elbowRoute(d), 16);
    if (connIsCurved(d)) return naturalSpline(connWaypoints(d), 16);
    return [e.A, e.B];
  }
  // Точка на кривой по доле длины дуги f∈[0,1] (для размещения ручки на кривой).
  function connPointAtFraction(d, f) {
    const pts = connSample(d); if (pts.length < 2) return pts[0] || { x: 0, y: 0 };
    let total = 0; const segL = [];
    for (let i = 1; i < pts.length; i++) { const L = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); segL.push(L); total += L; }
    let target = f * total, acc = 0;
    for (let i = 0; i < segL.length; i++) { if (acc + segL[i] >= target) { const t = (target - acc) / (segL[i] || 1); return { x: pts[i].x + (pts[i + 1].x - pts[i].x) * t, y: pts[i].y + (pts[i + 1].y - pts[i].y) * t }; } acc += segL[i]; }
    return pts[pts.length - 1];
  }
  // Перевести старую кривизну (c1/c2 или ctrl) в путевые слоты wl/wm/wr (один раз).
  function connMigrateCurve(d) {
    if (d.wl || d.wm || d.wr) { delete d.c1; delete d.c2; delete d.ctrl; return; }
    if ((d.c1 && d.c2) || d.ctrl) {
      const wp = connWaypoints(d); // [A, ...точки, B]
      if (wp.length === 5) { d.wl = [wp[1].x, wp[1].y]; d.wm = [wp[2].x, wp[2].y]; d.wr = [wp[3].x, wp[3].y]; }
      else if (wp.length === 3) { d.wm = [wp[1].x, wp[1].y]; }
    }
    delete d.c1; delete d.c2; delete d.ctrl;
  }
  function connBounds(d) {
    const pts = connSample(d); let a = Infinity, b = Infinity, c = -Infinity, e = -Infinity;
    pts.forEach((p) => { a = Math.min(a, p.x); b = Math.min(b, p.y); c = Math.max(c, p.x); e = Math.max(e, p.y); });
    const pad = (d.strokeWidth || 2) + 8; return { x: a - pad, y: b - pad, width: (c - a) + 2 * pad, height: (e - b) + 2 * pad };
  }
  function connTangent(p0, p1) { const dx = p1.x - p0.x, dy = p1.y - p0.y, L = Math.hypot(dx, dy) || 1; return { x: dx / L, y: dy / L }; }
  // Длина наконечника-стрелки в пикселях (растёт с толщиной).
  function connArrowLen(sw) { return Math.max(9, sw * 2.6); }
  // Путевая точка-центр по умолчанию для кнопки «кривая»: середина AB, сдвинутая
  // по нормали (заметный, но не резкий изгиб). Возвращает [x,y] (относит.).
  function connDefaultCurve(d) {
    const e = connEnds(d), A = e.A, B = e.B, mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
    const dx = B.x - A.x, dy = B.y - A.y, L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L, off = Math.max(30, L * 0.22);
    return [mx + nx * off, my + ny * off];
  }
  // Обрезать ломаную на dist пикселей с конца / с начала (по длине дуги) — чтобы
  // ствол упирался в ОСНОВАНИЕ наконечника, а не торчал из его острия.
  function connTrimEnd(pts, dist) {
    if (dist <= 0 || pts.length < 2) return pts.slice();
    let rem = dist;
    for (let i = pts.length - 1; i > 0; i--) {
      const p = pts[i], q = pts[i - 1], seg = Math.hypot(q.x - p.x, q.y - p.y);
      if (seg >= rem) { const t = rem / seg; return pts.slice(0, i).concat([{ x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t }]); }
      rem -= seg;
    }
    return [pts[0]];
  }
  function connTrimStart(pts, dist) {
    if (dist <= 0 || pts.length < 2) return pts.slice();
    let rem = dist;
    for (let i = 0; i < pts.length - 1; i++) {
      const p = pts[i], q = pts[i + 1], seg = Math.hypot(q.x - p.x, q.y - p.y);
      if (seg >= rem) { const t = rem / seg; return [{ x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t }].concat(pts.slice(i + 1)); }
      rem -= seg;
    }
    return [pts[pts.length - 1]];
  }
  // Насколько укоротить ствол под наконечником (чтобы торец прятался под фигурой).
  function capTrim(cap, sw) {
    if (cap === 'arrow' || cap === 'triangle_open') return connArrowLen(sw) * 0.9;
    if (cap === 'diamond' || cap === 'diamond_open') return connArrowLen(sw);
    return 0;
  }
  function drawConnCap(ctx, cap, at, dir, sw, col) {
    if (!cap || cap === 'none') return;
    const nx = -dir.y, ny = dir.x, thin = Math.max(1.5, sw * 0.7);
    if (cap === 'dot' || cap === 'circle_open') {
      const rad = Math.max(3, sw * 0.9 + 1.5); ctx.beginPath(); ctx.arc(at.x, at.y, rad, 0, 2 * Math.PI);
      if (cap === 'dot') { ctx.fillStyle = col; ctx.fill(); } else { ctx.strokeStyle = col; ctx.lineWidth = thin; ctx.stroke(); }
      return;
    }
    if (cap === 'bar') {
      const half = Math.max(5, sw * 1.7); ctx.beginPath(); ctx.strokeStyle = col; ctx.lineWidth = Math.max(2, sw); ctx.lineCap = 'round';
      ctx.moveTo(at.x + nx * half, at.y + ny * half); ctx.lineTo(at.x - nx * half, at.y - ny * half); ctx.stroke(); return;
    }
    const len = connArrowLen(sw), wid = Math.max(7, sw * 2.2);
    const bx = at.x - dir.x * len, by = at.y - dir.y * len; // центр основания
    if (cap === 'arrow' || cap === 'triangle_open') {
      ctx.beginPath(); ctx.moveTo(at.x, at.y); ctx.lineTo(bx + nx * wid / 2, by + ny * wid / 2); ctx.lineTo(bx - nx * wid / 2, by - ny * wid / 2); ctx.closePath();
      if (cap === 'arrow') { ctx.fillStyle = col; ctx.fill(); } else { ctx.strokeStyle = col; ctx.lineWidth = thin; ctx.lineJoin = 'round'; ctx.stroke(); }
      return;
    }
    if (cap === 'arrow_open') {
      ctx.beginPath(); ctx.strokeStyle = col; ctx.lineWidth = Math.max(2, sw); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.moveTo(bx + nx * wid / 2, by + ny * wid / 2); ctx.lineTo(at.x, at.y); ctx.lineTo(bx - nx * wid / 2, by - ny * wid / 2); ctx.stroke(); return;
    }
    if (cap === 'diamond' || cap === 'diamond_open') {
      const mx = at.x - dir.x * len * 0.5, my = at.y - dir.y * len * 0.5, w = wid * 0.62;
      ctx.beginPath(); ctx.moveTo(at.x, at.y); ctx.lineTo(mx + nx * w, my + ny * w); ctx.lineTo(bx, by); ctx.lineTo(mx - nx * w, my - ny * w); ctx.closePath();
      if (cap === 'diamond') { ctx.fillStyle = col; ctx.fill(); } else { ctx.strokeStyle = col; ctx.lineWidth = thin; ctx.lineJoin = 'round'; ctx.stroke(); }
      return;
    }
  }
  function drawConnector(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const d = el.data, ends = connEnds(d), A = ends.A, B = ends.B, col = d.stroke || '#1f2937', sw = d.strokeWidth || 2, full = connSample(d);
    ctx.save(); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    // СУЖЕНИЕ — самостоятельный тип: ПРЯМАЯ линия, сильно жирнеющая к концу (от
    // острия до толщины sw). Клин со straight-краями; без наконечников/обрезки.
    if (d.taper) {
      const N = 24, w0 = 0.6, tg = connTangent(A, B), nx = -tg.y, ny = tg.x, left = [], right = [];
      for (let i = 0; i <= N; i++) {
        const t = i / N, p = { x: A.x + (B.x - A.x) * t, y: A.y + (B.y - A.y) * t };
        const half = (w0 + (sw - w0) * Math.pow(t, 1.8)) / 2; // pow>1: тонкая большую часть, резкий разжир у конца
        left.push({ x: p.x + nx * half, y: p.y + ny * half }); right.push({ x: p.x - nx * half, y: p.y - ny * half });
      }
      ctx.beginPath(); ctx.moveTo(left[0].x, left[0].y);
      for (let i = 1; i < left.length; i++) ctx.lineTo(left[i].x, left[i].y);
      for (let i = right.length - 1; i >= 0; i--) ctx.lineTo(right[i].x, right[i].y);
      ctx.closePath(); ctx.fillStyle = col; ctx.fill(); ctx.restore(); return;
    }
    // Ствол укорачиваем до основания наконечника (чуть меньше, чтобы перекрытие
    // спряталось под треугольником): цельная стрелка без торчащего торца.
    let body = full;
    const trimE = capTrim(d.endCap, sw), trimS = capTrim(d.startCap, sw);
    if (trimE > 0) body = connTrimEnd(body, trimE);
    if (trimS > 0) body = connTrimStart(body, trimS);
    if (body.length >= 2) {
      ctx.beginPath(); ctx.moveTo(body[0].x, body[0].y);
      for (let i = 1; i < body.length; i++) ctx.lineTo(body[i].x, body[i].y);
      ctx.strokeStyle = col; ctx.lineWidth = sw; ctx.stroke();
    }
    // Наконечники — по ИСХОДНЫМ концам, направление по касательной исходной ломаной.
    drawConnCap(ctx, d.endCap, B, connTangent(full[full.length - 2], full[full.length - 1]), sw, col);
    drawConnCap(ctx, d.startCap, A, connTangent(full[1], full[0]), sw, col);
    ctx.restore();
  }
  function hitConnector(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const pts = connSample(el.data); ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.strokeShape(shape);
  }

  function upsertNode(el) {
    if (el.type === 'boardconfig') { elements.set(el.id, el); boardBg = (el.data && el.data.bg) || 'grid'; boardBgColor = (el.data && el.data.color) || ''; boardGridColor = (el.data && el.data.gridColor) || ''; applyBoardBgColor(); redrawGrid(); if (typeof syncBgUI === 'function') syncBgUI(); return; }
    if (el.type === 'geogebra') { elements.set(el.id, el); upsertGGB(el); return; }
    if (el.type === 'func') { elements.set(el.id, el); upsertFuncNode(el); return; }
    if (WIDGET_TYPES.indexOf(el.type) >= 0) { elements.set(el.id, el); upsertWidget(el); return; }
    if (el.type === 'textbox') { elements.set(el.id, el); upsertTextbox(el); return; }
    if (el.type === 'text') { elements.set(el.id, el); upsertMathText(el); return; }
    elements.set(el.id, el);
    let node = nodes.get(el.id);
    if (!node) {
      node = buildNode(el);
      if (!node) return;
      nodes.set(el.id, node);
      // Привязанная к окну геометрия — в группу окна (обрезается её clip);
      // иначе на общий слой. Если окно ещё не загружено — позже reattach.
      // Активный штрих — в лёгкий слой: пока его ведут, тяжёлый не трогаем.
      if (drawing && el.id === drawing.id && !(el.data && el.data.frame)) drawLayer.add(node);
      else if (!(el.data && el.data.frame && el.type !== 'measure' && attachToFrame(el, node))) layer.add(node);
    } else {
      const d = el.data || {};
      node.position({ x: d.x || 0, y: d.y || 0 });
      if (el.type === 'point') {
        // у группы-точки нет stroke(); обновляем только позицию и подпись
        if (node._plabel !== (d.label || '')) {
          const t = node.findOne('.plabel'); if (t) t.text(d.label || '');
          node._plabel = d.label || '';
        }
      } else if (el.type === 'circle') {
        node.radius(d.r || 0);
        node.stroke(d.stroke || '#1f2937');
        node.strokeWidth(d.strokeWidth || 2);
      } else if (el.type === 'frame') {
        const W = d.width || 0, H = d.height || 0;
        node.clipWidth(W); node.clipHeight(H);
        const bg = node.findOne('.fbg'); if (bg) { bg.size({ width: W, height: H }); bg.fill(d.bgColor || '#ffffff'); }
        const hd = node.findOne('.fheader'); if (hd) hd.width(W);
        const del = node.findOne('.fdel'); if (del) del.x(W - 16);
        // сетка/оси берут актуальные данные из elements при перерисовке
      } else if (el.type === 'line' || el.type === 'arrow') {
        // Кастомный Shape: sceneFunc берёт данные из elements; широкую hit-зону не трогаем.
      } else {
        // Картинка, PDF, формула и текст — это Konva.Image, и при СОЗДАНИИ им
        // обводка не назначается (у PDF своя, светло-серая в один пиксель).
        // Раньше все они попадали в общее правило ниже и при первом же
        // обновлении получали почти чёрную рамку в три пикселя. У себя это не
        // было видно: сервер не шлёт эхо отправителю, поэтому рамку получал
        // ТОЛЬКО второй участник — тот, кто картинку не трогал.
        const безОбводки = (el.type === 'image' || el.type === 'pdf'
          || el.type === 'latex' || el.type === 'text');
        if (безОбводки) {
          node.stroke(el.type === 'pdf' ? '#d9d9e0' : undefined);
          node.strokeWidth(el.type === 'pdf' ? 1 : 0);
        } else {
          node.stroke(d.stroke || '#1f2937');
          node.strokeWidth(d.strokeWidth || 2);
        }
        if (node.getClassName() === 'Line') node.points(d.points || [0, 0]);
        if (el.type === 'venn') { d._labSig = null; }
        if (el.type === 'rect') { node.width(d.width || 0); node.height(d.height || 0); node.fill(shapeFillStyle(d, null)); }
        if (el.type === 'ellipse') { node.radiusX(d.radiusX || 0); node.radiusY(d.radiusY || 0); node.fill(shapeFillStyle(d, null)); }
        if (el.type === 'image') { if (d.width) node.width(d.width); if (d.height) node.height(d.height); loadImageInto(node, el); applyCrop(node, el); }
        if (el.type === 'pdf') { if (d.width) node.width(d.width); if (d.height) node.height(d.height); renderPdfInto(node, el); }
        if (el.type === 'latex') {
          if (d.width) node.width(d.width);
          if (d.height) node.height(d.height);
          if (node._latex !== (d.latex || '') + '|' + (d.color || '')) renderLatexInto(node, el);
        }
        if (el.type === 'text') {
          if (d.width) node.width(d.width);
          if (d.height) node.height(d.height);
          if (node._textKey !== textKey(d)) renderTextInto(node, el);
        }
      }
    }
    node.draggable(tool === 'select' && !viewOnly && el.type !== 'frame' && !isPointBound(el) && !el.data.locked); // рамку, геометрию по точкам и закреплённые не таскаем; в режиме просмотра — ничего
    if (el.type === 'point' || el.type === 'circle' || el.type === 'circ' || isFilledPoly(el.type) || isConstruction(el.type)) recomputeGeometry();
    if (el.type === 'frame') reattachFuncs(); // привязать функции, ждавшие своё окно
    applyElVisibility(el); // учесть флаг data.hidden
    if (el.type === 'point' && el.data.trace) ensureTrace(el); // включить след, если помечен
    if (el.type === 'rect' || el.type === 'ellipse' || el.type === 'shape') syncShapeText(el); // текст внутри фигуры
    // Объект мог сдвинуть или изменить ДРУГОЙ участник — якоря у выделенного
    // должны переехать и в этом случае (а ещё при отмене и повторе действия).
    // Объект изменился — прежняя рамка больше не годится для отсечения.
    if (node) { node._bbox = null; node._culled = false; }
    if (typeof renderAnchors === 'function' && selected.has(el.id)) renderAnchors();
    // Во время рисования трогаем только лёгкий слой. Разница не косметическая:
    // без этого стоимость каждой точки росла вместе с числом чужих объектов.
    if (drawing && el.id === drawing.id && node.getLayer() === drawLayer) drawLayer.batchDraw();
    else layer.batchDraw();
  }

  // Погасить отложенную отправку для объекта. Зовём при удалении: иначе
  // сработавший позже таймер создаст объект заново.
  function cancelPendingSync(id) {
    if (typeof tboxSyncTimers !== 'undefined' && tboxSyncTimers[id]) {
      clearTimeout(tboxSyncTimers[id]); delete tboxSyncTimers[id];
    }
    if (typeof frameSyncTimers !== 'undefined' && frameSyncTimers[id]) {
      clearTimeout(frameSyncTimers[id]); delete frameSyncTimers[id];
    }
  }
  function removeNode(id) {
    cancelPendingSync(id);
    if (shapeTextItems.has(id)) removeShapeText(id);
    if (ggbItems.has(id)) { removeGGB(id); elements.delete(id); return; }
    if (widgetItems.has(id)) { removeWidget(id); return; }
    const tl = traceLines.get(id); if (tl) { tl.destroy(); traceLines.delete(id); } // убрать след
    const node = nodes.get(id);
    if (node) { node.destroy(); nodes.delete(id); }
    elements.delete(id);
    if (selected.has(id)) { selected.delete(id); refreshTransformer(); }
    layer.batchDraw();
  }

  // ── Зависимости при удалении ───────────────────────────────────────────
  // Элементы, ПРЯМО ссылающиеся на id (опорные точки построений/окружностей,
  // точки на линии/окружности/в пересечении, вся геометрия внутри окна).
  function directDependents(id) {
    const res = [];
    elements.forEach((el) => {
      const d = el.data; if (!d || el.id === id) return;
      let refs = (d.a === id || d.b === id || d.c === id || d.center === id || d.through === id || d.line === id || d.frame === id || d.vertex === id || d.func === id || d.f === id || d.g === id);
      if (!refs && d.parts && d.parts.some((p) => p.func === id)) refs = true; // условие области ссылается на график
      if (!refs && d.pts && d.pts.indexOf(id) >= 0) refs = true; // вершина многоугольника
      if (!refs && ((d.from && d.from.id === id) || (d.to && d.to.id === id))) refs = true; // стрелка, привязанная к объекту
      if (!refs && d.refs && d.refs.indexOf(id) >= 0) refs = true; // опора измерения
      if (!refs && d.on) {
        const o = d.on;
        if (o.line === id || o.c === id || o.circle === id || o.regpoly === id) refs = true;
        else if (o.isect && (o.isect[0] === id || o.isect[1] === id)) refs = true;
        else if (o.centroid && o.centroid.indexOf(id) >= 0) refs = true;
        else if (o.ratio && (o.ratio.a === id || o.ratio.b === id)) refs = true;
        else if (o.xform && (o.src === id || o.xform.c === id || o.xform.a === id || o.xform.b === id || o.xform.line === id || o.xform.through === id)) refs = true;
      }
      if (refs) res.push(el.id);
    });
    return res;
  }
  // Транзитивное замыкание зависимостей, упорядоченное «зависимые раньше основы»
  // (для корректной истории: undo восстановит основу первой).
  function withDependents(rootIds) {
    const layer = new Map(), queue = [];
    rootIds.forEach((id) => { if (elements.has(id) && !layer.has(id)) { layer.set(id, 0); queue.push(id); } });
    for (let qi = 0; qi < queue.length; qi++) {
      const cur = queue[qi], L = layer.get(cur);
      directDependents(cur).forEach((dep) => {
        if (!layer.has(dep) || layer.get(dep) <= L) { layer.set(dep, L + 1); queue.push(dep); }
      });
    }
    return Array.from(layer.keys()).sort((a, b) => layer.get(b) - layer.get(a)); // глубже — раньше
  }
  // Удалить элементы вместе со всем, что от них зависит.
  function deleteWithDependents(ids) {
    withDependents(ids).forEach((id) => {
      const el = elements.get(id); if (!el) return;
      histDel(el); send({ action: 'element_delete', id }); removeNode(id);
    });
  }

  // Перетаскивание нескольких выбранных объектов вместе (в т.ч. группы).
  // Стартовые позиции фиксируем на mousedown (captureDragStart ниже), ДО того
  // как Konva начнёт двигать узел, — иначе ведомые отстают на первый шаг мыши.
  let dragStart = null;
  let dragSnap = null; // снимки «до» для истории

  function captureDragSnap(ids) {
    if (dragSnap) return;
    dragSnap = ids.map((i) => elements.get(i)).filter(Boolean).map(clone);
  }
  function commitDragSnap() {
    if (!dragSnap) return;
    dragSnap.forEach((b) => { const cur = elements.get(b.id); if (cur) histUpd(b, cur); });
    dragSnap = null;
  }

  // ── Умные направляющие (как в Miro): при перетаскивании выравниваем края/центры
  // объекта к соседям (матокна, PDF, картинки, фигуры, таблицы) с прилипанием.
  let guideRefs = null; // боксы соседей {x,y,w,h}, снятые один раз за перетаскивание
  // Текста и формулы здесь намеренно НЕТ. Выравнивание по краю осмысленно у
  // блоков с границами — картинка, окно, фигура. У текста границы нет, есть
  // строки: выравниваться не по чему, а запись, которую ведут под текстом,
  // прыгала вверх по его краю и налезала сверху. Сам текст к другим объектам
  // по-прежнему притягивается — он тут в роли перетаскиваемого, а не соседа.
  // Текст и формулу вернули в опоры выравнивания: владелец просил, чтобы текст
  // тоже равнялся и чтобы направляющие между текстом и картинкой были видны.
  // Убирали их из-за того, что нижестоящие записи липли верхом к низу текста —
  // а такого сравнения после перехода на одноимённые края больше нет.
  const SNAP_BOX_TYPES = { frame: 1, image: 1, pdf: 1, shape: 1, rect: 1, ellipse: 1, text: 1, latex: 1 };
  function boxOfElem(el, id) {
    if (!el) return null;
    if (el.type === 'frame') return { x: el.data.x || 0, y: el.data.y || 0, w: el.data.width || 0, h: el.data.height || 0 };
    const n = nodes.get(id); if (!n || typeof n.getClientRect !== 'function') return null;
    const b = n.getClientRect({ relativeTo: layer });
    return (b && b.width && b.height) ? { x: b.x, y: b.y, w: b.width, h: b.height } : null;
  }
  let guidesEnabled = true; // тумблер «Направляющие (выравнивание)» в меню доски
  function collectGuideRefs(excludeIds) {
    if (!guidesEnabled) return []; // направляющие выключены — снапа нет
    const ex = new Set(excludeIds), refs = [];
    elements.forEach((el, id) => {
      if (ex.has(id) || (el.data && el.data.hidden && !revealHidden) || !SNAP_BOX_TYPES[el.type]) return;
      const b = boxOfElem(el, id); if (b) refs.push(b);
    });
    widgetItems.forEach((it, id) => {
      if (ex.has(id)) return;
      const d = it.el.data, w = it.wrapper.offsetWidth, h = it.wrapper.offsetHeight;
      if (w && h) refs.push({ x: d.x || 0, y: d.y || 0, w: w, h: h });
    });
    return refs;
  }
  function computeSnap(box) {
    if (!guideRefs || !guideRefs.length) return { dx: 0, dy: 0, lines: [] };
    const th = 7 / stage.scaleX();
    const dX = [box.x, box.x + box.w / 2, box.x + box.w], dY = [box.y, box.y + box.h / 2, box.y + box.h];
    let bV = null, bH = null;
    guideRefs.forEach((r) => {
      const rX = [r.x, r.x + r.w / 2, r.x + r.w], rY = [r.y, r.y + r.h / 2, r.y + r.h];
      // ОДНОИМЁННЫЕ края: лево↔лево, центр↔центр, право↔право; верх↔верх,
      // середина↔середина, низ↔низ. Раньше сравнивался каждый с каждым, и
      // объект, который кладут ПОД картинку, притягивался верхом к её низу —
      // «вещи снизу картинки прилипают». Выравнивание — это про одноимённые
      // края, а притяжение к противоположному только мешает.
      for (let i = 0; i < 3; i++) {
        const adx = Math.abs(rX[i] - dX[i]);
        if (adx <= th && (!bV || adx < bV.ad)) bV = { ad: adx, diff: rX[i] - dX[i], at: rX[i] };
        const ady = Math.abs(rY[i] - dY[i]);
        if (ady <= th && (!bH || ady < bH.ad)) bH = { ad: ady, diff: rY[i] - dY[i], at: rY[i] };
      }
    });
    const dx = bV ? bV.diff : 0, dy = bH ? bH.diff : 0, sb = { x: box.x + dx, y: box.y + dy, w: box.w, h: box.h };
    const lines = [];
    if (bV) { let a = sb.y, b = sb.y + sb.h; guideRefs.forEach((r) => { if ([r.x, r.x + r.w / 2, r.x + r.w].some((v) => Math.abs(v - bV.at) < 0.5)) { a = Math.min(a, r.y); b = Math.max(b, r.y + r.h); } }); lines.push({ v: true, at: bV.at, a: a, b: b }); }
    if (bH) { let a = sb.x, b = sb.x + sb.w; guideRefs.forEach((r) => { if ([r.y, r.y + r.h / 2, r.y + r.h].some((v) => Math.abs(v - bH.at) < 0.5)) { a = Math.min(a, r.x); b = Math.max(b, r.x + r.w); } }); lines.push({ v: false, at: bH.at, a: a, b: b }); }
    return { dx: dx, dy: dy, lines: lines, snappedX: !!bV, snappedY: !!bH };
  }
  // Одинаковые интервалы (как в Figma). Одна ось: pos/size тянущегося, intervals —
  // отрезки [s,e] соседей в той же полосе. Возвращает целевой pos и два равных зазора.
  function gapSnap1D(pos, size, intervals, th) {
    const end = pos + size, list = intervals.slice().sort((p, q) => p.s - q.s);
    const left = list.filter((r) => r.e <= pos + th), right = list.filter((r) => r.s >= end - th);
    const cands = [];
    // (1) по центру между ближайшими соседями слева и справа
    if (left.length && right.length) {
      const L = left[left.length - 1], R = right[0], target = (L.e + R.s - size) / 2, g = target - L.e;
      if (g > 0.5) cands.push({ target: target, gaps: [{ a: L.e, b: target }, { a: target + size, b: R.s }] });
    }
    // (2) повтор зазора слева: два ближайших слева дают зазор g, ставим справа от них так же
    if (left.length >= 2) {
      const L2 = left[left.length - 1], L1 = left[left.length - 2], g = L2.s - L1.e, target = L2.e + g;
      if (g > 0.5) cands.push({ target: target, gaps: [{ a: L1.e, b: L2.s }, { a: L2.e, b: target }] });
    }
    // (3) повтор зазора справа
    if (right.length >= 2) {
      const R1 = right[0], R2 = right[1], g = R2.s - R1.e, target = R1.s - g - size;
      if (g > 0.5) cands.push({ target: target, gaps: [{ a: target + size, b: R1.s }, { a: R1.e, b: R2.s }] });
    }
    let best = null;
    cands.forEach((c) => { const d = Math.abs(pos - c.target); if (d <= th && (!best || d < best.d)) best = { d: d, c: c }; });
    return best ? best.c : null;
  }
  // Снап равных интервалов при перетаскивании (по осям, где край НЕ примагнитился).
  function equalGapSnap(box, skipX, skipY) {
    const th = 7 / stage.scaleX(); let dx = 0, dy = 0; const marks = [];
    if (!skipX) {
      const band = (guideRefs || []).filter((r) => r.y < box.y + box.h && r.y + r.h > box.y);
      const r = gapSnap1D(box.x, box.w, band.map((o) => ({ s: o.x, e: o.x + o.w })), th);
      if (r) { dx = r.target - box.x; const cy = box.y + box.h / 2; r.gaps.forEach((g) => marks.push({ seg: true, x0: g.a, y0: cy, x1: g.b, y1: cy })); }
    }
    if (!skipY) {
      const band = (guideRefs || []).filter((r) => r.x < box.x + box.w && r.x + r.w > box.x);
      const r = gapSnap1D(box.y, box.h, band.map((o) => ({ s: o.y, e: o.y + o.h })), th);
      if (r) { dy = r.target - box.y; const cx = box.x + box.w / 2 + dx; r.gaps.forEach((g) => marks.push({ seg: true, x0: cx, y0: g.a, x1: cx, y1: g.b })); }
    }
    return { dx: dx, dy: dy, marks: marks };
  }
  // Полный снап при перетаскивании: край (приоритет) + равные интервалы по свободным осям.
  function computeDragSnap(box) {
    const e = computeSnap(box);
    const g = equalGapSnap(box, e.snappedX, e.snappedY);
    return { dx: e.snappedX ? e.dx : g.dx, dy: e.snappedY ? e.dy : g.dy, lines: e.lines.concat(g.marks) };
  }
  function drawGuides(lines) {
    guideLayer.destroyChildren();
    const sw = 1 / stage.scaleX(), cap = 5 / stage.scaleX();
    (lines || []).forEach((L) => {
      if (L.seg) {
        guideLayer.add(new Konva.Line({ points: [L.x0, L.y0, L.x1, L.y1], stroke: '#ff3b7f', strokeWidth: sw, listening: false }));
        if (L.y0 === L.y1) { [L.x0, L.x1].forEach((x) => guideLayer.add(new Konva.Line({ points: [x, L.y0 - cap, x, L.y0 + cap], stroke: '#ff3b7f', strokeWidth: sw, listening: false }))); }
        else { [L.y0, L.y1].forEach((y) => guideLayer.add(new Konva.Line({ points: [L.x0 - cap, y, L.x0 + cap, y], stroke: '#ff3b7f', strokeWidth: sw, listening: false }))); }
      } else { const pts = L.v ? [L.at, L.a, L.at, L.b] : [L.a, L.at, L.b, L.at]; guideLayer.add(new Konva.Line({ points: pts, stroke: '#ff3b7f', strokeWidth: sw, listening: false })); }
    });
    guideLayer.batchDraw();
  }
  function clearGuides() { guideLayer.destroyChildren(); guideLayer.batchDraw(); guideRefs = null; }
  // Снап ТЯНУЩЕГОСЯ угла при ресайзе: двигаем угол P (противоположный F зафиксирован),
  // липнем краями/центрами к соседям по X и Y независимо; линии — через выровненные.
  function snapResizePoint(P, F) {
    const th = 7 / stage.scaleX();
    let x = P.x, y = P.y, bV = null, bH = null;
    (guideRefs || []).forEach((r) => {
      [r.x, r.x + r.w / 2, r.x + r.w].forEach((v) => { const ad = Math.abs(v - P.x); if (ad <= th && (!bV || ad < bV.ad)) bV = { ad: ad, at: v }; });
      [r.y, r.y + r.h / 2, r.y + r.h].forEach((v) => { const ad = Math.abs(v - P.y); if (ad <= th && (!bH || ad < bH.ad)) bH = { ad: ad, at: v }; });
    });
    const lines = [];
    if (bV) { x = bV.at; let a = Math.min(y, F.y), b = Math.max(y, F.y); (guideRefs || []).forEach((r) => { if ([r.x, r.x + r.w / 2, r.x + r.w].some((v) => Math.abs(v - bV.at) < 0.5)) { a = Math.min(a, r.y); b = Math.max(b, r.y + r.h); } }); lines.push({ v: true, at: bV.at, a: a, b: b }); }
    if (bH) { y = bH.at; let a = Math.min(x, F.x), b = Math.max(x, F.x); (guideRefs || []).forEach((r) => { if ([r.y, r.y + r.h / 2, r.y + r.h].some((v) => Math.abs(v - bH.at) < 0.5)) { a = Math.min(a, r.x); b = Math.max(b, r.x + r.w); } }); lines.push({ v: false, at: bH.at, a: a, b: b }); }
    return { x: x, y: y, lines: lines, snappedX: !!bV, snappedY: !!bH };
  }
  // Равные интервалы при РЕСАЙЗЕ (одна ось): двигаем край E (противоположный F фикс.),
  // band — соседи [{s,e}] в полосе. Цель — зазор E↔соседа = либо зазору с фикс.стороны,
  // либо любому зазору-паре в ряду. Возвращает целевой E + два равных отрезка-мерки.
  function resizeGapTargets(F, E, band) {
    const th = 7 / stage.scaleX(), dir = Math.sign(E - F) || 1, list = band.slice().sort((a, b) => a.s - b.s);
    let Nedge = null;
    if (dir > 0) { const c = list.filter((r) => r.s >= E - th); if (c.length) Nedge = c[0].s; }
    else { const c = list.filter((r) => r.e <= E + th); if (c.length) Nedge = c[c.length - 1].e; }
    if (Nedge == null) return null;
    const targets = [];
    if (dir > 0) { const c = list.filter((r) => r.e <= F + th); if (c.length) { const M = c[c.length - 1]; targets.push({ G: F - M.e, ref: { a: M.e, b: F } }); } }
    else { const c = list.filter((r) => r.s >= F - th); if (c.length) { const M = c[0]; targets.push({ G: M.s - F, ref: { a: F, b: M.s } }); } }
    for (let i = 0; i < list.length - 1; i++) { const g = list[i + 1].s - list[i].e; if (g > 0.5) targets.push({ G: g, ref: { a: list[i].e, b: list[i + 1].s } }); }
    let best = null;
    targets.forEach((t) => { if (t.G <= 0.5) return; const targetE = Nedge - dir * t.G, d = Math.abs(E - targetE); if (d <= th && (!best || d < best.d)) best = { d: d, E: targetE, ref: t.ref, moving: dir > 0 ? { a: targetE, b: Nedge } : { a: Nedge, b: targetE } }; });
    return best;
  }
  // Снап тянущегося угла окна (P) при фикс. углу F: край/центр (приоритет) + равные
  // интервалы по свободным осям. Используется и при ресайзе окна, и при его создании.
  function frameCornerSnap(P, F) {
    const S = snapResizePoint(P, F);
    let Px = S.x, Py = S.y; const marks = S.lines.slice();
    const cy = (F.y + Py) / 2, cx = (F.x + Px) / 2;
    if (!S.snappedX) {
      const bandX = (guideRefs || []).filter((r) => r.y < Math.max(F.y, Py) && r.y + r.h > Math.min(F.y, Py)).map((r) => ({ s: r.x, e: r.x + r.w }));
      const g = resizeGapTargets(F.x, P.x, bandX);
      if (g) { Px = g.E; marks.push({ seg: true, x0: g.moving.a, y0: cy, x1: g.moving.b, y1: cy }, { seg: true, x0: g.ref.a, y0: cy, x1: g.ref.b, y1: cy }); }
    }
    if (!S.snappedY) {
      const bandY = (guideRefs || []).filter((r) => r.x < Math.max(F.x, Px) && r.x + r.w > Math.min(F.x, Px)).map((r) => ({ s: r.y, e: r.y + r.h }));
      const g = resizeGapTargets(F.y, P.y, bandY);
      if (g) { Py = g.E; marks.push({ seg: true, x0: cx, y0: g.moving.a, x1: cx, y1: g.moving.b }, { seg: true, x0: cx, y0: g.ref.a, x1: cx, y1: g.ref.b }); }
    }
    return { x: Px, y: Py, marks: marks };
  }
  // Снап для РАВНОМЕРНОГО ресайза (картинки/фигуры): масштаб один, поэтому липнем
  // тем краем угла, что ближе к линии соседа — второй край следует по пропорции.
  function snapUniformScale(F, dirX, dirY, w0, h0, s) {
    if (!guideRefs || !guideRefs.length) return { s: s, lines: [] };
    const th = 7 / stage.scaleX();
    const cornerX = F.x + dirX * w0 * s, cornerY = F.y + dirY * h0 * s;
    let best = null;
    // Кандидаты-выравнивания: угол к краю/центру соседа.
    (guideRefs || []).forEach((r) => {
      [r.x, r.x + r.w / 2, r.x + r.w].forEach((vx) => { const dist = Math.abs(cornerX - vx); if (dist <= th && (!best || dist < best.dist)) best = { dist: dist, s: Math.abs(vx - F.x) / w0, kind: 'edgeV', at: vx }; });
      [r.y, r.y + r.h / 2, r.y + r.h].forEach((vy) => { const dist = Math.abs(cornerY - vy); if (dist <= th && (!best || dist < best.dist)) best = { dist: dist, s: Math.abs(vy - F.y) / h0, kind: 'edgeH', at: vy }; });
    });
    // Кандидаты-интервалы: край угла делает зазор до соседа равным другому зазору.
    const yLo = Math.min(F.y, cornerY), yHi = Math.max(F.y, cornerY);
    const bandX = (guideRefs || []).filter((r) => r.y < yHi && r.y + r.h > yLo).map((r) => ({ s: r.x, e: r.x + r.w }));
    const gX = resizeGapTargets(F.x, cornerX, bandX);
    if (gX) { const dist = Math.abs(cornerX - gX.E); if (dist <= th && (!best || dist < best.dist)) best = { dist: dist, s: Math.abs(gX.E - F.x) / w0, kind: 'gapV', g: gX }; }
    const xLo = Math.min(F.x, cornerX), xHi = Math.max(F.x, cornerX);
    const bandY = (guideRefs || []).filter((r) => r.x < xHi && r.x + r.w > xLo).map((r) => ({ s: r.y, e: r.y + r.h }));
    const gY = resizeGapTargets(F.y, cornerY, bandY);
    if (gY) { const dist = Math.abs(cornerY - gY.E); if (dist <= th && (!best || dist < best.dist)) best = { dist: dist, s: Math.abs(gY.E - F.y) / h0, kind: 'gapH', g: gY }; }
    if (!best) return { s: s, lines: [] };
    const ns = Math.max(0.05, Math.min(40, best.s)), cX = F.x + dirX * w0 * ns, cY = F.y + dirY * h0 * ns, lines = [];
    if (best.kind === 'edgeV') { let a = Math.min(cY, F.y), b = Math.max(cY, F.y); (guideRefs || []).forEach((r) => { if ([r.x, r.x + r.w / 2, r.x + r.w].some((v) => Math.abs(v - best.at) < 0.5)) { a = Math.min(a, r.y); b = Math.max(b, r.y + r.h); } }); lines.push({ v: true, at: best.at, a: a, b: b }); }
    else if (best.kind === 'edgeH') { let a = Math.min(cX, F.x), b = Math.max(cX, F.x); (guideRefs || []).forEach((r) => { if ([r.y, r.y + r.h / 2, r.y + r.h].some((v) => Math.abs(v - best.at) < 0.5)) { a = Math.min(a, r.x); b = Math.max(b, r.x + r.w); } }); lines.push({ v: false, at: best.at, a: a, b: b }); }
    else if (best.kind === 'gapV') { const cy = (F.y + cY) / 2; lines.push({ seg: true, x0: best.g.moving.a, y0: cy, x1: best.g.moving.b, y1: cy }, { seg: true, x0: best.g.ref.a, y0: cy, x1: best.g.ref.b, y1: cy }); }
    else { const cx = (F.x + cX) / 2; lines.push({ seg: true, x0: cx, y0: best.g.moving.a, x1: cx, y1: best.g.moving.b }, { seg: true, x0: cx, y0: best.g.ref.a, x1: cx, y1: best.g.ref.b }); }
    return { s: ns, lines: lines };
  }

  function onNodeDragMove(id, node) {
    positionHandles(); // ручки следуют за объектом при перемещении
    recomputeConnectors(); renderAnchors(); // привязанные стрелки тянутся следом
    captureDragSnap(dragStart ? Array.from(selected) : [id]);
    const isLead = !dragStart || dragStart.leadId === id;
    if (!isLead) return; // следом-объекты двигает ведущий
    if (!guideRefs) guideRefs = collectGuideRefs(dragStart ? Array.from(selected) : [id]);
    const b = node.getClientRect({ relativeTo: layer });
    const snap = computeDragSnap({ x: b.x, y: b.y, w: b.width, h: b.height });
    if (snap.dx || snap.dy) node.position({ x: node.x() + snap.dx, y: node.y() + snap.dy });
    drawGuides(snap.lines);
    moveDragFollowers(id, node);
    // Ручки коннектора (синие концы + белые путевые точки) должны ехать ВМЕСТЕ с линией,
    // а не телепортироваться в конце: позиционируем их по ЖИВОЙ позиции узла (data.x/y ещё старые).
    if (connHandles.visible()) {
      const cel = connSelectedEl();
      if (cel) { const cn = nodes.get(cel.id); if (cn) positionConnHandlesAt(cel, cn.x(), cn.y()); }
    }
    if (shapeTextItems.size) repositionWidgets(); // текст внутри фигур едет вместе с фигурой
    layer.batchDraw();
  }

  function onNodeDragEnd(id, node) {
    recomputeConnectors();
    syncConnectorsOf(dragStart ? Array.from(selected) : [id]);
    // Синхронизируем все сдвинутые объекты: выделение + «прицепы» (надписи на
    // картинке/pdf едут с ней, даже если не выделены).
    const ids = new Set([id]);
    if (dragStart && dragStart.leadId === id) {
      Array.from(selected).forEach((x) => ids.add(x));
      dragStart.items.forEach((it) => { ids.add(it.node ? it.node.id() : (it.widget && it.widget.el.id)); });
    }
    ids.forEach((eid) => {
      const el = elements.get(eid); if (!el) return;
      // Геометрию по точкам не синкаем по x/y (её позиция определяется точками) —
      // иначе запишем и разошлём ложный сдвиг, оторвав её от точек.
      if (isPointBound(el)) return;
      const n = nodes.get(eid);
      if (n) { el.data.x = n.x(); el.data.y = n.y(); } // виджеты: data.x/y уже обновлены при move
      send({ action: 'element_update', element: el });
    });
    dragStart = null;
    commitDragSnap();
    positionHandles();
    clearGuides();
  }

  // Двигать «ведомых» группового перетаскивания за ведущим (Konva-узлы + DOM-виджеты).
  // Общий помощник — используют и onNodeDragMove, и onGeoDragMove (когда ведущий —
  // свободная точка/окружность), иначе гео-обработчики замораживали остальную группу.
  function moveDragFollowers(id, node) {
    if (!(dragStart && dragStart.leadId === id)) return;
    const dx = node.x() - dragStart.leadX0, dy = node.y() - dragStart.leadY0;
    let anyWidget = false;
    dragStart.items.forEach((it) => {
      if (it.node) it.node.position({ x: it.x0 + dx, y: it.y0 + dy });
      else if (it.widget) { it.widget.el.data.x = it.wx0 + dx; it.widget.el.data.y = it.wy0 + dy; anyWidget = true; }
    });
    if (anyWidget) repositionWidgets();
    tr.forceUpdate();
  }
  function commitDragFollowers(id) {
    if (!(dragStart && dragStart.leadId === id)) return;
    dragStart.items.forEach((it) => {
      const eid = it.node ? it.node.id() : (it.widget && it.widget.el.id);
      const el = eid && elements.get(eid); if (!el) return;
      if (isPointBound(el)) return;
      const n = nodes.get(eid);
      if (n) { el.data.x = n.x(); el.data.y = n.y(); }
      send({ action: 'element_update', element: el });
    });
  }

  // Групповое перемещение, начатое с DOM-элемента (текст/виджет) — двигаем ВСЁ
  // выделение (и Konva-объекты, и DOM), чтобы текст в выделении вёл себя как все.
  function selectionSnapshot() {
    const snap = [];
    selected.forEach((id) => {
      const n = nodes.get(id); if (n) { snap.push({ id, node: n, x0: n.x(), y0: n.y() }); return; }
      const w = widgetItems.get(id); if (w) snap.push({ id, widget: w, x0: (w.el.data.x || 0), y0: (w.el.data.y || 0) });
    });
    return snap;
  }
  function moveSnapshotBy(snap, dx, dy) {
    snap.forEach((it) => { if (it.node) it.node.position({ x: it.x0 + dx, y: it.y0 + dy }); else if (it.widget) { it.widget.el.data.x = it.x0 + dx; it.widget.el.data.y = it.y0 + dy; } });
    repositionWidgets(); layer.batchDraw();
  }
  function domSelectionDrag(startEv) {
    const s = stage.scaleX(), sx = startEv.clientX, sy = startEv.clientY;
    const snap = selectionSnapshot();
    const befores = snap.map((o) => ({ id: o.id, before: clone(elements.get(o.id)) })).filter((b) => b.before);
    let moved = false;
    const mv = (ev) => { if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) > 3) moved = true; if (moved) moveSnapshotBy(snap, (ev.clientX - sx) / s, (ev.clientY - sy) / s); };
    const up = () => {
      document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up);
      if (!moved) return;
      const ops = [];
      selected.forEach((id) => { const el = elements.get(id); if (!el) return; const n = nodes.get(id); if (n) { el.data.x = n.x(); el.data.y = n.y(); } send({ action: 'element_update', element: el }); });
      befores.forEach((b) => { const after = elements.get(b.id); if (after) ops.push({ kind: 'upd', before: b.before, after: clone(after) }); });
      histBatch(ops);
      if (tr) tr.forceUpdate();
    };
    document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
  }

  // ── Геометрия: точки и окружности с привязкой ──────────────────────────
  // Привязка курсора: сначала к окружности (точка ложится точно на неё и
  // запоминает угол), затем к существующей точке, затем к узлу сетки.
  function snapPoint(pt, excludeId) {
    const THRESH = 12 / stage.scaleX();
    // 1) на окружность
    let bestC = null, bestD = THRESH;
    elements.forEach((el) => {
      if (el.type !== 'circle') return;
      const d = Math.hypot(pt.x - el.data.x, pt.y - el.data.y);
      const diff = Math.abs(d - (el.data.r || 0));
      if (diff < bestD) { bestD = diff; bestC = el; }
    });
    if (bestC) {
      const a = Math.atan2(pt.y - bestC.data.y, pt.x - bestC.data.x);
      const r = bestC.data.r || 0;
      return { x: bestC.data.x + r * Math.cos(a), y: bestC.data.y + r * Math.sin(a), on: { c: bestC.id, a } };
    }
    // 2) к существующей точке
    let bestP = null, bestPD = THRESH, bestPW = null;
    elements.forEach((el) => {
      if (el.type !== 'point' || el.id === excludeId) return;
      const w = pointWorld(el);
      const d = Math.hypot(pt.x - w.x, pt.y - w.y);
      if (d < bestPD) { bestPD = d; bestP = el; bestPW = w; }
    });
    if (bestP) return { x: bestPW.x, y: bestPW.y, on: null };
    // 3) к узлу сетки
    const gx = Math.round(pt.x / GRID_STEP) * GRID_STEP, gy = Math.round(pt.y / GRID_STEP) * GRID_STEP;
    if (Math.abs(pt.x - gx) < THRESH && Math.abs(pt.y - gy) < THRESH) return { x: gx, y: gy, on: null };
    return { x: pt.x, y: pt.y, on: null };
  }

  // Пересчёт зависимой геометрии: точки «на окружности» держатся на ней по углу.
  // ── Построения по точкам (отрезок/луч/прямая/перпендикуляр/параллель/
  //    серединный перпендикуляр/биссектриса/угол) ────────────────────────
  const CONSTRUCT_LINES = ['segment', 'ray', 'gline', 'perpbis', 'perp', 'parallel', 'bisector'];
  const CONSTRUCT_PICKS = { segment: 2, ray: 2, gline: 2, perpbis: 2, bisector: 3, perp: 3, parallel: 3, angle: 3, conic: 5 };
  // Бесконечные построения (луч, прямая, перп., паралл., сред.перп., биссектриса)
  // живут СТРОГО внутри матокна — их обрезает граница окна. Отрезок и угол — конечные,
  // строятся где угодно.
  const INFINITE_CONSTRUCTS = ['ray', 'gline', 'perpbis', 'perp', 'parallel', 'bisector', 'conic'];
  const GEO_L = 6000; // «бесконечность» в локальных px матокна (обрежет clip окна)
  // Производная точка — положение полностью определено (пересечение), её не таскают.
  function isDerivedPoint(el) { return el.type === 'point' && el.data.on && !!(el.data.on.isect || el.data.on.regpoly || el.data.on.centroid || el.data.on.ratio || el.data.on.xform); }
  function ptPos(id) { const e = elements.get(id); return (e && e.type === 'point') ? pointWorld(e) : null; }
  function vnorm(v) { const m = Math.hypot(v.x, v.y) || 1; return { x: v.x / m, y: v.y / m }; }
  function isConstruction(t) { return CONSTRUCT_LINES.indexOf(t) >= 0 || t === 'angle'; }
  // ── Единая «трейт-таблица» геометрии по точкам ─────────────────────────
  // isPointBoundLine — объект ОПРЕДЕЛЯЕТСЯ точками, рисуется в абсолютных коорд.
  // от них: не таскается свободно как узел, двигается ПАРАЛЛЕЛЬНЫМ ПЕРЕНОСОМ своих
  // точек (startLineDrag) и следует за ними в recompute. isPointBound — то же + произв.
  // точки (двигаться не могут). ЕДИНАЯ точка правды вместо ~6 разрозненных списков
  // (два draggable-гейта, маршрутизация переноса, исключение из «ведомых», reattach).
  // Новый такой тип (напр. коника) добавляется ЗДЕСЬ, а не в шести местах.
  function isPointBoundLine(el) { return !!(el && (isConstruction(el.type) || el.type === 'circ' || el.type === 'vector' || el.type === 'conic' || isFilledPoly(el.type))); }
  function isPointBound(el) { return !!(el && (isPointBoundLine(el) || isDerivedPoint(el))); }

  // Функция позиции опорной точки для построения: привязанное к окну считаем
  // в ЛОКАЛЬНЫХ px группы окна (clip окна обрежет «бесконечное»), свободное — в мировых.
  function ptPosFor(el) {
    const fr = el.data.frame ? elements.get(el.data.frame) : null;
    if (!fr) return ptPos;
    return (id) => { const e = elements.get(id); if (!(e && e.type === 'point')) return null; return frameMathToLocal(fr, e.data.mx || 0, e.data.my || 0); };
  }
  // Параметры построения: базовая точка, направление и диапазон параметра t.
  //   segment  — конечный, концы A,B;
  //   ray/bisector — луч, t∈[0,∞);
  //   gline/perp/parallel/perpbis — полная прямая, t∈(−∞,∞).
  // Единичное направление опорной линии-объекта (для перп./паралл. «по линии»).
  function refLineDir(el, depth) {
    const P = constructionParams(el, depth);
    if (!P) return null;
    if (P.u) return P.u;
    if (P.seg) return vnorm({ x: P.seg[2] - P.seg[0], y: P.seg[3] - P.seg[1] });
    return null;
  }
  function constructionParams(el, depth) {
    depth = depth || 0; if (depth > 8) return null; // страховка от циклов ссылок
    const d = el.data;
    const pos = ptPosFor(el);
    // Перпендикуляр/параллель «по линии»: базовая линия-объект d.line + точка d.through.
    if ((el.type === 'perp' || el.type === 'parallel') && d.line) {
      const ref = elements.get(d.line);
      const ru = ref ? refLineDir(ref, depth + 1) : null;
      const through = pos(d.through);
      if (!ru || !through) return null;
      const u = (el.type === 'perp') ? { x: -ru.y, y: ru.x } : ru;
      return { base: through, u, tlo: -Infinity, thi: Infinity };
    }
    const A = pos(d.a), B = pos(d.b), C = d.c ? pos(d.c) : null;
    if (!A || !B) return null;
    if (el.type === 'segment') return { seg: [A.x, A.y, B.x, B.y] };
    const dir = vnorm({ x: B.x - A.x, y: B.y - A.y });
    const pdir = { x: -dir.y, y: dir.x };
    if (el.type === 'ray') return { base: A, u: dir, tlo: 0, thi: Infinity };
    if (el.type === 'gline') return { base: A, u: dir, tlo: -Infinity, thi: Infinity };
    if (el.type === 'perpbis') return { base: { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 }, u: pdir, tlo: -Infinity, thi: Infinity };
    // Перпендикуляр/параллель «по трём точкам»: A,B задают направление, C — через какую точку.
    if (el.type === 'perp') { if (!C) return null; return { base: C, u: pdir, tlo: -Infinity, thi: Infinity }; }
    if (el.type === 'parallel') { if (!C) return null; return { base: C, u: dir, tlo: -Infinity, thi: Infinity }; }
    if (el.type === 'bisector') {
      if (!C) return null; const V = B;
      const u = vnorm({ x: A.x - V.x, y: A.y - V.y }), w = vnorm({ x: C.x - V.x, y: C.y - V.y });
      let b = { x: u.x + w.x, y: u.y + w.y }; if (Math.hypot(b.x, b.y) < 1e-6) b = pdir;
      return { base: V, u: vnorm(b), tlo: 0, thi: Infinity };
    }
    return null;
  }
  // Концы вектора AB в коорд. узла (лок. окна или мировые).
  function vecEnds(el) { const pos = ptPosFor(el), A = pos(el.data.a), B = pos(el.data.b); return (A && B) ? [A.x, A.y, B.x, B.y] : null; }
  function constructionLinePoints(el) {
    const P = constructionParams(el);
    if (!P) return null;
    if (P.seg) return P.seg; // отрезок — конечный, живёт где угодно
    if (el.data.frame) {
      // Бесконечное построение по параметрическому уравнению P(t)=base+t·u —
      // строго ВНУТРИ матокна: тянем на ±GEO_L в локальных px, граница окна обрезает.
      const t0 = (P.tlo === -Infinity) ? -GEO_L : P.tlo, t1 = GEO_L;
      return [P.base.x + P.u.x * t0, P.base.y + P.u.y * t0, P.base.x + P.u.x * t1, P.base.y + P.u.y * t1];
    }
    return null; // бесконечное построение вне окна не рисуем — оно живёт только в матокне
  }
  // Многоугольник: плоский список координат вершин (лок. коорд окна или мировые).
  function polygonPoints(el) {
    const pos = ptPosFor(el), flat = [];
    for (const id of (el.data.pts || [])) { const p = pos(id); if (!p) return null; flat.push(p.x, p.y); }
    return flat.length >= 4 ? flat : null;
  }
  function hexToRgba(hex, a) {
    hex = (hex || '#1f2937').replace('#', '');
    if (hex.length === 3) hex = hex.split('').map((c) => c + c).join('');
    const n = parseInt(hex, 16);
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }
  // ── Базовые фигуры (для схем/оформления): рисуются протягиванием рамки ──
  const SHAPE_TOOLS = { sh_rrect: 'rrect', sh_tri: 'tri', sh_rtri: 'rtri', sh_para: 'para', sh_trap: 'trap', sh_rhomb: 'rhomb', sh_penta: 'penta', sh_hexa: 'hexa', sh_star: 'star', sh_cyl: 'cyl', sh_cloud: 'cloud', sh_cross: 'cross', sh_barrow: 'barrow', sh_callout: 'callout' };
  function shapeRegPts(W, H, n, rotDeg) { const cx = W / 2, cy = H / 2, out = []; for (let i = 0; i < n; i++) { const a = (rotDeg + i * 360 / n) * Math.PI / 180; out.push([cx + Math.cos(a) * W / 2, cy + Math.sin(a) * H / 2]); } return out; }
  function shapeStarPts(W, H, n, rotDeg, inner) { const cx = W / 2, cy = H / 2, out = []; for (let i = 0; i < 2 * n; i++) { const a = (rotDeg + i * 180 / n) * Math.PI / 180, rr = (i % 2 === 0) ? 1 : inner; out.push([cx + Math.cos(a) * W / 2 * rr, cy + Math.sin(a) * H / 2 * rr]); } return out; }
  function shapePolyPath(ctx, pts) { ctx.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]); ctx.closePath(); }
  function shapeRoundRect(ctx, x, y, w, h, r) { r = Math.min(r, w / 2, h / 2); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
  function shapeCylinder(ctx, W, H) { const rx = W / 2, ry = Math.min(H * 0.16, H / 2 - 2); ctx.moveTo(0, ry); ctx.lineTo(0, H - ry); ctx.ellipse(rx, H - ry, rx, ry, 0, Math.PI, 2 * Math.PI, false); ctx.lineTo(W, ry); ctx.ellipse(rx, ry, rx, ry, 0, 0, 2 * Math.PI, true); ctx.closePath(); }
  function shapeCloud(ctx, W, H) { const cx = W / 2, cy = H / 2, rx = W / 2, ry = H / 2, n = 9; ctx.moveTo(cx + rx * 0.82, cy); for (let i = 0; i < n; i++) { const a1 = (i + 1) / n * 2 * Math.PI, am = (i + 0.5) / n * 2 * Math.PI, bump = 0.3 * Math.min(rx, ry); const mx = cx + Math.cos(am) * (rx + bump), my = cy + Math.sin(am) * (ry + bump); const ex = cx + Math.cos(a1) * rx * 0.82, ey = cy + Math.sin(a1) * ry * 0.82; ctx.quadraticCurveTo(mx, my, ex, ey); } ctx.closePath(); }
  function shapeCallout(ctx, W, H) { const bh = H * 0.72, r = Math.min(W, H) * 0.14, t0 = W * 0.20, t1 = W * 0.36, tipX = W * 0.12, tipY = H; ctx.moveTo(r, 0); ctx.arcTo(W, 0, W, bh, r); ctx.arcTo(W, bh, 0, bh, r); ctx.lineTo(t1, bh); ctx.lineTo(tipX, tipY); ctx.lineTo(t0, bh); ctx.arcTo(0, bh, 0, 0, r); ctx.arcTo(0, 0, W, 0, r); ctx.closePath(); }
  function shapePath(ctx, kind, W, H) {
    switch (kind) {
      case 'rrect': shapeRoundRect(ctx, 0, 0, W, H, Math.min(W, H) * 0.16); break;
      case 'tri': shapePolyPath(ctx, [[W / 2, 0], [W, H], [0, H]]); break;
      case 'rtri': shapePolyPath(ctx, [[0, 0], [0, H], [W, H]]); break;
      case 'para': { const s = W * 0.25; shapePolyPath(ctx, [[s, 0], [W, 0], [W - s, H], [0, H]]); break; }
      case 'trap': shapePolyPath(ctx, [[W * 0.25, 0], [W * 0.75, 0], [W, H], [0, H]]); break;
      case 'rhomb': shapePolyPath(ctx, [[W / 2, 0], [W, H / 2], [W / 2, H], [0, H / 2]]); break;
      case 'penta': shapePolyPath(ctx, shapeRegPts(W, H, 5, -90)); break;
      case 'hexa': shapePolyPath(ctx, shapeRegPts(W, H, 6, -90)); break;
      case 'star': shapePolyPath(ctx, shapeStarPts(W, H, 5, -90, 0.42)); break;
      case 'cross': {
        // Симметричный крест: вписан в КВАДРАТ по меньшей стороне и центрирован
        // в рамке. Иначе рукава тянулись до краёв W и H по отдельности и при
        // неквадратной рамке крест перекашивало.
        const Sq = Math.min(W, H), ox = (W - Sq) / 2, oy = (H - Sq) / 2, aw = Sq * 0.34;
        const L = ox, R = ox + Sq, T = oy, Bt = oy + Sq;
        const x0 = ox + (Sq - aw) / 2, x1 = ox + (Sq + aw) / 2, y0 = oy + (Sq - aw) / 2, y1 = oy + (Sq + aw) / 2;
        shapePolyPath(ctx, [[x0, T], [x1, T], [x1, y0], [R, y0], [R, y1], [x1, y1], [x1, Bt], [x0, Bt], [x0, y1], [L, y1], [L, y0], [x0, y0]]);
        break;
      }
      case 'barrow': { const hw = Math.min(W * 0.42, W - 2), y0 = H * 0.25, y1 = H * 0.75; shapePolyPath(ctx, [[0, y0], [W - hw, y0], [W - hw, 0], [W, H / 2], [W - hw, H], [W - hw, y1], [0, y1]]); break; }
      case 'cyl': shapeCylinder(ctx, W, H); break;
      case 'cloud': shapeCloud(ctx, W, H); break;
      case 'callout': shapeCallout(ctx, W, H); break;
      default: ctx.rect(0, 0, W, H);
    }
  }
  // Стиль заливки фигуры. d.fill: undefined — легаси (значение legacy), '' — без
  // заливки, иначе цвет + d.fillOpacity (0..1). Граница — d.stroke/d.color.
  function shapeFillStyle(d, legacy) {
    if (d.fill === undefined) return legacy || null;
    if (!d.fill) return null;
    return hexToRgba(d.fill, d.fillOpacity == null ? 0.2 : d.fillOpacity);
  }
  function drawBasicShape(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const d = el.data, W = d.width || 0, H = d.height || 0; if (W <= 0 || H <= 0) return;
    const col = d.stroke || d.color || '#1f2937';
    ctx.beginPath(); shapePath(ctx, d.kind, W, H);
    const fillStyle = shapeFillStyle(d, hexToRgba(col, 0.10));
    if (fillStyle) { ctx.fillStyle = fillStyle; ctx.fill(); }
    if ((d.strokeWidth == null ? 2 : d.strokeWidth) > 0) { ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.lineWidth = d.strokeWidth || 2; ctx.strokeStyle = col; ctx.stroke(); }
  }
  function hitBasicShape(ctx, shape) { const el = elements.get(shape.id()); if (!el) return; const d = el.data; ctx.beginPath(); shapePath(ctx, d.kind, d.width || 0, d.height || 0); ctx.closePath(); ctx.fillStrokeShape(shape); }
  // Вершины правильного n-угольника (center: центр+вершина; edge: два соседних
  // против часовой). Возвращает массив {x,y} в тех же коорд, что и опорные точки.
  function regPolyVertices(el) {
    const pos = ptPosFor(el), d = el.data, n = Math.max(3, Math.min(200, d.n || 3));
    if (d.kind === 'center') {
      const C = pos(d.center), V = pos(d.vertex); if (!C || !V) return null;
      const r = Math.hypot(V.x - C.x, V.y - C.y), a0 = Math.atan2(V.y - C.y, V.x - C.x);
      const out = [];
      for (let k = 0; k < n; k++) { const a = a0 + 2 * Math.PI * k / n; out.push({ x: C.x + r * Math.cos(a), y: C.y + r * Math.sin(a) }); }
      return out;
    }
    // edge: A,B — соседние вершины, обход A→B против часовой (по экрану).
    const A = pos(d.a), B = pos(d.b); if (!A || !B) return null;
    const dx = B.x - A.x, dy = B.y - A.y, s = Math.hypot(dx, dy) || 1, ux = dx / s, uy = dy / s;
    const h = s / (2 * Math.tan(Math.PI / n)), R = s / (2 * Math.sin(Math.PI / n));
    const mid = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 };
    const C = { x: mid.x + uy * h, y: mid.y - ux * h }; // центр слева от A→B (экранное CCW)
    const aA = Math.atan2(A.y - C.y, A.x - C.x), aB = Math.atan2(B.y - C.y, B.x - C.x);
    let step = aB - aA; while (step <= -Math.PI) step += 2 * Math.PI; while (step > Math.PI) step -= 2 * Math.PI;
    const dir = step >= 0 ? 1 : -1;
    const out = [];
    for (let k = 0; k < n; k++) { const a = aA + dir * 2 * Math.PI * k / n; out.push({ x: C.x + R * Math.cos(a), y: C.y + R * Math.sin(a) }); }
    return out;
  }
  // Плоский контур замкнутой фигуры (обычный многоугольник / правильный).
  function shapeOutline(el) {
    if (el.type === 'polygon') return polygonPoints(el);
    if (el.type === 'regpoly') { const vs = regPolyVertices(el); if (!vs) return null; const flat = []; vs.forEach((v) => flat.push(v.x, v.y)); return flat.length >= 6 ? flat : null; }
    return null;
  }
  function isFilledPoly(t) { return t === 'polygon' || t === 'regpoly'; }
  // ── Диаграмма Венна ────────────────────────────────────────────────────
  // Как заливается ОДНА зона — главное решение здесь.
  //
  // Наивный путь: вычислять границы зон. Каждая зона ограничена дугами
  // окружностей; нужны точки пересечения, сборка дуг в правильном порядке и
  // обход по направлению. Для трёх кругов это заметный кусок математики, и он
  // разваливается на вырожденных случаях (круги разъехались, вложились).
  //
  // Путь, которым идём: обрезка ровно по зоне, без всякой геометрии.
  //   • нужные круги — обычная обрезка, они пересекаются сами собой;
  //   • лишние круги ВЫЧИТАЕМ правилом «чёт-нечет»: путь из рамки и круга при
  //     этом правиле даёт «внутри рамки, но снаружи круга».
  // Обрезки накладываются друг на друга, поэтому «A, без B и C» — это обрезка
  // по кругу A, затем вычитание B, затем вычитание C.
  //
  // Первая версия красила иначе — кругами по порядку, от общего к частному, —
  // и это было ошибкой: заливка круга A растекалась на все ЧЕТЫРЕ зоны, что в
  // него входят, если у остальных зон цвета не было. Порядок теперь не важен
  // вовсе: каждая зона рисуется только в своих границах.
  //
  // Рисунок остаётся чётким на любом увеличении: работаем прямо на холсте,
  // без промежуточного буфера, который пришлось бы растягивать.
  const VENN_KEYS2 = ['A', 'B', 'AB'];
  const VENN_KEYS3 = ['A', 'B', 'C', 'AB', 'AC', 'BC', 'ABC'];
  const VENN_FILLS = ['', '#ffd8a8', '#b2f2bb', '#a5d8ff', '#eebefa', '#ffc9c9', '#ffec99', '#c3fae8'];
  const VENN_PAD = 16;        // отступ от рамки-универсума
  const VENN_LABEL = 32;      // полоса снаружи кругов под буквы A, B, C
  const VENN_OVERLAP = 0.5;   // классическое пересечение; круги статичны

  function vennKeys(d) { return (d.sets === 2) ? VENN_KEYS2 : VENN_KEYS3; }

  // Геометрия: радиус и центры кругов внутри рамки.
  function vennGeom(d) {
    const W = Math.max(40, d.width || 0), H = Math.max(40, d.height || 0);
    // Из доступной площади вычитаем полосу под буквы — иначе они налезают
    // на круги, как только диаграмму уменьшат.
    const aw = W - 2 * VENN_PAD - 2 * VENN_LABEL, ah = H - 2 * VENN_PAD - 2 * VENN_LABEL;
    const s = VENN_OVERLAP;   // круги статичны: расположение классическое
    const cx = W / 2, cy = H / 2;
    if (d.sets === 2) {
      // Ширина рисунка = расстояние между центрами + два радиуса = 2R(2−s).
      const R = Math.max(12, Math.min(aw / (2 * (2 - s)), ah / 2));
      const dd = 2 * R * (1 - s);
      return { W: W, H: H, R: R, cs: [{ x: cx - dd / 2, y: cy }, { x: cx + dd / 2, y: cy }] };
    }
    // Три круга — вершины равностороннего треугольника со стороной dd.
    const Rw = aw / (2 * (2 - s));
    const Rh = ah / (2 + Math.sqrt(3) * (1 - s));
    const R = Math.max(12, Math.min(Rw, Rh));
    const dd = 2 * R * (1 - s);
    const m = dd / Math.sqrt(3);              // расстояние от центра до вершины
    return {
      W: W, H: H, R: R,
      cs: [
        { x: cx, y: cy - m },
        { x: cx + m * Math.cos(Math.PI / 6), y: cy + m * Math.sin(Math.PI / 6) },
        { x: cx - m * Math.cos(Math.PI / 6), y: cy + m * Math.sin(Math.PI / 6) },
      ],
    };
  }
  // Порядок кругов: A сверху, B справа-снизу, C слева-снизу (для двух — слева/справа).
  function vennInside(g, i, p) {
    const c = g.cs[i];
    return (p.x - c.x) * (p.x - c.x) + (p.y - c.y) * (p.y - c.y) <= g.R * g.R;
  }
  // Какой области принадлежит точка: 'A', 'AB', 'ABC', 'U'…
  function vennKeyAt(d, g, p) {
    const n = (d.sets === 2) ? 2 : 3;
    let key = '';
    for (let i = 0; i < n; i++) if (vennInside(g, i, p)) key += 'ABC'[i];
    return key || 'U';
  }

  // Точка для подписи — «самая внутренняя» точка области: пробуем сетку и
  // берём точку, максимально удалённую от всех границ. Аналитические формулы
  // пришлось бы писать отдельно для каждого случая, а это работает всегда,
  // включая разъехавшиеся круги (тогда область пуста — подписи просто нет).
  function vennLabelPoints(d, g) {
    const sig = [d.sets, Math.round(g.W), Math.round(g.H), Math.round(g.R)].join('|');
    if (d._labSig === sig && d._lab) return d._lab;
    const n = (d.sets === 2) ? 2 : 3;
    const best = {};
    const STEP = 46;
    for (let ix = 0; ix <= STEP; ix++) {
      for (let iy = 0; iy <= STEP; iy++) {
        const p = { x: VENN_PAD + (g.W - 2 * VENN_PAD) * ix / STEP, y: VENN_PAD + (g.H - 2 * VENN_PAD) * iy / STEP };
        const key = vennKeyAt(d, g, p);
        // Насколько точка «глубоко внутри»: минимум расстояний до всех границ.
        let room = Math.min(p.x - VENN_PAD, g.W - VENN_PAD - p.x, p.y - VENN_PAD, g.H - VENN_PAD - p.y);
        for (let i = 0; i < n; i++) {
          const c = g.cs[i];
          room = Math.min(room, Math.abs(Math.hypot(p.x - c.x, p.y - c.y) - g.R));
        }
        if (!best[key] || room > best[key].room) best[key] = { x: p.x, y: p.y, room: room };
      }
    }
    d._labSig = sig; d._lab = best;
    return best;
  }

  function drawVenn(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const d = el.data, g = vennGeom(d);
    const n = (d.sets === 2) ? 2 : 3;
    const col = d.stroke || '#1f2937';
    const lw = (d.strokeWidth == null ? 2 : d.strokeWidth);
    const fills = d.fills || {}, labels = d.labels || {};
    const circle = (i) => { ctx.beginPath(); ctx.arc(g.cs[i].x, g.cs[i].y, g.R, 0, 2 * Math.PI); };

    // Обрезка ровно по одной зоне: нужные круги пересекаем, лишние вычитаем.
    const clipZone = (letters) => {
      for (let i = 0; i < n; i++) {
        if (letters.indexOf('ABC'[i]) >= 0) { circle(i); ctx.clip(); continue; }
        // «Внутри рамки, но вне круга»: рамка и круг одним путём по «чёт-нечет».
        // moveTo обязателен — иначе дуга соединится с углом рамки линией и
        // испортит путь.
        ctx.beginPath();
        ctx.rect(0, 0, g.W, g.H);
        ctx.moveTo(g.cs[i].x + g.R, g.cs[i].y);
        ctx.arc(g.cs[i].x, g.cs[i].y, g.R, 0, 2 * Math.PI);
        ctx.clip('evenodd');
      }
    };
    const paint = (key, color) => {
      if (!color) return;
      ctx.save();
      clipZone(key === 'U' ? '' : key);
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, g.W, g.H);
      ctx.restore();
    };
    // Порядок не важен — зоны не пересекаются.
    vennKeys(d).concat(['U']).forEach((k) => paint(k, fills[k]));

    // Рамка-универсум поверх заливок, чтобы её линия не пряталась под цветом.
    if (d.universe !== false) {
      ctx.beginPath(); ctx.rect(0.5, 0.5, g.W - 1, g.H - 1);
      ctx.lineWidth = Math.max(1, lw - 0.5); ctx.strokeStyle = col; ctx.stroke();
    }

    // Контуры кругов.
    if (lw > 0) {
      ctx.lineWidth = lw; ctx.strokeStyle = col;
      for (let i = 0; i < n; i++) { circle(i); ctx.stroke(); }
    }

    // Подписи областей.
    const pts = vennLabelPoints(d, g);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = d.textColor || '#2b2b33';
    // Кегль привязан к радиусу, а не задан числом: иначе при уменьшении
    // диаграммы цифры остаются прежними и вылезают за края зон.
    const fs = Math.max(9, Math.min(30, Math.round(g.R * 0.17)));
    ctx.font = '600 ' + fs + 'px system-ui, sans-serif';
    vennKeys(d).concat(d.universe === false ? [] : ['U']).forEach((k) => {
      const t = labels[k]; if (!t) return;
      const p = pts[k]; if (!p || p.room < 6) return;
      ctx.fillText(String(t), p.x, p.y);
    });

    // Имена множеств — над кругами, снаружи.
    ctx.font = '700 ' + Math.round(fs * 1.1) + 'px system-ui, sans-serif';
    ctx.fillStyle = col;
    const names = d.names || ['A', 'B', 'C'];
    for (let i = 0; i < n; i++) {
      const c = g.cs[i];
      // Отводим подпись от центра диаграммы наружу.
      const vx = c.x - g.W / 2, vy = c.y - g.H / 2;
      const len = Math.hypot(vx, vy) || 1;
      const off = g.R + VENN_LABEL * 0.45;
      const ox = c.x + (vx / len) * off, oy = c.y + (vy / len) * off;
      ctx.fillText(names[i] || 'ABC'[i], ox, oy);
    }
    // Отметка зоны, выбранной для подписи: заливка сама себя показывает, а вот
    // «куда попадёт число» иначе не видно.
    if (vennSel.id === el.id && vennSel.key) {
      const mp = pts[vennSel.key];
      if (mp && mp.room > 5) {
        ctx.beginPath();
        ctx.arc(mp.x, mp.y, Math.min(mp.room - 1, fs * 1.1), 0, 2 * Math.PI);
        ctx.setLineDash([4, 3]); ctx.lineWidth = 1.5; ctx.strokeStyle = '#4d7cfe';
        ctx.stroke(); ctx.setLineDash([]);
      }
    }

    // Подпись универсума в углу.
    if (d.universe !== false) {
      ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      ctx.fillText(d.universeName || 'U', 6, 5);
    }
  }

  // ── Панель диаграммы Венна ─────────────────────────────────────────────
  // Тот же язык, что у таблицы: выбрал часть — появилась плашка с подписью и
  // палитрой. Ctrl-клик добавляет области к выбору, поэтому «залить A∪B» — это
  // два клика и цвет.
  // Выбранный цвет — «кисть». Нажатие на зону красит её этим цветом; нажатие
  // на зону, уже закрашенную ИМЕННО ЭТИМ цветом, снимает заливку. Отдельного
  // шага «сначала выдели, потом закрась» нет — так меньше действий и не бывает
  // непонятного состояния «что сейчас выделено».
  // Кисть изначально ПУСТАЯ: пока цвет не выбран, нажатия по зонам ничего не
  // красят — только выбирают зону для подписи. Порядок всегда один:
  // сначала цвет, потом зоны.
  let vennBrush = '';
  let vennSel = { id: null, key: null };     // последняя нажатая зона — для подписи

  // Названия зон. Для трёх кругов важно писать «без C»: иначе «A и B» читается
  // как «всё пересечение A и B», хотя это только часть без центра.
  function vennZoneName(d, k) {
    if (k === 'U') return 'вне кругов';
    const three = (d.sets !== 2);
    const map2 = { A: 'A, без B', B: 'B, без A', AB: 'A и B' };
    const map3 = {
      A: 'A, без B и C', B: 'B, без A и C', C: 'C, без A и B',
      AB: 'A и B, без C', AC: 'A и C, без B', BC: 'B и C, без A',
      ABC: 'A, B и C',
    };
    return (three ? map3 : map2)[k] || k;
  }

  function vennElAt(id) { const e = elements.get(id); return (e && e.type === 'venn') ? e : null; }
  function vennPickRegion(el, wx, wy) {
    const d = el.data, g = vennGeom(d);
    const p = { x: wx - (d.x || 0), y: wy - (d.y || 0) };
    if (p.x < 0 || p.y < 0 || p.x > g.W || p.y > g.H) return false;
    const k = vennKeyAt(d, g, p);
    if (k === 'U' && d.universe === false) return false;
    const before = clone(el);
    d.fills = d.fills || {};
    // Тем же цветом — снимаем заливку; «без заливки» — просто выбираем зону.
    if (!vennBrush || d.fills[k] === vennBrush) delete d.fills[k];
    else d.fills[k] = vennBrush;
    vennSel = { id: el.id, key: k };
    upsertNode(el);
    send({ action: 'element_update', element: stripPrivate(el) });
    histUpd(stripPrivate(before), stripPrivate(el));
    showVennBar(el);
    return true;
  }
  function vennPaintKeys(el, keys) {
    const before = clone(el);
    el.data.fills = el.data.fills || {};
    // Если все зоны уже этого цвета — снимаем; иначе красим все.
    const allSame = vennBrush && keys.every((k) => el.data.fills[k] === vennBrush);
    keys.forEach((k) => {
      if (!vennBrush || allSame) delete el.data.fills[k];
      else el.data.fills[k] = vennBrush;
    });
    upsertNode(el);
    send({ action: 'element_update', element: stripPrivate(el) });
    histUpd(stripPrivate(before), stripPrivate(el));
    showVennBar(el);
  }
  // Панель следует за выделением: выбрали диаграмму — она появилась, ушли — скрылась.
  function syncVennBar() {
    const b = document.getElementById('venn-bar'); if (!b) return;
    if (selected.size === 1) {
      const el = elements.get(Array.from(selected)[0]);
      if (el && el.type === 'venn') {
        if (vennSel.id !== el.id) vennSel = { id: el.id, key: null };
        showVennBar(el);
        return;
      }
    }
    clearVennSel();
  }
  function clearVennSel() {
    vennSel = { id: null, key: null };
    const b = document.getElementById('venn-bar'); if (b) b.hidden = true;
  }

  const VENN_PRESETS2 = [
    { t: 'A∪B', keys: ['A', 'B', 'AB'] },
    { t: 'A∩B', keys: ['AB'] },
    { t: 'A∖B', keys: ['A'] },
    { t: 'B∖A', keys: ['B'] },
  ];

  function buildVennBar() {
    const bar = document.getElementById('venn-bar');
    if (!bar || bar._built) return bar;
    bar._built = true;
    bar.innerHTML =
      '<div class="vn-row">'
      + '<span class="vn-lbl">Множеств</span>'
      + '<span class="vn-seg" id="vn-sets"><button data-n="2">2</button><button data-n="3">3</button></span>'
      + '<label class="vn-chk"><input type="checkbox" id="vn-universe"> рамка</label>'
      + '</div>'
      + '<div class="vn-row">'
      + '<span class="vn-lbl">Цвет</span>'
      + '<span class="vn-fills" id="vn-fills"></span>'
      + '<span class="vn-lbl vn-tip"></span>'
      + '</div>'
      + '<div class="vn-row">'
      + '<span class="vn-lbl" id="vn-what">зона</span>'
      + '<input type="text" id="vn-text" placeholder="число или подпись" maxlength="24">'
      + '</div>'
      + '<div class="vn-row" id="vn-presets"><span class="vn-lbl">Закрасить</span></div>';

    VENN_FILLS.forEach((c) => {
      const b = document.createElement('button');
      b.className = 'vn-sw' + (c ? '' : ' none');
      b.dataset.c = c; b.style.background = c || '#fff';
      b.title = c ? 'Залить выбранное' : 'Убрать заливку';
      bar.querySelector('#vn-fills').appendChild(b);
    });
    bar.addEventListener('mousedown', (e) => { if (e.target.tagName !== 'INPUT') e.preventDefault(); });

    bar.querySelector('#vn-fills').addEventListener('click', (e) => {
      const b = e.target.closest('.vn-sw'); if (!b) return;
      vennBrush = b.dataset.c || '';
      const el = vennElAt(vennSel.id);
      if (el) showVennBar(el);
    });
    bar.querySelector('#vn-text').addEventListener('input', (e) => {
      const el = vennElAt(vennSel.id); if (!el || !vennSel.key) return;
      el.data.labels = el.data.labels || {};
      const k = vennSel.key;
      const v = e.target.value.trim();
      if (v) el.data.labels[k] = v; else delete el.data.labels[k];
      upsertNode(el); vennSyncSoon(el);
    });
    bar.querySelector('#vn-sets').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      const el = vennElAt(vennSel.id); if (!el) return;
      const before = clone(el);
      el.data.sets = +b.dataset.n;
      el.data._labSig = null;
      vennSel.key = null;
      vennCommit(el, before);
    });
    bar.querySelector('#vn-universe').addEventListener('change', (e) => {
      const el = vennElAt(vennSel.id); if (!el) return;
      const before = clone(el);
      el.data.universe = !!e.target.checked;
      vennCommit(el, before);
    });
    bar.querySelector('#vn-presets').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      const el = vennElAt(vennSel.id); if (!el) return;
      vennPaintKeys(el, JSON.parse(b.dataset.keys));
    });
    return bar;
  }
  let vennSyncTimer = null;
  function vennSyncSoon(el) {
    clearTimeout(vennSyncTimer);
    vennSyncTimer = setTimeout(() => send({ action: 'element_update', element: stripPrivate(el) }), 250);
  }
  function vennCommit(el, before) {
    upsertNode(el);
    send({ action: 'element_update', element: stripPrivate(el) });
    if (before) histUpd(stripPrivate(before), stripPrivate(el));
    showVennBar(el);
  }

  function showVennBar(el) {
    const bar = buildVennBar(); if (!bar) return;
    bar.hidden = false;
    const d = el.data;
    bar.querySelectorAll('#vn-sets button').forEach((b) => b.classList.toggle('on', +b.dataset.n === (d.sets || 3)));
    bar.querySelector('#vn-universe').checked = (d.universe !== false);
    bar.querySelectorAll('.vn-sw').forEach((b) => b.classList.toggle('on', (b.dataset.c || '') === vennBrush));
    const tip = bar.querySelector('.vn-tip');
    if (tip) tip.textContent = vennBrush
      ? 'нажимайте на зоны; тем же цветом — снять'
      : 'выберите цвет, затем нажимайте на зоны';
    const one = vennSel.key;
    bar.querySelector('#vn-what').textContent = one ? vennZoneName(d, one) : 'зона';
    const inp = bar.querySelector('#vn-text');
    inp.disabled = !one;
    inp.value = one ? ((d.labels || {})[one] || '') : '';
    // Заготовки — только для двух множеств: для трёх список был бы длиннее пользы.
    const pr = bar.querySelector('#vn-presets');
    pr.querySelectorAll('button').forEach((b) => b.remove());
    pr.style.display = (d.sets === 2) ? '' : 'none';
    if (d.sets === 2) {
      VENN_PRESETS2.forEach((p) => {
        const b = document.createElement('button');
        b.className = 'vn-preset'; b.textContent = p.t; b.dataset.keys = JSON.stringify(p.keys);
        b.title = 'Закрасить эти зоны текущим цветом (повторно — снять)';
        pr.appendChild(b);
      });
    }
    const s = stage.scaleX();
    const left = (d.x || 0) * s + stage.x();
    const top = (d.y || 0) * s + stage.y() + STAGE_TOP;
    bar.style.left = Math.max(8, Math.min(left, window.innerWidth - 380)) + 'px';
    bar.style.top = Math.max(64, top - bar.offsetHeight - 10) + 'px';
  }

  function insertVenn() {
    const p = worldPoint() || viewportCenterWorld();
    const W = 420, H = 320;
    const el = {
      id: uuid(), type: 'venn', z: 0,
      data: {
        x: p.x - W / 2, y: p.y - H / 2, width: W, height: H,
        sets: 3, universe: true,
        stroke: strokeColor, strokeWidth: 2,
        names: ['A', 'B', 'C'], labels: {}, fills: {},
      },
    };
    upsertNode(el); send({ action: 'element_add', element: stripPrivate(el) }); histAdd(stripPrivate(el));
    setTool('select');
    selectOnly(el.id);
    showVennBar(el);
  }

  // ── Измерения (длина / угол / площадь) ─────────────────────────────────
  // Значение считается «вживую» в recomputeGeometry по опорным объектам.
  function fmtMeasure(v) { const r = Math.round(v * 100) / 100; return String(Math.abs(r) < 1e-9 ? 0 : r); }
  function angleDeg(A, V, B) {
    const v1 = { x: A.x - V.x, y: A.y - V.y }, v2 = { x: B.x - V.x, y: B.y - V.y };
    const m = Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y); if (m < 1e-9) return 0;
    let c = (v1.x * v2.x + v1.y * v2.y) / m; c = Math.max(-1, Math.min(1, c));
    return Math.acos(c) * 180 / Math.PI;
  }
  function shoelace(flat) { let s = 0; const n = flat.length / 2; for (let i = 0; i < n; i++) { const j = (i + 1) % n; s += flat[2 * i] * flat[2 * j + 1] - flat[2 * j] * flat[2 * i + 1]; } return s / 2; }
  // {text, x, y} — подпись и мировая точка привязки; null если опоры пропали.
  function measureInfo(el) {
    const d = el.data, refs = (d.refs || []).map((id) => elements.get(id));
    if (!refs.length || refs.some((e) => !e)) return null;
    const fr = d.frame ? elements.get(d.frame) : null, unit = fr ? (fr.data.unit || 1) : 1;
    if (d.kind === 'length') {
      if (refs[0].type !== 'point' || refs[1].type !== 'point') return null;
      const A = pointWorld(refs[0]), B = pointWorld(refs[1]); if (!A || !B) return null;
      const val = Math.hypot(B.x - A.x, B.y - A.y) / (fr ? unit : 1);
      const nm = pointName(refs[0]) + pointName(refs[1]);
      return { text: (nm ? nm + ' = ' : '') + fmtMeasure(val), x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 };
    }
    if (d.kind === 'angle') {
      const A = pointWorld(refs[0]), V = pointWorld(refs[1]), B = pointWorld(refs[2]); if (!A || !V || !B) return null;
      const nm = pointName(refs[0]) + pointName(refs[1]) + pointName(refs[2]);
      return { text: '∠' + (nm ? nm + ' = ' : '') + fmtMeasure(angleDeg(A, V, B)) + '°', x: V.x, y: V.y };
    }
    if (d.kind === 'area') {
      const poly = refs[0]; if (!isFilledPoly(poly.type)) return null;
      const flat = shapeOutline(poly); if (!flat || flat.length < 6) return null;
      const pfr = poly.data.frame ? elements.get(poly.data.frame) : null;
      let area = Math.abs(shoelace(flat)); if (pfr) { const u = pfr.data.unit || 1; area /= u * u; }
      let cx = 0, cy = 0, nn = flat.length / 2; for (let i = 0; i < flat.length; i += 2) { cx += flat[i]; cy += flat[i + 1]; }
      cx /= nn; cy /= nn; if (pfr) { cx += pfr.data.x; cy += pfr.data.y; }
      return { text: 'S = ' + fmtMeasure(area), x: cx, y: cy };
    }
    return null;
  }
  // Числовое значение измерения (длина/угол°/площадь в единицах окна) — для
  // вычислителя условий и динамического текста. null, если опоры пропали.
  function measureValue(el) {
    const d = el.data, refs = (d.refs || []).map((id) => elements.get(id));
    if (!refs.length || refs.some((e) => !e)) return null;
    const fr = d.frame ? elements.get(d.frame) : null, unit = fr ? (fr.data.unit || 1) : 1;
    if (d.kind === 'length') { if (refs[0].type !== 'point' || refs[1].type !== 'point') return null; const A = pointWorld(refs[0]), B = pointWorld(refs[1]); if (!A || !B) return null; return Math.hypot(B.x - A.x, B.y - A.y) / (fr ? unit : 1); }
    if (d.kind === 'angle') { const A = pointWorld(refs[0]), V = pointWorld(refs[1]), B = pointWorld(refs[2]); if (!A || !V || !B) return null; return angleDeg(A, V, B); }
    if (d.kind === 'area') { const poly = refs[0]; if (!isFilledPoly(poly.type)) return null; const flat = shapeOutline(poly); if (!flat || flat.length < 6) return null; const pfr = poly.data.frame ? elements.get(poly.data.frame) : null; let area = Math.abs(shoelace(flat)); if (pfr) { const u = pfr.data.unit || 1; area /= u * u; } return area; }
    return null;
  }
  const MEASURE_PICKS = { measure_len: 2, measure_area: 1 };
  // ── Пометки для доказательств (равенство/прямой угол/параллельность) ────
  // type 'mark', data:{kind:'tick'|'arc'|'right'|'para', refs:[ids], count}.
  // Рисуется sceneFunc'ом по текущим мировым координатам опор — следует за ними.
  function markRefsWorld(el) {
    const refs = (el.data.refs || []).map((id) => { const e = elements.get(id); return (e && e.type === 'point') ? pointWorld(e) : null; });
    return refs.some((p) => !p) ? null : refs;
  }
  // ── Общие «кисти» декораций (строят путь в ctx; штрих делает вызывающий) ──
  // Засечки равенства: n штрихов поперёк отрезка AB в его середине.
  function pathEqTicks(ctx, A, B, n) {
    const dx = B.x - A.x, dy = B.y - A.y, L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L, px = -uy, py = ux;
    const mid = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 }, half = 6, gap = 4.5;
    for (let i = 0; i < n; i++) { const o = (i - (n - 1) / 2) * gap, c = { x: mid.x + ux * o, y: mid.y + uy * o }; ctx.moveTo(c.x - px * half, c.y - py * half); ctx.lineTo(c.x + px * half, c.y + py * half); }
  }
  // Шевроны параллельности: n «галочек» вдоль AB, указывающих по направлению A→B.
  function pathChevrons(ctx, A, B, n) {
    const dx = B.x - A.x, dy = B.y - A.y, L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L, px = -uy, py = ux;
    const mid = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 }, w = 6, h = 5, gap = 5.5;
    for (let i = 0; i < n; i++) { const o = (i - (n - 1) / 2) * gap, ax = mid.x + ux * (o + w / 2), ay = mid.y + uy * (o + w / 2); ctx.moveTo(ax - ux * w + px * h, ay - uy * w + py * h); ctx.lineTo(ax, ay); ctx.lineTo(ax - ux * w - px * h, ay - uy * w - py * h); }
  }
  // Дуги равенства углов: n концентрических дуг у вершины V от угла a1 на diff.
  function pathEqArcs(ctx, V, a1, diff, n, r0) {
    for (let i = 0; i < n; i++) { const r = (r0 || 14) + i * 4.5; ctx.moveTo(V.x + r * Math.cos(a1), V.y + r * Math.sin(a1)); ctx.arc(V.x, V.y, r, a1, a1 + diff, diff < 0); }
  }
  // Знак прямого угла: маленький квадрат в вершине V между лучами на A и B.
  function pathRightAngle(ctx, A, V, B) {
    const u1 = vnorm({ x: A.x - V.x, y: A.y - V.y }), u2 = vnorm({ x: B.x - V.x, y: B.y - V.y }), s = 12;
    ctx.moveTo(V.x + u1.x * s, V.y + u1.y * s); ctx.lineTo(V.x + (u1.x + u2.x) * s, V.y + (u1.y + u2.y) * s); ctx.lineTo(V.x + u2.x * s, V.y + u2.y * s);
  }
  function drawMarkShape(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const P = markRefsWorld(el); if (!P) return;
    const d = el.data, kind = d.kind, n = Math.max(1, d.count || 1);
    ctx.save(); ctx.strokeStyle = d.color || '#1f2937'; ctx.lineWidth = 1.6; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.beginPath();
    if (kind === 'tick') pathEqTicks(ctx, P[0], P[1], n);
    else if (kind === 'para') pathChevrons(ctx, P[0], P[1], n);
    else if (kind === 'arc') { const a1 = Math.atan2(P[0].y - P[1].y, P[0].x - P[1].x), a2 = Math.atan2(P[2].y - P[1].y, P[2].x - P[1].x); let diff = a2 - a1; while (diff <= -Math.PI) diff += 2 * Math.PI; while (diff > Math.PI) diff -= 2 * Math.PI; pathEqArcs(ctx, P[1], a1, diff, n); }
    else if (kind === 'right') pathRightAngle(ctx, P[0], P[1], P[2]);
    ctx.stroke(); ctx.restore();
  }
  // Равенство отрезков/углов и шевроны переехали в настройки объектов; из отдельных
  // инструментов-пометок остался только знак прямого угла.
  const MARK_PICKS = { mark_right: 3 };
  // Габарит построения-линии (для рамки/marquee — у Konva.Shape нет своего selfRect).
  function lineSelfRect(el) {
    return function () {
      const pts = constructionLinePoints(el) || [];
      if (pts.length < 4) return { x: 0, y: 0, width: 0, height: 0 };
      let a = Infinity, b = Infinity, c = -Infinity, e = -Infinity;
      for (let i = 0; i < pts.length; i += 2) { a = Math.min(a, pts[i]); c = Math.max(c, pts[i]); b = Math.min(b, pts[i + 1]); e = Math.max(e, pts[i + 1]); }
      return { x: a, y: b, width: c - a, height: e - b };
    };
  }
  // Построение-линия: сама линия (цвет/толщина/стиль — из атрибутов узла) + декорации:
  // шевроны параллельности (любая линия), засечки равенства и подпись длины (отрезок).
  function drawLineShape(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const pts = constructionLinePoints(el); if (!pts || pts.length < 4) return;
    ctx.beginPath(); ctx.moveTo(pts[0], pts[1]);
    for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
    ctx.strokeShape(shape);
    const d = el.data;
    const chev = Math.max(0, Math.min(3, d.chevrons || 0));
    const isSeg = el.type === 'segment';
    const ticks = isSeg ? Math.max(0, Math.min(3, d.eqTicks || 0)) : 0;
    const showLen = isSeg && d.showLength;
    if (!chev && !ticks && !showLen) return;
    let A, B; const P = constructionParams(el);
    if (P && P.seg) { A = { x: P.seg[0], y: P.seg[1] }; B = { x: P.seg[2], y: P.seg[3] }; }
    else { A = { x: pts[0], y: pts[1] }; B = { x: pts[pts.length - 2], y: pts[pts.length - 1] }; }
    const col = d.color || d.stroke || '#1f2937';
    ctx.save(); ctx.setLineDash([]); ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    if (ticks) pathEqTicks(ctx, A, B, ticks);
    if (chev) pathChevrons(ctx, A, B, chev);
    ctx.stroke();
    if (showLen) {
      const fr = d.frame ? elements.get(d.frame) : null;
      const Ld = Math.hypot(B.x - A.x, B.y - A.y), val = fr ? Ld / (fr.data.unit || 1) : Ld;
      const ddx = B.x - A.x, ddy = B.y - A.y, L = Math.hypot(ddx, ddy) || 1, px = -ddy / L, py = ddx / L;
      ctx.fillStyle = col; ctx.font = '12px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(fmtMeasure(val), (A.x + B.x) / 2 + px * 12, (A.y + B.y) / 2 + py * 12);
    }
    ctx.restore();
  }
  // ── Геометрические преобразования (образ точки p в ЛОКАЛЬНЫХ коорд окна fr) ──
  // xf: {kind, ...}. csym: центр c; asym: прямая line; rot: центр c, угол°;
  // trans: вектор a→b; homo: центр c, коэф k; spiral: центр c, угол°, k.
  function xfPtLocal(fr, id) { const e = elements.get(id); if (!(e && e.type === 'point')) return null; return frameMathToLocal(fr, e.data.mx || 0, e.data.my || 0); }
  function applyXform(fr, xf, p) {
    if (!xf) return null;
    if (xf.kind === 'csym') { const C = xfPtLocal(fr, xf.c); if (!C) return null; return { x: 2 * C.x - p.x, y: 2 * C.y - p.y }; }
    if (xf.kind === 'trans') { const A = xfPtLocal(fr, xf.a), B = xfPtLocal(fr, xf.b); if (!A || !B) return null; return { x: p.x + (B.x - A.x), y: p.y + (B.y - A.y) }; }
    if (xf.kind === 'rot' || xf.kind === 'spiral') {
      const C = xfPtLocal(fr, xf.c); if (!C) return null;
      const a = -(xf.angle || 0) * Math.PI / 180; // экранное «против часовой» при положительном угле
      const k = (xf.kind === 'spiral') ? (xf.k || 1) : 1;
      const dx = p.x - C.x, dy = p.y - C.y;
      const rx = dx * Math.cos(a) - dy * Math.sin(a), ry = dx * Math.sin(a) + dy * Math.cos(a);
      return { x: C.x + k * rx, y: C.y + k * ry };
    }
    if (xf.kind === 'homo') { const C = xfPtLocal(fr, xf.c); if (!C) return null; const k = xf.k || 1; return { x: C.x + k * (p.x - C.x), y: C.y + k * (p.y - C.y) }; }
    if (xf.kind === 'asym') {
      const line = elements.get(xf.line), G = line ? lineGeom(line) : null; if (!G) return null;
      const proj = (p.x - G.base.x) * G.u.x + (p.y - G.base.y) * G.u.y;
      const fx = G.base.x + proj * G.u.x, fy = G.base.y + proj * G.u.y;
      return { x: 2 * fx - p.x, y: 2 * fy - p.y };
    }
    if (xf.kind === 'inv') {
      // Инверсия: центр c, радиус = расстояние от c до точки through.
      // Считаем прямо в локальных пикселях окна — по x и y там один и тот же
      // масштаб (frameMathToLocal), поэтому R²/|OP| согласовано.
      const C = xfPtLocal(fr, xf.c), T = xfPtLocal(fr, xf.through);
      if (!C || !T) return null;
      const R2 = (T.x - C.x) * (T.x - C.x) + (T.y - C.y) * (T.y - C.y);
      const dx = p.x - C.x, dy = p.y - C.y, d2 = dx * dx + dy * dy;
      if (d2 < 1e-9 || R2 < 1e-9) return null;   // сам центр образа не имеет
      const k = R2 / d2;
      return { x: C.x + k * dx, y: C.y + k * dy };
    }
    return null;
  }
  function drawAngleShape(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const pos = ptPosFor(el), d = el.data, col = d.color || '#1f2937';
    const A = pos(d.a), V = pos(d.b), C = pos(d.c); if (!A || !V || !C) return;
    const a1 = Math.atan2(A.y - V.y, A.x - V.x), a2 = Math.atan2(C.y - V.y, C.x - V.x);
    let diff = a2 - a1; while (diff <= -Math.PI) diff += 2 * Math.PI; while (diff > Math.PI) diff -= 2 * Math.PI;
    const deg = Math.abs(diff) * 180 / Math.PI, R = 34, hl = selected.has(el.id);
    ctx.save();
    if (hl) { ctx.beginPath(); ctx.strokeStyle = '#4d7cfe'; ctx.lineWidth = (d.strokeWidth || 1.6) + 3; ctx.globalAlpha = 0.4; ctx.arc(V.x, V.y, R, a1, a1 + diff, diff < 0); ctx.stroke(); ctx.globalAlpha = 1; }
    // Заливка сектора с прозрачностью.
    const fo = Math.max(0, Math.min(1, d.fillOpacity || 0));
    if (fo > 0) { ctx.beginPath(); ctx.moveTo(V.x, V.y); ctx.arc(V.x, V.y, R, a1, a1 + diff, diff < 0); ctx.closePath(); ctx.fillStyle = hexToRgba(col, fo); ctx.fill(); }
    // Прямой угол (ровно 90°) обозначаем квадратиком вместо дуги и без числа —
    // это делает «обычный» инструмент, автоматически. (Ручной знак для любого угла —
    // отдельный инструмент mark_right, для стереометрии.)
    const isRight = Math.abs(deg - 90) < 0.5;
    ctx.strokeStyle = col; ctx.lineWidth = d.strokeWidth || 1.6; ctx.setLineDash(figureDash(d.style, d.strokeWidth || 2) || []);
    if (isRight) {
      ctx.beginPath(); pathRightAngle(ctx, A, V, C); ctx.stroke(); ctx.setLineDash([]);
    } else {
      // Дуги (1..3 — обозначают равные углы), стиль штриха из настроек.
      const n = Math.max(1, Math.min(3, d.arcCount || 1));
      ctx.beginPath(); pathEqArcs(ctx, V, a1, diff, n, R - (n - 1) * 4.5); ctx.stroke(); ctx.setLineDash([]);
      // Градусная мера (можно отключить).
      if (d.showDegree !== false) {
        const mid = a1 + diff / 2;
        ctx.fillStyle = col; ctx.font = '13px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(deg.toFixed(0) + '°', V.x + Math.cos(mid) * (R + 16), V.y + Math.sin(mid) * (R + 16));
      }
    }
    ctx.restore();
  }
  // Полуокружность: дуга от a0 против часовой на π (диаметр AB).
  function drawSemiShape(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const C = circleGeom(el); if (!C) return;
    ctx.beginPath();
    ctx.arc(C.cx, C.cy, C.r, C.a0, C.a0 + Math.PI, false);
    ctx.strokeShape(shape);
  }

  // ── Внешний вид точки: размер (плавающий 1..100) + форма ───────────────
  // Единая числовая шкала 1..100 для размеров (точка/подпись), чтобы разные
  // объекты можно было подогнать под одно число. 50 — базовый.
  function numSize(v) {
    if (typeof v === 'number') return v;
    if (typeof v === 'string') return { small: 30, normal: 50, large: 80 }[v] || 50;
    return 50;
  }
  function pointRadiusOf(d) { return Math.max(1, 1 + numSize(d.size) * 0.09); }      // 50→5.5px, 100→10px
  function labelFontOf(d) { return Math.max(6, 6 + numSize(d.labelSize) * 0.2); }    // 50→16px, 100→26px
  function drawPointGlyph(ctx, shape) {
    const parent = shape.getParent(); const el = parent && elements.get(parent.id()); if (!el) return;
    const d = el.data, r = pointRadiusOf(d), color = d.color || '#1f2937', sh = d.shape || 'dot';
    if (selected.has(el.id)) { ctx.beginPath(); ctx.arc(0, 0, r + 4, 0, 2 * Math.PI); ctx.strokeStyle = '#4d7cfe'; ctx.lineWidth = 2; ctx.stroke(); } // подсветка выделения
    ctx.lineWidth = 2; ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    if (sh === 'open') { ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.stroke(); }
    else if (sh === 'cross') { ctx.moveTo(-r, -r); ctx.lineTo(r, r); ctx.moveTo(-r, r); ctx.lineTo(r, -r); ctx.stroke(); }
    else if (sh === 'plus') { ctx.moveTo(-r, 0); ctx.lineTo(r, 0); ctx.moveTo(0, -r); ctx.lineTo(0, r); ctx.stroke(); }
    else if (sh === 'square') { ctx.rect(-r, -r, 2 * r, 2 * r); ctx.fill(); }
    else if (sh === 'diamond') { ctx.moveTo(0, -r); ctx.lineTo(r, 0); ctx.lineTo(0, r); ctx.lineTo(-r, 0); ctx.closePath(); ctx.fill(); }
    else if (sh === 'triangle') { ctx.moveTo(0, -r * 1.1); ctx.lineTo(r, r * 0.72); ctx.lineTo(-r, r * 0.72); ctx.closePath(); ctx.fill(); }
    else { ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.fill(); } // dot (без белой обводки)
  }
  function pointHitFunc(ctx, shape) { ctx.beginPath(); ctx.arc(0, 0, 12, 0, Math.PI * 2); ctx.closePath(); ctx.fillStrokeShape(shape); }
  function fmtCoord(v) { const r = Math.round(v * 100) / 100; return Math.abs(r) < 1e-9 ? 0 : r; }
  // Нижний индекс из цифр (₀₁₂…). Базовый объект — индекс 1, образ преобразования — +1.
  function subscriptNum(n) { const S = '₀₁₂₃₄₅₆₇₈₉'; return String(n).split('').map((c) => (c >= '0' && c <= '9') ? S[+c] : c).join(''); }
  // Базовая точка — без индекса (просто «A»); индекс появляется у образов преобразований (A₁, A₂…).
  function pointName(el) { const d = el.data; return (d.label || '') + (d.idx ? subscriptNum(d.idx) : ''); }
  // Имя не-точечного объекта (прямая/окружность/коника/вектор/функция…): первая
  // свободная строчная буква a,b,c… (у точек — заглавные метки, разные пространства).
  function nextObjName() {
    const used = new Set(); elements.forEach((e) => { if (e.data && e.data.name) used.add(e.data.name); });
    for (let i = 0; i < 26; i++) { const L = String.fromCharCode(97 + i); if (!used.has(L)) return L; }
    for (let k = 1; ; k++) { const L = 'a' + k; if (!used.has(L)) return L; }
  }
  function objName(e) { return (e && e.data && e.data.name) ? e.data.name : ''; }
  function odescHtml(e, desc) { const n = objName(e); return '<span class="fe-odesc">' + (n ? '<b>' + escapeHtml(n) + '</b>: ' : '') + escapeHtml(desc) + '</span>'; }
  function pointLabelText(el) {
    const d = el.data, name = pointName(el), mode = d.labelMode || 'name';
    if (mode === 'name') return name;
    const cx = d.frame ? (d.mx || 0) : (d.x || 0), cy = d.frame ? (d.my || 0) : (d.y || 0);
    const coords = '(' + fmtCoord(cx) + '; ' + fmtCoord(cy) + ')';
    if (mode === 'coords') return coords;
    return (name ? name + ' ' : '') + coords;
  }
  function updatePointLabel(el) {
    const n = nodes.get(el.id); if (!n) return; const lbl = n.findOne('.plabel'); if (!lbl) return;
    const fs = labelFontOf(el.data), lo = el.data.labelOff || { x: 0, y: 0 };
    lbl.text(pointLabelText(el));
    // Подпись видна, только если точка ЖИВЁТ В МАТОКНЕ: у точки на голой доске
    // буква не нужна.
    lbl.visible(!el.data.labelHidden && !!el.data.frame);
    lbl.fill(el.data.color || '#1f2937');
    lbl.fontSize(fs);
    lbl.x(8 + (lo.x || 0)); lbl.y(-(fs + 3) + (lo.y || 0));
  }

  // ── Стиль фигур (толщина + сплошная/пунктир/точки) ─────────────────────
  function figureDash(style, w) {
    if (style === 'dashed') return [Math.max(7, w * 3.5), Math.max(5, w * 2.5)];
    if (style === 'dotted') return [0.1, Math.max(4, w * 2.4)];
    return [];
  }
  function applyFigureVisual(el) {
    const n = nodes.get(el.id); if (!n) return;
    // Картинка, PDF, формула и текст рисуются как изображение, а у изображения
    // в Konva ЕСТЬ и strokeWidth, и dash — и без этой проверки свойства фигуры
    // ложились на них: получалась толстая пунктирная рамка вокруг картинки.
    // Ровно из этой дыры росла и прежняя чёрная обводка.
    if (el.type === 'image' || el.type === 'pdf' || el.type === 'latex' || el.type === 'text') return;
    const w = el.data.strokeWidth || 2;
    if (typeof n.strokeWidth === 'function') n.strokeWidth(w);
    if (typeof n.dash === 'function') n.dash(figureDash(el.data.style, w));
    if (typeof n.lineCap === 'function') n.lineCap('round'); // круглые концы (и точки в 'dotted')
  }

  // ── Показать / скрыть объект ───────────────────────────────────────────
  // data.hidden: объект есть, но не рисуется. revealHidden — режим «показать
  // скрытое» (полупрозрачно, чтобы можно было выделить и вернуть).
  let revealHidden = false;
  function nodeVisible(el) { return !((el.data && el.data.hidden) || el._condHide) || revealHidden; }
  function applyElVisibility(el) {
    const hid = !!((el.data && el.data.hidden) || el._condHide);
    // Таблицы, страницы, голосования и экран живут в DOM-слое, а не на холсте,
    // и до сих пор не скрывались вовсе: флаг ставился, а на экране ничего не
    // менялось. В режиме скрытия это выглядело бы как сломанная кнопка.
    const wi = widgetItems.get(el.id);
    if (wi && wi.wrapper) {
      wi.wrapper.style.display = (hid && !revealHidden) ? 'none' : '';
      wi.wrapper.style.opacity = (hid && revealHidden) ? '0.3' : '';
    }
    const n = nodes.get(el.id); if (!n || typeof n.visible !== 'function') return;
    // Чего хочет ПРИЛОЖЕНИЕ. Отдельно от того, попал ли объект в кадр:
    // если писать обе причины в один visible(), они затрут друг друга —
    // скрытый объект проявится при подъезде, а показанный пропадёт.
    n._appVisible = (!hid || revealHidden);
    setNodeShown(n);
    const baseOp = (el.data && el.data.marker) ? (el.data.opacity != null ? el.data.opacity : 0.4) : 1; // маркер — полупрозрачный, не затирать
    if (typeof n.opacity === 'function') n.opacity(hid && revealHidden ? 0.3 : baseOp);
    if (typeof n.listening === 'function') n.listening(!(hid && !revealHidden));
  }
  function setHidden(ids, hidden) {
    ids.forEach((id) => {
      const el = elements.get(id); if (!el) return;
      const before = clone(el); el.data.hidden = hidden ? true : undefined;
      applyElVisibility(el); histUpd(before, el); send({ action: 'element_update', element: el });
      if (hidden && selected.has(id)) selected.delete(id);
    });
    refreshTransformer(); syncAlgebra(); layer.batchDraw();
  }
  // Режим скрытия. Включён — скрытое проступает призраком, а щелчок по любому
  // объекту прячет его или возвращает. Выделение при входе сбрасываем: в этом
  // режиме щелчок означает «спрятать», а не «выбрать», и подсвеченная рамка
  // вокруг объектов только путала бы.
  let hideModeBackTool = null;
  function toggleRevealHidden() {
    revealHidden = !revealHidden;
    if (revealHidden) {
      clearSelection();
      // Щелчок прячет объект только инструментом «выделение»: с карандашом в
      // руке нажатие рисует линию. Берём инструмент сами, иначе человек жмёт
      // на объекты, а не происходит ничего.
      hideModeBackTool = tool;
      if (tool !== 'select') setTool('select');
    } else {
      // Возвращаем прежний инструмент — но только если человек сам его не
      // сменил, пока был в режиме.
      if (hideModeBackTool && tool === 'select') setTool(hideModeBackTool);
      hideModeBackTool = null;
    }
    elements.forEach((el) => applyElVisibility(el));
    const btn = document.getElementById('reveal-hidden'); if (btn) btn.classList.toggle('on', revealHidden);
    document.body.classList.toggle('board-hidemode', revealHidden);
    layer.batchDraw();
    boardHint(revealHidden
      ? 'Режим скрытия: нажимайте на объекты или обводите рамкой — прячем и возвращаем'
      : 'Обычный режим: скрытое снова не видно');
  }
  // Рамка в этом режиме переключает всё пойманное РАЗОМ: есть хоть один видимый
  // — прячем всё, иначе возвращаем всё. Иначе рамка половину прятала бы, а
  // половину возвращала, и предсказать результат было бы нельзя.
  function toggleHiddenInBox(box) {
    const ids = [];
    nodes.forEach((node, id) => {
      const el = elements.get(id);
      if (!el || el.type === 'frame') return;   // окно — не объект, а вместилище
      const b = node.getClientRect({ relativeTo: layer });
      if (rectsIntersect(box, b)) ids.push(id);
    });
    widgetItems.forEach((it, id) => {
      const d = it.el.data, w = it.wrapper.offsetWidth || 0, h = it.wrapper.offsetHeight || 0;
      if (!w && !h) return;
      if (rectsIntersect(box, { x: d.x || 0, y: d.y || 0, width: w, height: h })) ids.push(id);
    });
    if (!ids.length) return;
    const anyVisible = ids.some((id) => { const el = elements.get(id); return el && !(el.data && el.data.hidden); });
    setHidden(ids, anyVisible);
    boardHint((anyVisible ? 'Скрыто объектов: ' : 'Возвращено объектов: ') + ids.length);
  }

  function recomputeGeometry() {
    elements.forEach((el) => {
      if (el.type === 'point' && el.data.frame) {
        const fr = elements.get(el.data.frame), n = nodes.get(el.id);
        if (!(fr && n)) return;
        if (el.data.on && el.data.on.isect) {
          // ЖЁСТКО в пересечении двух фигур: позиция = решение по их уравнениям.
          // k — которая из двух точек. Нет пересечения → точку прячем.
          const o1 = elements.get(el.data.on.isect[0]), o2 = elements.get(el.data.on.isect[1]);
          const g1 = o1 ? curveGeom(o1) : null, g2 = o2 ? curveGeom(o2) : null;
          const pts = (g1 && g2) ? intersectCurves(g1, g2) : [];
          const P = pts[el.data.on.k || 0];
          if (P) {
            n.position(P); n.visible(nodeVisible(el));
            const m = frameLocalToMath(fr, P.x, P.y); el.data.mx = m.mx; el.data.my = m.my; // кэш
          } else if (n.visible()) { n.visible(false); }
        } else if (el.data.on && el.data.on.line) {
          // ЖЁСТКО на линии: позиция = base + t·u (в локальных коорд окна), t неизменен.
          const line = elements.get(el.data.on.line), G = line ? lineGeom(line) : null;
          if (G) {
            const t = el.data.on.t || 0, lx = G.base.x + G.u.x * t, ly = G.base.y + G.u.y * t;
            n.position({ x: lx, y: ly });
            const m = frameLocalToMath(fr, lx, ly); el.data.mx = m.mx; el.data.my = m.my; // кэш
          }
        } else if (el.data.on && el.data.on.circle) {
          // ЖЁСТКО на окружности: позиция = центр + r·(cos a, sin a), угол a неизменен.
          const circ = elements.get(el.data.on.circle), C = circ ? circleGeom(circ) : null;
          if (C) {
            const a = el.data.on.a || 0, lx = C.cx + C.r * Math.cos(a), ly = C.cy + C.r * Math.sin(a);
            n.position({ x: lx, y: ly });
            const m = frameLocalToMath(fr, lx, ly); el.data.mx = m.mx; el.data.my = m.my; // кэш
          }
        } else if (el.data.on && el.data.on.regpoly) {
          // ЖЁСТКО на вершине правильного многоугольника (индекс k).
          const host = elements.get(el.data.on.regpoly), vs = host ? regPolyVertices(host) : null;
          const V = vs && vs[el.data.on.k];
          if (V) {
            n.position(V); n.visible(nodeVisible(el));
            const m = frameLocalToMath(fr, V.x, V.y); el.data.mx = m.mx; el.data.my = m.my; // кэш
          } else if (n.visible()) { n.visible(false); }
        } else if (el.data.on && el.data.on.centroid) {
          // Центр масс (середина): среднее локальных координат исходных точек.
          let sx = 0, sy = 0, cnt = 0;
          el.data.on.centroid.forEach((pid) => { const pe = elements.get(pid); if (pe && pe.type === 'point' && pe.data.frame === el.data.frame) { const L = frameMathToLocal(fr, pe.data.mx || 0, pe.data.my || 0); sx += L.x; sy += L.y; cnt++; } });
          if (cnt) { const V = { x: sx / cnt, y: sy / cnt }; n.position(V); const m = frameLocalToMath(fr, V.x, V.y); el.data.mx = m.mx; el.data.my = m.my; }
        } else if (el.data.on && el.data.on.ratio) {
          // Деление отрезка AB в отношении t: P = A + t·(B−A).
          const R = el.data.on.ratio, A = elements.get(R.a), B = elements.get(R.b);
          if (A && B && A.data.frame === el.data.frame && B.data.frame === el.data.frame) {
            const la = frameMathToLocal(fr, A.data.mx || 0, A.data.my || 0), lb = frameMathToLocal(fr, B.data.mx || 0, B.data.my || 0);
            const t = R.t || 0, V = { x: la.x + t * (lb.x - la.x), y: la.y + t * (lb.y - la.y) };
            n.position(V); const m = frameLocalToMath(fr, V.x, V.y); el.data.mx = m.mx; el.data.my = m.my;
          }
        } else if (el.data.on && el.data.on.xform) {
          // Образ преобразования: T применяется к позиции исходной точки.
          const src = elements.get(el.data.on.src);
          if (src && src.type === 'point' && src.data.frame === el.data.frame) {
            const sp = frameMathToLocal(fr, src.data.mx || 0, src.data.my || 0);
            const V = applyXform(fr, el.data.on.xform, sp);
            if (V) { n.position(V); n.visible(nodeVisible(el)); const m = frameLocalToMath(fr, V.x, V.y); el.data.mx = m.mx; el.data.my = m.my; }
            else if (n.visible()) n.visible(false);
          }
        } else {
          // привязанная к окну точка: позиция = матем. коорды → локальные px окна
          const L = frameMathToLocal(fr, el.data.mx || 0, el.data.my || 0); n.position({ x: L.x, y: L.y });
        }
        updatePointLabel(el);
      } else if (el.type === 'point' && el.data.on) {
        const circle = elements.get(el.data.on.c);
        if (circle && circle.type === 'circle') {
          const r = circle.data.r || 0, a = el.data.on.a || 0;
          el.data.x = circle.data.x + r * Math.cos(a);
          el.data.y = circle.data.y + r * Math.sin(a);
          const n = nodes.get(el.id);
          if (n) n.position({ x: el.data.x, y: el.data.y });
        }
      } else if (CONSTRUCT_LINES.indexOf(el.type) >= 0) {
        // Линия рисуется sceneFunc'ом по опорам при каждой перерисовке слоя —
        // отдельно точки задавать не нужно (layer.batchDraw перерисует форму).
      } else if (el.type === 'vector') {
        const n = nodes.get(el.id), pts = vecEnds(el); if (n && pts) n.points(pts);
      } else if (isFilledPoly(el.type)) {
        const n = nodes.get(el.id), pts = shapeOutline(el);
        if (n && pts) n.points(pts);
      } else if (el.type === 'circ') {
        const n = nodes.get(el.id), C = circleGeom(el);
        if (n) {
          if (!C) { if (n.visible()) n.visible(false); }
          else { n.visible(nodeVisible(el)); if (el.data.kind !== 'semi') { n.position({ x: C.cx, y: C.cy }); n.radius(C.r); } }
        }
      } else if (el.type === 'measure') {
        const n = nodes.get(el.id); if (!n) return;
        const info = measureInfo(el);
        if (info) {
          const t = n.findOne('.mtext'); if (t && t.text() !== info.text) t.text(info.text);
          const off = el.data.off || { x: 12, y: -14 };
          n.position({ x: info.x + off.x, y: info.y + off.y });
          n.visible(nodeVisible(el));
        } else if (n.visible()) n.visible(false);
      }
    });
    updateTraces();
    applyConditions();
  }
  // ── Именованные значения окна (для условий/динам. текста) ──────────────
  // Имя → число: ползунки, параметры окна, измерения. Точки — не число, поэтому
  // доступны через функции x(A)/y(A)/dist(A,B) прямо в вычислителе (см. compileNum).
  function frameVars(frame) {
    const vars = {}, pts = {}, fid = frame && frame.id;
    elements.forEach((e) => {
      if (!e.data) return;
      if (e.type === 'slider' && e.data.name) vars[e.data.name] = Number(e.data.value);
      else if (e.type === 'measure' && e.data.name) { const v = measureValue(e); if (v != null && isFinite(v)) vars[e.data.name] = v; }
      else if (e.type === 'point' && e.data.label && (!fid || e.data.frame === fid)) pts[((e.data.label || '') + (e.data.idx ? e.data.idx : '')).toUpperCase()] = { x: e.data.mx || 0, y: e.data.my || 0 };
    });
    if (frame && frame.data && frame.data.params) for (const k in frame.data.params) vars[k] = Number(frame.data.params[k].v);
    vars._pts = pts;
    return vars;
  }
  // ── Условная видимость: data.showIf — булево выражение; ложь → объект скрыт ──
  function applyConditions() {
    const varCache = new Map();
    const varsFor = (fr) => { const key = fr ? fr.id : '_'; if (!varCache.has(key)) varCache.set(key, frameVars(fr)); return varCache.get(key); };
    let changed = false;
    elements.forEach((el) => {
      if (!el.data) return;
      const src = el.data.showIf;
      if (!src) { if (el._condHide) { el._condHide = false; applyElVisibility(el); changed = true; } el._condFn = null; el._condSrc = null; return; }
      if (el._condSrc !== src) { el._condSrc = src; el._condFn = compileNum(src); }
      let vis = true;
      if (el._condFn) { try { const r = el._condFn(varsFor(el.data.frame ? elements.get(el.data.frame) : null)); vis = isNaN(r) ? true : !!r; } catch (_) { vis = true; } }
      const hide = !vis;
      if (!!el._condHide !== hide) { el._condHide = hide; applyElVisibility(el); changed = true; }
    });
    if (changed) layer.batchDraw();
    refreshDynamicTexts();
  }
  // ── Динамический текст: {выражение} в тексте → живое значение ────────────
  function renderDynamicText(html, frame) {
    if (!html || html.indexOf('{') < 0) return html;
    const env = frameVars(frame);
    return html.replace(/\{([^{}]+)\}/g, (m, expr) => {
      const f = compileNum(expr); if (!f) return m; // не выражение — оставляем как есть
      let v; try { v = f(env); } catch (_) { return m; }
      return isFinite(v) ? fmtMeasure(v) : m;
    });
  }
  function refreshDynamicTexts() {
    if (typeof widgetItems === 'undefined') return;
    widgetItems.forEach((it) => {
      if (!it || !it.isTbox || it.editing) return;
      const el = it.el; if (!el || !el.data || (el.data.html || '').indexOf('{') < 0) return;
      if (document.activeElement === it.ed) return;
      const h = sanitizeHtml(renderDynamicText(el.data.html || '', el.data.frame ? elements.get(el.data.frame) : null));
      if (it.ed.innerHTML !== h) it.ed.innerHTML = h;
    });
  }
  // ── След точки (locus): точка с data.trace оставляет траекторию (локально) ──
  const traceLines = new Map(); // pointId → Konva.Line (не сохраняется, копится при движении)
  function ensureTrace(el) {
    if (!el || !el.data.trace) { const tl = traceLines.get(el && el.id); if (tl) { tl.destroy(); traceLines.delete(el.id); } return; }
    if (!traceLines.has(el.id)) { const tl = new Konva.Line({ points: [], stroke: el.data.color || '#e7505a', strokeWidth: 1.5, opacity: 0.85, listening: false, lineCap: 'round', lineJoin: 'round' }); layer.add(tl); tl.moveToBottom(); traceLines.set(el.id, tl); }
  }
  function updateTraces() {
    traceLines.forEach((tl, id) => {
      const el = elements.get(id);
      if (!el || !el.data.trace) { tl.destroy(); traceLines.delete(id); return; }
      const w = pointWorld(el); if (!w) return;
      const pts = tl.points(), n = pts.length;
      if (n < 2 || Math.hypot(w.x - pts[n - 2], w.y - pts[n - 1]) > 0.5) { pts.push(w.x, w.y); if (pts.length > 1600) pts.splice(0, pts.length - 1600); tl.points(pts); tl.stroke(el.data.color || '#e7505a'); }
    });
  }
  function toggleTrace(id) {
    const el = elements.get(id); if (!el || el.type !== 'point') return;
    const before = clone(el); const on = !el.data.trace;
    el.data.trace = on ? true : undefined;
    const tl = traceLines.get(id); if (tl) { tl.destroy(); traceLines.delete(id); } // сброс траектории
    ensureTrace(el); updateTraces();
    histUpd(before, el); send({ action: 'element_update', element: el }); layer.batchDraw();
    boardHint(on ? 'След включён — двигайте точку' : 'След выключен');
  }
  // Перетаскивание подписи-измерения: запоминаем смещение от точки привязки.
  function onMeasureDragEnd(id, node) {
    const el = elements.get(id); if (!el) return;
    const before = clone(el), info = measureInfo(el);
    if (info) el.data.off = { x: node.x() - info.x, y: node.y() - info.y };
    histUpd(before, el); send({ action: 'element_update', element: el });
    commitDragFollowers(id); dragStart = null; // синкнуть ведомых группы и сбросить
  }

  // Выбор/создание точки для построения: ближайшая существующая или новая.
  let pendingPicks = [];
  function pickPointId(p) {
    const THRESH = 14 / stage.scaleX();
    let best = null, bd = THRESH;
    elements.forEach((el) => { if (el.type !== 'point') return; const w = pointWorld(el); const d = Math.hypot(p.x - w.x, p.y - w.y); if (d < bd) { bd = d; best = el; } });
    if (best) return best.id;
    return newPointAt(p).id;
  }
  // Существующая точка под курсором (для приоритета выделения над линиями/фоном).
  function pickSelectablePointNear(w) {
    const TH = 12 / stage.scaleX();
    let best = null, bd = TH;
    elements.forEach((el) => { if (el.type !== 'point' || (el.data.hidden && !revealHidden)) return; const wp = pointWorld(el); const d = Math.hypot(w.x - wp.x, w.y - wp.y); if (d < bd) { bd = d; best = el; } });
    return best;
  }
  // Точка внутри многоугольника (луч-алгоритм; flat = [x0,y0,x1,y1,...]).
  function pointInPolygon(p, flat) {
    let inside = false; const n = flat.length / 2;
    for (let i = 0, j = n - 1; i < n; j = i++) {
      const xi = flat[2 * i], yi = flat[2 * i + 1], xj = flat[2 * j], yj = flat[2 * j + 1];
      if (((yi > p.y) !== (yj > p.y)) && (p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }
  // Многоугольник (обычный/правильный) под курсором — по заливке (клик внутри).
  function distToPolyEdges(p, flat) {
    let best = Infinity; const n = flat.length / 2;
    for (let i = 0, j = n - 1; i < n; j = i++) { const d = distPointToSeg(p, { x: flat[2 * j], y: flat[2 * j + 1] }, { x: flat[2 * i], y: flat[2 * i + 1] }); if (d < best) best = d; }
    return best;
  }
  // ЕДИНЫЙ выбор объекта под курсором (геометрически, не полагаясь на hit-граф):
  // точка → ближайшая граница (линия/окружность-кольцо/ребро многоугольника) → заливка многоугольника.
  // Расстояние клика (в лок. коорд окна) до дуги угла, если попадает в его сектор.
  function angleArcDist(el, lp) {
    const pos = ptPosFor(el), A = pos(el.data.a), V = pos(el.data.b), C = pos(el.data.c);
    if (!A || !V || !C) return Infinity;
    const R = 34, dr = Math.abs(Math.hypot(lp.x - V.x, lp.y - V.y) - R);
    const a1 = Math.atan2(A.y - V.y, A.x - V.x), a2 = Math.atan2(C.y - V.y, C.x - V.x);
    let diff = a2 - a1; while (diff <= -Math.PI) diff += 2 * Math.PI; while (diff > Math.PI) diff -= 2 * Math.PI;
    const aw = Math.atan2(lp.y - V.y, lp.x - V.x);
    let da = aw - a1; while (da <= -Math.PI) da += 2 * Math.PI; while (da > Math.PI) da -= 2 * Math.PI;
    const within = diff >= 0 ? (da >= -0.2 && da <= diff + 0.2) : (da <= 0.2 && da >= diff - 0.2);
    return within ? dr : Infinity;
  }
  function pickObjectAtWorld(w) {
    const p = pickSelectablePointNear(w); if (p) return p; // точки — высший приоритет
    const fr = frameAtWorld(w.x, w.y, true); if (!fr) return null;
    const lw = { x: w.x - fr.data.x, y: w.y - fr.data.y }, TH = 12 / stage.scaleX();
    let best = null, bd = TH, insidePoly = null;
    elements.forEach((el) => {
      if (el.data.frame !== fr.id || (el.data.hidden && !revealHidden)) return;
      if (isFilledPoly(el.type)) { const o = shapeOutline(el); if (o) { if (pointInPolygon(lw, o)) insidePoly = el; const d = distToPolyEdges(lw, o); if (d < bd) { bd = d; best = el; } } return; }
      let d = Infinity;
      if (CONSTRUCT_LINES.indexOf(el.type) >= 0) { const P = constructionParams(el); if (P) d = P.seg ? distPointToSeg(lw, { x: P.seg[0], y: P.seg[1] }, { x: P.seg[2], y: P.seg[3] }) : distPointToLine(lw, P.base, P.u); }
      else if (el.type === 'circ') { const C = circleGeom(el); if (C) { d = Math.abs(Math.hypot(lw.x - C.cx, lw.y - C.cy) - C.r); if (C.semi && !pointOnArc(C, lw)) d += 1e6; } }
      else if (el.type === 'angle') { d = angleArcDist(el, lw); }
      if (d < bd) { bd = d; best = el; }
    });
    return best || insidePoly; // граница ближе → её; иначе — заливку многоугольника
  }
  // Новая точка: привязанная к активному окну (если курсор внутри) или свободная.
  function newPointAt(p) {
    const fr = frameForCreation();
    let el;
    if (fr) {
      // Приоритет: пересечение двух линий → точка на линии → свободная в окне.
      const X = pickIntersectionAt(fr, p);
      // На месте пересечения уже есть точка — берём её, новую не плодим.
      if (X) { const ex = existingPointAtLocal(fr, X.p.x, X.p.y); if (ex) return ex; }
      const line = X ? null : pickLineAt(p);
      const info = line ? onLineInfo(fr, line, p) : null;
      let m, on = null;
      if (X) { m = frameLocalToMath(fr, X.p.x, X.p.y); on = { isect: [X.a, X.b], k: X.k || 0 }; }
      else if (info) { m = info; on = info.on; }
      else { m = frameWorldToMath(fr, p.x, p.y); }
      const data = { frame: fr.id, mx: m.mx, my: m.my, label: nextPointLabel(), color: strokeColor };
      if (on) data.on = on;
      el = { id: uuid(), type: 'point', z: 0, data: data };
    } else {
      const s = snapPoint(p);
      el = { id: uuid(), type: 'point', z: 0, data: { x: s.x, y: s.y, label: nextPointLabel(), color: strokeColor, on: s.on || undefined } };
    }
    applyTypeDefaults(el.data, 'point'); // новые точки — по настройкам типа
    // Привязка к сетке при СОЗДАНИИ (для свободной точки в окне): округляем матем. коорды.
    if (el.data.snap && el.data.frame && !el.data.on) {
      el.data.mx = Math.round(el.data.mx * 2) / 2;
      el.data.my = Math.round(el.data.my * 2) / 2;
    }
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    return el;
  }
  function createConstruction(type, ids) {
    const el = { id: uuid(), type, z: 0, data: { color: strokeColor, strokeWidth: Math.max(1.5, strokeWidth), name: nextObjName() } };
    if (type === 'conic') { el.data.pts = ids.slice(0, 5); } // коника по 5 точкам — хранит массив точек, как многоугольник
    else { el.data.a = ids[0]; el.data.b = ids[1]; if (ids.length >= 3) el.data.c = ids[2]; }
    applyTypeDefaults(el.data, type === 'segment' ? 'segment' : type === 'angle' ? 'angle' : 'line'); // по настройкам своего типа
    // Привязка к окну: если все опорные точки принадлежат одному окну —
    // построение тоже его (рисуется в коорд. окна и обрезается границей).
    const frs = ids.map((id) => { const e = elements.get(id); return e && e.data ? e.data.frame : null; });
    const commonFrame = (frs[0] && frs.every((f) => f === frs[0])) ? frs[0] : null;
    // Бесконечное построение без общего окна не создаём (страховка; обычно
    // отсекается ещё на кликах в handleConstructPick).
    if (INFINITE_CONSTRUCTS.indexOf(type) >= 0 && !commonFrame) return;
    if (commonFrame) el.data.frame = commonFrame;
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
    // Опорные точки — поверх линии построения, чтобы их можно было схватить.
    if (el.data.frame) {
      const fnode = nodes.get(el.data.frame), h = fnode && fnode.findOne('.fheader');
      ids.forEach((pid) => { const n = nodes.get(pid); if (n && h) n.zIndex(h.zIndex()); }); // над линией, под шапкой
    } else {
      ids.forEach((pid) => { const n = nodes.get(pid); if (n) n.moveToTop(); });
    }
    layer.batchDraw();
  }
  // Вектор AB (стрелка, следует за точками).
  let vectorPicks = [];
  function createVector(ids) {
    const el = { id: uuid(), type: 'vector', z: 0, data: { a: ids[0], b: ids[1], color: strokeColor, strokeWidth: Math.max(1.5, strokeWidth), name: nextObjName() } };
    const frs = ids.map((id) => { const e = elements.get(id); return e && e.data ? e.data.frame : null; });
    const cf = (frs[0] && frs.every((f) => f === frs[0])) ? frs[0] : null; if (cf) el.data.frame = cf;
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
    if (el.data.frame) { const fn = nodes.get(el.data.frame), h = fn && fn.findOne('.fheader'); ids.forEach((pid) => { const n = nodes.get(pid); if (n && h) n.zIndex(h.zIndex()); }); }
    else ids.forEach((pid) => { const n = nodes.get(pid); if (n) n.moveToTop(); });
    layer.batchDraw();
  }
  function handleVectorPick(w) {
    const id = pickPointId(w); if (!id) return;
    vectorPicks.push(id);
    if (vectorPicks.length >= 2) { const ids = vectorPicks.slice(); vectorPicks = []; createVector(ids); }
    else boardHint('Теперь конец вектора');
  }
  // ── Анализ функций: выбор графика под курсором и создание элементов ────
  function pickFuncAt(w) {
    const fr = frameAtWorld(w.x, w.y, true); if (!fr) return null;
    const m = planeMap(fr), env = frameParamEnv(fr), lx = w.x - fr.data.x, ly = w.y - fr.data.y, planeX = m.P2X(lx);
    let best = null, bd = 14 / stage.scaleX();
    elements.forEach((e) => { if (e.type !== 'func' || e.data.frame !== fr.id) return; const fn = funcFnOf(e.id); if (!fn) return; let y; try { y = fn(planeX, env); } catch (err) { return; } if (!isFinite(y)) return; const dpx = Math.abs(m.Y2P(y) - ly); if (dpx < bd) { bd = dpx; best = { func: e, x0: planeX, fr: fr }; } });
    return best;
  }
  function createAnalysis(type, data) { const el = { id: uuid(), type: type, z: 0, data: data }; upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); layer.batchDraw(); if (typeof syncAlgebra === 'function') syncAlgebra(); }
  let areaPicks = [], fintPicks = [];
  function handleTangentPick(w) { const p = pickFuncAt(w); if (!p) { boardHint('Кликните по графику функции'); return; } createAnalysis('ftangent', { frame: p.fr.id, func: p.func.id, x0: p.x0 }); boardHint('Касательная построена'); }
  function handleAreaPick(w) {
    const p = pickFuncAt(w); if (!p) { boardHint('Кликните по графику функции'); return; }
    if (!areaPicks.length) { areaPicks = [{ func: p.func.id, frame: p.fr.id, x: p.x0 }]; boardHint('Теперь вторая граница (по этому же графику)'); return; }
    const a = areaPicks[0]; areaPicks = []; createAnalysis('farea', { frame: a.frame, func: a.func, a: a.x, b: p.x0 }); boardHint('Площадь построена');
  }
  function handleFIntersectPick(w) {
    const p = pickFuncAt(w); if (!p) { boardHint('Кликните по графику функции'); return; }
    if (!fintPicks.length) { fintPicks = [p.func.id, p.fr.id]; boardHint('Теперь второй график'); return; }
    const f = fintPicks[0]; const fid = fintPicks[1]; fintPicks = []; if (f === p.func.id) { boardHint('Нужны два разных графика'); return; }
    createAnalysis('fintersect', { frame: fid, f: f, g: p.func.id }); boardHint('Точки пересечения отмечены');
  }
  // ── Неравенства / области ──────────────────────────────────────────────
  function createRegion(frameId, parts) { const el = { id: uuid(), type: 'region', z: 0, data: { frame: frameId, parts: parts, color: '#2e86de' } }; upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); layer.batchDraw(); if (typeof syncAlgebra === 'function') syncAlgebra(); return el; }
  function handleRegionPick(w) { const p = pickFuncAt(w); if (!p) { boardHint('Кликните по графику функции'); return; } createRegion(p.fr.id, [{ func: p.func.id, sense: 'gt' }]); boardHint('Область y ≥ f(x) закрашена — «выше/ниже» переключается в панели «Алгебра окна»'); }
  let regionParts = [], regionFrame = null;
  function handleRegionSysPick(w) {
    const p = pickFuncAt(w); if (!p) { boardHint('Кликните по графику функции'); return; }
    if (regionFrame && regionFrame !== p.fr.id) { boardHint('Все условия — в одном окне'); return; }
    regionFrame = p.fr.id; regionParts.push({ func: p.func.id, sense: 'gt' });
    boardHint('Условий: ' + regionParts.length + '. Ещё график — или Enter, чтобы закрасить систему');
  }
  function finishRegionSys() { if (!regionParts.length || !regionFrame) { regionParts = []; regionFrame = null; return; } createRegion(regionFrame, regionParts.slice()); regionParts = []; regionFrame = null; setTool('select'); boardHint('Система неравенств закрашена'); }
  function toggleRegionSense(regionId, partIdx) {
    const el = elements.get(regionId); if (!el || !el.data.parts || !el.data.parts[partIdx]) return;
    el.data.parts[partIdx].sense = el.data.parts[partIdx].sense === 'gt' ? 'lt' : 'gt';
    send({ action: 'element_update', element: el }); layer.batchDraw(); if (activeFrameId) renderFuncList(activeFrameId);
  }
  // Перпендикуляр/параллель «по линии»: строит объект со ссылкой на линию-основу и точку.
  function createPerpParallelByLine(type, lineId, throughId, frameId) {
    const el = { id: uuid(), type, z: 0, data: { color: strokeColor, strokeWidth: Math.max(1.5, strokeWidth), line: lineId, through: throughId, frame: frameId } };
    applyTypeDefaults(el.data, 'line'); // новые прямые — по настройкам типа
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
    const fnode = nodes.get(frameId), h = fnode && fnode.findOne('.fheader');
    const n = nodes.get(throughId); if (n && h) n.zIndex(h.zIndex()); // точка над линией
    layer.batchDraw();
  }
  // ── Построение окружностей по точкам ───────────────────────────────────
  const CIRCLE_PICKS = { circ_cp: 2, circ_cr: 1, circ_3: 3, semi: 2, compass: 3 };
  const CIRCLE_KIND = { circ_cp: 'cp', circ_cr: 'cr', circ_3: 'c3', semi: 'semi', compass: 'compass' };
  function createCircle(kind, ids, extra) {
    const el = { id: uuid(), type: 'circ', z: 0, data: { kind: kind, color: strokeColor, strokeWidth: Math.max(1.5, strokeWidth), name: nextObjName() } };
    applyTypeDefaults(el.data, 'circle'); // новые окружности — по настройкам типа
    if (kind === 'cp') { el.data.center = ids[0]; el.data.through = ids[1]; }
    else if (kind === 'cr') { el.data.center = ids[0]; el.data.r = extra.r; }
    else if (kind === 'c3') { el.data.a = ids[0]; el.data.b = ids[1]; el.data.c = ids[2]; }
    else if (kind === 'semi') { el.data.a = ids[0]; el.data.b = ids[1]; }
    else if (kind === 'compass') { el.data.a = ids[0]; el.data.b = ids[1]; el.data.center = ids[2]; }
    // Привязка к окну, если все опорные точки в одном (окружность конечна — но
    // живёт в координатах окна, чтобы двигаться с плоскостью и пересекаться).
    const frs = ids.map((id) => { const e = elements.get(id); return e && e.data ? e.data.frame : null; });
    const commonFrame = (frs[0] && frs.every((f) => f === frs[0])) ? frs[0] : null;
    if (commonFrame) el.data.frame = commonFrame;
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
    if (el.data.frame) { const fnode = nodes.get(el.data.frame), h = fnode && fnode.findOne('.fheader'); ids.forEach((pid) => { const n = nodes.get(pid); if (n && h) n.zIndex(h.zIndex()); }); }
    else { ids.forEach((pid) => { const n = nodes.get(pid); if (n) n.moveToTop(); }); }
    layer.batchDraw();
  }
  function handleCirclePick() {
    pendingPicks.push(pickPointId(worldPoint()));
    if (tool === 'circ_cr') { // центр задан — спрашиваем радиус
      const picks = pendingPicks; pendingPicks = [];
      uiPrompt('Радиус окружности (в единицах окна):', '2').then((txt) => {
        const r = parseFloat((txt || '').replace(',', '.'));
        if (isFinite(r) && r > 0) createCircle('cr', picks, { r: r });
      });
      return;
    }
    if (pendingPicks.length >= CIRCLE_PICKS[tool]) { createCircle(CIRCLE_KIND[tool], pendingPicks); pendingPicks = []; }
  }
  // ── Многоугольник по вершинам ──────────────────────────────────────────
  function createPolygon(ids) {
    const el = { id: uuid(), type: 'polygon', z: 0, data: { pts: ids.slice(), color: strokeColor, strokeWidth: Math.max(1.5, strokeWidth), name: nextObjName() } };
    applyTypeDefaults(el.data, 'polygon');
    const frs = ids.map((id) => { const e = elements.get(id); return e && e.data ? e.data.frame : null; });
    const commonFrame = (frs[0] && frs.every((f) => f === frs[0])) ? frs[0] : null;
    if (commonFrame) el.data.frame = commonFrame;
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
    // Вершины — поверх многоугольника, чтобы их можно было схватить.
    if (el.data.frame) { const fnode = nodes.get(el.data.frame), h = fnode && fnode.findOne('.fheader'); ids.forEach((pid) => { const n = nodes.get(pid); if (n && h) n.zIndex(h.zIndex()); }); }
    else { ids.forEach((pid) => { const n = nodes.get(pid); if (n) n.moveToTop(); }); }
    layer.batchDraw();
  }
  let polyPicks = [], polyPreview = null;
  function updatePolyPreview(cursorWorld) {
    if (!polyPicks.length) { if (polyPreview) { polyPreview.destroy(); polyPreview = null; layer.batchDraw(); } return; }
    if (!polyPreview) { polyPreview = new Konva.Line({ points: [], stroke: '#4d7cfe', strokeWidth: 1.5, dash: [6, 4], listening: false }); layer.add(polyPreview); }
    const flat = [];
    polyPicks.forEach((id) => { const e = elements.get(id); if (e && e.type === 'point') { const w = pointWorld(e); flat.push(w.x, w.y); } });
    if (cursorWorld) flat.push(cursorWorld.x, cursorWorld.y);
    polyPreview.points(flat); polyPreview.moveToTop(); layer.batchDraw();
  }
  function clearPolyPicks() { polyPicks = []; if (polyPreview) { polyPreview.destroy(); polyPreview = null; } layer.batchDraw(); }
  function finishPolygon() { if (polyPicks.length >= 3) createPolygon(polyPicks); clearPolyPicks(); }
  function handlePolygonPick() {
    const w = worldPoint();
    // Замыкание: клик по ПЕРВОЙ вершине (при ≥3 вершинах).
    if (polyPicks.length >= 3) {
      const first = elements.get(polyPicks[0]);
      if (first) { const fp = pointWorld(first); if (Math.hypot(w.x - fp.x, w.y - fp.y) < 14 / stage.scaleX()) { finishPolygon(); return; } }
    }
    const id = pickPointId(w);
    if (polyPicks[polyPicks.length - 1] !== id) polyPicks.push(id); // не дублируем ту же вершину подряд
    updatePolyPreview(null);
  }
  // ── Правильный многоугольник (центр+вершина / две вершины) ──────────────
  const REGPOLY_KIND = { regpoly_center: 'center', regpoly_edge: 'edge' };
  function createRegPoly(kind, ids, n) {
    const el = { id: uuid(), type: 'regpoly', z: 0, data: { kind: kind, n: n, color: strokeColor, strokeWidth: Math.max(1.5, strokeWidth), name: nextObjName() } };
    applyTypeDefaults(el.data, 'polygon'); // общие дефолты с многоугольником
    if (kind === 'center') { el.data.center = ids[0]; el.data.vertex = ids[1]; }
    else { el.data.a = ids[0]; el.data.b = ids[1]; }
    const frs = ids.map((id) => { const e = elements.get(id); return e && e.data ? e.data.frame : null; });
    const commonFrame = (frs[0] && frs.every((f) => f === frs[0])) ? frs[0] : null;
    if (commonFrame) el.data.frame = commonFrame;
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
    // Точки-вершины: управляющие (center: vertex=k0; edge: a=k0,b=k1) уже есть,
    // остальные создаём как производные точки on:{regpoly,k} — по ним строят диагонали.
    const startK = (kind === 'center') ? 1 : 2;
    const vptIds = [];
    for (let k = startK; k < n; k++) {
      const vp = { id: uuid(), type: 'point', z: 0, data: { frame: el.data.frame, on: { regpoly: el.id, k: k }, label: nextPointLabel(), color: strokeColor } };
      applyTypeDefaults(vp.data, 'point');
      upsertNode(vp); send({ action: 'element_add', element: vp }); histAdd(vp);
      vptIds.push(vp.id);
    }
    recomputeGeometry();
    // Все точки (управляющие + вершины) — поверх фигуры, чтобы их можно было схватить/кликнуть.
    const allPts = ids.concat(vptIds);
    if (el.data.frame) { const fnode = nodes.get(el.data.frame), h = fnode && fnode.findOne('.fheader'); allPts.forEach((pid) => { const p = nodes.get(pid); if (p && h) p.zIndex(h.zIndex()); }); }
    else { allPts.forEach((pid) => { const p = nodes.get(pid); if (p) p.moveToTop(); }); }
    layer.batchDraw();
  }
  function handleRegPolyPick() {
    pendingPicks.push(pickPointId(worldPoint()));
    if (pendingPicks.length >= 2) {
      const picks = pendingPicks; pendingPicks = []; const kind = REGPOLY_KIND[tool];
      uiPrompt('Число сторон правильного многоугольника:', '5').then((txt) => {
        const n = parseInt((txt || '').trim(), 10);
        if (isFinite(n) && n >= 3) createRegPoly(kind, picks, Math.min(200, n));
      });
    }
  }
  // ── Производная точка со ссылками (центр масс / деление отрезка) ─────────
  function createDerivedPoint(onData, ids) {
    const frs = ids.map((id) => { const e = elements.get(id); return e && e.data ? e.data.frame : null; });
    const commonFrame = (frs[0] && frs.every((f) => f === frs[0])) ? frs[0] : null;
    if (!commonFrame) { boardHint('Опорные точки должны быть в одном окне'); return null; }
    const el = { id: uuid(), type: 'point', z: 0, data: { frame: commonFrame, on: onData, label: nextPointLabel(), color: strokeColor } };
    applyTypeDefaults(el.data, 'point');
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
    const fnode = nodes.get(commonFrame), h = fnode && fnode.findOne('.fheader');
    ids.forEach((pid) => { const p = nodes.get(pid); if (p && h) p.zIndex(h.zIndex()); });
    const self = nodes.get(el.id); if (self && h) self.zIndex(h.zIndex());
    layer.batchDraw();
    return el;
  }
  // Середина / центр масс: копим точки, Enter — построить (≥2). Esc — отмена.
  let midPicks = [];
  function handleMidpointPick() {
    const id = pickPointId(worldPoint());
    if (midPicks[midPicks.length - 1] !== id) midPicks.push(id);
    boardHint(midPicks.length < 2 ? 'Ещё точки; Enter — построить центр' : 'Enter — построить центр (или ещё точки)');
  }
  function finishMidpoint() {
    if (midPicks.length >= 2) createDerivedPoint({ centroid: midPicks.slice() }, midPicks);
    midPicks = [];
  }
  // Деление отрезка AB в отношении: 2 точки + запрос m:n или числа t.
  function parseRatio(s) {
    s = (s || '').trim(); if (!s) return null;
    if (s.indexOf(':') >= 0) { const parts = s.split(':').map((x) => parseFloat(x.replace(',', '.'))); const m = parts[0], nn = parts[1]; if (isFinite(m) && isFinite(nn) && (m + nn) !== 0) return m / (m + nn); return null; }
    const v = parseFloat(s.replace(',', '.')); return isFinite(v) ? v : null;
  }
  function handleRatioPick() {
    pendingPicks.push(pickPointId(worldPoint()));
    if (pendingPicks.length >= 2) {
      const picks = pendingPicks; pendingPicks = [];
      uiPrompt('Деление отрезка A→B: отношение m:n или число t (0..1):', '1:1').then((txt) => {
        const t = parseRatio(txt);
        if (t != null) createDerivedPoint({ ratio: { a: picks[0], b: picks[1], t: t } }, picks);
      });
    }
  }
  // ── Преобразования: образы точек и фигур (связаны с источником через on:{xform}) ──
  // Опорные точки фигуры (какие переносим/образуем).
  // Образ точки src под преобразованием xf (переиспользуем через pmap).
  function imagePointOf(srcId, xf, pmap) {
    if (pmap[srcId]) return pmap[srcId];
    const src = elements.get(srcId); if (!src || src.type !== 'point') return null;
    // Образ наследует БУКВУ источника, а индекс = индекс источника + 1 (A₁→A₂→A₃…).
    const el = { id: uuid(), type: 'point', z: 0, data: { frame: src.data.frame, on: { xform: xf, src: srcId }, label: src.data.label || nextPointLabel(), idx: (src.data.idx || 0) + 1, color: strokeColor } };
    applyTypeDefaults(el.data, 'point');
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    pmap[srcId] = el.id;
    return el.id;
  }
  // Отсчёты исходной кривой в локальных координатах окна — по ним строится
  // образ при инверсии. Возвращаем массив точек, идущих вдоль кривой.
  const XC_STEPS = 400;
  function xcurveSamples(src) {
    if (!src) return null;
    if (src.type === 'circ') {
      const G = circleGeom(src); if (!G) return null;
      const a0 = G.semi ? G.a0 : 0, размах = G.semi ? Math.PI : Math.PI * 2;
      const out = [];
      for (let i = 0; i <= XC_STEPS; i++) {
        const a = a0 + размах * i / XC_STEPS;
        out.push({ x: G.cx + G.r * Math.cos(a), y: G.cy + G.r * Math.sin(a) });
      }
      return out;
    }
    if (isConstruction(src.type)) {
      const G = lineGeom(src); if (!G) return null;
      const t0 = (G.tmin === -Infinity) ? -GEO_L : G.tmin;
      const t1 = (G.tmax === Infinity) ? GEO_L : G.tmax;
      const out = [];
      // Сгущаем отсчёты к середине: ближняя к центру часть прямой уходит в
      // дальнюю часть окружности-образа и требует частых точек, а хвосты
      // сжимаются к центру, там хватает редких.
      const РАЗМАХ = 1.45, T = Math.tan(РАЗМАХ);
      for (let i = 0; i <= XC_STEPS; i++) {
        const u = i / XC_STEPS * 2 - 1;
        const доля = (Math.tan(u * РАЗМАХ) / T + 1) / 2;
        const t = t0 + (t1 - t0) * доля;
        out.push({ x: G.base.x + G.u.x * t, y: G.base.y + G.u.y * t });
      }
      return out;
    }
    if (isFilledPoly(src.type)) {
      const flat = shapeOutline(src); if (!flat || flat.length < 6) return null;
      const out = [], n = flat.length / 2;
      for (let i = 0; i < n; i++) {
        const ax = flat[i * 2], ay = flat[i * 2 + 1];
        const j = (i + 1) % n, bx = flat[j * 2], by = flat[j * 2 + 1];
        for (let k = 0; k < 60; k++) out.push({ x: ax + (bx - ax) * k / 60, y: ay + (by - ay) * k / 60 });
      }
      out.push({ x: flat[0], y: flat[1] });
      return out;
    }
    return null;
  }
  // Рисование образа кривой: каждый отсчёт через applyXform. Путь рвём там,
  // где образа нет (сам центр инверсии) или где он улетел за пределы окна —
  // соединять такие куски одной линией нельзя.
  function drawXformCurve(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return;
    const d = el.data, fr = elements.get(d.frame), src = elements.get(d.src);
    if (!fr || !src) return;
    const S = xcurveSamples(src); if (!S) return;
    ctx.beginPath();
    let ведём = false;
    for (let i = 0; i < S.length; i++) {
      const q = applyXform(fr, d.xf, S[i]);
      if (!q || !isFinite(q.x) || !isFinite(q.y) || Math.abs(q.x) > GEO_L || Math.abs(q.y) > GEO_L) { ведём = false; continue; }
      if (!ведём) { ctx.moveTo(q.x, q.y); ведём = true; } else ctx.lineTo(q.x, q.y);
    }
    ctx.strokeShape(shape);
  }
  // Образ объекта src: та же фигура на образах опорных точек. objMap — против циклов/дублей.
  function imageObjOf(src, xf, pmap, objMap) {
    if (!src) return null;
    if (objMap[src.id]) return objMap[src.id];
    if (src.type === 'point') { const iid = imagePointOf(src.id, xf, pmap); if (iid) objMap[src.id] = iid; return iid; }
    // Инверсия меняет РОД фигуры: прямая становится окружностью через центр,
    // окружность через центр — прямой. Поэтому образ нельзя построить «той же
    // фигурой на образах точек», и он рисуется отсчётами.
    if (xf.kind === 'inv') {
      if (!xcurveSamples(src)) return null;
      const el = { id: uuid(), type: 'xcurve', z: 0,
        data: { frame: src.data.frame, src: src.id, xf: clone(xf),
                color: src.data.color || src.data.stroke || strokeColor,
                strokeWidth: src.data.strokeWidth || 2 } };
      upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
      objMap[src.id] = el.id;
      return el.id;
    }
    if (!(isConstruction(src.type) || src.type === 'circ' || isFilledPoly(src.type))) return null; // прочее (виджеты/рисунки) не преобразуем
    const nd = { frame: src.data.frame };
    ['color', 'stroke', 'strokeWidth', 'style', 'kind', 'n', 'r'].forEach((k) => { if (src.data[k] !== undefined) nd[k] = src.data[k]; });
    let ok = true;
    ['a', 'b', 'c', 'center', 'through', 'vertex'].forEach((k) => { if (src.data[k] !== undefined) { const iid = imagePointOf(src.data[k], xf, pmap); if (!iid) ok = false; else nd[k] = iid; } });
    if (src.data.pts) { nd.pts = src.data.pts.map((pid) => imagePointOf(pid, xf, pmap)); if (nd.pts.some((x) => !x)) ok = false; }
    if (src.data.line) { const rl = elements.get(src.data.line); const il = rl ? imageObjOf(rl, xf, pmap, objMap) : null; if (!il) ok = false; else nd.line = il; }
    if (!ok) return null;
    const el = { id: uuid(), type: src.type, z: 0, data: nd };
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    objMap[src.id] = el.id;
    return el.id;
  }
  function applyTransform(sourceIds, xf) {
    if (!sourceIds || !sourceIds.length) { boardHint('Сначала выделите объект(ы), затем преобразование'); return; }
    const pmap = {}, objMap = {}, imgPts = [];
    const before = elements.size;
    sourceIds.forEach((sid) => { const src = elements.get(sid); if (src) imageObjOf(src, xf, pmap, objMap); });
    if (elements.size === before) { boardHint('Не удалось построить образ'); return; }
    recomputeGeometry();
    // Точки-образы — поверх фигур-образов.
    Object.values(pmap).forEach((pid) => { const p = nodes.get(pid); const pe = elements.get(pid); if (p && pe && pe.data.frame) { const fnode = nodes.get(pe.data.frame), h = fnode && fnode.findOne('.fheader'); if (h) p.zIndex(h.zIndex()); } else if (p) p.moveToTop(); });
    layer.batchDraw();
    boardHint('Образ построен');
  }
  // Инструменты-преобразования: собирают параметры (точки/прямую) кликами + числа prompt'ом.
  const XFORM_SPEC = {
    csym:   { picks: ['point'], nums: [], hint: 'Кликните центр симметрии' },
    asym:   { picks: ['line'],  nums: [], hint: 'Кликните ось (прямую)' },
    rot:    { picks: ['point'], nums: [['angle', 'Угол поворота (°, + против часовой):', '90']], hint: 'Кликните центр поворота' },
    trans:  { picks: ['point', 'point'], nums: [], hint: 'Кликните начало вектора, затем конец' },
    homo:   { picks: ['point'], nums: [['k', 'Коэффициент гомотетии k:', '2']], hint: 'Кликните центр гомотетии' },
    spiral: { picks: ['point'], nums: [['angle', 'Угол (°):', '90'], ['k', 'Коэффициент k:', '2']], hint: 'Кликните центр' },
    inv:    { picks: ['point', 'point'], nums: [], hint: 'Кликните центр инверсии, затем точку на её окружности' },
  };
  let xformSources = [], xformPicks = [];
  // Активация инструмента: источники = текущее выделение (если было). Дальше можно
  // добавлять кликами (Shift — несколько). setTool сохраняет выделение для xform-инструментов.
  function startXformTool() { xformSources = Array.from(selected); xformPicks = []; const s = XFORM_SPEC[tool]; if (s) boardHint(xformSources.length ? ('Shift — ещё объект; ' + s.hint) : 'Кликните объект (Shift — несколько), затем параметр'); }
  function addXformSource(id) { if (xformSources.indexOf(id) < 0) xformSources.push(id); selected.add(id); refreshTransformer(); }
  function handleXformPick(w, shift) {
    const spec = XFORM_SPEC[tool]; if (!spec) return;
    // Фаза выбора источника: Shift — добавить; первый обычный клик — задать источник.
    if (shift || !xformSources.length) {
      const obj = pickObjectAtWorld(w);
      if (obj) { addXformSource(obj.id); boardHint('Shift — ещё объект; затем: ' + spec.hint); }
      else boardHint('Кликните по объекту для преобразования');
      return;
    }
    // Источники есть, клик без Shift — задаём ПАРАМЕТР преобразования.
    const want = spec.picks[xformPicks.length];
    if (want === 'point') xformPicks.push(pickPointId(w));
    else if (want === 'line') { const ln = pickLineAt(w); if (!ln) { boardHint('Кликните по прямой (ось)'); return; } xformPicks.push(ln.id); }
    if (xformPicks.length < spec.picks.length) { boardHint(spec.hint + ' — ещё'); return; }
    const xf = { kind: tool };
    if (tool === 'csym' || tool === 'rot' || tool === 'homo' || tool === 'spiral') xf.c = xformPicks[0];
    else if (tool === 'asym') xf.line = xformPicks[0];
    else if (tool === 'trans') { xf.a = xformPicks[0]; xf.b = xformPicks[1]; }
    else if (tool === 'inv') { xf.c = xformPicks[0]; xf.through = xformPicks[1]; }
    (async () => {
      let ok = true;
      for (const nm of spec.nums) {
        const txt = await uiPrompt(nm[1], nm[2]);
        const v = parseFloat((txt || '').replace(',', '.'));
        if (!isFinite(v)) { ok = false; break; }
        xf[nm[0]] = v;
      }
      if (ok) applyTransform(xformSources, xf);
      xformSources = []; xformPicks = []; clearSelection(); setTool('select');
    })();
  }
  function cancelXform() { xformSources = []; xformPicks = []; clearSelection(); }
  // ── Инструмент «точка пересечения»: клик по двум фигурам → их пересечения ──
  let pickCurve1 = null;
  function handleIsectPick(w) {
    const c = pickCurveAt(w);
    if (!c) { boardHint('Кликните по фигуре (прямой или окружности)'); return; }
    if (!pickCurve1) { pickCurve1 = c.id; boardHint('Теперь вторая фигура'); return; }
    if (c.id === pickCurve1) { boardHint('Выберите другую фигуру'); return; }
    createIntersectionPoints(pickCurve1, c.id);
    pickCurve1 = null;
  }
  // Существующая точка окна в этом месте (локальные коорд), или null. exclude — id, которые игнорировать.
  function existingPointAtLocal(fr, lx, ly, exclude) {
    const tol = 8 / stage.scaleX();
    let found = null;
    elements.forEach((el) => {
      if (found || el.type !== 'point' || el.data.frame !== fr.id) return;
      if (exclude && exclude.indexOf(el.id) >= 0) return;
      const p = frameMathToLocal(fr, el.data.mx || 0, el.data.my || 0);
      if (Math.hypot(p.x - lx, p.y - ly) <= tol) found = el;
    });
    return found;
  }
  function createIntersectionPoints(id1, id2) {
    const o1 = elements.get(id1), o2 = elements.get(id2);
    if (!o1 || !o2) { pickCurve1 = null; return; }
    if (o1.data.frame !== o2.data.frame || !o1.data.frame) { boardHint('Фигуры должны быть в одном окне'); return; }
    const g1 = curveGeom(o1), g2 = curveGeom(o2);
    const pts = (g1 && g2) ? intersectCurves(g1, g2) : [];
    if (!pts.length) { boardHint('Фигуры не пересекаются'); return; }
    const fr = elements.get(o1.data.frame);
    let added = 0;
    pts.forEach((p, k) => {
      if (existingPointAtLocal(fr, p.x, p.y)) return; // на этом месте уже есть точка — не дублируем
      const m = frameLocalToMath(fr, p.x, p.y);
      const el = { id: uuid(), type: 'point', z: 0, data: { frame: fr.id, mx: m.mx, my: m.my, on: { isect: [id1, id2], k: k }, label: nextPointLabel(), color: strokeColor } };
      upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); added++;
    });
    if (!added) boardHint('Точки пересечения уже отмечены');
    recomputeGeometry(); layer.batchDraw();
  }
  // Расстояние от точки до бесконечной прямой (u единичный) и до отрезка.
  function distPointToLine(p, base, u) { const vx = p.x - base.x, vy = p.y - base.y; return Math.abs(vx * u.y - vy * u.x); }
  function distPointToSeg(p, a, b) {
    const abx = b.x - a.x, aby = b.y - a.y, len2 = abx * abx + aby * aby || 1;
    let t = ((p.x - a.x) * abx + (p.y - a.y) * aby) / len2; t = Math.max(0, Math.min(1, t));
    return Math.hypot(p.x - (a.x + abx * t), p.y - (a.y + aby * t));
  }
  // Линия-построение под курсором (только видимая внутри окна под курсором).
  function pickLineAt(w) {
    const fr = frameAtWorld(w.x, w.y, true); if (!fr) return null;
    const THRESH = 12 / stage.scaleX();
    const lw = { x: w.x - fr.data.x, y: w.y - fr.data.y }; // курсор в локальных коорд окна
    let best = null, bd = THRESH;
    elements.forEach((el) => {
      if (el.data.frame !== fr.id || CONSTRUCT_LINES.indexOf(el.type) < 0) return;
      const P = constructionParams(el); if (!P) return;
      const dist = P.seg ? distPointToSeg(lw, { x: P.seg[0], y: P.seg[1] }, { x: P.seg[2], y: P.seg[3] })
                         : distPointToLine(lw, P.base, P.u);
      if (dist < bd) { bd = dist; best = el; }
    });
    return best;
  }
  // Геометрия линии в ЛОКАЛЬНЫХ коорд окна: база, единичное направление и
  // допустимый диапазон параметра t (для «точки на линии» — точка = base+t·u).
  function lineGeom(el) {
    const P = constructionParams(el); if (!P) return null;
    if (P.seg) {
      const A = { x: P.seg[0], y: P.seg[1] }, B = { x: P.seg[2], y: P.seg[3] };
      const len = Math.hypot(B.x - A.x, B.y - A.y) || 1;
      return { base: A, u: { x: (B.x - A.x) / len, y: (B.y - A.y) / len }, tmin: 0, tmax: len };
    }
    return { base: P.base, u: P.u, tmin: (P.tlo === -Infinity ? -Infinity : 0), tmax: Infinity };
  }
  // Опорные («собственные») точки фигуры — их двигаем при параллельном переносе.
  function lineOwnPoints(el) {
    const d = el.data;
    if ((el.type === 'perp' || el.type === 'parallel') && d.line) return d.through ? [d.through] : [];
    if (el.type === 'circ') return [d.center, d.through, d.a, d.b, d.c].filter(Boolean);
    if (el.type === 'polygon' || el.type === 'conic') return (d.pts || []).slice();
    if (el.type === 'regpoly') return (d.kind === 'center' ? [d.center, d.vertex] : [d.a, d.b]).filter(Boolean);
    return [d.a, d.b, d.c].filter(Boolean);
  }
  // Параметры «точки на линии»: проекция мировой точки w на линию → {on, mx, my, lx, ly}.
  function onLineInfo(fr, line, w) {
    const G = lineGeom(line); if (!G) return null;
    const lw = { x: w.x - fr.data.x, y: w.y - fr.data.y };
    let t = (lw.x - G.base.x) * G.u.x + (lw.y - G.base.y) * G.u.y;
    t = Math.max(G.tmin, Math.min(G.tmax, t));
    const lx = G.base.x + G.u.x * t, ly = G.base.y + G.u.y * t;
    const m = frameLocalToMath(fr, lx, ly);
    return { on: { line: line.id, t: t }, mx: m.mx, my: m.my, lx: lx, ly: ly };
  }
  // Пересечение двух линий (геометрии в локальных коорд окна). Возвращает {p} —
  // точку пересечения, либо null (параллельны или пересечение вне отрезка/луча).
  function cross2(ax, ay, bx, by) { return ax * by - ay * bx; }
  function lineLineIntersect(G1, G2) {
    const den = cross2(G1.u.x, G1.u.y, G2.u.x, G2.u.y);
    if (Math.abs(den) < 1e-9) return null; // параллельны
    const dx = G2.base.x - G1.base.x, dy = G2.base.y - G1.base.y;
    const t = cross2(dx, dy, G2.u.x, G2.u.y) / den;
    const p = { x: G1.base.x + G1.u.x * t, y: G1.base.y + G1.u.y * t };
    const s = (p.x - G2.base.x) * G2.u.x + (p.y - G2.base.y) * G2.u.y;
    if (t < G1.tmin - 1e-6 || t > G1.tmax + 1e-6) return null; // вне диапазона первой
    if (s < G2.tmin - 1e-6 || s > G2.tmax + 1e-6) return null; // вне диапазона второй
    return { p: p, t: t, s: s };
  }
  // ── Окружности по точкам (5 построений) и кривые для пересечений ────────
  function isCurveType(t) { return CONSTRUCT_LINES.indexOf(t) >= 0 || t === 'circ'; }
  // Центр описанной окружности треугольника ABC (или null, если точки коллинеарны).
  function circumcenter(A, B, C) {
    const d = 2 * (A.x * (B.y - C.y) + B.x * (C.y - A.y) + C.x * (A.y - B.y));
    if (Math.abs(d) < 1e-9) return null;
    const A2 = A.x * A.x + A.y * A.y, B2 = B.x * B.x + B.y * B.y, C2 = C.x * C.x + C.y * C.y;
    return {
      x: (A2 * (B.y - C.y) + B2 * (C.y - A.y) + C2 * (A.y - B.y)) / d,
      y: (A2 * (C.x - B.x) + B2 * (A.x - C.x) + C2 * (B.x - A.x)) / d,
    };
  }
  // Геометрия окружности в ЛОКАЛЬНЫХ коорд окна: центр (cx,cy), радиус r,
  // для полуокружности — флаг semi и углы концов a0,a1.
  //   kind: cp (центр+точка), cr (центр+радиус), c3 (по 3 точкам),
  //         compass (циркуль: радиус=|AB|, центр=C), semi (полукруг на диаметре AB).
  function circleGeom(el) {
    const pos = ptPosFor(el), d = el.data;
    const fr = d.frame ? elements.get(d.frame) : null;
    const unit = fr ? (fr.data.unit || 40) : 1;
    if (d.kind === 'cp') { const C = pos(d.center), T = pos(d.through); if (!C || !T) return null; return { cx: C.x, cy: C.y, r: Math.hypot(T.x - C.x, T.y - C.y) }; }
    if (d.kind === 'cr') { const C = pos(d.center); if (!C) return null; return { cx: C.x, cy: C.y, r: (d.r || 0) * unit }; }
    if (d.kind === 'compass') { const A = pos(d.a), B = pos(d.b), C = pos(d.center); if (!A || !B || !C) return null; return { cx: C.x, cy: C.y, r: Math.hypot(B.x - A.x, B.y - A.y) }; }
    if (d.kind === 'c3') { const A = pos(d.a), B = pos(d.b), Cc = pos(d.c); if (!A || !B || !Cc) return null; const O = circumcenter(A, B, Cc); if (!O) return null; return { cx: O.x, cy: O.y, r: Math.hypot(A.x - O.x, A.y - O.y) }; }
    if (d.kind === 'semi') { const A = pos(d.a), B = pos(d.b); if (!A || !B) return null; const cx = (A.x + B.x) / 2, cy = (A.y + B.y) / 2; return { cx: cx, cy: cy, r: Math.hypot(B.x - A.x, B.y - A.y) / 2, semi: true, a0: Math.atan2(A.y - cy, A.x - cx), a1: Math.atan2(B.y - cy, B.x - cx) }; }
    return null;
  }
  // Единое описание кривой (линия | окружность | дуга) для пересечений/выбора.
  function curveGeom(el) {
    if (CONSTRUCT_LINES.indexOf(el.type) >= 0) { const G = lineGeom(el); return G ? { type: 'line', base: G.base, u: G.u, tmin: G.tmin, tmax: G.tmax } : null; }
    if (el.type === 'circ') { const C = circleGeom(el); return C ? { type: C.semi ? 'arc' : 'circle', cx: C.cx, cy: C.cy, r: C.r, a0: C.a0, semi: C.semi } : null; }
    return null;
  }
  // Точка на дуге полуокружности? (полукруг рисуем от a0 против часовой на π.)
  function pointOnArc(C, p) {
    if (!C.semi) return true;
    let d = Math.atan2(p.y - C.cy, p.x - C.cx) - C.a0;
    while (d < 0) d += 2 * Math.PI; while (d >= 2 * Math.PI) d -= 2 * Math.PI;
    return d <= Math.PI + 1e-6;
  }
  // Пересечения (в локальных коорд). Порядок точек стабилен (по t / по стороне),
  // чтобы «которая из двух» (k) не прыгала при движении фигур.
  function lineCircleIntersect(L, C) {
    const dx = L.base.x - C.cx, dy = L.base.y - C.cy;
    const b = dx * L.u.x + dy * L.u.y, c = dx * dx + dy * dy - C.r * C.r;
    const disc = b * b - c; if (disc < -1e-9) return [];
    const sq = Math.sqrt(Math.max(0, disc));
    const ts = (Math.abs(disc) < 1e-9) ? [-b] : [-b - sq, -b + sq];
    const res = [];
    ts.forEach((t) => {
      if (t < L.tmin - 1e-6 || t > L.tmax + 1e-6) return;
      const p = { x: L.base.x + L.u.x * t, y: L.base.y + L.u.y * t };
      if (pointOnArc(C, p)) res.push(p);
    });
    return res;
  }
  function circleCircleIntersect(C1, C2) {
    const dx = C2.cx - C1.cx, dy = C2.cy - C1.cy, D = Math.hypot(dx, dy);
    if (D < 1e-9) return [];
    if (D > C1.r + C2.r + 1e-6 || D < Math.abs(C1.r - C2.r) - 1e-6) return [];
    const a = (C1.r * C1.r - C2.r * C2.r + D * D) / (2 * D);
    const h = Math.sqrt(Math.max(0, C1.r * C1.r - a * a));
    const mx = C1.cx + a * dx / D, my = C1.cy + a * dy / D, ex = -dy / D, ey = dx / D;
    const cand = (h < 1e-9) ? [{ x: mx, y: my }] : [{ x: mx + h * ex, y: my + h * ey }, { x: mx - h * ex, y: my - h * ey }];
    return cand.filter((p) => pointOnArc(C1, p) && pointOnArc(C2, p));
  }
  function intersectCurves(g1, g2) {
    const line1 = g1.type === 'line', line2 = g2.type === 'line';
    if (line1 && line2) { const X = lineLineIntersect(g1, g2); return X ? [X.p] : []; }
    if (line1 && !line2) return lineCircleIntersect(g1, g2);
    if (!line1 && line2) return lineCircleIntersect(g2, g1);
    return circleCircleIntersect(g1, g2);
  }
  function distToCurve(g, p) {
    if (g.type === 'line') {
      if (g.tmin === -Infinity && g.tmax === Infinity) return distPointToLine(p, g.base, g.u);
      let t = (p.x - g.base.x) * g.u.x + (p.y - g.base.y) * g.u.y; t = Math.max(g.tmin, Math.min(g.tmax, t));
      return Math.hypot(p.x - (g.base.x + g.u.x * t), p.y - (g.base.y + g.u.y * t));
    }
    let d = Math.abs(Math.hypot(p.x - g.cx, p.y - g.cy) - g.r);
    if (g.semi && !pointOnArc(g, p)) d += 1e6; // вне дуги — недоступна
    return d;
  }
  // Кривая (линия/окружность) под курсором внутри окна.
  function pickCurveAt(w) {
    const fr = frameAtWorld(w.x, w.y, true); if (!fr) return null;
    const THRESH = 12 / stage.scaleX(), lw = { x: w.x - fr.data.x, y: w.y - fr.data.y };
    let best = null, bd = THRESH;
    elements.forEach((el) => {
      if (el.data.frame !== fr.id || !isCurveType(el.type)) return;
      const g = curveGeom(el); if (!g) return;
      const d = distToCurve(g, lw); if (d < bd) { bd = d; best = el; }
    });
    return best;
  }
  // Пересечение двух кривых окна рядом с курсором → {a, b, k, p} (для точки-инструмента).
  function pickIntersectionAt(fr, w) {
    const THRESH = 12 / stage.scaleX(), lw = { x: w.x - fr.data.x, y: w.y - fr.data.y };
    const curves = [];
    elements.forEach((el) => { if (el.data.frame !== fr.id || !isCurveType(el.type)) return; const g = curveGeom(el); if (g) curves.push({ id: el.id, g: g }); });
    let best = null, bd = THRESH;
    for (let i = 0; i < curves.length; i++) for (let j = i + 1; j < curves.length; j++) {
      const pts = intersectCurves(curves[i].g, curves[j].g);
      pts.forEach((p, k) => { const d = Math.hypot(p.x - lw.x, p.y - lw.y); if (d < bd) { bd = d; best = { a: curves[i].id, b: curves[j].id, k: k, p: p }; } });
    }
    return best;
  }
  // Ненавязчивая всплывающая подсказка вверху холста (~1.6 c). Монохром, без иконок.
  let hintEl = null, hintTimer = null;
  function boardHint(msg) {
    if (!hintEl) {
      hintEl = document.createElement('div');
      hintEl.style.cssText = 'position:fixed;left:50%;top:76px;transform:translateX(-50%);background:#1f2937;color:#fff;font:13px/1.4 sans-serif;padding:6px 12px;border-radius:8px;z-index:60;pointer-events:none;opacity:0;transition:opacity .15s;box-shadow:0 6px 24px rgba(0,0,0,.18);';
      document.body.appendChild(hintEl);
    }
    hintEl.textContent = msg; hintEl.style.opacity = '1';
    clearTimeout(hintTimer); hintTimer = setTimeout(() => { hintEl.style.opacity = '0'; }, 1600);
  }

  // Экранные окошки вместо системных alert/confirm/prompt. Системные («сайт
  // сообщает…») выглядят чужеродно и пугают. Свои — в оформлении доски,
  // промис-based: confirm → true/false, prompt → строка/null, alert → true.
  function uiModal(opts) {
    return new Promise((resolve) => {
      const back = document.createElement('div'); back.className = 'ui-modal-back';
      const card = document.createElement('div'); card.className = 'ui-modal';
      if (opts.title) { const h = document.createElement('div'); h.className = 'ui-modal-title'; h.textContent = opts.title; card.appendChild(h); }
      if (opts.message) { const m = document.createElement('div'); m.className = 'ui-modal-msg'; m.textContent = opts.message; card.appendChild(m); }
      let field = null;
      if (opts.kind === 'prompt') {
        field = document.createElement(opts.multiline ? 'textarea' : 'input');
        field.className = 'ui-modal-input';
        if (!opts.multiline) field.type = 'text';
        field.value = (opts.def != null) ? String(opts.def) : '';
        if (opts.readonly) field.readOnly = true;
        card.appendChild(field);
      }
      const row = document.createElement('div'); row.className = 'ui-modal-btns';
      let cancelBtn = null;
      if (opts.kind !== 'alert') {
        cancelBtn = document.createElement('button'); cancelBtn.type = 'button';
        cancelBtn.className = 'ui-modal-btn ui-modal-cancel'; cancelBtn.textContent = opts.cancelText || 'Отмена';
        row.appendChild(cancelBtn);
      }
      const okBtn = document.createElement('button'); okBtn.type = 'button';
      okBtn.className = 'ui-modal-btn ui-modal-ok' + (opts.danger ? ' danger' : ''); okBtn.textContent = opts.okText || 'ОК';
      row.appendChild(okBtn);
      card.appendChild(row);
      back.appendChild(card); document.body.appendChild(back);
      const okVal = () => (opts.kind === 'prompt') ? (field ? field.value : '') : true;
      const cancelVal = () => (opts.kind === 'prompt') ? null : false;
      const done = (v) => { document.removeEventListener('keydown', onKey, true); if (back.parentNode) back.remove(); resolve(v); };
      okBtn.addEventListener('click', () => done(okVal()));
      if (cancelBtn) cancelBtn.addEventListener('click', () => done(cancelVal()));
      back.addEventListener('mousedown', (e) => { if (e.target === back) done(cancelVal()); });
      // Клавиши ловим в фазе перехвата и гасим — иначе Enter/Esc уйдут в
      // горячие клавиши доски. Enter в многострочном поле — обычный перенос.
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(cancelVal()); }
        else if (e.key === 'Enter' && !(opts.kind === 'prompt' && opts.multiline)) { e.preventDefault(); e.stopPropagation(); done(okVal()); }
      }
      document.addEventListener('keydown', onKey, true);
      setTimeout(() => { if (field) { field.focus(); if (field.select) field.select(); } else okBtn.focus(); }, 30);
    });
  }
  function uiAlert(message, title) { return uiModal({ kind: 'alert', message: message, title: title }); }
  function uiConfirm(message, opts) { opts = opts || {}; return uiModal({ kind: 'confirm', message: message, title: opts.title, okText: opts.ok, cancelText: opts.cancel, danger: opts.danger }); }
  function uiPrompt(message, def, opts) { opts = opts || {}; return uiModal({ kind: 'prompt', message: message, def: def, multiline: opts.multiline, readonly: opts.readonly, okText: opts.ok, cancelText: opts.cancel }); }
  let pickFrame = null;   // окно, в котором идёт текущее бесконечное построение
  let pickRefLine = null; // выбранная линия-основа (режим «линия + точка»)
  // Валидная точка внутри целевого окна pickFrame (иначе подсказка). Возвращает id или null.
  function pickPointInFrame(w) {
    const fr = frameAtWorld(w.x, w.y, true);
    if (!fr) { boardHint('Бесконечные построения — только внутри матокна'); return null; }
    if (pickFrame && fr.id !== pickFrame) { boardHint('Все точки — в одном матокне'); return null; }
    pickFrame = pickFrame || fr.id;
    const id = pickPointId(w), pe = elements.get(id);
    if (!pe || pe.data.frame !== pickFrame) { boardHint('Точка вне матокна'); return null; }
    return id;
  }
  // Угол заданной градусной меры: клик по точке-стороне A, затем вершине V, ввод
  // градусов → строим A′ (поворот A вокруг V) и луч VA′ — вторую сторону угла.
  let angleDegPicks = [];
  function handleAngleDegPick(w) {
    const id = pickPointInFrame(w); if (!id) return; // как лучи — строго в одном окне
    angleDegPicks.push(id);
    if (angleDegPicks.length < 2) { boardHint('Теперь вершина угла'); return; }
    const aId = angleDegPicks[0], vId = angleDegPicks[1]; angleDegPicks = []; pickFrame = null;
    const A = elements.get(aId), V = elements.get(vId);
    if (!A || !V || !A.data.frame || A.data.frame !== V.data.frame) { boardHint('Обе точки — в одном окне'); return; }
    uiPrompt('Градусная мера угла (против часовой):', '90').then((txt) => {
      const deg = parseFloat(String(txt == null ? '' : txt).replace(',', '.'));
      if (!isFinite(deg)) return;
      // A′ — производная точка: поворот A вокруг V на deg (следит за A и V).
      const el = { id: uuid(), type: 'point', z: 0, data: { frame: A.data.frame, on: { xform: { kind: 'rot', c: vId, angle: deg }, src: aId }, label: nextPointLabel(), color: strokeColor } };
      applyTypeDefaults(el.data, 'point');
      upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry();
      createConstruction('ray', [vId, el.id]); // вторая сторона угла
      boardHint('Угол ' + deg + '° построен');
    });
  }
  // Перпендикуляр/параллель: первый клик по существующей линии → режим «линия + точка»;
  // по пустому месту → режим «три точки» (A,B задают направление, C — через какую точку).
  function handlePerpParallelPick(w) {
    if (pendingPicks.length === 0 && !pickRefLine) {
      const line = pickLineAt(w);
      if (line) { pickRefLine = line.id; pickFrame = line.data.frame; boardHint('Теперь точка, через которую провести'); return; }
    }
    if (pickRefLine) {
      const fr = frameAtWorld(w.x, w.y, true);
      if (!fr || fr.id !== pickFrame) { boardHint('Точка — в том же матокне'); return; }
      const id = pickPointId(w), pe = elements.get(id);
      if (!pe || pe.data.frame !== pickFrame) { boardHint('Точка вне матокна'); return; }
      createPerpParallelByLine(tool, pickRefLine, id, pickFrame);
      pendingPicks = []; pickRefLine = null; pickFrame = null;
      return;
    }
    const id = pickPointInFrame(w); if (!id) return;
    pendingPicks.push(id);
    if (pendingPicks.length >= 3) { createConstruction(tool, pendingPicks); pendingPicks = []; pickFrame = null; }
  }
  function handleConstructPick() {
    const w = worldPoint();
    if (tool === 'perp' || tool === 'parallel') { handlePerpParallelPick(w); return; }
    if (INFINITE_CONSTRUCTS.indexOf(tool) >= 0) {
      // Прочие бесконечные построения — строго внутри одного матокна.
      const id = pickPointInFrame(w); if (!id) return;
      pendingPicks.push(id);
    } else {
      pendingPicks.push(pickPointId(w)); // конечные (отрезок, угол) — где угодно
    }
    if (pendingPicks.length >= CONSTRUCT_PICKS[tool]) { createConstruction(tool, pendingPicks); pendingPicks = []; pickFrame = null; }
  }

  // ── Измерения: выбор опор и создание ──────────────────────────────────
  let measurePicks = [];
  // Залитый многоугольник под курсором (контур → мировые коорды → тест «внутри»).
  function pickFilledPolyAt(w) {
    let found = null;
    elements.forEach((el) => {
      if (!isFilledPoly(el.type)) return;
      const flat = shapeOutline(el); if (!flat || flat.length < 6) return;
      const fr = el.data.frame ? elements.get(el.data.frame) : null;
      const wf = []; for (let i = 0; i < flat.length; i += 2) { wf.push(flat[i] + (fr ? fr.data.x : 0), flat[i + 1] + (fr ? fr.data.y : 0)); }
      if (pointInPolygon(w, wf)) found = el;
    });
    return found;
  }
  function handleMeasurePick(w) {
    if (tool === 'measure_area') {
      const poly = pickFilledPolyAt(w);
      if (!poly) { boardHint('Кликните внутрь многоугольника'); return; }
      createMeasure('area', [poly.id], poly.data.frame);
      return;
    }
    const id = pickPointId(w); if (!id) return;
    measurePicks.push(id);
    const need = MEASURE_PICKS[tool];
    if (measurePicks.length < need) { boardHint('Точка ' + measurePicks.length + ' из ' + need); return; }
    const kind = 'length'; // осталось только измерение длины (measure_len); угол — см. angle_deg
    const frs = measurePicks.map((pid) => { const e = elements.get(pid); return e ? e.data.frame : undefined; });
    const common = frs.every((f) => f && f === frs[0]) ? frs[0] : undefined;
    createMeasure(kind, measurePicks.slice(), common);
    measurePicks = [];
  }
  function createMeasure(kind, refs, frame) {
    const data = { kind, refs, color: '#1f2937', name: nextObjName() };
    if (frame) data.frame = frame;
    const el = { id: uuid(), type: 'measure', z: 0, data };
    upsertNode(el); recomputeGeometry();
    send({ action: 'element_add', element: el }); histAdd(el);
    layer.batchDraw();
    boardHint(kind === 'length' ? 'Длина измерена' : kind === 'angle' ? 'Угол измерен' : 'Площадь измерена');
  }

  // ── Пометка «прямой угол»: 3 точки (A, вершина, B); повторный клик снимает ──
  let markPicks = [];
  function sameMarkRefs(r1, r2) { return r1[1] === r2[1] && ((r1[0] === r2[0] && r1[2] === r2[2]) || (r1[0] === r2[2] && r1[2] === r2[0])); }
  function findMark(refs) { let f = null; elements.forEach((el) => { if (el.type === 'mark' && el.data.kind === 'right' && el.data.refs && el.data.refs.length === 3 && sameMarkRefs(el.data.refs, refs)) f = el; }); return f; }
  function handleMarkPick(w) {
    const id = pickPointId(w); if (!id) return;
    markPicks.push(id);
    if (markPicks.length < 3) { boardHint('Точка ' + markPicks.length + ' из 3'); return; }
    const refs = markPicks.slice(); markPicks = [];
    const ex = findMark(refs);
    if (ex) { deleteMarkEl(ex); return; }
    const el = { id: uuid(), type: 'mark', z: 0, data: { kind: 'right', refs, count: 1, color: '#1f2937' } };
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); layer.batchDraw();
    boardHint('Прямой угол отмечен');
  }
  function deleteMarkEl(el) { histDel(el); send({ action: 'element_delete', id: el.id }); removeNode(el.id); layer.batchDraw(); }

  // ── Пользовательские инструменты (макросы): записать конструкцию и применять ──
  // Пользователь выбирает исходные точки, затем итоговые объекты. Записываем
  // «рецепт» (цепочку зависимостей) и переигрываем его на новых точках.
  const MACRO_KEY = 'board-macros-v1';
  function loadMacros() { try { return JSON.parse(localStorage.getItem(MACRO_KEY) || '[]'); } catch (e) { return []; } }
  function saveMacros(list) { try { localStorage.setItem(MACRO_KEY, JSON.stringify(list)); } catch (e) {} }
  function renderMacroTools() {
    const box = document.getElementById('macro-list'); if (!box) return;
    const list = loadMacros();
    box.innerHTML = list.length ? list.map((m, i) =>
      '<div class="macro-tool" data-macro="' + i + '" title="' + escapeAttr(m.name) + ' — кликните ' + m.nInputs + ' точк(и)"><span class="macro-name">' + escapeHtml(m.name) + '</span><button class="macro-del" data-macro="' + i + '" title="Удалить">×</button></div>'
    ).join('') : '<div class="macro-empty">пока нет — нажмите «Создать инструмент»</div>';
  }
  // Id-ссылки, на которые опирается элемент (обратное к directDependents).
  function elemRefs(el) {
    const d = el.data, out = [];
    ['a', 'b', 'c', 'center', 'through', 'line', 'vertex'].forEach((k) => { if (d[k]) out.push(d[k]); });
    (d.pts || []).forEach((id) => out.push(id));
    (d.refs || []).forEach((id) => out.push(id));
    if (d.on) { const o = d.on;
      ['line', 'c', 'circle', 'regpoly'].forEach((k) => { if (o[k]) out.push(o[k]); });
      (o.isect || []).forEach((id) => out.push(id));
      (o.centroid || []).forEach((id) => out.push(id));
      if (o.ratio) { if (o.ratio.a) out.push(o.ratio.a); if (o.ratio.b) out.push(o.ratio.b); }
      if (o.xform) ['src', 'c', 'a', 'b', 'line', 'through'].forEach((k) => { if (o.xform[k]) out.push(o.xform[k]); });
    }
    return out;
  }
  // Заменить в данных все id-ссылки по карте (uuid → uuid); строки-неид не трогаем.
  function remapIds(v, map) {
    if (Array.isArray(v)) { for (let i = 0; i < v.length; i++) { if (typeof v[i] === 'string') { if (map[v[i]]) v[i] = map[v[i]]; } else if (v[i] && typeof v[i] === 'object') remapIds(v[i], map); } return; }
    if (v && typeof v === 'object') { for (const k in v) { const val = v[k]; if (typeof val === 'string') { if (map[val]) v[k] = map[val]; } else if (val && typeof val === 'object') remapIds(val, map); } }
  }
  function buildMacroRecipe(inputIds, outputIds) {
    const inputSet = new Set(inputIds), closure = new Set(), stack = outputIds.slice();
    while (stack.length) { const id = stack.pop(); if (closure.has(id) || inputSet.has(id)) continue; const el = elements.get(id); if (!el) continue; closure.add(id); elemRefs(el).forEach((r) => { if (!inputSet.has(r)) stack.push(r); }); }
    const steps = []; // в порядке создания (Map хранит порядок вставки = топологический)
    elements.forEach((el) => { if (closure.has(el.id)) steps.push({ id: el.id, type: el.type, data: clone(el.data) }); });
    return { name: '', nInputs: inputIds.length, inputIds: inputIds.slice(), steps: steps };
  }
  function applyMacro(macro, newInputIds) {
    if (!macro || newInputIds.length < macro.nInputs) return;
    const idMap = {};
    macro.inputIds.forEach((oldId, i) => { idMap[oldId] = newInputIds[i]; });
    macro.steps.forEach((s) => { idMap[s.id] = uuid(); });
    const p0 = elements.get(newInputIds[0]), targetFrame = p0 ? p0.data.frame : undefined;
    macro.steps.forEach((s) => {
      const data = clone(s.data); remapIds(data, idMap);
      if (targetFrame) data.frame = targetFrame; else delete data.frame;
      if (s.type === 'point') { data.label = nextPointLabel(); data.idx = undefined; }
      const el = { id: idMap[s.id], type: s.type, z: 0, data: data };
      upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    });
    recomputeGeometry(); layer.batchDraw();
    boardHint('Инструмент «' + macro.name + '» применён');
  }

  // Запись макроса (двухфазный выбор: исходные точки → итоговые объекты).
  let macroMode = null, macroInputs = [], macroOutputs = [], activeMacro = null, macroPickPts = [];
  function startMacroRecord() {
    macroMode = 'inputs'; macroInputs = []; macroOutputs = []; clearSelection();
    setTool('macro_record');
    boardHint('Шаг 1: кликните исходные точки по порядку, затем Enter');
  }
  function handleMacroRecordPick(w) {
    if (macroMode === 'inputs') {
      const p = pickSelectablePointNear(w); if (!p) { boardHint('Кликайте по существующим точкам'); return; }
      if (macroInputs.indexOf(p.id) < 0) macroInputs.push(p.id);
      boardHint('Исходных точек: ' + macroInputs.length + ' (Enter — дальше)');
    } else if (macroMode === 'outputs') {
      const o = pickObjectAtWorld(w); if (!o) { boardHint('Кликайте по итоговым объектам'); return; }
      if (macroOutputs.indexOf(o.id) < 0) macroOutputs.push(o.id);
      boardHint('Итоговых объектов: ' + macroOutputs.length + ' (Enter — сохранить)');
    }
  }
  function macroRecordEnter() {
    if (macroMode === 'inputs') {
      if (!macroInputs.length) { boardHint('Сначала выберите хотя бы одну исходную точку'); return; }
      macroMode = 'outputs'; boardHint('Шаг 2: кликните итоговые объекты, затем Enter');
    } else if (macroMode === 'outputs') {
      if (!macroOutputs.length) { boardHint('Выберите хотя бы один итоговый объект'); return; }
      const recipe = buildMacroRecipe(macroInputs, macroOutputs);
      uiPrompt('Название инструмента:', 'Мой инструмент').then((name) => {
        if (name && name.trim()) { recipe.name = name.trim(); const list = loadMacros(); list.push(recipe); saveMacros(list); renderMacroTools(); boardHint('Инструмент «' + recipe.name + '» создан'); }
      });
      macroMode = null; setTool('select');
    }
  }
  function cancelMacro() { macroMode = null; macroInputs = []; macroOutputs = []; activeMacro = null; macroPickPts = []; }
  function startMacroApply(macro) { activeMacro = macro; macroPickPts = []; setTool('macro'); boardHint('Инструмент «' + macro.name + '»: кликните ' + macro.nInputs + ' точк(и)'); }
  function handleMacroApplyPick(w) {
    if (!activeMacro) return;
    const id = pickPointId(w); if (!id) return;
    macroPickPts.push(id);
    if (macroPickPts.length >= activeMacro.nInputs) { const m = activeMacro, pts = macroPickPts.slice(); macroPickPts = []; applyMacro(m, pts); }
    else boardHint('Точка ' + macroPickPts.length + ' из ' + activeMacro.nInputs);
  }

  // ── Виджеты (таблица, канбан, таймер, колесо) — DOM-оверлей ─────────────
  const widgetLayerEl = document.getElementById('widget-layer');
  const widgetItems = new Map();
  const WIDGET_TYPES = ['table', 'kanban', 'timer', 'wheel', 'slider', 'sticky', 'card', 'embed', 'poll', 'screen', 'comment'];

  function repositionWidgets() {
    if (typeof recomputeConnectors === 'function') recomputeConnectors(); // стрелки к DOM-объектам
    const s = stage.scaleX();
    widgetItems.forEach((it) => {
      const d = it.el.data;
      it.wrapper.style.transform = 'translate(' + ((d.x || 0) * s + stage.x()) + 'px,' + ((d.y || 0) * s + stage.y()) + 'px) scale(' + s + ')';
    });
    if (typeof shapeTextItems !== 'undefined' && shapeTextItems.size) shapeTextItems.forEach((it) => repositionShapeText(it.shapeId));
    if (typeof activeTbox !== 'undefined' && activeTbox && tboxBar && !tboxBar.classList.contains('ps-hidden')) positionTboxBar(activeTbox);
    if (typeof positionStickyPanel === 'function') positionStickyPanel();
    // У текста, стикеров и таблиц угловых ручек нет, значит через
    // positionHandles их якоря не обновятся — двигаем здесь.
    if (typeof renderAnchors === 'function') renderAnchors();
  }
  function widgetTitle(el) { return { table: 'Таблица', kanban: 'Канбан', timer: 'Таймер', wheel: 'Колесо', slider: 'Параметр', sticky: '', card: '', embed: 'Страница', poll: 'Голосование', screen: 'Экран' }[el.type] || ''; }
  function syncWidget(it) { send({ action: 'element_update', element: it.el }); }

  function upsertWidget(el) {
    let it = widgetItems.get(el.id);
    if (it) { it.el = el; if (it.update) it.update(el); repositionWidgets(); return; }
    const wrapper = document.createElement('div');
    wrapper.className = 'wgt wgt-' + el.type;
    const bar = document.createElement('div'); bar.className = 'wgt-bar';
    bar.innerHTML = '<span class="wgt-title">' + widgetTitle(el) + '</span><button class="wgt-del" title="Удалить">×</button>';
    const body = document.createElement('div'); body.className = 'wgt-body';
    wrapper.appendChild(bar); wrapper.appendChild(body);
    widgetLayerEl.appendChild(wrapper);
    it = { el, wrapper, bar, body, update: null, timer: null };
    widgetItems.set(el.id, it);
    enableWidgetDrag(it, bar);
    bar.querySelector('.wgt-del').addEventListener('click', () => { histDel(it.el); send({ action: 'element_delete', id: el.id }); removeWidget(el.id); });
    buildWidgetContent(it);
    repositionWidgets();
  }
  function removeWidget(id) {
    const it = widgetItems.get(id);
    if (!it) return;
    cancelPendingSync(id);
    if (it.saveTimer) { clearTimeout(it.saveTimer); it.saveTimer = null; }
    const tb = document.getElementById('tbl-bar');
    if (tb && tb._owner === it) { tb.hidden = true; tb._owner = null; }
    if (it.timer) clearInterval(it.timer);
    it.wrapper.remove();
    widgetItems.delete(id);
    elements.delete(id);
  }
  function enableWidgetDrag(it, handle) {
    handle.addEventListener('mousedown', (e) => {
      if (e.target.closest('.wgt-del')) return;
      e.preventDefault();
      if (isAddKey(e)) { toggleSelect(it.el.id); return; }   // добавить к выделению, не тащить
      if (selected.has(it.el.id) && selected.size > 1) { domSelectionDrag(e); return; } // тащим всё выделение
      const s = stage.scaleX();
      const sx = e.clientX, sy = e.clientY, ox = it.el.data.x || 0, oy = it.el.data.y || 0;
      const before = clone(it.el);
      // Отличаем перетаскивание от клика: клик по объекту должен его ВЫДЕЛИТЬ
      // (иначе к нему не подступиться — ни якорей, ни настроек), а рассылать
      // соседям «я не сдвинулся» незачем.
      let moved = false;
      const mv = (ev) => {
        if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 3) return;
        moved = true;
        it.el.data.x = ox + (ev.clientX - sx) / s; it.el.data.y = oy + (ev.clientY - sy) / s;
        repositionWidgets();
      };
      const up = () => {
        document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up);
        if (!moved) { selectOnly(it.el.id); return; }
        syncWidget(it); syncConnectorsOf([it.el.id]); histUpd(before, it.el);
      };
      document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
    });
  }

  function insertWidget(type, data, at) {
    // at — заранее запомненная точка (нужна, когда между выбором инструмента и
    // созданием объекта успевает открыться диалог).
    const p = at || worldPoint() || { x: -stage.x() / stage.scaleX() + 200, y: -stage.y() / stage.scaleX() + 200 };
    const el = { id: uuid(), type, z: 0, data: Object.assign({ x: p.x, y: p.y }, data) };
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    setTool('select');
  }
  function insertTable() {
    insertWidget('table', {
      rows: 3, cols: 3,
      colW: [120, 120, 120], rowH: [36, 36, 36],
      cells: [[{}, {}, {}], [{}, {}, {}], [{}, {}, {}]],
    });
  }
  function insertKanban() { insertWidget('kanban', { columns: [{ title: 'To do', cards: [] }, { title: 'В работе', cards: [] }, { title: 'Готово', cards: [] }] }); }
  function insertTimer() { insertWidget('timer', { duration: 300, remaining: 300, running: false, startedAt: 0 }); }
  function insertWheel() { insertWidget('wheel', { options: ['Аня', 'Боря', 'Вера', 'Гена'] }); }

  function escapeAttr(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  function buildWidgetContent(it) {
    if (it.el.type === 'embed') buildEmbed(it);
    else if (it.el.type === 'screen') buildScreen(it);
    else if (it.el.type === 'poll') buildPoll(it);
    else if (it.el.type === 'table') buildTable(it);
    else if (it.el.type === 'kanban') buildKanban(it);
    else if (it.el.type === 'timer') buildTimer(it);
    else if (it.el.type === 'wheel') buildWheel(it);
    else if (it.el.type === 'slider') buildSlider(it);
    else if (it.el.type === 'sticky') buildSticky(it);
    else if (it.el.type === 'card') buildCard(it);
    else if (it.el.type === 'comment') buildComment(it);
  }

  // — Стикер — цветная заметка с текстом —
  const STICKY_COLORS = ['#fff7ae', '#ffd18c', '#c8f7c5', '#a8e6ff', '#ffc9de', '#e6d6ff', '#ffffff'];
  function buildSticky(it) {
    const render = () => {
      const d = it.el.data, col = d.color || STICKY_COLORS[0];
      it.wrapper.style.background = col;
      // Кружки выбора цвета убраны из тела: они занимали верх заметки и вели
      // себя не как у прочих объектов доски. Цвет и размер текста теперь в
      // плавающей панели над выделенным стикером — как у фигур.
      it.body.innerHTML = '<textarea class="stk-text" placeholder="Заметка…">' + escapeAttr(d.text || '') + '</textarea>';
      const ta = it.body.querySelector('.stk-text');
      ta.style.fontSize = (d.fontSize || 14) + 'px';
      ta.addEventListener('input', () => { it.el.data.text = ta.value; syncWidget(it); });
    };
    it.update = render; render();
  }
  function insertSticky() { insertWidget('sticky', { text: '', color: STICKY_COLORS[0] }); }

  // — Комментарий: свёрнутая метка, разворачивается в нить —
  const COMMENT_MAX = 2000;   // символов в одной записи
  const THREAD_MAX = 100;     // записей в нити: элемент не должен упереться в предел размера
  function commentInitial(name) { const t = (name || '?').trim(); return t ? t.charAt(0).toUpperCase() : '?'; }
  function buildComment(it) {
    if (it._open == null) it._open = !((it.el.data.thread || []).length);  // новый — сразу открыт
    const render = () => {
      const d = it.el.data, нить = d.thread || [];
      it.wrapper.classList.toggle('cmt-collapsed', !it._open);
      it.wrapper.classList.toggle('cmt-done', !!d.resolved);
      if (!it._open) {
        const кто = нить.length ? нить[нить.length - 1].name : myLabel;
        it.body.innerHTML = '<button class="cmt-dot" title="Показать комментарий">'
          + escapeHtml(commentInitial(кто))
          + (нить.length > 1 ? '<span class="cmt-n">' + нить.length + '</span>' : '') + '</button>';
        it.body.querySelector('.cmt-dot').addEventListener('click', () => { it._open = true; render(); });
        return;
      }
      const записи = нить.map((r) => '<div class="cmt-row"><span class="cmt-who">' + escapeHtml(r.name || '—')
        + '</span><span class="cmt-at">' + escapeHtml(histTime(r.at)) + '</span>'
        + '<div class="cmt-text">' + linkifyHtml(escapeHtml(r.text || '')) + '</div></div>').join('');
      it.body.innerHTML = '<div class="cmt-head"><b>Комментарий</b>'
        + '<button class="cmt-fold" title="Свернуть">–</button></div>'
        + '<div class="cmt-list">' + (записи || '<div class="cmt-empty">Пока пусто</div>') + '</div>'
        + '<textarea class="cmt-input" rows="2" maxlength="' + COMMENT_MAX + '" placeholder="Написать…"></textarea>'
        + '<div class="cmt-actions"><button class="cmt-send">Отправить</button>'
        + '<button class="cmt-res">' + (d.resolved ? 'Вернуть' : 'Решено') + '</button></div>';
      const поле = it.body.querySelector('.cmt-input');
      const отправить = () => {
        const t = (поле.value || '').trim(); if (!t) return;
        const н = it.el.data.thread || (it.el.data.thread = []);
        if (н.length >= THREAD_MAX) { boardHint('В одной нити не больше ' + THREAD_MAX + ' записей'); return; }
        н.push({ text: t.slice(0, COMMENT_MAX), name: myLabel || 'Аноним', at: Date.now() });
        поле.value = ''; render(); syncWidget(it);
      };
      it.body.querySelector('.cmt-send').addEventListener('click', отправить);
      // Enter отправляет, Shift+Enter — перенос строки: так привычнее в переписке.
      поле.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); отправить(); } });
      it.body.querySelector('.cmt-fold').addEventListener('click', () => { it._open = false; render(); });
      it.body.querySelector('.cmt-res').addEventListener('click', () => {
        it.el.data.resolved = it.el.data.resolved ? undefined : true; render(); syncWidget(it);
      });
    };
    it.update = render; render();
  }
  function insertComment(at) { insertWidget('comment', { thread: [] }, at); }

  // — Карточка (двусторонняя): вопрос ↔ ответ, переворот по кнопке (как в Quizlet) —
  // Содержимое (front/back/цвет) синхронизируется; ТЕКУЩАЯ сторона — локальная у
  // каждого зрителя (переворот не мешает соседям, как настоящие карточки).
  const CARD_COLORS = STICKY_COLORS;
  const CARD_FLIP_SVG = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/></svg>';
  function buildCard(it) {
    if (it._side == null) it._side = 0; // 0 — лицо (вопрос), 1 — оборот (ответ); ЛОКАЛЬНО
    const render = () => {
      const d = it.el.data, col = d.color || CARD_COLORS[0], back = !!it._side;
      it.wrapper.style.background = col;
      it.body.innerHTML = '<div class="stk-colors">' + CARD_COLORS.map((c) => '<span class="stk-c' + (c === col ? ' on' : '') + '" data-c="' + c + '" style="background:' + c + '"></span>').join('') + '</div>'
        + '<div class="card-head"><span class="card-label">' + (back ? 'Ответ' : 'Вопрос') + '</span><button class="card-flip" title="Перевернуть карточку">' + CARD_FLIP_SVG + ' Перевернуть</button></div>'
        + '<textarea class="stk-text card-text" placeholder="' + (back ? 'Ответ…' : 'Вопрос…') + '">' + escapeAttr(back ? (d.back || '') : (d.front || '')) + '</textarea>';
      const ta = it.body.querySelector('.card-text');
      ta.addEventListener('input', () => { if (it._side) it.el.data.back = ta.value; else it.el.data.front = ta.value; syncWidget(it); });
      it.body.querySelector('.card-flip').addEventListener('click', () => { it._side = it._side ? 0 : 1; render(); });
      it.body.querySelectorAll('.stk-c').forEach((s) => s.addEventListener('click', () => { it.el.data.color = s.dataset.c; render(); syncWidget(it); }));
    };
    it.update = render; render();
  }
  function insertCard() { insertWidget('card', { front: '', back: '', color: CARD_COLORS[0] }); }

  // ── ОБЫЧНЫЙ ТЕКСТ (textbox) — живой HTML на доске, правится на месте ───────
  // Не картинка и не Konva-узел: DOM-элемент на #widget-layer (как виджеты).
  // Клик — правка прямо в нём; тянешь — двигаешь; клик мимо — готово. Без рамок.
  function applyTboxStyle(ed, d) {
    ed.style.fontFamily = d.font || TEXT_FONT;
    ed.style.fontSize = (d.fontSize || 20) + 'px';
    ed.style.color = d.color || '#1f2937';
    ed.style.textAlign = d.align || 'left';
    ed.style.background = d.boxBg || '';
    // Начертание ВСЕГО поля. Внутри текста те же кнопки работают по-старому —
    // на выделенный кусок; здесь же настройка applies ко всей рамке сразу и
    // хранится в данных, поэтому переживает перезагрузку и уходит соседям.
    ed.style.fontWeight = d.bold ? '700' : '';
    ed.style.fontStyle = d.italic ? 'italic' : '';
    const deco = [];
    if (d.underline) deco.push('underline');
    if (d.strike) deco.push('line-through');
    ed.style.textDecoration = deco.length ? deco.join(' ') : '';
    if (d.wrapWidth) { ed.style.width = d.wrapWidth + 'px'; ed.style.maxWidth = 'none'; }
    else { ed.style.width = ''; ed.style.maxWidth = '640px'; }
  }
  let activeTbox = null;
  const tboxSyncTimers = {};
  function tboxSyncSoon(it) { const el = it._realEl || it.el, id = el.id; if (tboxSyncTimers[id]) clearTimeout(tboxSyncTimers[id]); tboxSyncTimers[id] = setTimeout(() => { send({ action: 'element_update', element: el }); }, 250); }
  // Что ПОКАЗЫВАТЬ в обычном текстовом поле: подставленные значения {выражений}
  // плюс настоящие ссылки. В самих данных при этом лежит ИСХОДНИК без разметки
  // ссылок — иначе при каждой правке текст обрастал бы тегами, а курсор попадал
  // бы внутрь ссылки и дописывал бы к ней лишнее.
  function tboxDisplayHtml(el) {
    const d = el.data || {};
    const frame = d.frame ? elements.get(d.frame) : null;
    return linkifyHtml(sanitizeHtml(renderDynamicText(d.html || '', frame)));
  }

  function upsertTextbox(el) {
    let it = widgetItems.get(el.id);
    if (it && it.isTbox) {
      it.el = el;
      if (document.activeElement !== it.ed) { const h = tboxDisplayHtml(el); if (it.ed.innerHTML !== h) it.ed.innerHTML = h; }
      applyTboxStyle(it.ed, el.data); repositionWidgets(); return;
    }
    const wrapper = document.createElement('div'); wrapper.className = 'tbox';
    const ed = document.createElement('div'); ed.className = 'tbox-edit'; ed.setAttribute('spellcheck', 'false'); ed.setAttribute('data-ph', 'Текст…');
    ed.innerHTML = tboxDisplayHtml(el);
    applyTboxStyle(ed, el.data);
    wrapper.appendChild(ed); widgetLayerEl.appendChild(wrapper);
    it = { el, wrapper, ed, isTbox: true, editing: false, editBefore: null };
    widgetItems.set(el.id, it);
    enableTboxInteract(it);
    repositionWidgets();
    if (el.data._new) { delete el.data._new; startTboxEdit(it, null); } // только что созданный — сразу правим
  }
  function enableTboxInteract(it) {
    const ed = it.ed, wrapper = it.wrapper;
    wrapper.addEventListener('mousedown', (e) => {
      if (it.editing || viewOnly) return; // уже правим / только-просмотр — не перехватываем
      if (e.target.closest('a.lnk')) return;  // клик по ссылке — открыть её, а не начать правку
      e.preventDefault();
      if (isAddKey(e)) { toggleSelect(it.el.id); return; }   // добавить к выделению, не править
      if (selected.has(it.el.id) && selected.size > 1) { domSelectionDrag(e); return; } // тащим всё выделение
      const s = stage.scaleX(), sx = e.clientX, sy = e.clientY, ox = it.el.data.x || 0, oy = it.el.data.y || 0;
      const before = clone(it.el); let moved = false;
      const mv = (ev) => {
        if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) > 3) { moved = true; wrapper.classList.add('moving'); }
        if (moved) { it.el.data.x = ox + (ev.clientX - sx) / s; it.el.data.y = oy + (ev.clientY - sy) / s; repositionWidgets(); }
      };
      const up = (ev) => {
        document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); wrapper.classList.remove('moving');
        if (moved) { send({ action: 'element_update', element: it.el }); histUpd(before, it.el); }
        // Клик без перетаскивания. Первый — ВЫБИРАЕТ поле: появляется рамка и
        // панель, настройки которой меняют оформление всего поля сразу. И только
        // повторный клик по уже выбранному полю открывает ввод текста. Раньше
        // клик сразу проваливался в набор, и до настроек поля было не добраться.
        else if (!selected.has(it.el.id)) selectOnly(it.el.id);
        else startTboxEdit(it, ev);
      };
      document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
    });
    // Двойной клик открывает правку даже по ссылке — иначе поле, состоящее из
    // одной только ссылки, нельзя было бы отредактировать вовсе.
    wrapper.addEventListener('dblclick', (e) => {
      if (viewOnly || it.editing) return;
      e.preventDefault(); e.stopPropagation();
      startTboxEdit(it, e);
    });
    ed.addEventListener('input', () => { it.el.data.html = ed.innerHTML; tboxSyncSoon(it); });
    ed.addEventListener('blur', () => { setTimeout(() => {
      if (!it.editing || document.activeElement === ed || (tboxBar && tboxBar.contains(document.activeElement))) return;
      // Свежесозданное пустое поле теряет фокус из-за mousedown по холсту — вернуть фокус, не удалять.
      if (it.grace && !(ed.textContent || '').trim()) { ed.focus(); return; }
      endTboxEdit(it);
    }, 0); });
    ed.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); ed.blur(); } });
  }
  function startTboxEdit(it, ev) {
    if (it.editing) return;
    activeTbox = it; it.editing = true; it.editBefore = clone(it.el); it.wrapper.classList.add('editing');
    // Правим ИСХОДНИК: без подставленных значений {выражений} и без разметки
    // ссылок — так курсор не попадает внутрь ссылки, а текст не обрастает тегами.
    it.ed.innerHTML = sanitizeHtml(it.el.data.html || '');
    it.ed.setAttribute('contenteditable', 'true'); it.ed.focus();
    it.grace = true; setTimeout(() => { it.grace = false; }, 400); // окно защиты от «мгновенной потери фокуса»
    requestAnimationFrame(() => { if (it.editing && document.activeElement !== it.ed) it.ed.focus(); }); // добить фокус после mousedown
    if (ev && document.caretRangeFromPoint) { try { const r = document.caretRangeFromPoint(ev.clientX, ev.clientY); if (r) { const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); } } catch (e) {} }
    else { const r = document.createRange(); r.selectNodeContents(it.ed); r.collapse(false); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); }
    showTboxBar(it);
  }
  function endTboxEdit(it) {
    if (!it.editing) return;
    it.editing = false; it.wrapper.classList.remove('editing'); it.ed.setAttribute('contenteditable', 'false');
    it.el.data.html = it.ed.innerHTML;
    if (activeTbox === it) activeTbox = null;
    hideTboxBar();
    if (!(it.ed.textContent || '').trim()) { histDel(it.el); send({ action: 'element_delete', id: it.el.id }); removeWidget(it.el.id); return; }
    it.ed.innerHTML = tboxDisplayHtml(it.el);   // правка окончена — снова показываем ссылки
    send({ action: 'element_update', element: it.el }); if (it.editBefore) histUpd(it.editBefore, it.el);
    syncTboxFieldBar();   // поле осталось выбранным — панель вернётся в режим «всё поле»
  }
  function insertTextbox() {
    const p = worldPoint() || viewportCenterWorld();
    const el = { id: uuid(), type: 'textbox', z: 0, data: { x: p.x, y: p.y, html: '', color: strokeColor, fontSize: 20, font: TEXT_FONT, align: 'left', _new: true } };
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    setTool('select');
  }
  // — Плавающая панель форматирования обычного текста (.tbox) —
  const tboxBar = document.getElementById('tbox-bar');
  const tbFontSel = document.getElementById('tb-font');
  const tbSizeInp = document.getElementById('tb-size');
  let tbBuilt = false;
  function tbCloseP() { ['tb-color-pop', 'tb-hilite-pop', 'tb-boxbg-pop'].forEach((id) => { const e = document.getElementById(id); if (e) e.classList.add('ps-hidden'); }); }
  function tbAfterExec() { if (!activeTbox) return; activeTbox.el.data.html = activeTbox.ed.innerHTML; tboxSyncSoon(activeTbox); syncTboxBar(); }
  // Поле выбрано, но текст не правится → команды панели меняют ВСЁ поле.
  function tbFieldMode() { return !!(activeTbox && !activeTbox.editing); }
  const TB_FIELD_FLAGS = { bold: 'bold', italic: 'italic', underline: 'underline', strikeThrough: 'strike' };
  const TB_FIELD_ALIGN = { justifyLeft: 'left', justifyCenter: 'center', justifyRight: 'right' };
  function tbApplyField(cmd) {
    const it = activeTbox; if (!it) return;
    const d = it.el.data;
    if (TB_FIELD_FLAGS[cmd]) { const k = TB_FIELD_FLAGS[cmd]; d[k] = !d[k]; }
    else if (TB_FIELD_ALIGN[cmd]) { d.align = TB_FIELD_ALIGN[cmd]; }
    else { boardHint('Списки задаются внутри текста — откройте поле двойным щелчком'); return; }
    applyTboxStyle(it.ed, d); tboxSyncSoon(it); syncTboxBar();
  }
  function tbExec(cmd, val) {
    if (!activeTbox) return;
    if (tbFieldMode()) { tbApplyField(cmd); return; }
    activeTbox.ed.focus();
    try { document.execCommand('styleWithCSS', false, true); } catch (e) {}
    document.execCommand(cmd, false, val == null ? null : val);
    tbAfterExec();
  }
  function syncTboxBar() {
    const field = tbFieldMode(), d = (activeTbox && activeTbox.el.data) || null;
    tboxBar.classList.toggle('tb-field', field);
    tboxBar.querySelectorAll('.te-b[data-cmd]').forEach((b) => {
      const cmd = b.dataset.cmd; let on = false;
      if (field && d) {
        if (TB_FIELD_FLAGS[cmd]) on = !!d[TB_FIELD_FLAGS[cmd]];
        else if (TB_FIELD_ALIGN[cmd]) on = (d.align || 'left') === TB_FIELD_ALIGN[cmd];
      } else {
        try { on = document.queryCommandState(cmd); } catch (e) {}
      }
      b.classList.toggle('te-on', on);
    });
  }
  function buildTboxBar() {
    if (tbBuilt) return; tbBuilt = true;
    TEXT_FONTS.forEach((f) => { const o = document.createElement('option'); o.value = f.css; o.textContent = f.label; o.style.fontFamily = f.css; tbFontSel.appendChild(o); });
    const mk = (gridId, onPick, noneLabel) => {
      const grid = document.getElementById(gridId);
      if (noneLabel) { const n = document.createElement('div'); n.className = 'cp-none'; n.textContent = noneLabel; n.addEventListener('mousedown', (e) => e.preventDefault()); n.addEventListener('click', () => onPick('')); grid.appendChild(n); }
      BASE_COLORS.forEach((c) => { const sw = document.createElement('div'); sw.className = 'cp-sw'; sw.style.background = c; sw.dataset.color = c; sw.title = c; sw.addEventListener('mousedown', (e) => e.preventDefault()); sw.addEventListener('click', () => onPick(c)); grid.appendChild(sw); });
    };
    mk('tb-color-grid', (c) => {
      const col = c || '#1f2937';
      if (tbFieldMode()) { activeTbox.el.data.color = col; applyTboxStyle(activeTbox.ed, activeTbox.el.data); tboxSyncSoon(activeTbox); }
      else { tbExec('foreColor', col); if (activeTbox) activeTbox.el.data.color = col; }
      document.getElementById('tb-color-dot').style.background = col; tbCloseP();
    });
    mk('tb-hilite-grid', (c) => { const col = c || 'transparent'; if (tbFieldMode()) { boardHint('Фон за текстом красит выделенный кусок — откройте поле двойным щелчком'); tbCloseP(); return; } if (activeTbox) activeTbox.ed.focus(); try { document.execCommand('styleWithCSS', false, true); } catch (e) {} if (!document.execCommand('hiliteColor', false, col)) document.execCommand('backColor', false, col); tbAfterExec(); tbCloseP(); }, 'Убрать фон');
    mk('tb-boxbg-grid', (c) => { if (!activeTbox) return; activeTbox.el.data.boxBg = c; applyTboxStyle(activeTbox.ed, activeTbox.el.data); tboxSyncSoon(activeTbox); tbCloseP(); }, 'Прозрачный');
    tboxBar.querySelectorAll('.te-b[data-cmd]').forEach((b) => { b.addEventListener('mousedown', (e) => e.preventDefault()); b.addEventListener('click', () => tbExec(b.dataset.cmd)); });
    // всё, кроме select/number, не должно уводить фокус из редактируемого поля
    tboxBar.addEventListener('mousedown', (e) => { if (!e.target.closest('#tb-font, #tb-size')) e.preventDefault(); });
    const pop = (btnId, popId) => { document.getElementById(btnId).addEventListener('click', (e) => { e.stopPropagation(); const el = document.getElementById(popId); const wasHidden = el.classList.contains('ps-hidden'); tbCloseP(); if (wasHidden) el.classList.remove('ps-hidden'); }); };
    pop('tb-color-btn', 'tb-color-pop'); pop('tb-hilite-btn', 'tb-hilite-pop'); pop('tb-boxbg-btn', 'tb-boxbg-pop');
    tbFontSel.addEventListener('change', () => { if (!activeTbox) return; activeTbox.el.data.font = tbFontSel.value; applyTboxStyle(activeTbox.ed, activeTbox.el.data); tboxSyncSoon(activeTbox); if (!tbFieldMode()) activeTbox.ed.focus(); });
    tbSizeInp.addEventListener('change', () => { if (!activeTbox) return; const v = Math.max(8, Math.min(200, parseInt(tbSizeInp.value, 10) || 20)); tbSizeInp.value = v; activeTbox.el.data.fontSize = v; applyTboxStyle(activeTbox.ed, activeTbox.el.data); tboxSyncSoon(activeTbox); if (!tbFieldMode()) activeTbox.ed.focus(); });
    // e.target на уровне документа не обязательно элемент (бывает сам
    // document), а у него нет closest — без проверки обработчик падал.
    document.addEventListener('mousedown', (e) => {
      if (tboxBar.classList.contains('ps-hidden')) return;
      const t = e.target;
      if (!t || !t.closest || !t.closest('#tbox-bar')) tbCloseP();
    }, true);
  }
  function positionTboxBar(it) {
    const r = it.wrapper.getBoundingClientRect();
    const w = tboxBar.offsetWidth || 380, h = tboxBar.offsetHeight || 44;
    let left = r.left, top = r.top - h - 8;
    if (top < 8) top = r.bottom + 8;
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - h - 8));
    tboxBar.style.left = left + 'px'; tboxBar.style.top = top + 'px';
  }
  function showTboxBar(it) {
    buildTboxBar();
    tbFontSel.value = it.el.data.font || TEXT_FONT;
    tbSizeInp.value = it.el.data.fontSize || 20;
    document.getElementById('tb-color-dot').style.background = it.el.data.color || '#1f2937';
    // «Фон окна» не нужен тексту внутри фигуры — у фигуры своя заливка (конфликт).
    document.getElementById('tb-boxbg-btn').style.display = it.isShapeText ? 'none' : '';
    tboxBar.classList.remove('ps-hidden');
    positionTboxBar(it);
    syncTboxBar();
  }
  function hideTboxBar() { tboxBar.classList.add('ps-hidden'); tbCloseP(); }

  // ── ЛАТЕХ-ТЕКСТ (тип 'text') — живой DOM на доске с формулами (MathJax), БЕЗ Konva ──
  // Отображение — DOM-элемент .mtext на #widget-layer (как textbox/стикер), поэтому нет
  // Konva-узла и трансформера → нет «чёрной рамки». Правка — через окно предпросмотра.
  function applyMtextStyle(body, d) {
    body.style.fontFamily = d.font || TEXT_FONT;
    body.style.fontSize = (d.fontSize || 20) + 'px';
    body.style.color = d.color || '#1f2937';
    body.style.textAlign = d.align || 'left';
    body.style.background = d.boxBg || '';
    if (d.wrapWidth) { body.style.width = d.wrapWidth + 'px'; body.style.maxWidth = 'none'; }
    else { body.style.width = ''; body.style.maxWidth = '720px'; }
  }
  function renderMtext(it) {
    const d = it.el.data;
    applyMtextStyle(it.body, d);
    const html = textContentHtml(d);
    it.body.innerHTML = (html && html.trim()) ? linkifyHtml(html) : '<span style="color:#b0b0ba">пусто</span>';
    if (!d.plain && window.MathJax && MathJax.typesetPromise) {
      it.body.querySelectorAll('mjx-assistive-mml').forEach((e) => e.remove());
      MathJax.typesetPromise([it.body]).then(() => { it.body.querySelectorAll('mjx-assistive-mml').forEach((e) => e.remove()); repositionWidgets(); }).catch(() => {});
    }
  }
  function upsertMathText(el) {
    let it = widgetItems.get(el.id);
    if (it && it.isMtext) { it.el = el; renderMtext(it); repositionWidgets(); return; }
    const wrapper = document.createElement('div'); wrapper.className = 'mtext';
    const body = document.createElement('div'); body.className = 'mtext-body';
    const del = document.createElement('button'); del.className = 'mtext-del'; del.title = 'Удалить'; del.textContent = '×';
    wrapper.appendChild(body); wrapper.appendChild(del);
    widgetLayerEl.appendChild(wrapper);
    it = { el, wrapper, body, del, isMtext: true };
    widgetItems.set(el.id, it);
    renderMtext(it);
    enableMtextInteract(it);
    repositionWidgets();
  }
  function enableMtextInteract(it) {
    const wrapper = it.wrapper;
    wrapper.addEventListener('mousedown', (e) => {
      if (viewOnly || e.target.closest('.mtext-del')) return;
      if (e.target.closest('a.lnk')) return;  // клик по ссылке — открыть её, а не тащить текст
      e.preventDefault();
      if (isAddKey(e)) { toggleSelect(it.el.id); return; }
      if (selected.has(it.el.id) && selected.size > 1) { domSelectionDrag(e); return; } // тащим всё выделение
      const s = stage.scaleX(), sx = e.clientX, sy = e.clientY, ox = it.el.data.x || 0, oy = it.el.data.y || 0;
      const before = clone(it.el); let moved = false;
      const mv = (ev) => {
        if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) > 3) { moved = true; wrapper.classList.add('moving'); }
        if (moved) { it.el.data.x = ox + (ev.clientX - sx) / s; it.el.data.y = oy + (ev.clientY - sy) / s; repositionWidgets(); }
      };
      const up = () => {
        document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); wrapper.classList.remove('moving');
        if (moved) { send({ action: 'element_update', element: it.el }); histUpd(before, it.el); }
        else selectOnly(it.el.id);   // клик — выбрать; правка по двойному щелчку
      };
      document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
    });
    wrapper.addEventListener('dblclick', (e) => { if (viewOnly) return; e.preventDefault(); e.stopPropagation(); openTextEditorFor(it.el); });
    it.del.addEventListener('click', (e) => { e.stopPropagation(); if (viewOnly) return; histDel(it.el); send({ action: 'element_delete', id: it.el.id }); removeWidget(it.el.id); });
  }

  // — Ползунок-параметр — имя (a,b,k…), диапазон и текущее значение; функции его читают —
  function buildSlider(it) {
    const render = () => {
      const d = it.el.data;
      it.body.innerHTML =
        '<div class="sld-top"><input class="sld-name" value="' + escapeAttr(d.name || 'k') + '" maxlength="3" title="Имя параметра"> = <span class="sld-val">' + fmtMeasure(d.value) + '</span></div>'
        + '<input type="range" class="sld-range" min="' + d.min + '" max="' + d.max + '" step="' + (d.step || 0.1) + '" value="' + d.value + '">'
        + '<div class="sld-bounds"><input class="sld-min" type="number" step="any" value="' + d.min + '"><input class="sld-max" type="number" step="any" value="' + d.max + '"></div>';
      const range = it.body.querySelector('.sld-range'), valEl = it.body.querySelector('.sld-val');
      range.addEventListener('input', () => { it.el.data.value = parseFloat(range.value); valEl.textContent = fmtMeasure(it.el.data.value); redrawFuncs(); applyConditions(); });
      range.addEventListener('change', () => syncWidget(it));
      it.body.querySelector('.sld-name').addEventListener('change', (e) => { it.el.data.name = (e.target.value.trim() || 'k'); syncWidget(it); redrawFuncs(); applyConditions(); });
      const mn = it.body.querySelector('.sld-min'), mx = it.body.querySelector('.sld-max');
      const updB = () => { it.el.data.min = parseFloat(mn.value); it.el.data.max = parseFloat(mx.value); range.min = it.el.data.min; range.max = it.el.data.max; syncWidget(it); };
      mn.addEventListener('change', updB); mx.addEventListener('change', updB);
      redrawFuncs(); // удалённое изменение значения тоже перерисует графики
    };
    it.update = render; render();
  }
  function nextParamName() { const used = new Set(); elements.forEach((e) => { if (e.type === 'slider' && e.data.name) used.add(e.data.name); }); for (const L of ['k', 'a', 'b', 'c', 'm', 'n', 'p', 'q', 't']) if (!used.has(L)) return L; return 'k'; }
  function insertSlider() { insertWidget('slider', { name: nextParamName(), min: -5, max: 5, value: 1, step: 0.1 }); }

  // — Таблица —
  // Клетки — прямоугольники без заливки, ширины столбцов и высоты строк хранятся
  // явно, чтобы границы можно было двигать. Клетка устроена как обычное
  // текстовое поле (те же ключи стиля), поэтому к ней подключается та же панель
  // форматирования, что и к тексту внутри фигур — «почти всё как в фигурах».
  //
  // Выделение клеток — ЛОКАЛЬНОЕ, соседям не рассылается: иначе двое, работая
  // за одной таблицей, отбирали бы друг у друга выделение.
  const TBL_W = 120, TBL_H = 36;      // размеры клетки по умолчанию
  const TBL_FILLS = ['', '#fff3bf', '#ffe3e3', '#e3fafc', '#e6fcf5', '#f3f0ff', '#f1f3f5'];

  function tblCell(d, r, c) {
    const row = (d.cells && d.cells[r]) || [];
    const v = row[c];
    if (v == null) return {};
    // Старые таблицы хранили клетку строкой — читаем и такие.
    if (typeof v === 'string') return { html: escapeHtml(v) };
    return v;
  }
  function tblSetCell(d, r, c, patch) {
    if (!d.cells) d.cells = [];
    if (!d.cells[r]) d.cells[r] = [];
    const cur = tblCell(d, r, c);
    d.cells[r][c] = Object.assign({}, cur, patch);
    return d.cells[r][c];
  }
  function tblColW(d, c) { return (d.colW && d.colW[c]) || TBL_W; }
  function tblRowH(d, r) { return (d.rowH && d.rowH[r]) || TBL_H; }
  function tblEnsureSizes(d) {
    if (!d.colW) d.colW = [];
    if (!d.rowH) d.rowH = [];
    for (let c = 0; c < d.cols; c++) if (!d.colW[c]) d.colW[c] = TBL_W;
    for (let r = 0; r < d.rows; r++) if (!d.rowH[r]) d.rowH[r] = TBL_H;
  }

  function buildTable(it) {
    if (!it._sel) it._sel = new Set();      // выбранные клетки, «r,c»
    const key = (r, c) => r + ',' + c;

    const render = () => {
      const d = it.el.data;
      tblEnsureSizes(d);
      const cols = d.colW.slice(0, d.cols).map((w) => w + 'px').join(' ');
      const rows = d.rowH.slice(0, d.rows).map((h) => h + 'px').join(' ');

      let html = '<div class="tbl" style="grid-template-columns:' + cols + ';grid-template-rows:' + rows + '">';
      for (let r = 0; r < d.rows; r++) {
        for (let c = 0; c < d.cols; c++) {
          const cell = tblCell(d, r, c);
          const sel = it._sel.has(key(r, c)) ? ' sel' : '';
          html += '<div class="tcell' + sel + '" data-r="' + r + '" data-c="' + c + '"'
            + ' style="background:' + escapeAttr(cell.boxBg || '') + '">'
            + '<div class="tcell-in">' + linkifyClickable(cell.html || '') + '</div></div>';
        }
      }
      html += '</div>';
      html += '<div class="tbl-tools">'
        + '<button data-act="addrow" title="Добавить строку">+ стр.</button>'
        + '<button data-act="delrow" title="Убрать последнюю строку">− стр.</button>'
        + '<button data-act="addcol" title="Добавить столбец">+ стлб.</button>'
        + '<button data-act="delcol" title="Убрать последний столбец">− стлб.</button>'
        + '</div>';
      it.body.innerHTML = html;

      const grid = it.body.querySelector('.tbl');
      // Стиль клетки применяем после вставки: цвет текста, шрифт, начертание.
      grid.querySelectorAll('.tcell').forEach((td) => {
        const cell = tblCell(d, +td.dataset.r, +td.dataset.c);
        applyTboxStyle(td.querySelector('.tcell-in'), Object.assign({ fontSize: 14 }, cell, { boxBg: '' }));
      });
      addResizeHandles(grid, d);
      wireCells(grid, d);
      wireTools();
      updateTblBar();
    };

    // ── Границы: тянем — меняем ширину столбца или высоту строки ──────────
    function addResizeHandles(grid, d) {
      let x = 0;
      for (let c = 0; c < d.cols - 1; c++) {
        x += tblColW(d, c);
        const h = document.createElement('div');
        h.className = 'tbl-vh'; h.style.left = x + 'px';
        h.title = 'Потяните — изменится ширина столбца';
        h.addEventListener('mousedown', (e) => startLineDragT(e, 'col', c));
        grid.appendChild(h);
      }
      let y = 0;
      for (let r = 0; r < d.rows - 1; r++) {
        y += tblRowH(d, r);
        const h = document.createElement('div');
        h.className = 'tbl-hh'; h.style.top = y + 'px';
        h.title = 'Потяните — изменится высота строки';
        h.addEventListener('mousedown', (e) => startLineDragT(e, 'row', r));
        grid.appendChild(h);
      }
    }
    function startLineDragT(e, kind, i) {
      e.preventDefault(); e.stopPropagation();
      const d = it.el.data, s = stage.scaleX();
      const start = (kind === 'col') ? e.clientX : e.clientY;
      const was = (kind === 'col') ? tblColW(d, i) : tblRowH(d, i);
      const before = clone(it.el);
      const mv = (ev) => {
        const delta = ((kind === 'col' ? ev.clientX : ev.clientY) - start) / s;
        const v = Math.max(28, Math.round(was + delta));
        if (kind === 'col') d.colW[i] = v; else d.rowH[i] = v;
        render();
      };
      const up = () => {
        document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up);
        syncWidget(it); histUpd(before, it.el); syncConnectorsOf([it.el.id]);
      };
      document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
    }

    // ── Выбор клеток ─────────────────────────────────────────────────────
    function selectRange(r0, c0, r1, c1, additive) {
      if (!additive) it._sel.clear();
      for (let r = Math.min(r0, r1); r <= Math.max(r0, r1); r++) {
        for (let c = Math.min(c0, c1); c <= Math.max(c0, c1); c++) it._sel.add(key(r, c));
      }
    }
    function wireCells(grid, d) {
      grid.querySelectorAll('.tcell').forEach((td) => {
        const r = +td.dataset.r, c = +td.dataset.c;
        td.addEventListener('mousedown', (e) => {
          if (it._editing) return;                       // идёт правка — не мешаем
          e.stopPropagation();                           // не тащить таблицу
          if (isAddKey(e)) { const k = key(r, c); if (it._sel.has(k)) it._sel.delete(k); else it._sel.add(k); render(); return; }
          selectRange(r, c, r, c, false);
          render();
          // Протяжка по клеткам — выбор прямоугольного участка.
          const mv = (ev) => {
            const t = document.elementFromPoint(ev.clientX, ev.clientY);
            const cell = t && t.closest ? t.closest('.tcell') : null;
            if (!cell || !grid.contains(cell)) return;
            selectRange(r, c, +cell.dataset.r, +cell.dataset.c, false);
            render();
          };
          const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); };
          document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
        });
        td.addEventListener('dblclick', (e) => { e.stopPropagation(); startCellEdit(r, c); });
      });
    }

    // ── Правка текста в клетке ───────────────────────────────────────────
    // Подключаем ту же панель, что у текста внутри фигур: клетка хранит те же
    // ключи стиля, поэтому кнопки шрифта, цвета и начертания работают как есть.
    function startCellEdit(r, c) {
      if (viewOnly) return;
      const d = it.el.data;
      const cell = tblSetCell(d, r, c, {});
      const td = it.body.querySelector('.tcell[data-r="' + r + '"][data-c="' + c + '"]');
      if (!td) return;
      const ed = td.querySelector('.tcell-in');
      it._editing = { r: r, c: c, ed: ed };
      it._sel.clear(); it._sel.add(key(r, c));
      td.classList.add('editing');
      ed.setAttribute('contenteditable', 'true');
      ed.innerHTML = sanitizeHtml(cell.html || '');       // сырой html — для правки
      ed.focus();
      const rng = document.createRange(); rng.selectNodeContents(ed); rng.collapse(false);
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rng);
      const before = clone(it.el);
      activeTbox = { ed: ed, el: { id: it.el.id, data: cell }, _realEl: it.el, wrapper: it.wrapper, isShapeText: true, editing: true };
      showTboxBar(activeTbox);
      const finish = () => {
        ed.removeEventListener('blur', onBlur);
        ed.setAttribute('contenteditable', 'false');
        td.classList.remove('editing');
        tblSetCell(it.el.data, r, c, { html: ed.innerHTML });
        it._editing = null;
        if (activeTbox && activeTbox._realEl === it.el) { activeTbox = null; hideTboxBar(); }
        syncWidget(it); histUpd(before, it.el);
        render();
      };
      const onBlur = () => setTimeout(() => {
        if (document.activeElement === ed) return;
        if (tboxBar && tboxBar.contains(document.activeElement)) return;
        finish();
      }, 0);
      ed.addEventListener('blur', onBlur);
      ed.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { e.preventDefault(); ed.blur(); }
        else if (e.key === 'Tab') { e.preventDefault(); const nc = (c + 1) % it.el.data.cols; const nr = nc ? r : (r + 1) % it.el.data.rows; ed.blur(); setTimeout(() => startCellEdit(nr, nc), 30); }
      });
    }

    // ── Строки и столбцы ─────────────────────────────────────────────────
    function wireTools() {
      const tools = it.body.querySelector('.tbl-tools');
      tools.addEventListener('mousedown', (e) => e.stopPropagation());
      tools.addEventListener('click', (e) => {
        const b = e.target.closest('button'); if (!b) return;
        const d = it.el.data, a = b.dataset.act;
        const before = clone(it.el);
        if (a === 'addrow') { d.rows++; d.rowH.push(TBL_H); d.cells.push(new Array(d.cols).fill(null).map(() => ({}))); }
        else if (a === 'delrow' && d.rows > 1) { d.rows--; d.rowH.pop(); d.cells.pop(); }
        else if (a === 'addcol') { d.cols++; d.colW.push(TBL_W); d.cells.forEach((row) => row.push({})); }
        else if (a === 'delcol' && d.cols > 1) { d.cols--; d.colW.pop(); d.cells.forEach((row) => row.pop()); }
        else return;
        it._sel.clear();
        syncWidget(it); histUpd(before, it.el); render();
      });
    }

    // ── Панель заливки выбранных клеток ──────────────────────────────────
    function updateTblBar() {
      const bar = document.getElementById('tbl-bar');
      if (!bar) return;
      if (!it._sel.size || it._editing) { if (bar._owner === it) { bar.hidden = true; bar._owner = null; } return; }
      bar._owner = it;
      bar.hidden = false;
      if (!bar._built) {
        bar._built = true;
        bar.innerHTML = '<span class="tb-lbl">Заливка клеток</span>'
          + TBL_FILLS.map((c) => '<button class="tb-sw' + (c ? '' : ' none') + '" data-c="' + c + '"'
              + ' style="background:' + (c || '#fff') + '" title="' + (c ? c : 'без заливки') + '"></button>').join('');
        bar.addEventListener('mousedown', (e) => e.preventDefault());
        bar.addEventListener('click', (e) => {
          const b = e.target.closest('.tb-sw'); if (!b) return;
          const own = bar._owner; if (!own) return;
          const d = own.el.data, before = clone(own.el);
          own._sel.forEach((k) => { const p = k.split(','); tblSetCell(d, +p[0], +p[1], { boxBg: b.dataset.c }); });
          syncWidget(own); histUpd(before, own.el);
          if (own._render) own._render();
        });
      }
      const r = it.wrapper.getBoundingClientRect();
      bar.style.left = Math.max(8, Math.min(r.left, window.innerWidth - 260)) + 'px';
      bar.style.top = Math.max(8, r.top - 44) + 'px';
    }

    it._render = render;
    it.update = render;
    render();
  }

  // — Канбан —
  function buildKanban(it) {
    const render = () => {
      const d = it.el.data;
      let html = '<div class="kb-cols">';
      d.columns.forEach((col, ci) => {
        html += '<div class="kb-col"><div class="kb-coltitle" contenteditable="true" data-ci="' + ci + '">' + escapeAttr(col.title) + '</div>';
        col.cards.forEach((card, di) => {
          html += '<div class="kb-card" data-ci="' + ci + '" data-di="' + di + '"><span contenteditable="true">' + escapeAttr(card) + '</span>'
            + '<button class="kb-mv" data-ci="' + ci + '" data-di="' + di + '" data-dir="-1" title="Влево"' + (ci === 0 ? ' disabled' : '') + '>‹</button>'
            + '<button class="kb-mv" data-ci="' + ci + '" data-di="' + di + '" data-dir="1" title="Вправо"' + (ci === d.columns.length - 1 ? ' disabled' : '') + '>›</button>'
            + '<button class="kb-cardel" data-ci="' + ci + '" data-di="' + di + '">×</button></div>';
        });
        html += '<button class="kb-add" data-ci="' + ci + '">+ карточка</button></div>';
      });
      html += '</div>';
      it.body.innerHTML = html;
      it.body.querySelectorAll('.kb-coltitle').forEach((t) => t.addEventListener('blur', () => { it.el.data.columns[+t.dataset.ci].title = t.textContent; syncWidget(it); }));
      it.body.querySelectorAll('.kb-card span').forEach((sp) => sp.addEventListener('blur', () => { const card = sp.parentElement; it.el.data.columns[+card.dataset.ci].cards[+card.dataset.di] = sp.textContent; syncWidget(it); }));
      it.body.querySelectorAll('.kb-add').forEach((b) => b.addEventListener('click', () => { it.el.data.columns[+b.dataset.ci].cards.push('Новая карточка'); syncWidget(it); render(); }));
      it.body.querySelectorAll('.kb-cardel').forEach((b) => b.addEventListener('click', () => { it.el.data.columns[+b.dataset.ci].cards.splice(+b.dataset.di, 1); syncWidget(it); render(); }));
      it.body.querySelectorAll('.kb-mv').forEach((b) => b.addEventListener('click', () => {
        const ci = +b.dataset.ci, di = +b.dataset.di, to = ci + (+b.dataset.dir);
        const cols = it.el.data.columns; if (to < 0 || to >= cols.length) return;
        const card = cols[ci].cards.splice(di, 1)[0]; cols[to].cards.push(card);
        syncWidget(it); render();
      }));
    };
    it.update = render; render();
  }

  // — Таймер —
  function buildTimer(it) {
    const fmt = (s) => { s = Math.max(0, Math.round(s)); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); };
    const calcRemaining = () => {
      const d = it.el.data;
      if (d.running && d.startedAt) return Math.max(0, d.remaining - (Date.now() - d.startedAt) / 1000);
      return d.remaining;
    };
    const tick = () => { const disp = it.body.querySelector('.tm-disp'); if (disp) disp.textContent = fmt(calcRemaining()); if (calcRemaining() <= 0 && it.timer) { clearInterval(it.timer); it.timer = null; } };
    const render = () => {
      it.body.innerHTML = '<div class="tm-disp">' + fmt(calcRemaining()) + '</div>'
        + '<div class="wgt-actions"><button data-act="toggle">' + (it.el.data.running ? 'Пауза' : 'Старт') + '</button>'
        + '<button data-act="reset">Сброс</button><button data-act="m1">−1м</button><button data-act="p1">+1м</button></div>';
      it.body.querySelector('[data-act="toggle"]').addEventListener('click', () => {
        const d = it.el.data;
        if (d.running) { d.remaining = calcRemaining(); d.running = false; d.startedAt = 0; }
        else { d.running = true; d.startedAt = Date.now(); }
        syncWidget(it); render();
      });
      it.body.querySelector('[data-act="reset"]').addEventListener('click', () => { const d = it.el.data; d.running = false; d.startedAt = 0; d.remaining = d.duration; syncWidget(it); render(); });
      it.body.querySelector('[data-act="m1"]').addEventListener('click', () => { const d = it.el.data; d.duration = Math.max(0, d.duration - 60); d.remaining = Math.max(0, calcRemaining() - 60); d.startedAt = d.running ? Date.now() : 0; syncWidget(it); render(); });
      it.body.querySelector('[data-act="p1"]').addEventListener('click', () => { const d = it.el.data; d.duration += 60; d.remaining = calcRemaining() + 60; d.startedAt = d.running ? Date.now() : 0; syncWidget(it); render(); });
      // Тикаем ТОЛЬКО пока таймер идёт: на паузе и в покое показания не
      // меняются, а перерисовка четыре раза в секунду сажает батарею планшета.
      // render() зовётся при каждом изменении, поэтому отсчёт возобновится сам.
      if (it.timer) { clearInterval(it.timer); it.timer = null; }
      if (it.el.data.running) it.timer = setInterval(tick, 250);
    };
    it.update = render; render();
  }

  // — Голосование —
  // Голоса хранятся картой «кто → за какой вариант», а не счётчиками. Так у
  // каждого ровно один голос, переголосовать можно, а пересчёт всегда сходится,
  // даже если два голоса прилетели одновременно.
  //
  // Голос отправляется отдельным действием poll_vote, а не обычной правкой:
  // наблюдателю править доску нельзя, а голосовать он должен.
  const POLL_COLORS = ['#4d7cfe', '#27ae60', '#e67e22', '#8e44ad', '#e7505a', '#16a2b8'];

  function pollCounts(d) {
    const opts = d.options || [], counts = opts.map(() => 0);
    const votes = d.votes || {};
    Object.keys(votes).forEach((k) => {
      const i = votes[k];
      if (typeof i === 'number' && i >= 0 && i < counts.length) counts[i]++;
    });
    return counts;
  }
  function pollMyChoice(d) {
    const v = (d.votes || {})[String(myId)];
    return (typeof v === 'number') ? v : null;
  }

  function buildPoll(it) {
    const render = () => {
      const d = it.el.data;
      const opts = d.options || [];
      const counts = pollCounts(d);
      const total = counts.reduce((a, b) => a + b, 0);
      const mine = pollMyChoice(d);
      const open = d.showResults !== false || mine != null;   // свой голос видно всегда

      let html = '<div class="poll-q" contenteditable="' + (viewOnly ? 'false' : 'true')
        + '" data-ph="Вопрос">' + escapeHtml(d.title || '') + '</div>';
      html += '<div class="poll-opts">';
      opts.forEach((o, i) => {
        const n = counts[i];
        const pct = total ? Math.round(n * 100 / total) : 0;
        const on = (mine === i);
        html += '<button type="button" class="poll-opt' + (on ? ' on' : '') + '" data-i="' + i + '">'
          + '<span class="poll-fill" style="width:' + (open ? pct : 0) + '%;background:'
          + POLL_COLORS[i % POLL_COLORS.length] + '22"></span>'
          + '<span class="poll-mark"></span>'
          + '<span class="poll-label">' + escapeHtml(o) + '</span>'
          + (open ? '<span class="poll-num">' + n + (total ? ' · ' + pct + '%' : '') + '</span>' : '')
          + '</button>';
      });
      html += '</div>';
      html += '<div class="poll-foot">'
        + '<span class="poll-total">' + (total ? 'голосов: ' + total : 'пока никто не голосовал') + '</span>'
        + '<span class="poll-tools">'
        + '<button type="button" data-act="results" title="Показывать ли результаты до конца голосования">'
        + (d.showResults === false ? 'Показать всем' : 'Скрыть до конца') + '</button>'
        + '<button type="button" data-act="edit" title="Изменить варианты">Варианты</button>'
        + '<button type="button" data-act="reset" title="Убрать все голоса">Сброс</button>'
        + '</span></div>';
      it.body.innerHTML = html;

      // Вопрос правится прямо на месте.
      const q = it.body.querySelector('.poll-q');
      q.addEventListener('blur', () => {
        const t = (q.textContent || '').trim();
        if (t === (d.title || '')) return;
        d.title = t; syncWidget(it);
      });
      q.addEventListener('mousedown', (e) => e.stopPropagation());   // не тащить объект

      it.body.querySelectorAll('.poll-opt').forEach((b) => {
        b.addEventListener('click', () => {
          const i = +b.dataset.i;
          const was = pollMyChoice(d);
          const choice = (was === i) ? null : i;      // повторный клик снимает голос
          // Показываем сразу, не дожидаясь сервера: свой голос должен отзываться мгновенно.
          const votes = Object.assign({}, d.votes || {});
          if (choice === null) delete votes[String(myId)]; else votes[String(myId)] = choice;
          d.votes = votes;
          render();
          send({ action: 'poll_vote', id: it.el.id, choice: choice });
        });
      });

      const tools = it.body.querySelector('.poll-tools');
      tools.addEventListener('click', (e) => {
        const b = e.target.closest('button'); if (!b) return;
        e.stopPropagation();
        if (b.dataset.act === 'results') { d.showResults = (d.showResults === false); syncWidget(it); render(); }
        else if (b.dataset.act === 'reset') {
          uiConfirm('Убрать все голоса?', { danger: true, ok: 'Убрать' }).then((ok) => { if (!ok) return; d.votes = {}; syncWidget(it); render(); });
        } else if (b.dataset.act === 'edit') {
          uiPrompt('Варианты — по одному в строке:', (d.options || []).join('\n'), { multiline: true }).then((raw) => {
            if (raw == null) return;
            const list = raw.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 12);
            if (!list.length) return;
            d.options = list; d.votes = {};    // варианты сменились — прежние голоса не о том
            syncWidget(it); render();
          });
        }
      });
    };
    it.update = render; render();
  }

  function insertPoll() {
    insertWidget('poll', {
      title: 'Вопрос', options: ['Вариант 1', 'Вариант 2', 'Вариант 3'],
      votes: {}, showResults: true,
    });
  }

  // — Колесо случайного выбора —
  // Рисуем под плотность экрана (иначе на ретине края секторов мылят), крутим
  // с длинным замедлением и отбойником, который щёлкает по каждому сектору.
  const WHEEL_SIZE = 240;                    // видимый размер, px
  const WHEEL_PALETTE = ['#4d7cfe', '#e7505a', '#27ae60', '#e67e22', '#8e44ad', '#16a2b8', '#d63384', '#f1c40f', '#2dd4bf', '#f97316'];

  function wheelDraw(cv, opts, rot, winner) {
    const dpr = window.devicePixelRatio || 1;
    const S = WHEEL_SIZE, R = S / 2 - 10, cx = S / 2, cy = S / 2;
    if (cv.width !== S * dpr) { cv.width = S * dpr; cv.height = S * dpr; cv.style.width = S + 'px'; cv.style.height = S + 'px'; }
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, S, S);
    const n = Math.max(1, opts.length);

    // Обод — тонкая тень под колесом, чтобы оно не выглядело наклейкой.
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, R + 5, 0, 2 * Math.PI);
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = 'rgba(0,0,0,.22)'; ctx.shadowBlur = 12; ctx.shadowOffsetY = 3;
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rot || 0);
    for (let i = 0; i < n; i++) {
      const a0 = i / n * 2 * Math.PI, a1 = (i + 1) / n * 2 * Math.PI;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, R, a0, a1); ctx.closePath();
      ctx.fillStyle = WHEEL_PALETTE[i % WHEEL_PALETTE.length];
      ctx.fill();
      // Выпавший сектор притушаем остальные, а не подсвечиваем его: так виднее.
      if (winner != null && winner !== i) { ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.fill(); }
      ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.lineWidth = 1.5; ctx.stroke();

      // Подпись вдоль радиуса, обрезаем по ширине сектора.
      const label = String(opts[i] == null ? '' : opts[i]);
      if (label) {
        ctx.save();
        ctx.rotate((a0 + a1) / 2);
        ctx.fillStyle = (winner != null && winner !== i) ? '#8a8a94' : '#fff';
        ctx.font = (n > 8 ? '600 11px ' : '600 13px ') + 'system-ui, sans-serif';
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        let t = label;
        const maxW = R - 26;
        while (t.length > 1 && ctx.measureText(t).width > maxW) t = t.slice(0, -1);
        if (t !== label) t = t.slice(0, -1) + '…';
        ctx.shadowColor = 'rgba(0,0,0,.35)'; ctx.shadowBlur = 2;
        ctx.fillText(t, R - 12, 0);
        ctx.restore();
      }
    }
    ctx.restore();

    // Втулка.
    ctx.beginPath(); ctx.arc(cx, cy, 15, 0, 2 * Math.PI);
    ctx.fillStyle = '#fff'; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = '#e0e0e8'; ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, 4.5, 0, 2 * Math.PI);
    ctx.fillStyle = '#c2c2ce'; ctx.fill();
  }

  // Отбойник справа: отклоняется, когда мимо проходит граница сектора.
  function wheelDrawPointer(el, kick) {
    el.style.transform = 'rotate(' + (kick || 0) + 'deg)';
  }

  function buildWheel(it) {
    const render = () => {
      const opts = it.el.data.options || [];
      it.body.innerHTML = '<div class="wh-stage">'
        + '<canvas class="wh-canvas"></canvas>'
        + '<div class="wh-pointer"></div>'
        + '</div>'
        + '<div class="wh-result"></div>'
        + '<textarea class="wh-opts" rows="3" placeholder="по одному варианту в строке">' + escapeAttr(opts.join('\n')) + '</textarea>'
        + '<div class="wgt-actions"><button data-act="spin">Крутить</button></div>';
      const cv = it.body.querySelector('.wh-canvas');
      const ptr = it.body.querySelector('.wh-pointer');
      const res = it.body.querySelector('.wh-result');
      const btn = it.body.querySelector('[data-act="spin"]');
      wheelDraw(cv, it.el.data.options || [], it._rot || 0, it._winner);
      if (it._winner != null && (it.el.data.options || [])[it._winner] != null) {
        res.textContent = 'Выпало: ' + it.el.data.options[it._winner];
        res.classList.add('on');
      }

      it.body.querySelector('.wh-opts').addEventListener('blur', (e) => {
        it.el.data.options = e.target.value.split('\n').map((s) => s.trim()).filter(Boolean);
        it._winner = null; syncWidget(it); render();
      });

      btn.addEventListener('click', () => {
        const o = it.el.data.options || [];
        if (!o.length || it._spinning) return;
        it._spinning = true; it._winner = null;
        btn.disabled = true; res.textContent = ''; res.classList.remove('on');

        const pick = Math.floor(Math.random() * o.length);
        const seg = 2 * Math.PI / o.length;
        // Останавливаемся так, чтобы середина выпавшего сектора смотрела вправо,
        // где стоит отбойник. Небольшой сдвиг внутри сектора — чтобы колесо не
        // замирало каждый раз в одной и той же позе.
        const jitter = (Math.random() - 0.5) * seg * 0.5;
        const turns = 6 + Math.floor(Math.random() * 3);          // 6–8 оборотов
        const start = it._rot || 0;
        const base = 2 * Math.PI * turns;
        const target = start + base + ((2 * Math.PI - ((pick + 0.5) * seg + jitter)) - (start % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
        const dur = 4200 + Math.random() * 900;
        const t0 = (window.performance && performance.now) ? performance.now() : Date.now();
        let lastSeg = -1;

        const anim = () => {
          const now = (window.performance && performance.now) ? performance.now() : Date.now();
          const k = Math.min(1, (now - t0) / dur);
          // Замедление пятой степени: долгий разгон-выбег без рывка в конце.
          const ease = 1 - Math.pow(1 - k, 5);
          it._rot = start + (target - start) * ease;
          wheelDraw(cv, o, it._rot, null);
          // Отбойник щёлкает на каждой границе сектора — и всё замедляется вместе с колесом.
          const segNow = Math.floor(((2 * Math.PI - (it._rot % (2 * Math.PI))) % (2 * Math.PI)) / seg);
          if (segNow !== lastSeg) {
            lastSeg = segNow;
            wheelDrawPointer(ptr, -14 * (1 - k) - 3);
            setTimeout(() => wheelDrawPointer(ptr, 0), 70);
          }
          if (k < 1) requestAnimationFrame(anim);
          else {
            it._spinning = false; it._winner = pick; btn.disabled = false;
            wheelDraw(cv, o, it._rot, pick);
            res.textContent = 'Выпало: ' + o[pick];
            res.classList.add('on');
          }
        };
        requestAnimationFrame(anim);
      });
    };
    it.update = render; render();
  }

  function onGeoDragMove(id, node) {
    const el = elements.get(id);
    if (!el) return;
    if (isDerivedPoint(el)) { recomputeGeometry(); return; } // пересечение не двигается
    captureDragSnap(dragStart ? Array.from(selected) : [id]); // для истории — всё выделение при групповом переносе
    if (el.type === 'point') {
      if (el.data.frame) {
        const fr = elements.get(el.data.frame);
        if (fr && el.data.on && el.data.on.line) {
          // Точка ЖЁСТКО на линии: тащим — скользит вдоль (проекция на линию → t).
          const line = elements.get(el.data.on.line), G = line ? lineGeom(line) : null;
          if (G) {
            let t = (node.x() - G.base.x) * G.u.x + (node.y() - G.base.y) * G.u.y;
            t = Math.max(G.tmin, Math.min(G.tmax, t));
            el.data.on.t = t;
            const lx = G.base.x + G.u.x * t, ly = G.base.y + G.u.y * t;
            node.position({ x: lx, y: ly });
            const m = frameLocalToMath(fr, lx, ly); el.data.mx = m.mx; el.data.my = m.my;
            recomputeGeometry();
          }
        } else if (fr && el.data.on && el.data.on.circle) {
          // Точка ЖЁСТКО на окружности: тащим — скользит по дуге (угол a от центра).
          const circ = elements.get(el.data.on.circle), C = circ ? circleGeom(circ) : null;
          if (C) {
            const a = Math.atan2(node.y() - C.cy, node.x() - C.cx);
            el.data.on.a = a;
            const lx = C.cx + C.r * Math.cos(a), ly = C.cy + C.r * Math.sin(a);
            node.position({ x: lx, y: ly });
            const m = frameLocalToMath(fr, lx, ly); el.data.mx = m.mx; el.data.my = m.my;
            recomputeGeometry();
          }
        } else if (fr) {
          // привязанная точка: локальная позиция узла → матем. коорды окна (+ привязка к сетке)
          let m = frameLocalToMath(fr, node.x(), node.y());
          if (el.data.snap) { m = { mx: Math.round(m.mx * 2) / 2, my: Math.round(m.my * 2) / 2 }; const L = frameMathToLocal(fr, m.mx, m.my); node.position({ x: L.x, y: L.y }); }
          el.data.mx = m.mx; el.data.my = m.my; recomputeGeometry();
        }
        updatePointLabel(el);
      } else {
        const s = snapPoint({ x: node.x(), y: node.y() }, id);
        node.position({ x: s.x, y: s.y });
        el.data.x = s.x; el.data.y = s.y; el.data.on = s.on || undefined;
        recomputeGeometry(); // живой пересчёт зависимого (отрезки, измерения) при перетаскивании свободной точки
      }
    } else if (el.type === 'circle') {
      el.data.x = node.x(); el.data.y = node.y();
      recomputeGeometry();
    }
    moveDragFollowers(id, node); // тащим остальную группу за точкой/окружностью (не замораживаем)
    positionHandles();
    layer.batchDraw();
  }

  function onGeoDragEnd(id, node) {
    const el = elements.get(id);
    if (!el) return;
    if (el.type === 'circle') { el.data.x = node.x(); el.data.y = node.y(); }
    send({ action: 'element_update', element: el });
    // Точки, привязанные к этой окружности, изменили положение — пусть и у
    // других участников пересчитается (их `on.a` тот же, x/y они посчитают сами).
    commitDragFollowers(id); dragStart = null; // синкнуть ведомых группы + сбросить (иначе оставался «висеть»)
    recomputeGeometry();
    commitDragSnap();
    positionHandles();
  }

  function nextPointLabel() {
    // Первая свободная буква (образы переиспользуют букву источника, буквы не пропускаем).
    const used = new Set();
    elements.forEach((el) => { if (el.type === 'point' && el.data.label) used.add(el.data.label); });
    for (let i = 0; i < 26; i++) { const L = String.fromCharCode(65 + i); if (!used.has(L)) return L; }
    for (let k = 1; ; k++) { const L = 'P' + k; if (!used.has(L)) return L; }
  }

  function placePoint() { newPointAt(worldPoint()); }

  // ── Встроенные страницы (iframe) ───────────────────────────────────────
  // Что синхронизируется, а что нет — и почему.
  //
  // Браузер намеренно не даёт родительской странице заглядывать внутрь чужого
  // сайта во фрейме: нельзя узнать ни прокрутку, ни введённый текст, ни секунду
  // видео. Это защита, а не недоработка, и обойти её нельзя. Поэтому:
  //   • ВСЕГДА синхронно: сам объект — адрес, положение, размер, подпись.
  //     Вставил — появилось у всех; подвинул — уехало у всех.
  //   • ВСЕГДА синхронно: смена адреса и «перезагрузить у всех». Для Desmos,
  //     Google Документов и ссылок с якорем адрес и ЕСТЬ состояние, поэтому это
  //     покрывает большую часть случаев.
  //   • ДЛЯ ВИДЕО: у плеера YouTube есть свой канал управления, и через него мы
  //     рассылаем «включить», «пауза» и «всем на мою секунду».
  //   • НЕ синхронно: прокрутка и ввод внутри обычной страницы. У каждого свои.
  //     Так и написано под объектом, чтобы это не было сюрпризом на занятии.

  // Разрешаем только настоящие веб-адреса. Проверка нужна ИМЕННО при отрисовке:
  // данные приходят от других участников, а адрес вида javascript:… во фрейме
  // выполнился бы уже в контексте нашей страницы — это была бы дыра.
  // Разрешённые для встраивания сервисы. Ровно те, которые доска умеет
  // распознавать ниже по коду; чужой сайт внутри урока участникам не нужен, а
  // грузится он у всех сразу, без спроса.
  const EMBED_HOSTS = [
    'youtube.com', 'youtu.be', 'youtube-nocookie.com',
    'vimeo.com', 'rutube.ru',
    'docs.google.com', 'drive.google.com',
    'desmos.com', 'geogebra.org',
    'wikipedia.org',
  ];
  function embedHostAllowed(host) {
    const h = String(host || '').toLowerCase().replace(/^www\./, '');
    // Поддомены разрешаем (m.youtube.com, player.vimeo.com, ru.wikipedia.org),
    // но только настоящие: проверяем по границе точки, иначе «notyoutube.com»
    // прошёл бы как «youtube.com».
    return EMBED_HOSTS.some((d) => h === d || h.endsWith('.' + d));
  }
  function safeEmbedUrl(u) {
    const s = String(u == null ? '' : u).trim();
    if (!/^https?:\/\//i.test(s)) return '';
    try { return embedHostAllowed(new URL(s).hostname) ? s : ''; }
    catch (e) { return ''; }
  }

  // Приводим ссылку к встраиваемому виду: обычная ссылка на YouTube во фрейме
  // не открывается, нужен адрес плеера. Заодно узнаём, чем управлять.
  function normalizeEmbedUrl(raw) {
    const src = String(raw == null ? '' : raw).trim();
    if (!/^https?:\/\//i.test(src)) return null;
    let u;
    try { u = new URL(src); } catch (e) { return null; }
    const host = u.hostname.replace(/^www\./, '');

    let vid = null;
    if (host === 'youtu.be') vid = u.pathname.slice(1).split('/')[0];
    else if (host === 'youtube.com' || host === 'youtube-nocookie.com' || host === 'm.youtube.com') {
      if (u.pathname === '/watch') vid = u.searchParams.get('v');
      else if (u.pathname.indexOf('/shorts/') === 0) vid = u.pathname.split('/')[2];
      else if (u.pathname.indexOf('/embed/') === 0) vid = u.pathname.split('/')[2];
    }
    if (vid && /^[A-Za-z0-9_-]{6,20}$/.test(vid)) {
      const t = parseInt(u.searchParams.get('t') || u.searchParams.get('start') || '0', 10) || 0;
      return {
        // nocookie-домен: YouTube не ставит рекламные куки ученикам.
        url: 'https://www.youtube-nocookie.com/embed/' + vid
             + '?enablejsapi=1&rel=0&modestbranding=1&playsinline=1' + (t ? '&start=' + t : ''),
        src: src, kind: 'youtube', title: 'Видео YouTube',
      };
    }
    if (host === 'vimeo.com') {
      const id = (u.pathname.match(/\/(\d+)/) || [])[1];
      if (id) return { url: 'https://player.vimeo.com/video/' + id, src: src, kind: 'page', title: 'Видео Vimeo' };
    }
    if (host === 'player.vimeo.com') return { url: src, src: src, kind: 'page', title: 'Видео Vimeo' };
    // Rutube: обычная ссылка на ролик во фрейм не пускается, нужен адрес плеера.
    if (host === 'rutube.ru') {
      const m2 = u.pathname.match(/^\/video\/(?:private\/)?([0-9a-f]{16,40})/i);
      if (m2) return { url: 'https://rutube.ru/play/embed/' + m2[1], src: src, kind: 'page', title: 'Видео Rutube' };
      if (u.pathname.indexOf('/play/embed/') === 0) return { url: src, src: src, kind: 'page', title: 'Видео Rutube' };
    }
    // VK Видео: собрать адрес плеера из обычной ссылки нельзя (нужен ключ из кода
    // вставки), поэтому принимаем только готовый адрес плеера.
    if ((host === 'vk.com' && u.pathname.indexOf('/video_ext.php') === 0) || host === 'vkvideo.ru') {
      return { url: src, src: src, kind: 'page', title: 'Видео VK' };
    }
    if (host === 'docs.google.com') {
      // Режим правки во фрейм не пускают — подменяем на режим просмотра.
      return { url: src.replace(/\/edit[^/]*$/, '/preview'), src: src, kind: 'page', title: 'Google Документы' };
    }
    if (host === 'desmos.com' && u.pathname.indexOf('/calculator') === 0) {
      return { url: u.origin + u.pathname + '?embed', src: src, kind: 'page', title: 'Desmos' };
    }
    return { url: src, src: src, kind: 'page', title: host };
  }

  // ── Разбор кода вставки (<iframe …>) ───────────────────────────────────
  // Сайты обычно дают не ссылку, а готовый кусок разметки под кнопкой
  // «Поделиться → Встроить». Принимаем и его.
  //
  // Ключевой момент: сам код мы НИКОГДА не вставляем в страницу. Из него
  // извлекаются только адрес и размеры, а фрейм строится наш собственный — в
  // песочнице и с проверенным адресом. Иначе чужая разметка приехала бы на
  // доску целиком, вместе с тем, что в ней может быть спрятано.
  function parseEmbedInput(text) {
    const raw = String(text == null ? '' : text).trim();
    if (!raw) return { error: 'Пусто — вставьте ссылку или код для вставки.' };

    // Обычная ссылка — разбираем как раньше.
    if (raw.indexOf('<') < 0) {
      const info = normalizeEmbedUrl(raw);
      return info || { error: 'Нужна ссылка, начинающаяся с http:// или https://' };
    }

    // Разметку читаем через DOMParser: он строит «мёртвый» документ — скрипты в
    // нём не выполняются, картинки и фреймы не загружаются. Через innerHTML так
    // делать нельзя: там содержимое ожило бы прямо у нас на странице.
    let doc = null;
    try { doc = new DOMParser().parseFromString(raw, 'text/html'); } catch (e) { doc = null; }
    const fr = doc && doc.querySelector('iframe[src], iframe[data-src]');
    if (!fr) {
      return { error: /<script\b/i.test(raw)
        ? 'Этот код вставки работает через скрипт — такие мы не поддерживаем. Возьмите вариант с <iframe> или обычную ссылку на страницу.'
        : 'В коде не нашёлся <iframe>. Вставьте ссылку или код с тегом <iframe>.' };
    }

    let src = (fr.getAttribute('src') || fr.getAttribute('data-src') || '').trim();
    if (src.indexOf('//') === 0) src = 'https:' + src;   // адрес без схемы
    const info = normalizeEmbedUrl(src);
    if (!info) return { error: 'Адрес внутри кода не похож на обычную ссылку — вставка отклонена.' };

    // Размеры из кода берём, если они разумные (бывает width="100%").
    const w = parseInt(fr.getAttribute('width'), 10);
    const h = parseInt(fr.getAttribute('height'), 10);
    if (w > 100 && w < 4000) info.width = w;
    if (h > 80 && h < 4000) info.height = h;
    const t = (fr.getAttribute('title') || '').trim();
    if (t) info.title = t.slice(0, 60);
    return info;
  }

  // ── Диалог вставки ─────────────────────────────────────────────────────
  // Системное окошко prompt() не годится: код вставки многострочный, и в
  // однострочное поле он вставляется как попало.
  let embedDlgCb = null;
  function openEmbedDialog(initial, cb) {
    const dlg = document.getElementById('embed-dialog');
    const ta = document.getElementById('emb-input');
    const err = document.getElementById('emb-error');
    if (!dlg || !ta) {                       // подстраховка, если разметки нет
      uiPrompt('Ссылка или код для вставки:', initial || 'https://', { multiline: true }).then((v) => { if (v != null) cb(v); });
      return;
    }
    embedDlgCb = cb;
    if (err) err.textContent = '';
    ta.value = initial || '';
    dlg.hidden = false;
    setTimeout(() => { try { ta.focus(); ta.select(); } catch (e) {} }, 30);
  }
  function closeEmbedDialog() {
    const dlg = document.getElementById('embed-dialog');
    if (dlg) dlg.hidden = true;
    embedDlgCb = null;
  }
  function submitEmbedDialog() {
    const ta = document.getElementById('emb-input');
    const err = document.getElementById('emb-error');
    if (!ta || !embedDlgCb) return;
    const info = parseEmbedInput(ta.value);
    if (!info || !info.url) {
      if (err) err.textContent = (info && info.error) || 'Не удалось разобрать вставку.';
      return;
    }
    // Источник не из списка разрешённых. Отказать молча нельзя: человек будет
    // жать кнопку и не понимать, почему ничего не происходит.
    if (!safeEmbedUrl(info.url)) {
      if (err) {
        err.textContent = 'Такой сайт встраивать нельзя. Доступны: YouTube, '
          + 'Vimeo, Rutube, Google Документы, Desmos, GeoGebra и Википедия. '
          + 'Для остального дайте обычную ссылку в тексте.';
      }
      return;
    }
    const cb = embedDlgCb;
    closeEmbedDialog();
    cb(info);
  }
  (function initEmbedDialog() {
    const dlg = document.getElementById('embed-dialog');
    if (!dlg) return;
    const ok = document.getElementById('emb-ok');
    const cancel = document.getElementById('emb-cancel');
    const ta = document.getElementById('emb-input');
    if (ok) ok.addEventListener('click', submitEmbedDialog);
    if (cancel) cancel.addEventListener('click', closeEmbedDialog);
    dlg.addEventListener('mousedown', (e) => { if (e.target === dlg) closeEmbedDialog(); });
    if (ta) ta.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); closeEmbedDialog(); }
      // Enter отправляет, Shift+Enter — перенос строки (код бывает многострочным).
      else if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitEmbedDialog(); }
    });
  })();

  function insertEmbed() {
    // Точку вставки запоминаем СЕЙЧАС: пока человек вставляет код в диалог,
    // указатель уедет, и объект встал бы не туда.
    const at = worldPoint() || viewportCenterWorld();
    openEmbedDialog('', (info) => {
      insertWidget('embed', {
        width: info.width || (info.kind === 'youtube' ? 560 : 620),
        height: info.height || (info.kind === 'youtube' ? 315 : 420),
        url: info.url, src: info.src, title: info.title, kind: info.kind, rev: 1,
      }, at);
    });
    setTool('select');
  }

  // Команда плееру YouTube. Плеер слушает такие сообщения, потому что мы
  // добавили в адрес enablejsapi=1.
  function ytPost(frame, func, args) {
    if (!frame || !frame.contentWindow) return;
    try {
      frame.contentWindow.postMessage(JSON.stringify({ event: 'command', func: func, args: args || [] }), '*');
    } catch (e) { /* фрейм ещё не готов — не страшно */ }
  }

  // Плеер сам присылает своё состояние, если с ним «поздороваться». Так мы
  // узнаём текущую секунду, чтобы подтянуть к ней остальных.
  window.addEventListener('message', (ev) => {
    if (!/(^|\.)youtube(-nocookie)?\.com$/.test((function () {
      try { return new URL(ev.origin).hostname; } catch (e) { return ''; }
    })())) return;
    let m;
    try { m = JSON.parse(ev.data); } catch (e) { return; }
    if (!m || m.event !== 'infoDelivery' || !m.info) return;
    widgetItems.forEach((it) => {
      if (it.el.type !== 'embed' || !it.frame || it.frame.contentWindow !== ev.source) return;
      if (typeof m.info.currentTime === 'number') it._t = m.info.currentTime;
      if (typeof m.info.playerState === 'number') it._state = m.info.playerState;
    });
  });

  // Применить общее состояние воспроизведения, пришедшее от другого участника.
  function embedApplyPlay(it) {
    const d = it.el.data, p = d && d.play;
    if (!p || d.kind !== 'youtube' || !it.frame) return;
    if (it._playSeen === p.at) return;         // это состояние уже применяли
    it._playSeen = p.at;
    // Пока сообщение шло по сети, видео у отправителя ушло вперёд — учитываем.
    const drift = (p.state === 'playing') ? Math.max(0, (Date.now() - (p.at || 0)) / 1000) : 0;
    ytPost(it.frame, 'seekTo', [Math.max(0, (p.t || 0) + drift), true]);
    ytPost(it.frame, p.state === 'playing' ? 'playVideo' : 'pauseVideo');
  }
  function embedBroadcastPlay(it, state) {
    it.el.data.play = { state: state, t: it._t || 0, at: Date.now() };
    it._playSeen = it.el.data.play.at;
    ytPost(it.frame, 'seekTo', [it._t || 0, true]);
    ytPost(it.frame, state === 'playing' ? 'playVideo' : 'pauseVideo');
    syncWidget(it);
    boardHint(state === 'playing' ? 'Включили видео у всех' : 'Поставили на паузу у всех');
  }

  // «Крышка» поверх фрейма: пока она есть, объект можно таскать и выделять.
  // Нажали — работаем со страницей. Это состояние ЛОКАЛЬНОЕ: каждый решает сам.
  function setEmbedLive(it, on) {
    it._live = !!on;
    it.wrapper.classList.toggle('live', it._live);
  }

  function buildEmbed(it) {
    it.wrapper.classList.add('wgt-embed');

    const tools = document.createElement('span');
    tools.className = 'emb-tools';
    it.bar.insertBefore(tools, it.bar.querySelector('.wgt-del'));

    const wrap = document.createElement('div');
    wrap.className = 'emb-wrap';
    const frame = document.createElement('iframe');
    frame.className = 'emb-frame';
    // Песочница: чужая страница не сможет увести нашу вкладку на другой адрес.
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-presentation allow-popups-to-escape-sandbox');
    frame.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen');
    frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    const lock = document.createElement('div');
    lock.className = 'emb-lock';
    lock.innerHTML = '<span>Нажмите, чтобы работать со страницей</span>';
    lock.addEventListener('click', () => setEmbedLive(it, true));
    const grip = document.createElement('div');
    grip.className = 'emb-grip';
    grip.title = 'Потянуть — изменить размер';
    wrap.appendChild(frame); wrap.appendChild(lock); wrap.appendChild(grip);
    const note = document.createElement('div');
    note.className = 'emb-note';
    it.body.appendChild(wrap);
    it.body.appendChild(note);
    it.frame = frame;
    it._live = false;
    it._t = 0;

    function applySize() {
      const d = it.el.data;
      const w = Math.max(200, d.width || 560), h = Math.max(140, d.height || 340);
      wrap.style.width = w + 'px';
      wrap.style.height = h + 'px';
      it.wrapper.style.width = w + 'px';
    }
    function applySrc() {
      const url = safeEmbedUrl(it.el.data.url);
      const key = url + '|' + (it.el.data.rev || 1);
      if (it._srcKey === key) return;
      it._srcKey = key;
      frame.src = url || 'about:blank';
      if (!url) note.textContent = 'Адрес не распознан — вставьте ссылку заново.';
    }
    function applyTools() {
      const d = it.el.data, video = d.kind === 'youtube';
      tools.innerHTML =
        (video
          ? '<button class="emb-play" title="Включить видео у всех">▶</button>'
            + '<button class="emb-pause" title="Поставить на паузу у всех">❙❙</button>'
            + '<button class="emb-here" title="Перемотать всех на мою секунду">⇥</button>'
          : '<button class="emb-reload" title="Перезагрузить страницу у всех">⟳</button>')
        + '<button class="emb-url" title="Сменить адрес — у всех участников">Адрес</button>'
        + '<button class="emb-open" title="Открыть в новой вкладке">↗</button>';
      note.textContent = video
        ? 'Кнопки ▶ ❙❙ ⇥ управляют просмотром у всех участников.'
        : 'Прокрутка и ввод здесь у каждого свои — браузер не даёт их передавать. Общее: адрес и кнопка ⟳.';
    }
    function render() {
      const d = it.el.data;
      it.bar.querySelector('.wgt-title').textContent = d.title || 'Страница';
      applySize(); applyTools(); applySrc();
      embedApplyPlay(it);
    }

    // Нажатия в шапке.
    tools.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      e.stopPropagation();
      const d = it.el.data;
      if (b.classList.contains('emb-play')) embedBroadcastPlay(it, 'playing');
      else if (b.classList.contains('emb-pause')) embedBroadcastPlay(it, 'paused');
      else if (b.classList.contains('emb-here')) embedBroadcastPlay(it, 'playing');
      else if (b.classList.contains('emb-reload')) {
        d.rev = (d.rev || 1) + 1; it._srcKey = null; applySrc(); syncWidget(it);
        boardHint('Перезагрузили страницу у всех');
      } else if (b.classList.contains('emb-open')) {
        const u = safeEmbedUrl(d.src || d.url);
        if (u) window.open(u, '_blank', 'noopener');
      } else if (b.classList.contains('emb-url')) {
        openEmbedDialog(d.src || d.url || '', (info) => {
          const before = clone(it.el);
          d.url = info.url; d.src = info.src; d.kind = info.kind; d.title = info.title;
          if (info.width) d.width = info.width;
          if (info.height) d.height = info.height;
          d.rev = (d.rev || 1) + 1; d.play = null;
          it._srcKey = null; render(); syncWidget(it); histUpd(before, it.el);
          boardHint('Адрес сменился у всех участников');
        });
      }
    });

    // Своя ручка размера: у обычных виджетов её нет, а встроенной странице она
    // нужна больше всего. Размер синхронизируется, как и положение.
    grip.addEventListener('mousedown', (e) => {
      e.preventDefault(); e.stopPropagation();
      const s = stage.scaleX();
      const sx = e.clientX, sy = e.clientY;
      const w0 = it.el.data.width || 560, h0 = it.el.data.height || 340;
      const before = clone(it.el);
      const mv = (ev) => {
        it.el.data.width = Math.max(200, w0 + (ev.clientX - sx) / s);
        it.el.data.height = Math.max(140, h0 + (ev.clientY - sy) / s);
        applySize();
      };
      const up = () => {
        document.removeEventListener('mousemove', mv);
        document.removeEventListener('mouseup', up);
        syncWidget(it); histUpd(before, it.el);
      };
      document.addEventListener('mousemove', mv);
      document.addEventListener('mouseup', up);
    });

    // Здороваемся с плеером, чтобы он присылал текущую секунду.
    frame.addEventListener('load', () => {
      if (it.el.data.kind !== 'youtube') return;
      const hello = () => {
        if (!it.frame || !it.frame.contentWindow) return;
        try { it.frame.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: 1, channel: 'widget' }), '*'); } catch (e) {}
      };
      hello(); setTimeout(hello, 400); setTimeout(hello, 1200);
      embedApplyPlay(it);
    });

    it.update = render;
    render();
  }

  // Клик мимо встроенной страницы — снова «накрываем» её, чтобы объект можно
  // было двигать и выделять.
  document.addEventListener('mousedown', (e) => {
    widgetItems.forEach((it) => {
      if (it.el.type !== 'embed' || !it._live) return;
      const inside = e.target.closest && e.target.closest('.wgt-embed') === it.wrapper;
      if (!inside) setEmbedLive(it, false);
    });
  }, true);

  // ── Математические рамки (окна с собственной системой координат) ───────
  // Окно: прямоугольник (x,y,width,height в координатах доски) + своя матем.
  // система (cx,cy — матем. координата центра окна, unit — px на 1 ед.). Внутри
  // рисуются оси/сетка и (позже) обрезанные по границе графики/прямые.
  const FRAME_HEADER = 0;   // плот заполняет всё окно: серой полосы сверху больше нет
  const FRAME_GRAB = 22;    // невидимая полоса-ручка сверху: за неё окно двигают, в ней крестик
  let frameMove = null;   // перетаскивание окна по доске (за шапку)
  let framePan = null;    // панорама матем. плоскости внутри окна
  let lineDrag = null;    // параллельный перенос линии-построения (двигаем опорные точки)
  let labelDrag = null;   // перетаскивание подписи точки (смещение в пределах радиуса)
  const frameSyncTimers = {};

  function fmtNum(v) { return String(+v.toFixed(6)); }
  function niceStep(unit) {
    const target = 48 / unit; // целимся ~48px между линиями
    const p = Math.pow(10, Math.floor(Math.log10(target)));
    const c = target / p;
    const n = c < 1.5 ? 1 : c < 3.5 ? 2 : c < 7.5 ? 5 : 10;
    return n * p;
  }

  function drawFrameGrid(ctx, el) {
    if (!el) return;
    const d = el.data;
    const W = d.width || 0, H = d.height || 0, unit = d.unit || 40;
    const plotTop = FRAME_HEADER, plotH = H - FRAME_HEADER;
    if (W <= 0 || plotH <= 0) return;
    const cxpx = W / 2, cypx = plotTop + plotH / 2;
    const X2P = (mx) => cxpx + (mx - d.cx) * unit;
    const Y2P = (my) => cypx - (my - d.cy) * unit;
    const xL = d.cx - cxpx / unit, xR = d.cx + (W - cxpx) / unit;
    const yB = d.cy - (H - cypx) / unit, yT = d.cy + (cypx - plotTop) / unit;
    const step = niceStep(unit);
    const sx = Math.ceil(xL / step) * step, sy = Math.ceil(yB / step) * step;
    // Настройки фона окна (по умолчанию — сетка линиями + оси с подписями).
    const gridOn = d.gridOn !== false, axesOn = d.axesOn !== false, dots = d.gridStyle === 'dots';
    const gc = d.gridColor || '#e4e6ee'; // цвет рисунка окна (линии/точки)
    // Волосяная линия и точка постоянного размера НА ЭКРАНЕ — ровно так же
    // рисуется фон самой доски. Прежде толщина здесь была задана в координатах
    // окна и росла вместе с приближением: на 200% сетка окна выходила вдвое
    // толще сетки доски рядом с ним.
    const мсш = stage.scaleX() || 1;
    const волос = 1 / мсш;
    ctx.save();
    if (gridOn && dots) {
      // Точки в узлах сетки.
      ctx.fillStyle = gc;
      const r = 1.1 / мсш;
      for (let mx = sx; mx <= xR; mx += step) { const px = X2P(mx); for (let my = sy; my <= yT; my += step) { ctx.beginPath(); ctx.arc(px, Y2P(my), r, 0, 2 * Math.PI); ctx.fill(); } }
    } else if (gridOn) {
      // Сетка линиями.
      ctx.beginPath(); ctx.lineWidth = волос; ctx.strokeStyle = gc;
      for (let mx = sx; mx <= xR; mx += step) { const px = X2P(mx); ctx.moveTo(px, plotTop); ctx.lineTo(px, H); }
      for (let my = sy; my <= yT; my += step) { const py = Y2P(my); ctx.moveTo(0, py); ctx.lineTo(W, py); }
      ctx.stroke();
    }
    // оси
    const ax = X2P(0), ay = Y2P(0);
    if (axesOn) {
      // Оси и подписи перекрашиваются вместе с рисунком (d.gridColor), иначе — свои дефолты.
      ctx.beginPath(); ctx.lineWidth = 1.4 / мсш; ctx.strokeStyle = d.gridColor || '#b8b8c2';
      if (ax >= 0 && ax <= W) { ctx.moveTo(ax, plotTop); ctx.lineTo(ax, H); }
      if (ay >= plotTop && ay <= H) { ctx.moveTo(0, ay); ctx.lineTo(W, ay); }
      ctx.stroke();
      // подписи делений
      ctx.fillStyle = d.gridColor || '#8a8a96'; ctx.font = '11px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      const ly = (ay >= plotTop && ay <= H - 14) ? ay + 3 : H - 14;
      for (let mx = sx; mx <= xR; mx += step) { if (Math.abs(mx) < step / 2) continue; ctx.fillText(fmtNum(mx), X2P(mx), ly); }
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      const lx = (ax >= 2 && ax <= W - 20) ? ax + 4 : 3;
      for (let my = sy; my <= yT; my += step) { if (Math.abs(my) < step / 2) continue; ctx.fillText(fmtNum(my), lx, Y2P(my)); }
    }
    ctx.restore();
  }

  function frameAtWorld(wx, wy, plotOnly) {
    let found = null;
    elements.forEach((el) => {
      if (el.type !== 'frame') return;
      const d = el.data;
      const top = d.y + (plotOnly ? FRAME_HEADER : 0);
      if (wx >= d.x && wx <= d.x + d.width && wy >= top && wy <= d.y + d.height) found = el;
    });
    return found;
  }

  // ── Координаты окна: матем. ↔ локальные px группы ↔ мировые ────────────
  function frameCenters(d) {
    const plotH = d.height - FRAME_HEADER;
    return { cxpx: d.width / 2, cypx: FRAME_HEADER + plotH / 2 };
  }
  function frameMathToLocal(fr, mx, my) {
    const d = fr.data, c = frameCenters(d);
    return { x: c.cxpx + (mx - d.cx) * d.unit, y: c.cypx - (my - d.cy) * d.unit };
  }
  function frameLocalToMath(fr, lpx, lpy) {
    const d = fr.data, c = frameCenters(d);
    return { mx: d.cx + (lpx - c.cxpx) / d.unit, my: d.cy - (lpy - c.cypx) / d.unit };
  }
  function frameWorldToMath(fr, wx, wy) { return frameLocalToMath(fr, wx - fr.data.x, wy - fr.data.y); }
  // Активное окно для создания фигуры: только если оно активно И курсор внутри.
  function frameForCreation() {
    // Привязываем к окну ПОД КУРСОРОМ (область графика), без требования «окно активно»:
    // рисуешь внутри окна → фигура принадлежит окну. Активность нужна лишь для панорамы плоскости.
    const w = worldPoint(); if (!w) return null;
    return frameAtWorld(w.x, w.y, true);
  }
  // Мировые координаты точки (свободной или привязанной к окну).
  function pointWorld(el) {
    if (!el || el.type !== 'point') return null;
    if (el.data.frame) {
      const fr = elements.get(el.data.frame); if (!fr) return { x: 0, y: 0 };
      const L = frameMathToLocal(fr, el.data.mx || 0, el.data.my || 0);
      return { x: fr.data.x + L.x, y: fr.data.y + L.y };
    }
    return { x: el.data.x || 0, y: el.data.y || 0 };
  }

  function syncFrameSoon(id) {
    if (frameSyncTimers[id]) clearTimeout(frameSyncTimers[id]);
    frameSyncTimers[id] = setTimeout(() => {
      const el = elements.get(id);
      if (el) send({ action: 'element_update', element: el });
    }, 250);
  }

  function attachFrameHandlers(node, id) {
    const header = node.findOne('.fheader');
    const del = node.findOne('.fdel');
    const startMove = (e) => {
      e.cancelBubble = true;
      const el = elements.get(id); if (!el) return;
      const w = worldPoint();
      frameMove = { id, sx: w.x, sy: w.y, ox: el.data.x, oy: el.data.y, moved: false, shift: isAddKey(e.evt) };
    };
    header.on('mousedown', startMove);
    // Полоса-ручка невидима и ничего не красит. Наведёшь на неё — курсор
    // «перемещение» и проступает крестик; ушёл — гаснут. Серой плашки нет.
    header.on('mouseenter', () => { stageEl.style.cursor = 'move'; del.opacity(0.9); layer.batchDraw(); });
    header.on('mouseleave', () => { stageEl.style.cursor = ''; del.opacity(0); layer.batchDraw(); });
    del.on('mousedown', (e) => { e.cancelBubble = true; });
    del.on('click tap', (e) => { e.cancelBubble = true; deleteWithDependents([id]); }); // окно + вся геометрия внутри
  }

  // Зум матем. плоскости внутри окна к точке курсора (lpx,lpy — лок. px окна).
  function frameZoomAt(el, wp, deltaY) {
    const d = el.data;
    const lpx = wp.x - d.x, lpy = wp.y - d.y;
    const plotH = d.height - FRAME_HEADER, cxpx = d.width / 2, cypx = FRAME_HEADER + plotH / 2;
    const mx = d.cx + (lpx - cxpx) / d.unit;
    const my = d.cy - (lpy - cypx) / d.unit;
    const factor = Math.min(1.25, Math.max(0.8, Math.exp(-deltaY * 0.0015)));
    d.unit = Math.min(4000, Math.max(2, d.unit * factor));
    d.cx = mx - (lpx - cxpx) / d.unit;
    d.cy = my + (lpy - cypx) / d.unit;
    recomputeGeometry(); // привязанная геометрия следует за плоскостью
    layer.batchDraw();
    syncFrameSoon(el.id);
  }

  // ── Математические функции: ОДНА таблица на все разборщики ─────────────
  // Их было ЧЕТЫРЕ копии: у графика y=f(x), у неявного уравнения, у числовых
  // выражений и отдельный список имён FUNC_NAMES. И они успели разойтись —
  // floor и min понимались в числовых выражениях и не понимались в графике.
  // Четвёртая опаснее всех: список имён решает, что считать параметром-
  // ползунком, и имя, забытое в нём, завело бы в окне фантомный ползунок
  // «sec» вместо вызова секанса. Поэтому таблица одна, а список из неё выводится.
  function _факториал(n) {
    n = Math.round(n);
    if (!isFinite(n) || n < 0 || n > 170) return NaN; // 171! уже за пределом double
    let r = 1; for (let i = 2; i <= n; i++) r *= i; return r;
  }
  const MATH_FN1 = {
    sin: Math.sin, cos: Math.cos, tan: Math.tan, tg: Math.tan,
    asin: Math.asin, acos: Math.acos, atan: Math.atan,
    arcsin: Math.asin, arccos: Math.acos, arctg: Math.atan,
    // Обратные тригонометрические: в задачах встречаются, а их не было вовсе.
    cot: (v) => 1 / Math.tan(v), ctg: (v) => 1 / Math.tan(v),
    sec: (v) => 1 / Math.cos(v), csc: (v) => 1 / Math.sin(v),
    acot: (v) => Math.PI / 2 - Math.atan(v), asec: (v) => Math.acos(1 / v), acsc: (v) => Math.asin(1 / v),
    sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
    coth: (v) => 1 / Math.tanh(v), sech: (v) => 1 / Math.cosh(v), csch: (v) => 1 / Math.sinh(v),
    asinh: Math.asinh, acosh: Math.acosh, atanh: Math.atanh,
    sqrt: Math.sqrt, cbrt: Math.cbrt, abs: Math.abs, exp: Math.exp,
    ln: Math.log,
    // log — ДЕСЯТИЧНЫЙ. Был натуральным: log(100) давало 4.6 вместо 2, хотя
    // этого ждут и Десмос, и школьная запись. Натуральный логарифм — это ln.
    log: (v) => Math.log10(v), lg: (v) => Math.log10(v), log2: (v) => Math.log2(v),
    floor: Math.floor, ceil: Math.ceil, round: (v) => Math.round(v),
    trunc: Math.trunc, sign: Math.sign, sgn: Math.sign,
    factorial: _факториал,
  };
  const MATH_FN2 = {
    pow: Math.pow, atan2: Math.atan2,
    // Остаток по МАТЕМАТИЧЕСКОМУ правилу: mod(-1, 3) = 2, а не −1, как даёт «%».
    mod: (a, b) => ((a % b) + b) % b,
    // Логарифм по основанию: log(2, 8) = 3. Имя то же, что у десятичного, —
    // какой из двух брать, решает число аргументов.
    log: (b, v) => Math.log(v) / Math.log(b),
    // Корень n-й степени. Для нечётной степени отрицательное число законно:
    // Math.pow(-8, 1/3) даёт NaN, а корень равен −2.
    nthroot: (n, v) => (v < 0 && Math.abs(Math.round(n) % 2) === 1) ? -Math.pow(-v, 1 / n) : Math.pow(v, 1 / n),
    nCr: (n, k) => _факториал(n) / (_факториал(k) * _факториал(n - k)),
    nPr: (n, k) => _факториал(n) / _факториал(n - k),
  };
  // Любое число аргументов, как в Десмосе: min(1, 2, 3).
  const MATH_FNN = {
    min: (a, b) => Math.min(a, b), max: (a, b) => Math.max(a, b),
    gcd: (a, b) => { a = Math.abs(Math.round(a)); b = Math.abs(Math.round(b)); while (b) { const t = b; b = a % b; a = t; } return a; },
    lcm: (a, b) => { const g = MATH_FNN.gcd(a, b); return g ? Math.abs(Math.round(a) * Math.round(b)) / g : 0; },
  };
  const MATH_CONST = { pi: Math.PI, e: Math.E, tau: 2 * Math.PI };

  function isMathName(n) { return (n in MATH_FN1) || (n in MATH_FN2) || (n in MATH_FNN); }
  // Как вызвать функцию с таким числом аргументов. null — такого сочетания нет
  // (скажем, sin с двумя аргументами): разборщик тогда откажется от формулы.
  function mathApply(name, k) {
    if (k === 1 && (name in MATH_FN1)) { const f = MATH_FN1[name]; return (a) => f(a[0]); }
    if (k === 2 && (name in MATH_FN2)) { const f = MATH_FN2[name]; return (a) => f(a[0], a[1]); }
    if (k >= 1 && (name in MATH_FNN)) { const f = MATH_FNN[name]; return (a) => a.reduce((p, v) => f(p, v)); }
    return null;
  }
  // Дочитать цифры в конце имени: log2, atan2. Только если получается известная
  // функция И дальше скобка — иначе «x2» стало бы именем, а не «x·2».
  function eatFnDigits(str, pos, name) {
    if (!/[0-9]/.test(str[pos] || '')) return { name: name, pos: pos };
    let j = pos, d = '';
    while (j < str.length && /[0-9]/.test(str[j])) d += str[j++];
    if (isMathName(name + d) && str[j] === '(') return { name: name + d, pos: j };
    return { name: name, pos: pos };
  }

  // ── Функции y=f(x) внутри окна ─────────────────────────────────────────
  // График — дочерний Konva.Shape окна (обрезается его clip). Сэмплируем по x
  // в координатах окна, рисуем ломаную с разрывами на асимптотах.
  const FUNC_COLORS = ['#1f6feb', '#e7505a', '#27ae60', '#8e44ad', '#e67e22', '#16a2b8'];

  // Компилирует выражение от x в функцию (или null). Синтаксис: + - * / ^,
  // скобки, неявное умножение (2x, (x+1)(x-1)), постфиксный факториал (5!),
  // модуль чертами (|x-1|), несколько аргументов через запятую (log(2,8)).
  // Набор самих функций и констант — в таблицах MATH_FN1/MATH_FN2/MATH_FNN
  // выше; перечислять их ещё и здесь значило бы завести пятую копию списка.
  function compileFunc(src) {
    let s = String(src).replace(/\s+/g, '').replace(/^y=/i, '').replace(/^f\(x\)=/i, '');
    if (!s) return null;
    let pos = 0; const peek = () => s[pos];
    const CONSTS = MATH_CONST;
    // Глубина вложенности модульных черт |…|. Без неё закрывающая черта была бы
    // принята за начало новой группы, и «|x|» не разобралось бы вовсе.
    let bars = 0;
    // Каждый узел — функция (x, env): env — значения ползунков-параметров {имя:знач}.
    function parseExpr() { let f = parseTerm(); while (peek() === '+' || peek() === '-') { const op = s[pos++]; const g = parseTerm(); const ff = f; f = (op === '+') ? (x, e) => ff(x, e) + g(x, e) : (x, e) => ff(x, e) - g(x, e); } return f; }
    function parseTerm() { let f = parseUnary(); while (true) { const c = peek(); if (c === '*' || c === '/') { pos++; const g = parseUnary(); const ff = f; f = (c === '*') ? (x, e) => ff(x, e) * g(x, e) : (x, e) => ff(x, e) / g(x, e); } else if (c && (/[0-9.a-zA-Z(]/.test(c) || (c === '|' && bars === 0))) { const g = parseFactor(); const ff = f; f = (x, e) => ff(x, e) * g(x, e); } else break; } return f; }
    function parseUnary() { const c = peek(); if (c === '-') { pos++; const g = parseUnary(); return (x, e) => -g(x, e); } if (c === '+') { pos++; return parseUnary(); } return parseFactor(); }
    function parseFactor() {
      let f = parseBase();
      // Постфиксный факториал: 5! = 120.
      while (peek() === '!') { pos++; const ff = f; f = (x, e) => _факториал(ff(x, e)); }
      if (peek() === '^') { pos++; const g = parseUnary(); const ff = f; f = (x, e) => Math.pow(ff(x, e), g(x, e)); }
      return f;
    }
    // Список аргументов в скобках. Раньше читался ровно ОДИН, и запятая ломала
    // разбор — поэтому min, mod и логарифм по основанию были недоступны.
    function parseArgs() {
      pos++; const args = [parseExpr()];
      while (peek() === ',') { pos++; args.push(parseExpr()); }
      if (peek() === ')') pos++; else throw 0;
      return args;
    }
    function parseBase() {
      const c = peek();
      if (c === '(') { pos++; const f = parseExpr(); if (peek() === ')') pos++; else throw 0; return f; }
      if (/[0-9.]/.test(c)) { let n = ''; while (pos < s.length && /[0-9.]/.test(s[pos])) n += s[pos++]; const v = parseFloat(n); return () => v; }
      // Модуль чертами: |x − 1|. Так его и пишут в школе.
      if (c === '|') { pos++; bars++; const f = parseExpr(); bars--; if (peek() === '|') pos++; else throw 0; return (x, e) => Math.abs(f(x, e)); }
      if (/[a-zA-Z]/.test(c)) {
        let name = ''; while (pos < s.length && /[a-zA-Z]/.test(s[pos])) name += s[pos++];
        const d = eatFnDigits(s, pos, name); name = d.name; pos = d.pos;
        if (name === 'x') return (x) => x;
        if (name in CONSTS) { const v = CONSTS[name]; return () => v; }
        if (isMathName(name)) {
          if (peek() !== '(') throw 0;
          const args = parseArgs(), call = mathApply(name, args.length);
          if (!call) throw 0;
          return (x, e) => call(args.map((a) => a(x, e)));
        }
        return (x, e) => (e && name in e) ? e[name] : NaN; // неизвестное имя — параметр-ползунок
      }
      throw 0;
    }
    try { const f = parseExpr(); if (pos < s.length) return null; return f; } catch (e) { return null; }
  }

  // Компилирует уравнение с ДВУМЯ переменными (x и y) в функцию F(x,y,env).
  // «lhs = rhs» → F = lhs − rhs (нуль-контур F=0 и есть кривая). Без «=» — сам F.
  // Синтаксис как у compileFunc + переменная y. Узлы — функции (x, y, e).
  function compileImplicit(src) {
    let s = String(src).replace(/\s+/g, '').replace(/^f\(x,?y?\)=/i, '');
    if (!s) return null;
    const eq = s.indexOf('=');
    const lhs = eq >= 0 ? s.slice(0, eq) : s;
    const rhs = eq >= 0 ? s.slice(eq + 1) : '0';
    const CONSTS = MATH_CONST;
    function build(str) {
      let pos = 0; const peek = () => str[pos];
      let bars = 0; // см. пояснение к чертам модуля в compileFunc
      function parseExpr() { let f = parseTerm(); while (peek() === '+' || peek() === '-') { const op = str[pos++]; const g = parseTerm(); const ff = f; f = (op === '+') ? (x, y, e) => ff(x, y, e) + g(x, y, e) : (x, y, e) => ff(x, y, e) - g(x, y, e); } return f; }
      function parseTerm() { let f = parseUnary(); while (true) { const c = peek(); if (c === '*' || c === '/') { pos++; const g = parseUnary(); const ff = f; f = (c === '*') ? (x, y, e) => ff(x, y, e) * g(x, y, e) : (x, y, e) => ff(x, y, e) / g(x, y, e); } else if (c && (/[0-9.a-zA-Z(]/.test(c) || (c === '|' && bars === 0))) { const g = parseFactor(); const ff = f; f = (x, y, e) => ff(x, y, e) * g(x, y, e); } else break; } return f; }
      function parseUnary() { const c = peek(); if (c === '-') { pos++; const g = parseUnary(); return (x, y, e) => -g(x, y, e); } if (c === '+') { pos++; return parseUnary(); } return parseFactor(); }
      function parseFactor() {
        let f = parseBase();
        while (peek() === '!') { pos++; const ff = f; f = (x, y, e) => _факториал(ff(x, y, e)); }
        if (peek() === '^') { pos++; const g = parseUnary(); const ff = f; f = (x, y, e) => Math.pow(ff(x, y, e), g(x, y, e)); }
        return f;
      }
      function parseArgs() {
        pos++; const args = [parseExpr()];
        while (peek() === ',') { pos++; args.push(parseExpr()); }
        if (peek() === ')') pos++; else throw 0;
        return args;
      }
      function parseBase() {
        const c = peek();
        if (c === '(') { pos++; const f = parseExpr(); if (peek() === ')') pos++; else throw 0; return f; }
        if (/[0-9.]/.test(c)) { let n = ''; while (pos < str.length && /[0-9.]/.test(str[pos])) n += str[pos++]; const v = parseFloat(n); return () => v; }
        if (c === '|') { pos++; bars++; const f = parseExpr(); bars--; if (peek() === '|') pos++; else throw 0; return (x, y, e) => Math.abs(f(x, y, e)); }
        if (/[a-zA-Z]/.test(c)) {
          let name = ''; while (pos < str.length && /[a-zA-Z]/.test(str[pos])) name += str[pos++];
          const d = eatFnDigits(str, pos, name); name = d.name; pos = d.pos;
          if (name === 'x') return (x) => x;
          if (name === 'y') return (x, y) => y;
          if (name in CONSTS) { const v = CONSTS[name]; return () => v; }
          if (isMathName(name)) {
            if (peek() !== '(') throw 0;
            const args = parseArgs(), call = mathApply(name, args.length);
            if (!call) throw 0;
            return (x, y, e) => call(args.map((a) => a(x, y, e)));
          }
          return (x, y, e) => (e && name in e) ? e[name] : NaN; // параметр-ползунок
        }
        throw 0;
      }
      try { const f = parseExpr(); if (pos < str.length) return null; return f; } catch (e) { return null; }
    }
    const L = build(lhs), R = build(rhs);
    if (!L || !R) return null;
    return (x, y, e) => L(x, y, e) - R(x, y, e);
  }
  // Нужна ли неявная кривая (двумерное уравнение), а не обычная y=f(x)?
  // Признак: есть «=» (после снятия ведущего y=) или встречается переменная y.
  function isImplicitExpr(raw) {
    let s = String(raw || '').replace(/\s+/g, '').replace(/^y=/i, '').replace(/^f\(x\)=/i, '');
    if (s.indexOf('=') >= 0) return true;
    return /(^|[^a-zA-Z])y([^a-zA-Z]|$)/.test(s);
  }

  // Вычислитель числовых/логических выражений над ИМЕНОВАННЫМИ значениями окна
  // (ползунки/параметры/измерения) + функции точек x(A)/y(A)/dist(A,B)/angle(A,B,C).
  // env = {имя:число, _pts:{ИМЯ:{x,y}}}. Сравнения дают 1/0. null при ошибке разбора.
  // Используется условной видимостью (data.showIf) и динамическим текстом ({expr}).
  function compileNum(src) {
    let s = String(src == null ? '' : src).replace(/\s+/g, '');
    s = s.replace(/≤/g, '<=').replace(/≥/g, '>=').replace(/≠/g, '!=').replace(/∧/g, '&&').replace(/∨/g, '||');
    if (!s) return null;
    let pos = 0; const peek = () => s[pos], two = () => s.substr(pos, 2);
    const CONST = MATH_CONST;
    // Постфиксного «!» здесь НЕТ намеренно: в этих выражениях «!» уже занят —
    // это отрицание (!a) и «не равно» (a != b). Факториал пишется factorial(n).
    // Модульных черт тоже нет: «||» здесь — логическое ИЛИ.
    function readName() { let n = ''; while (pos < s.length && /[a-zA-Z0-9_]/.test(s[pos])) n += s[pos++]; return n; }
    function ptLook(e, nm) { return e && e._pts && e._pts[nm.toUpperCase()]; }
    function parseOr() { let f = parseAnd(); while (two() === '||') { pos += 2; const g = parseAnd(), ff = f; f = (e) => (ff(e) || g(e)) ? 1 : 0; } return f; }
    function parseAnd() { let f = parseCmp(); while (two() === '&&') { pos += 2; const g = parseCmp(), ff = f; f = (e) => (ff(e) && g(e)) ? 1 : 0; } return f; }
    function parseCmp() {
      let f = parseAdd(); const t = two();
      if (t === '<=' || t === '>=' || t === '==' || t === '!=') { pos += 2; const g = parseAdd(), ff = f; return t === '<=' ? (e) => ff(e) <= g(e) ? 1 : 0 : t === '>=' ? (e) => ff(e) >= g(e) ? 1 : 0 : t === '==' ? (e) => ff(e) === g(e) ? 1 : 0 : (e) => ff(e) !== g(e) ? 1 : 0; }
      const c = peek();
      if (c === '<' || c === '>' || c === '=') { pos++; const g = parseAdd(), ff = f; return c === '<' ? (e) => ff(e) < g(e) ? 1 : 0 : c === '>' ? (e) => ff(e) > g(e) ? 1 : 0 : (e) => ff(e) === g(e) ? 1 : 0; }
      return f;
    }
    function parseAdd() { let f = parseMul(); while (peek() === '+' || peek() === '-') { const op = s[pos++], g = parseMul(), ff = f; f = op === '+' ? (e) => ff(e) + g(e) : (e) => ff(e) - g(e); } return f; }
    function parseMul() { let f = parseUnary(); while (true) { const c = peek(); if (c === '*' || c === '/') { pos++; const g = parseUnary(), ff = f; f = c === '*' ? (e) => ff(e) * g(e) : (e) => ff(e) / g(e); } else if (c && /[0-9.a-zA-Z(]/.test(c)) { const g = parseUnary(), ff = f; f = (e) => ff(e) * g(e); } else break; } return f; }
    function parseUnary() { const c = peek(); if (c === '-') { pos++; const g = parseUnary(); return (e) => -g(e); } if (c === '!') { pos++; const g = parseUnary(); return (e) => g(e) ? 0 : 1; } if (c === '+') { pos++; return parseUnary(); } return parsePow(); }
    function parsePow() { let f = parseBase(); if (peek() === '^') { pos++; const g = parseUnary(), ff = f; f = (e) => Math.pow(ff(e), g(e)); } return f; }
    function parseBase() {
      const c = peek();
      if (c == null) throw 0; // конец строки на месте операнда — выражение неполное
      if (c === '(') { pos++; const f = parseOr(); if (peek() === ')') pos++; else throw 0; return f; }
      if (/[0-9.]/.test(c)) { let n = ''; while (pos < s.length && /[0-9.]/.test(s[pos])) n += s[pos++]; const v = parseFloat(n); return () => v; }
      if (/[a-zA-Z_]/.test(c)) {
        const name = readName();
        if (name in CONST) { const v = CONST[name]; return () => v; }
        if (peek() === '(') {
          if (name === 'x' || name === 'y') { pos++; const p = readName(); if (peek() === ')') pos++; else throw 0; const key = name; return (e) => { const q = ptLook(e, p); return q ? (key === 'x' ? q.x : q.y) : NaN; }; }
          if (name === 'dist') { pos++; const a = readName(); if (peek() === ',') pos++; else throw 0; const b = readName(); if (peek() === ')') pos++; else throw 0; return (e) => { const A = ptLook(e, a), B = ptLook(e, b); return (A && B) ? Math.hypot(B.x - A.x, B.y - A.y) : NaN; }; }
          if (name === 'angle') { pos++; const a = readName(); if (peek() === ',') pos++; else throw 0; const b = readName(); if (peek() === ',') pos++; else throw 0; const cc = readName(); if (peek() === ')') pos++; else throw 0; return (e) => { const A = ptLook(e, a), V = ptLook(e, b), B = ptLook(e, cc); return (A && V && B) ? angleDeg(A, V, B) : NaN; }; }
          pos++; const args = [parseOr()]; while (peek() === ',') { pos++; args.push(parseOr()); } if (peek() === ')') pos++; else throw 0;
          const call = mathApply(name, args.length);
          if (call) return (e) => call(args.map((a) => a(e)));
          throw 0;
        }
        return (e) => (e && name in e) ? Number(e[name]) : NaN;
      }
      throw 0;
    }
    try { const f = parseOr(); if (pos < s.length) return null; return f; } catch (_) { return null; }
  }

  // Значения всех ползунков-параметров: {имя: число}. Функции читают их при отрисовке.
  // ВЫВОДИМ из таблицы, а не переписываем руками. Этот список решает, что
  // считать параметром-ползунком: имя функции, забытое здесь, завело бы в окне
  // фантомный ползунок «sec» вместо вызова секанса.
  const FUNC_NAMES = Object.keys(MATH_FN1).concat(Object.keys(MATH_FN2), Object.keys(MATH_FNN));
  // Незнакомые имена в формуле = параметры (не x, не pi/e, не имена функций).
  function funcVarsOf(expr, exclude) {
    const s = String(expr || '').replace(/^y=/i, '').replace(/^f\(x\)=/i, '');
    const skip = exclude || [];
    const out = [];
    (s.match(/[a-zA-Z]+/g) || []).forEach((n) => {
      if (n === 'x' || (n in MATH_CONST) || FUNC_NAMES.indexOf(n) >= 0 || skip.indexOf(n) >= 0) return;
      if (out.indexOf(n) < 0) out.push(n);
    });
    return out;
  }
  // Значения параметров для функции в окне: локальные параметры окна (frame.data.params)
  // имеют приоритет, глобальные ползунки-виджеты — запасной вариант (совместимость).
  function frameParamEnv(frameEl) {
    const env = {};
    elements.forEach((e) => { if (e.type === 'slider' && e.data.name) env[e.data.name] = Number(e.data.value); });
    const p = (frameEl && frameEl.data.params) || {};
    for (const k in p) env[k] = Number(p[k].v);
    return env;
  }
  // Завести в окне недостающие локальные параметры для незнакомых переменных формулы.
  function ensureFrameParams(fr, expr, exclude) {
    fr.data.params = fr.data.params || {};
    let changed = false;
    funcVarsOf(expr, exclude).forEach((v) => { if (!fr.data.params[v]) { fr.data.params[v] = { v: 1, min: -5, max: 5 }; changed = true; } });
    return changed;
  }
  // Перерисовать все графики (после изменения параметра-ползунка).
  function redrawFuncs() { layer.batchDraw(); }
  function drawFuncShape(ctx, shape) {
    const fel = elements.get(shape.id());
    if (!fel) return;
    const frameEl = elements.get(fel.data.frame);
    if (!frameEl) return;
    const d = frameEl.data;
    if (shape._expr !== fel.data.expr) { shape._fn = compileFunc(fel.data.expr); shape._expr = fel.data.expr; }
    const fn = shape._fn; if (!fn) return;
    const W = d.width, H = d.height, unit = d.unit;
    const plotTop = FRAME_HEADER, plotH = H - plotTop;
    if (W <= 0 || plotH <= 0) return;
    const cxpx = W / 2, cypx = plotTop + plotH / 2;
    const P2X = (px) => d.cx + (px - cxpx) / unit;
    const Y2P = (my) => cypx - (my - d.cy) * unit;
    const env = frameParamEnv(frameEl); // локальные параметры окна (+ глоб. ползунки)
    ctx.save();
    ctx.beginPath();
    ctx.lineWidth = 2; ctx.strokeStyle = fel.data.color || '#1f6feb';
    let pen = false, prevPy = 0;
    for (let px = 0; px <= W; px += 2) {
      let my; try { my = fn(P2X(px), env); } catch (e) { my = NaN; }
      const py = Y2P(my);
      if (!isFinite(py) || py < -plotH * 3 || py > H + plotH * 3) { pen = false; continue; }
      if (pen && Math.abs(py - prevPy) > plotH * 2.5) { ctx.moveTo(px, py); } // разрыв (асимптота)
      else if (!pen) { ctx.moveTo(px, py); }
      else { ctx.lineTo(px, py); }
      pen = true; prevPy = py;
    }
    ctx.stroke();
    ctx.restore();
  }

  // ── Анализ функций: касательная, площадь под кривой, пересечение графиков ──
  function planeMap(fr) {
    const d = fr.data, W = d.width, H = d.height, unit = d.unit, plotTop = FRAME_HEADER, plotH = H - plotTop, cxpx = W / 2, cypx = plotTop + plotH / 2;
    return { W: W, H: H, unit: unit, X2P: (x) => cxpx + (x - d.cx) * unit, P2X: (px) => d.cx + (px - cxpx) / unit, Y2P: (y) => cypx - (y - d.cy) * unit, P2Y: (py) => d.cy - (py - cypx) / unit };
  }
  const funcFnCache = {}; // funcId → {expr, fn}
  function funcFnOf(funcId) {
    const f = elements.get(funcId); if (!f || f.type !== 'func') return null;
    if (!funcFnCache[funcId] || funcFnCache[funcId].expr !== f.data.expr) funcFnCache[funcId] = { expr: f.data.expr, fn: compileFunc(f.data.expr) };
    return funcFnCache[funcId].fn;
  }
  function drawTangent(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return; const fr = elements.get(el.data.frame), fn = funcFnOf(el.data.func); if (!fr || !fn) return;
    const m = planeMap(fr), env = frameParamEnv(fr), x0 = el.data.x0; let y0, slope;
    try { y0 = fn(x0, env); const h = 1e-4; slope = (fn(x0 + h, env) - fn(x0 - h, env)) / (2 * h); } catch (e) { return; }
    if (!isFinite(y0) || !isFinite(slope)) return;
    const col = el.data.color || '#e67e22', yAt = (px) => m.Y2P(y0 + slope * (m.P2X(px) - x0));
    ctx.save(); ctx.beginPath(); ctx.lineWidth = 1.8; ctx.strokeStyle = col; ctx.moveTo(0, yAt(0)); ctx.lineTo(m.W, yAt(m.W)); ctx.stroke();
    ctx.beginPath(); ctx.fillStyle = col; ctx.arc(m.X2P(x0), m.Y2P(y0), 3.5, 0, 2 * Math.PI); ctx.fill();
    ctx.font = '12px sans-serif'; ctx.fillText('k = ' + (Math.round(slope * 100) / 100), m.X2P(x0) + 8, m.Y2P(y0) - 8); ctx.restore();
  }
  function drawArea(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return; const fr = elements.get(el.data.frame), fn = funcFnOf(el.data.func); if (!fr || !fn) return;
    const m = planeMap(fr), env = frameParamEnv(fr), a = Math.min(el.data.a, el.data.b), b = Math.max(el.data.a, el.data.b), col = el.data.color || '#27ae60', y0px = m.Y2P(0);
    ctx.save(); ctx.beginPath(); ctx.moveTo(m.X2P(a), y0px);
    for (let px = m.X2P(a); px <= m.X2P(b); px += 2) { const x = m.P2X(px); let y; try { y = fn(x, env); } catch (e) { y = NaN; } ctx.lineTo(px, isFinite(y) ? m.Y2P(y) : y0px); }
    ctx.lineTo(m.X2P(b), y0px); ctx.closePath(); ctx.fillStyle = hexToRgba(col, 0.20); ctx.fill(); ctx.strokeStyle = col; ctx.lineWidth = 1; ctx.stroke();
    let S = 0; const steps = 240, dx = (b - a) / steps; for (let i = 0; i < steps; i++) { let y1, y2; try { y1 = fn(a + i * dx, env); y2 = fn(a + (i + 1) * dx, env); } catch (e) { y1 = y2 = 0; } if (isFinite(y1) && isFinite(y2)) S += (y1 + y2) / 2 * dx; }
    ctx.fillStyle = col; ctx.font = '12px sans-serif'; ctx.fillText('S = ' + (Math.round(S * 100) / 100), (m.X2P(a) + m.X2P(b)) / 2 - 14, m.Y2P(0) - 6); ctx.restore();
  }
  function drawFIntersect(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return; const fr = elements.get(el.data.frame), fn = funcFnOf(el.data.f), gn = funcFnOf(el.data.g); if (!fr || !fn || !gn) return;
    const m = planeMap(fr), env = frameParamEnv(fr), col = '#8e44ad', diff = (x) => { let a, b; try { a = fn(x, env); b = gn(x, env); } catch (e) { return NaN; } return a - b; };
    // Ищем корни f−g на видимом диапазоне. Отдельно ловим случай, когда узел
    // выборки попал ровно в корень (diff===0) — иначе целочисленные точки
    // пересечения (частый случай в задачах) терялись бы из-за prevH*hv==0.
    const roots = [];
    let prevX = m.P2X(0), prevH = diff(prevX);
    for (let px = 2; px <= m.W; px += 2) { const x = m.P2X(px), hv = diff(x);
      if (isFinite(prevH) && isFinite(hv)) {
        if (hv === 0) { roots.push(x); }
        else if (prevH !== 0 && prevH * hv < 0) {
          let lo = prevX, hi = x, flo = prevH; for (let it = 0; it < 40; it++) { const mid = (lo + hi) / 2, fm = diff(mid); if (!isFinite(fm)) break; if (fm === 0) { lo = hi = mid; break; } if (flo * fm < 0) hi = mid; else { lo = mid; flo = fm; } }
          roots.push((lo + hi) / 2);
        }
      }
      prevX = x; prevH = hv;
    }
    const uniq = []; roots.forEach((r) => { if (!uniq.some((u) => Math.abs(u - r) < 1e-6)) uniq.push(r); });
    ctx.save();
    uniq.forEach((xr) => { let yr; try { yr = fn(xr, env); } catch (e) { yr = NaN; } if (!isFinite(yr)) return;
      const cx = m.X2P(xr), cy = m.Y2P(yr); ctx.beginPath(); ctx.fillStyle = col; ctx.arc(cx, cy, 4, 0, 2 * Math.PI); ctx.fill(); ctx.lineWidth = 1; ctx.strokeStyle = '#fff'; ctx.stroke();
      ctx.fillStyle = col; ctx.font = '11px sans-serif'; ctx.fillText('(' + (Math.round(xr * 100) / 100) + '; ' + (Math.round(yr * 100) / 100) + ')', cx + 6, cy - 6); });
    ctx.restore();
  }
  // Область неравенства / система: закрашиваем точки окна, где выполнены ВСЕ
  // условия. Каждое условие — y ≥ f(x) (sense 'gt', выше кривой) или y ≤ f(x)
  // ('lt', ниже). Идём по столбцам px: пересечение условий даёт интервал y.
  function drawRegion(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return; const fr = elements.get(el.data.frame); if (!fr) return;
    const parts = (el.data.parts || []).map((p) => ({ sense: p.sense, fn: funcFnOf(p.func) })).filter((p) => p.fn);
    if (!parts.length) return;
    const m = planeMap(fr), env = frameParamEnv(fr), col = el.data.color || '#2e86de', plotTop = FRAME_HEADER, plotBot = fr.data.height, step = 2;
    ctx.save(); ctx.fillStyle = hexToRgba(col, 0.18);
    for (let px = 0; px < m.W; px += step) {
      const x = m.P2X(px + step / 2); let lower = -Infinity, upper = Infinity, ok = true;
      for (let i = 0; i < parts.length; i++) { let v; try { v = parts[i].fn(x, env); } catch (e) { v = NaN; } if (!isFinite(v)) { ok = false; break; } if (parts[i].sense === 'gt') { if (v > lower) lower = v; } else { if (v < upper) upper = v; } }
      if (!ok || lower >= upper) continue;
      let yTop = upper === Infinity ? plotTop : m.Y2P(upper), yBot = lower === -Infinity ? plotBot : m.Y2P(lower);
      if (yTop < plotTop) yTop = plotTop; if (yBot > plotBot) yBot = plotBot;
      if (yBot > yTop) ctx.fillRect(px, yTop, step + 0.6, yBot - yTop);
    }
    ctx.restore();
  }
  // Неявная кривая F(x,y)=0 — марширующие квадраты по сетке окна. В каждой
  // клетке по знакам F в углах рисуем отрезок нуль-контура (линейная интерполяция).
  function drawImplicit(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return; const fr = elements.get(el.data.frame); if (!fr) return;
    if (shape._iexpr !== el.data.expr) { shape._ifn = compileImplicit(el.data.expr); shape._iexpr = el.data.expr; }
    const fn = shape._ifn; if (!fn) return;
    const m = planeMap(fr), env = frameParamEnv(fr), plotTop = FRAME_HEADER, W = m.W, H = fr.data.height, step = 6;
    const cols = Math.floor(W / step) + 1, rows = Math.floor((H - plotTop) / step) + 1;
    const val = new Float64Array(cols * rows);
    for (let j = 0; j < rows; j++) { const yy = m.P2Y(plotTop + j * step); for (let i = 0; i < cols; i++) { let v; try { v = fn(m.P2X(i * step), yy, env); } catch (e) { v = NaN; } val[j * cols + i] = v; } }
    ctx.save(); ctx.strokeStyle = el.data.color || '#c0392b'; ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.beginPath();
    for (let j = 0; j < rows - 1; j++) {
      for (let i = 0; i < cols - 1; i++) {
        const a = val[j * cols + i], b = val[j * cols + i + 1], c = val[(j + 1) * cols + i + 1], d = val[(j + 1) * cols + i];
        if (!(isFinite(a) && isFinite(b) && isFinite(c) && isFinite(d))) continue;
        let idx = 0; if (a > 0) idx |= 1; if (b > 0) idx |= 2; if (c > 0) idx |= 4; if (d > 0) idx |= 8;
        if (idx === 0 || idx === 15) continue;
        const x0 = i * step, y0 = plotTop + j * step, x1 = x0 + step, y1 = y0 + step;
        const T = () => [x0 + step * a / (a - b), y0], R = () => [x1, y0 + step * b / (b - c)], B = () => [x0 + step * d / (d - c), y1], L = () => [x0, y0 + step * a / (a - d)];
        const link = (p, q) => { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); };
        switch (idx) {
          case 1: case 14: link(L(), T()); break;
          case 2: case 13: link(T(), R()); break;
          case 3: case 12: link(L(), R()); break;
          case 4: case 11: link(R(), B()); break;
          case 6: case 9: link(T(), B()); break;
          case 7: case 8: link(L(), B()); break;
          case 5: link(L(), T()); link(R(), B()); break;
          case 10: link(T(), R()); link(L(), B()); break;
        }
      }
    }
    ctx.stroke(); ctx.restore();
  }
  // ── Коника по 5 точкам ─────────────────────────────────────────────────
  // Общая коника Ax²+Bxy+Cy²+Dx+Ey+F=0 проходит через 5 точек. Коэффициенты —
  // знакопеременные миноры 6×6-определителя [x² xy y² x y 1; (5 строк точек)]=0.
  function det5(m) { // определитель 5×5 методом Гаусса (частичный выбор)
    const n = 5, a = m.map((r) => r.slice()); let det = 1;
    for (let i = 0; i < n; i++) {
      let p = i; for (let r = i + 1; r < n; r++) if (Math.abs(a[r][i]) > Math.abs(a[p][i])) p = r;
      if (Math.abs(a[p][i]) < 1e-12) return 0;
      if (p !== i) { const t = a[p]; a[p] = a[i]; a[i] = t; det = -det; }
      det *= a[i][i];
      for (let r = i + 1; r < n; r++) { const f = a[r][i] / a[i][i]; for (let c = i; c < n; c++) a[r][c] -= f * a[i][c]; }
    }
    return det;
  }
  function conicCoeffs(P) { // P: [{x,y}×≥5] → [A,B,C,D,E,F] или null (вырождено)
    if (P.length < 5) return null;
    const rows = P.slice(0, 5).map((p) => [p.x * p.x, p.x * p.y, p.y * p.y, p.x, p.y, 1]);
    const co = [];
    for (let k = 0; k < 6; k++) { const minor = rows.map((r) => r.filter((_, j) => j !== k)); co.push((k % 2 === 0 ? 1 : -1) * det5(minor)); }
    const norm = Math.max.apply(null, co.map(Math.abs));
    if (!(norm > 1e-9)) return null;
    return co.map((c) => c / norm);
  }
  function conicPtsFor(el) { const pos = ptPosFor(el); return (el.data.pts || []).map(pos).filter(Boolean); }
  // Трассируем контур F=0 в коорд. окна (marching squares) — общий для рисования и хит-теста.
  function traceConic(ctx, el, fr, step) {
    const P = conicPtsFor(el); if (P.length < 5) return false;
    const co = conicCoeffs(P); if (!co) return false;
    const A = co[0], B = co[1], C = co[2], D = co[3], E = co[4], G = co[5];
    const plotTop = FRAME_HEADER, W = fr.data.width, H = fr.data.height;
    const cols = Math.floor(W / step) + 1, rows = Math.floor((H - plotTop) / step) + 1;
    const val = new Float64Array(cols * rows);
    for (let j = 0; j < rows; j++) { const yy = plotTop + j * step; for (let i = 0; i < cols; i++) { const xx = i * step; val[j * cols + i] = A * xx * xx + B * xx * yy + C * yy * yy + D * xx + E * yy + G; } }
    ctx.beginPath();
    for (let j = 0; j < rows - 1; j++) {
      for (let i = 0; i < cols - 1; i++) {
        const a = val[j * cols + i], b = val[j * cols + i + 1], c = val[(j + 1) * cols + i + 1], d = val[(j + 1) * cols + i];
        if (!(isFinite(a) && isFinite(b) && isFinite(c) && isFinite(d))) continue;
        let idx = 0; if (a > 0) idx |= 1; if (b > 0) idx |= 2; if (c > 0) idx |= 4; if (d > 0) idx |= 8;
        if (idx === 0 || idx === 15) continue;
        const x0 = i * step, y0 = plotTop + j * step, x1 = x0 + step, y1 = y0 + step;
        const T = () => [x0 + step * a / (a - b), y0], R = () => [x1, y0 + step * b / (b - c)], Bt = () => [x0 + step * d / (d - c), y1], L = () => [x0, y0 + step * a / (a - d)];
        const link = (p, q) => { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); };
        switch (idx) {
          case 1: case 14: link(L(), T()); break; case 2: case 13: link(T(), R()); break; case 3: case 12: link(L(), R()); break; case 4: case 11: link(R(), Bt()); break;
          case 6: case 9: link(T(), Bt()); break; case 7: case 8: link(L(), Bt()); break; case 5: link(L(), T()); link(R(), Bt()); break; case 10: link(T(), R()); link(L(), Bt()); break;
        }
      }
    }
    return true;
  }
  function drawConicShape(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return; const fr = elements.get(el.data.frame); if (!fr) return;
    ctx.save(); ctx.strokeStyle = el.data.color || el.data.stroke || '#c0392b'; ctx.lineWidth = el.data.strokeWidth || 2; ctx.lineJoin = 'round';
    if (traceConic(ctx, el, fr, 6)) ctx.stroke();
    ctx.restore();
  }
  function hitConicShape(ctx, shape) {
    const el = elements.get(shape.id()); if (!el) return; const fr = elements.get(el.data.frame); if (!fr) return;
    if (traceConic(ctx, el, fr, 8)) ctx.strokeShape(shape);
  }
  // Привязать узел к группе окна и убрать ПОД шапку (над сеткой/предыдущими).
  // Узлы, добавленные позже, оказываются выше ранее добавленных, но ниже шапки —
  // поэтому точки (создаются после линий) лежат над линиями и доступны для захвата.
  function attachToFrame(el, node) {
    const frameNode = nodes.get(el.data.frame);
    if (!frameNode) return false; // окна ещё нет — привяжем позже (reattach)
    frameNode.add(node);
    const header = frameNode.findOne('.fheader');
    if (header) node.zIndex(header.zIndex());
    // Точки должны лежать НАД линиями/окружностями: иначе клик по точке попадает в
    // линию (она сверху), точку нельзя схватить и перетащить. После привязки любой
    // НЕ-точки поднимаем точки этого окна обратно наверх (под шапку).
    if (el.type !== 'point') raiseFramePoints(el.data.frame);
    return true;
  }
  // Поднять все точки окна над остальной геометрией (но под шапку/подпись/крестик).
  function raiseFramePoints(frameId) {
    const frameNode = nodes.get(frameId); if (!frameNode) return;
    elements.forEach((el) => {
      if (el.type === 'point' && el.data.frame === frameId) {
        const n = nodes.get(el.id); if (n && n.getParent() === frameNode) n.moveToTop();
      }
    });
    ['.fheader', '.fdel'].forEach((s) => { const h = frameNode.findOne(s); if (h) h.moveToTop(); });
  }
  function attachFuncNode(el, node) { attachToFrame(el, node); }
  function upsertFuncNode(el) {
    let node = nodes.get(el.id);
    if (!node) {
      node = new Konva.Shape({ id: el.id, listening: false, sceneFunc: drawFuncShape });
      nodes.set(el.id, node);
      attachFuncNode(el, node);
    } else {
      node._expr = null; // пересобрать формулу при изменении
    }
    layer.batchDraw();
  }
  function reattachFuncs() {
    elements.forEach((el) => {
      if (el.type === 'func') {
        const node = nodes.get(el.id), frameNode = nodes.get(el.data.frame);
        if (node && frameNode && node.getParent() !== frameNode) attachFuncNode(el, node);
      } else if (el.data && el.data.frame && (el.type === 'point' || el.type === 'circle' || isPointBoundLine(el) || el.type === 'ftangent' || el.type === 'farea' || el.type === 'fintersect' || el.type === 'region' || el.type === 'implicit')) {
        // привязанная геометрия — в группу окна (если окно загрузилось позже)
        const node = nodes.get(el.id), frameNode = nodes.get(el.data.frame);
        if (node && frameNode && node.getParent() !== frameNode) attachToFrame(el, node);
      }
    });
    recomputeGeometry();
    layer.batchDraw();
  }
  function addFunc(frameId, expr) {
    expr = String(expr || '').trim();
    if (!expr || !elements.get(frameId)) return;
    let n = 0; elements.forEach((e) => { if (e.type === 'func' && e.data.frame === frameId) n++; });
    const el = { id: uuid(), type: 'func', z: 0, data: { frame: frameId, expr, color: FUNC_COLORS[n % FUNC_COLORS.length], name: nextObjName() } };
    upsertNode(el);
    send({ action: 'element_add', element: el });
    histAdd(el);
    // Незнакомые переменные формулы → локальные параметры окна (со своими ползунками).
    const fr = elements.get(frameId), before = clone(fr);
    if (ensureFrameParams(fr, expr)) { histUpd(before, fr); send({ action: 'element_update', element: fr }); }
    redrawFuncs();
    return el;
  }
  // Неявная кривая F(x,y)=0 (например x^2+y^2=9). Параметры — как у функций, но
  // из списка переменных исключаем y (иначе y стал бы ползунком).
  function addImplicit(frameId, expr) {
    expr = String(expr || '').trim();
    if (!expr || !elements.get(frameId)) return;
    if (!compileImplicit(expr)) { boardHint('Не понял уравнение — проверьте запись'); return; }
    let n = 0; elements.forEach((e) => { if ((e.type === 'func' || e.type === 'implicit') && e.data.frame === frameId) n++; });
    const el = { id: uuid(), type: 'implicit', z: 0, data: { frame: frameId, expr, color: FUNC_COLORS[n % FUNC_COLORS.length], name: nextObjName() } };
    upsertNode(el);
    send({ action: 'element_add', element: el });
    histAdd(el);
    const fr = elements.get(frameId), before = clone(fr);
    if (ensureFrameParams(fr, expr, ['y'])) { histUpd(before, fr); send({ action: 'element_update', element: fr }); }
    redrawFuncs();
    return el;
  }

  // ── Формулы LaTeX → изображение ────────────────────────────────────────
  // Хранится только исходник LaTeX + позиция + цвет; картинку каждый клиент
  // рисует у себя через MathJax. Размер фиксируем в данных, чтобы раскладка
  // совпадала у всех и после перезагрузки.
  const latexMeasure = document.createElement('div');
  latexMeasure.style.cssText = 'position:absolute;visibility:hidden;left:-99999px;top:0;';
  document.body.appendChild(latexMeasure);

  const SVG_NS = 'http://www.w3.org/2000/svg';

  // MathJax (fontCache: 'global') хранит контуры глифов в одном общем
  // <svg id="MJX-SVG-global-cache">, а формулы ссылаются на них через <use>.
  // При сериализации отдельного <svg> в картинку этот кэш не попадает и
  // изображение выходит пустым. Поэтому встраиваем нужные определения глифов
  // прямо в наш <svg>, делая его самодостаточным.
  function inlineGlyphDefs(svg) {
    if (!svg.querySelector('use')) return;
    const cache = document.getElementById('MJX-SVG-global-cache');
    if (!cache) return;
    const cacheDefs = cache.querySelector('defs') || cache;
    let defs = svg.querySelector('defs');
    if (!defs) {
      defs = document.createElementNS(SVG_NS, 'defs');
      svg.insertBefore(defs, svg.firstChild);
    }
    // Клонируем все кэшированные глифы (≈5 КБ) — гарантированно покрывает и
    // составные глифы, которые сами ссылаются на другие через <use>.
    Array.from(cacheDefs.children).forEach((ch) => defs.appendChild(ch.cloneNode(true)));
  }

  // Готовность MathJax. tex-svg.js стартует асинхронно, поэтому формулы,
  // восстановленные из БД на старте, могут попасть на ещё не готовый MathJax —
  // ждём его. Заодно один раз отключаем общий кэш шрифтов (fontCache:'none'),
  // чтобы каждый <svg> был самодостаточным и корректно растеризовался в картинку.
  let mjFontCacheSet = false;
  function whenMathJaxReady(fn) {
    if (window.MathJax && MathJax.tex2svg) {
      if (!mjFontCacheSet) {
        try {
          const out = MathJax.startup && MathJax.startup.output;
          if (out && out.options) out.options.fontCache = 'none';
        } catch (e) { /* не критично: останется подстраховка inlineGlyphDefs */ }
        mjFontCacheSet = true;
      }
      fn();
    } else if (window.MathJax && MathJax.startup && MathJax.startup.promise) {
      MathJax.startup.promise.then(() => whenMathJaxReady(fn));
    } else {
      setTimeout(() => whenMathJaxReady(fn), 60);
    }
  }

  function latexToImage(latex, color, cb) {
    whenMathJaxReady(() => latexToImageNow(latex, color, cb));
  }

  function latexToImageNow(latex, color, cb) {
    let svg;
    try {
      const container = MathJax.tex2svg(latex || '', { display: true });
      svg = container.querySelector('svg');
    } catch (e) { cb(null); return; }
    if (!svg) { cb(null); return; }
    svg.style.color = color || '#1f2937';
    latexMeasure.innerHTML = '';
    latexMeasure.appendChild(svg);
    const r = svg.getBoundingClientRect();
    const w = Math.max(2, Math.ceil(r.width));
    const h = Math.max(2, Math.ceil(r.height));
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
    inlineGlyphDefs(svg); // встроить глифы до сериализации
    const xml = new XMLSerializer().serializeToString(svg);
    latexMeasure.innerHTML = '';
    const img = new Image();
    img.onload = () => cb(img, w, h);
    img.onerror = () => cb(null);
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
  }

  function renderLatexInto(node, el) {
    const d = el.data || {};
    node._latex = (d.latex || '') + '|' + (d.color || '');
    latexToImage(d.latex, d.color, (img, w, h) => {
      if (!img) return;
      node.image(img);
      // Если размер ещё не зафиксирован — берём натуральный.
      if (!d.width || !d.height) {
        d.width = w; d.height = h;
        node.width(w); node.height(h);
        // Рассылает размер только автор формулы (у остальных он придёт обновлением),
        // иначе клиенты затирали бы размеры друг друга.
        const mine = (el.author == null || el.author === myId);
        if (mine && el === elements.get(el.id)) send({ action: 'element_update', element: el });
      }
      layer.batchDraw();
    });
  }

  // ── Текст с инлайн-формулами → изображение ─────────────────────────────
  // Текст может содержать формулы в $...$. Верстаем его как HTML, прогоняем
  // MathJax (формулы становятся самодостаточным SVG, т.к. fontCache:'none'),
  // затем растеризуем через <foreignObject>. Хранится только исходный текст,
  // цвет и размер — картинку каждый клиент строит у себя.
  const TEXT_FONT = "-apple-system, 'Segoe UI', Roboto, Arial, sans-serif";
  // Доступные шрифты (только системные — SVG самодостаточен, без внешних загрузок).
  const TEXT_FONTS = [
    { label: 'Обычный', css: TEXT_FONT },
    { label: 'С засечками', css: "Georgia, 'Times New Roman', serif" },
    { label: 'Моноширинный', css: "'Courier New', monospace" },
    { label: 'Times', css: "'Times New Roman', Times, serif" },
    { label: 'Verdana', css: 'Verdana, Geneva, sans-serif' },
    { label: 'Tahoma', css: 'Tahoma, Geneva, sans-serif' },
    { label: 'Trebuchet', css: "'Trebuchet MS', sans-serif" },
    { label: 'Comic', css: "'Comic Sans MS', cursive" },
  ];
  // Базовый стиль текстового окна: шрифт/кегль/цвет/выравнивание по умолчанию + ФОН
  // ОКНА (на всю область). Фон ЗА текстом — это inline highlight внутри html.
  function textBaseCss(d) {
    d = d || {};
    return 'font-family:' + (d.font || TEXT_FONT)
      + ';color:' + (d.color || '#1f2937')
      + ';font-size:' + (d.fontSize || 20) + 'px'
      + ';text-align:' + (d.align || 'left')
      + ';line-height:1.35;white-space:pre-wrap;word-wrap:break-word'
      + ';' + (d.wrapWidth ? 'width:' + Math.max(40, d.wrapWidth) + 'px' : 'max-width:700px')
      + ';display:inline-block;box-sizing:border-box;padding:6px 9px'
      + (d.boxBg ? ';background:' + d.boxBg : '');
  }
  function textKey(d) { d = d || {}; return [d.html || '', d.text || '', d.color || '', d.fontSize || '', d.font || '', d.align || '', d.boxBg || '', d.wrapWidth || '', d.plain ? '1' : ''].join(''); }
  const URL_RE = /(https?:\/\/[^\s<>"']+|www\.[^\s<>"']+)/g;
  // Обернуть «голые» ссылки в текстовых узлах в подсвеченный span (кроме уже-ссылок).
  // ── Санитайзер HTML текста (защита от stored-XSS) ─────────────────────
  // Текст элементов рендерится через innerHTML у ВСЕХ участников; злонамеренный
  // редактор мог бы вписать <img onerror=…> и выполнить код в чужом браузере.
  // Пропускаем только безопасные теги/атрибуты форматирования.
  const SAN_TAGS = { B: 1, STRONG: 1, I: 1, EM: 1, U: 1, S: 1, STRIKE: 1, SPAN: 1, DIV: 1, P: 1, BR: 1, UL: 1, OL: 1, LI: 1, A: 1, FONT: 1, SUB: 1, SUP: 1 };
  const SAN_DROP = { SCRIPT: 1, STYLE: 1, IFRAME: 1, OBJECT: 1, EMBED: 1, LINK: 1, META: 1, SVG: 1, IMG: 1, VIDEO: 1, AUDIO: 1, FORM: 1, INPUT: 1, BUTTON: 1 };
  const SAN_STYLE_PROPS = { color: 1, background: 1, 'background-color': 1, 'font-weight': 1, 'font-style': 1, 'font-family': 1, 'font-size': 1, 'text-align': 1, 'text-decoration': 1, 'text-decoration-line': 1, 'text-decoration-style': 1 };
  const SAN_ATTR_OK = { class: 1, target: 1, rel: 1, color: 1, face: 1, size: 1, align: 1 };
  function sanitizeStyle(v) {
    return String(v || '').split(';').map((s) => s.trim()).filter(Boolean).filter((decl) => {
      const i = decl.indexOf(':'); if (i < 0) return false;
      const prop = decl.slice(0, i).trim().toLowerCase(), val = decl.slice(i + 1).trim().toLowerCase();
      if (!SAN_STYLE_PROPS[prop]) return false;
      if (/url\(|expression|javascript:|<|@import/.test(val)) return false;
      return true;
    }).join('; ');
  }
  function sanitizeHtml(html) {
    const root = document.createElement('div'); root.innerHTML = String(html == null ? '' : html);
    (function walk(node) {
      let child = node.firstChild;
      while (child) {
        const next = child.nextSibling;
        if (child.nodeType === 1) {
          const tag = child.tagName;
          if (!SAN_TAGS[tag]) {
            if (SAN_DROP[tag]) child.remove(); // опасный тег — вместе с содержимым
            else { while (child.firstChild) node.insertBefore(child.firstChild, child); child.remove(); } // прочее — развернуть текст
            child = next; continue;
          }
          Array.prototype.slice.call(child.attributes).forEach((a) => {
            const name = a.name.toLowerCase();
            if (name.indexOf('on') === 0) { child.removeAttribute(a.name); return; } // обработчики событий
            if (name === 'style') { const s = sanitizeStyle(a.value); if (s) child.setAttribute('style', s); else child.removeAttribute('style'); return; }
            if (name === 'href' || name === 'src' || name === 'xlink:href') { if (!/^(https?:|mailto:|#|\/)/i.test(a.value.trim())) child.removeAttribute(a.name); return; }
            if (!SAN_ATTR_OK[name]) child.removeAttribute(a.name);
          });
          if (tag === 'A' && child.getAttribute('href')) { child.setAttribute('target', '_blank'); child.setAttribute('rel', 'noopener noreferrer nofollow'); }
          walk(child);
        } else if (child.nodeType !== 3) { child.remove(); } // комментарии/CDATA — убрать
        child = next;
      }
    })(root);
    return root.innerHTML;
  }
  function linkifyHtml(html) {
    const root = document.createElement('div'); root.innerHTML = html || '';
    (function walk(node) {
      let child = node.firstChild;
      while (child) {
        const next = child.nextSibling;
        if (child.nodeType === 3) {
          const t = child.nodeValue; URL_RE.lastIndex = 0;
          if (URL_RE.test(t)) {
            URL_RE.lastIndex = 0; const frag = document.createDocumentFragment(); let last = 0, m;
            while ((m = URL_RE.exec(t))) {
              if (m.index > last) frag.appendChild(document.createTextNode(t.slice(last, m.index)));
              // Настоящая ссылка, а не просто покрашенный текст: раньше здесь был
              // <span>, из-за чего адрес выглядел кликабельным, но клик ничего не
              // делал. Адрес без схемы (www.…) дополняем до https://.
              const a = document.createElement('a');
              a.className = 'lnk';
              a.href = /^https?:\/\//i.test(m[0]) ? m[0] : 'https://' + m[0];
              a.target = '_blank'; a.rel = 'noopener noreferrer nofollow';
              a.style.color = '#1f6feb'; a.style.textDecoration = 'underline';
              a.textContent = m[0];
              frag.appendChild(a); last = m.index + m[0].length;
            }
            if (last < t.length) frag.appendChild(document.createTextNode(t.slice(last)));
            child.replaceWith(frag);
          }
        } else if (child.nodeType === 1) {
          const tag = child.tagName, isLink = tag === 'A' || (child.classList && child.classList.contains('lnk'));
          if (!isLink) walk(child);
        }
        child = next;
      }
    })(root);
    return root.innerHTML;
  }
  // Содержимое элемента как html (миграция старого plain-text в html). Санитайзим —
  // это единая точка получения html текста для отрисовки (защита от XSS).
  function textContentHtml(d) {
    if (d.html != null && d.html !== '') return sanitizeHtml(d.html);
    const esc = escapeHtml(d.text || ' ').replace(/\n/g, '<br>');
    return esc;
  }

  function textToImage(d, cb) {
    whenMathJaxReady(() => {
      const css = textBaseCss(d);
      const inner = linkifyHtml(textContentHtml(d));
      const host = document.createElement('div');
      host.style.cssText = 'position:absolute;left:-99999px;top:0;' + css;
      host.innerHTML = inner;
      document.body.appendChild(host);
      const finish = () => {
        // MathJax добавляет невидимую в норме MathML-копию (mjx-assistive-mml) для
        // скринридеров; её CSS в SVG-foreignObject не подхватывается → формула
        // дублируется обычным шрифтом. Удаляем ДО замера и растеризации.
        host.querySelectorAll('mjx-assistive-mml').forEach((e) => e.remove());
        const r = host.getBoundingClientRect();
        const w = Math.max(2, Math.ceil(r.width) + 2);
        const h = Math.max(2, Math.ceil(r.height) + 2);
        const rendered = host.innerHTML;
        host.remove();
        const styleBlock = '<style>div,p{margin:0}ul,ol{margin:0.2em 0;padding-left:1.5em}li{margin:0}a,.lnk{color:#1f6feb;text-decoration:underline}mjx-assistive-mml{display:none}</style>';
        const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + h + '">'
          + '<foreignObject width="100%" height="100%">'
          + '<div xmlns="http://www.w3.org/1999/xhtml" style="' + css + '">' + styleBlock + rendered + '</div>'
          + '</foreignObject></svg>';
        const img = new Image();
        img.onload = () => cb(img, w, h);
        img.onerror = () => cb(null);
        img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
      };
      // Обычный текст (d.plain) — БЕЗ MathJax: $…$ остаются как есть (как в Miro).
      if (!d.plain && window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([host]).then(finish).catch(finish);
      else finish();
    });
  }

  function renderTextInto(node, el) {
    const d = el.data || {};
    node._textKey = textKey(d);
    textToImage(d, (img, w, h) => {
      if (!img) return;
      node.image(img);
      // Размер всегда пересчитываем под контент (текст мог стать больше/меньше).
      d.width = w; d.height = h; node.width(w); node.height(h);
      const mine = (el.author == null || el.author === myId);
      const resizingThis = resizeState && resizeState.id === el.id; // при ресайзе шлём один раз в конце
      if (mine && el === elements.get(el.id) && !resizingThis) send({ action: 'element_update', element: el });
      if (resizeState && resizeState.id === el.id) positionHandles(); // ручки за новым размером
      layer.batchDraw();
    });
  }

  // ── Импорт картинок и PDF ──────────────────────────────────────────────
  function boardCodeStr() { const p = location.pathname.split('/').filter(Boolean); return p[1] || 'board'; }
  function getCookie(name) { const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'); return m ? m.pop() : ''; }
  function viewportCenterWorld() { const s = stage.scaleX(); return { x: (-stage.x() + stage.width() / 2) / s, y: (-stage.y() + stage.height() / 2) / s }; }
  function uploadFile(file) {
    const fd = new FormData(); fd.append('file', file);
    return fetch('/board/' + boardCodeStr() + '/upload/', { method: 'POST', body: fd, headers: { 'X-CSRFToken': getCookie('csrftoken') } }).then((r) => r.json());
  }
  function importFiles(files) {
    const tasks = Array.from(files).map((f) => {
      boardHint('Загрузка ' + f.name + '…');
      return uploadFile(f).then((res) => {
        if (!res || res.error) { boardHint('Ошибка загрузки: ' + ((res && res.error) || '')); return null; }
        return (res.kind === 'image') ? createImageElement(res.url, f.name) : createPdfElement(res.url, f.name);
      }).catch(() => { boardHint('Не удалось загрузить файл'); return null; });
    });
    Promise.all(tasks).then((ids) => { const good = ids.filter(Boolean); if (good.length >= 2) autoGridArrange(good); });
  }
  // Заглушка вместо не загрузившейся картинки. Рисуем её в отдельный холст и
  // отдаём узлу как изображение: тогда она масштабируется вместе с объектом и
  // не требует ни нового слоя, ни разметки. Без заглушки объект оставался
  // невидимым, но кликабельным — человек не понимал, что вообще произошло.
  function brokenImageCanvas(w, h) {
    const cv = document.createElement('canvas');
    cv.width = Math.max(80, Math.round(w || 200)); cv.height = Math.max(60, Math.round(h || 140));
    const g = cv.getContext('2d');
    g.fillStyle = '#f6f2ef'; g.fillRect(0, 0, cv.width, cv.height);
    g.strokeStyle = '#d9a37a'; g.lineWidth = 2; g.setLineDash([7, 5]);
    g.strokeRect(1, 1, cv.width - 2, cv.height - 2);
    g.setLineDash([]);
    g.fillStyle = '#a5673f';
    g.font = '600 ' + Math.max(11, Math.min(16, Math.round(cv.width / 16))) + 'px sans-serif';
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('Картинка не загрузилась', cv.width / 2, cv.height / 2 - 9);
    g.font = Math.max(10, Math.min(13, Math.round(cv.width / 20))) + 'px sans-serif';
    g.fillStyle = '#b98a67';
    g.fillText('двойной щелчок — загрузить снова', cv.width / 2, cv.height / 2 + 12);
    return cv;
  }
  // Картинка: грузим в узел (при создании и при обновлении url).
  function loadImageInto(node, el) {
    const url = el.data.url; if (!url) return;
    if (node._src === url && !node._imgFail) { node.width(el.data.width || node.width()); node.height(el.data.height || node.height()); return; }
    node._src = url; node._imgFail = false;
    const img = new Image(); img.crossOrigin = 'anonymous';
    img.onload = () => {
      node._imgFail = false;
      node.image(img); node.width(el.data.width || img.naturalWidth); node.height(el.data.height || img.naturalHeight);
      applyCrop(node, el);   // окно кадра задаётся ПОСЛЕ картинки, иначе Konva его потеряет
      layer.batchDraw();
    };
    img.onerror = () => {
      // Адрес у картинки всегда свой, локальный, значит файл на месте — не дошёл
      // именно этот участник. Сторож кеша сбрасываем, иначе повторить попытку
      // было бы нельзя: узел остался бы «отравленным» навсегда.
      node._imgFail = true; node._src = null;
      node.image(brokenImageCanvas(el.data.width, el.data.height));
      node.width(el.data.width || 200); node.height(el.data.height || 140);
      layer.batchDraw();
      boardHint('Картинка не загрузилась — двойной щелчок по ней, чтобы попробовать снова');
    };
    img.src = url;
  }
  // Показ обрезанной картинки. Konva рисует часть изображения сама, если задать
  // окно кадра; нули означают «обрезки нет, показываем целиком».
  function applyCrop(node, el) {
    const c = el.data && el.data.crop;
    if (c && c.w > 0 && c.h > 0) { node.cropX(c.x); node.cropY(c.y); node.cropWidth(c.w); node.cropHeight(c.h); }
    else { node.cropX(0); node.cropY(0); node.cropWidth(0); node.cropHeight(0); }
  }
  // Размер исходного файла в пикселях. Нужен, чтобы обрезать «от целого», когда
  // обрезки ещё не было.
  function imageNatural(node) {
    const im = node.image(); if (!im) return null;
    const w = im.naturalWidth || im.width, h = im.naturalHeight || im.height;
    return (w && h) ? { w: w, h: h } : null;
  }
  // Повторная попытка: сбрасываем сторож кеша и грузим заново.
  function reloadImage(id) {
    const el = elements.get(id), n = nodes.get(id);
    if (!el || !n || el.type !== 'image') return;
    n._src = null; n._imgFail = false;
    boardHint('Загружаю картинку заново…');
    loadImageInto(n, el);
  }
  function createImageElement(url, name) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const maxW = 440, sc = Math.min(1, maxW / img.naturalWidth);
        const w = Math.round(img.naturalWidth * sc), h = Math.round(img.naturalHeight * sc), c = viewportCenterWorld();
        const el = { id: uuid(), type: 'image', z: 0, data: { x: c.x - w / 2, y: c.y - h / 2, width: w, height: h, url: url, name: name } };
        upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); setTool('select'); layer.batchDraw();
        boardHint('Картинка добавлена'); resolve(el.id);
      };
      img.onerror = () => { boardHint('Не удалось открыть картинку'); resolve(null); };
      img.src = url;
    });
  }
  // ── PDF через pdf.js (CDN) ──────────────────────────────────────────────
  const PDFJS_VER = '3.11.174';
  function ensurePdfLib(cb, tries) {
    if (window.pdfjsLib) { if (!window.pdfjsLib.GlobalWorkerOptions.workerSrc) window.pdfjsLib.GlobalWorkerOptions.workerSrc = cfg.pdfWorker; cb(window.pdfjsLib); return; }
    if ((tries || 0) > 40) { boardHint('pdf.js не загрузился'); return; }
    setTimeout(() => ensurePdfLib(cb, (tries || 0) + 1), 150);
  }
  const pdfDocs = new Map(); // url → Promise<pdfDoc>
  function getPdfDoc(url) {
    if (pdfDocs.has(url)) return pdfDocs.get(url);
    // cMaps нужны только для иероглифических PDF (китайский/японский/корейский) —
    // такие у нас не встречаются, поэтому их одних оставляем на CDN, а всё, без
    // чего PDF не откроется, лежит у нас.
    const cmaps = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@' + PDFJS_VER + '/cmaps/';
    const p = new Promise((res, rej) => {
      ensurePdfLib((lib) => {
        // cMap + стандартные шрифты нужны pdf.js 3.x, иначе отрисовка текста зависает/падает.
        lib.getDocument({ url: url, cMapUrl: cmaps, cMapPacked: true, standardFontDataUrl: cfg.pdfFonts }).promise.then(res, rej);
      });
    });
    pdfDocs.set(url, p); return p;
  }
  function createPdfElement(url, name) {
    return new Promise((resolve) => {
      getPdfDoc(url).then((doc) => doc.getPage(1).then((page) => {
        const vp = page.getViewport({ scale: 1 }), maxW = 460, sc = Math.min(1, maxW / vp.width);
        const w = Math.round(vp.width * sc), h = Math.round(vp.height * sc), c = viewportCenterWorld();
        const el = { id: uuid(), type: 'pdf', z: 0, data: { x: c.x - w / 2, y: c.y - h / 2, width: w, height: h, url: url, pages: doc.numPages, page: 1, name: name } };
        upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); setTool('select'); layer.batchDraw();
        boardHint('PDF добавлен (' + doc.numPages + ' стр.)'); resolve(el.id);
      })).catch(() => { boardHint('Не удалось открыть PDF'); resolve(null); });
    });
  }
  function renderPdfInto(node, el) {
    const key = el.data.url + '#' + (el.data.page || 1);
    if (node._pdfKey === key) return; node._pdfKey = key;
    node.width(el.data.width || 300); node.height(el.data.height || 400);
    getPdfDoc(el.data.url).then((doc) => {
      const pg = Math.max(1, Math.min(doc.numPages, el.data.page || 1));
      return doc.getPage(pg).then((page) => {
        const vp0 = page.getViewport({ scale: 1 }), scale = ((el.data.width || 300) * 2) / vp0.width, vp = page.getViewport({ scale });
        const cv = document.createElement('canvas'); cv.width = Math.ceil(vp.width); cv.height = Math.ceil(vp.height);
        return page.render({ canvasContext: cv.getContext('2d'), viewport: vp }).promise.then(() => { node.image(cv); layer.batchDraw(); });
      });
    }).catch(() => {});
  }
  // Извлекает ОДНУ страницу в картинку и кладёт её в (x, y). Промис НИКОГДА
  // не отклоняется: любой сбой — на разборе документа, на рендере, на PNG,
  // на загрузке — даёт { error }, а не непойманное отклонение. В старом коде
  // .catch стоял только на getPdfDoc/getPage: отказ САМОГО РЕНДЕРА и отказ
  // uploadFile (он вызывался внутри колбэка toBlob, отдельным от него
  // промисом) не ловились вообще — человек не видел ни картинки, ни ошибки.
  // Ни подсказки, ни записи в историю здесь нет: и то, и другое решает
  // вызывающий (одна страница — свои, пакет — один итог на все).
  function extractPdfPageAt(el, page, x, y) {
    return getPdfDoc(el.data.url).then((doc) => doc.getPage(page)).then((pg) => {
      const vp = pg.getViewport({ scale: 2 }), cv = document.createElement('canvas');
      cv.width = Math.ceil(vp.width); cv.height = Math.ceil(vp.height);
      // intent: 'print' — НЕ косметика. Обычный (display) рендер pdf.js гонит
      // через requestAnimationFrame, а его браузер останавливает во вкладке,
      // которая не на экране. Пакет на 30 страниц как раз и оставляют идти,
      // переключившись на другое, — и он замирал бы до возвращения. Холст здесь
      // невидимый, на экран не идёт, поэтому print-режим (обычные промисы,
      // без кадров) даёт ту же картинку, но не зависит от видимости вкладки.
      // Проверено: при замороженных кадрах display висит бесконечно, print
      // заканчивается за миллисекунды.
      return pg.render({ canvasContext: cv.getContext('2d'), viewport: vp, intent: 'print' }).promise.then(() => new Promise((resolve) => {
        cv.toBlob((blob) => {
          // Освобождаем backing store СРАЗУ после снятия картинки. Раньше холст
          // жил в замыкании до конца загрузки на сервер — при пачке страниц
          // именно так планшет исчерпывает память: N холстов по ~8 МБ разом,
          // а не один.
          cv.width = 0; cv.height = 0;
          if (!blob) { resolve({ error: 'не удалось подготовить картинку' }); return; }
          const file = new File([blob], (el.data.name || 'pdf').replace(/\.pdf$/i, '') + '-стр' + page + '.png', { type: 'image/png' });
          uploadFile(file).then((res) => {
            if (!res || !res.url) { resolve({ error: (res && res.error) || 'сервер не принял файл' }); return; }
            const iel = { id: uuid(), type: 'image', z: 0, data: { x: x, y: y, width: el.data.width, height: el.data.height, url: res.url, name: file.name } };
            resolve({ iel: iel });
          }).catch(() => resolve({ error: 'обрыв связи при загрузке' }));
        }, 'image/png');
      }));
    }).catch(() => ({ error: 'не удалось открыть страницу ' + page }));
  }
  // Кнопка «Извлечь страницу»: одна страница сама по себе — свои подсказки,
  // свой шаг отмены (это самостоятельное действие, не часть пакета).
  function extractPdfPage(el, page) {
    extractPdfPageAt(el, page, el.data.x + el.data.width + 20, el.data.y).then((r) => {
      if (r.error) { boardHint('Ошибка извлечения: ' + r.error); return; }
      upsertNode(r.iel); send({ action: 'element_add', element: r.iel }); histAdd(r.iel); layer.batchDraw();
      boardHint('Страница ' + page + ' извлечена как картинка');
    });
  }
  // Разбор списка страниц: «1-5, 8, 12-14». Тире всех видов (в том числе то
  // длинное, что остаётся при вставке из скопированного оглавления) читается
  // как обычный дефис. «5-1» не ошибка — диапазон просто переворачивается.
  // Непонятые куски НЕ прерывают разбор — собираются в bad, чтобы итоговое
  // сообщение назвало их, а не молча выбросило.
  function parsePageRange(str, maxPage) {
    const seen = new Set(); const bad = [];
    String(str || '')
      .replace(/[\u2010-\u2015\u2212]/g, '-')
      .split(/[,;]+/)
      .map((t) => t.trim())
      .filter(Boolean)
      .forEach((tok) => {
        // Пробелы вокруг дефиса («1 - 3» — обычное дело при ручном наборе) —
        // не ошибка: их и не должно быть видно человеку, который просто
        // нажал пробел до и после тире.
        const m = tok.match(/^(\d+)\s*(?:-\s*(\d+))?$/);
        if (!m) { bad.push(tok); return; }
        let a = parseInt(m[1], 10), b = m[2] != null ? parseInt(m[2], 10) : a;
        // Клемп КАЖДОГО конца по отдельности и ДО перестановки: одиночная
        // страница за пределом документа («99» при 20 страницах) иначе после
        // клемпа получала бы a=99, b=20 — то есть a>b — и весь кусок молча
        // терялся бы, не попадая даже в bad.
        a = Math.max(1, Math.min(maxPage, a)); b = Math.max(1, Math.min(maxPage, b));
        if (a > b) { const t = a; a = b; b = t; }
        for (let p = a; p <= b; p++) seen.add(p);
      });
    return { pages: Array.from(seen).sort((x, y) => x - y), bad: bad };
  }
  // Тот же потолок, что у самой доски (_BOARD_FILES_MAX, board/views.py) —
  // за один раз больше всё равно не поместится.
  const PDF_BATCH_MAX = 60;
  // Извлекает СПИСОК страниц пакетом.
  //  • Строго ПО ОЧЕРЕДИ — не все сразу: старый код запускал все страницы
  //    параллельно, и на iPad это ~8 МБ холста × N разом — подвисание или
  //    перезагрузка вкладки (жалоба «доска зависает»).
  //  • Кладёт каждую страницу СРАЗУ на своё место в сетке, размер которой
  //    посчитан от ширины ВИДИМОЙ области (общая сетка автораскладки в 12
  //    колонок для одинаковых по размеру страниц одного PDF уезжает за
  //    экран). Второго прохода раскладки нет — а значит нет и второй волны
  //    element_update всем соседям, и нет второй порции строк в общем
  //    журнале доски (у него потолок 200 записей на всю доску).
  //  • Одна запись в истории на весь пакет (histBatch): раньше 20 страниц —
  //    20 шагов отмены, и «Отменить» после автораскладки сваливало все
  //    картинки обратно в одну точку, а не убирало их.
  //  • Одно итоговое сообщение вместо N мигающих одинаковых (boardHint держит
  //    только одну строку разом, и хуже того — раньше при ЛЮБОЙ неудавшейся
  //    странице счётчик done никогда не доходил до n, и сетка не строилась
  //    ВООБЩЕ — все успешные страницы оставались лежать друг на друге).
  function extractPdfPages(el, pages, badTokens) {
    if (!pages || !pages.length) return;
    const requested = pages.length;
    if (pages.length > PDF_BATCH_MAX) pages = pages.slice(0, PDF_BATCH_MAX);
    const w = el.data.width, h = el.data.height, gap = arrangeGap;
    const s = stage.scaleX(), vw = stage.width() / s;
    const cols = Math.max(1, Math.min(pages.length, Math.floor((vw - 40 / s) / (w + gap)) || 1));
    const baseX = el.data.x + el.data.width + 20, baseY = el.data.y;
    const ops = []; let ok = 0, firstError = '';
    boardHint('Извлечение: 0 из ' + pages.length + '…');
    function step(i) {
      if (i >= pages.length) { finish(); return; }
      const col = i % cols, row = Math.floor(i / cols);
      extractPdfPageAt(el, pages[i], baseX + col * (w + gap), baseY + row * (h + gap)).then((r) => {
        if (r.iel) {
          ok++;
          upsertNode(r.iel); send({ action: 'element_add', element: r.iel });
          ops.push({ kind: 'add', el: clone(r.iel) });
          layer.batchDraw();
        } else if (!firstError) { firstError = r.error || ''; }
        boardHint('Извлечение: ' + (i + 1) + ' из ' + pages.length + '…');
        step(i + 1);
      });
    }
    function finish() {
      if (ops.length) histBatch(ops);
      let msg = (ok === pages.length) ? ('Извлечено страниц: ' + ok)
        : ('Извлечено ' + ok + ' из ' + pages.length + (firstError ? ' — ' + firstError : ''));
      if (requested > PDF_BATCH_MAX) msg += ' (запрошено ' + requested + ', за раз — не больше ' + PDF_BATCH_MAX + ')';
      if (badTokens && badTokens.length) msg += '; не понял: ' + badTokens.join(', ');
      boardHint(msg);
    }
    step(0);
  }
  function setPdfPage(el, page) {
    page = Math.max(1, Math.min(el.data.pages || 1, page));
    if (page === el.data.page) return;
    const before = clone(el); el.data.page = page;
    const node = nodes.get(el.id); if (node) { node._pdfKey = null; renderPdfInto(node, el); }
    histUpd(before, el); send({ action: 'element_update', element: el });
    updatePdfControls();
  }
  // Панель управления PDF показывается у выбранного PDF (листание + извлечение).
  function selectedPdf() { if (selected.size !== 1) return null; const el = elements.get(Array.from(selected)[0]); return (el && el.type === 'pdf') ? el : null; }
  function updatePdfControls() {
    const bar = document.getElementById('pdf-controls'); if (!bar) return;
    const el = (tool === 'select') ? selectedPdf() : null;
    if (!el) { bar.hidden = true; return; }
    bar.hidden = false;
    const info = document.getElementById('pdf-page-info'); if (info) info.textContent = (el.data.page || 1) + ' / ' + (el.data.pages || 1);
    // Наблюдателю извлекать нечего — сервер и так откажет (board_upload
    // требует ROLE_EDITOR), но честнее не показывать кнопку, которая всегда
    // отвечает ошибкой.
    const row = document.getElementById('pdf-extract-row');
    if (row) row.hidden = viewOnly;
    const s = stage.scaleX(), sx = el.data.x * s + stage.x(), sy = el.data.y * s + stage.y() + STAGE_TOP;
    // Меряем панель ПО МЕСТУ (offsetWidth/offsetHeight), а не жёстким числом:
    // с полем списка страниц она стала заметно шире прежнего бюджета в 300px.
    // Клемп добавлен по ОБЕИМ осям — снизу его не было вовсе. 70 — тот же
    // потолок, что у соседних плавающих панелей (positionConnPanel), чтобы не
    // залезать на плашку названия и меню доски.
    const w = bar.offsetWidth || 300, h = bar.offsetHeight || 40;
    bar.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, sx)) + 'px';
    bar.style.top = Math.max(70, Math.min(window.innerHeight - h - 8, sy - 42)) + 'px';
  }

  // ── Рисование новых элементов ─────────────────────────────────────────
  let drawing = null;        // текущий рисуемый элемент
  let lastStreamAt = 0;

  function worldPoint() {
    // Координаты указателя в системе слоя (с учётом зума/панорамы).
    return stage.getRelativePointerPosition();
  }

  // Начали рисовать — убираем с глаз всё, что открыто поверх доски. Панель
  // связи, звонок и история сюда не входят: их открывают намеренно и надолго.
  function closeToolPanels() {
    document.querySelectorAll('#board-toolbar .tool-flyout.open').forEach((f) => f.classList.remove('open'));
    const скрыть = [['color-palette', 'cp-hidden'], ['settings-menu', 'sm-hidden'],
      ['stroke-panel', 'ps-hidden'], ['shape-panel', 'ps-hidden']];
    скрыть.forEach(([id, кл]) => { const el = document.getElementById(id); if (el) el.classList.add(кл); });
    // Всплывашка настроек пера прячется АТРИБУТОМ, а не классом: правила
    // «#dp-pop.ps-hidden» в стилях нет, и прежняя строка не делала ничего.
    closeDpPop();
    const bm = document.getElementById('board-menu'), bb = document.getElementById('board-menu-btn');
    if (bm) bm.hidden = true; if (bb) bb.classList.remove('on');
    // Мобильный лист — тоже панель поверх доски.
    if (typeof closeMobileSheet === 'function') closeMobileSheet();
  }
  // Округление значения ползунка толщины до половины. Раньше все три панели
  // настроек читали толщину целым числом, и половинные значения новых наборов
  // (1.5 и 2.5) при первом же касании ползунка пропадали навсегда.
  function полшага(v, lo, hi, шаг) {
    шаг = шаг || 0.5;
    let x = parseFloat(v);
    if (!isFinite(x)) x = lo;
    x = Math.round(x / шаг) * шаг;
    x = Math.max(lo, Math.min(hi, x));
    // 1.5 остаётся 1.5, а 3.0 печатается как 3 — иначе в поле видно «3.0».
    return Math.round(x * 100) / 100;
  }
  const PEN_MIN_STEP = 2;   // ближе этого (пикселей экрана) точки в штрих не берём
  // Лёгкое сглаживание: каждая внутренняя точка подтягивается к среднему с
  // соседями. Концы не трогаем — иначе штрих уползает от места, где человек
  // начал и закончил вести.
  function smoothStroke(pts) {
    const n = pts.length;
    if (n < 10) return pts;              // короткий штрих сглаживать нечего
    const out = pts.slice();
    for (let i = 2; i < n - 2; i += 2) {
      out[i] = pts[i - 2] * 0.25 + pts[i] * 0.5 + pts[i + 2] * 0.25;
      out[i + 1] = pts[i - 1] * 0.25 + pts[i + 1] * 0.5 + pts[i + 3] * 0.25;
    }
    return out;
  }
  function startDraw() {
    closeToolPanels();
    if (selected.size) clearSelection(); // начали рисовать — снять прежнее выделение
    const p = worldPoint();
    const base = { stroke: strokeColor, strokeWidth: strokeWidth };
    if (tool === 'pen') {
      drawing = { id: uuid(), type: 'freehand', z: 0,
        data: { ...base, x: p.x, y: p.y, points: [0, 0] } };
    } else if (tool === 'marker') {
      drawing = { id: uuid(), type: 'freehand', z: 0,
        data: { stroke: markerColor, strokeWidth: markerWidth, opacity: markerOpacity, x: p.x, y: p.y, points: [0, 0], marker: true } };
    } else if (tool === 'arrow') {
      drawing = { id: uuid(), type: 'arrow', z: 0,
        data: { ...base, strokeWidth: Math.max(1.5, strokeWidth), x: p.x, y: p.y, points: [0, 0, 0, 0], startCap: 'none', endCap: 'arrow' } };
    } else if (tool === 'line') {
      drawing = { id: uuid(), type: 'line', z: 0,
        data: { ...base, x: p.x, y: p.y, points: [0, 0, 0, 0], startCap: 'none', endCap: 'none' } };
    } else if (tool === 'divider') {
      // Разделитель — строго горизонтальная/вертикальная линия (ось выберется при протяжке).
      drawing = { id: uuid(), type: 'line', z: 0,
        data: { ...base, x: p.x, y: p.y, points: [0, 0, 0, 0], startCap: 'none', endCap: 'none', divider: 'h' } };
    } else if (tool === 'rect') {
      drawing = { id: uuid(), type: 'rect', z: 0,
        data: { ...base, x: p.x, y: p.y, width: 0, height: 0, _ax: p.x, _ay: p.y } };
    } else if (tool === 'ellipse') {
      drawing = { id: uuid(), type: 'ellipse', z: 0,
        data: { ...base, x: p.x, y: p.y, radiusX: 0, radiusY: 0, _ax: p.x, _ay: p.y } };
    } else if (SHAPE_TOOLS[tool]) {
      drawing = { id: uuid(), type: 'shape', z: 0,
        data: { ...base, color: strokeColor, x: p.x, y: p.y, width: 0, height: 0, _ax: p.x, _ay: p.y, kind: SHAPE_TOOLS[tool] } };
    } else if (tool === 'circle') {
      // Окружность: центр (с привязкой) фиксируем, радиус тянем мышью.
      const c = snapPoint(p);
      drawing = { id: uuid(), type: 'circle', z: 0,
        data: { stroke: strokeColor, strokeWidth: Math.max(1.5, strokeWidth), x: c.x, y: c.y, r: 0 } };
    } else if (tool === 'frame') {
      drawing = { id: uuid(), type: 'frame', z: 0,
        data: { x: p.x, y: p.y, width: 0, height: 0, _ax: p.x, _ay: p.y, cx: 0, cy: 0, unit: 40 } };
    }
    if (drawing) {
      upsertNode(drawing);
      send({ action: 'element_add', element: stripPrivate(drawing) });
    }
  }

  function moveDraw(shift) {
    if (!drawing) return;
    // Указателя может не быть вовсе: Konva забывает его позицию, когда курсор
    // покинул сцену. Без этой проверки обработчик движения падал с ошибкой, а
    // вместе с ним переставала работать вся остальная обработка движения.
    const p = worldPoint(); if (!p) return;
    const d = drawing.data;
    if (drawing.type === 'freehand') {
      // Не берём точки чаще, чем раз в PEN_MIN_STEP пикселей экрана. Раньше в
      // штрих попадало каждое событие движения, включая субпиксельное дрожание
      // руки, и сплайн Konva превращал его в пилу.
      const пт = d.points, n = пт.length;
      const nx = p.x - d.x, ny = p.y - d.y;
      if (n >= 2) {
        const шаг = PEN_MIN_STEP / (stage.scaleX() || 1);
        if (Math.hypot(nx - пт[n - 2], ny - пт[n - 1]) < шаг) return;
      }
      пт.push(nx, ny);
    } else if (drawing.type === 'rect') {
      const x = Math.min(p.x, d._ax), y = Math.min(p.y, d._ay);
      d.x = x; d.y = y;
      d.width = Math.abs(p.x - d._ax);
      d.height = Math.abs(p.y - d._ay);
    } else if (drawing.type === 'ellipse') {
      d.x = (p.x + d._ax) / 2; d.y = (p.y + d._ay) / 2;
      d.radiusX = Math.abs(p.x - d._ax) / 2;
      d.radiusY = Math.abs(p.y - d._ay) / 2;
    } else if (drawing.type === 'shape') {
      d.x = Math.min(p.x, d._ax); d.y = Math.min(p.y, d._ay);
      d.width = Math.abs(p.x - d._ax); d.height = Math.abs(p.y - d._ay);
    } else if (drawing.type === 'circle') {
      d.r = Math.hypot(p.x - d.x, p.y - d.y);
    } else if (drawing.type === 'line' || drawing.type === 'arrow') {
      let rx = p.x - d.x, ry = p.y - d.y;
      if (d.divider) { // разделитель — строго горизонтально/вертикально
        if (Math.abs(rx) >= Math.abs(ry)) { ry = 0; d.divider = 'h'; }
        else { rx = 0; d.divider = 'v'; }
      } else if (shift) { // Shift — привязка к ближайшему кратному 45° (проекция на луч)
        const ang = Math.round(Math.atan2(ry, rx) / (Math.PI / 4)) * (Math.PI / 4);
        const ux = Math.cos(ang), uy = Math.sin(ang), proj = rx * ux + ry * uy;
        rx = proj * ux; ry = proj * uy;
      }
      d.points = [0, 0, rx, ry];
    } else if (drawing.type === 'frame') {
      // Создание окна — тот же снап угла: края/центры + равные интервалы к соседям.
      const F = { x: d._ax, y: d._ay };
      if (!guideRefs) guideRefs = collectGuideRefs([drawing.id]);
      const R = frameCornerSnap({ x: p.x, y: p.y }, F);
      d.x = Math.min(R.x, F.x); d.y = Math.min(R.y, F.y);
      d.width = Math.abs(R.x - F.x); d.height = Math.abs(R.y - F.y);
      drawGuides(R.marks);
    }
    upsertNode(drawing);
    // Стримим рост штриха соседям, но не чаще ~30 мс.
    const now = Date.now();
    if (now - lastStreamAt > 30) {
      lastStreamAt = now;
      send({ action: 'element_update', element: stripPrivate(drawing) });
    }
  }

  // Вернуть узел активного штриха в общий слой. Зовётся из ВСЕХ выходов
  // endDraw, включая отказные: узел, забытый в лёгком слое, оказался бы вне
  // выделения, ластика и экспорта — то есть выглядел бы нарисованным, но не
  // существовал бы ни для чего.
  function settleDrawNode(id) {
    const n = nodes.get(id);
    if (n && n.getLayer() === drawLayer) {
      n.moveTo(layer);
      const el = elements.get(id);
      if (el && el.data && el.data.frame) attachToFrame(el, n);
      drawLayer.batchDraw(); layer.batchDraw();
    }
  }

  function endDraw() {
    if (!drawing) return;
    settleDrawNode(drawing.id);
    clearGuides(); // убрать направляющие создания окна (если были)
    // Случайный «клик» рамкой без протяжки — не создаём вырожденное окно.
    if (drawing.type === 'frame' && (drawing.data.width < 40 || drawing.data.height < 40)) {
      send({ action: 'element_delete', id: drawing.id });
      removeNode(drawing.id);
      drawing = null;
      return;
    }
    if (drawing.type === 'shape' && (drawing.data.width < 4 || drawing.data.height < 4)) {
      send({ action: 'element_delete', id: drawing.id }); removeNode(drawing.id); drawing = null; return;
    }
    // Линия/стрелка/разделитель без протяжки (клик) — вырожденная, не создаём.
    if ((drawing.type === 'line' || drawing.type === 'arrow')) {
      const pp = drawing.data.points || [0, 0, 0, 0];
      if (Math.hypot(pp[2] - pp[0], pp[3] - pp[1]) < 4) { send({ action: 'element_delete', id: drawing.id }); removeNode(drawing.id); drawing = null; return; }
    }
    if (drawing.type === 'freehand') {
      const пт = drawing.data.points || [];
      // Щелчок без движения — ставим точку. Отрезок нулевой длины браузер не
      // рисует даже с круглым концом, поэтому раздвигаем концы на волосок.
      // Отсюда и было «точка ставится через раз»: она появлялась, только если
      // рука дрогнула на пиксель и точек оказывалось две.
      if (пт.length <= 2) drawing.data.points = [пт[0] || 0, пт[1] || 0, (пт[0] || 0) + 0.01, пт[1] || 0];
      else drawing.data.points = smoothStroke(пт);
      upsertNode(drawing);      // без этого узел на холсте остаётся с прежними точками
    }
    send({ action: 'element_update', element: stripPrivate(drawing) });
    histAdd(stripPrivate(drawing));
    drawing = null;
  }

  function stripPrivate(el) {
    // Не шлём служебные поля (_ax/_ay) по сети.
    const data = {};
    for (const k in el.data) if (k[0] !== '_') data[k] = el.data[k];
    return { id: el.id, type: el.type, z: el.z, data };
  }

  // ── Касания, стилус и графический планшет ──────────────────────────────
  // Доска задумывалась под мышь: панорама была только на стрелках и колесе, а
  // палец на пустом месте рисовал рамку выделения. На телефоне и планшете это
  // означало, что по доске вообще нельзя перемещаться. Здесь мы добавляем жесты
  // и учим доску отличать перо от пальца.
  //
  // Правила (выбраны владельцем):
  //   • перо — всегда рисует;
  //   • пока перо ведёт, все касания считаются ладонью и игнорируются;
  //   • если на устройстве видели перо — палец ДВИГАЕТ доску (как в Procreate),
  //     чтобы можно было писать, положив руку на экран;
  //   • если пера не видели — палец рисует, а доску двигают двумя пальцами;
  //   • два пальца всегда: щипок — масштаб, движение — панорама.
  // Нажим намеренно не читаем: толщина линии всегда ровная.

  // Ключ поднят до v2: у тех, у кого доска ошибочно «увидела перо» от пальца,
  // старая отметка осталась бы в памяти браузера и правка не помогла бы.
  const PEN_SEEN_KEY = 'board-pen-seen-v2';     // на этом устройстве работали пером
  const FINGER_DRAW_KEY = 'board-finger-draw';  // ручное «всё равно рисовать пальцем»
  let penSeen = false, fingerDrawPref = false;
  try { penSeen = localStorage.getItem(PEN_SEEN_KEY) === '1'; } catch (e) {}
  try { fingerDrawPref = localStorage.getItem(FINGER_DRAW_KEY) === '1'; } catch (e) {}

  // Режим пера: палец двигает доску, а не рисует.
  function penMode() { return penSeen && !fingerDrawPref; }

  const touchPts = new Map();   // pointerId → {x, y} — активные касания на холсте
  let penDown = false;          // перо сейчас на экране
  let lastPenAt = 0;            // когда перо последний раз касалось — для отсечения ладони после пера
  let lastDownType = 'mouse';   // тип последнего нажатия (перо приходит и как касание)
  let gesture = null;           // идёт жест холста (панорама/щипок), рисованию не мешаем

  // Событие Konva — это касание ПАЛЬЦЕМ? Перо на iPad приходит тоже как касание,
  // поэтому проверяем и признак стилуса Safari, и тип последнего события указателя.
  function evtIsFinger(e) {
    const ev = e && e.evt;
    const list = ev && (ev.touches || ev.changedTouches);
    if (!list) return false;                    // мышь или перо без тач-совместимости
    const t0 = list[0];
    if (t0 && t0.touchType === 'stylus') return false;
    if (lastDownType === 'pen') return false;
    return true;
  }

  // Должна ли обычная логика доски пропустить это событие.
  function touchBlocked(e) {
    if (gesture) return true;                   // идёт жест — доска не рисует и не выделяет
    if (!evtIsFinger(e)) return false;          // мышь и перо всегда работают как раньше
    if (penDown) return true;                   // перо ведёт → это ладонь
    // В режиме пера палец не ведёт ШТРИХ — для этого есть перо, и именно от
    // касания ладонью мы защищаемся. Всё остальное пальцу доступно: стрелки,
    // фигуры, стирание, стикеры, текст, матокна. Раньше здесь стояло
    // `tool !== 'select'`, то есть пальцем можно было ТОЛЬКО выделять, хотя
    // перо для стрелки или стикера нужнее пальца ничуть не больше.
    //
    // Ладонь во время письма пером отсекается выше, проверкой penDown, и это
    // послабление её не касается.
    // Только что писали пером → палец сейчас это ладонь (перо ещё рядом).
    if (Date.now() - lastPenAt < 1200) return true;
    // Иначе палец РАБОТАЕТ как выбранный инструмент, в том числе рисует. Прежде
    // здесь пальцу запрещали карандаш/маркер в penMode — теперь пальцем можно
    // писать; панорама ушла на два пальца и кнопку «Перемещение».
    return false;
  }

  // Прервать начатое действие: при жесте нарисованное «в процессе» надо убрать,
  // иначе от щипка на доске останется случайная закорючка.
  function abortBoardInput() {
    if (typeof drawing !== 'undefined' && drawing) {
      send({ action: 'element_delete', id: drawing.id });
      removeNode(drawing.id);
      drawing = null;
    }
    endMarquee(); endFrameDrag(); endResize(); laserUp(); eraserUp(); lassoUp();
  }

  function markPenSeen() {
    if (penSeen) return;
    penSeen = true;
    try { localStorage.setItem(PEN_SEEN_KEY, '1'); } catch (e) {}
    syncFingerDrawUI();
    if (!fingerDrawPref) boardHint('Перо распознано. Писать можно и пером, и пальцем; доску двигайте двумя пальцами или кнопкой «Перемещение»');
  }

  function touchCenter() {
    let sx = 0, sy = 0, n = 0;
    touchPts.forEach((p) => { sx += p.x; sy += p.y; n++; });
    return n ? { x: sx / n, y: sy / n, n: n } : null;
  }
  function touchSpread() {
    const pts = Array.from(touchPts.values());
    if (pts.length < 2) return 0;
    return Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y);
  }
  // Экранная точка → координаты внутри контейнера сцены (их ждёт zoomTo).
  function toStageXY(x, y) {
    const r = stageEl.getBoundingClientRect();
    return { x: x - r.left, y: y - r.top };
  }

  function startGesture() {
    const c = touchCenter();
    if (!c) return;
    gesture = { cx: c.x, cy: c.y, dist: touchSpread() };
    abortBoardInput();
    stageEl.style.cursor = 'grabbing';
  }
  function updateGesture() {
    if (!gesture) return;
    const c = touchCenter();
    if (!c) return;
    // Панорама: доска едет за серединой между пальцами (или за единственным пальцем).
    const dx = c.x - gesture.cx, dy = c.y - gesture.cy;
    if (dx || dy) stage.position({ x: stage.x() + dx, y: stage.y() + dy });
    gesture.cx = c.x; gesture.cy = c.y;
    // Щипок: масштаб вокруг середины между пальцами — точка под пальцами стоит на месте.
    const d = touchSpread();
    if (d > 0 && gesture.dist > 0) {
      const k = d / gesture.dist;
      if (Math.abs(k - 1) > 0.002) zoomTo(stage.scaleX() * k, toStageXY(c.x, c.y));
      gesture.dist = d;
    } else if (d > 0) {
      gesture.dist = d;
    }
    scheduleViewRedraw();   // перерисовать сетку/курсоры и передать вид ведомым
  }
  function endGestureIfDone() {
    if (touchPts.size === 0) {
      gesture = null;
      stageEl.style.cursor = (tool === 'select') ? 'default' : 'crosshair';
    }
  }

  // Слушаем события указателя ДО Konva: браузер шлёт pointerdown раньше
  // touchstart, поэтому к моменту работы обычных обработчиков доски мы уже
  // знаем, чем именно человек прикоснулся к экрану.
  // Стилус у части устройств приходит не как 'pen', а как касание с признаком
  // стилуса. Такое касание — это перо, и в жестах оно участвовать не должно:
  // иначе стилус вместо письма таскает доску.
  function stylusEvent(ev) {
    // ТОЛЬКО честный тип указателя. Прежде здесь была ещё догадка по касанию
    // (нулевое пятно и давление), и на части планшетов под неё попадал обычный
    // ПАЛЕЦ: доска запоминала «здесь есть перо» навсегда, после чего пальцем
    // нельзя было ни выделить объект, ни нажать кнопку на холсте. Современные
    // планшеты сообщают перо честно, догадка не нужна.
    return ev.pointerType === 'pen';
  }
  // Палец сдвинулся на столько — значит ведёт доску, а не тыкает.
  const TOUCH_PAN_PX = 8;
  let pendingPan = null;   // палец лежит, но пока непонятно: щелчок это или панорама

  stageEl.addEventListener('pointerdown', (ev) => {
    lastDownType = ev.pointerType || 'mouse';
    if (stylusEvent(ev)) { lastDownType = 'pen'; markPenSeen(); penDown = true; lastPenAt = Date.now(); return; }
    if (ev.pointerType !== 'touch') return;
    touchPts.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    if (penDown) return;                       // ладонь при письме пером — молчим
    if (gesture) { startGesture(); return; }   // добавился ещё палец — пересчитать опору
    // Два пальца — щипок сразу, тут гадать нечего.
    if (touchPts.size >= 2) { pendingPan = null; startGesture(); return; }
    // Один палец в режиме пера или в режиме перемещения: НЕ хватаем доску сразу.
    // Сначала ждём движения — иначе пальцем нельзя ни выбрать объект, ни ткнуть
    // в кнопку на холсте, только возить доску.
    // Один палец возит доску ТОЛЬКО при включённой кнопке «Перемещение».
    // Иначе палец делает то, что выбрано (рисует, ставит объект, двигает).
    // Панорама двумя пальцами — выше, отдельной веткой.
    if (panMode) pendingPan = { id: ev.pointerId, x: ev.clientX, y: ev.clientY };
  }, true);

  stageEl.addEventListener('pointermove', (ev) => {
    if (ev.pointerType !== 'touch') return;
    if (!touchPts.has(ev.pointerId)) return;
    touchPts.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    // Палец пошёл — только теперь это панорама.
    if (pendingPan && ev.pointerId === pendingPan.id && !gesture) {
      if (Math.hypot(ev.clientX - pendingPan.x, ev.clientY - pendingPan.y) >= TOUCH_PAN_PX) {
        pendingPan = null; startGesture();
      }
    }
    if (gesture) { ev.preventDefault(); updateGesture(); }
  }, true);

  function onPointerGone(ev) {
    if (ev.pointerType === 'pen') { penDown = false; lastPenAt = Date.now(); return; }
    if (ev.pointerType !== 'touch') return;
    if (pendingPan && ev.pointerId === pendingPan.id) pendingPan = null;
    touchPts.delete(ev.pointerId);
    if (gesture) {
      if (touchPts.size >= 1) startGesture();  // остались пальцы — продолжаем с новой опорой
      else endGestureIfDone();
    }
  }
  stageEl.addEventListener('pointerup', onPointerGone, true);
  stageEl.addEventListener('pointercancel', onPointerGone, true);
  // Перо могло уйти за край экрана — иначе penDown завис бы включённым.
  // То же самое и с пальцем: pointerup слушался только на сцене, поэтому палец,
  // отпущенный за её краем, навсегда оставался в списке касаний. Следующее
  // касание считалось вторым, начинался «щипок» — и доска переставала рисовать.
  window.addEventListener('pointerup', (ev) => {
    if (ev.pointerType === 'pen') { penDown = false; return; }
    if (ev.pointerType === 'touch' && touchPts.has(ev.pointerId)) onPointerGone(ev);
  }, true);
  // То же и для отмены: системный жест у края экрана шлёт pointercancel, и он
  // тоже приходит мимо сцены.
  window.addEventListener('pointercancel', (ev) => {
    if (ev.pointerType === 'pen') { penDown = false; return; }
    if (ev.pointerType === 'touch' && touchPts.has(ev.pointerId)) onPointerGone(ev);
  }, true);

  // Переключатель «Рисовать пальцем» в меню доски: нужен, если перо на устройстве
  // есть, но сейчас его нет под рукой. Показываем только там, где он осмыслен.
  function syncFingerDrawUI() {
    const row = document.getElementById('finger-draw-row');
    const box = document.getElementById('finger-draw');
    if (!row || !box) return;
    row.hidden = !penSeen;
    box.checked = fingerDrawPref;
  }
  function setFingerDraw(on) {
    fingerDrawPref = !!on;
    try { localStorage.setItem(FINGER_DRAW_KEY, on ? '1' : '0'); } catch (e) {}
    boardHint(on ? 'Палец рисует; доску двигайте двумя пальцами'
                 : 'Палец двигает доску; рисуйте пером');
  }
  (function initFingerDrawToggle() {
    const box = document.getElementById('finger-draw');
    if (box) box.addEventListener('change', () => setFingerDraw(box.checked));
    syncFingerDrawUI();
  })();

  // ── События указателя ─────────────────────────────────────────────────
  // Выделение и захват старта перетаскивания — на mousedown (press-to-select),
  // ДО того как Konva сдвинет узел. Это и устраняет рассинхрон группового
  // перетаскивания (стартовые позиции точны), и убирает двойную обработку.
  stage.on('mousedown touchstart', (e) => {
    if (e.evt && e.evt.button === 2) return;  // правая кнопка двигает доску
    if (rmbPan) return;                       // правой уже тянут — не мешаем
    // Идёт обрезка: нажатие начинает рамку, а не выделение.
    if (cropId) {
      const p = worldPoint(), b = cropBox();
      if (p && b) {
        cropDrag = { x0: Math.max(b.x, Math.min(p.x, b.x + b.w)), y0: Math.max(b.y, Math.min(p.y, b.y + b.h)) };
        cropRect.x(cropDrag.x0); cropRect.y(cropDrag.y0); cropRect.width(0); cropRect.height(0);
      }
      if (e.evt) e.evt.preventDefault();
      return;
    }
    if (panMode || touchBlocked(e)) return;   // идёт перемещение доски / щипок — не выделяем
    if (tool !== 'select') return;
    // Клик по ручке/рамке трансформера — отдать Konva (ресайз), не обрабатывать.
    if (e.target && (e.target === tr || (e.target.getParent && e.target.getParent() === tr))) return;
    // Клик по ПОДПИСИ точки — тащим только подпись, а не саму точку. Ищем по
    // рамке подписи в координатах слоя (хит-граф Konva для геометрии не годится,
    // см. pickObjectAtWorld). Кружок точки в приоритете: рядом с ним — захват
    // самой точки, а не буквы. Ловим ДО геометрического разбора объекта.
    if (!viewOnly) {
      const wp0 = stage.getRelativePointerPosition();
      const inBox = (p, r, m) => p && r && p.x >= r.x - m && p.x <= r.x + r.width + m && p.y >= r.y - m && p.y <= r.y + r.height + m;
      let labelPid = null;
      if (wp0) elements.forEach((pe) => {
        if (labelPid || pe.type !== 'point' || !pe.data.frame || pe.data.labelHidden) return;
        const n = nodes.get(pe.id); if (!n) return;
        const lbl = n.findOne('.plabel'); if (!lbl || !lbl.visible()) return;
        const gl = n.findOne('.pglyph');
        if (gl && inBox(wp0, gl.getClientRect({ relativeTo: layer }), 2)) return; // это сам кружок
        if (inBox(wp0, lbl.getClientRect({ relativeTo: layer }), 2)) labelPid = pe.id;
      });
      if (labelPid) {
        const n = nodes.get(labelPid), lbl = n.findOne('.plabel');
        labelDrag = { pid: labelPid, sx: wp0.x, sy: wp0.y, lx0: lbl.x(), ly0: lbl.y(), before: clone(elements.get(labelPid)), moved: false };
        return;
      }
    }
    // Сначала ищем объект под курсором (включая привязанную к окну геометрию).
    let resolved = e.target;
    while (resolved && resolved !== stage && !(resolved.id && nodes.has(resolved.id()))) {
      resolved = resolved.getParent();
    }
    let id = (resolved && resolved.id && nodes.has(resolved.id())) ? resolved.id() : null;
    let rel = id ? elements.get(id) : null;

    // ЕДИНЫЙ геометрический выбор объекта под курсором (надёжнее hit-графа Konva:
    // точки/окружности/линии/заливка многоугольника ловятся по геометрии).
    {
      const wpp = stage.getRelativePointerPosition();
      const g = wpp ? pickObjectAtWorld(wpp) : null;
      if (g) { id = g.id; rel = g; }
    }

    // Режим скрытия: щелчок прячет объект или возвращает его. Окна пропускаем —
    // щелчок по пустому месту внутри окна должен начинать рамку, а не прятать
    // окно целиком вместе со всем построением.
    if (revealHidden && !viewOnly && rel && rel.type !== 'frame') {
      setHidden([rel.id], !(rel.data && rel.data.hidden));
      dragStart = null;
      return;
    }

    // Под курсором окно (его фон/сетка) или пусто → панорама плоскости/активация.
    if (!rel || rel.type === 'frame') {
      const wpp = stage.getRelativePointerPosition();
      const fp = wpp && frameAtWorld(wpp.x, wpp.y, true);
      if (fp) {
        if (activeFrameId === fp.id) {
          framePan = { id: fp.id, sx: wpp.x, sy: wpp.y, cx0: fp.data.cx, cy0: fp.data.cy };
        } else {
          selectOnly(fp.id); // первый клик — активировать окно
        }
        dragStart = null;
        return;
      }
      if (vennSel.id) clearVennSel();
      startMarquee(e); // пустое место → рамочное выделение
      dragStart = null;
      return;
    }

    // Линия/окружность — свой параллельный перенос (двигаем опорные точки).
    if (rel && isPointBoundLine(rel)) {
      if (isAddKey(e.evt)) { toggleSelect(id); }
      else { selectOnly(id); startLineDrag(id); }
      dragStart = null;
      return;
    }

    // Клик по диаграмме Венна выбирает ОБЛАСТЬ внутри неё (Ctrl — несколько),
    // а не только сам объект: заливать и подписывать надо именно области.
    if (rel && rel.type === 'venn' && !isAddKey(e.evt)) {
      // Первый клик по невыделенной диаграмме только ВЫБИРАЕТ её — тогда
      // появляется палитра. Красить начинаем со второго клика, когда цвет уже
      // выбран. Иначе палитры ещё нет на экране, а зона уже закрашена.
      if (selected.has(rel.id)) {
        const wp = stage.getRelativePointerPosition();
        if (wp) vennPickRegion(rel, wp.x, wp.y);
      } else {
        vennSel = { id: rel.id, key: null };
        showVennBar(rel);
      }
    } else if (vennSel.id && (!rel || rel.type !== 'venn')) {
      clearVennSel();
    }

    // Под курсором обычный объект (или привязанная геометрия) — выделяем/тащим.
    if (isAddKey(e.evt)) {
      toggleSelect(id);            // Shift/Ctrl — добавить или убрать из выделения
    } else if (!selected.has(id)) {
      selectOnly(id);              // обычный клик по невыделенному — выбрать его группу
    } // клик по уже выделенному без Shift — сохраняем выделение (чтобы тащить всё)

    // Картинка/PDF «уносит» с собой надписи карандашом/маркером, лежащие на ней.
    const clickedEl = elements.get(id);
    let carry = [];
    if (clickedEl && (clickedEl.type === 'image' || clickedEl.type === 'pdf')) {
      carry = objectsOnCarrier(clickedEl).filter((x) => x !== id && !selected.has(x));
    }
    if ((selected.has(id) && selected.size > 1) || carry.length) {
      const lead = nodes.get(id);
      const followerIds = new Set();
      Array.from(selected).forEach((x) => { if (x !== id) followerIds.add(x); });
      carry.forEach((x) => followerIds.add(x));
      dragStart = {
        leadId: id, leadX0: lead.x(), leadY0: lead.y(),
        items: Array.from(followerIds)
          .map((x) => {
            // Геометрию по точкам НЕ смещаем узлом (это оторвёт её от точек) — она
            // следует за своими точками через recomputeGeometry, если те в выделении.
            if (isPointBound(elements.get(x))) return null;
            const n = nodes.get(x); if (n) return { node: n, x0: n.x(), y0: n.y() };
            const w = widgetItems.get(x); if (w) return { widget: w, wx0: (w.el.data.x || 0), wy0: (w.el.data.y || 0) };
            return null;
          })
          .filter(Boolean),
      };
    } else {
      dragStart = null;
    }
  });
  // Всё, что лежит НА картинке или PDF, едет вместе с ней. Раньше ехали только
  // штрихи карандаша, а подписи, формулы, стрелки и стикеры оставались на
  // месте — и разбор отрывался от картинки, к которой относился.
  //
  // Носителями друг друга не считаем: картинка, PDF и матокно — самостоятельные
  // объекты, они не должны утаскивать друг друга. И не трогаем то, что живёт
  // ВНУТРИ матокна: у такого объекта координаты локальные, относительно окна, и
  // сдвиг на мировые dx/dy оторвал бы его от окна.
  const CARRY_SKIP = { image: 1, pdf: 1, frame: 1 };
  function objectsOnCarrier(imgEl) {
    const d = imgEl.data, ib = { x: d.x || 0, y: d.y || 0, w: d.width || 0, h: d.height || 0 };
    if (ib.w <= 0 || ib.h <= 0) return [];
    const внутри = (cx, cy) => cx >= ib.x && cx <= ib.x + ib.w && cy >= ib.y && cy <= ib.y + ib.h;
    const res = [];
    elements.forEach((el, eid) => {
      if (eid === imgEl.id || CARRY_SKIP[el.type]) return;
      if (el.data && el.data.frame) return;          // геометрия внутри матокна
      if (isPointBound(el)) return;                  // следует за своими точками
      const w = widgetItems.get(eid);
      if (w && w.wrapper) {                          // текст, стикер, таблица — DOM
        const ww = w.wrapper.offsetWidth || 0, wh = w.wrapper.offsetHeight || 0;
        if (внутри((el.data.x || 0) + ww / 2, (el.data.y || 0) + wh / 2)) res.push(eid);
        return;
      }
      const n = nodes.get(eid); if (!n || typeof n.getClientRect !== 'function') return;
      const b = n.getClientRect({ relativeTo: layer });
      if (!b || (!b.width && !b.height)) return;
      if (внутри(b.x + b.width / 2, b.y + b.height / 2)) res.push(eid);
    });
    return res;
  }
  // Щелчок по объекту, которому задана ссылка, переходит по ней. Только
  // инструментом «выделение» и только если это именно щелчок, а не окончание
  // перетаскивания: иначе объект нельзя было бы просто подвинуть.
  let clickDownAt = null;
  stage.on('mousedown touchstart', (e) => {
    if (e.evt && e.evt.button === 2) return;
    const p = stage.getPointerPosition();
    clickDownAt = p ? { x: p.x, y: p.y } : null;
  });
  stage.on('click tap', () => {
    if (tool !== 'select' || !clickDownAt) return;
    const p = stage.getPointerPosition();
    if (!p || Math.hypot(p.x - clickDownAt.x, p.y - clickDownAt.y) > 4) return;  // это было перетаскивание
    const w = stage.getRelativePointerPosition();
    const g = w ? pickObjectAtWorld(w) : null;
    if (g && g.data && g.data.link) openObjectLink(g);
  });
  // Двойной щелчок по не загрузившейся картинке — попробовать ещё раз.
  stage.on('dblclick dbltap', (e) => {
    let n = e.target;
    while (n && n !== stage && !(n.id && nodes.has(n.id()))) n = n.getParent();
    const id = (n && n.id && nodes.has(n.id())) ? n.id() : null;
    const el = id ? elements.get(id) : null;
    if (el && el.type === 'image' && nodes.get(id) && nodes.get(id)._imgFail) {
      if (e.evt) e.evt.preventDefault();
      reloadImage(id);
    }
  });
  // Двойной клик по тексту — открыть редактор с его содержимым (в любом режиме).
  stage.on('dblclick dbltap', (e) => {
    let n = e.target;
    while (n && n !== stage && !(n.id && nodes.has(n.id()))) n = n.getParent();
    const id = (n && n.id && nodes.has(n.id())) ? n.id() : null;
    let el = id ? elements.get(id) : null;
    // Под курсором мог оказаться оверлей (ручка/рамка выделенного текста) — тогда
    // ищем текст геометрически по рамке (иначе повторное редактирование не открывается).
    if (!(el && el.type === 'text')) {
      const w = stage.getRelativePointerPosition();
      if (w) {
        elements.forEach((t) => {
          if (t.type !== 'text' || (t.data && t.data.hidden)) return;
          const nn = nodes.get(t.id); if (!nn) return;
          const b = nn.getClientRect({ relativeTo: layer });
          if (w.x >= b.x && w.x <= b.x + b.width && w.y >= b.y && w.y <= b.y + b.height) el = t;
        });
      }
    }
    teLog({ ev: 'dblclick', resolvedType: el ? el.type : null, editorOpen: !textEditor.hidden });
    if (el && el.type === 'text' && !(el.data && el.data.locked)) {
      if (e.evt) e.evt.preventDefault();
      // НЕ выделяем текст (иначе вокруг него рамка выделения) — сразу в редактор.
      setTool('select'); openTextEditorFor(el);
    } else if (el && (el.type === 'rect' || el.type === 'ellipse' || el.type === 'shape') && !(el.data && el.data.locked)) {
      if (e.evt) e.evt.preventDefault();
      setTool('select'); startShapeTextEdit(el); // двойной клик по фигуре — писать текст внутри
    }
  });
  stage.on('mousedown touchstart', (e) => {
    // Правая кнопка двигает доску. Без этой проверки нажатие правой при
    // карандаше НАЧИНАЛО штрих — заодно с меню.
    if (e.evt && e.evt.button === 2) return;
    // Взялись за холст — панели поверх него убираем. Раньше это делал только
    // startDraw, а ветки «точка», «отрезок», «текст», «лазер» и вся геометрия
    // выходят раньше и панели оставляли висеть. На планшете это особенно
    // заметно: там сторожа «нажали мимо» не срабатывают вовсе, потому что
    // Konva гасит touchstart при попадании в фигуру.
    closeToolPanels();
    if (rmbPan) return;                       // правой уже тянут — не мешаем
    if (panMode || touchBlocked(e)) return;   // идёт перемещение доски / щипок — не рисуем
    if (tool === 'select') return; // в режиме выделения сцена сама панорамит
    if (tool === 'latex') { openLatexEditor(); return; }
    if (tool === 'graph') { if (e.evt) e.evt.preventDefault(); handleGraphPick(worldPoint()); return; }
    if (tool === 'text') { openTextEditor(false); return; }
    if (tool === 'text_plain') { if (e.evt) e.evt.preventDefault(); insertTextbox(); return; }
    if (tool === 'geogebra') { insertGeoGebra(); return; }
    if (tool === 'embed') { if (e.evt) e.evt.preventDefault(); insertEmbed(); return; }
    if (tool === 'poll') { if (e.evt) e.evt.preventDefault(); insertPoll(); return; }
    if (tool === 'venn') { if (e.evt) e.evt.preventDefault(); insertVenn(); return; }
    if (tool === 'screen') { if (e.evt) e.evt.preventDefault(); setTool('select'); startScreenShare(); return; }
    if (tool === 'point') { if (e.evt) e.evt.preventDefault(); placePoint(); return; }
    if (tool === 'isect') { if (e.evt) e.evt.preventDefault(); handleIsectPick(worldPoint()); return; }
    if (tool === 'polygon') { if (e.evt) e.evt.preventDefault(); handlePolygonPick(); return; }
    if (tool === 'regpoly_center' || tool === 'regpoly_edge') { if (e.evt) e.evt.preventDefault(); handleRegPolyPick(); return; }
    if (tool === 'midpoint') { if (e.evt) e.evt.preventDefault(); handleMidpointPick(); return; }
    if (tool === 'ratio') { if (e.evt) e.evt.preventDefault(); handleRatioPick(); return; }
    if (tool === 'angle_deg') { if (e.evt) e.evt.preventDefault(); handleAngleDegPick(worldPoint()); return; }
    if (tool === 'vector') { if (e.evt) e.evt.preventDefault(); handleVectorPick(worldPoint()); return; }
    if (tool === 'ftangent') { if (e.evt) e.evt.preventDefault(); handleTangentPick(worldPoint()); return; }
    if (tool === 'farea') { if (e.evt) e.evt.preventDefault(); handleAreaPick(worldPoint()); return; }
    if (tool === 'fintersect') { if (e.evt) e.evt.preventDefault(); handleFIntersectPick(worldPoint()); return; }
    if (tool === 'region') { if (e.evt) e.evt.preventDefault(); handleRegionPick(worldPoint()); return; }
    if (tool === 'regionsys') { if (e.evt) e.evt.preventDefault(); handleRegionSysPick(worldPoint()); return; }
    if (tool === 'macro_record') { if (e.evt) e.evt.preventDefault(); handleMacroRecordPick(worldPoint()); return; }
    if (tool === 'macro') { if (e.evt) e.evt.preventDefault(); handleMacroApplyPick(worldPoint()); return; }
    if (MEASURE_PICKS[tool]) { if (e.evt) e.evt.preventDefault(); handleMeasurePick(worldPoint()); return; }
    if (MARK_PICKS[tool]) { if (e.evt) e.evt.preventDefault(); handleMarkPick(worldPoint()); return; }
    if (XFORM_SPEC[tool]) { if (e.evt) e.evt.preventDefault(); handleXformPick(worldPoint(), !!(e.evt && e.evt.shiftKey)); return; }
    if (CIRCLE_PICKS[tool]) { if (e.evt) e.evt.preventDefault(); handleCirclePick(); return; }
    if (CONSTRUCT_PICKS[tool]) { if (e.evt) e.evt.preventDefault(); handleConstructPick(); return; }
    if (tool === 'table') { if (e.evt) e.evt.preventDefault(); insertTable(); return; }
    if (tool === 'kanban') { if (e.evt) e.evt.preventDefault(); insertKanban(); return; }
    if (tool === 'timer') { if (e.evt) e.evt.preventDefault(); insertTimer(); return; }
    if (tool === 'wheel') { if (e.evt) e.evt.preventDefault(); insertWheel(); return; }
    if (tool === 'slider') { if (e.evt) e.evt.preventDefault(); insertSlider(); return; }
    if (tool === 'sticky') { if (e.evt) e.evt.preventDefault(); insertSticky(); return; }
    if (tool === 'comment') { if (e.evt) e.evt.preventDefault(); insertComment(); return; }
    if (tool === 'card') { if (e.evt) e.evt.preventDefault(); insertCard(); return; }
    if (tool === 'laser') { if (e.evt) e.evt.preventDefault(); laserDown(); return; }
    if (isEraser(tool)) { if (e.evt) e.evt.preventDefault(); eraserDown(); return; }
    if (tool === 'lasso') { if (e.evt) e.evt.preventDefault(); lassoDown(); return; }
    if (e.evt) e.evt.preventDefault();
    startDraw();
  });
  stage.on('mousemove touchmove', (e) => {
    if (touchBlocked(e)) return;   // движение принадлежит жесту холста
    sendCursor();
    if (tool === 'laser') laserMove();
    else if (isEraser(tool)) { eraserMove(); positionEraserRing(); }
    else if (tool === 'lasso') lassoMove();
    if (drawing) moveDraw(!!(e && e.evt && e.evt.shiftKey));
    if (cropId && cropDrag) cropMove();
    if (marquee) updateMarquee();
    if (frameMove) doFrameMove();
    if (framePan) doFramePan();
    if (lineDrag) doLineDrag();
    if (labelDrag) doLabelDrag();
    if (resizeState) doResize();
    if (tool === 'polygon' && polyPicks.length) updatePolyPreview(worldPoint());
  });
  stage.on('mouseup touchend', (e) => { if (touchBlocked(e)) return; abortActiveInput(); });
  stage.on('mouseleave', () => { abortActiveInput(); });

  // Закрыть любое начатое действие. Вызывается и со сцены, и из страховки на
  // уровне окна, поэтому все end-функции внутри устроены так, что повторный
  // вызов ничего не делает.
  function abortActiveInput() {
    if (cropId) { finishCrop(); return; }
    endDraw(); endMarquee(); endFrameDrag(); endResize();
    laserUp(); eraserUp(); lassoUp();
    if (eraserRing) eraserRing.style.display = 'none';
  }

  // СТРАХОВКА НА УРОВНЕ ОКНА. Сцена узнаёт об отпускании кнопки только если оно
  // случилось над ней. Стоит увести указатель за край окна и отпустить там —
  // и штрих остаётся незавершённым, а доска перестаёт слушаться: карандаш
  // больше не рисует, пока что-нибудь случайно не сбросит состояние.
  // Слушаем на окне, в фазе перехвата, чтобы поймать событие где угодно.
  window.addEventListener('mouseup', abortActiveInput, true);
  window.addEventListener('pointerup', abortActiveInput, true);
  window.addEventListener('pointercancel', abortActiveInput, true);
  // Окно потеряло фокус (переключились в другую программу прямо во время
  // штриха) — отпускания мы уже не увидим никогда.
  window.addEventListener('blur', () => {
    abortActiveInput();
    // Пробел-панорама: клавиша могла быть отпущена в другом окне, и тогда
    // доска навсегда осталась бы в режиме перемещения — рисование в нём
    // выключено, что выглядит ровно как «карандаш не рисует».
    if (spaceHeld) { spaceHeld = false; setPanMode(panBeforeSpace); }
  });

  function doFrameMove() {
    const el = elements.get(frameMove.id); if (!el) return;
    const w = worldPoint();
    // мелкое дрожание = клик (для выделения), а не перемещение
    if (!frameMove.moved && Math.hypot(w.x - frameMove.sx, w.y - frameMove.sy) < 3 / stage.scaleX()) return;
    frameMove.moved = true;
    el.data.x = frameMove.ox + (w.x - frameMove.sx);
    el.data.y = frameMove.oy + (w.y - frameMove.sy);
    const n = nodes.get(frameMove.id);
    if (n) {
      n.position({ x: el.data.x, y: el.data.y });
      if (!guideRefs) guideRefs = collectGuideRefs([frameMove.id]);
      const snap = computeDragSnap({ x: el.data.x, y: el.data.y, w: el.data.width, h: el.data.height });
      if (snap.dx || snap.dy) { el.data.x += snap.dx; el.data.y += snap.dy; n.position({ x: el.data.x, y: el.data.y }); }
      drawGuides(snap.lines);
    }
    positionHandles();
    tr.forceUpdate();
    if (activeFrameId === frameMove.id) updateFuncEditor();
    recomputeGeometry(); // как doFramePan/zoom/resize: векторы и подписи-измерения на главном слое, привязанные к точкам окна, тоже пересчитать
    layer.batchDraw();
  }
  function doFramePan() {
    const el = elements.get(framePan.id); if (!el) return;
    const w = worldPoint();
    const dpx = w.x - framePan.sx, dpy = w.y - framePan.sy; // сдвиг в px доски
    el.data.cx = framePan.cx0 - dpx / el.data.unit; // тянем плоскость за курсором
    el.data.cy = framePan.cy0 + dpy / el.data.unit;
    recomputeGeometry();
    layer.batchDraw();
  }
  function endFrameDrag() {
    if (frameMove) {
      const el = elements.get(frameMove.id);
      if (frameMove.moved) { if (el) send({ action: 'element_update', element: el }); }
      else if (frameMove.shift) { toggleSelect(frameMove.id); } // Shift+клик по шапке — добавить окно к выделению
      else { selectOnly(frameMove.id); } // клик по шапке без сдвига — выделить окно (ручки)
      frameMove = null;
      clearGuides();
    }
    if (framePan) { const el = elements.get(framePan.id); if (el) send({ action: 'element_update', element: el }); framePan = null; }
    if (lineDrag) { endLineDrag(); }
    if (labelDrag) { endLabelDrag(); }
  }

  // ── Параллельный перенос линии-построения ──────────────────────────────
  // Тащим линию → двигаем её опорные точки; точки НА линии (on:{line}) едут за
  // ней автоматически (их пересчитывает recomputeGeometry по параметру t).
  function startLineDrag(id) {
    const el = elements.get(id); if (!el) return;
    const fr = el.data.frame ? elements.get(el.data.frame) : null;
    const w = worldPoint();
    const s = fr ? { x: w.x - fr.data.x, y: w.y - fr.data.y } : w; // локальные коорд окна (или мировые)
    const pts = lineOwnPoints(el).map((pid) => {
      const pe = elements.get(pid); if (!pe) return null;
      const l = fr ? frameMathToLocal(fr, pe.data.mx || 0, pe.data.my || 0) : { x: pe.data.x, y: pe.data.y };
      return { id: pid, x0: l.x, y0: l.y };
    }).filter(Boolean);
    lineDrag = { id: id, fr: fr, sx: s.x, sy: s.y, pts: pts, moved: false };
  }
  function doLineDrag() {
    const el = elements.get(lineDrag.id); if (!el) { lineDrag = null; return; }
    const fr = lineDrag.fr, w = worldPoint();
    const cur = fr ? { x: w.x - fr.data.x, y: w.y - fr.data.y } : w;
    const dx = cur.x - lineDrag.sx, dy = cur.y - lineDrag.sy;
    if (!lineDrag.moved && Math.hypot(dx, dy) < 3 / stage.scaleX()) return; // дрожание = клик
    lineDrag.moved = true;
    lineDrag.pts.forEach((p) => {
      const pe = elements.get(p.id); if (!pe) return;
      const nx = p.x0 + dx, ny = p.y0 + dy;
      if (fr) { const m = frameLocalToMath(fr, nx, ny); pe.data.mx = m.mx; pe.data.my = m.my; }
      else {
        // ВНЕ матокна пересчёт узлы точек не трогает — двигаем их сами, иначе
        // фигура уедет за опорными точками, а маркеры точек останутся стоять
        // («многоугольник летает без точек»).
        pe.data.x = nx; pe.data.y = ny;
        const pn = nodes.get(p.id); if (pn) pn.position({ x: nx, y: ny });
      }
    });
    recomputeGeometry();
    positionHandles();
    layer.batchDraw();
  }
  function endLineDrag() {
    if (!lineDrag) return;
    const el = elements.get(lineDrag.id);
    if (lineDrag.moved && el) {
      // Разослать сдвинутые опорные точки и точки, привязанные к этой линии.
      const moved = new Set(lineDrag.pts.map((p) => p.id));
      elements.forEach((e) => { if (e.type === 'point' && e.data.on && e.data.on.line === lineDrag.id) moved.add(e.id); });
      moved.forEach((pid) => { const pe = elements.get(pid); if (pe) send({ action: 'element_update', element: pe }); });
    } else if (el) {
      selectOnly(lineDrag.id); // клик без сдвига — просто выделить
    }
    lineDrag = null;
  }
  // Подпись точки: тянем букву, смещение от места по умолчанию (8, -(fs+3))
  // ограничиваем радиусом и храним в data.labelOff. Работаем в координатах слоя
  // (worldPoint): группа точки и подпись — чистые сдвиги без своего масштаба,
  // поэтому сдвиг указателя в мире = сдвиг подписи в её локальных координатах.
  function labelBaseFor(el) { const fs = labelFontOf(el.data); return { x: 8, y: -(fs + 3), R: Math.max(28, fs * 2.4) }; }
  function doLabelDrag() {
    const el = elements.get(labelDrag.pid); if (!el) { labelDrag = null; return; }
    const n = nodes.get(el.id), lbl = n && n.findOne('.plabel'); if (!lbl) return;
    const w = worldPoint(), b = labelBaseFor(el);
    let ox = (labelDrag.lx0 + (w.x - labelDrag.sx)) - b.x;
    let oy = (labelDrag.ly0 + (w.y - labelDrag.sy)) - b.y;
    const dd = Math.hypot(ox, oy);
    if (dd > b.R) { ox = ox / dd * b.R; oy = oy / dd * b.R; }
    lbl.position({ x: b.x + ox, y: b.y + oy });
    if (!labelDrag.moved && Math.hypot(w.x - labelDrag.sx, w.y - labelDrag.sy) > 2 / stage.scaleX()) labelDrag.moved = true;
    layer.batchDraw();
  }
  function endLabelDrag() {
    const el = elements.get(labelDrag.pid);
    if (el && labelDrag.moved) {
      const n = nodes.get(el.id), lbl = n && n.findOne('.plabel'), b = labelBaseFor(el);
      if (lbl) el.data.labelOff = { x: Math.round((lbl.x() - b.x) * 10) / 10, y: Math.round((lbl.y() - b.y) * 10) / 10 };
      histUpd(labelDrag.before, el); send({ action: 'element_update', element: el });
    } else if (el) { selectOnly(labelDrag.pid); }
    labelDrag = null;
  }

  // ── Зум: колесо к указателю + контрол справа снизу ────────────────────
  const SCALE_BY = 1.06;
  // 3%: доска обзорная, на ней раскладывают уроки целиком, и с 15% общий план
  // не помещался. Сетка теперь не мешает — шаг подстраивается (gridStepFor).
  const MIN_SCALE = 0.03, MAX_SCALE = 5;
  const zoomInput = document.getElementById('zoom-percent');

  function updateZoomLabel() {
    if (zoomInput && document.activeElement !== zoomInput) {
      zoomInput.value = Math.round(stage.scaleX() * 100) + '%';
    }
  }

  // Масштабирует к newScale вокруг точки center (экранные коорды). Без center —
  // вокруг центра видимой области.
  function zoomTo(newScale, center) {
    const oldScale = stage.scaleX();
    const clamped = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScale));
    const c = center || { x: stage.width() / 2, y: stage.height() / 2 };
    const wp = { x: (c.x - stage.x()) / oldScale, y: (c.y - stage.y()) / oldScale };
    stage.scale({ x: clamped, y: clamped });
    stage.position({ x: c.x - wp.x * clamped, y: c.y - wp.y * clamped });
    scheduleViewRedraw();
    updateZoomLabel();
    repositionConnPanel();
  }

  // Панорама колесом/тачпадом с гашением «залипания оси»: ОС во время инерции
  // продолжает слать дельту по оси броска, и новый перпендикулярный жест тонет
  // в ней. Следим за сглаженным направлением недавнего потока; если он был явно
  // по одной оси, а пришёл импульс по другой — гасим остаточную (инерционную)
  // ось, чтобы новое направление сработало сразу.
  let wheelLastT = 0, wheelDxAvg = 0, wheelDyAvg = 0;
  function wheelPan(dx, dy) {
    const now = (window.performance && performance.now) ? performance.now() : Date.now();
    if (now - wheelLastT > 150) { wheelDxAvg = 0; wheelDyAvg = 0; } // пауза → новый жест
    wheelLastT = now;
    const odx = dx, ody = dy; // исходные дельты — для «памяти» направления оси
    const wasH = Math.abs(wheelDxAvg) > Math.abs(wheelDyAvg) * 1.5;
    const wasV = Math.abs(wheelDyAvg) > Math.abs(wheelDxAvg) * 1.5;
    // Гасим инерционную ось, только когда новый импульс ЯВНО перпендикулярен
    // (×1.2) — чтобы не мешать намеренной диагонали.
    if (wasH && Math.abs(dy) > Math.abs(dx) * 1.2) dx *= 0.2;
    else if (wasV && Math.abs(dx) > Math.abs(dy) * 1.2) dy *= 0.2;
    // Среднее считаем по ИСХОДНЫМ дельтам и сглаживаем медленнее (0.7/0.3),
    // чтобы «память оси» держалась во время устойчивой инерции.
    wheelDxAvg = wheelDxAvg * 0.7 + odx * 0.3;
    wheelDyAvg = wheelDyAvg * 0.7 + ody * 0.3;
    stage.position({ x: stage.x() - dx, y: stage.y() - dy });
    scheduleViewRedraw();
  }

  // Жесты тачпада/колеса:
  //  • щипок (пальцы разъезжаются) → браузер шлёт wheel с ctrlKey=true → зум;
  //  • два пальца параллельно (или колесо мыши) → обычный wheel → панорама.
  // Панорама/зум доски колесом. center — экранная точка (отн. контейнера сцены).
  // Колесо: приближать или двигать. Выбор личный (мышь у всех разная), поэтому
  // храним в браузере у себя, а не в доске — иначе один участник менял бы
  // поведение другому.
  const WHEEL_STORE = 'board_wheel_zoom_v1';
  let wheelZoom = true;
  try { const v = localStorage.getItem(WHEEL_STORE); if (v !== null) wheelZoom = (v === '1'); } catch (e) {}
  function setWheelZoom(on) {
    wheelZoom = !!on;
    try { localStorage.setItem(WHEEL_STORE, wheelZoom ? '1' : '0'); } catch (e) {}
    const c = document.getElementById('wheel-zoom'); if (c) c.checked = wheelZoom;
    boardHint(wheelZoom ? 'Колесо и два пальца приближают. Щипок на тачпаде — тоже'
                        : 'Колесо и два пальца двигают доску; щипок на тачпаде приближает');
  }
  // Значит ли этот жест «приблизить». Щипок на тачпаде браузер шлёт как колесо
  // с ctrlKey (своего события для щипка нет), и это ВСЕГДА приближение — жест
  // единый во всех программах. Настройка ниже про мышь, а у мыши щипка нет.
  //
  // Прежде здесь стояло «wheelZoom !== ev.ctrlKey», и при включённой настройке
  // выходило наоборот задуманного: прокрутка приближала, а щипок двигал доску.
  // Тачпад или мышь. Судим по самому событию и НЕ запоминаем: ошибка
  // распознавания тогда стоит один жест, а не запирает ввод намертво — как
  // это вышло когда-то с распознаванием пера.
  //
  // Колесо мыши даёт крупные ступени (обычно 100 или 120) строго по вертикали.
  // Тачпад — мелкие приращения, часто дробные, и почти всегда с горизонтальной
  // составляющей, потому что пальцы едут не идеально прямо.
  function looksLikeTrackpad(ev) {
    if (ev.deltaMode !== 0) return false;          // строки/страницы — это колесо
    if (ev.deltaX) return true;                    // мышь по горизонтали не умеет
    const dy = Math.abs(ev.deltaY);
    if (dy === 0) return false;
    return dy < 50 || dy % 1 !== 0;                // мелко или дробно — палец
  }
  function wheelMeansZoom(ev) {
    if (ev.ctrlKey) return true;                   // щипок — всегда приближение
    // Два пальца по тачпаду — это ПРОКРУТКА, и она двигает доску независимо от
    // настройки: настройка про колесо мыши, а у тачпада колеса нет.
    if (looksLikeTrackpad(ev)) return false;
    return wheelZoom;
  }
  function boardWheel(ev, center) {
    if (wheelMeansZoom(ev)) {
      const factor = Math.min(1.15, Math.max(0.85, Math.exp(-ev.deltaY * 0.01)));
      zoomTo(stage.scaleX() * factor, center);
    } else {
      let dx = ev.deltaX, dy = ev.deltaY;
      if (ev.deltaMode === 1) { dx *= 16; dy *= 16; }          // строки → ~px
      else if (ev.deltaMode === 2) { dx *= stage.width(); dy *= stage.height(); } // страницы
      wheelPan(dx, dy);
    }
  }
  function pointerInStage(ev) {
    const r = stageEl.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top };
  }

  stage.on('wheel', (e) => {
    const ev = e.evt;
    ev.preventDefault();
    // Колесо приближает ДОСКУ — и над пустым местом, и над матокном. Плоскость
    // самого окна зумится, только когда окно ВЫБРАНО: пока его не тронули, оно
    // ведёт себя как обычный объект на доске, и над ним можно спокойно летать.
    // Ctrl — отходной путь: с ним колесо работает наоборот, как настроено в меню.
    const wpz = stage.getRelativePointerPosition();
    const fz = wpz && frameAtWorld(wpz.x, wpz.y, true);
    // Внутри выбранного окна приближаем его плоскость — тем же жестом, каким
    // приближают доску снаружи, иначе щипок над окном вёл бы себя иначе, чем
    // прокрутка над ним же.
    if (fz && activeFrameId === fz.id && wheelMeansZoom(ev)) { frameZoomAt(fz, wpz, ev.deltaY); return; }
    boardWheel(ev, stage.getPointerPosition());
  });

  // Виджеты и аплеты ГеоГебры — DOM поверх холста; над ними колесо перехватывал
  // браузер, и доска «застывала». Перенаправляем колесо на панораму/зум доски
  // (клики по виджету при этом работают). Координату курсора берём из события.
  function forwardWheel(ev) { ev.preventDefault(); boardWheel(ev, pointerInStage(ev)); }
  // Щипок над ПАНЕЛЯМИ. Над холстом его ловит сцена, а над тулбаром и верхней
  // плашкой — никто, и браузер масштабировал сам интерфейс. Ловим на документе
  // в фазе перехвата и только жест с ctrlKey: простое колесо панелям нужно,
  // они прокручиваются им.
  document.addEventListener('wheel', (ev) => {
    if (!ev.ctrlKey) return;                       // обычная прокрутка — не наше дело
    if (stageEl && stageEl.contains(ev.target)) return;  // холст обслуживает сцена
    ev.preventDefault();
    // Указатель над панелью, а не над доской: приближаем к середине видимой
    // области — тянуть доску к тулбару было бы странно.
    boardWheel(ev, { x: stage.width() / 2, y: stage.height() / 2 });
  }, { passive: false, capture: true });

  if (widgetLayerEl) widgetLayerEl.addEventListener('wheel', forwardWheel, { passive: false });
  // ggb-layer берём напрямую: его const объявлен ниже по файлу (избегаем TDZ).
  const _ggbLayer = document.getElementById('ggb-layer');
  if (_ggbLayer) _ggbLayer.addEventListener('wheel', forwardWheel, { passive: false });

  (function wireWheelZoom() {
    const c = document.getElementById('wheel-zoom');
    if (!c) return;
    c.checked = wheelZoom;
    c.addEventListener('change', () => setWheelZoom(c.checked));
  })();

  if (zoomInput) {
    document.getElementById('zoom-in').addEventListener('click', () => zoomTo(stage.scaleX() * 1.2));
    document.getElementById('zoom-out').addEventListener('click', () => zoomTo(stage.scaleX() / 1.2));
    zoomInput.addEventListener('focus', () => zoomInput.select());
    zoomInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); zoomInput.blur(); }
    });
    zoomInput.addEventListener('blur', () => {
      const v = parseFloat(String(zoomInput.value).replace(/[^\d.]/g, ''));
      if (isFinite(v) && v > 0) zoomTo(v / 100);
      zoomInput.value = Math.round(stage.scaleX() * 100) + '%';
    });
  }

  stage.on('dragmove', () => { redrawGrid(); repositionCursors(); repositionConnPanel(); });

  // ── Панель инструментов ───────────────────────────────────────────────
  const toolButtons = document.querySelectorAll('#board-toolbar .tool[data-tool]');
  // Фокус после щелчка по инструменту остаётся на кнопке внутри тулбара, а он
  // прокручиваемый — и стрелки начинали листать его вместо панорамы доски.
  // Снимаем фокус ТОЛЬКО когда он внутри панели: в текстовом редакторе и полях
  // ввода он нужен, и трогать его там нельзя.
  function releaseToolbarFocus() {
    const a = document.activeElement;
    if (a && a.closest && a.closest('#board-toolbar') && a.blur) a.blur();
  }

  function setTool(name) {
    releaseToolbarFocus();
    if (viewOnly) name = 'select'; // «только просмотр» — без инструментов
    // Любой инструмент выводит из перемещения доски. Раньше это делал только
    // обработчик кнопок панели, а кнопка ГРУППЫ (под ней карандаш и прочие)
    // зовёт setTool напрямую — режим оставался включённым, и рисовать было
    // нельзя. Флаг гасит обратный вызов: setPanMode(false) сам зовёт setTool.
    if (panMode && !_panExiting) { _panExiting = true; setPanMode(false); _panExiting = false; }
    tool = name;
    pendingPicks = []; pickFrame = null; pickRefLine = null; pickCurve1 = null; // сбрасываем незавершённое построение
    if (typeof clearPolyPicks === 'function' && name !== 'polygon') clearPolyPicks(); // отменяем недорисованный многоугольник
    if (name !== 'midpoint') midPicks = [];
    if (!MEASURE_PICKS[name]) measurePicks = [];
    if (name !== 'angle_deg') angleDegPicks = [];
    if (name !== 'vector') vectorPicks = [];
    if (name !== 'farea') areaPicks = [];
    if (name !== 'fintersect') fintPicks = [];
    if (name !== 'regionsys') { regionParts = []; regionFrame = null; }
    if (name !== 'macro') macroPickPts = [];
    if (name !== 'macro_record') macroMode = null;
    if (!MARK_PICKS[name]) markPicks = [];
    if (name !== 'laser') laserDrawing = false;
    if (!isEraser(name)) eraserActive = false;
    if (name !== 'lasso') { lassoActive = false; if (lassoLine) lassoLine.visible(false); }
    toolButtons.forEach((b) => b.classList.toggle('active', b.dataset.tool === name));
    // Табуляция должна приводить к тому инструменту, которым работают сейчас.
    if (typeof обновитьВходВПанель === 'function') обновитьВходВПанель();
    // Рисующие инструменты пропускают нажатие сквозь текст и виджеты на холст.
    // Инструменты установки текста сюда НЕ входят: там щелчок по существующему
    // блоку должен попадать в него, а не создавать новый блок поверх.
    document.body.classList.toggle('board-draw',
      name !== 'select' && name !== 'text' && name !== 'text_plain' && name !== 'latex');
    // В режиме выделения перетаскивание по пустому месту рисует рамку выделения,
    // а не панорамирует, поэтому stage.draggable выключен везде. Панорама — на
    // стрелках и колесе (зум).
    stage.draggable(false);
    stageEl.style.cursor =
      (name === 'select') ? 'default' : (name === 'latex' || name === 'text' || name === 'text_plain') ? 'text' : 'crosshair';
    nodes.forEach((node) => {
      const e = elements.get(node.id());
      node.draggable(name === 'select' && !viewOnly && (!e || (e.type !== 'frame' && !isPointBound(e) && !e.data.locked)));
    });
    // При уходе из select снимаем выделение, но АКТИВНОЕ окно сохраняем —
    // чтобы можно было рисовать геометрию «внутри» него.
    // Инструменты преобразований работают по выделению как по ИСТОЧНИКАМ и позволяют
    // добирать объекты кликами — поэтому выделение НЕ сбрасываем.
    const keepFrame = activeFrameId;
    if (name !== 'select' && !XFORM_SPEC[name]) { clearSelection(); activeFrameId = keepFrame; }
    if (XFORM_SPEC[name]) startXformTool();
    updateFuncEditor();
    if (typeof updateEraserPanel === 'function') updateEraserPanel();
    if (typeof syncMobileFab === 'function') syncMobileFab();
  }

  // ── Якоря и соединительные стрелки ─────────────────────────────────────
  // У блочных объектов по краям четыре точки. Потянул от точки — тянется
  // стрелка; отпустил на другом объекте — она к нему привязалась и дальше
  // следует за обоими концами при перемещении.
  //
  // Кому якорей НЕ даём и почему:
  //   • карандашу и маркеру — форма произвольная, якоря по прямоугольной рамке
  //     повисли бы в пустоте рядом с закорючкой;
  //   • всей геометрии по точкам (точки, отрезки, прямые, окружности,
  //     многоугольники, углы, векторы, засечки, измерения) — соединительная
  //     стрелка не входит в язык чертежа, а якоря начали бы перехватывать
  //     клики вместо точек, которые на чертеже стоят плотно;
  //   • бесконечным построениям — у прямой нет рамки;
  //   • графикам и областям — они живут внутри матокна и обрезаются им;
  //   • матокну — у него своя панорама, зум и шапка, якоря ловили бы жесты;
  //   • самим линиям и стрелкам — стрелка к стрелке даёт кольцо ссылок.
  const ANCHOR_TYPES = {
    rect: 1, ellipse: 1, shape: 1, image: 1, pdf: 1, latex: 1, text: 1, textbox: 1,
    sticky: 1, card: 1, table: 1, kanban: 1, timer: 1, wheel: 1, slider: 1,
    embed: 1, poll: 1, geogebra: 1, venn: 1, screen: 1,
  };
  const ANCHOR_SIDES = ['top', 'right', 'bottom', 'left'];
  function hasAnchors(el) { return !!(el && ANCHOR_TYPES[el.type] && !(el.data && el.data.hidden)); }

  // Прямоугольник объекта в мировых координатах — одинаково для холста и DOM.
  function objBox(id) {
    const el = elements.get(id);
    if (!el) return null;
    const w = widgetItems.get(id);
    if (w) {
      const ww = w.wrapper.offsetWidth || 0, hh = w.wrapper.offsetHeight || 0;
      if (!ww && !hh) return null;
      return { x: el.data.x || 0, y: el.data.y || 0, width: ww, height: hh };
    }
    const g = ggbItems.get(id);
    if (g) return { x: el.data.x || 0, y: el.data.y || 0, width: el.data.width || 0, height: el.data.height || 0 };
    const n = nodes.get(id);
    if (!n) return null;
    const b = n.getClientRect({ relativeTo: layer });
    return (b.width || b.height) ? b : null;
  }
  function anchorPoint(box, side) {
    if (side === 'top') return { x: box.x + box.width / 2, y: box.y };
    if (side === 'bottom') return { x: box.x + box.width / 2, y: box.y + box.height };
    if (side === 'left') return { x: box.x, y: box.y + box.height / 2 };
    return { x: box.x + box.width, y: box.y + box.height / 2 };
  }

  // ── Пересчёт привязанных стрелок ───────────────────────────────────────
  // Привязанная стрелка — обычная стрелка, у которой концы каждый раз
  // вычисляются заново. Так весь прежний рендер (кривые, уступы, наконечники)
  // работает без изменений.
  function connBoundEnd(bind) {
    if (!bind || !bind.id) return null;
    const box = objBox(bind.id);
    if (!box) return null;
    return anchorPoint(box, bind.side || 'right');
  }
  function recomputeConnectors() {
    let touched = false;
    elements.forEach((el) => {
      const d = el.data;
      if (!d || (el.type !== 'line' && el.type !== 'arrow')) return;
      if (!d.from && !d.to) return;
      const e = connEnds(d);
      const A = connBoundEnd(d.from) || { x: (d.x || 0) + e.A.x, y: (d.y || 0) + e.A.y };
      const B = connBoundEnd(d.to) || { x: (d.x || 0) + e.B.x, y: (d.y || 0) + e.B.y };
      const nx = A.x, ny = A.y;
      const pts = [0, 0, B.x - A.x, B.y - A.y];
      const same = (d.x === nx && d.y === ny && (d.points || []).join() === pts.join());
      if (same) return;
      d.x = nx; d.y = ny; d.points = pts;
      const n = nodes.get(el.id);
      if (n) n.position({ x: nx, y: ny });
      touched = true;
    });
    if (touched) layer.batchDraw();
  }
  // Разослать соседям стрелки, привязанные к этим объектам (после перемещения).
  function syncConnectorsOf(ids) {
    const set = new Set(ids);
    elements.forEach((el) => {
      const d = el.data;
      if (!d || (el.type !== 'line' && el.type !== 'arrow')) return;
      if ((d.from && set.has(d.from.id)) || (d.to && set.has(d.to.id))) {
        send({ action: 'element_update', element: stripPrivate(el) });
      }
    });
  }

  // ── Точки на объекте ───────────────────────────────────────────────────
  const anchorLayerEl = document.getElementById('anchor-layer');
  let anchorEls = null, anchorForId = null, anchorDrag = null;

  function ensureAnchorEls() {
    if (anchorEls || !anchorLayerEl) return anchorEls;
    anchorEls = {};
    ANCHOR_SIDES.forEach((side) => {
      const a = document.createElement('div');
      a.className = 'anch';
      a.dataset.side = side;
      a.title = 'Потяните, чтобы соединить стрелкой';
      a.addEventListener('pointerdown', (e) => startAnchorDrag(e, side));
      anchorLayerEl.appendChild(a);
      anchorEls[side] = a;
    });
    return anchorEls;
  }
  function hideAnchors() {
    anchorForId = null;
    if (anchorEls) ANCHOR_SIDES.forEach((s) => { anchorEls[s].style.display = 'none'; });
  }
  // Показываем якоря у ОДНОГО выделенного блочного объекта. На наведение не
  // вешаем: пришлось бы опрашивать холст на каждом движении мыши, а выигрыш
  // невелик — объект всё равно почти всегда сначала выделяют.
  function renderAnchors() {
    if (!anchorLayerEl) return;
    // Признак — само выделение, а не активный инструмент: по объекту можно
    // щёлкнуть и с карандашом в руках, и якоря должны появиться.
    if (viewOnly || panMode || selected.size !== 1) { hideAnchors(); return; }
    const id = Array.from(selected)[0];
    const el = elements.get(id);
    if (!hasAnchors(el) || (el.data && el.data.locked)) { hideAnchors(); return; }
    const box = objBox(id);
    if (!box) { hideAnchors(); return; }
    ensureAnchorEls();
    anchorForId = id;
    const s = stage.scaleX();
    ANCHOR_SIDES.forEach((side) => {
      const p = anchorPoint(box, side);
      const a = anchorEls[side];
      a.style.display = 'block';
      a.style.left = (p.x * s + stage.x()) + 'px';
      a.style.top = (p.y * s + stage.y()) + 'px';
    });
  }

  // Якоря — такой же наложенный слой, что и угловые ручки размера, и обновляться
  // должны в тех же случаях. Раньше их двигали в трёх местах из четырнадцати,
  // поэтому при изменении размера объекта они оставались на старом месте.
  // Связываем напрямую: где двигаются ручки — там же двигаются и якоря. Новые
  // места, откуда позовут positionHandles, подхватятся сами.
  function positionHandles() { positionHandlesCore(); renderAnchors(); }

  // Куда целимся: объект под курсором и его ближайшая сторона.
  function anchorTargetAt(wx, wy, excludeId) {
    let best = null;
    elements.forEach((el) => {
      if (el.id === excludeId || !hasAnchors(el)) return;
      const box = objBox(el.id);
      if (!box) return;
      if (wx < box.x || wx > box.x + box.width || wy < box.y || wy > box.y + box.height) return;
      // Ближайшая сторона — по наименьшему расстоянию до края.
      const dl = wx - box.x, dr = box.x + box.width - wx;
      const dt = wy - box.y, db = box.y + box.height - wy;
      const m = Math.min(dl, dr, dt, db);
      const side = (m === dt) ? 'top' : (m === db) ? 'bottom' : (m === dl) ? 'left' : 'right';
      // Мельче — значит сверху: берём самый маленький подходящий объект.
      const area = box.width * box.height;
      if (!best || area < best.area) best = { id: el.id, side: side, area: area };
    });
    return best ? { id: best.id, side: best.side } : null;
  }

  function startAnchorDrag(e, side) {
    if (!anchorForId || viewOnly) return;
    e.preventDefault(); e.stopPropagation();
    const box = objBox(anchorForId);
    if (!box) return;
    const A = anchorPoint(box, side);
    const el = {
      id: uuid(), type: 'arrow', z: 0,
      data: {
        stroke: strokeColor, strokeWidth: Math.max(1.5, strokeWidth),
        x: A.x, y: A.y, points: [0, 0, 0, 0],
        startCap: 'none', endCap: 'arrow',
        from: { id: anchorForId, side: side },
      },
    };
    anchorDrag = { el: el, pid: e.pointerId, target: null, moved: false };
    upsertNode(el);
    try { e.target.setPointerCapture(e.pointerId); } catch (err) {}
    document.body.classList.add('anchor-dragging');
  }
  function moveAnchorDrag(e) {
    if (!anchorDrag) return;
    const r = stageEl.getBoundingClientRect();
    const s = stage.scaleX();
    const wx = (e.clientX - r.left - stage.x()) / s;
    const wy = (e.clientY - r.top - stage.y()) / s;
    anchorDrag.moved = true;
    const d = anchorDrag.el.data;
    const tgt = anchorTargetAt(wx, wy, d.from.id);
    anchorDrag.target = tgt;
    let B = { x: wx, y: wy };
    if (tgt) {
      const tb = objBox(tgt.id);
      if (tb) B = anchorPoint(tb, tgt.side);
    }
    d.points = [0, 0, B.x - d.x, B.y - d.y];
    upsertNode(anchorDrag.el);
    highlightAnchorTarget(tgt);
  }
  function endAnchorDrag() {
    if (!anchorDrag) return;
    const st = anchorDrag;
    anchorDrag = null;
    document.body.classList.remove('anchor-dragging');
    highlightAnchorTarget(null);
    const d = st.el.data;
    const len = Math.hypot(d.points[2] - d.points[0], d.points[3] - d.points[1]);
    if (!st.moved || len < 8) {          // просто щёлкнули по якорю — стрелки не надо
      removeNode(st.el.id);
      return;
    }
    if (st.target) d.to = { id: st.target.id, side: st.target.side };
    recomputeConnectors();
    send({ action: 'element_add', element: stripPrivate(st.el) });
    histAdd(stripPrivate(st.el));
    selectOnly(st.el.id);
  }
  function highlightAnchorTarget(tgt) {
    document.querySelectorAll('.anch-target').forEach((e) => e.classList.remove('anch-target'));
    if (!tgt) { if (anchorHalo) anchorHalo.style.display = 'none'; return; }
    const box = objBox(tgt.id);
    if (!box) return;
    if (!anchorHalo) {
      anchorHalo = document.createElement('div');
      anchorHalo.className = 'anch-halo';
      anchorLayerEl.appendChild(anchorHalo);
    }
    const s = stage.scaleX();
    anchorHalo.style.display = 'block';
    anchorHalo.style.left = (box.x * s + stage.x()) + 'px';
    anchorHalo.style.top = (box.y * s + stage.y()) + 'px';
    anchorHalo.style.width = (box.width * s) + 'px';
    anchorHalo.style.height = (box.height * s) + 'px';
  }
  let anchorHalo = null;

  document.addEventListener('pointermove', (e) => { if (anchorDrag && e.pointerId === anchorDrag.pid) moveAnchorDrag(e); }, true);
  document.addEventListener('pointerup', (e) => { if (anchorDrag && e.pointerId === anchorDrag.pid) endAnchorDrag(); }, true);
  document.addEventListener('pointercancel', () => { if (anchorDrag) { removeNode(anchorDrag.el.id); anchorDrag = null; document.body.classList.remove('anchor-dragging'); highlightAnchorTarget(null); } }, true);

  // ── Режим перемещения доски ────────────────────────────────────────────
  // Мышью доску подвинуть было нельзя вовсе: панорама жила только на стрелках
  // и колесе, а перетаскивание по пустому месту рисовало рамку выделения.
  //
  // Включается повторным нажатием на «Выделение»: первый клик выбирает
  // инструмент, второй — переводит в перемещение. Кнопка гаснет, курсор
  // становится рукой. Выключается так же, сменой инструмента или Esc.
  //
  // Мышь и перо ведём сами (перехватываем нажатие раньше всех остальных
  // обработчиков), а касания отдаём той же системе жестов, что уже умеет
  // панораму и щипок, — чтобы два пальца по-прежнему меняли масштаб.
  let panMode = false, panDrag = null;
  let _panExiting = false;   // идёт выход из перемещения — не зацикливать setTool
  let panDbl = null;         // прошлое нажатие в перемещении — ловим двойной щелчок

  // Панели поверх доски: нажатие на них — не перемещение.
  const PAN_SKIP = '#board-toolbar, #board-topbar, #board-head, #board-menu, #history-panel,'
    + ' #people-panel, #voice-panel, .tool-flyout, .settings-panel, .conn-panel, #zoom-control,'
    + ' #settings-btn, #settings-menu, #color-palette, #latex-editor, #text-editor, #func-editor,'
    + ' #tbox-bar, #tbl-bar, #venn-bar, #dp-pop, #eraser-panel, #storyboard, #pdf-controls,'
    + ' #frame-exit-btn, #mobile-sheet, #mobile-fab, #mobile-backdrop, #embed-dialog,'
    + ' #board-pw-dialog, #pdf-export-dialog';

  function setPanMode(on) {
    panMode = !!on;
    document.body.classList.toggle('board-pan', panMode);
    const sel = document.querySelector('#board-toolbar .tool[data-tool="select"]');
    if (sel) {
      // Синей подсветки нет — вместо неё отдельный вид «рука», иначе не понять,
      // почему клики вдруг перестали выделять.
      sel.classList.toggle('active', !panMode && tool === 'select');
      sel.classList.toggle('panning', panMode);
    }
    if (panMode) {
      // В перемещении объекты не таскаем и якоря прячем — они ловили бы нажатия.
      nodes.forEach((n) => n.draggable(false));
      clearSelection();
    } else if (!_panExiting) {
      setTool(tool);   // вернуть обычное поведение выбранного инструмента
    }
    renderAnchors();
    stageEl.style.cursor = panMode ? 'grab' : ((tool === 'select') ? 'default' : 'crosshair');
    boardHint(panMode ? 'Перемещение доски: тяните мышью, пальцем или пером'
                      : 'Обычный режим');
  }

  function panBoardBy(dx, dy) {
    stage.position({ x: panDrag.sx + dx, y: panDrag.sy + dy });
    scheduleViewRedraw();   // сетка, курсоры, якоря и трансляция вида ведомым
  }

  // Мышь и перо: перехватываем на самом раннем этапе, чтобы объекты под
  // курсором не начали выделяться или двигаться.
  document.addEventListener('pointerdown', (e) => {
    if (!panMode || e.pointerType === 'touch') return;
    if (e.button != null && e.button > 0) return;
    if (e.target.closest && e.target.closest(PAN_SKIP)) return;
    const r = stageEl.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
    // Двойной щелчок возвращает выделение и берёт объект под курсором: не надо
    // искать кнопку, чтобы продолжить работу с тем, на что смотришь. Считаем
    // нажатия сами — перемещение перехватывает их раньше Konva, и её
    // собственный dblclick сюда не доходит.
    const _t = Date.now();
    if (panDbl && _t - panDbl.t < 350
      && Math.abs(e.clientX - panDbl.x) < 5 && Math.abs(e.clientY - panDbl.y) < 5) {
      panDbl = null; panDrag = null;
      document.body.classList.remove('panning');
      setPanMode(false);
      // Ищем объект двумя способами: геометрией (точки, окружности, построения)
      // и обычным попаданием Konva. Одной геометрии мало — карандашные штрихи
      // и картинки она не знает, и двойной щелчок по ним ничего не выделял.
      const wp = worldFromClient(e.clientX, e.clientY);
      const g = wp && pickObjectAtWorld(wp);
      let целевой = g ? g.id : null;
      if (!целевой) {
        const rr = stage.content.getBoundingClientRect();
        let t = stage.getIntersection({ x: e.clientX - rr.left, y: e.clientY - rr.top });
        while (t && t !== stage && !(t.id && nodes.has(t.id()))) t = t.getParent();
        if (t && t.id && nodes.has(t.id())) целевой = t.id();
      }
      if (целевой) selectOnly(целевой);
      e.preventDefault(); e.stopPropagation();
      return;
    }
    panDbl = { t: _t, x: e.clientX, y: e.clientY };
    panDrag = { id: e.pointerId, x: e.clientX, y: e.clientY, sx: stage.x(), sy: stage.y() };
    document.body.classList.add('panning');
    e.preventDefault(); e.stopPropagation();
  }, true);
  document.addEventListener('pointermove', (e) => {
    if (!panDrag || e.pointerId !== panDrag.id) return;
    if (!(e.buttons & 1)) { endPanDrag(e); return; }   // отпустили вне окна
    e.preventDefault(); e.stopPropagation();
    panBoardBy(e.clientX - panDrag.x, e.clientY - panDrag.y);
  }, true);
  function endPanDrag(e) {
    if (!panDrag || (e && e.pointerId !== panDrag.id)) return;
    panDrag = null;
    document.body.classList.remove('panning');
  }
  document.addEventListener('pointerup', endPanDrag, true);
  document.addEventListener('pointercancel', endPanDrag, true);

  // ── Перемещение доски правой кнопкой ──────────────────────────────────
  // Инструмент в руке, а холст всё равно надо подвинуть. Раньше для этого
  // приходилось бросать инструмент, брать «руку» и возвращаться обратно.
  // Теперь правая кнопка делает и то и другое: потянул — доска поехала,
  // отпустил на месте — вышло меню. Порог отделяет одно от другого, иначе
  // дрожание руки при вызове меню сдвигало бы доску.
  const RMB_MOVE_PX = 5;
  let rmbPan = null;      // идущее перетаскивание правой кнопкой
  let rmbMoved = false;   // прошлое нажатие правой оказалось перетаскиванием
  let rmbMovedAt = 0;     // когда именно — чтобы признак не жил вечно
  let rmbMenu = null;     // отложенный показ меню (macOS шлёт его на нажатии)

  document.addEventListener('pointerdown', (e) => {
    if (e.button !== 2 || e.pointerType === 'touch') return;
    rmbMoved = false; rmbMenu = null;
    if (e.buttons & 1) return;               // левая уже зажата — идёт рисование
    if (e.target.closest && e.target.closest(PAN_SKIP)) return;
    const r = stageEl.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
    // Действие по умолчанию НЕ отменяем: иначе браузер не пришлёт contextmenu
    // и меню пропадёт совсем. Достаточно не пустить событие дальше.
    // x0/y0 — откуда нажали (для порога), x/y — предыдущая точка (для шага).
    rmbPan = { id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY };
    e.stopPropagation();
  }, true);

  // Виджеты (тексты, стикеры, таблицы, формулы) — это HTML поверх холста, и
  // их перетаскивание висит на mousedown без проверки кнопки. Пока доску тянут
  // правой, событие до них не доводим, иначе объект поедет вместе с доской.
  document.addEventListener('mousedown', (e) => {
    if (rmbPan && e.button === 2) e.stopPropagation();
  }, true);

  document.addEventListener('pointermove', (e) => {
    if (!rmbPan || e.pointerId !== rmbPan.id) return;
    // Кнопку отпустили за пределами окна — pointerup сюда не пришёл. Иначе
    // доска ехала бы за курсором без нажатой кнопки.
    if (!(e.buttons & 2)) { endRmbPan(e); return; }
    if (!rmbMoved) {
      if (Math.abs(e.clientX - rmbPan.x0) < RMB_MOVE_PX
        && Math.abs(e.clientY - rmbPan.y0) < RMB_MOVE_PX) return;
      rmbMoved = true; rmbMovedAt = Date.now(); rmbMenu = null;
      hideCtxMenu();                         // macOS успевает открыть меню на нажатии
      document.body.classList.add('rmb-pan');
    }
    e.preventDefault(); e.stopPropagation();
    // Двигаем ШАГАМИ от прошлой точки, а не от точки нажатия. Иначе колесо,
    // покрученное посреди перетаскивания, откатывалось бы назад: зум меняет и
    // положение сцены, а абсолютный пересчёт затирал бы его.
    const dx = e.clientX - rmbPan.x, dy = e.clientY - rmbPan.y;
    rmbPan.x = e.clientX; rmbPan.y = e.clientY;
    stage.position({ x: stage.x() + dx, y: stage.y() + dy });
    scheduleViewRedraw();                    // сетка, курсоры, якоря и вид ведомым
  }, true);

  function endRmbPan(e) {
    if (!rmbPan || (e && e.pointerId !== rmbPan.id)) return;
    rmbPan = null;
    document.body.classList.remove('rmb-pan');
    // Меню пришло на нажатии и было отложено: не потянули — показываем сейчас.
    if (!rmbMoved && rmbMenu) { const показать = rmbMenu; rmbMenu = null; показать(); }
  }
  document.addEventListener('pointerup', endRmbPan, true);
  document.addEventListener('pointercancel', endRmbPan, true);
  // Alt+Tab с зажатой кнопкой: отпускания мы уже не увидим.
  window.addEventListener('blur', () => { endRmbPan(null); endPanDrag(null); });

  // Потянули правой — меню не показываем: это было перемещение, а не вызов
  // меню. Ловим на перехвате, чтобы событие не дошло ни до сцены, ни до
  // виджетов, у которых свои обработчики.
  document.addEventListener('contextmenu', (e) => {
    if (!rmbMoved) return;
    // Гасим ТОЛЬКО меню от самой правой кнопки и только сразу после жеста.
    // Там, где браузер шлёт contextmenu на нажатии (macOS, Firefox), второго
    // события за жест не будет и признак остаётся поднятым до следующего
    // правого клика. Меню, вызванное иначе — клавишей Menu, Shift+F10,
    // Ctrl+кликом на маке, долгим касанием, — приходит с кодом кнопки 0, и
    // глушить его нельзя: человек остался бы вообще без меню.
    if (e.button !== 2 || Date.now() - rmbMovedAt > 1500) return;
    rmbMoved = false;
    e.preventDefault(); e.stopPropagation();
  }, true);

  // ── Выделение и удаление ───────────────────────────────────────────────
  // Выделение в режиме select: клик по объекту — выбрать, Shift+клик — добавить,
  // клик по пустому месту — снять. Рамку рисует Konva.Transformer (без ручек
  // ресайза — только подсветка). Удаление выбранного — Delete / Backspace.
  const selected = new Set();
  // Рамку выделения рисует Konva.Transformer (без ручек — только подсветка).
  const tr = new Konva.Transformer({
    resizeEnabled: false, rotateEnabled: false,
    borderStroke: '#4d7cfe', borderStrokeWidth: 1.5, borderDash: [4, 4], padding: 4,
  });
  layer.add(tr);

  // ── Ресайз/гомотетия собственными угловыми ручками ────────────────────
  // Konva.Transformer в нашей связке не запускал трансформ, поэтому делаем свои
  // ручки на том же надёжном механизме, что перемещение (mousedown→stage mousemove).
  const RESIZABLE = ['rect', 'ellipse', 'circle', 'latex', 'text', 'freehand', 'frame', 'shape', 'image', 'pdf', 'venn'];
  // Габариты объекта для ручек: у окна берём его прямоугольник из данных.
  function elBox(el, node) {
    if (el.type === 'frame') return { x: el.data.x, y: el.data.y, width: el.data.width, height: el.data.height };
    return node.getClientRect({ relativeTo: layer });
  }
  const handlesGroup = new Konva.Group({ visible: false });
  layer.add(handlesGroup);
  const HCORNERS = ['tl', 'tr', 'bl', 'br'];
  HCORNERS.forEach((c) => {
    const h = new Konva.Rect({ name: c, width: 10, height: 10, fill: '#fff', stroke: '#4d7cfe', strokeWidth: 1.5, cornerRadius: 1 });
    h.on('mousedown touchstart', (e) => { e.cancelBubble = true; startResize(c); });
    h.on('mouseenter', () => { stageEl.style.cursor = (c === 'tl' || c === 'br') ? 'nwse-resize' : 'nesw-resize'; });
    h.on('mouseleave', () => { if (tool === 'select') stageEl.style.cursor = 'default'; });
    handlesGroup.add(h);
  });
  // Боковые ручки для ТЕКСТА: тянешь влево/вправо — меняется ширина строки (перенос),
  // высота подстраивается под содержимое. Показываются только у текста (вместо углов).
  const HEDGES = ['ml', 'mr'];
  HEDGES.forEach((c) => {
    const h = new Konva.Rect({ name: c, width: 8, height: 18, fill: '#fff', stroke: '#4d7cfe', strokeWidth: 1.5, cornerRadius: 2, visible: false });
    h.on('mousedown touchstart', (e) => { e.cancelBubble = true; startResize(c); });
    h.on('mouseenter', () => { stageEl.style.cursor = 'ew-resize'; });
    h.on('mouseleave', () => { if (tool === 'select') stageEl.style.cursor = 'default'; });
    handlesGroup.add(h);
  });

  // Ручки линии/стрелки: концы (a,b) + путевые точки кривизны. 'm' — центр, 'l'/'r'
  // — центры левой/правой половин. Все три — точки НА кривой (равноправны, влияют
  // локально и независимо). 'l'/'r' появляются после первого сгиба центральной.
  const connHandles = new Konva.Group({ visible: false });
  layer.add(connHandles);
  const connHandleEls = {};
  const CONN_HANDLES = ['a', 'b', 'm', 'l', 'r'];
  const CONN_SLOT = { m: 'wm', l: 'wl', r: 'wr' };
  const CONN_FRAC = { m: 0.5, l: 0.25, r: 0.75 };
  function connSelectedEl() { if (selected.size !== 1) return null; const el = elements.get(Array.from(selected)[0]); return (el && (el.type === 'line' || el.type === 'arrow')) ? el : null; }
  // Где сидит ручка (относит.): a=A, b=B; m/l/r — либо своя путевая точка, либо
  // (пока не задана) точка на текущей кривой по доле длины.
  function connHandleRel(d, k) {
    const e = connEnds(d);
    if (k === 'a') return e.A;
    if (k === 'b') return e.B;
    if (k === 'm' && d.elbow) return elbowMidHandle(d); // у уступа 'm' — ручка излома
    const slot = d[CONN_SLOT[k]];
    if (slot) return { x: slot[0], y: slot[1] };
    return connPointAtFraction(d, CONN_FRAC[k]);
  }
  function positionConnHandlesAt(el, ox, oy, skip) {
    const d = el.data;
    CONN_HANDLES.forEach((k) => { if (k === skip) return; const P = connHandleRel(d, k); connHandleEls[k].position({ x: ox + P.x, y: oy + P.y }); });
  }
  function positionConnHandles(el, skip) { positionConnHandlesAt(el, el.data.x || 0, el.data.y || 0, skip); }
  CONN_HANDLES.forEach((k) => {
    const isEnd = k === 'a' || k === 'b';
    const h = new Konva.Circle({ name: k, radius: 6, fill: isEnd ? '#4d7cfe' : '#fff', stroke: isEnd ? '#fff' : '#4d7cfe', strokeWidth: 2, draggable: true });
    h.on('mouseenter', () => { stageEl.style.cursor = 'pointer'; });
    h.on('mouseleave', () => { if (tool === 'select') stageEl.style.cursor = 'default'; });
    let cBefore = null;
    h.on('dragstart', (e) => { e.cancelBubble = true; const el = connSelectedEl(); cBefore = el ? clone(el) : null; });
    h.on('dragmove', (e) => {
      e.cancelBubble = true;
      const el = connSelectedEl(); if (!el) return;
      const d = el.data, P = { x: h.x() - (d.x || 0), y: h.y() - (d.y || 0) };
      if (k === 'a') { const p = (d.points || [0, 0, 0, 0]).slice(); p[0] = P.x; p[1] = P.y; if (d.divider === 'h') p[1] = p[3]; else if (d.divider === 'v') p[0] = p[2]; d.points = p; }
      else if (k === 'b') { const p = (d.points || [0, 0, 0, 0]).slice(); p[2] = P.x; p[3] = P.y; if (d.divider === 'h') p[3] = p[1]; else if (d.divider === 'v') p[2] = p[0]; d.points = p; }
      else if (k === 'm' && d.elbow) { // сдвиг излома уступа вдоль главной оси
        const en = connEnds(d), dx = en.B.x - en.A.x, dy = en.B.y - en.A.y, cl = (v) => Math.max(0.02, Math.min(0.98, v));
        d.elbowT = (Math.abs(dx) >= Math.abs(dy)) ? cl((P.x - en.A.x) / (dx || 1)) : cl((P.y - en.A.y) / (dy || 1));
      } else { connMigrateCurve(d); d[CONN_SLOT[k]] = [P.x, P.y]; } // путевая точка идёт РОВНО за курсором
      const node = nodes.get(el.id); if (node) node.draw();
      positionConnHandles(el, k); layer.batchDraw(); repositionConnPanel();
    });
    h.on('dragend', (e) => { e.cancelBubble = true; const el = connSelectedEl(); if (el && cBefore) { histUpd(cBefore, el); send({ action: 'element_update', element: el }); } cBefore = null; positionHandles(); });
    connHandles.add(h); connHandleEls[k] = h;
  });

  let resizeState = null;
  const OPP = { tl: 'br', tr: 'bl', bl: 'tr', br: 'tl' };
  function boxCorners(b) {
    return { tl: { x: b.x, y: b.y }, tr: { x: b.x + b.width, y: b.y }, bl: { x: b.x, y: b.y + b.height }, br: { x: b.x + b.width, y: b.y + b.height } };
  }
  function snapshotGeom(el) {
    const d = el.data;
    return { width: d.width, height: d.height, radiusX: d.radiusX, radiusY: d.radiusY, r: d.r, points: (d.points || []).slice() };
  }
  function applyScaledSize(el, node, s, start) {
    const d = el.data;
    if (el.type === 'rect') { d.width = Math.max(1, start.width * s); d.height = Math.max(1, start.height * s); node.width(d.width); node.height(d.height); }
    else if (el.type === 'ellipse') { d.radiusX = Math.max(1, start.radiusX * s); d.radiusY = Math.max(1, start.radiusY * s); node.radiusX(d.radiusX); node.radiusY(d.radiusY); }
    else if (el.type === 'circle') { d.r = Math.max(1, start.r * s); node.radius(d.r); }
    else if (el.type === 'latex' || el.type === 'text') { d.width = Math.max(2, start.width * s); d.height = Math.max(2, start.height * s); node.width(d.width); node.height(d.height); }
    else if (el.type === 'line' || el.type === 'freehand') { d.points = start.points.map((v) => v * s); node.points(d.points); }
    else if (el.type === 'shape') { d.width = Math.max(1, start.width * s); d.height = Math.max(1, start.height * s); }
    else if (el.type === 'venn') { d.width = Math.max(120, start.width * s); d.height = Math.max(90, start.height * s); d._labSig = null; }
    else if (el.type === 'image' || el.type === 'pdf') { d.width = Math.max(8, start.width * s); d.height = Math.max(8, start.height * s); node.width(d.width); node.height(d.height); if (el.type === 'pdf') { node._pdfKey = null; renderPdfInto(node, el); } }
  }
  let _txtRenderAt = 0;
  function scheduleTextRender(el, node) { const now = Date.now(); if (now - _txtRenderAt >= 80) { _txtRenderAt = now; renderTextInto(node, el); } }
  function startResize(corner) {
    const id = Array.from(selected)[0];
    const el = elements.get(id), node = nodes.get(id);
    if (!el || !node) { updateDebug('resize: нет объекта'); return; }
    const b = elBox(el, node);
    // Боковые ручки текста: фиксирован противоположный край (по X).
    let F;
    if (corner === 'ml') F = { x: b.x + b.width, y: b.y };
    else if (corner === 'mr') F = { x: b.x, y: b.y };
    else F = boxCorners(b)[OPP[corner]];
    resizeState = { id, corner, F, w0: Math.max(1, b.width), h0: Math.max(1, b.height), start: snapshotGeom(el), histBefore: clone(el) };
    updateDebug('resize СТАРТ ' + corner);
  }
  function doResize() {
    const el = elements.get(resizeState.id), node = nodes.get(resizeState.id);
    if (!el || !node) return;
    const P = worldPoint();
    if (el.type === 'frame') {
      // Окно: меняем размер прямоугольника (произвольно по осям), масштаб
      // плоскости (unit) и центр не трогаем — видно больше/меньше плоскости.
      const F = resizeState.F;
      // Умные направляющие при ресайзе окна: липнем тянущимся углом к соседям.
      if (!guideRefs) guideRefs = collectGuideRefs([resizeState.id]);
      const R = frameCornerSnap(P, F);
      const w = Math.max(80, Math.abs(R.x - F.x));
      const h = Math.max(60, Math.abs(R.y - F.y));
      el.data.x = Math.min(R.x, F.x); el.data.y = Math.min(R.y, F.y);
      el.data.width = w; el.data.height = h;
      drawGuides(R.marks);
      node.position({ x: el.data.x, y: el.data.y });
      node.clipWidth(w); node.clipHeight(h);
      const bg = node.findOne('.fbg'); if (bg) bg.size({ width: w, height: h });
      const hd = node.findOne('.fheader'); if (hd) hd.width(w);
      const del = node.findOne('.fdel'); if (del) del.x(w - 16);
      recomputeGeometry(); // привязанная геометрия — под новый размер окна
      positionHandles();
      tr.forceUpdate(); // пунктирная рамка следует за новым размером окна
      if (activeFrameId === el.id) updateFuncEditor();
      layer.draw();
      updateDebug('окно ' + Math.round(w) + '×' + Math.round(h));
      return;
    }
    if (el.type === 'text') {
      // Текст: тянем ширину строки (перенос), высота — под содержимое. Правим wrapWidth.
      const F = resizeState.F;
      // Направляющие при растягивании текста. У картинок и фигур они есть
      // давно, а здесь ветка своя (тянут ширину, а не масштаб) — и текст
      // нельзя было подогнать по ширине ни к картинке, ни к соседнему тексту.
      if (!guideRefs) guideRefs = collectGuideRefs([resizeState.id]);
      let px = P.x;
      const th = 7 / stage.scaleX();
      const верх = el.data.y || node.y(), низ = верх + (node.height() || 0);
      let лучший = null;
      guideRefs.forEach((r) => {
        // Одноимённые края, как и при перетаскивании: движущийся край текста
        // равняем на левый, центральный или правый край соседа.
        [r.x, r.x + r.w / 2, r.x + r.w].forEach((v) => {
          const a = Math.abs(v - px);
          if (a <= th && (!лучший || a < лучший.a)) лучший = { a: a, v: v, r: r };
        });
      });
      const линии = [];
      if (лучший) {
        px = лучший.v;
        линии.push({ v: true, at: лучший.v,
                     a: Math.min(верх, лучший.r.y),
                     b: Math.max(низ, лучший.r.y + лучший.r.h) });
      }
      drawGuides(линии);
      const newW = Math.max(40, Math.abs(px - F.x));
      el.data.wrapWidth = newW;
      el.data.x = Math.min(px, F.x); node.x(el.data.x);
      node.width(newW); // мгновенный предпросмотр до асинхронной перерисовки
      scheduleTextRender(el, node); // перерисовать с переносом (троттлинг)
      positionHandles(); tr.forceUpdate(); layer.batchDraw();
      updateDebug('текст ширина ' + Math.round(newW));
      return;
    }
    const sx = Math.abs(P.x - resizeState.F.x) / resizeState.w0;
    const sy = Math.abs(P.y - resizeState.F.y) / resizeState.h0;
    let s = Math.max(0.05, Math.min(40, Math.max(sx, sy))); // равномерно (гомотетия)
    // Умные направляющие: липнем ближним краём угла к соседям (масштаб один на обе оси).
    if (!guideRefs) guideRefs = collectGuideRefs([resizeState.id]);
    const dirX = Math.sign(P.x - resizeState.F.x) || 1, dirY = Math.sign(P.y - resizeState.F.y) || 1;
    const uni = snapUniformScale(resizeState.F, dirX, dirY, resizeState.w0, resizeState.h0, s);
    s = uni.s; drawGuides(uni.lines);
    applyScaledSize(el, node, s, resizeState.start);
    // двигаем узел так, чтобы противоположный (зафиксированный) угол остался на F
    const b = node.getClientRect({ relativeTo: layer });
    const cur = boxCorners(b)[OPP[resizeState.corner]];
    node.x(node.x() + (resizeState.F.x - cur.x));
    node.y(node.y() + (resizeState.F.y - cur.y));
    el.data.x = node.x(); el.data.y = node.y();
    recomputeGeometry();
    positionHandles();
    if (shapeTextItems.has(el.id)) repositionShapeText(el.id); // текст внутри — под новый размер
    tr.forceUpdate();
    layer.batchDraw();
    updateDebug('resize s=' + s.toFixed(2));
  }
  function endResize() {
    if (!resizeState) return;
    const el = elements.get(resizeState.id), node = nodes.get(resizeState.id);
    const hist = resizeState.histBefore, wasText = el && el.type === 'text';
    resizeState = null; // сбрасываем ДО финальной перерисовки, чтобы она отправила update
    clearGuides();
    if (el) {
      if (wasText && node) renderTextInto(node, el); // финальная перерисовка с переносом (сама шлёт update)
      else send({ action: 'element_update', element: el });
      if (hist) histUpd(hist, el);
    }
    updateDebug('resize КОНЕЦ');
  }

  // Версию считает сервер по времени последней правки board.js и передаёт в
  // BOARD_CONFIG.ver — вручную её здесь больше не задают.
  const BOARD_VER = (cfg && cfg.ver) || 'dev';
  (function () { const v = document.getElementById('board-version'); if (v) v.textContent = 'v' + BOARD_VER; })();
  function updateDebug(extra) {
    const el = document.getElementById('board-debug');
    if (!el) return;
    el.textContent = 'v' + BOARD_VER + '  выбрано: ' + selected.size
      + '  ручки: ' + (handlesGroup.visible() ? 'да' : 'нет')
      + (extra ? '  ' + extra : '');
  }

  function positionHandlesCore() {
    const ids = Array.from(selected);
    const el = ids.length === 1 ? elements.get(ids[0]) : null;
    // Линия/стрелка — ручки концов + контроль (вместо рамки-ресайза).
    if (el && (el.type === 'line' || el.type === 'arrow') && tool === 'select' && !(el.data && el.data.locked) && !(el.data && el.data.hidden)) {
      if (handlesGroup.visible()) handlesGroup.hide();
      const r = 6 / stage.scaleX();
      CONN_HANDLES.forEach((k) => { const h = connHandleEls[k]; h.radius(r); h.strokeWidth(2 / stage.scaleX()); });
      // 'm' есть всегда: у прямой — приглашение согнуть, у кривой — центр, у уступа
      // — ручка излома. 'l'/'r' — только у согнутой кривой. У разделителя гибки нет —
      // только концы a/b (двигаются строго по своей оси).
      const dd = el.data, isDiv = !!dd.divider, curved = connIsCurved(dd) && !dd.elbow;
      connHandleEls.m.visible(!isDiv);
      connHandleEls.l.visible(curved && !isDiv);
      connHandleEls.r.visible(curved && !isDiv);
      positionConnHandles(el);
      connHandles.show(); connHandles.moveToTop();
      showConnPanel(el); hideShapePanel();
      layer.draw(); updateDebug(); return;
    }
    hideConnPanel();
    if (connHandles.visible()) connHandles.hide();
    // Панель фигуры — у одиночной фигуры (прямоугольник/эллипс/фигура).
    const shapeEl = (el && SHAPE_TYPES_PANEL.indexOf(el.type) >= 0 && tool === 'select' && !(el.data && el.data.locked) && !(el.data && el.data.hidden)) ? el : null;
    if (shapeEl) showShapePanel(shapeEl); else hideShapePanel();
    // Панель стикера — там же, где решается судьба остальных панелей.
    const stickyEl = stickySelectedEl();
    if (stickyEl) showStickyPanel(stickyEl); else hideStickyPanel();
    // Штрихи карандаша и маркера — своя панель с цветом и толщиной.
    const strokeEls = strokeSelectedEls();
    if (strokeEls.length) showStrokePanel(strokeEls[0]); else hideStrokePanel();
    const node = el && RESIZABLE.includes(el.type) ? nodes.get(ids[0]) : null;
    if (!node) {
      if (handlesGroup.visible()) { handlesGroup.hide(); }
      layer.draw();
      updateDebug();
      return;
    }
    const b = elBox(el, node);
    const sz = 10 / stage.scaleX();
    const isText = el.type === 'text';
    const pts = boxCorners(b);
    const edgePts = { ml: { x: b.x, y: b.y + b.height / 2 }, mr: { x: b.x + b.width, y: b.y + b.height / 2 } };
    // Ручки выносим ЗА рамку объекта. Раньше они стояли центром на углу, и
    // половина ручки лежала поверх содержимого: у картинки и формулы это
    // закрывает угол рисунка, а при точной подгонке размера мешает видеть тот
    // самый край, который подгоняешь.
    //
    // На попадание в размер это не влияет: doResize считает от координат
    // указателя, а не от положения ручки.
    const зазор = 4 / stage.scaleX();
    handlesGroup.getChildren().forEach((h) => {
      const name = h.name(), isEdge = (name === 'ml' || name === 'mr');
      h.visible(isText ? isEdge : !isEdge); // текст — боковые ручки, остальное — угловые
      if (isText !== isEdge) return;
      if (isEdge) {
        const p = edgePts[name], ew = 8 / stage.scaleX(), eh = 20 / stage.scaleX();
        const наружу = (name === 'ml' ? -1 : 1) * (ew / 2 + зазор);
        h.size({ width: ew, height: eh }); h.strokeWidth(1.5 / stage.scaleX());
        h.position({ x: p.x - ew / 2 + наружу, y: p.y - eh / 2 });
      } else {
        const p = pts[name];
        // Угловая ручка уходит по диагонали от центра объекта — то есть
        // строго наружу, в какой бы угол она ни ставилась.
        const зх = (p.x <= b.x + b.width / 2 ? -1 : 1) * (sz / 2 + зазор);
        const зy = (p.y <= b.y + b.height / 2 ? -1 : 1) * (sz / 2 + зазор);
        h.size({ width: sz, height: sz }); h.strokeWidth(1.5 / stage.scaleX());
        h.position({ x: p.x - sz / 2 + зх, y: p.y - sz / 2 + зy });
      }
    });
    handlesGroup.show();
    handlesGroup.moveToTop();
    layer.draw(); // синхронно (rAF может быть не готов) — ручки появляются сразу
    updateDebug();
  }

  // Подсветка выделенных построений/окружностей (у них нет рамки трансформера).
  function refreshConstructionHighlight() {
    elements.forEach((el) => {
      if (!(CONSTRUCT_LINES.indexOf(el.type) >= 0 || el.type === 'circ' || isFilledPoly(el.type))) return;
      const n = nodes.get(el.id); if (!n) return;
      const on = selected.has(el.id);
      n.stroke(on ? '#4d7cfe' : (el.data.color || el.data.stroke || '#1f2937'));
      n.strokeWidth((el.data.strokeWidth || 2) + (on ? 1.5 : 0));
    });
  }
  function refreshTransformer() {
    // Построения (линии ±∞) и окружности в трансформер не берём (рамка/ресайз не нужны).
    const sel = Array.from(selected).map((id) => nodes.get(id))
      .filter((n) => { const e = n && elements.get(n.id()); return e && !(e.type === 'point' || e.type === 'angle' || CONSTRUCT_LINES.indexOf(e.type) >= 0 || e.type === 'circ' || isFilledPoly(e.type)); });
    tr.nodes(sel);
    tr.moveToTop();
    // DOM-объекты (текст/виджеты) трансформер не оборачивает — показываем рамку через класс.
    if (widgetItems.size) widgetItems.forEach((it, id) => it.wrapper.classList.toggle('wsel', selected.has(id)));
    syncTboxFieldBar();
    renderAnchors();   // якоря показываем у одиночного выделенного объекта
    if (typeof syncVennBar === 'function') syncVennBar();
    refreshConstructionHighlight();
    positionHandles();
    updateFuncEditor();
    syncPointSettings();
    syncFigureSettings();
    updatePdfControls();
  }
  // Показать панель форматирования у ВЫБРАННОГО (не правящегося) текстового
  // поля и убрать её, когда выделение ушло. Во время правки панелью занимается
  // startTboxEdit/endTboxEdit — сюда не вмешиваемся.
  function syncTboxFieldBar() {
    if (typeof tboxBar === 'undefined' || !tboxBar) return;
    if (activeTbox && activeTbox.editing) return;
    let it = null;
    if (selected.size === 1) {
      const w = widgetItems.get(Array.from(selected)[0]);
      if (w && w.isTbox) it = w;
    }
    if (it) { activeTbox = it; showTboxBar(it); }
    else if (activeTbox) { activeTbox = null; hideTboxBar(); }
  }

  function clearSelection() {
    activeFrameId = null; // клик по пустому — деактивировать окно
    if (selected.size === 0) { tr.nodes([]); updateFuncEditor(); return; }
    selected.clear();
    refreshTransformer();
  }

  // ── Контекстный редактор функций у выделенного окна ────────────────────
  const funcEditor = document.getElementById('func-editor');
  const feInput = document.getElementById('fe-input');
  const feList = document.getElementById('fe-list');
  let activeFrameId = null;

  let _feFrame = null;
  function updateFuncEditor() {
    updateStoryboard(); // раскадровка обновляется в тех же точках, что и редактор функций
    updateFrameExitBtn(); // и кнопка «выйти из окна» — тоже
    if (!funcEditor) return;
    // Редактор функций показываем у АКТИВНОГО окна и только в режиме выделения.
    const fr = (tool === 'select' && activeFrameId) ? elements.get(activeFrameId) : null;
    if (!fr || fr.type !== 'frame') { funcEditor.hidden = true; _feFrame = null; return; }
    funcEditor.hidden = false;
    if (_feFrame !== fr.id) { _feFrame = fr.id; renderFuncList(fr.id); }
    positionFuncEditor(fr);
  }
  function positionFuncEditor(fr) {
    const s = stage.scaleX();
    const winLeft = fr.data.x * s + stage.x();
    const winTop = fr.data.y * s + stage.y() + STAGE_TOP; // 56 — высота навбара над холстом
    const winH = fr.data.height * s, W = 240;
    // Панель слева от окна, в полную его высоту; если слева не влезает — справа.
    let left = winLeft - W - 10;
    if (left < 8) left = winLeft + fr.data.width * s + 10;
    funcEditor.style.left = left + 'px';
    funcEditor.style.top = Math.max(STAGE_TOP + 6, winTop) + 'px';
    funcEditor.style.height = Math.max(120, winH) + 'px';
  }
  // ── Выход из окна на весь экран ────────────────────────────────────────
  // Когда активное матокно занимает почти весь экран, два пальца тачпада зумят
  // его плоскость, и «улететь» на доску нельзя (колесо перехватывается окном).
  // Кнопка деактивирует окно (колесо снова двигает доску) и отдаляет вид,
  // показывая окно целиком.
  function frameScreenRect(fr) {
    const s = stage.scaleX();
    return { left: fr.data.x * s + stage.x(), top: fr.data.y * s + stage.y() + STAGE_TOP, w: fr.data.width * s, h: fr.data.height * s };
  }
  function updateFrameExitBtn() {
    if (!frameExitBtn) return;
    const fr = activeFrameId && elements.get(activeFrameId);
    let show = false;
    if (fr && fr.type === 'frame') {
      const r = frameScreenRect(fr), vw = window.innerWidth, vh = window.innerHeight;
      const visW = Math.min(r.left + r.w, vw) - Math.max(r.left, 0);
      const visH = Math.min(r.top + r.h, vh) - Math.max(r.top, STAGE_TOP);
      const cov = (Math.max(0, visW) * Math.max(0, visH)) / (vw * Math.max(1, vh - STAGE_TOP));
      show = cov > 0.65; // окно закрывает ≳2/3 холста — легко «застрять» внутри
    }
    frameExitBtn.hidden = !show;
  }
  function fitFrameToView(fr, frac) {
    const vw = window.innerWidth, vh = window.innerHeight - STAGE_TOP;
    const target = Math.max(MIN_SCALE, Math.min(MAX_SCALE,
      Math.min(frac * vw / Math.max(1, fr.data.width), frac * vh / Math.max(1, fr.data.height))));
    stage.scale({ x: target, y: target });
    const cxW = fr.data.x + fr.data.width / 2, cyW = fr.data.y + fr.data.height / 2;
    stage.position({ x: vw / 2 - cxW * target, y: vh / 2 - cyW * target }); // центр окна → центр экрана
    scheduleViewRedraw(); updateZoomLabel(); repositionConnPanel();
  }
  function exitActiveFrame() {
    const fr = activeFrameId && elements.get(activeFrameId);
    clearSelection();                          // окно деактивировано — колесо снова двигает доску
    if (fr && fr.type === 'frame') fitFrameToView(fr, 0.6);
    updateFrameExitBtn();                       // спрятать кнопку
  }
  if (frameExitBtn) frameExitBtn.addEventListener('click', exitActiveFrame);
  // ── Настройщик алгебры окна: список всех объектов с редактированием ──────
  function algPName(id) { const p = elements.get(id); return (p && p.type === 'point') ? pointName(p) : '?'; }
  function algDescLine(e) {
    const nm = { segment: 'отрезок', ray: 'луч', gline: 'прямая', perpbis: 'сер. перпендикуляр', perp: 'перпендикуляр', parallel: 'параллель', bisector: 'биссектриса' }[e.type] || 'прямая';
    return (e.data.a && e.data.b) ? nm + ' ' + algPName(e.data.a) + algPName(e.data.b) : nm;
  }
  function algDescPoly(e) {
    if (e.type === 'regpoly') return 'правильный ' + (e.data.n || '') + '-угольник';
    return 'многоугольник ' + (e.data.pts || []).map(algPName).join('');
  }
  function algDescAngle(e) { return '∠' + algPName(e.data.a) + algPName(e.data.b) + algPName(e.data.c); }
  function algDescAnalysis(e) {
    const ex = (id) => { const f = elements.get(id); return f ? f.data.expr : '?'; };
    if (e.type === 'ftangent') return 'касательная к y=' + ex(e.data.func) + ' при x=' + (Math.round(e.data.x0 * 100) / 100);
    if (e.type === 'farea') return 'площадь под y=' + ex(e.data.func) + ' на [' + (Math.round(Math.min(e.data.a, e.data.b) * 100) / 100) + '; ' + (Math.round(Math.max(e.data.a, e.data.b) * 100) / 100) + ']';
    return 'пересечение y=' + ex(e.data.f) + ' и y=' + ex(e.data.g);
  }
  function regionFuncExpr(id) { const f = elements.get(id); return f ? f.data.expr : '?'; }
  function regionShortDesc(e) { const n = (e.data.parts || []).length; return n <= 1 ? 'область неравенства' : 'система из ' + n + ' неравенств'; }
  const EYE_ON = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="2.6"/></svg>';
  const EYE_OFF = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 4l16 16"/><path d="M9.9 5.2A9.6 9.6 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3 3.6M6.5 7.5A17 17 0 0 0 2 12s3.5 7 10 7a9.6 9.6 0 0 0 3.4-.6"/></svg>';
  function algEyeBtn(e) { const hid = !!e.data.hidden; return '<button class="fe-eye' + (hid ? ' off' : '') + '" data-eye="' + e.id + '" title="' + (hid ? 'Показать' : 'Скрыть') + '">' + (hid ? EYE_OFF : EYE_ON) + '</button>'; }
  function algObjRow(e, desc) {
    return '<div class="fe-obj">' + odescHtml(e, desc)
      + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>';
  }
  function algParamRows(expr, params, exclude) {
    let html = '';
    funcVarsOf(expr, exclude).forEach((v) => {
      const p = params[v]; if (!p) return;
      html += '<div class="fe-param"><span class="fe-pname">' + escapeHtml(v) + ' =</span>'
        + '<input type="range" class="fe-prange" data-p="' + escapeAttr(v) + '" min="' + p.min + '" max="' + p.max + '" step="0.1" value="' + p.v + '">'
        + '<span class="fe-pval" data-pv="' + escapeAttr(v) + '">' + fmtMeasure(p.v) + '</span></div>'
        + '<div class="fe-pbounds"><input class="fe-pmin" data-p="' + escapeAttr(v) + '" type="number" step="1" value="' + p.min + '"><span>…</span><input class="fe-pmax" data-p="' + escapeAttr(v) + '" type="number" step="1" value="' + p.max + '"></div>';
    });
    return html;
  }
  // Редактируемая ячейка формулы (функция/неявная кривая): имя + правка выражения на месте.
  function algFuncExprCell(e, kind) {
    return (objName(e) ? '<b class="fe-nm">' + escapeHtml(objName(e)) + '</b>:&nbsp;' : '')
      + '<input class="fe-editexpr" data-id="' + e.id + '" data-kind="' + kind + '" value="' + escapeAttr(e.data.expr) + '" spellcheck="false">';
  }
  function renderFuncList(frameId) {
    if (!feList) return;
    const fr = elements.get(frameId); if (!fr) { feList.innerHTML = ''; return; }
    const params = fr.data.params || {};
    const g = { point: [], line: [], circ: [], conic: [], poly: [], vector: [], angle: [], measure: [], func: [], implicit: [], analysis: [], region: [] };
    elements.forEach((e) => {
      if (!e.data || e.id === frameId || e.data.frame !== frameId) return;
      if (e.type === 'point') g.point.push(e);
      else if (CONSTRUCT_LINES.indexOf(e.type) >= 0) g.line.push(e);
      else if (e.type === 'circ') g.circ.push(e);
      else if (e.type === 'conic') g.conic.push(e);
      else if (isFilledPoly(e.type)) g.poly.push(e);
      else if (e.type === 'vector') g.vector.push(e);
      else if (e.type === 'angle') g.angle.push(e);
      else if (e.type === 'measure') g.measure.push(e);
      else if (e.type === 'func') g.func.push(e);
      else if (e.type === 'implicit') g.implicit.push(e);
      else if (e.type === 'ftangent' || e.type === 'farea' || e.type === 'fintersect') g.analysis.push(e);
      else if (e.type === 'region') g.region.push(e);
    });
    let html = '';
    if (g.point.length) {
      html += '<div class="fe-group-label">Точки</div>';
      g.point.forEach((e) => {
        const free = !e.data.on; // производные/привязанные — только просмотр координат
        html += '<div class="fe-obj"><span class="fe-oname">' + escapeHtml(pointName(e)) + '</span>'
          + '<input class="fe-coord" data-id="' + e.id + '" data-axis="x" type="number" step="0.5" value="' + fmtCoord(e.data.mx || 0) + '"' + (free ? '' : ' disabled') + '>'
          + '<input class="fe-coord" data-id="' + e.id + '" data-axis="y" type="number" step="0.5" value="' + fmtCoord(e.data.my || 0) + '"' + (free ? '' : ' disabled') + '>'
          + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>'
          + algCondRow(e);
      });
    }
    if (g.func.length) {
      html += '<div class="fe-group-label">Функции</div>';
      g.func.forEach((e) => {
        html += '<div class="fe-item"><span class="fe-sw" style="background:' + (e.data.color || '#1f6feb') + '"></span>'
          + algFuncExprCell(e, 'func')
          + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>'
          + algParamRows(e.data.expr, params) + algCondRow(e);
      });
    }
    if (g.implicit.length) {
      html += '<div class="fe-group-label">Неявные кривые</div>';
      g.implicit.forEach((e) => {
        html += '<div class="fe-item"><span class="fe-sw" style="background:' + (e.data.color || '#c0392b') + '"></span>'
          + algFuncExprCell(e, 'implicit')
          + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>'
          + algParamRows(e.data.expr, params, ['y']) + algCondRow(e);
      });
    }
    if (g.line.length) {
      html += '<div class="fe-group-label">Прямые и отрезки</div>';
      g.line.forEach((e) => { html += algLineRow(e) + algCondRow(e); });
    }
    if (g.circ.length) {
      html += '<div class="fe-group-label">Окружности</div>';
      g.circ.forEach((e) => { html += algCircleRow(e) + algCondRow(e); });
    }
    if (g.conic.length) {
      html += '<div class="fe-group-label">Коники</div>';
      g.conic.forEach((e) => { html += algConicRow(e) + algCondRow(e); });
    }
    if (g.poly.length) {
      html += '<div class="fe-group-label">Многоугольники</div>';
      g.poly.forEach((e) => { html += algObjRow(e, algDescPoly(e)) + algCondRow(e); });
    }
    if (g.vector.length) {
      html += '<div class="fe-group-label">Векторы</div>';
      g.vector.forEach((e) => { html += algVectorRow(e) + algCondRow(e); });
    }
    if (g.angle.length) {
      html += '<div class="fe-group-label">Углы</div>';
      g.angle.forEach((e) => { html += algObjRow(e, algDescAngle(e)) + algCondRow(e); });
    }
    if (g.measure.length) {
      html += '<div class="fe-group-label">Измерения</div>';
      g.measure.forEach((e) => { html += algMeasureRow(e) + algCondRow(e); });
    }
    if (g.analysis.length) {
      html += '<div class="fe-group-label">Анализ</div>';
      g.analysis.forEach((e) => { html += algObjRow(e, algDescAnalysis(e)); });
    }
    if (g.region.length) {
      html += '<div class="fe-group-label">Области (неравенства)</div>';
      g.region.forEach((e) => {
        html += '<div class="fe-item"><span class="fe-sw" style="background:' + (e.data.color || '#2e86de') + '"></span>'
          + '<span class="fe-expr">' + escapeHtml(regionShortDesc(e)) + '</span>'
          + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>';
        (e.data.parts || []).forEach((p, idx) => {
          html += '<div class="fe-param"><span class="fe-pname">y ' + (p.sense === 'gt' ? '≥' : '≤') + ' ' + escapeHtml(regionFuncExpr(p.func)) + '</span>'
            + '<button class="fe-rsense" data-region="' + e.id + '" data-part="' + idx + '">' + (p.sense === 'gt' ? 'выше' : 'ниже') + '</button></div>';
        });
      });
    }
    feList.innerHTML = html || '<div class="fe-empty">окно пустое — добавьте объекты или формулу</div>';
    syncFrameBg(fr);
  }
  function syncFrameBg(fr) {
    const box = document.getElementById('fe-bg'); if (!box || !fr) return;
    // Сетка и Точки — взаимоисключающие СТИЛИ рисунка (не горят вместе); Оси — отдельно.
    const gridOn = fr.data.gridOn !== false, dots = fr.data.gridStyle === 'dots';
    const st = { grid: gridOn && !dots, dots: gridOn && dots, axes: fr.data.axesOn !== false };
    box.querySelectorAll('button').forEach((b) => b.classList.toggle('on', !!st[b.dataset.bg]));
    const csw = document.getElementById('fe-bgcolor-sw'), pick = document.getElementById('fe-bgcolor-custom');
    if (csw) csw.style.background = fr.data.bgColor || '#ffffff';
    const cur = (fr.data.bgColor || '#ffffff').toLowerCase();
    if (pick && /^#[0-9a-f]{6}$/.test(cur)) pick.value = cur;
    const gsw = document.getElementById('fe-gridcolor-sw'), gpick = document.getElementById('fe-gridcolor-custom');
    if (gsw) gsw.style.background = fr.data.gridColor || '#e4e6ee';
    const gcur = (fr.data.gridColor || '').toLowerCase();
    if (gpick && /^#[0-9a-f]{6}$/.test(gcur)) gpick.value = gcur;
  }
  function setFrameBgColor(color) {
    const fr = activeFrameId && elements.get(activeFrameId); if (!fr || fr.type !== 'frame') return;
    const before = clone(fr); fr.data.bgColor = color;
    const node = nodes.get(fr.id); if (node) { const bg = node.findOne('.fbg'); if (bg) bg.fill(color || '#ffffff'); }
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    layer.batchDraw(); syncFrameBg(fr);
  }
  function setFrameGridColor(color) {
    const fr = activeFrameId && elements.get(activeFrameId); if (!fr || fr.type !== 'frame') return;
    const before = clone(fr); fr.data.gridColor = color;
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    layer.batchDraw(); syncFrameBg(fr);
  }
  function toggleFrameBg(which) {
    const fr = activeFrameId && elements.get(activeFrameId); if (!fr || fr.type !== 'frame') return;
    const before = clone(fr);
    const gridOn = fr.data.gridOn !== false, dots = fr.data.gridStyle === 'dots';
    if (which === 'grid') {
      // «Сетка» — линии. Если уже линии — выключаем рисунок; иначе включаем линии.
      if (gridOn && !dots) fr.data.gridOn = false;
      else { fr.data.gridOn = true; fr.data.gridStyle = 'lines'; }
    } else if (which === 'dots') {
      // «Точки». Если уже точки — выключаем; иначе включаем точки (взамен линий).
      if (gridOn && dots) fr.data.gridOn = false;
      else { fr.data.gridOn = true; fr.data.gridStyle = 'dots'; }
    } else if (which === 'axes') {
      fr.data.axesOn = !(fr.data.axesOn !== false);
    }
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    layer.batchDraw(); syncFrameBg(fr);
  }
  // Единый роутер числовых полей панели.
  function algEditNum(id, axis, val) {
    if (axis === 'link' || axis === 'linb' || axis === 'linx') return algEditLine(id, axis, val);
    return algEditCoord(id, axis, val);
  }
  // Правка координаты точки / радиуса (r) / квадрата радиуса (r²) окружности.
  function algEditCoord(id, axis, val) {
    const el = elements.get(id); if (!el || !isFinite(val)) return;
    const before = clone(el);
    if (el.type === 'point') { if (axis === 'x') el.data.mx = val; else el.data.my = val; }
    else if (el.type === 'circ') { el.data.r = (axis === 'r2') ? Math.sqrt(Math.max(0, val)) : Math.max(0, val); }
    histUpd(before, el); recomputeGeometry(); send({ action: 'element_update', element: el }); layer.batchDraw();
  }
  // Прямая по двум свободным точкам A,B: правка наклона k / свободного члена b / x
  // (для вертикальной). «Переопределяем» прямую, двигая её опорные точки.
  function algEditLine(id, axis, val) {
    const e = elements.get(id); if (!e || !isFinite(val)) return;
    const A = elements.get(e.data.a), B = elements.get(e.data.b);
    if (!A || !B || A.type !== 'point' || B.type !== 'point') return;
    const bA = clone(A), bB = clone(B);
    const ax = A.data.mx || 0, ay = A.data.my || 0, bx = B.data.mx || 0, by = B.data.my || 0;
    if (axis === 'linx') { A.data.mx = val; B.data.mx = val; }
    else if (axis === 'link') { if (Math.abs(bx - ax) < 1e-9) return; B.data.my = ay + val * (bx - ax); } // держим A, наклоняем к B
    else if (axis === 'linb') { const k = (Math.abs(bx - ax) < 1e-9) ? 0 : (by - ay) / (bx - ax); A.data.my = k * ax + val; B.data.my = k * bx + val; } // вертикальный сдвиг под свободный член
    histUpd(bA, A); histUpd(bB, B); recomputeGeometry();
    send({ action: 'element_update', element: A }); send({ action: 'element_update', element: B }); layer.batchDraw();
  }
  // Правка формулы функции/неявной кривой «на месте»: тот же объект (id, цвет, имя),
  // просто новое выражение. Невалидный ввод — подсветить и не менять объект.
  function editFuncExpr(id, kind, raw, inputEl) {
    const el = elements.get(id); if (!el) return;
    const newExpr = String(raw || '').trim();
    if (!newExpr) { if (inputEl) inputEl.value = el.data.expr; return; }
    if (newExpr === el.data.expr) { if (inputEl) inputEl.classList.remove('invalid'); return; }
    const ok = (kind === 'implicit') ? compileImplicit(newExpr) : compileFunc(newExpr);
    if (!ok) {
      boardHint(kind === 'implicit' ? 'Не понял уравнение — проверьте запись' : 'Не понял формулу — проверьте запись');
      if (inputEl) inputEl.classList.add('invalid');
      return;
    }
    if (inputEl) inputEl.classList.remove('invalid');
    const before = clone(el); el.data.expr = newExpr;
    const fr = elements.get(el.data.frame);
    if (fr) { const bf = clone(fr); if (ensureFrameParams(fr, newExpr, kind === 'implicit' ? ['y'] : undefined)) { histUpd(bf, fr); send({ action: 'element_update', element: fr }); } }
    histUpd(before, el); send({ action: 'element_update', element: el });
    redrawFuncs(); renderFuncList(el.data.frame);
  }
  // Уравнение прямой по её опорным точкам (в координатах плоскости окна).
  function algLineEq(e) {
    const A = elements.get(e.data.a), B = elements.get(e.data.b);
    if (!A || !B || A.type !== 'point' || B.type !== 'point') return null;
    const ax = A.data.mx || 0, ay = A.data.my || 0, bx = B.data.mx || 0, by = B.data.my || 0;
    const editable = !A.data.on && !B.data.on;
    if (Math.abs(bx - ax) < 1e-9) return { vertical: true, c: ax, editable };
    const k = (by - ay) / (bx - ax);
    return { vertical: false, k, b: ay - k * ax, editable };
  }
  // Строка прямой: описание + (для отрезка/луча/прямой по 2 свободным точкам)
  // редактируемое уравнение y = k·x + b (или x = c для вертикальной).
  function algLineRow(e) {
    let html = '<div class="fe-obj">' + odescHtml(e, algDescLine(e)) + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>';
    const hasAB = (e.type === 'segment' || e.type === 'ray' || e.type === 'gline') && e.data.a && e.data.b;
    if (!hasAB) return html;
    const eq = algLineEq(e); if (!eq) return html;
    if (eq.editable) {
      if (eq.vertical) html += '<div class="fe-subrow">x =<input class="fe-coord" data-id="' + e.id + '" data-axis="linx" type="number" step="0.5" value="' + fmtCoord(eq.c) + '"></div>';
      else html += '<div class="fe-subrow">y =<input class="fe-coord" data-id="' + e.id + '" data-axis="link" type="number" step="0.1" value="' + fmtCoord(eq.k) + '"> · x +<input class="fe-coord" data-id="' + e.id + '" data-axis="linb" type="number" step="0.5" value="' + fmtCoord(eq.b) + '"></div>';
    } else {
      html += '<div class="fe-subrow">' + escapeHtml(eq.vertical ? ('x = ' + fmtCoord(eq.c)) : ('y = ' + fmtCoord(eq.k) + 'x + ' + fmtCoord(eq.b))) + '</div>';
    }
    return html;
  }
  // Строка окружности: центр (координаты, редакт. если центр — свободная точка) + r².
  function algCircleRow(e) {
    const d = e.data;
    const centerId = (d.kind === 'cp' || d.kind === 'cr' || d.kind === 'compass') ? d.center : null;
    const cpt = centerId ? elements.get(centerId) : null;
    const fr = d.frame ? elements.get(d.frame) : null, unit = fr ? (fr.data.unit || 40) : 1;
    const rMath = (d.kind === 'cr') ? (d.r || 0) : (function () { const C = circleGeom(e); return C ? C.r / unit : 0; })();
    let html = '<div class="fe-obj">' + odescHtml(e, 'окружность') + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>';
    let center;
    if (cpt && cpt.type === 'point') {
      const free = !cpt.data.on;
      center = 'центр ' + escapeHtml(pointName(cpt)) + ':'
        + '<input class="fe-coord" data-id="' + centerId + '" data-axis="x" type="number" step="0.5" value="' + fmtCoord(cpt.data.mx || 0) + '"' + (free ? '' : ' disabled') + '>'
        + '<input class="fe-coord" data-id="' + centerId + '" data-axis="y" type="number" step="0.5" value="' + fmtCoord(cpt.data.my || 0) + '"' + (free ? '' : ' disabled') + '>';
    } else {
      const C = circleGeom(e), m = (C && fr) ? frameLocalToMath(fr, C.cx, C.cy) : { mx: 0, my: 0 };
      center = 'центр: (' + fmtCoord(m.mx) + '; ' + fmtCoord(m.my) + ')';
    }
    const r2edit = (d.kind === 'cr');
    html += '<div class="fe-subrow">' + center + '</div>'
      + '<div class="fe-subrow">r² =<input class="fe-coord" data-id="' + e.id + '" data-axis="r2" type="number" step="0.5" value="' + fmtCoord(rMath * rMath) + '"' + (r2edit ? '' : ' disabled') + '></div>';
    return html;
  }
  // Вектор в алгебре: компоненты (в матем. коорд. окна) и длина.
  function vectorMath(e) {
    const A = elements.get(e.data.a), B = elements.get(e.data.b);
    if (!A || !B || A.type !== 'point' || B.type !== 'point') return null;
    const dx = (B.data.mx || 0) - (A.data.mx || 0), dy = (B.data.my || 0) - (A.data.my || 0);
    return { dx, dy, len: Math.hypot(dx, dy), A, B };
  }
  function algVectorRow(e) {
    const v = vectorMath(e);
    const name = v ? ('вектор ' + pointName(v.A) + pointName(v.B)) : 'вектор';
    let html = '<div class="fe-obj">' + odescHtml(e, name) + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>';
    if (v) html += '<div class="fe-subrow">(' + fmtCoord(v.dx) + '; ' + fmtCoord(v.dy) + '), |v| = ' + fmtCoord(v.len) + '</div>';
    return html;
  }
  // Коника в алгебре: уравнение Ax²+Bxy+Cy²+Dx+Ey+F=0 по 5 точкам (матем. коорд.).
  function conicMathCoeffs(e) {
    const P = (e.data.pts || []).map((id) => elements.get(id)).filter((p) => p && p.type === 'point').slice(0, 5).map((p) => ({ x: p.data.mx || 0, y: p.data.my || 0 }));
    return P.length >= 5 ? conicCoeffs(P) : null;
  }
  function fmtConicEq(co) {
    const labels = ['x²', 'xy', 'y²', 'x', 'y', ''];
    const terms = [];
    for (let i = 0; i < 6; i++) {
      const cc = Math.round(co[i] * 100) / 100; if (Math.abs(cc) < 0.005) continue;
      const mag = Math.abs(cc), lab = labels[i];
      const body = lab ? ((mag === 1 ? '' : mag) + lab) : ('' + mag);
      terms.push({ neg: cc < 0, body });
    }
    if (!terms.length) return '';
    let s = (terms[0].neg ? '−' : '') + terms[0].body;
    for (let i = 1; i < terms.length; i++) s += ' ' + (terms[i].neg ? '−' : '+') + ' ' + terms[i].body;
    return s + ' = 0';
  }
  function algConicRow(e) {
    const co = conicMathCoeffs(e);
    let html = '<div class="fe-obj">' + odescHtml(e, 'коника по 5 точкам') + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>';
    if (co) html += '<div class="fe-subrow">' + escapeHtml(fmtConicEq(co)) + '</div>';
    return html;
  }
  // Измерение в алгебре: живое значение (длина/угол/площадь) + имя.
  function algMeasureRow(e) {
    const info = measureInfo(e);
    const kindName = { length: 'длина', angle: 'угол', area: 'площадь' }[e.data.kind] || 'измерение';
    const desc = kindName + (info ? ' · ' + info.text : ' · —');
    return '<div class="fe-obj">' + odescHtml(e, desc) + algEyeBtn(e) + '<button class="fe-del" data-id="' + e.id + '" title="Удалить">×</button></div>';
  }
  // Строка условной видимости объекта: «показ. если <условие>» (по значениям окна).
  function algCondRow(e) {
    const c = (e.data && e.data.showIf) || '';
    return '<div class="fe-cond"><span class="fe-condlbl">пок. если</span>'
      + '<input class="fe-condinput' + (c ? ' set' : '') + '" data-id="' + e.id + '" value="' + escapeAttr(c) + '" placeholder="напр. k>2" spellcheck="false" title="Объект виден, только когда условие истинно. Имена: ползунки/параметры/измерения; функции x(A), y(A), dist(A,B), angle(A,B,C); сравнения < > = и & |"></div>';
  }
  function setShowIf(id, raw) {
    const el = elements.get(id); if (!el) return;
    const v = String(raw || '').trim(), before = clone(el);
    if (!v) { if (el.data.showIf) { delete el.data.showIf; } el._condSrc = null; el._condFn = null; el._condHide = false; }
    else { if (!compileNum(v)) { boardHint('Не понял условие — проверьте запись'); return; } el.data.showIf = v; }
    applyElVisibility(el); histUpd(before, el); send({ action: 'element_update', element: el });
    applyConditions(); layer.batchDraw();
  }
  // Перерисовать список алгебры, если панель открыта у активного окна.
  function syncAlgebra() { const fe = document.getElementById('func-editor'); if (fe && !fe.hidden && activeFrameId && feList) renderFuncList(activeFrameId); }
  // Правка границ параметра (на вкус пользователя).
  function algEditBound(frameId, name) {
    const fr = elements.get(frameId); if (!fr || !fr.data.params || !fr.data.params[name]) return;
    const mnEl = feList.querySelector('.fe-pmin[data-p="' + name + '"]'), mxEl = feList.querySelector('.fe-pmax[data-p="' + name + '"]');
    if (!mnEl || !mxEl) return;
    const p = fr.data.params[name], before = clone(fr);
    let mn = parseFloat(mnEl.value), mx = parseFloat(mxEl.value);
    if (!isFinite(mn)) mn = p.min; if (!isFinite(mx)) mx = p.max;
    if (mx <= mn) mx = mn + 1;
    p.min = mn; p.max = mx; p.v = Math.max(mn, Math.min(mx, p.v));
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    feList.querySelectorAll('.fe-prange[data-p="' + name + '"]').forEach((r) => { r.min = mn; r.max = mx; r.value = p.v; });
    feList.querySelectorAll('.fe-pval[data-pv="' + name + '"]').forEach((s) => { s.textContent = fmtMeasure(p.v); });
    mnEl.value = mn; mxEl.value = mx; redrawFuncs();
  }
  // ── Командная строка окна ──────────────────────────────────────────────
  // Один ввод понимает: A=(2;3) — точка; Line(A,B)/Прямая(A,B); Segment/Ray;
  // Vector(A,B); Circle(центр,точка) или Circle(центр,радиус); Midpoint(A,…);
  // Polygon(A,B,C,…); Point(x;y); c: x^2+y^2=9 — именованная кривая. Иначе —
  // обычная функция/неявная кривая (прежнее поведение).
  const CMD_ALIASES = {
    line: 'gline', 'прямая': 'gline', segment: 'segment', 'отрезок': 'segment',
    ray: 'ray', 'луч': 'ray', vector: 'vector', 'вектор': 'vector',
    circle: 'circle', 'окружность': 'circle', circ: 'circle',
    midpoint: 'midpoint', 'середина': 'midpoint', center: 'midpoint', 'центр': 'midpoint',
    polygon: 'polygon', 'многоугольник': 'polygon', poly: 'polygon',
    point: 'point', 'точка': 'point',
    sequence: 'sequence', 'послед': 'sequence', 'последовательность': 'sequence', 'семейство': 'sequence'
  };
  // Разбить аргументы по запятым/точкам с запятой верхнего уровня (скобки координат целы).
  function cmdSplitArgs(s) {
    const out = []; let d = 0, cur = '';
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (c === '(') { d++; cur += c; } else if (c === ')') { d--; cur += c; }
      else if ((c === ',' || (c === ';' && d === 0)) && d === 0) { out.push(cur.trim()); cur = ''; }
      else cur += c;
    }
    if (cur.trim()) out.push(cur.trim());
    return out;
  }
  // Литерал координат «(x; y)» → {mx,my} или null (разделитель — «,» или «;»).
  function cmdParseCoords(s) {
    const m = String(s).trim().match(/^\(\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*\)$/);
    return m ? { mx: parseFloat(m[1]), my: parseFloat(m[2]) } : null;
  }
  // Найти точку окна по имени (буква ± индекс, регистр не важен).
  function cmdFindPoint(frameId, name) {
    const key = String(name).trim().toUpperCase(); let hit = null;
    elements.forEach((e) => {
      if (hit || !e.data || e.data.frame !== frameId || e.type !== 'point') return;
      const nm = (e.data.label || '') + (e.data.idx ? e.data.idx : '');
      if (nm.toUpperCase() === key) hit = e;
    });
    return hit;
  }
  // Создать свободную точку окна в матем. координатах (label — задать или авто).
  function cmdCreatePoint(frameId, mx, my, label) {
    const el = { id: uuid(), type: 'point', z: 0, data: { frame: frameId, mx: mx, my: my, label: label || nextPointLabel(), color: strokeColor } };
    applyTypeDefaults(el.data, 'point');
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el); recomputeGeometry(); layer.batchDraw();
    return el;
  }
  function cmdCanResolve(frameId, arg) { return !!(cmdParseCoords(arg) || cmdFindPoint(frameId, arg)); }
  function cmdResolvePoint(frameId, arg) {
    const co = cmdParseCoords(arg);
    if (co) { const p = cmdCreatePoint(frameId, co.mx, co.my); return p ? p.id : null; }
    const p = cmdFindPoint(frameId, arg); return p ? p.id : null;
  }
  // Разрешить список аргументов-точек: null, если хоть один не распознан (точки не плодим).
  function cmdResolvePoints(frameId, args) {
    if (!args.length || !args.every((a) => cmdCanResolve(frameId, a))) return null;
    return args.map((a) => cmdResolvePoint(frameId, a));
  }
  // Параметрическое семейство точек: Sequence((x(k), y(k)), k, от, до[, шаг]).
  // Разворачивается в обычные (свободные) точки — их можно двигать/удалять.
  function runSequence(frameId, args) {
    if (args.length < 4) { boardHint('Семейство: Sequence((x(k); y(k)), k, от, до, шаг)'); return true; }
    let pair = String(args[0]).trim();
    if (pair.charAt(0) === '(' && pair.charAt(pair.length - 1) === ')') pair = pair.slice(1, -1);
    const parts = cmdSplitArgs(pair);
    if (parts.length !== 2) { boardHint('Первый аргумент — пара (x(k); y(k))'); return true; }
    const fx = compileNum(parts[0]), fy = compileNum(parts[1]);
    if (!fx || !fy) { boardHint('Не понял формулы координат семейства'); return true; }
    const varName = String(args[1]).trim();
    if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(varName)) { boardHint('Переменная семейства — имя (напр. k)'); return true; }
    let from = parseFloat(String(args[2]).replace(',', '.')), to = parseFloat(String(args[3]).replace(',', '.'));
    let step = args.length >= 5 ? parseFloat(String(args[4]).replace(',', '.')) : 1;
    if (!isFinite(from) || !isFinite(to) || !isFinite(step) || step === 0) { boardHint('Проверьте «от», «до», «шаг»'); return true; }
    if ((to - from) * step < 0) step = -step; // шаг всегда в сторону «до»
    const n = Math.floor(Math.abs((to - from) / step) + 1e-9) + 1;
    if (n > 200) { boardHint('Слишком много точек (>200) — увеличьте шаг'); return true; }
    let made = 0;
    for (let i = 0; i < n; i++) {
      const kv = from + i * step, env = {}; env[varName] = kv;
      let x, y; try { x = fx(env); y = fy(env); } catch (_) { continue; }
      if (!isFinite(x) || !isFinite(y)) continue;
      const el = { id: uuid(), type: 'point', z: 0, data: { frame: frameId, mx: x, my: y, label: nextPointLabel(), color: strokeColor } };
      applyTypeDefaults(el.data, 'point'); el.data.labelHidden = true; // семейство — без подписей
      upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
      made++;
    }
    recomputeGeometry(); layer.batchDraw();
    boardHint('Семейство: создано точек — ' + made);
    return true;
  }
  function runNamedCommand(frameId, cmd, args) {
    if (cmd === 'sequence') return runSequence(frameId, args);
    if (cmd === 'point') {
      const co = cmdParseCoords('(' + args.join(';') + ')') || (args.length === 2 ? { mx: parseFloat(args[0]), my: parseFloat(args[1]) } : null);
      if (!co || !isFinite(co.mx) || !isFinite(co.my)) { boardHint('Точка(x; y) — две координаты'); return true; }
      const p = cmdCreatePoint(frameId, co.mx, co.my); boardHint('Точка ' + (p ? pointName(p) : '') + ' создана'); return true;
    }
    if (cmd === 'circle') {
      if (args.length !== 2) { boardHint('Окружность(центр, точка) или Окружность(центр, радиус)'); return true; }
      const c = cmdResolvePoint(frameId, args[0]); if (!c) { boardHint('Не нашёл точку ' + args[0]); return true; }
      if (cmdCanResolve(frameId, args[1])) { const t = cmdResolvePoint(frameId, args[1]); createCircle('cp', [c, t]); }
      else { const r = parseFloat(String(args[1]).replace(',', '.')); if (!isFinite(r) || r <= 0) { boardHint('Второй аргумент — точка или радиус'); return true; } createCircle('cr', [c], { r: r }); }
      boardHint('Окружность построена'); return true;
    }
    if (cmd === 'midpoint') {
      const ids = cmdResolvePoints(frameId, args);
      if (!ids || ids.length < 2) { boardHint('Середина(A, B) — по двум точкам'); return true; }
      createDerivedPoint({ centroid: ids }, ids); boardHint('Середина построена'); return true;
    }
    if (cmd === 'polygon') {
      const ids = cmdResolvePoints(frameId, args);
      if (!ids || ids.length < 3) { boardHint('Многоугольник(A, B, C, …) — не менее 3 точек'); return true; }
      createPolygon(ids); boardHint('Многоугольник построен'); return true;
    }
    if (cmd === 'vector') {
      const ids = cmdResolvePoints(frameId, args);
      if (!ids || ids.length !== 2) { boardHint('Вектор(A, B) — по двум точкам'); return true; }
      createVector(ids); boardHint('Вектор построен'); return true;
    }
    // прямая / отрезок / луч — построение по двум точкам
    const ids = cmdResolvePoints(frameId, args);
    if (!ids || ids.length !== 2) { boardHint('Нужны две точки'); return true; }
    createConstruction(cmd, ids); boardHint('Построено'); return true;
  }
  // Разобрать ввод как команду. true — обработано (в т.ч. с ошибкой-подсказкой);
  // false — это не команда, обрабатываем как функцию/неявную кривую.
  function runCommand(frameId, raw) {
    const fr = elements.get(frameId); if (!fr || fr.type !== 'frame') return false;
    const src = String(raw || '').trim();
    // 1) Присваивание точки: Name=(x; y)
    let m = src.match(/^([A-Za-z][A-Za-z0-9]*)\s*=\s*(\(.*\))$/);
    if (m) {
      const co = cmdParseCoords(m[2]); if (!co) { boardHint('Координаты вида (x; y)'); return true; }
      const label = m[1].toUpperCase(), ex = cmdFindPoint(frameId, label);
      if (ex && ex.data.on) { boardHint('Точка ' + label + ' зависит от построения — её нельзя переопределить'); return true; }
      if (ex) { const before = clone(ex); ex.data.mx = co.mx; ex.data.my = co.my; histUpd(before, ex); recomputeGeometry(); send({ action: 'element_update', element: ex }); layer.batchDraw(); }
      else cmdCreatePoint(frameId, co.mx, co.my, label);
      boardHint('Точка ' + label + ' = (' + co.mx + '; ' + co.my + ')'); return true;
    }
    // 2) Голый литерал координат: (x; y) → точка с авто-именем
    const bare = cmdParseCoords(src);
    if (bare) { const p = cmdCreatePoint(frameId, bare.mx, bare.my); boardHint('Точка ' + (p ? pointName(p) : '') + ' создана'); return true; }
    // 3) Именованная кривая/функция: name: expr
    m = src.match(/^([A-Za-z][A-Za-z0-9]*)\s*:\s*(.+)$/);
    if (m && !/^\s*\(/.test(m[2])) {
      const nm = m[1], expr = m[2].trim();
      if (!isImplicitExpr(expr) && !compileFunc(expr)) { boardHint('Не понял формулу — проверьте запись'); return true; }
      const el = isImplicitExpr(expr) ? addImplicit(frameId, expr) : addFunc(frameId, expr);
      if (el) { el.data.name = nm; send({ action: 'element_update', element: el }); }
      return true;
    }
    // 4) Вызов команды: Cmd(a, b, …)
    m = src.match(/^([A-Za-zА-Яа-я][A-Za-zА-Яа-я0-9]*)\s*\((.*)\)$/);
    if (m) {
      const cmd = CMD_ALIASES[m[1].toLowerCase()];
      if (cmd) return runNamedCommand(frameId, cmd, cmdSplitArgs(m[2]));
      // Заглавное неизвестное имя со скобками — похоже на опечатку в команде;
      // строчное (sin, cos, f, g…) — это функция y=f(x), отдаём формуле.
      if (/^[A-ZА-Я]/.test(m[1])) { boardHint('Неизвестная команда: ' + m[1]); return true; }
    }
    return false;
  }
  function feSubmit() {
    if (!activeFrameId || !feInput.value.trim()) return;
    const raw = feInput.value;
    // Сначала пробуем как команду (точка/прямая/окружность/…); если это не команда —
    // трактуем как формулу: уравнение (есть «=» или y) → неявная кривая, иначе y=f(x).
    if (runCommand(activeFrameId, raw)) { feInput.value = ''; renderFuncList(activeFrameId); return; }
    if (isImplicitExpr(raw)) addImplicit(activeFrameId, raw);
    else addFunc(activeFrameId, raw);
    feInput.value = '';
    renderFuncList(activeFrameId);
  }
  // Инструмент «Функции»: клик по окну → выделяем его и фокусируем ввод формулы.
  function handleGraphPick(w) {
    const fr = frameAtWorld(w.x, w.y, true);
    if (!fr) { boardHint('Кликните по окну, где рисовать график'); return; }
    setTool('select');
    selectOnly(fr.id); // выделение окна → показывается панель функций/алгебры
    const inp = document.getElementById('fe-input'); if (inp) { try { inp.focus(); } catch (e) {} }
    boardHint('Введите формулу, например y = k*x^2');
  }
  if (feInput) {
    feInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); feSubmit(); } });
    document.getElementById('fe-add').addEventListener('click', feSubmit);
    const feBg = document.getElementById('fe-bg');
    if (feBg) feBg.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) toggleFrameBg(b.dataset.bg); });
    const feBgCustom = document.getElementById('fe-bgcolor-custom');
    if (feBgCustom) feBgCustom.addEventListener('input', () => setFrameBgColor(feBgCustom.value));
    const feGridCustom = document.getElementById('fe-gridcolor-custom');
    if (feGridCustom) feGridCustom.addEventListener('input', () => setFrameGridColor(feGridCustom.value));
    feList.addEventListener('click', (e) => {
      const eye = e.target.closest && e.target.closest('.fe-eye');
      if (eye) { const el = elements.get(eye.getAttribute('data-eye')); if (el) { setHidden([el.id], !el.data.hidden); if (activeFrameId) renderFuncList(activeFrameId); } return; }
      const rs = e.target.closest && e.target.closest('.fe-rsense');
      if (rs) { toggleRegionSense(rs.getAttribute('data-region'), +rs.getAttribute('data-part')); return; }
      const btn = e.target.closest && e.target.closest('.fe-del');
      if (!btn) return;
      deleteWithDependents([btn.getAttribute('data-id')]); // каскадно (точка → зависимые построения)
      if (activeFrameId) renderFuncList(activeFrameId);
    });
    // Правка формулы на месте: Enter — зафиксировать (change ловит потерю фокуса).
    feList.addEventListener('keydown', (e) => {
      const ex = e.target.closest && e.target.closest('.fe-editexpr');
      if (ex && e.key === 'Enter') { e.preventDefault(); editFuncExpr(ex.dataset.id, ex.dataset.kind, ex.value, ex); }
    });
    // Живое изменение: ползунок параметра.
    feList.addEventListener('input', (e) => {
      const ex = e.target.closest && e.target.closest('.fe-editexpr');
      if (ex) { ex.classList.remove('invalid'); return; } // снимаем подсветку по ходу набора
      const rng = e.target.closest && e.target.closest('.fe-prange'); if (!rng || !activeFrameId) return;
      const fr = elements.get(activeFrameId), p = fr && fr.data.params && fr.data.params[rng.dataset.p]; if (!p) return;
      p.v = parseFloat(rng.value);
      feList.querySelectorAll('.fe-pval[data-pv="' + rng.dataset.p + '"]').forEach((s) => { s.textContent = fmtMeasure(p.v); });
      feList.querySelectorAll('.fe-prange[data-p="' + rng.dataset.p + '"]').forEach((r) => { if (r !== rng) r.value = p.v; });
      redrawFuncs(); applyConditions();
    });
    // Фиксация: параметр (окно), координата точки/радиус, границы параметра.
    feList.addEventListener('change', (e) => {
      const t = e.target;
      if (t.classList.contains('fe-editexpr')) { editFuncExpr(t.dataset.id, t.dataset.kind, t.value, t); return; }
      if (t.classList.contains('fe-condinput')) { setShowIf(t.dataset.id, t.value); return; }
      if (t.classList.contains('fe-prange')) { const fr = elements.get(activeFrameId); if (fr) send({ action: 'element_update', element: fr }); return; }
      if (t.classList.contains('fe-coord')) { algEditNum(t.dataset.id, t.dataset.axis, parseFloat(t.value)); return; }
      if (t.classList.contains('fe-pmin') || t.classList.contains('fe-pmax')) { algEditBound(activeFrameId, t.dataset.p); return; }
    });
  }

  // ── Раскадровка окна: кадры-снимки состояния матокна ───────────────────
  // Кнопка-камера фиксирует текущее содержимое окна как кадр (миниатюра-картинка
  // + снимок объектов). Клик по кадру — предпросмотр (окно не трогаем), «Вернуть»
  // загружает кадр обратно в окно. Кадры хранятся на элементе-окне (data.sb).
  const storyboardEl = document.getElementById('storyboard');
  const sbStrip = document.getElementById('sb-strip');
  const sbBar = document.getElementById('sb-bar');
  const sbIdx = document.getElementById('sb-idx');
  const sbCapIn = document.getElementById('sb-cap-in');
  let _sbFrame = null;   // id окна, чью ленту показываем
  // Идёт просмотр кадров: {frameId, index, work} — work хранит ОТЛОЖЕННУЮ
  // работу (что было в окне до первого щелчка по карточке). Пока она здесь,
  // кадры можно перещёлкивать сколько угодно, ничего не теряя.
  let sbView = null;

  function sbList(fr) { return (fr.data.sb = fr.data.sb || []); }
  // Элементы, принадлежащие окну (кроме самого окна) — их и снимаем/восстанавливаем.
  function frameContentEls(frameId) {
    const out = [];
    elements.forEach((e) => { if (e.id !== frameId && e.data && e.data.frame === frameId) out.push(e); });
    return out;
  }
  // Сколько кадров помещается в одно окно и каким должен быть их размер.
  // Сервер принимает элемент не больше 256 КБ (board/consumers.py), поэтому
  // держимся с запасом: лучше честно отказать заранее, чем потерять молча.
  // Предел был 24, потому что каждый кадр тащил PNG примерно на 11 КБ.
  // Картинки больше нет; elementFits всё равно проверяет по факту.
  const SB_MAX_FRAMES = 48;
  const EL_SAFE_BYTES = 240 * 1024;    // запас под служебную обвязку сообщения
  // Кадр описываем СЛОВАМИ, а не картинкой. PNG размывался при растяжении,
  // весил около 11 КБ на кадр и при загрузке кадра всё равно не читался: окно
  // восстанавливается из snap (элементы) и view (центр и масштаб плоскости).
  // Состав построения виден прямо из snap — оттуда описание и берём.
  const SB_WORDS = {
    segment: ['отрезок', 'отрезка', 'отрезков'],
    ray: ['луч', 'луча', 'лучей'],
    gline: ['прямая', 'прямые', 'прямых'],
    perpbis: ['серед. перпендикуляр', 'серед. перпендикуляра', 'серед. перпендикуляров'],
    perp: ['перпендикуляр', 'перпендикуляра', 'перпендикуляров'],
    parallel: ['параллельная', 'параллельные', 'параллельных'],
    bisector: ['биссектриса', 'биссектрисы', 'биссектрис'],
    conic: ['кривая', 'кривые', 'кривых'],
    circle: ['окружность', 'окружности', 'окружностей'],
    polygon: ['многоугольник', 'многоугольника', 'многоугольников'],
    regpoly: ['многоугольник', 'многоугольника', 'многоугольников'],
    vector: ['вектор', 'вектора', 'векторов'],
    region: ['область', 'области', 'областей'],
    measure: ['измерение', 'измерения', 'измерений'],
    mark: ['пометка', 'пометки', 'пометок'],
    text: ['подпись', 'подписи', 'подписей'],
    textbox: ['подпись', 'подписи', 'подписей'],
  };
  const SB_WORD_ANY = ['объект', 'объекта', 'объектов'];
  function словоЧисло(n, формы) {
    const a = n % 100, b = a % 10;
    if (a > 10 && a < 20) return формы[2];
    if (b === 1) return формы[0];
    if (b >= 2 && b <= 4) return формы[1];
    return формы[2];
  }
  // Разбор кадра: имена точек, счёт фигур по видам, формулы как есть.
  function frameParts(rec) {
    const snap = (rec && rec.snap) || [];
    const точки = [], формулы = [], счёт = [], индекс = {};
    snap.forEach((e) => {
      const d = e.data || {};
      if (e.type === 'point') { if (d.label) точки.push(d.label); return; }
      if (d.expr) { формулы.push(d.expr); return; }
      const формы = SB_WORDS[e.type] || SB_WORD_ANY;
      if (индекс[e.type] == null) { индекс[e.type] = счёт.length; счёт.push({ n: 0, формы: формы }); }
      счёт[индекс[e.type]].n++;
    });
    return { точки: точки, формулы: формулы, счёт: счёт };
  }
  // Короткие строки для карточки в полоске — чем кадры отличаются друг от друга.
  function frameLines(rec) {
    const p = frameParts(rec), out = [];
    if (p.точки.length) out.push(p.точки.slice(0, 6).join(' ') + (p.точки.length > 6 ? ' …' : ''));
    p.счёт.forEach((g) => out.push(g.n + ' ' + словоЧисло(g.n, g.формы)));
    p.формулы.forEach((f) => out.push(f));
    return out;
  }
  // Кадры, снятые до отказа от PNG, всё ещё таскают картинку в данных.
  // Выбрасываем её при первой перезаписи списка — доска худеет сама.
  function sbDropImages(list) { list.forEach((f) => { if (f && f.img) delete f.img; }); }
  // Собственный вид окна: центр и масштаб его плоскости. Это часть состояния
  // построения — без него кадр возвращает те же объекты, но в другом
  // приближении, и результат не совпадает с миниатюрой.
  function frameView(fr) {
    const d = fr.data || {};
    return { cx: d.cx, cy: d.cy, unit: d.unit };
  }
  function applyFrameView(fr, v) {
    if (!v) return false;                       // старые кадры вида не хранят
    const d = fr.data;
    let изменилось = false;
    ['cx', 'cy', 'unit'].forEach((k) => {
      if (v[k] != null && d[k] !== v[k]) { d[k] = v[k]; изменилось = true; }
    });
    return изменилось;
  }
  // Влезет ли элемент в то, что примет сервер. Проверяем ДО отправки.
  function elementFits(el) {
    try { return JSON.stringify((stripPrivate(el) || {}).data || {}).length <= EL_SAFE_BYTES; }
    catch (e) { return false; }
  }
  function frameSnap(fr) { return frameContentEls(fr.id).map((e) => clone({ id: e.id, type: e.type, z: e.z || 0, data: e.data })); }
  function captureFrame(fr) {
    const list = sbList(fr);
    if (list.length >= SB_MAX_FRAMES) {
      boardHint('В окне уже ' + SB_MAX_FRAMES + ' кадров — удалите лишние');
      return;
    }
    const before = clone(fr);
    sbDropImages(list);
    list.push({ cap: '', snap: frameSnap(fr), view: frameView(fr) });
    // Не влезли — откатываем и говорим словами. Раньше кадр «снимался», доска
    // рапортовала об успехе, а сервер молча его не принимал.
    if (!elementFits(fr)) {
      list.pop();
      boardHint('Кадр не помещается: удалите несколько прежних или уменьшите окно');
      return;
    }
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    renderStrip(fr); if (sbStrip) sbStrip.scrollLeft = sbStrip.scrollWidth;
    boardHint('Кадр ' + list.length + ' снят');
  }
  function renderStrip(fr) {
    if (!sbStrip) return;
    const list = sbList(fr);
    const показан = (sbView && sbView.frameId === fr.id) ? sbView.index : -1;
    sbStrip.innerHTML = list.map((f, i) => {
      // Состав построения — только в подсказке. Смотреть кадр надо в окне,
      // а не вычитывать из карточки, сколько там точек и прямых.
      const состав = frameLines(f).join(', ') || 'окно было пустым';
      return '<div class="sb-frame' + (i === показан ? ' sb-on' : '') + '" draggable="true" data-i="' + i + '"'
        + ' title="' + escapeHtml('Кадр ' + (i + 1) + ': ' + состав) + '">'
        + '<span class="sb-num">' + (i + 1) + '</span>'
        + '<span class="sb-cap">' + escapeHtml(f.cap || '') + '</span>'
        + '<button class="sb-del" data-i="' + i + '" title="Удалить кадр">×</button></div>';
    }).join('');
  }
  function updateStoryboard() {
    if (!storyboardEl) return;
    let fr = (tool === 'select' && activeFrameId) ? elements.get(activeFrameId) : null;
    // Идёт просмотр кадра — лента остаётся на экране, каким бы инструментом ни
    // работали. Раньше «нет ленты» означало «человек ушёл из окна», и просмотр
    // обрывался от любого действия: взял карандаш дорисовать в кадре — окно
    // тут же сбросилось на отложенную работу.
    if (!fr && sbView) fr = elements.get(sbView.frameId) || null;
    if (!fr || fr.type !== 'frame') { storyboardEl.hidden = true; sbLeaveView(true); _sbFrame = null; return; }
    storyboardEl.hidden = false;
    if (_sbFrame !== fr.id) { sbLeaveView(true); _sbFrame = fr.id; renderStrip(fr); }
    positionStoryboard(fr);

  }
  function positionStoryboard(fr) {
    const s = stage.scaleX();
    const sx = fr.data.x * s + stage.x();
    const sy = (fr.data.y + fr.data.height) * s + stage.y() + STAGE_TOP + 8; // сразу под окном
    storyboardEl.style.left = Math.max(8, Math.min(window.innerWidth - 360, sx)) + 'px';
    storyboardEl.style.top = sy + 'px';
  }
  // ── Просмотр кадров ───────────────────────────────────────────────────
  // Кадр показываем В САМОМ ОКНЕ: то же построение, тот же масштаб. Так его
  // видно по-настоящему, а не по описанию или мутной картинке.
  //
  // В истории отмены просмотр НЕ отражаем: это навигация, а не правка. Поэтому
  // на время просмотра отмена выключена (см. doUndo) — история относится к
  // отложенной работе, и мешать одно с другим нельзя.
  function sbApplyState(fr, state) {
    if (!state) return;
    frameContentEls(fr.id).forEach((e) => { send({ action: 'element_delete', id: e.id }); removeNode(e.id); });
    if (applyFrameView(fr, state.view)) { upsertNode(fr); send({ action: 'element_update', element: fr }); }
    (state.snap || []).forEach((sd) => { const el = clone(sd); upsertNode(el); send({ action: 'element_add', element: el }); });
    recomputeGeometry(); layer.batchDraw();
  }
  function sbSnapshot(fr) { return { snap: frameSnap(fr), view: frameView(fr) }; }
  // Правки, сделанные во время просмотра, сохраняем в САМ кадр — при переходе
  // к другому кадру и при выходе из просмотра. Кадры от этого работают как
  // слайды: открыл, поправил, пошёл дальше, ничего не нажимая.
  function sbSyncViewed(fr) {
    if (!sbView || !fr) return;
    const list = sbList(fr), prev = list[sbView.index];
    if (!prev) return;
    const стало = sbSnapshot(fr);
    const было = { snap: prev.snap || [], view: prev.view };
    if (JSON.stringify(стало) === JSON.stringify(было)) return;   // ничего не меняли
    const before = clone(fr);
    list[sbView.index] = { cap: prev.cap || '', snap: стало.snap, view: стало.view };
    if (!elementFits(fr)) {
      list[sbView.index] = prev;
      boardHint('Правки не помещаются в кадр — упростите построение или удалите лишние кадры');
      return;
    }
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    renderStrip(fr);
    boardHint('Правки сохранены в кадр ' + (sbView.index + 1));
  }

  function sbShowFrame(fr, i) {
    const list = sbList(fr); if (i < 0 || i >= list.length) return;
    // Первый щелчок откладывает текущую работу. Дальше её не трогаем, сколько
    // бы кадров ни пролистали.
    if (!sbView || sbView.frameId !== fr.id) sbView = { frameId: fr.id, work: sbSnapshot(fr) };
    else if (sbView.index !== i) sbSyncViewed(fr);   // уходим с кадра — забираем правки
    sbView.index = i;
    sbApplyState(fr, list[i]);
    renderStrip(fr); sbShowBar(fr);
    boardHint('Кадр ' + (i + 1) + '. Правки уйдут в него; «К работе» вернёт вашу работу');
  }
  function sbShowBar(fr) {
    if (!sbBar) return;
    const list = sbList(fr);
    sbBar.hidden = !sbView;
    if (!sbView) return;
    sbIdx.textContent = 'Кадр ' + (sbView.index + 1) + ' / ' + list.length;
    sbCapIn.value = (list[sbView.index] || {}).cap || '';
  }
  // Уходим из просмотра. вернуть=true — окно возвращается к отложенной работе.
  function sbLeaveView(вернуть) {
    if (!sbView) return;
    const fr = elements.get(sbView.frameId), work = sbView.work;
    sbSyncViewed(fr);                 // правки в кадре не теряем
    sbView = null;
    if (sbBar) sbBar.hidden = true;
    if (fr) { if (вернуть) sbApplyState(fr, work); renderStrip(fr); }
  }
  // «Оставить»: продолжаем работу с показанного кадра. В отмену кладём один
  // общий шаг — разницу между отложенной работой и тем, что сейчас в окне.
  function sbKeepFrame() {
    if (!sbView) return;
    const fr = elements.get(sbView.frameId); if (!fr) { sbView = null; return; }
    const было = sbView.work, стало = sbSnapshot(fr), ops = [];
    const прежние = new Map((было.snap || []).map((e) => [e.id, e]));
    const текущие = new Map((стало.snap || []).map((e) => [e.id, e]));
    прежние.forEach((e, id) => { if (!текущие.has(id)) ops.push({ kind: 'del', el: clone(e) }); });
    текущие.forEach((e, id) => {
      const p = прежние.get(id);
      if (!p) ops.push({ kind: 'add', el: clone(e) });
      else if (JSON.stringify(p.data) !== JSON.stringify(e.data)) ops.push({ kind: 'upd', before: clone(p), after: clone(e) });
    });
    if (JSON.stringify(было.view) !== JSON.stringify(стало.view)) {
      const b = clone(fr); applyFrameView(b, было.view);
      ops.push({ kind: 'upd', before: b, after: clone(fr) });
    }
    const n = sbView.index + 1;
    histBatch(ops);
    sbSyncViewed(fr);
    sbLeaveView(false);
    boardHint('Работаем дальше с кадра ' + n);
  }
  function sbNav(delta) {
    if (!sbView) return; const fr = elements.get(sbView.frameId); if (!fr) return;
    const list = sbList(fr); if (!list.length) return;
    sbShowFrame(fr, Math.max(0, Math.min(list.length - 1, sbView.index + delta)));
  }
  function sbDeleteFrame(fr, i) {
    const list = sbList(fr); if (i < 0 || i >= list.length) return;
    const before = clone(fr); list.splice(i, 1);
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    renderStrip(fr);
    if (sbView && sbView.frameId === fr.id) {
      if (!list.length) sbLeaveView(true);
      else { sbView.index = Math.min(sbView.index, list.length - 1); sbShowFrame(fr, sbView.index); }
    }
  }
  const _sbCap = document.getElementById('sb-cap');
  if (_sbCap) _sbCap.addEventListener('click', () => { const fr = elements.get(_sbFrame); if (fr) captureFrame(fr); });
  if (sbStrip) sbStrip.addEventListener('click', (e) => {
    const fr = elements.get(_sbFrame); if (!fr) return;
    const del = e.target.closest('.sb-del'); if (del) { e.stopPropagation(); sbDeleteFrame(fr, +del.dataset.i); return; }
    const cell = e.target.closest('.sb-frame'); if (cell) sbShowFrame(fr, +cell.dataset.i);
  });
  // Перетаскивание миниатюр — смена порядка кадров.
  function sbMoveFrame(from, to) {
    const fr = elements.get(_sbFrame); if (!fr) return;
    const list = sbList(fr);
    if (from < 0 || to < 0 || from >= list.length || to >= list.length || from === to) return;
    const before = clone(fr);
    const item = list.splice(from, 1)[0]; list.splice(to, 0, item);
    histUpd(before, fr); send({ action: 'element_update', element: fr });
    sbLeaveView(true); renderStrip(fr);
  }
  let sbDragFrom = null;
  if (sbStrip) {
    sbStrip.addEventListener('dragstart', (e) => { const c = e.target.closest('.sb-frame'); if (!c) return; sbDragFrom = +c.dataset.i; c.classList.add('sb-dragging'); if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'; });
    sbStrip.addEventListener('dragend', (e) => { const c = e.target.closest('.sb-frame'); if (c) c.classList.remove('sb-dragging'); sbDragFrom = null; });
    sbStrip.addEventListener('dragover', (e) => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'; });
    sbStrip.addEventListener('drop', (e) => { e.preventDefault(); const c = e.target.closest('.sb-frame'); if (!c || sbDragFrom === null) return; sbMoveFrame(sbDragFrom, +c.dataset.i); sbDragFrom = null; });
  }
  (function () {
    const on = (id, fn) => { const b = document.getElementById(id); if (b) b.addEventListener('click', fn); };
    on('sb-prev', () => sbNav(-1));
    on('sb-next', () => sbNav(1));
    on('sb-back', () => sbLeaveView(true));
    on('sb-keep', sbKeepFrame);
    if (sbCapIn) sbCapIn.addEventListener('change', () => {
      if (!sbView) return; const fr = elements.get(sbView.frameId); if (!fr) return;
      const list = sbList(fr); if (!list[sbView.index]) return;
      const before = clone(fr); list[sbView.index].cap = sbCapIn.value;
      histUpd(before, fr); send({ action: 'element_update', element: fr }); renderStrip(fr);
    });
  })();

  // ── Рамочное выделение (как выбор файлов в папке) ──────────────────────
  // Тянем по пустому месту → выделяем все объекты, попавшие в рамку. Shift —
  // добавить к текущему выделению. Работаем в мировых координатах (как позиции
  // объектов), рамку рисуем в том же слое.
  let marquee = null;
  const marqueeRect = new Konva.Rect({
    stroke: '#4d7cfe', strokeWidth: 1, dash: [4, 4],
    fill: 'rgba(77,124,254,0.10)', visible: false, listening: false,
  });
  layer.add(marqueeRect);

  function startMarquee(e) {
    const w = worldPoint();
    marquee = { x0: w.x, y0: w.y, additive: isAddKey(e.evt), moved: false };
    marqueeRect.moveToTop();
    // Пока тянем рамку — DOM-текст/виджеты «прозрачны» для мыши, иначе указатель
    // цепляется за них, события не доходят до холста и рамка «спотыкается».
    widgetLayerEl.classList.add('marquee-thru');
  }
  function updateMarquee() {
    const w = worldPoint();
    const x = Math.min(marquee.x0, w.x), y = Math.min(marquee.y0, w.y);
    const width = Math.abs(w.x - marquee.x0), height = Math.abs(w.y - marquee.y0);
    const thr = 3 / stage.scaleX(); // порог «движения» ≈ 3px экрана
    if (width > thr || height > thr) marquee.moved = true;
    marqueeRect.setAttrs({ x, y, width, height, strokeWidth: 1 / stage.scaleX(), visible: marquee.moved });
    layer.batchDraw();
  }
  function endMarquee() {
    widgetLayerEl.classList.remove('marquee-thru'); // вернуть интерактивность DOM-объектам
    if (!marquee) return;
    const m = marquee;
    marquee = null;
    marqueeRect.visible(false);
    if (m.moved) {
      const box = { x: marqueeRect.x(), y: marqueeRect.y(), width: marqueeRect.width(), height: marqueeRect.height() };
      if (revealHidden && !viewOnly) toggleHiddenInBox(box);
      else applyMarquee(box, m.additive);
    } else if (!m.additive) {
      clearSelection(); // клик по пустому без движения — снять выделение
    }
    layer.batchDraw();
  }
  // Страховка: любое отпускание мыши возвращает DOM-объектам интерактивность.
  window.addEventListener('mouseup', () => { if (widgetLayerEl.classList.contains('marquee-thru')) widgetLayerEl.classList.remove('marquee-thru'); });
  function rectsIntersect(a, b) {
    return !(b.x > a.x + a.width || b.x + b.width < a.x || b.y > a.y + a.height || b.y + b.height < a.y);
  }
  function applyMarquee(box, additive) {
    if (!additive) selected.clear();
    const picked = new Set();
    nodes.forEach((node, id) => {
      const el = elements.get(id); if (el && el.data.hidden && !revealHidden) return; // скрытые не выделяем
      const b = node.getClientRect({ relativeTo: layer });
      if (rectsIntersect(box, b)) {
        groupMembers(id).forEach((m) => { if (nodes.has(m)) picked.add(m); });
      }
    });
    // DOM-объекты (текст/виджеты) — их нет в nodes; берём по мировой рамке обёртки.
    widgetItems.forEach((it, id) => {
      const d = it.el.data, w = it.wrapper.offsetWidth || 0, h = it.wrapper.offsetHeight || 0;
      if (!w && !h) return;
      if (rectsIntersect(box, { x: d.x || 0, y: d.y || 0, width: w, height: h })) picked.add(id);
    });
    picked.forEach((id) => selected.add(id));
    refreshTransformer();
  }
  // ── Ластик: стирает только карандаш и маркер (freehand) ────────────────
  // Тянешь ластиком — точки штриха в радиусе удаляются, штрих распадается на
  // уцелевшие куски (частичное стирание). Прочие объекты не трогаются. Весь
  // проход одного «мазка» — один шаг отмены (histBatch).
  // Два ластика: eraser_full — стирает мазок целиком; eraser_fine — «точный»,
  // вырезает только точки в радиусе, штрих распадается на уцелевшие куски.
  let eraserActive = false, eraserOps = null, eraserRadius = 13, lastEraseW = null; // радиус в px экрана
  function eraserDown() { closeToolPanels(); eraserActive = true; eraserOps = []; lastEraseW = worldPoint(); eraserAt(lastEraseW); }
  function eraserMove() {
    if (!eraserActive) return;
    const w = worldPoint(), r = eraserRadius / stage.scaleX();
    // Досэмплируем путь ластика между кадрами (быстрое движение иначе оставляет пропуски).
    if (lastEraseW) {
      const dx = w.x - lastEraseW.x, dy = w.y - lastEraseW.y, dist = Math.hypot(dx, dy);
      const steps = Math.floor(dist / Math.max(1, r * 0.7));
      for (let k = 1; k <= steps; k++) { const t = k / (steps + 1); eraserAt({ x: lastEraseW.x + dx * t, y: lastEraseW.y + dy * t }); }
    }
    eraserAt(w); lastEraseW = w;
  }
  function eraserUp() { if (!eraserActive) return; eraserActive = false; lastEraseW = null; if (eraserOps && eraserOps.length) histBatch(eraserOps); eraserOps = null; }
  // Расстояние от точки до отрезка (для попадания ластика по линии, а не только по её вершинам).
  function distPtSeg(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
    if (l2 === 0) return Math.hypot(px - ax, py - ay);
    let t = ((px - ax) * dx + (py - ay) * dy) / l2; t = t < 0 ? 0 : t > 1 ? 1 : t;
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }
  // Уплотнить ломаную: добавить промежуточные точки, чтобы шаг не превышал maxStep.
  function densifyPts(pts, maxStep) {
    if (pts.length < 4) return pts.slice();
    const out = [pts[0], pts[1]];
    for (let i = 0; i + 3 < pts.length; i += 2) {
      const ax = pts[i], ay = pts[i + 1], bx = pts[i + 2], by = pts[i + 3];
      const n = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay) / maxStep));
      for (let k = 1; k <= n; k++) { const t = k / n; out.push(ax + (bx - ax) * t, ay + (by - ay) * t); }
    }
    return out;
  }
  function eraserAt(w) {
    const r = eraserRadius / stage.scaleX(), full = (tool === 'eraser_full');
    const list = []; elements.forEach((el) => { if (el.type === 'freehand') list.push(el); });
    let changed = false;
    list.forEach((el) => {
      const d = el.data, ox = d.x || 0, oy = d.y || 0, pts = d.points || [];
      if (full) {
        // Попадание по ЛИНИИ (любому её отрезку), а не только по вершинам.
        let hit = pts.length >= 2 && Math.hypot(ox + pts[0] - w.x, oy + pts[1] - w.y) <= r;
        for (let i = 0; i + 3 < pts.length && !hit; i += 2) {
          if (distPtSeg(w.x, w.y, ox + pts[i], oy + pts[i + 1], ox + pts[i + 2], oy + pts[i + 3]) <= r) hit = true;
        }
        if (!hit) return;
        changed = true; eraserOps.push({ kind: 'del', el: clone(el) });
        removeNode(el.id); send({ action: 'element_delete', id: el.id });
        return;
      }
      // Точный ластик: уплотняем ломаную, чтобы резать и посреди длинного отрезка.
      const dp = densifyPts(pts, Math.max(1.5, r * 0.5));
      const runs = []; let cur = [];
      for (let i = 0; i < dp.length; i += 2) {
        const hit = Math.hypot(ox + dp[i] - w.x, oy + dp[i + 1] - w.y) <= r;
        if (hit) { if (cur.length >= 4) runs.push(cur); cur = []; }
        else cur.push(dp[i], dp[i + 1]);
      }
      if (cur.length >= 4) runs.push(cur);
      const survived = runs.reduce((s, run) => s + run.length, 0);
      if (survived === dp.length) return; // штрих не задет
      changed = true;
      if (!runs.length) {                     // от штриха ничего не осталось
        eraserOps.push({ kind: 'del', el: clone(el) });
        removeNode(el.id); send({ action: 'element_delete', id: el.id });
        return;
      }
      // Первый уцелевший кусок ПЕРЕПИСЫВАЕМ на месте. Раньше штрих удалялся
      // целиком и куски создавались заново: у себя это одна перерисовка и
      // незаметно, а второму участнику приходят два разных сообщения, и между
      // ними штрих успевает пропасть — это и мерцало.
      const было = clone(el);
      el.data.points = runs[0];
      upsertNode(el); send({ action: 'element_update', element: stripPrivate(el) });
      eraserOps.push({ kind: 'upd', before: было, after: clone(el) });
      for (let k = 1; k < runs.length; k++) {  // разрез посередине — добавочные куски
        const nel = { id: uuid(), type: 'freehand', z: el.z, data: Object.assign({}, clone(d), { points: runs[k] }) };
        upsertNode(nel); send({ action: 'element_add', element: nel });
        eraserOps.push({ kind: 'add', el: clone(nel) });
      }
    });
    if (changed) layer.batchDraw();
  }
  // Кольцо-подсказка размера ластика под курсором.
  const eraserRing = document.createElement('div'); eraserRing.className = 'eraser-ring'; eraserRing.style.display = 'none';
  cursorLayerEl.appendChild(eraserRing);
  function isEraser(t) { return t === 'eraser_full' || t === 'eraser_fine'; }
  function positionEraserRing() {
    if (!isEraser(tool)) { eraserRing.style.display = 'none'; return; }
    const w = worldPoint(); const d = eraserRadius * 2;
    eraserRing.style.display = 'block';
    eraserRing.style.width = d + 'px'; eraserRing.style.height = d + 'px';
    eraserRing.style.left = (w.x * stage.scaleX() + stage.x()) + 'px';
    eraserRing.style.top = (w.y * stage.scaleY() + stage.y()) + 'px';
  }
  function updateEraserPanel() {
    const old = document.getElementById('eraser-panel'); if (old) old.hidden = true; // старая панель заменена на #draw-cfg в тулбаре
    eraserRing.style.display = 'none';
    syncDrawFlyout();
  }

  // ── Контекстная настройка карандаша/маркера/ластика ──────────────────────
  // 3 пресета-кружка (каждый — толщина+цвет+прозрачность), «своя» толщина/цвет/
  // прозрачность активного, для ластика — радиус. Демо рисуется прямо в кружке.
  // Ключ поднят до v2 вместе со сменой толщин: сохранённые наборы берутся
  // ВМЕСТО умолчаний, и без этого новые толщины никто бы не увидел.
  const DP_STORE = 'board_draw_presets_v2';
  const DP_DEFAULTS = {
    // Толщины смещены в тонкую сторону: прежние 2 / 5 / 10 писали слишком
    // жирно. Соотношение 1 : 2 : 4 сохранено, чтобы три кружка оставались
    // различимы на глаз.
    pen: { active: 0, presets: [{ w: 1.5, c: '#1f2937' }, { w: 3, c: '#ef4444' }, { w: 6, c: '#3b82f6' }] },
    // Маркер тоньше 12 не делаем: выделитель должен перекрывать строку текста.
    marker: { active: 0, presets: [{ w: 12, c: '#ffe14a', o: 0.4 }, { w: 18, c: '#8ef58e', o: 0.4 }, { w: 26, c: '#7cc4ff', o: 0.4 }] },
    eraser: { active: 0, presets: [{ r: 10 }, { r: 22 }, { r: 40 }] },
    // Линия, стрелка, разделитель — один общий набор: рисуют они одним и тем же
    // пером, и держать им разные настройки значило бы путать самого себя.
    line: { active: 0, presets: [{ w: 1.5, c: '#1f2937' }, { w: 3, c: '#ef4444' }, { w: 5, c: '#3b82f6' }] },
    // Прямоугольник, эллипс и все фигуры — контур.
    shape: { active: 0, presets: [{ w: 1.5, c: '#1f2937' }, { w: 2.5, c: '#ef4444' }, { w: 4, c: '#3b82f6' }] },
  };
  // Сохранённые настройки могли быть записаны до появления новых групп —
  // недостающие ключи добираем из умолчаний, а не сбрасываем всё.
  function loadDrawCfg() {
    const out = clone(DP_DEFAULTS);
    try {
      const s = JSON.parse(localStorage.getItem(DP_STORE));
      if (s) Object.keys(out).forEach((k) => { if (s[k] && s[k].presets) out[k] = s[k]; });
    } catch (e) {}
    return out;
  }
  let drawCfg = loadDrawCfg();
  function saveDrawCfg() { try { localStorage.setItem(DP_STORE, JSON.stringify(drawCfg)); } catch (e) {} }
  let markerColor = drawCfg.marker.presets[drawCfg.marker.active].c;
  let markerWidth = drawCfg.marker.presets[drawCfg.marker.active].w;
  let markerOpacity = drawCfg.marker.presets[drawCfg.marker.active].o;
  const DP_SW = {
    pen: ['#1f2937', '#6b7280', '#ef4444', '#f97316', '#f59e0b', '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899', '#ffffff'],
    marker: ['#ffe14a', '#ffb14a', '#8ef58e', '#7cc4ff', '#ff9ecb', '#c9a7ff'],
    line: ['#1f2937', '#6b7280', '#ef4444', '#f97316', '#f59e0b', '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899', '#ffffff'],
    shape: ['#1f2937', '#6b7280', '#ef4444', '#f97316', '#f59e0b', '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899', '#ffffff'],
  };
  function drawKey(t) {
    if (t === 'pen') return 'pen';
    if (t === 'marker') return 'marker';
    if (isEraser(t)) return 'eraser';
    if (t === 'line' || t === 'arrow' || t === 'divider') return 'line';
    if (t === 'rect' || t === 'ellipse' || SHAPE_TOOLS[t]) return 'shape';
    return null;
  }
  // Группа на панели, к которой относится текущий инструмент — туда и
  // переезжает блок настроек.
  function cfgGroupEl() {
    if (!drawKey(tool)) return null;
    const b = document.querySelector('#board-toolbar .tool-flyout .tool[data-tool="' + tool + '"]');
    return b ? b.closest('.tool-group') : null;
  }
  function dpActive(key) { const c = drawCfg[key]; return c.presets[c.active]; }
  function applyDrawPreset(key) {
    const p = dpActive(key);
    if (key === 'pen') {
      strokeColor = p.c; strokeWidth = p.w;
      if (colorBtn) colorBtn.style.background = p.c;
      const sw = document.getElementById('stroke-width'); if (sw) sw.value = p.w;
    } else if (key === 'line' || key === 'shape') {
      // Линии и фигуры рисуются теми же двумя глобальными значениями, что и
      // карандаш, — поэтому больше нигде править ничего не нужно.
      strokeColor = p.c; strokeWidth = p.w;
      const cb = document.getElementById('color-btn'); if (cb) cb.style.background = p.c;
      const sw2 = document.getElementById('stroke-width'); if (sw2) sw2.value = p.w;
    } else if (key === 'marker') { markerColor = p.c; markerWidth = p.w; markerOpacity = p.o; }
    else if (key === 'eraser') { eraserRadius = p.r; }
  }
  function dpDemoHtml(key, p) {
    if (key === 'eraser') { const d = Math.max(8, Math.min(30, Math.round(p.r * 0.7))); return '<span class="dp-ring" style="width:' + d + 'px;height:' + d + 'px"></span>'; }
    if (key === 'line') {
      const h = Math.max(2, Math.min(10, p.w));
      return '<span class="dp-line" style="height:' + h + 'px;background:' + p.c + '"></span>';
    }
    if (key === 'shape') {
      const b = Math.max(1, Math.min(5, p.w));
      return '<span class="dp-sq" style="border-width:' + b + 'px;border-color:' + p.c + '"></span>';
    }
    const d = Math.max(4, Math.min(28, p.w)), op = key === 'marker' ? p.o : 1;
    return '<span class="dp-dot" style="width:' + d + 'px;height:' + d + 'px;background:' + p.c + ';opacity:' + op + '"></span>';
  }
  // Кружки-пресеты (вертикально). Клик — выбрать пресет и открыть панель настроек справа.
  function renderDrawPanel(key) {
    const cfg = drawCfg[key];
    const presetsEl = document.getElementById('dp-presets'); presetsEl.innerHTML = '';
    cfg.presets.forEach((p, i) => {
      const b = document.createElement('button'); b.className = 'dp-preset' + (i === cfg.active ? ' on' : ''); b.title = 'Пресет ' + (i + 1);
      b.innerHTML = dpDemoHtml(key, p);
      b.addEventListener('click', (ev) => { ev.stopPropagation(); cfg.active = i; applyDrawPreset(key); saveDrawCfg(); renderDrawPanel(key); const nb = document.querySelectorAll('#dp-presets .dp-preset')[i] || b; openDpPop(nb, key); });
      presetsEl.appendChild(b);
    });
  }
  function dpUpdateActiveDemo(key) { const p = dpActive(key); const btn = document.querySelectorAll('#dp-presets .dp-preset')[drawCfg[key].active]; if (btn) btn.innerHTML = dpDemoHtml(key, p); }
  // Панель выбора толщины/цвета/прозрачности (или радиуса) — всплывает справа от кружка.
  function renderDpPop(key) {
    const p = dpActive(key);
    const thick = document.getElementById('dp-thick'), tval = document.getElementById('dp-thick-val'), tlbl = document.getElementById('dp-thick-lbl');
    if (key === 'eraser') { tlbl.textContent = 'Радиус'; thick.min = 5; thick.step = 1; thick.max = 80; thick.value = p.r; tval.textContent = p.r; }
    else { tlbl.textContent = 'Толщина'; thick.min = 0.5; thick.step = 0.5; thick.max = (key === 'marker' ? 40 : 24); thick.value = p.w; tval.textContent = p.w; }
    // Прозрачность есть только у маркера; у остальных строку прячем ниже.
    const orow = document.getElementById('dp-opacity-row'); orow.style.display = key === 'marker' ? 'flex' : 'none';
    if (key === 'marker') { const o = document.getElementById('dp-opacity'), ov = document.getElementById('dp-opacity-val'); o.value = Math.round(p.o * 100); ov.textContent = Math.round(p.o * 100) + '%'; }
    const colorsEl = document.getElementById('dp-colors'); colorsEl.style.display = key === 'eraser' ? 'none' : 'flex';
    if (key !== 'eraser') {
      colorsEl.innerHTML = '';
      DP_SW[key].forEach((c) => { const s = document.createElement('div'); s.className = 'dp-sw' + (c.toLowerCase() === String(p.c).toLowerCase() ? ' on' : ''); s.style.background = c; s.title = c; s.addEventListener('click', () => { p.c = c; applyDrawPreset(key); saveDrawCfg(); renderDpPop(key); dpUpdateActiveDemo(key); }); colorsEl.appendChild(s); });
      const add = document.createElement('button'); add.className = 'dp-add'; add.textContent = '+'; add.title = 'Свой цвет';
      add.addEventListener('click', () => { const n = document.getElementById('dp-native'); n.value = (/^#[0-9a-f]{6}$/i.test(p.c) ? p.c : '#3b82f6'); dpNativeKey = key; n.click(); });
      colorsEl.appendChild(add);
    }
  }
  function positionDpPop(circleEl) {
    const pop = document.getElementById('dp-pop'), e = drawGroupEls(); if (!e) return;
    const fr = e.fly.getBoundingClientRect(), r = circleEl.getBoundingClientRect();
    pop.style.left = (fr.right + 8) + 'px';
    const ph = pop.offsetHeight || 150, vh = window.innerHeight;
    let top = r.top - 8; if (top + ph > vh - 8) top = vh - ph - 8;
    pop.style.top = Math.max(8, top) + 'px';
  }
  function openDpPop(circleEl, key) { const pop = document.getElementById('dp-pop'); renderDpPop(key); pop.hidden = false; positionDpPop(circleEl); }
  function closeDpPop() { const pop = document.getElementById('dp-pop'); if (pop) pop.hidden = true; }
  function drawGroupEls() {
    const g = cfgGroupEl() || document.querySelector('.tool-group[data-group="draw"]');
    return g ? { g, fly: g.querySelector('.tool-flyout') } : null;
  }
  function isDrawToolActive() { return !!drawKey(tool) || tool === 'laser' || tool === 'lasso'; }
  function positionDrawFlyout(g, fly) {
    const r = g.getBoundingClientRect();
    fly.style.left = (r.right + 10) + 'px';
    fly.classList.add('open');
    const fh = fly.offsetHeight, vh = window.innerHeight;
    let top = r.top; if (top + fh > vh - 8) top = Math.max(8, vh - fh - 8);
    fly.style.top = top + 'px';
  }
  // Меню рисования держим открытым, пока активен инструмент рисования; блок настроек
  // #draw-cfg показываем под лассо для карандаша/маркера/ластика.
  function syncDrawFlyout() {
    closeDpPop(); // при смене инструмента панель настроек закрываем
    const cfg = document.getElementById('draw-cfg');
    const key = drawKey(tool);
    const e = drawGroupEls(); if (!e) return;
    if (isDrawToolActive()) {
      if (cfg) {
        cfg.hidden = !key;
        // Блок настроек ОДИН на всю панель и переезжает к активной группе:
        // открыта всегда одна, так что второго не требуется.
        if (key && cfg.parentElement !== e.fly) e.fly.appendChild(cfg);
        if (key) { applyDrawPreset(key); renderDrawPanel(key); }
      }
      positionDrawFlyout(e.g, e.fly);
    } else {
      if (cfg) cfg.hidden = true;
      e.fly.classList.remove('open');
    }
  }
  let dpNativeKey = null;
  (function wireDrawPanel() {
    const thick = document.getElementById('dp-thick'); if (!thick) return;
    thick.addEventListener('input', (e) => {
      // parseFloat, а не parseInt: толщины теперь дробные (1.5, 2.5), и целое
      // округление съело бы их при первом же касании ползунка.
      // Если сейчас не рисующий инструмент — правим карандаш. На компьютере
      // этого не случается (панель открыта только при рисующем), а вот в
      // мобильном листе ползунок «Толщина» доступен всегда, и молчаливое
      // бездействие выглядело бы поломкой.
      const key = drawKey(tool) || 'pen'; const p = dpActive(key); const v = parseFloat(e.target.value);
      if (key === 'eraser') p.r = v; else p.w = v;
      document.getElementById('dp-thick-val').textContent = v; applyDrawPreset(key); saveDrawCfg();
      const btn = document.querySelectorAll('#dp-presets .dp-preset')[drawCfg[key].active]; if (btn) btn.innerHTML = dpDemoHtml(key, p);
    });
    document.getElementById('dp-opacity').addEventListener('input', (e) => {
      if (tool !== 'marker') return; const p = dpActive('marker'); const v = parseInt(e.target.value, 10) / 100; p.o = v;
      document.getElementById('dp-opacity-val').textContent = Math.round(v * 100) + '%'; applyDrawPreset('marker'); saveDrawCfg();
      const btn = document.querySelectorAll('#dp-presets .dp-preset')[drawCfg.marker.active]; if (btn) btn.innerHTML = dpDemoHtml('marker', p);
    });
    const nat = document.getElementById('dp-native');
    nat.addEventListener('input', (e) => { if (!dpNativeKey) return; const p = dpActive(dpNativeKey); p.c = e.target.value; applyDrawPreset(dpNativeKey); saveDrawCfg(); renderDpPop(dpNativeKey); dpUpdateActiveDemo(dpNativeKey); });
    // Клик мимо панели настроек (и не по кружку) — закрыть её.
    document.addEventListener('mousedown', (ev) => {
      const pop = document.getElementById('dp-pop'); if (!pop || pop.hidden) return;
      if (ev.target && ev.target.closest && (ev.target.closest('#dp-pop') || ev.target.closest('.dp-preset'))) return;
      closeDpPop();
    });
  })();

  // ── Лассо: выделение произвольным контуром ─────────────────────────────
  let lassoActive = false, lassoPts = null;
  const lassoLine = new Konva.Line({ stroke: '#4d7cfe', strokeWidth: 1, dash: [4, 4], closed: true, fill: 'rgba(77,124,254,0.10)', listening: false, visible: false });
  layer.add(lassoLine);
  function lassoDown() { const w = worldPoint(); if (!w) return; lassoActive = true; lassoPts = [w.x, w.y]; lassoLine.points(lassoPts); lassoLine.visible(true); lassoLine.moveToTop(); layer.batchDraw(); }
  function lassoMove() { if (!lassoActive) return; const w = worldPoint(); if (!w) return; lassoPts.push(w.x, w.y); lassoLine.points(lassoPts); lassoLine.strokeWidth(1 / stage.scaleX()); layer.batchDraw(); }
  function lassoUp() {
    if (!lassoActive) return; lassoActive = false; lassoLine.visible(false);
    const poly = lassoPts; lassoPts = null; layer.batchDraw();
    if (poly && poly.length >= 6) applyLasso(poly);
  }
  function pointInPoly(x, y, poly) {
    let inside = false; const n = poly.length / 2;
    for (let i = 0, j = n - 1; i < n; j = i++) {
      const xi = poly[2 * i], yi = poly[2 * i + 1], xj = poly[2 * j], yj = poly[2 * j + 1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }
  function applyLasso(poly) {
    const picked = new Set();
    nodes.forEach((node, id) => {
      const el = elements.get(id); if (!el || (el.data.hidden && !revealHidden)) return;
      const b = node.getClientRect({ relativeTo: layer });
      if (pointInPoly(b.x + b.width / 2, b.y + b.height / 2, poly)) groupMembers(id).forEach((m) => { if (nodes.has(m)) picked.add(m); });
    });
    setTool('select'); // после обводки — режим выделения, чтобы двигать/удалять
    clearSelection();
    picked.forEach((id) => selected.add(id));
    refreshTransformer();
    boardHint(picked.size ? ('Выделено объектов: ' + picked.size) : 'Внутри контура ничего нет');
  }

  // Все объекты той же группы (или сам объект, если он не в группе).
  function groupMembers(id) {
    const el = elements.get(id);
    const gid = el && el.data && el.data.groupId;
    if (!gid) return [id];
    return Array.from(elements.values())
      .filter((e) => e.data && e.data.groupId === gid)
      .map((e) => e.id);
  }
  // Выделять умеем и объекты холста (nodes), и DOM-объекты — текст, стикеры,
  // таблицы, встроенные страницы (widgetItems). Раньше здесь проверялся только
  // nodes, поэтому кликом такие объекты не выделялись вовсе: сработать могло
  // лишь рамочное выделение, которое их учитывает отдельно.
  function selectable(mid) { return nodes.has(mid) || widgetItems.has(mid); }
  // «Добавить к выделению»: Shift, Ctrl или Cmd. Ctrl привычен по проводнику и
  // офисным программам, Cmd — то же самое на маке. Осторожно: Shift отдельно
  // используется при РИСОВАНИИ (привязка к 45°), поэтому там его не трогаем.
  function isAddKey(ev) { return !!(ev && (ev.shiftKey || ev.ctrlKey || ev.metaKey)); }
  function selectOnly(id) {
    selected.clear();
    groupMembers(id).forEach((mid) => { if (selectable(mid)) selected.add(mid); });
    const el = elements.get(id);
    activeFrameId = (el && el.type === 'frame') ? id : null; // активное окно
    refreshTransformer();
  }
  // Выделить всё: скрытое берём только когда включён режим скрытия (иначе
  // человек «выделит» то, чего не видит), окна пропускаем — это вместилища.
  function selectAllElements() {
    selected.clear();
    const takeable = (el) => el && el.type !== 'frame' && !(el.data && el.data.hidden && !revealHidden);
    nodes.forEach((node, id) => { if (takeable(elements.get(id))) selected.add(id); });
    widgetItems.forEach((it, id) => { if (takeable(it.el)) selected.add(id); });
    refreshTransformer();
    boardHint(selected.size ? ('Выделено объектов: ' + selected.size) : 'Выделять нечего');
  }
  function toggleSelect(id) {
    const members = groupMembers(id).filter(selectable);
    if (!members.length) return;
    const allSelected = members.every((mid) => selected.has(mid));
    members.forEach((mid) => { if (allSelected) selected.delete(mid); else selected.add(mid); });
    refreshTransformer();
  }
  function groupSelected() {
    if (selected.size < 2) return;
    const gid = 'g' + uuid();
    Array.from(selected).forEach((id) => {
      const el = elements.get(id);
      if (!el) return;
      el.data.groupId = gid;
      send({ action: 'element_update', element: el });
    });
    refreshTransformer();
  }
  function ungroupSelected() {
    let changed = false;
    Array.from(selected).forEach((id) => {
      const el = elements.get(id);
      if (el && el.data && el.data.groupId != null) {
        delete el.data.groupId;
        send({ action: 'element_update', element: el });
        changed = true;
      }
    });
    if (changed) refreshTransformer();
  }
  function deleteSelected() {
    if (selected.size === 0) return;
    deleteWithDependents(Array.from(selected)); // каскад: точка → всё, что на ней завязано
    selected.clear();
    refreshTransformer();
  }
  // ── Дублирование ───────────────────────────────────────────────────────
  // Таблицы, голосования и таймеры сюда НЕ входят намеренно: у них живое
  // состояние (ход голосования, отсчёт), и копия сбивала бы с толку.
  const DUP_TYPES = ['shape', 'image', 'rect', 'ellipse', 'line', 'arrow', 'freehand',
    'text', 'textbox', 'latex', 'sticky', 'card'];
  function canDuplicate(el) { return DUP_TYPES.indexOf(el.type) >= 0 || (el.type === 'point' && !el.data.on); }
  function duplicateSelected() {
    const news = [];
    // Сортируем по глубине и раздаём НОВЫЕ z по возрастанию поверх доски.
    // Раньше дубликат получал тот же z, что и оригинал: при равных z порядок
    // задаётся не глубиной, а тем, как объекты легли на слой, — то есть
    // обходом множества выделенного. Оттого слои в дубликате и путались.
    let maxz = 0; elements.forEach((e) => { const z = e.z || 0; if (z > maxz) maxz = z; });
    const исходники = Array.from(selected)
      .map((id) => elements.get(id))
      .filter((el) => el && canDuplicate(el))
      .sort((a, b) => (a.z || 0) - (b.z || 0));
    исходники.forEach((src) => {
      const id = src.id;
      const el = elements.get(id); if (!el || !canDuplicate(el)) return;
      const data = clone(el.data); delete data.hidden;
      if (el.type === 'point') {
        if (data.frame) { data.mx = (data.mx || 0) + 0.5; data.my = (data.my || 0) - 0.5; } else { data.x = (data.x || 0) + 20; data.y = (data.y || 0) + 20; }
        data.label = nextPointLabel(); data.idx = undefined;
      } else { if (data.x != null) data.x += 20; if (data.y != null) data.y += 20; }
      const nel = { id: uuid(), type: el.type, z: ++maxz, data: data };
      upsertNode(nel); send({ action: 'element_add', element: nel }); histAdd(nel); news.push(nel.id);
    });
    if (news.length) { selected.clear(); news.forEach((i) => selected.add(i)); refreshTransformer(); layer.batchDraw(); boardHint('Дублировано: ' + news.length); }
    else boardHint('Эти объекты нельзя дублировать');
  }
  // ── Копирование и вставка ──────────────────────────────────────────────
  // Свой буфер нужен потому, что системный не умеет хранить объекты доски —
  // только текст и файлы. Картинки же, наоборот, приходят именно из системного,
  // событием paste: снимок экрана или картинку из переписки иначе пришлось бы
  // сначала сохранять в файл и потом импортировать кнопкой.
  let boardClip = [];
  // Метка, по которой узнаём СВОЮ запись в системном буфере. Нужна потому, что
  // системный буфер умеет хранить только текст: кладём в него объекты доски
  // строкой, а при вставке узнаём их по этой метке.
  const CLIP_TAG = 'TUTORBOARD/v1:';
  const CLIP_MAX = 2 * 1024 * 1024;   // очень большую пачку в буфер не пишем
  function copySelected(cut) {
    if (!selected.size) { boardHint('Сначала выделите объекты'); return; }
    boardClip = Array.from(selected)
      .map((id) => elements.get(id))
      .filter((el) => el && canDuplicate(el))
      .map((el) => ({ type: el.type, z: el.z || 0, data: clone(el.data) }));
    if (!boardClip.length) { boardHint('Эти объекты нельзя скопировать'); return; }
    // Кладём и в системный буфер: иначе Ctrl+V подхватит чужой текст, который
    // лежал там с прошлого раза. Заодно объекты станут переноситься между
    // досками и вкладками.
    try {
      const строка = CLIP_TAG + JSON.stringify(boardClip);
      if (строка.length <= CLIP_MAX && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(строка).catch(() => {});
      }
    } catch (e) {}
    boardHint((cut ? 'Вырезано: ' : 'Скопировано: ') + boardClip.length);
    if (cut) deleteSelected();
  }
  function pasteBoardClip(at) {
    if (!boardClip.length) return false;
    // Всю пачку сдвигаем как целое: её левый верхний угол встаёт под курсор,
    // взаимное расположение объектов сохраняется.
    const xs = boardClip.map((c) => c.data.x).filter((v) => v != null);
    const ys = boardClip.map((c) => c.data.y).filter((v) => v != null);
    const ox = xs.length ? Math.min.apply(null, xs) : 0;
    const oy = ys.length ? Math.min.apply(null, ys) : 0;
    const news = [];
    boardClip.forEach((c) => {
      const data = clone(c.data);
      delete data.hidden;
      if (data.x != null) data.x = at.x + (data.x - ox);
      if (data.y != null) data.y = at.y + (data.y - oy);
      if (c.type === 'point') { data.label = nextPointLabel(); data.idx = undefined; }
      const nel = { id: uuid(), type: c.type, z: c.z, data: data };
      upsertNode(nel); send({ action: 'element_add', element: nel }); histAdd(nel);
      news.push(nel.id);
    });
    selected.clear(); news.forEach((i) => selected.add(i));
    refreshTransformer(); layer.batchDraw();
    boardHint('Вставлено: ' + news.length);
    return true;
  }
  function pasteTextAt(text, at) {
    const el = { id: uuid(), type: 'textbox', z: 0, data: {
      // Переносы строк — в <br>. Коды символов вместо регулярного
      // выражения: так в исходнике нет обратных слешей, которые легко
      // теряются при переносе правок между инструментами.
      x: at.x, y: at.y,
      html: escapeHtml(text)
        .split(String.fromCharCode(13)).join('')
        .split(String.fromCharCode(10)).join('<br>'),
      color: strokeColor, fontSize: 20, font: TEXT_FONT, align: 'left' } };
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    boardHint('Текст вставлен');
  }
  function ctxWorldOrCentre() { return worldPoint() || viewportCenterWorld(); }

  window.addEventListener('paste', (e) => {
    if (viewOnly) return;
    // Внутри поля ввода вставка — дело самого поля, не доски.
    const t = e.target;
    if (t && t.matches && t.matches('input, textarea, [contenteditable], [contenteditable] *')) return;
    const dt = e.clipboardData; if (!dt) return;
    const at = ctxWorldOrCentre();

    const files = [];
    if (dt.files && dt.files.length) Array.prototype.push.apply(files, Array.from(dt.files));
    else if (dt.items) Array.from(dt.items).forEach((it) => {
      if (it.kind === 'file') { const f = it.getAsFile(); if (f) files.push(f); }
    });
    if (files.length) { e.preventDefault(); importFiles(files); return; }

    const text = dt.getData && dt.getData('text/plain');
    // Своя запись узнаётся по метке и разбирается ПЕРВОЙ. Раньше здесь сразу
    // проверялся текст, и объекты, скопированные по Ctrl+C, никогда не
    // доходили до вставки — вместо них появлялся чужой текст из буфера.
    if (text && text.indexOf(CLIP_TAG) === 0) {
      e.preventDefault();
      try {
        const пачка = JSON.parse(text.slice(CLIP_TAG.length));
        if (Array.isArray(пачка) && пачка.length) { boardClip = пачка; pasteBoardClip(at); return; }
      } catch (err) { boardHint('Не удалось разобрать скопированные объекты'); return; }
      return;
    }
    // Свой буфер полон, а в системном лежит текст — значит доступ к буферу нам
    // не дали при копировании. Своё всё равно важнее: человек только что нажал
    // Ctrl+C на объектах доски.
    if (boardClip.length && pasteBoardClip(at)) { e.preventDefault(); return; }
    if (text && text.trim()) { e.preventDefault(); pasteTextAt(text, at); return; }

    if (pasteBoardClip(at)) e.preventDefault();
  });

  // ── Обрезка картинки ───────────────────────────────────────────────────
  // Рамкой по картинке: что обвели, то и осталось. Прямоугольник живёт в
  // пикселях ИСХОДНОГО файла, поэтому не зависит от того, как картинку потом
  // растянут на доске.
  let cropId = null, cropDrag = null;
  const cropRect = new Konva.Rect({
    stroke: '#3b62d8', strokeWidth: 1.5, dash: [6, 4], fill: 'rgba(59,98,216,0.10)',
    listening: false, visible: false,
  });
  layer.add(cropRect);
  function startCropMode(id) {
    const el = elements.get(id), n = nodes.get(id);
    if (!el || el.type !== 'image' || !n) { boardHint('Обрезать можно только картинку'); return; }
    if (!imageNatural(n)) { boardHint('Картинка ещё не загрузилась'); return; }
    cropId = id; cropDrag = null;
    cropRect.visible(false); cropRect.moveToTop(); layer.batchDraw();
    stageEl.style.cursor = 'crosshair';
    boardHint('Обведите часть, которую нужно оставить. Escape — отмена');
  }
  function endCropMode() {
    cropId = null; cropDrag = null;
    cropRect.visible(false); layer.batchDraw();
    stageEl.style.cursor = (tool === 'select') ? 'default' : 'crosshair';
  }
  function cropBox() {
    const el = elements.get(cropId); if (!el) return null;
    return { x: el.data.x || 0, y: el.data.y || 0, w: el.data.width || 0, h: el.data.height || 0 };
  }
  function cropMove() {
    if (!cropDrag) return;
    const p = worldPoint(); if (!p) return;
    const b = cropBox(); if (!b) return;
    // Рамку держим внутри картинки: обрезать «наружу» нечего.
    const x = Math.max(b.x, Math.min(p.x, b.x + b.w));
    const y = Math.max(b.y, Math.min(p.y, b.y + b.h));
    cropRect.x(Math.min(cropDrag.x0, x)); cropRect.y(Math.min(cropDrag.y0, y));
    cropRect.width(Math.abs(x - cropDrag.x0)); cropRect.height(Math.abs(y - cropDrag.y0));
    cropRect.visible(true); cropRect.moveToTop();
    layer.batchDraw();
  }
  function finishCrop() {
    if (!cropDrag) { endCropMode(); return; }
    const el = elements.get(cropId), n = nodes.get(cropId);
    const nat = n && imageNatural(n);
    const b = cropBox();
    const rx = cropRect.x(), ry = cropRect.y(), rw = cropRect.width(), rh = cropRect.height();
    if (!el || !nat || !b || rw < 6 || rh < 6) { boardHint('Слишком маленькая рамка — обрезка отменена'); endCropMode(); return; }
    const d = el.data;
    // Что показывается сейчас: либо прежнее окно кадра, либо весь файл.
    const c0 = (d.crop && d.crop.w > 0) ? d.crop : { x: 0, y: 0, w: nat.w, h: nat.h };
    // Сколько пикселей доски приходится на пиксель исходника.
    const kx = b.w / c0.w, ky = b.h / c0.h;
    if (!(kx > 0 && ky > 0)) { endCropMode(); return; }
    const before = clone(el);
    d.crop = {
      x: c0.x + (rx - b.x) / kx,
      y: c0.y + (ry - b.y) / ky,
      w: rw / kx,
      h: rh / ky,
    };
    // Оставленная часть остаётся ровно там, где была: границы объекта совпадают
    // с обведённой рамкой, масштаб картинки не меняется.
    d.x = rx; d.y = ry; d.width = rw; d.height = rh;
    n.x(rx); n.y(ry); n.width(rw); n.height(rh);
    applyCrop(n, el);
    histUpd(before, el); send({ action: 'element_update', element: stripPrivate(el) });
    endCropMode(); refreshTransformer(); layer.batchDraw();
    boardHint('Обрезано. Вернуть — правая кнопка → «Сбросить обрезку»');
  }
  function resetCrop(id) {
    const el = elements.get(id), n = nodes.get(id);
    if (!el || el.type !== 'image' || !el.data.crop) return;
    const nat = n && imageNatural(n); if (!nat) return;
    const before = clone(el);
    const c0 = el.data.crop;
    // Возвращаем весь файл, сохранив масштаб: размер объекта растёт во столько
    // же раз, во сколько окно кадра меньше исходника.
    const kx = (el.data.width || 1) / c0.w, ky = (el.data.height || 1) / c0.h;
    el.data.x = (el.data.x || 0) - c0.x * kx;
    el.data.y = (el.data.y || 0) - c0.y * ky;
    el.data.width = nat.w * kx; el.data.height = nat.h * ky;
    delete el.data.crop;
    n.x(el.data.x); n.y(el.data.y); n.width(el.data.width); n.height(el.data.height);
    applyCrop(n, el);
    histUpd(before, el); send({ action: 'element_update', element: stripPrivate(el) });
    refreshTransformer(); layer.batchDraw();
    boardHint('Обрезка снята');
  }

  // ── Порядок слоёв ──────────────────────────────────────────────────────
  // dir: 'front' | 'back' — сразу наверх или вниз; 'up' | 'down' — на один шаг,
  // то есть поменяться местами с ближайшим соседом по глубине. Шаг нужен, когда
  // объектов много и прыжок через все ломает разложенный порядок.
  function moveElZ(ids, dir) {
    let mz = 0, minz = 0; elements.forEach((e) => { const z = e.z || 0; if (z > mz) mz = z; if (z < minz) minz = z; });
    if (dir === 'up' || dir === 'down') {
      ids.forEach((id) => {
        const el = elements.get(id), n = nodes.get(id); if (!el || !n) return;
        const мой = el.z || 0;
        // Ближайший сосед по глубине в нужную сторону. Равные z разводим по
        // порядку узлов, иначе объекты с одинаковым z никогда не разъедутся.
        let сосед = null;
        elements.forEach((e, eid) => {
          if (eid === id || !nodes.get(eid)) return;
          const z = e.z || 0;
          if (dir === 'up' ? (z > мой) : (z < мой)) {
            if (!сосед || (dir === 'up' ? z < сосед.z : z > сосед.z)) сосед = { id: eid, el: e, z: z };
          }
        });
        const before = clone(el);
        if (сосед) { el.z = сосед.z + (dir === 'up' ? 1 : -1); }
        else { el.z = dir === 'up' ? ++mz : --minz; }
        if (dir === 'up' && typeof n.moveUp === 'function') n.moveUp();
        if (dir === 'down' && typeof n.moveDown === 'function') n.moveDown();
        histUpd(before, el); send({ action: 'element_update', element: el });
      });
      refreshTransformer(); layer.batchDraw();
      return;
    }
    ids.forEach((id) => {
      const el = elements.get(id), n = nodes.get(id); if (!el || !n) return; const before = clone(el);
      if (dir === 'front') { el.z = ++mz; if (typeof n.moveToTop === 'function') n.moveToTop(); }
      else { el.z = --minz; if (typeof n.moveToBottom === 'function') n.moveToBottom(); }
      histUpd(before, el); send({ action: 'element_update', element: el });
    });
    refreshTransformer(); layer.batchDraw();
  }
  // ── Замок ──────────────────────────────────────────────────────────────
  // data.locked уважается всюду (перетаскивание, двойной щелчок, якоря), но
  // поставить его можно было только точке — чекбоксом в её настройках.
  function setLocked(ids, locked) {
    ids.forEach((id) => {
      const el = elements.get(id); if (!el) return;
      const before = clone(el); el.data.locked = locked ? true : undefined;
      const n = nodes.get(id);
      if (n && typeof n.draggable === 'function') n.draggable(!locked && tool === 'select' && !viewOnly && !isPointBound(el) && el.type !== 'frame');
      histUpd(before, el); send({ action: 'element_update', element: el });
    });
    renderAnchors(); refreshTransformer(); layer.batchDraw();
    boardHint(locked ? 'Заблокировано: объект не двигается и не правится' : 'Разблокировано');
  }
  function allLocked(ids) { return ids.length > 0 && ids.every((id) => { const e = elements.get(id); return e && e.data && e.data.locked; }); }
  // ── Ссылка на объект: якорь в адресе ───────────────────────────────────
  // Хеш, а не параметр запроса: хеш не уходит на сервер и не оседает в журналах.
  function boardLink(eid) { return location.origin + location.pathname + '#o=' + encodeURIComponent(eid); }
  // Адрес вида …/board/КОД/#o=<id>: доезжаем до объекта и подсвечиваем его.
  // Картинки и виджеты появляются не сразу, поэтому пробуем ещё раз кадром позже.
  // Доска догрузилась целиком: только теперь можно пересчитывать построения
  // (им нужны ВСЕ точки) и ехать по якорю из адреса.
  function finishInit() {
    reattachFuncs();     // функции могли загрузиться раньше своих окон
    recomputeGeometry(); // построения — после загрузки всех точек
    gotoHashAnchor();    // адрес мог содержать #o=<объект>
  }
  function gotoHashAnchor() {
    const m = /^#o=(.+)$/.exec(location.hash || ''); if (!m) return;
    const eid = decodeURIComponent(m[1]);
    const дойти = () => { if (elements.get(eid)) focusElement(eid); };
    дойти(); requestAnimationFrame(дойти);
  }
  window.addEventListener('hashchange', gotoHashAnchor);
  // Копирование в буфер с честным запасным путём: браузер может не дать доступ
  // (нет фокуса, не https), и молча отказывать нельзя — показываем текст.
  function copyText(text, чтоЭто) {
    const вручную = () => {
      boardHint('Не удалось скопировать — текст показан, скопируйте вручную');
      uiPrompt(чтоЭто || 'Скопируйте (Ctrl+C):', text, { readonly: true });
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => boardHint('Скопировано')).catch(вручную);
    } else вручную();
  }
  // Внешний адрес: только http и https. Ссылку кладёт один участник, а щёлкают
  // по ней все, поэтому javascript:… или data:… выполнили бы чужой код у
  // каждого. Та же проверка продублирована на сервере.
  function safeLinkUrl(raw) {
    const t = (raw || '').trim(); if (!t) return null;
    let u; try { u = new URL(t); } catch (e) { try { u = new URL('https://' + t); } catch (e2) { return null; } }
    return (u.protocol === 'http:' || u.protocol === 'https:') ? u.href : null;
  }
  function openObjectLink(el) {
    const L = el && el.data && el.data.link; if (!L) return false;
    if (L.kind === 'obj') { focusElement(L.id); return true; }
    if (L.kind === 'url') {
      const href = safeLinkUrl(L.href); if (!href) { boardHint('Ссылка испорчена и не открыта'); return true; }
      // Шаг для безопасности: наружу уходим только с подтверждением и показываем,
      // куда именно. Ссылку мог положить другой участник.
      let host = href; try { host = new URL(href).host; } catch (e) {}
      uiConfirm('Открыть внешний сайт?\n\n' + host + '\n\n' + href, { ok: 'Открыть' }).then((ok) => { if (ok) window.open(href, '_blank', 'noopener,noreferrer'); });
      return true;
    }
    return false;
  }
  function askLinkFor(ids) {
    const el = ids.length === 1 ? elements.get(ids[0]) : null; if (!el) { boardHint('Выберите один объект'); return; }
    const было = el.data.link ? (el.data.link.kind === 'url' ? el.data.link.href : boardLink(el.data.link.id)) : '';
    uiPrompt('Куда ведёт ссылка?\n\nВставьте адрес сайта или ссылку на объект этой доски\n(её даёт пункт «Копировать ссылку»).\nПустая строка — убрать ссылку.', было, { multiline: true }).then((txt) => {
      if (txt === null) return;
      const before = clone(el);
      const t = txt.trim();
      if (!t) { el.data.link = undefined; boardHint('Ссылка убрана'); }
      else {
        // Свой же адрес доски с якорем — это переход внутри доски.
        let свой = null;
        try { const u = new URL(t, location.href); if (u.pathname === location.pathname && /^#o=/.test(u.hash)) свой = decodeURIComponent(u.hash.slice(3)); } catch (e) {}
        if (свой) { el.data.link = { kind: 'obj', id: свой }; boardHint('Ссылка на объект доски'); }
        else {
          const href = safeLinkUrl(t);
          if (!href) { boardHint('Не похоже на адрес. Разрешены только http и https'); return; }
          el.data.link = { kind: 'url', href: href }; boardHint('Внешняя ссылка добавлена');
        }
      }
      histUpd(before, el); send({ action: 'element_update', element: el });
    });
  }
  // ── Выравнивание выделенных объектов (по рамкам) ───────────────────────
  function moveItemTo(o, b, nx, ny, ops) {
    const before = clone(o.el);
    o.el.data.x += (nx - b.x); o.el.data.y += (ny - b.y);
    o.n.x(o.el.data.x); o.n.y(o.el.data.y);
    send({ action: 'element_update', element: o.el });
    if (ops) ops.push({ kind: 'upd', before: before, after: clone(o.el) }); else histUpd(before, o.el);
  }
  function boxesForIds(ids) {
    return ids.map((id) => { const o = { el: elements.get(id), n: nodes.get(id) }; return (o.el && o.n && o.el.data && o.el.data.x != null && typeof o.n.getClientRect === 'function') ? { o: o, b: o.n.getClientRect({ relativeTo: layer }) } : null; }).filter(Boolean);
  }
  // Разложить боксы (в заданном порядке) в сетку из cols колонок: строки —
  // слева-направо с зазором gap и выравниванием по верху; следующая строка ниже
  // предыдущей на (наибольшую высоту в строке + gap).
  function arrangeGridBoxes(boxes, cols, gap, ox, oy) {
    if (!boxes.length) return;
    const ops = []; let x = ox, y = oy, col = 0, rowMaxH = 0;
    boxes.forEach(({ o, b }) => {
      if (col === cols) { x = ox; y += rowMaxH + gap; col = 0; rowMaxH = 0; }
      moveItemTo(o, b, x, y, ops);
      x += b.width + gap; if (b.height > rowMaxH) rowMaxH = b.height; col++;
    });
    histBatch(ops); refreshTransformer(); layer.batchDraw();
  }
  function viewportTopLeftWorld() { const s = stage.scaleX(); return { x: -stage.x() / s, y: -stage.y() / s }; }
  const GRID_COLS = 12;
  // Авто-раскладка партии импортированных/извлечённых объектов в сетку у левого
  // верха видимой области (с отступом, чтобы не залезать под тулбар/шапку).
  function autoGridArrange(ids) {
    const boxes = boxesForIds(ids); if (boxes.length < 2) return;
    const tl = viewportTopLeftWorld(), s = stage.scaleX();
    arrangeGridBoxes(boxes, GRID_COLS, arrangeGap, tl.x + 90 / s, tl.y + 70 / s);
    setTool('select'); boardHint('Разложено в сетку: ' + boxes.length + ' объект(ов)');
  }
  const arrangeGap = 20; // зазор между объектами при авто-раскладке в сетку (импорт), мир. ед.
  // ── Контекстное меню (правый клик) ─────────────────────────────────────
  const ctxMenu = document.createElement('div'); ctxMenu.id = 'ctx-menu'; ctxMenu.style.display = 'none'; document.body.appendChild(ctxMenu);
  const CTX_ITEMS = [
    { label: 'Копировать', key: 'Ctrl+C', act: function () { copySelected(false); } },
    { label: 'Вырезать', key: 'Ctrl+X', act: function () { copySelected(true); } },
    { label: 'Дублировать', key: 'Ctrl+D', act: duplicateSelected },
    { label: 'Скрыть', key: 'H', act: () => { if (selected.size) setHidden(Array.from(selected), true); } },
    { sep: true },
    { label: 'Выше', act: () => moveElZ(Array.from(selected), 'up') },
    { label: 'Ниже', act: () => moveElZ(Array.from(selected), 'down') },
    { label: 'На передний план', act: () => moveElZ(Array.from(selected), 'front') },
    { label: 'На задний план', act: () => moveElZ(Array.from(selected), 'back') },
    { sep: true },
    { label: 'Обрезать', act: () => { const id = Array.from(selected)[0]; if (id) startCropMode(id); } },
    { label: 'Сбросить обрезку', act: () => { Array.from(selected).forEach(resetCrop); } },
    { label: 'Загрузить картинку снова', act: () => { Array.from(selected).forEach(reloadImage); } },
    { label: 'Копировать ссылку', act: () => { const id = Array.from(selected)[0]; if (id) copyText(boardLink(id), 'Ссылка на объект:'); } },
    { label: 'Связать с…', act: () => askLinkFor(Array.from(selected)) },
    { label: 'Комментировать', act: () => insertComment(ctxWorld) },
    { label: 'Заблокировать', act: () => { const ids = Array.from(selected); setLocked(ids, !allLocked(ids)); } },
    { sep: true },
    { label: 'Удалить', key: 'Del', danger: true, act: deleteSelected },
  ];
  // «Показать всё»: вписываем в экран прямоугольник по всем видимым объектам.
  function fitAllToView() {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const take = (x, y, w, h) => {
      minX = Math.min(minX, x); minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + w); maxY = Math.max(maxY, y + h);
    };
    nodes.forEach((node, id) => {
      const el = elements.get(id);
      if (!el || (el.data && el.data.hidden && !revealHidden)) return;
      const b = node.getClientRect({ relativeTo: layer });
      if (b && (b.width || b.height)) take(b.x, b.y, b.width, b.height);
    });
    widgetItems.forEach((it) => {
      const d = it.el.data;
      if (d && d.hidden && !revealHidden) return;
      const w = it.wrapper.offsetWidth || 0, h = it.wrapper.offsetHeight || 0;
      if (w || h) take(d.x || 0, d.y || 0, w, h);
    });
    if (!isFinite(minX)) { boardHint('На доске пока пусто'); return; }
    const pad = 60;
    const sc = Math.max(MIN_SCALE, Math.min(MAX_SCALE, Math.min(
      (stage.width() - pad * 2) / Math.max(1, maxX - minX),
      (stage.height() - pad * 2) / Math.max(1, maxY - minY))));
    stage.scale({ x: sc, y: sc });
    stage.position({
      x: (stage.width() - (maxX - minX) * sc) / 2 - minX * sc,
      y: (stage.height() - (maxY - minY) * sc) / 2 - minY * sc,
    });
    redrawGrid(); repositionWidgets(); positionHandles();
    layer.batchDraw(); updateZoomLabel();
  }

  // Точка мира по экранным координатам. Считаем из них напрямую, а не через
  // указатель Konva: меню открывается и с DOM-слоя, где указатель сцены
  // остаётся от прошлого события и врёт.
  function worldFromClient(cx, cy) {
    const r = stage.container().getBoundingClientRect(), sc = stage.scaleX();
    return { x: (cx - r.left - stage.x()) / sc, y: (cy - r.top - stage.y()) / sc };
  }
  let ctxWorld = null;   // где именно нажали правой кнопкой

  // Вставка ИЗ МЕНЮ. Браузер не даёт читать системный буфер по нажатию пункта
  // без разрешения, поэтому честно объясняем и предлагаем Ctrl+V.
  function pasteFromMenu() {
    const at = ctxWorld || viewportCenterWorld();
    if (!navigator.clipboard || !navigator.clipboard.read) {
      if (!pasteBoardClip(at)) boardHint('Нажмите Ctrl+V — из меню буфер прочитать нельзя');
      return;
    }
    navigator.clipboard.read().then((items) => {
      const files = [];
      let chain = Promise.resolve();
      items.forEach((it) => {
        const imgType = (it.types || []).filter((t) => t.indexOf('image/') === 0)[0];
        if (!imgType) return;
        chain = chain.then(() => it.getType(imgType))
          .then((blob) => { files.push(new File([blob], 'вставка.png', { type: blob.type })); });
      });
      return chain.then(() => {
        if (files.length) { importFiles(files); return null; }
        return navigator.clipboard.readText().then((txt) => {
          if (txt && txt.trim()) pasteTextAt(txt, at);
          else if (!pasteBoardClip(at)) boardHint('Буфер пуст');
        });
      });
    }).catch(() => {
      if (!pasteBoardClip(at)) boardHint('Нажмите Ctrl+V — браузер не дал прочитать буфер');
    });
  }

  // Меню по ПУСТОМУ месту — то, чего не было совсем.
  function ctxEmptyItems() {
    const gridOn = (boardBg === 'grid');
    return [
      { label: 'Вставить', key: 'Ctrl+V', accent: true, act: pasteFromMenu },
      { sep: true },
      { label: 'Добавить текст', act: function () { insertTextbox(); } },
      { label: 'Добавить стикер', act: function () { insertSticky(); } },
      { sep: true },
      { label: 'Выделить всё', key: 'Ctrl+A', act: selectAllElements },
      { label: 'Показать всё', act: fitAllToView },
      { label: 'Масштаб 100%', key: 'Ctrl+0', act: function () { zoomTo(1); } },
      { sep: true },
      { label: 'Сетка', tick: gridOn, act: function () { setBoardBg(gridOn ? 'blank' : 'grid'); } },
      { label: 'Привязка к объектам', tick: guidesEnabled, act: function () {
          guidesEnabled = !guidesEnabled;
          const g = document.getElementById('guides-toggle'); if (g) g.checked = guidesEnabled;
          boardHint(guidesEnabled ? 'Привязка включена' : 'Привязка выключена');
        } },
      { label: 'Показать скрытое', key: 'Shift+H', tick: revealHidden, act: toggleRevealHidden },
    ];
  }
  function hideCtxMenu() { ctxMenu.style.display = 'none'; }
  function showCtxMenu(x, y, onEmpty) {
    ctxMenu.innerHTML = '';
    const put = (it) => {
      if (it.sep) { const sp = document.createElement('div'); sp.className = 'ctx-sep'; ctxMenu.appendChild(sp); return; }
      const b = document.createElement('button');
      b.className = 'ctx-item' + (it.danger ? ' danger' : '') + (it.accent ? ' accent' : '');
      b.innerHTML = '<span class="ctx-tick">' + (it.tick ? '✓' : '') + '</span>'
        + '<span style="flex:1;text-align:left">' + it.label + '</span>'
        + (it.key ? '<span class="ctx-key">' + it.key + '</span>' : '');
      b.addEventListener('click', () => { hideCtxMenu(); it.act(); });
      ctxMenu.appendChild(b);
    };
    if (onEmpty) {
      ctxEmptyItems().forEach(put);
      ctxMenu.style.left = Math.min(x, window.innerWidth - 230) + 'px';
      ctxMenu.style.top = Math.min(y, window.innerHeight - 330) + 'px';
      ctxMenu.style.display = 'block';
      return;
    }
    if (selected.size === 1) {
      const el = elements.get(Array.from(selected)[0]);
      if (el && el.type === 'point') {
        const b = document.createElement('button'); b.className = 'ctx-item';
        b.innerHTML = '<span>' + (el.data.trace ? 'Убрать след точки' : 'След точки (locus)') + '</span>';
        b.addEventListener('click', () => { hideCtxMenu(); toggleTrace(el.id); }); ctxMenu.appendChild(b);
        const s = document.createElement('div'); s.className = 'ctx-sep'; ctxMenu.appendChild(s);
      }
    }
    // Замок — переключатель, поэтому подпись зависит от текущего состояния.
    const _ids = Array.from(selected);
    // «Загрузить снова» имеет смысл только для картинки — прочим он бы мешал.
    const _естьКартинка = _ids.some((id) => { const e = elements.get(id); return e && e.type === 'image'; });
    CTX_ITEMS.forEach((it) => {
      if (it.label === 'Загрузить картинку снова' || it.label === 'Обрезать') { if (_естьКартинка) put(it); return; }
      if (it.label === 'Сбросить обрезку') {
        const есть = _ids.some((id) => { const e2 = elements.get(id); return e2 && e2.type === 'image' && e2.data && e2.data.crop; });
        if (есть) put(it);
        return;
      }
      if (it.label === 'Заблокировать') put(Object.assign({}, it, { label: allLocked(_ids) ? 'Разблокировать' : 'Заблокировать' }));
      else put(it);
    });
    ctxMenu.style.left = Math.min(x, window.innerWidth - 210) + 'px';
    ctxMenu.style.top = Math.min(y, window.innerHeight - 260) + 'px';
    ctxMenu.style.display = 'block';
  }
  document.addEventListener('click', hideCtxMenu);
  // Сторож закрывает меню при нажатии мимо доски. Слой виджетов сюда тоже
  // входит — иначе меню, открытое на тексте, тут же закрывалось бы само.
  document.addEventListener('contextmenu', (e) => {
    const inBoard = e.target.closest && (e.target.closest('#board-stage') || e.target.closest('#widget-layer'));
    if (!inBoard) hideCtxMenu();
  });

  // Тексты, стикеры, таблицы и прочие виджеты — это HTML поверх холста, и
  // правая кнопка на них до сцены не доходила. Вешаем меню и на них.
  widgetLayerEl.addEventListener('contextmenu', (e) => {
    const wrap = e.target.closest && e.target.closest('.wgt, .tbox, .mtext');
    if (!wrap) return;
    let id = null;
    widgetItems.forEach((it, wid) => { if (it.wrapper === wrap) id = wid; });
    if (!id) return;
    e.preventDefault();
    e.stopPropagation();
    // Правая кнопка ещё зажата — значит меню пришло на НАЖАТИИ (так делает
    // macOS). Откладываем до отпускания: потянут — будет перемещение доски,
    // а не выскочившее и тут же закрытое меню.
    const x = e.clientX, y = e.clientY;
    if (rmbPan) { rmbMenu = () => openWidgetCtxMenu(id, x, y); return; }
    openWidgetCtxMenu(id, x, y);
  });
  function openWidgetCtxMenu(id, x, y) {
    ctxWorld = worldFromClient(x, y);
    if (!selected.has(id)) selectOnly(id);
    showCtxMenu(x, y, false);
  }
  stage.on('contextmenu', (e) => {
    if (e.evt) e.evt.preventDefault();
    const x = e.evt ? e.evt.clientX : 0, y = e.evt ? e.evt.clientY : 0, цель = e.target;
    // Правая кнопка ещё зажата — меню пришло на нажатии (macOS). Откладываем:
    // потянут — выйдет перемещение доски, а не мелькнувшее меню.
    if (rmbPan) { rmbMenu = () => openStageCtxMenu(x, y, цель); return; }
    openStageCtxMenu(x, y, цель);
  });
  function openStageCtxMenu(x, y, цель) {
    const w = worldPoint(); let id = null;
    const g = w ? pickObjectAtWorld(w) : null;
    if (g) id = g.id; else { const t = цель; if (t && t !== stage && elements.get(t.id())) id = t.id(); }
    ctxWorld = worldFromClient(x, y);
    if (id && !selected.has(id)) selectOnly(id);
    // По пустому месту — меню доски, как в Miro. Раньше здесь не появлялось
    // ничего, и правая кнопка казалась несуществующей.
    showCtxMenu(x, y, !id || !selected.size);
  }


  // ── Редактор формул LaTeX ──────────────────────────────────────────────
  const latexEditor = document.getElementById('latex-editor');
  const leInput = document.getElementById('le-input');
  const lePreview = document.getElementById('le-preview');
  let latexInsertPos = null;

  function openLatexEditor() {
    latexInsertPos = worldPoint();
    const p = stage.getPointerPosition();
    // Координаты экрана: контейнер сцены начинается на 56px ниже навбара.
    let left = p.x + 14, top = p.y + STAGE_TOP + 14;
    left = Math.min(left, window.innerWidth - 340);
    latexEditor.style.left = left + 'px';
    latexEditor.style.top = top + 'px';
    latexEditor.hidden = false;
    leInput.value = '';
    lePreview.innerHTML = '<span style="color:#9a9aa4">превью формулы</span>';
    leInput.focus();
  }
  function closeLatexEditor() { latexEditor.hidden = true; }

  function updateLatexPreview() {
    const tex = leInput.value;
    if (!tex.trim()) { lePreview.innerHTML = '<span style="color:#9a9aa4">превью формулы</span>'; return; }
    lePreview.textContent = '\\[' + tex + '\\]';
    if (window.MathJax && MathJax.typesetPromise) {
      MathJax.typesetPromise([lePreview]).catch(() => {});
    }
  }
  function insertLatex() {
    const tex = leInput.value.trim();
    if (!tex) { closeLatexEditor(); return; }
    const el = { id: uuid(), type: 'latex', z: 0,
      data: { x: latexInsertPos.x, y: latexInsertPos.y, latex: tex, color: strokeColor } };
    upsertNode(el);
    send({ action: 'element_add', element: el });
    histAdd(el);
    closeLatexEditor();
    setTool('select'); // сразу можно двигать вставленную формулу
  }

  if (leInput) {
    leInput.addEventListener('input', updateLatexPreview);
    leInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); insertLatex(); }
      if (e.key === 'Escape') { e.preventDefault(); closeLatexEditor(); }
    });
    document.getElementById('le-insert').addEventListener('click', insertLatex);
    document.getElementById('le-cancel').addEventListener('click', closeLatexEditor);
  }
  // ── Редактор текста (с инлайн-формулами $...$) ─────────────────────────
  // ── Rich-text редактор: тулбар (шрифт/кегль/Ж-К-Ч-З/цвет/фон/выравнивание/
  //    списки/фон окна) + contenteditable. Формулы — внутри $…$, ссылки — авто. ──
  const textEditor = document.getElementById('text-editor');
  const tePanel = document.getElementById('te-panel');
  const teEdit = document.getElementById('te-edit');
  const teBar = document.getElementById('te-bar');
  const teFont = document.getElementById('te-font');
  const teSize = document.getElementById('te-size');
  const TE_DEFAULT_SIZE = 22;
  let teHiddenNode = null; // узел текста, скрытый на время правки «на месте»
  // Диагностика правки текста (для отладки бага у пользователя): window.__teLog
  window.__teLog = window.__teLog || [];
  function teLog(o) { try { window.__teLog.push(o); if (window.__teLog.length > 300) window.__teLog.shift(); } catch (e) {} }
  let teEl = null;            // редактируемый элемент (null — создаём новый)
  let textInsertPos = null;   // мир-координаты для нового текста
  let teBox = {};             // box-настройки текущего сеанса {font,fontSize,color,align,boxBg}

  if (teFont) {
    TEXT_FONTS.forEach((f) => { const o = document.createElement('option'); o.value = f.css; o.textContent = f.label; o.style.fontFamily = f.css; teFont.appendChild(o); });
  }
  // Попапы выбора цвета: строим лениво (BASE_COLORS объявлен ниже по файлу).
  const TE_POPS = { color: 'te-color-pop', hilite: 'te-hilite-pop', boxbg: 'te-boxbg-pop' };
  const TE_PBTN = { color: 'te-color-btn', hilite: 'te-hilite-btn', boxbg: 'te-boxbg-btn' };
  function teCloseP() { Object.values(TE_POPS).forEach((id) => document.getElementById(id).classList.add('ps-hidden')); Object.values(TE_PBTN).forEach((id) => document.getElementById(id).classList.remove('te-on')); }
  function teToggleP(which) {
    const pop = document.getElementById(TE_POPS[which]), hid = pop.classList.contains('ps-hidden'); teCloseP();
    if (hid) { const btn = document.getElementById(TE_PBTN[which]), r = btn.getBoundingClientRect(), er = tePanel.getBoundingClientRect(); pop.style.left = (r.left - er.left) + 'px'; pop.style.top = (r.bottom - er.top + 2) + 'px'; pop.classList.remove('ps-hidden'); btn.classList.add('te-on'); }
  }
  function teExec(cmd, val) { teEdit.focus(); try { document.execCommand('styleWithCSS', false, true); } catch (e) {} document.execCommand(cmd, false, val == null ? null : val); syncTeBar(); updateTextPreview(); }
  let teSwatchesBuilt = false;
  function buildTeSwatches() {
    if (teSwatchesBuilt) return; teSwatchesBuilt = true;
    const mk = (gridId, onPick, noneLabel) => {
      const grid = document.getElementById(gridId);
      if (noneLabel) { const n = document.createElement('div'); n.className = 'cp-none'; n.textContent = noneLabel; n.addEventListener('click', () => onPick('')); grid.appendChild(n); }
      BASE_COLORS.forEach((c) => { const sw = document.createElement('div'); sw.className = 'cp-sw'; sw.style.background = c; sw.dataset.color = c; sw.title = c; sw.addEventListener('click', () => onPick(c)); grid.appendChild(sw); });
    };
    mk('te-color-grid', (c) => { teExec('foreColor', c || '#1f2937'); teCloseP(); });
    mk('te-hilite-grid', (c) => { const col = c || 'transparent'; teEdit.focus(); try { document.execCommand('styleWithCSS', false, true); } catch (e) {} if (!document.execCommand('hiliteColor', false, col)) document.execCommand('backColor', false, col); updateTextPreview(); teCloseP(); }, 'Убрать фон');
    mk('te-boxbg-grid', (c) => { teBox.boxBg = c; layoutTextEditor(); teCloseP(); }, 'Прозрачный');
  }
  function syncTeBar() {
    teBar.querySelectorAll('.te-b[data-cmd]').forEach((b) => { let on = false; try { on = document.queryCommandState(b.dataset.cmd); } catch (e) {} b.classList.toggle('te-on', on); });
  }
  const tePreview = document.getElementById('te-preview');
  let teAnchor = null; // (не используется в оконном режиме, оставлено для совместимости)
  // Живой предпросмотр: как отрисуется текст (шрифт/кегль/цвет/выравнивание/фон + формулы).
  let tePrevTimer = null;
  function updateTextPreview() {
    if (!tePreview) return;
    tePreview.style.fontFamily = teBox.font || TEXT_FONT;
    tePreview.style.fontSize = (teBox.fontSize || TE_DEFAULT_SIZE) + 'px';
    tePreview.style.color = teBox.color || '#1f2937';
    tePreview.style.textAlign = teBox.align || 'left';
    tePreview.style.background = teBox.boxBg || '';
    if (!(teEdit.textContent || '').trim()) { tePreview.innerHTML = '<span style="color:#b0b0ba;font-size:13px">пусто — здесь появится предпросмотр</span>'; return; }
    tePreview.innerHTML = linkifyHtml(teEdit.innerHTML);
    if (!teBox.plain && window.MathJax && MathJax.typesetPromise) {
      tePreview.querySelectorAll('mjx-assistive-mml').forEach((e) => e.remove());
      MathJax.typesetPromise([tePreview]).then(() => { tePreview.querySelectorAll('mjx-assistive-mml').forEach((e) => e.remove()); }).catch(() => {});
    }
  }
  function schedulePreview() { if (tePrevTimer) clearTimeout(tePrevTimer); tePrevTimer = setTimeout(updateTextPreview, 200); }
  // Окно редактора — по центру сверху; поля тулбара синхронизируем с teBox; превью обновляем.
  function layoutTextEditor() {
    const pw = tePanel.offsetWidth || 540;
    let left = Math.max(12, Math.round((window.innerWidth - pw) / 2));
    tePanel.style.left = left + 'px';
    tePanel.style.top = '72px';
    teFont.value = teBox.font || TEXT_FONT; teSize.value = teBox.fontSize || TE_DEFAULT_SIZE;
    updateTextPreview();
  }
  function setTeHint() {
    const h = textEditor.querySelector('.te-hint'); if (!h) return;
    h.textContent = teBox.plain
      ? 'Обычный текст (без формул). Ссылки распознаются. Ctrl+Enter — готово, Esc — отмена'
      : 'Формулы — внутри $…$. Ссылки распознаются. Ctrl+Enter — готово, Esc — отмена';
  }
  function openTextEditor(plain) {
    teLog({ ev: 'openNew', plain: !!plain });
    buildTeSwatches(); teEl = null; teHiddenNode = null; teAnchor = null; textInsertPos = worldPoint();
    teBox = { font: TEXT_FONT, fontSize: TE_DEFAULT_SIZE, color: strokeColor, align: 'left', boxBg: '', wrapWidth: 0, plain: !!plain };
    teEdit.innerHTML = ''; setTeHint();
    clearSelection(); // без рамки выделения — правим «начисто»
    textEditor.hidden = false; teCloseP(); layoutTextEditor(); teEdit.focus();
  }
  function openTextEditorFor(el) {
    teLog({ ev: 'openFor', id: el.id, editorWasOpen: !textEditor.hidden, prevHiddenNode: teHiddenNode ? teHiddenNode.id() : null });
    buildTeSwatches(); teEl = el; const d = el.data;
    teBox = { font: d.font || TEXT_FONT, fontSize: d.fontSize || TE_DEFAULT_SIZE, color: d.color || strokeColor, align: d.align || 'left', boxBg: d.boxBg || '', wrapWidth: d.wrapWidth || 0, plain: !!d.plain };
    teEdit.innerHTML = textContentHtml(d); setTeHint();
    teHiddenNode = null; teAnchor = null; // окно отдельное — узел на доске не прячем
    clearSelection();
    textEditor.hidden = false; teCloseP(); layoutTextEditor(); teEdit.focus();
    const r = document.createRange(); r.selectNodeContents(teEdit); r.collapse(false); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    syncTeBar(); updateTextPreview();
  }
  function restoreHiddenTextNode() { if (teHiddenNode) { teHiddenNode.visible(true); layer.batchDraw(); teHiddenNode = null; } }
  function closeTextEditor() { teLog({ ev: 'close', hadHiddenNode: teHiddenNode ? teHiddenNode.id() : null }); textEditor.hidden = true; teCloseP(); restoreHiddenTextNode(); teEl = null; }
  let teCommitting = false;
  function commitText() {
    if (teCommitting) { teLog({ ev: 'commit-reentry-blocked' }); return; } // защита от повторного входа
    teCommitting = true;
    const html = teEdit.innerHTML, plain = (teEdit.textContent || '').trim();
    teLog({ ev: 'commit-enter', teEl: teEl ? teEl.id : null, plainLen: plain.length, htmlLen: html.length, html: html.slice(0, 80) });
    try {
      if (!plain) { // пусто — новый не создаём; существующий (очистили) удаляем
        teLog({ ev: 'commit-DELETE', teEl: teEl ? teEl.id : null });
        if (teEl) { const gid = teEl.id; teHiddenNode = null; histDel(teEl); send({ action: 'element_delete', id: gid }); removeNode(gid); }
        return;
      }
      if (teEl) {
        teLog({ ev: 'commit-UPDATE', id: teEl.id });
        const el = teEl, before = clone(el), d = el.data;
        d.html = html; d.text = plain; d.font = teBox.font; d.fontSize = teBox.fontSize; d.color = teBox.color; d.align = teBox.align; d.boxBg = teBox.boxBg; d.plain = teBox.plain;
        delete d.width; delete d.height; // пересчитать размер под новый контент
        if (teHiddenNode) { teHiddenNode.visible(true); teHiddenNode = null; } // вернуть узел ДО перерисовки
        upsertNode(el); histUpd(before, el); send({ action: 'element_update', element: el });
      } else {
        teLog({ ev: 'commit-NEW' });
        const el = { id: uuid(), type: 'text', z: 0, data: { x: textInsertPos.x, y: textInsertPos.y, html, text: plain, color: teBox.color, fontSize: teBox.fontSize, font: teBox.font, align: teBox.align, boxBg: teBox.boxBg, plain: teBox.plain } };
        upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
      }
    } catch (err) {
      teLog({ ev: 'commit-ERROR', err: String(err && err.stack || err) });
      try { console.error('commitText error', err); } catch (e) {}
    } finally {
      teLog({ ev: 'commit-finally' });
      closeTextEditor(); setTool('select'); clearSelection(); // без рамки выделения после правки
      if (handlesGroup.visible()) handlesGroup.hide();
      if (connHandles.visible()) connHandles.hide();
      tr.nodes([]); layer.batchDraw(); teCommitting = false;
    }
  }

  if (teEdit) {
    // Сохраняем выделение при кликах по тулбару/попапам (иначе execCommand теряет его).
    textEditor.addEventListener('mousedown', (e) => { if (e.target.closest('#te-edit, #te-font, #te-size')) return; e.preventDefault(); });
    teBar.querySelectorAll('.te-b[data-cmd]').forEach((b) => b.addEventListener('click', () => teExec(b.dataset.cmd)));
    document.getElementById('te-color-btn').addEventListener('click', () => teToggleP('color'));
    document.getElementById('te-hilite-btn').addEventListener('click', () => teToggleP('hilite'));
    document.getElementById('te-boxbg-btn').addEventListener('click', () => teToggleP('boxbg'));
    teFont.addEventListener('change', () => { teBox.font = teFont.value; layoutTextEditor(); });
    teSize.addEventListener('change', () => { const v = Math.max(8, Math.min(200, parseInt(teSize.value, 10) || TE_DEFAULT_SIZE)); teSize.value = v; teBox.fontSize = v; layoutTextEditor(); });
    teEdit.addEventListener('keyup', syncTeBar);
    teEdit.addEventListener('mouseup', syncTeBar);
    teEdit.addEventListener('input', () => { syncTeBar(); schedulePreview(); });
    teEdit.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); commitText(); }
      else if (e.key === 'Escape') { e.preventDefault(); closeTextEditor(); }
    });
    document.getElementById('te-insert').addEventListener('click', commitText);
    document.getElementById('te-cancel').addEventListener('click', closeTextEditor);
    // Окно с предпросмотром: клик мимо НЕ коммитит (завершение — Готово/Отмена/Esc).
    // Блокируем клик, чтобы он не дошёл до холста (иначе откроется второй редактор/рисование).
    document.addEventListener('mousedown', (e) => {
      if (textEditor.hidden) return;
      if (e.target.closest('#text-editor')) return; // клик по окну/попапу
      e.stopPropagation(); e.preventDefault();
    }, true);
  }

  toolButtons.forEach((b) => b.addEventListener('click', () => {
    // Повторный клик по уже выбранному «Выделению» — переход в перемещение доски.
    if (b.dataset.tool === 'select' && tool === 'select' && !panMode) { setPanMode(true); return; }
    if (panMode) setPanMode(false);           // любой другой инструмент выводит из перемещения
    setTool(b.dataset.tool);
  }));

  // ── Группы инструментов с выпадающим подменю (математика, материалы) ───
  (function initToolGroups() {
    const groups = Array.from(document.querySelectorAll('#board-toolbar .tool-group'));
    if (!groups.length) return;
    const defIcon = new Map();
    groups.forEach((g) => defIcon.set(g, g.querySelector('.grp-icon').innerHTML));
    // Чем в группе пользовались в последний раз. Нажатие на саму группу
    // включает именно его: человек, который рисует ластиком, ждёт ластик, а не
    // карандаш только потому, что тот в списке первый.
    const lastInGroup = new Map();
    groups.forEach((g) => {
      const act = g.querySelector('.tool[data-tool].active') || g.querySelector('.tool[data-tool]');
      if (act) lastInGroup.set(g.dataset.group, act.dataset.tool);
      g.querySelectorAll('.tool[data-tool]').forEach((b) => {
        b.addEventListener('click', () => lastInGroup.set(g.dataset.group, b.dataset.tool));
      });
    });
    function closeAll(except) {
      groups.forEach((g) => { if (g !== except) g.querySelector('.tool-flyout').classList.remove('open'); });
    }
    groups.forEach((g) => {
      const fly = g.querySelector('.tool-flyout');
      g.addEventListener('click', (e) => {
        if (e.target.closest('.tool-flyout')) return; // клик по под-инструменту — не трогаем
        e.stopPropagation();
        // Состояние панели запоминаем ДО переключения инструмента: взяв в руку
        // карандаш, syncDrawFlyout сам открывает панель рисования (там толщина
        // и цвет), и проверка «была ли открыта» иначе видела бы уже открытую —
        // нажатие закрывало бы только что открытое.
        const wasOpen = fly.classList.contains('open');
        // Сразу берём инструмент группы в руки. Если он уже активен (в группе
        // есть подсвеченный под-инструмент), ничего не переключаем — нажатие
        // тогда просто открывает и закрывает панель.
        if (!g.querySelector('.tool[data-tool].active')) {
          const want = lastInGroup.get(g.dataset.group);
          const sub = (want && g.querySelector('.tool[data-tool="' + want + '"]'))
            || g.querySelector('.tool[data-tool]');
          if (sub) setTool(sub.dataset.tool);
        }
        const open = !wasOpen;
        closeAll(g);
        if (open) {
          const r = g.getBoundingClientRect();
          fly.style.left = (r.right + 10) + 'px';
          fly.style.top = r.top + 'px';
          fly.classList.add('open');
          // Не даём высокому меню уехать за нижний край экрана — сдвигаем вверх.
          const fh = fly.offsetHeight, vh = window.innerHeight;
          let top = r.top;
          if (top + fh > vh - 8) top = Math.max(8, vh - fh - 8);
          fly.style.top = top + 'px';
        } else { fly.classList.remove('open'); }
      });
      // Меню рисования НЕ закрываем при выборе под-инструмента — под лассо живут настройки.
      if (g.dataset.group !== 'draw') fly.querySelectorAll('.tool[data-tool]').forEach((b) => b.addEventListener('click', () => fly.classList.remove('open')));
    });
    // Клик по пустому месту/холсту закрывает меню — кроме меню рисования, пока активен его инструмент.
    // Панель группы держим открытой, пока в руке её инструмент: там живут
    // толщина и цвет, и закрывать её на каждый щелчок по холсту неудобно.
    document.addEventListener('click', (e) => {
      const inGroup = e.target && e.target.closest && e.target.closest('.tool-group');
      if (!inGroup) closeAll(isDrawToolActive() ? (cfgGroupEl() || document.querySelector('.tool-group[data-group="draw"]')) : null);
    });
    // Отразить активный под-инструмент на кнопке группы (иконка + подсветка).
    function syncGroups() {
      groups.forEach((g) => {
        const active = g.querySelector('.tool[data-tool].active');
        const icon = g.querySelector('.grp-icon');
        if (active) { g.classList.add('active'); icon.innerHTML = active.querySelector('svg').outerHTML; }
        else { g.classList.remove('active'); icon.innerHTML = defIcon.get(g); }
      });
    }
    const obs = new MutationObserver(syncGroups);
    document.querySelectorAll('#board-toolbar .tool-flyout .tool[data-tool]')
      .forEach((b) => obs.observe(b, { attributes: true, attributeFilter: ['class'] }));
    syncGroups();
  })();

  // ── Перетаскивание инструментов левой панели (свой порядок, в localStorage) ──
  // Двигать можно верхнеуровневые кнопки-инструменты и группы (до первого разделителя);
  // под-инструменты в флайаутах и служебные кнопки (отмена/очистка/цвет) не трогаем.
  (function initToolbarReorder() {
    const bar = document.getElementById('board-toolbar');
    if (!bar) return;
    const KEY = 'board-toolbar-order-v1', SEL = '.tool[data-tool], .tool-group';
    const isMovable = (el) => !!(el && el.parentElement === bar && el.matches && el.matches(SEL));
    const keyOf = (el) => el.dataset.tool ? el.dataset.tool : ('group:' + el.dataset.group);
    const movables = () => Array.from(bar.children).filter(isMovable);
    const refNode = () => bar.querySelector('hr'); // блок инструментов — до первого разделителя
    function save() { try { localStorage.setItem(KEY, JSON.stringify(movables().map(keyOf))); } catch (e) {} }
    function applySaved() {
      let order; try { order = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return; }
      if (!Array.isArray(order)) return;
      const map = new Map(); movables().forEach((el) => map.set(keyOf(el), el));
      const used = new Set(), seq = [];
      order.forEach((k) => { const el = map.get(k); if (el) { seq.push(el); used.add(el); } });
      movables().forEach((el) => { if (!used.has(el)) seq.push(el); });
      const ref = refNode();
      seq.forEach((el) => bar.insertBefore(el, ref));
    }
    movables().forEach((el) => el.setAttribute('draggable', 'true'));
    let dragEl = null;
    bar.addEventListener('dragstart', (e) => {
      // Тянут подынструмент из выпадающего меню — это перетаскивание на холст
      // (см. initToolDragToCanvas). Родное HTML5-перетаскивание группы гасим,
      // иначе оно перехватит жест: флайаут лежит внутри кнопки-группы.
      if (e.target.closest && e.target.closest('.tool-flyout')) { e.preventDefault(); dragEl = null; return; }
      const it = e.target.closest(SEL);
      if (!isMovable(it)) { dragEl = null; return; }
      // Закрываем открытые флайауты: они спозиционированы фиксированно по месту
      // кнопки и при перетаскивании «зависли» бы на старом месте.
      document.querySelectorAll('#board-toolbar .tool-flyout.open').forEach((f) => f.classList.remove('open'));
      dragEl = it; it.classList.add('tool-dragging');
      if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
    });
    bar.addEventListener('dragend', () => { if (dragEl) dragEl.classList.remove('tool-dragging'); dragEl = null; });
    bar.addEventListener('dragover', (e) => {
      if (!dragEl) return;
      const it = e.target.closest(SEL);
      if (!isMovable(it) || it === dragEl) return;
      e.preventDefault();
      const r = it.getBoundingClientRect();
      bar.insertBefore(dragEl, (e.clientY < r.top + r.height / 2) ? it : it.nextSibling);
    });
    bar.addEventListener('drop', (e) => { if (dragEl) { e.preventDefault(); save(); } });
    applySaved();
  })();

  // ── Перетаскивание инструмента с панели прямо на холст (как в Miro) ─────
  // Обычный клик по инструменту работает как раньше: выбрал — щёлкнул по доске.
  // Но кнопку можно и просто перетащить на холст — объект появится там, где
  // отпустили. Слушаем события указателя (pointer), а не HTML5-перетаскивание:
  // только так один и тот же код работает мышью, пальцем и пером.

  // Короткая подпись из подсказки: «Стикер — цветная заметка» → «Стикер».
  function toolShortTitle(el) {
    const t = (el && el.getAttribute && el.getAttribute('title')) || '';
    return t.split(/[—(:]/)[0].trim();
  }

  // Размеры по умолчанию для того, что обычно рисуют протяжкой рамки.
  const DROP_SIZE = { rect: [180, 120], ellipse: [180, 120], shape: [160, 120], frame: [640, 460] };

  // Инструменты, создающие объект «в точке». Ключ — имя инструмента.
  const DROP_MAKE = {
    sticky: insertSticky, comment: insertComment, card: insertCard, table: insertTable, kanban: insertKanban,
    timer: insertTimer, wheel: insertWheel, slider: insertSlider,
    text_plain: insertTextbox, geogebra: insertGeoGebra, point: placePoint, embed: insertEmbed, poll: insertPoll, venn: insertVenn,
    screen: function () { setTool('select'); startScreenShare(); },
    text: function () { openTextEditor(false); },
    latex: function () { openLatexEditor(); },
  };
  function isDropTool(name) {
    return !!(DROP_MAKE[name] || SHAPE_TOOLS[name]
      || name === 'rect' || name === 'ellipse' || name === 'frame');
  }

  // Фигуры и матокно при броске ставим готового размера, центром в точку броска.
  function dropCreateShape(name, w) {
    const base = { stroke: strokeColor, strokeWidth: strokeWidth };
    let el = null, W, H;
    if (name === 'rect') {
      W = DROP_SIZE.rect[0]; H = DROP_SIZE.rect[1];
      el = { id: uuid(), type: 'rect', z: 0, data: Object.assign({}, base, { x: w.x - W / 2, y: w.y - H / 2, width: W, height: H }) };
    } else if (name === 'ellipse') {
      W = DROP_SIZE.ellipse[0]; H = DROP_SIZE.ellipse[1];
      el = { id: uuid(), type: 'ellipse', z: 0, data: Object.assign({}, base, { x: w.x, y: w.y, radiusX: W / 2, radiusY: H / 2 }) };
    } else if (name === 'frame') {
      W = DROP_SIZE.frame[0]; H = DROP_SIZE.frame[1];
      el = { id: uuid(), type: 'frame', z: 0, data: { x: w.x - W / 2, y: w.y - H / 2, width: W, height: H, cx: 0, cy: 0, unit: 40 } };
    } else if (SHAPE_TOOLS[name]) {
      W = DROP_SIZE.shape[0]; H = DROP_SIZE.shape[1];
      el = { id: uuid(), type: 'shape', z: 0, data: Object.assign({}, base, { color: strokeColor, x: w.x - W / 2, y: w.y - H / 2, width: W, height: H, kind: SHAPE_TOOLS[name] }) };
    }
    if (!el) return false;
    upsertNode(el);
    send({ action: 'element_add', element: stripPrivate(el) });
    histAdd(stripPrivate(el));
    setTool('select');
    return true;
  }

  // Создать объект инструмента name там, где отпустили указатель.
  function createToolAt(name, ev) {
    // Сообщаем Konva позицию указателя из события броска: вся дальнейшая логика
    // создания читает координаты указателя, и объект встанет ровно в эту точку.
    try { stage.setPointersPositions(ev); } catch (e) { return; }
    const w = stage.getRelativePointerPosition();
    if (!w) return;
    if (dropCreateShape(name, w)) return;
    const make = DROP_MAKE[name];
    if (make) make();
  }

  // Подключает перетаскивание на холст к контейнеру с кнопками инструментов.
  // Вызывается и для панели компьютера, и для мобильного листа.
  function enableToolDragToCanvas(bar) {
    if (!bar) return;
    // Панели поверх холста — бросать в них нельзя.
    const PANELS = '#board-toolbar, #board-topbar, #board-head, #board-menu, #history-panel,'
      + ' #people-panel, .tool-flyout, .settings-panel, .conn-panel, #zoom-control, #settings-btn,'
      + ' #settings-menu, #color-palette, #latex-editor, #text-editor, #func-editor, #tbox-bar,'
      + ' #dp-pop, #eraser-panel, #storyboard, #pdf-controls, #frame-exit-btn,'
      + ' #mobile-sheet, #mobile-fab, #mobile-backdrop';
    const THRESHOLD = 8; // сдвиг меньше этого — обычный клик, а не перетаскивание
    let src = null, ghost = null, pid = null, startX = 0, startY = 0, dragging = false;

    // Помечаем перетаскиваемые кнопки: им нужен touch-action: none, иначе на
    // касании жест уедет в прокрутку панели вместо перетаскивания.
    bar.querySelectorAll('[data-tool]').forEach((b) => {
      if (isDropTool(b.dataset.tool)) b.classList.add('tool-draggable');
    });

    function makeGhost(btn) {
      const g = document.createElement('div');
      g.className = 'tool-ghost';
      g.innerHTML = btn.innerHTML;
      const cap = toolShortTitle(btn);
      if (cap) { const s2 = document.createElement('span'); s2.className = 'tg-cap'; s2.textContent = cap; g.appendChild(s2); }
      document.body.appendChild(g);
      return g;
    }
    function dropAllowed(x, y) {
      const r = stageEl.getBoundingClientRect();
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) return false;
      const t = document.elementFromPoint(x, y);
      return !(t && t.closest && t.closest(PANELS));
    }
    // После перетаскивания браузер шлёт click по кнопке — он выбрал бы инструмент.
    // Гасим ровно один такой клик.
    function suppressNextClick() {
      const kill = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
      document.addEventListener('click', kill, true);
      setTimeout(() => document.removeEventListener('click', kill, true), 0);
    }
    function cleanup() {
      if (src) { try { src.releasePointerCapture(pid); } catch (e) {} src.classList.remove('tool-dragging'); }
      if (ghost) { ghost.remove(); ghost = null; }
      document.body.classList.remove('tool-dragging-body');
    }
    function finish(e, place) {
      const wasDragging = dragging, btn = src;
      cleanup();
      src = null; pid = null; dragging = false;
      if (!wasDragging) return;      // просто клик — обычный выбор инструмента
      suppressNextClick();
      if (place && btn && dropAllowed(e.clientX, e.clientY)) createToolAt(btn.dataset.tool, e);
    }

    bar.addEventListener('pointerdown', (e) => {
      if (e.button != null && e.button > 0) return;   // правая/средняя кнопка — не наше дело
      const btn = e.target.closest('[data-tool]');
      if (!btn || !isDropTool(btn.dataset.tool)) return;
      src = btn; pid = e.pointerId; startX = e.clientX; startY = e.clientY; dragging = false;
      try { btn.setPointerCapture(pid); } catch (err) {}
    });
    bar.addEventListener('pointermove', (e) => {
      if (!src || e.pointerId !== pid) return;
      if (!dragging) {
        if (Math.hypot(e.clientX - startX, e.clientY - startY) < THRESHOLD) return;
        dragging = true;
        // Флайауты спозиционированы по месту кнопки — при перетаскивании закрываем.
        document.querySelectorAll('#board-toolbar .tool-flyout.open').forEach((f) => f.classList.remove('open'));
        if (typeof closeMobileSheet === 'function') closeMobileSheet();
        ghost = makeGhost(src);
        src.classList.add('tool-dragging');
        document.body.classList.add('tool-dragging-body');
      }
      e.preventDefault();
      ghost.style.left = e.clientX + 'px';
      ghost.style.top = e.clientY + 'px';
      ghost.classList.toggle('over', dropAllowed(e.clientX, e.clientY));
    });
    bar.addEventListener('pointerup', (e) => { if (src && e.pointerId === pid) finish(e, true); });
    bar.addEventListener('pointercancel', (e) => { if (src && e.pointerId === pid) finish(e, false); });
    // Esc во время перетаскивания — отменить.
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && cropId) { endCropMode(); boardHint('Обрезка отменена'); return; }
      // Панель участников закрывается Escape наравне с крестиком и щелчком мимо.
      if (e.key === 'Escape') { const pp = document.getElementById('people-panel'); if (pp && !pp.hidden) { togglePeoplePanel(false); return; } }
      if (e.key === 'Escape' && panMode && !dragging) { setPanMode(false); return; }
    if (e.key === 'Escape' && dragging) {
        const btn = src; cleanup(); src = null; pid = null; dragging = false;
        if (btn) suppressNextClick();
      }
    });
  }
  enableToolDragToCanvas(document.getElementById('board-toolbar'));

  // Ползунок убран с панели; привязку оставляем на случай, если он вернётся.
  const swInput = document.getElementById('stroke-width');
  if (swInput) swInput.addEventListener('input', (e) => { strokeWidth = parseFloat(e.target.value); });

  // ── Палитра цветов ─────────────────────────────────────────────────────
  // 16 базовых цветов + свои (в localStorage). Выделены объекты → перекрашиваем
  // их (группа однотипных — тоже); иначе задаём цвет по умолчанию для новых.
  const BASE_COLORS = ['#1f2937', '#6b7280', '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e',
    '#10b981', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#ffffff'];
  const COLOR_STORE = 'board_custom_colors';
  function loadCustomColors() { try { return JSON.parse(localStorage.getItem(COLOR_STORE) || '[]'); } catch (e) { return []; } }
  function saveCustomColors(list) { try { localStorage.setItem(COLOR_STORE, JSON.stringify(list.slice(0, 16))); } catch (e) {} }
  let customColors = loadCustomColors();

  const colorBtn = document.getElementById('color-btn');
  const palette = document.getElementById('color-palette');
  const cpBase = document.getElementById('cp-base');
  const cpCustom = document.getElementById('cp-custom');
  const cpScope = document.getElementById('cp-scope');
  const cpNative = document.getElementById('cp-native');

  // Поля цвета зависят от типа: у части объектов это data.stroke, у геометрии — data.color.
  function setElColor(el, color) {
    el.data.color = color;
    el.data.stroke = color;
    const n = nodes.get(el.id); if (!n) return;
    if (el.type === 'point') {
      const lbl = n.findOne('.plabel'); if (lbl) lbl.fill(color); // глиф читает data.color сам
    } else if (typeof n.stroke === 'function') {
      n.stroke(color);
      if (isFilledPoly(el.type) && typeof n.fill === 'function') n.fill(hexToRgba(color, 0.10)); // полупрозрачная заливка
      if (el.type === 'vector' && typeof n.fill === 'function') n.fill(color); // наконечник стрелки
    }
    // angle рисуется sceneFunc'ом по data.color — перерисуется на batchDraw.
  }
  function applyColorTo(ids, color) {
    ids.forEach((id) => {
      const el = elements.get(id); if (!el) return;
      const before = clone(el); setElColor(el, color); histUpd(before, el);
      send({ action: 'element_update', element: el });
    });
    refreshConstructionHighlight(); // вернуть подсветку выделенным линиям/окружностям
    layer.batchDraw();
  }
  function applyColorToAllPoints(color) {
    const ids = []; elements.forEach((el) => { if (el.type === 'point') ids.push(el.id); });
    applyColorTo(ids, color);
  }
  // Выбор цвета: есть выделение → перекрасить его; иначе — цвет по умолчанию.
  function chooseColor(color) {
    if (selected.size) { applyColorTo(Array.from(selected), color); }
    else { strokeColor = color; }
    colorBtn.style.background = color;
    renderPalette();
  }
  function swatch(color, container) {
    const b = document.createElement('div');
    b.className = 'cp-sw'; b.style.background = color; b.title = color;
    const cur = selected.size ? null : strokeColor;
    if (cur && cur.toLowerCase() === color.toLowerCase()) b.classList.add('cp-sel');
    b.addEventListener('click', () => chooseColor(color));
    container.appendChild(b);
  }
  function renderPalette() {
    cpScope.textContent = selected.size ? ('Перекрасить выделенные (' + selected.size + ')') : 'Цвет по умолчанию (для новых)';
    cpBase.innerHTML = ''; BASE_COLORS.forEach((c) => swatch(c, cpBase));
    cpCustom.innerHTML = '';
    if (!customColors.length) { const e = document.createElement('div'); e.className = 'cp-custom-empty'; e.textContent = 'пока нет'; cpCustom.appendChild(e); }
    else customColors.forEach((c) => swatch(c, cpCustom));
  }
  function openPalette() {
    renderPalette();
    const r = colorBtn.getBoundingClientRect();
    palette.style.left = (r.right + 10) + 'px';
    palette.style.top = Math.max(8, r.top - 40) + 'px';
    palette.classList.remove('cp-hidden');
  }
  function closePalette() { palette.classList.add('cp-hidden'); }
  colorBtn.style.background = strokeColor;
  colorBtn.addEventListener('click', (e) => { e.stopPropagation(); palette.classList.contains('cp-hidden') ? openPalette() : closePalette(); });
  palette.addEventListener('click', (e) => e.stopPropagation());
  document.addEventListener('click', (e) => { if (!palette.classList.contains('cp-hidden') && e.target !== colorBtn) closePalette(); });
  document.getElementById('cp-add').addEventListener('click', () => cpNative.click());
  cpNative.addEventListener('input', (e) => {
    const c = e.target.value;
    if (customColors.indexOf(c) < 0) { customColors.unshift(c); saveCustomColors(customColors); customColors = loadCustomColors(); }
    chooseColor(c); // выбрать сразу
    renderPalette();
  });
  document.getElementById('cp-all').addEventListener('click', () => { applyColorToAllPoints(strokeColor); });

  // ── Настройки точки (панель справа сверху) ─────────────────────────────
  const settingsBtn = document.getElementById('settings-btn');
  const pointSettings = document.getElementById('point-settings');
  const SHAPE_ICONS = {
    dot: '<circle cx="9" cy="9" r="5" fill="currentColor"/>',
    open: '<circle cx="9" cy="9" r="4.5" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    cross: '<path d="M5 5l8 8M13 5l-8 8" stroke="currentColor" stroke-width="1.8" fill="none"/>',
    plus: '<path d="M9 4v10M4 9h10" stroke="currentColor" stroke-width="1.8" fill="none"/>',
    square: '<rect x="4.5" y="4.5" width="9" height="9" fill="currentColor"/>',
    diamond: '<path d="M9 3l6 6-6 6-6-6z" fill="currentColor"/>',
    triangle: '<path d="M9 3.5l5.5 11h-11z" fill="currentColor"/>',
  };
  function selectedPoints() { return Array.from(selected).map((id) => elements.get(id)).filter((e) => e && e.type === 'point'); }
  function allPoints() { const a = []; elements.forEach((el) => { if (el.type === 'point') a.push(el); }); return a; }
  // Режим панели: 'selection' — по выделенным; 'all' — по всем точкам доски.
  let psMode = 'selection';
  // «Применять только к новым»: в режиме «все …» изменение задаёт лишь дефолт типа
  // (для будущих объектов), существующие объекты не трогаются. Общий флаг для обеих панелей.
  let onlyNew = false;
  function targetPoints() { return psMode === 'all' ? allPoints() : selectedPoints(); }
  // Применить изменение к целевым точкам (выделенным или всем — по режиму панели).
  function applyPointSetting(mutator) {
    if (onlyNew && psMode === 'all') { renderPointSettings(); return; } // только дефолт, existing не трогаем
    const pts = targetPoints(); // может быть пусто (режим «все» на доске без точек) — дефолт уже записан
    pts.forEach((el) => { const before = clone(el); mutator(el); histUpd(before, el); });
    if (pts.length) recomputeGeometry();
    pts.forEach((el) => { const n = nodes.get(el.id); if (n) n.draggable(tool === 'select' && !el.data.locked && !isDerivedPoint(el)); updatePointLabel(el); send({ action: 'element_update', element: el }); });
    if (pts.length) layer.batchDraw();
    renderPointSettings(); // всегда — чтобы подсветка/значения отражали дефолт типа
  }
  // Ближайшая фигура (линия/окружность) окна к точке, не зависящая от неё (без цикла).
  function nearestCurveToPoint(fr, lp, exclude) {
    const TOL = 12 / stage.scaleX();
    const deps = new Set(directDependents(exclude));
    let best = null, bd = TOL;
    elements.forEach((el) => {
      if (el.id === exclude || el.data.frame !== fr.id || !isCurveType(el.type) || deps.has(el.id)) return;
      const g = curveGeom(el); if (!g) return;
      const d = distToCurve(g, lp); if (d < bd) { bd = d; best = el; }
    });
    return best;
  }
  function detachPoint(el) {
    const fr = el.data.frame ? elements.get(el.data.frame) : null, n = nodes.get(el.id);
    if (fr && n) { const m = frameLocalToMath(fr, n.x(), n.y()); el.data.mx = m.mx; el.data.my = m.my; }
    delete el.data.on;
  }
  function attachPointToNearest(el) {
    const fr = el.data.frame ? elements.get(el.data.frame) : null; if (!fr) { boardHint('Привязка — только в окне'); return; }
    const lp = frameMathToLocal(fr, el.data.mx || 0, el.data.my || 0);
    const c = nearestCurveToPoint(fr, lp, el.id);
    if (!c) { boardHint('Рядом нет фигуры для привязки'); return; }
    const g = curveGeom(c);
    if (g.type === 'line') { let t = (lp.x - g.base.x) * g.u.x + (lp.y - g.base.y) * g.u.y; t = Math.max(g.tmin, Math.min(g.tmax, t)); el.data.on = { line: c.id, t: t }; }
    else { const C = circleGeom(c); el.data.on = { circle: c.id, a: Math.atan2(lp.y - C.cy, lp.x - C.cx) }; }
  }
  function renderBindSection(el) {
    const box = document.getElementById('ps-bind'); box.innerHTML = '';
    if (!el) return;
    const on = el.data.on, bound = on && (on.line || on.circle || on.isect || on.c);
    const btn = document.createElement('button');
    if (bound) { btn.textContent = 'Снять привязку (сделать свободной)'; btn.addEventListener('click', () => applyPointSetting(detachPoint)); }
    else { btn.textContent = 'Привязать к ближайшей фигуре'; btn.addEventListener('click', () => applyPointSetting(attachPointToNearest)); }
    box.appendChild(btn);
  }
  // Живое изменение (во время движения ползунка) — без сети/истории.
  function livePointSetting(mutator) {
    if (onlyNew && psMode === 'all') return; // только дефолт — existing не двигаем
    targetPoints().forEach(mutator); recomputeGeometry();
    targetPoints().forEach(updatePointLabel); layer.batchDraw();
  }
  function renderPointSettings() {
    const pts = targetPoints(), el = pts[0], d = el ? el.data : {};
    // В режиме «все …» панель отражает ДЕФОЛТ типа (typeDefaults), а не первый объект
    // (иначе на пустой доске/при разных объектах подсветка не совпадала с заданным).
    const eff = psMode === 'all' ? Object.assign({}, d, typeDefaults.point) : d;
    document.getElementById('ps-head').textContent = psMode === 'all'
      ? ('Все точки (' + pts.length + ')')
      : (!pts.length ? 'Выделите точку' : (pts.length > 1 ? ('Настройки точек (' + pts.length + ')') : 'Настройки точки'));
    // Переименование и привязка — только по одиночному выделению (не для «всех»).
    const perPoint = psMode !== 'all' && pts.length === 1;
    document.getElementById('ps-rename-row').style.display = perPoint ? '' : 'none';
    document.getElementById('ps-bind').style.display = perPoint ? '' : 'none';
    const sz = numSize(eff.size), lsz = numSize(eff.labelSize);
    document.getElementById('ps-size-range').value = sz; document.getElementById('ps-size-num').value = sz;
    document.getElementById('ps-labelsize-range').value = lsz; document.getElementById('ps-labelsize-num').value = lsz;
    document.querySelectorAll('#ps-shape button').forEach((b) => b.classList.toggle('ps-on', b.dataset.shape === (eff.shape || 'dot')));
    document.querySelectorAll('#ps-labelmode button').forEach((b) => b.classList.toggle('ps-on', b.dataset.mode === (eff.labelMode || 'name')));
    document.getElementById('ps-labelhide').checked = !!eff.labelHidden;
    document.getElementById('ps-rename').value = d.label || '';
    document.getElementById('ps-lock').checked = !!eff.locked;
    document.getElementById('ps-snap').checked = !!eff.snap;
    const onRow = document.getElementById('ps-onlynew-row');
    onRow.style.display = psMode === 'all' ? '' : 'none'; // «только к новым» — лишь в режиме «все»
    document.getElementById('ps-onlynew').checked = onlyNew;
    renderBindSection(el);
  }
  function syncPointSettings() { const ps = document.getElementById('point-settings'); if (ps && !ps.classList.contains('ps-hidden')) renderPointSettings(); }
  // В режиме «все точки» изменение поля становится ДЕФОЛТОМ для новых точек.
  function recPointDefault(field, value) { if (psMode === 'all') typeDefaults.point[field] = value; }
  // Кнопки формы
  (function () {
    const box = document.getElementById('ps-shape');
    Object.keys(SHAPE_ICONS).forEach((sh) => {
      const b = document.createElement('button'); b.dataset.shape = sh; b.title = sh;
      b.innerHTML = '<svg viewBox="0 0 18 18">' + SHAPE_ICONS[sh] + '</svg>';
      b.addEventListener('click', () => { recPointDefault('shape', sh); applyPointSetting((e) => { e.data.shape = sh; }); });
      box.appendChild(b);
    });
  })();
  // Ползунок + число (парой) на поле data (size / labelSize). Во время движения —
  // живое обновление, на отпускании — фиксация (сеть + история от снимка).
  function bindSizeControl(rangeId, numId, field) {
    const range = document.getElementById(rangeId), num = document.getElementById(numId);
    let snap = null;
    const startSnap = () => { snap = targetPoints().map(clone); };
    const live = (v) => { v = Math.max(1, Math.min(100, parseInt(v, 10) || 1)); range.value = v; num.value = v; recPointDefault(field, v); livePointSetting((e) => { e.data[field] = v; }); };
    const commit = () => {
      const before = snap; snap = null;
      if (onlyNew && psMode === 'all') return; // дефолт уже записан, existing не рассылаем
      if (before) before.forEach((b) => { const el = elements.get(b.id); if (el) { histUpd(b, el); send({ action: 'element_update', element: el }); } });
      else targetPoints().forEach((el) => send({ action: 'element_update', element: el }));
    };
    range.addEventListener('mousedown', startSnap);
    range.addEventListener('input', () => live(range.value));
    range.addEventListener('change', commit);
    num.addEventListener('focus', startSnap);
    num.addEventListener('input', () => live(num.value));
    num.addEventListener('change', commit);
  }
  bindSizeControl('ps-size-range', 'ps-size-num', 'size');
  bindSizeControl('ps-labelsize-range', 'ps-labelsize-num', 'labelSize');
  document.querySelectorAll('#ps-labelmode button').forEach((b) => b.addEventListener('click', () => { recPointDefault('labelMode', b.dataset.mode); applyPointSetting((e) => { e.data.labelMode = b.dataset.mode; }); }));
  document.getElementById('ps-labelhide').addEventListener('change', (ev) => { recPointDefault('labelHidden', ev.target.checked); applyPointSetting((e) => { e.data.labelHidden = ev.target.checked; }); });
  document.getElementById('ps-lock').addEventListener('change', (ev) => { recPointDefault('locked', ev.target.checked); applyPointSetting((e) => { e.data.locked = ev.target.checked; }); });
  document.getElementById('ps-snap').addEventListener('change', (ev) => { recPointDefault('snap', ev.target.checked); applyPointSetting((e) => { e.data.snap = ev.target.checked; }); });
  document.getElementById('ps-rename').addEventListener('change', (ev) => applyPointSetting((e) => { e.data.label = ev.target.value; }));
  document.getElementById('ps-onlynew').addEventListener('change', (ev) => { onlyNew = ev.target.checked; });

  // Выпадающее меню кнопки настроек (категории — точка / прямая / …).
  const settingsMenu = document.getElementById('settings-menu');
  function closeSettingsMenu() { settingsMenu.classList.add('sm-hidden'); }
  function openSettingsMenu() {
    const r = settingsBtn.getBoundingClientRect();
    settingsMenu.style.top = r.bottom + 8 + 'px';
    settingsMenu.style.right = (window.innerWidth - r.right) + 'px';
    settingsMenu.classList.remove('sm-hidden');
  }
  // ── Настройки фигур (прямая / окружность): цвет, толщина, стиль ─────────
  const figureSettings = document.getElementById('figure-settings');
  let fsMode = 'selection', fsType = 'line';
  // 'line' — бесконечные/лучи (без отрезка, у отрезка своя панель); 'segment' — отрезок; 'angle' — угол.
  function figTypeList() {
    if (fsType === 'segment') return ['segment'];
    if (fsType === 'angle') return ['angle'];
    if (fsType === 'circle') return ['circ'];
    if (fsType === 'polygon') return ['polygon', 'regpoly'];
    return CONSTRUCT_LINES.filter((t) => t !== 'segment');
  }
  function allOfTypes(types) { const a = []; elements.forEach((el) => { if (types.indexOf(el.type) >= 0) a.push(el); }); return a; }
  function selectedOfTypes(types) { return Array.from(selected).map((id) => elements.get(id)).filter((el) => el && types.indexOf(el.type) >= 0); }
  function figureTargets() { return fsMode === 'all' ? allOfTypes(figTypeList()) : selectedOfTypes(figTypeList()); }
  function applyFigureSetting(mutator) {
    if (onlyNew && fsMode === 'all') { renderFigureSettings(); return; } // только дефолт, existing не трогаем
    const fs = figureTargets(); // может быть пусто (режим «все» без фигур этого типа) — дефолт уже записан
    fs.forEach((el) => { const before = clone(el); mutator(el); histUpd(before, el); applyFigureVisual(el); send({ action: 'element_update', element: el }); });
    if (fs.length) { refreshConstructionHighlight(); layer.batchDraw(); }
    renderFigureSettings(); // всегда — чтобы подсветка отражала дефолт типа
  }
  function liveFigureSetting(mutator) { if (onlyNew && fsMode === 'all') return; figureTargets().forEach((el) => { mutator(el); applyFigureVisual(el); }); layer.batchDraw(); }
  function renderFigureSettings() {
    const fs = figureTargets(), el = fs[0], d = el ? el.data : {};
    // В режиме «все …» отражаем ДЕФОЛТ типа, а не первый объект.
    const eff = fsMode === 'all' ? Object.assign({}, d, typeDefaults[fsType]) : d;
    const many = fs.length > 1 ? ' (' + fs.length + ')' : '';
    const nameAll = { line: 'Все прямые', segment: 'Все отрезки', angle: 'Все углы', circle: 'Все окружности', polygon: 'Все многоугольники' }[fsType];
    const nameSel = { line: 'Настройки прямой', segment: 'Настройки отрезка', angle: 'Настройки угла', circle: 'Настройки окружности', polygon: 'Настройки многоугольника' }[fsType];
    document.getElementById('fs-head').textContent = fsMode === 'all' ? (nameAll + ' (' + fs.length + ')') : (nameSel + many);
    const w = eff.strokeWidth || 2;
    document.getElementById('fs-width-range').value = w; document.getElementById('fs-width-num').value = w;
    document.querySelectorAll('#fs-style button').forEach((b) => b.classList.toggle('ps-on', b.dataset.style === (eff.style || 'solid')));
    document.querySelectorAll('#fs-colors .cp-sw').forEach((sw) => sw.classList.toggle('cp-sel', eff.color && eff.color.toLowerCase() === sw.dataset.color.toLowerCase()));
    // Условные строки по типу.
    const show = (id, on) => { const r = document.getElementById(id); if (r) r.style.display = on ? '' : 'none'; };
    const isLine = fsType === 'line', isSeg = fsType === 'segment', isAngle = fsType === 'angle';
    show('fs-chevrons-row', isLine || isSeg);
    show('fs-ticks-row', isSeg); show('fs-length-row', isSeg);
    show('fs-opacity-row', isAngle); show('fs-arcs-row', isAngle); show('fs-degree-row', isAngle);
    const segN = (v, def) => String(v == null ? def : v);
    document.querySelectorAll('#fs-chevrons button').forEach((b) => b.classList.toggle('ps-on', b.dataset.n === segN(eff.chevrons, 0)));
    document.querySelectorAll('#fs-ticks button').forEach((b) => b.classList.toggle('ps-on', b.dataset.n === segN(eff.eqTicks, 0)));
    document.querySelectorAll('#fs-arcs button').forEach((b) => b.classList.toggle('ps-on', b.dataset.n === segN(eff.arcCount, 1)));
    document.getElementById('fs-length').checked = !!eff.showLength;
    document.getElementById('fs-degree').checked = eff.showDegree !== false;
    const op = Math.round((eff.fillOpacity || 0) * 100);
    document.getElementById('fs-opacity-range').value = op; document.getElementById('fs-opacity-num').value = op;
    const onRow = document.getElementById('fs-onlynew-row');
    onRow.style.display = fsMode === 'all' ? '' : 'none';
    document.getElementById('fs-onlynew').checked = onlyNew;
  }
  function syncFigureSettings() { const fs = document.getElementById('figure-settings'); if (fs && !fs.classList.contains('ps-hidden')) renderFigureSettings(); }
  // В режиме «все …» изменение поля становится ДЕФОЛТОМ для новых фигур этого типа.
  function recFigDefault(field, value) { if (fsMode === 'all') typeDefaults[fsType][field] = value; }
  (function () { // свотчи цвета (16 базовых)
    const box = document.getElementById('fs-colors');
    BASE_COLORS.forEach((c) => { const sw = document.createElement('div'); sw.className = 'cp-sw'; sw.style.background = c; sw.dataset.color = c; sw.title = c; sw.addEventListener('click', () => { recFigDefault('color', c); applyFigureSetting((e) => setElColor(e, c)); }); box.appendChild(sw); });
  })();
  (function () { // толщина: ползунок + число (живое + фиксация)
    const range = document.getElementById('fs-width-range'), num = document.getElementById('fs-width-num');
    let snap = null;
    const startSnap = () => { snap = figureTargets().map(clone); };
    // Полшага, а не целое: наборы пера и фигур теперь 1.5 / 2.5 / 4, и целое
    // округление молча портило нарисованное — тронул ползунок, и 1.5 стало 1.
    const live = (v) => { v = полшага(v, 0.5, 16); range.value = v; num.value = v; recFigDefault('strokeWidth', v); liveFigureSetting((e) => { e.data.strokeWidth = v; }); };
    const commit = () => { const before = snap; snap = null; if (onlyNew && fsMode === 'all') return; if (before) before.forEach((b) => { const el = elements.get(b.id); if (el) { histUpd(b, el); send({ action: 'element_update', element: el }); } }); else figureTargets().forEach((el) => send({ action: 'element_update', element: el })); };
    range.addEventListener('mousedown', startSnap); range.addEventListener('input', () => live(range.value)); range.addEventListener('change', commit);
    num.addEventListener('focus', startSnap); num.addEventListener('input', () => live(num.value)); num.addEventListener('change', commit);
  })();
  document.querySelectorAll('#fs-style button').forEach((b) => b.addEventListener('click', () => { recFigDefault('style', b.dataset.style); applyFigureSetting((e) => { e.data.style = b.dataset.style; }); }));
  document.getElementById('fs-onlynew').addEventListener('change', (ev) => { onlyNew = ev.target.checked; });
  // Сегментные кнопки-числа: шевроны / засечки / дуги.
  function bindFigNums(boxId, field) {
    document.querySelectorAll('#' + boxId + ' button').forEach((b) => b.addEventListener('click', () => {
      const v = parseInt(b.dataset.n, 10); recFigDefault(field, v); applyFigureSetting((e) => { e.data[field] = v; });
    }));
  }
  bindFigNums('fs-chevrons', 'chevrons');
  bindFigNums('fs-ticks', 'eqTicks');
  bindFigNums('fs-arcs', 'arcCount');
  document.getElementById('fs-length').addEventListener('change', (ev) => { recFigDefault('showLength', ev.target.checked); applyFigureSetting((e) => { e.data.showLength = ev.target.checked; }); });
  document.getElementById('fs-degree').addEventListener('change', (ev) => { recFigDefault('showDegree', ev.target.checked); applyFigureSetting((e) => { e.data.showDegree = ev.target.checked; }); });
  (function () { // прозрачность заливки угла: ползунок + число (0..100 → 0..1)
    const range = document.getElementById('fs-opacity-range'), num = document.getElementById('fs-opacity-num');
    let snap = null;
    const startSnap = () => { snap = figureTargets().map(clone); };
    const live = (v) => { v = Math.max(0, Math.min(100, parseInt(v, 10) || 0)); range.value = v; num.value = v; recFigDefault('fillOpacity', v / 100); liveFigureSetting((e) => { e.data.fillOpacity = v / 100; }); };
    const commit = () => { const before = snap; snap = null; if (onlyNew && fsMode === 'all') return; if (before) before.forEach((b) => { const el = elements.get(b.id); if (el) { histUpd(b, el); send({ action: 'element_update', element: el }); } }); else figureTargets().forEach((el) => send({ action: 'element_update', element: el })); };
    range.addEventListener('mousedown', startSnap); range.addEventListener('input', () => live(range.value)); range.addEventListener('change', commit);
    num.addEventListener('focus', startSnap); num.addEventListener('input', () => live(num.value)); num.addEventListener('change', commit);
  })();

  // ── Всплывающая панель линии/стрелки (у выделенного объекта) ──────────
  const connPanel = document.getElementById('conn-panel');
  // Применить правку к выделенному коннектору: перерисовать, записать в историю,
  // разослать, переставить ручки и обновить панель.
  function connApply(mutator, before) {
    const el = connSelectedEl(); if (!el) return;
    const b = before || clone(el);
    mutator(el);
    const node = nodes.get(el.id); if (node) node.draw();
    histUpd(b, el); send({ action: 'element_update', element: el });
    // Полный positionHandles: переставит ручки, скроет/покажет контроль (у уступа
    // его нет) и обновит/переставит панель через showConnPanel.
    positionHandles(); layer.batchDraw();
  }
  (function () { // свотчи цвета (те же 16 базовых)
    const box = document.getElementById('cn-colors');
    BASE_COLORS.forEach((c) => {
      const sw = document.createElement('div'); sw.className = 'cp-sw';
      sw.style.background = c; sw.dataset.color = c; sw.title = c;
      sw.addEventListener('click', () => connApply((e) => setElColor(e, c)));
      box.appendChild(sw);
    });
  })();
  (function () { // толщина: ползунок + число (живое + фиксация в историю)
    const range = document.getElementById('cn-width-range'), num = document.getElementById('cn-width-num');
    let snap = null;
    const start = () => { const el = connSelectedEl(); snap = el ? clone(el) : null; };
    const live = (v) => {
      v = Math.max(1, Math.min(24, parseInt(v, 10) || 1)); range.value = v; num.value = v;
      const el = connSelectedEl(); if (!el) return;
      el.data.strokeWidth = v; const node = nodes.get(el.id); if (node) node.draw(); layer.batchDraw();
    };
    const commit = () => { const before = snap; snap = null; const el = connSelectedEl(); if (el) { if (before) histUpd(before, el); send({ action: 'element_update', element: el }); } };
    range.addEventListener('mousedown', start); range.addEventListener('input', () => live(range.value)); range.addEventListener('change', commit);
    num.addEventListener('focus', start); num.addEventListener('input', () => live(num.value)); num.addEventListener('change', commit);
  })();
  // Иконки концов (SVG): линия + наконечник/точка справа; для начала — зеркально.
  function capIcon(cap, side) {
    if (!cap || cap === 'none') return '<span class="cn-none">Нет</span>';
    const L = '<line x1="2" y1="8" x2="17" y2="8"/>';
    let head;
    switch (cap) {
      case 'arrow': head = '<path d="M13 3 L22 8 L13 13 Z" fill="currentColor" stroke="none"/>'; break;
      case 'arrow_open': head = '<polyline points="14,3 22,8 14,13" fill="none"/>'; break;
      case 'triangle_open': head = '<path d="M13 3 L22 8 L13 13 Z" fill="none"/>'; break;
      case 'diamond': head = '<path d="M13 8 L18 3.5 L23 8 L18 12.5 Z" fill="currentColor" stroke="none"/>'; break;
      case 'diamond_open': head = '<path d="M13 8 L18 3.5 L23 8 L18 12.5 Z" fill="none"/>'; break;
      case 'bar': head = '<line x1="20" y1="2" x2="20" y2="14"/>'; break;
      case 'circle_open': head = '<circle cx="20" cy="8" r="3.4" fill="none"/>'; break;
      default: head = '<circle cx="20" cy="8" r="3.2" fill="currentColor" stroke="none"/>'; // dot
    }
    const inner = L + head;
    const g = side === 'start' ? '<g transform="scale(-1,1) translate(-28,0)">' + inner + '</g>' : inner;
    return '<svg viewBox="0 0 28 16" class="cn-capsvg">' + g + '</svg>';
  }
  const CAP_OPTS = ['none', 'arrow', 'arrow_open', 'diamond', 'bar', 'dot'];
  // Выпадашки выбора конца/начала — РИСУНКИ концов (не названия).
  ['start', 'end'].forEach((side) => {
    const box = document.createElement('div'); box.className = 'cn-caps';
    CAP_OPTS.forEach((cap) => {
      const btn = document.createElement('button'); btn.type = 'button'; btn.dataset.cap = cap; btn.innerHTML = capIcon(cap, side);
      btn.addEventListener('click', () => connApply((e) => { e.data[side === 'start' ? 'startCap' : 'endCap'] = cap; }));
      box.appendChild(btn);
    });
    document.getElementById('cn-' + side + '-pop').appendChild(box);
  });
  function connStraighten(d) { delete d.wl; delete d.wm; delete d.wr; delete d.c1; delete d.c2; delete d.ctrl; }
  // Форма — взаимоисключающие типы: «кривая» (сплайн) и «уступ» (ортогональный).
  document.querySelectorAll('#cn-shape button').forEach((b) => b.addEventListener('click', () => connApply((e) => {
    const shape = b.dataset.shape, d = e.data;
    if (shape === 'curve') {
      if (connIsCurved(d) && !d.elbow) { connStraighten(d); } // уже кривая → выпрямить
      else { connStraighten(d); d.elbow = false; d.wm = connDefaultCurve(d); }
    } else { // уступ
      if (d.elbow) { d.elbow = false; } else { connStraighten(d); d.elbow = true; }
    }
  })));
  document.getElementById('cn-straighten').addEventListener('click', () => connApply((e) => { connStraighten(e.data); e.data.elbow = false; }));

  // Выпадашки панели (цвет / тип / начало / конец) — открыта максимум одна.
  const CN_POPS = { color: 'cn-color-pop', type: 'cn-type-pop', start: 'cn-start-pop', end: 'cn-end-pop' };
  const CN_BTNS = { color: 'cn-color-btn', type: 'cn-type-btn', start: 'cn-start-btn', end: 'cn-end-btn' };
  function closeConnPops() { Object.values(CN_POPS).forEach((id) => document.getElementById(id).classList.add('ps-hidden')); Object.values(CN_BTNS).forEach((id) => document.getElementById(id).classList.remove('cn-open')); }
  function toggleConnPop(which) {
    const pop = document.getElementById(CN_POPS[which]), wasHidden = pop.classList.contains('ps-hidden');
    closeConnPops();
    if (wasHidden) { pop.classList.remove('ps-hidden'); document.getElementById(CN_BTNS[which]).classList.add('cn-open'); }
  }
  Object.keys(CN_BTNS).forEach((which) => document.getElementById(CN_BTNS[which]).addEventListener('click', (e) => { e.stopPropagation(); if (!connSelectedEl()) return; renderConnPanel(); toggleConnPop(which); }));
  document.addEventListener('click', (e) => { if (!connPanel.classList.contains('ps-hidden') && !connPanel.contains(e.target)) closeConnPops(); });

  function renderConnPanel() {
    const el = connSelectedEl(); if (!el) return;
    const d = el.data, isArrow = el.type === 'arrow';
    const w = d.strokeWidth || 2;
    document.getElementById('cn-width-range').value = w; document.getElementById('cn-width-num').value = w;
    const col = d.stroke || d.color || '#1f2937';
    document.getElementById('cn-color-dot').style.background = col;
    document.querySelectorAll('#cn-colors .cp-sw').forEach((sw) => sw.classList.toggle('cp-sel', sw.dataset.color.toLowerCase() === col.toLowerCase()));
    // Разделитель — только цвет+толщина: концы и «форму» прячем.
    const isDiv = !!d.divider;
    // Иконки концов на кнопках-бара + активная опция в выпадашках. У сужения/разделителя концов нет.
    const sc = d.startCap || 'none', ec = d.endCap || (isArrow ? 'arrow' : 'none');
    document.getElementById('cn-start-btn').style.display = (d.taper || isDiv) ? 'none' : '';
    document.getElementById('cn-end-btn').style.display = (d.taper || isDiv) ? 'none' : '';
    document.getElementById('cn-start-btn').innerHTML = capIcon(sc, 'start');
    document.getElementById('cn-end-btn').innerHTML = capIcon(ec, 'end');
    document.querySelectorAll('#cn-start-pop .cn-caps button').forEach((b) => b.classList.toggle('cn-on', b.dataset.cap === sc));
    document.querySelectorAll('#cn-end-pop .cn-caps button').forEach((b) => b.classList.toggle('cn-on', b.dataset.cap === ec));
    // Тип: «кривая» у всех; «уступ» только у стрелок; у разделителя формы нет.
    const isCurve = connIsCurved(d) && !d.elbow;
    document.querySelectorAll('#cn-shape button').forEach((b) => {
      const shape = b.dataset.shape;
      b.style.display = (!isDiv && (shape === 'curve' || isArrow)) ? '' : 'none';
      const on = shape === 'curve' ? isCurve : shape === 'elbow' ? !!d.elbow : !!d.taper;
      b.classList.toggle('cn-on', on);
    });
    document.getElementById('cn-shape').style.display = isDiv ? 'none' : '';
    document.getElementById('cn-straighten').style.display = (!isDiv && (isCurve || d.elbow)) ? '' : 'none';
  }
  function positionConnPanel(el) {
    el = el || connSelectedEl(); if (!el) return;
    const node = nodes.get(el.id); if (!node) return;
    const cr = node.getClientRect(); // в координатах контейнера stage (учёт масштаба/сдвига)
    const box = stage.container().getBoundingClientRect();
    const pw = connPanel.offsetWidth || 232, ph = connPanel.offsetHeight || 220;
    let left = box.left + cr.x + cr.width / 2 - pw / 2;
    let top = box.top + cr.y - ph - 14;
    if (top < 70) top = box.top + cr.y + cr.height + 14; // не влезает сверху — показываем снизу
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    top = Math.max(70, Math.min(top, window.innerHeight - ph - 8));
    connPanel.style.left = left + 'px'; connPanel.style.top = top + 'px';
  }
  function showConnPanel(el) { renderConnPanel(); connPanel.classList.remove('ps-hidden'); positionConnPanel(el); }
  function hideConnPanel() { if (!connPanel.classList.contains('ps-hidden')) { closeConnPops(); connPanel.classList.add('ps-hidden'); } }
  function repositionConnPanel() { if (!connPanel.classList.contains('ps-hidden')) { const el = connSelectedEl(); if (el) positionConnPanel(el); } }

  // ── Панель фигуры: граница (цвет/толщина) + заливка (цвет/прозрачность) ──
  const SHAPE_TYPES_PANEL = ['rect', 'ellipse', 'shape'];
  const shapePanel = document.getElementById('shape-panel');
  // ── Панель нарисованного штриха (карандаш и маркер) ────────────────────
  const strokePanel = document.getElementById('stroke-panel');
  const ST_POPS = { color: 'st-color-pop', width: 'st-width-pop' };
  const ST_BTNS = { color: 'st-color-btn', width: 'st-width-btn' };
  // Все выделенные штрихи. Если среди выделенного есть что-то ещё — панели нет:
  // иначе непонятно, к чему относится толщина.
  function strokeSelectedEls() {
    if (!selected.size || tool !== 'select') return [];
    const out = [];
    let ok = true;
    selected.forEach((id) => {
      const el = elements.get(id);
      if (!el || el.type !== 'freehand' || (el.data && (el.data.locked || el.data.hidden))) { ok = false; return; }
      out.push(el);
    });
    return ok ? out : [];
  }
  function strokeIsMarker(els) { return els.length > 0 && els.every((e) => e.data && e.data.marker); }
  function strokeApply(mutator) {
    const els = strokeSelectedEls(); if (!els.length) return;
    els.forEach((el) => {
      const before = clone(el);
      mutator(el);
      upsertNode(el); histUpd(before, el); send({ action: 'element_update', element: el });
    });
    layer.batchDraw(); renderStrokePanel();
  }
  function closeStrokePops() {
    Object.values(ST_POPS).forEach((id) => { const e = document.getElementById(id); if (e) e.classList.add('ps-hidden'); });
    Object.values(ST_BTNS).forEach((id) => { const e = document.getElementById(id); if (e) e.classList.remove('cn-open'); });
  }
  function toggleStrokePop(which) {
    const pop = document.getElementById(ST_POPS[which]); if (!pop) return;
    const wasHidden = pop.classList.contains('ps-hidden');
    closeStrokePops();
    if (wasHidden) { pop.classList.remove('ps-hidden'); document.getElementById(ST_BTNS[which]).classList.add('cn-open'); }
  }
  function renderStrokePanel() {
    const els = strokeSelectedEls(); if (!els.length) return;
    const d = els[0].data || {};
    const dot = document.getElementById('st-color-dot');
    if (dot) dot.style.background = d.stroke || d.color || '#1f2937';
    const w = d.strokeWidth == null ? 3 : d.strokeWidth;
    const range = document.getElementById('st-width-range'), num = document.getElementById('st-width-num');
    if (range) range.value = w; if (num) num.value = w;
    // Прозрачность — только у маркера: у карандаша её нет вовсе.
    const orow = document.getElementById('st-opacity-row');
    const marker = strokeIsMarker(els);
    if (orow) orow.style.display = marker ? '' : 'none';
    if (marker) {
      const o = Math.round((d.opacity == null ? 0.4 : d.opacity) * 100);
      const orange = document.getElementById('st-opacity-range'), onum = document.getElementById('st-opacity-num');
      if (orange) orange.value = o; if (onum) onum.value = o;
    }
    const box = document.getElementById('st-colors');
    if (box && !box.childElementCount) {
      BASE_COLORS.forEach((c) => {
        const sw = document.createElement('div'); sw.className = 'cp-sw'; sw.style.background = c; sw.title = c;
        sw.addEventListener('click', () => strokeApply((e) => { e.data.stroke = c; e.data.color = c; }));
        box.appendChild(sw);
      });
    }
  }
  function positionStrokePanel(el) {
    const node = nodes.get(el.id); if (!node) return;
    const cr = node.getClientRect(), box = stage.container().getBoundingClientRect();
    const pw = strokePanel.offsetWidth || 90, ph = strokePanel.offsetHeight || 48;
    let left = box.left + cr.x + cr.width / 2 - pw / 2, top = box.top + cr.y - ph - 14;
    if (top < 70) top = box.top + cr.y + cr.height + 14;
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    top = Math.max(70, Math.min(top, window.innerHeight - ph - 8));
    strokePanel.style.left = left + 'px'; strokePanel.style.top = top + 'px';
  }
  function showStrokePanel(el) { renderStrokePanel(); strokePanel.classList.remove('ps-hidden'); positionStrokePanel(el); }
  function hideStrokePanel() { if (strokePanel && !strokePanel.classList.contains('ps-hidden')) { closeStrokePops(); strokePanel.classList.add('ps-hidden'); } }
  Object.keys(ST_BTNS).forEach((which) => {
    const b = document.getElementById(ST_BTNS[which]);
    if (b) b.addEventListener('click', (e) => { e.stopPropagation(); if (!strokeSelectedEls().length) return; renderStrokePanel(); toggleStrokePop(which); });
  });
  document.addEventListener('click', (e) => {
    if (strokePanel && !strokePanel.classList.contains('ps-hidden') && !strokePanel.contains(e.target)) closeStrokePops();
  });
  (function wireStrokeSliders() {
    const pairs = [
      // step: 0.5 у толщины — иначе тонкий штрих 1.5 не выставить и не сохранить.
      { r: 'st-width-range', n: 'st-width-num', lo: 0.5, hi: 40, step: 0.5, set: (el, v) => { el.data.strokeWidth = v; } },
      { r: 'st-opacity-range', n: 'st-opacity-num', lo: 10, hi: 100, step: 1, set: (el, v) => { el.data.opacity = v / 100; } },
    ];
    pairs.forEach((p) => {
      const range = document.getElementById(p.r), num = document.getElementById(p.n);
      if (!range || !num) return;
      let snaps = null;
      // Снимок ДО начала перетаскивания: в историю пишем один шаг на всё
      // движение, а не по шагу на каждый пиксель ползунка.
      const start = () => { snaps = strokeSelectedEls().map((el) => clone(el)); };
      const live = (v) => {
        v = полшага(v, p.lo, p.hi, p.step);
        range.value = v; num.value = v;
        strokeSelectedEls().forEach((el) => { p.set(el, v); upsertNode(el); });
        layer.batchDraw();
      };
      const commit = () => {
        const before = snaps; snaps = null;
        const els = strokeSelectedEls();
        els.forEach((el, i) => {
          if (before && before[i]) histUpd(before[i], el);
          send({ action: 'element_update', element: el });
        });
      };
      range.addEventListener('mousedown', start); range.addEventListener('input', () => live(range.value)); range.addEventListener('change', commit);
      num.addEventListener('focus', start); num.addEventListener('input', () => live(num.value)); num.addEventListener('change', commit);
    });
  })();

  function shapeSelectedEl() { if (selected.size !== 1) return null; const el = elements.get(Array.from(selected)[0]); return (el && SHAPE_TYPES_PANEL.indexOf(el.type) >= 0) ? el : null; }
  function shapeApply(mutator) {
    const el = shapeSelectedEl(); if (!el) return;
    const before = clone(el); mutator(el);
    upsertNode(el); histUpd(before, el); send({ action: 'element_update', element: el });
    layer.batchDraw(); renderShapePanel();
  }
  (function buildShapeSwatches() {
    const bc = document.getElementById('sp-border-colors');
    BASE_COLORS.forEach((c) => { const sw = document.createElement('div'); sw.className = 'cp-sw'; sw.style.background = c; sw.dataset.color = c; sw.title = c; sw.addEventListener('click', () => shapeApply((e) => { e.data.stroke = c; e.data.color = c; })); bc.appendChild(sw); });
    const fc = document.getElementById('sp-fill-colors');
    const none = document.createElement('div'); none.className = 'cp-sw cp-nofill'; none.title = 'Без заливки'; none.addEventListener('click', () => shapeApply((e) => { e.data.fill = ''; })); fc.appendChild(none);
    BASE_COLORS.forEach((c) => { const sw = document.createElement('div'); sw.className = 'cp-sw'; sw.style.background = c; sw.dataset.color = c; sw.title = c; sw.addEventListener('click', () => shapeApply((e) => { e.data.fill = c; if (e.data.fillOpacity == null) e.data.fillOpacity = 0.2; })); fc.appendChild(sw); });
  })();
  (function () { // толщина границы: ползунок + число, живое + фиксация
    const range = document.getElementById('sp-border-range'), num = document.getElementById('sp-border-num'); let snap = null;
    const start = () => { const el = shapeSelectedEl(); snap = el ? clone(el) : null; };
    const live = (v) => { v = полшага(v, 0, 24); range.value = v; num.value = v; const el = shapeSelectedEl(); if (!el) return; el.data.strokeWidth = v; upsertNode(el); layer.batchDraw(); };
    const commit = () => { const before = snap; snap = null; const el = shapeSelectedEl(); if (el) { if (before) histUpd(before, el); send({ action: 'element_update', element: el }); } };
    range.addEventListener('mousedown', start); range.addEventListener('input', () => live(range.value)); range.addEventListener('change', commit);
    num.addEventListener('focus', start); num.addEventListener('input', () => live(num.value)); num.addEventListener('change', commit);
  })();
  (function () { // прозрачность заливки
    const range = document.getElementById('sp-fill-opacity'), val = document.getElementById('sp-fill-opacity-val'); let snap = null;
    const start = () => { const el = shapeSelectedEl(); snap = el ? clone(el) : null; };
    const live = (v) => {
      v = Math.max(0, Math.min(100, parseInt(v, 10) || 0)); range.value = v; val.textContent = v + '%';
      const el = shapeSelectedEl(); if (!el) return; el.data.fillOpacity = v / 100;
      if (el.data.fill === undefined || el.data.fill === '') el.data.fill = el.data.stroke || el.data.color || '#1f2937'; // прозрачности нужна заливка
      upsertNode(el); layer.batchDraw(); renderShapePanel();
    };
    const commit = () => { const before = snap; snap = null; const el = shapeSelectedEl(); if (el) { if (before) histUpd(before, el); send({ action: 'element_update', element: el }); } };
    range.addEventListener('mousedown', start); range.addEventListener('input', () => live(range.value)); range.addEventListener('change', commit);
  })();
  const SP_POPS = { border: 'sp-border-pop', fill: 'sp-fill-pop' }, SP_BTNS = { border: 'sp-border-btn', fill: 'sp-fill-btn' };
  function closeShapePops() { Object.values(SP_POPS).forEach((id) => document.getElementById(id).classList.add('ps-hidden')); Object.values(SP_BTNS).forEach((id) => document.getElementById(id).classList.remove('cn-open')); }
  function toggleShapePop(which) { const pop = document.getElementById(SP_POPS[which]), wasHidden = pop.classList.contains('ps-hidden'); closeShapePops(); if (wasHidden) { pop.classList.remove('ps-hidden'); document.getElementById(SP_BTNS[which]).classList.add('cn-open'); } }
  Object.keys(SP_BTNS).forEach((which) => document.getElementById(SP_BTNS[which]).addEventListener('click', (e) => { e.stopPropagation(); if (!shapeSelectedEl()) return; renderShapePanel(); toggleShapePop(which); }));
  document.addEventListener('click', (e) => { if (!shapePanel.classList.contains('ps-hidden') && !shapePanel.contains(e.target)) closeShapePops(); });
  // ── Панель стикера: цвет заметки и размер текста ──────────────────────
  // Устроена так же, как панель фигуры, и показывается из того же места.
  // Отличие одно: стикер — HTML-объект, а не фигура на холсте, поэтому
  // положение панели считаем по рамке его обёртки, а не по узлу Konva.
  const stickyPanel = document.getElementById('sticky-panel');
  function stickySelectedEl() {
    if (tool !== 'select' || selected.size !== 1) return null;
    const el = elements.get(Array.from(selected)[0]);
    if (!el || el.type !== 'sticky') return null;
    if (el.data && (el.data.locked || el.data.hidden)) return null;
    return el;
  }
  function closeStickyPops() {
    ['stp-color-pop', 'stp-size-pop'].forEach((id) => { const p = document.getElementById(id); if (p) p.classList.add('ps-hidden'); });
  }
  function renderStickyPanel() {
    const el = stickySelectedEl(); if (!el) return; const d = el.data;
    const col = d.color || STICKY_COLORS[0];
    const dot = document.getElementById('stp-color-dot'); if (dot) dot.style.background = col;
    document.querySelectorAll('#stp-colors .cp-sw').forEach((sw) => {
      sw.classList.toggle('cp-sel', (sw.dataset.color || '').toLowerCase() === String(col).toLowerCase());
    });
    const fs = d.fontSize || 14;
    const r = document.getElementById('stp-size-range'), n = document.getElementById('stp-size-num');
    if (r) r.value = fs; if (n) n.value = fs;
  }
  function positionStickyPanel(el) {
    el = el || stickySelectedEl(); if (!el || !stickyPanel) return;
    const it = widgetItems.get(el.id); if (!it || !it.wrapper) return;
    const cr = it.wrapper.getBoundingClientRect();
    const pw = stickyPanel.offsetWidth || 110, ph = stickyPanel.offsetHeight || 48;
    let left = cr.left + cr.width / 2 - pw / 2, top = cr.top - ph - 14;
    if (top < 70) top = cr.bottom + 14;
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    top = Math.max(70, Math.min(top, window.innerHeight - ph - 8));
    stickyPanel.style.left = left + 'px'; stickyPanel.style.top = top + 'px';
  }
  function showStickyPanel(el) { if (!stickyPanel) return; renderStickyPanel(); stickyPanel.classList.remove('ps-hidden'); positionStickyPanel(el); }
  function hideStickyPanel() { if (stickyPanel && !stickyPanel.classList.contains('ps-hidden')) { closeStickyPops(); stickyPanel.classList.add('ps-hidden'); } }
  function applyStickySetting(изменить) {
    const el = stickySelectedEl(); if (!el) return;
    const before = clone(el); изменить(el.data);
    const it = widgetItems.get(el.id); if (it && it.update) it.update();
    if (it) { it.wrapper.style.background = el.data.color || STICKY_COLORS[0]; }
    histUpd(before, el); send({ action: 'element_update', element: el });
    renderStickyPanel();
  }
  (function wireStickyPanel() {
    if (!stickyPanel) return;
    const grid = document.getElementById('stp-colors');
    if (grid) STICKY_COLORS.forEach((c) => {
      const sw = document.createElement('div');
      sw.className = 'cp-sw'; sw.style.background = c; sw.dataset.color = c; sw.title = c;
      sw.addEventListener('click', () => applyStickySetting((d) => { d.color = c; }));
      grid.appendChild(sw);
    });
    const пара = (id, поле) => {
      const el = document.getElementById(id); if (!el) return;
      el.addEventListener('input', () => applyStickySetting((d) => { d[поле] = parseInt(el.value, 10) || 14; }));
    };
    пара('stp-size-range', 'fontSize'); пара('stp-size-num', 'fontSize');
    const кнопка = (btn, pop) => {
      const b = document.getElementById(btn), p = document.getElementById(pop); if (!b || !p) return;
      b.addEventListener('click', (e) => { e.stopPropagation(); const было = p.classList.contains('ps-hidden'); closeStickyPops(); if (было) p.classList.remove('ps-hidden'); });
    };
    кнопка('stp-color-btn', 'stp-color-pop'); кнопка('stp-size-btn', 'stp-size-pop');
    document.addEventListener('click', (e) => { if (!stickyPanel.contains(e.target)) closeStickyPops(); });
  })();
  function renderShapePanel() {
    const el = shapeSelectedEl(); if (!el) return; const d = el.data;
    const bw = d.strokeWidth == null ? 2 : d.strokeWidth;
    document.getElementById('sp-border-range').value = bw; document.getElementById('sp-border-num').value = bw;
    const bcol = d.stroke || d.color || '#1f2937';
    document.querySelectorAll('#sp-border-colors .cp-sw').forEach((sw) => sw.classList.toggle('cp-sel', (sw.dataset.color || '').toLowerCase() === bcol.toLowerCase()));
    const legacyFill = (el.type === 'shape');
    const fillCol = (d.fill === undefined) ? (legacyFill ? bcol : '') : d.fill;
    document.getElementById('sp-fill-dot').style.background = fillCol ? fillCol : 'transparent';
    const op = d.fillOpacity == null ? 0.2 : d.fillOpacity;
    document.getElementById('sp-fill-opacity').value = Math.round(op * 100); document.getElementById('sp-fill-opacity-val').textContent = Math.round(op * 100) + '%';
    document.querySelectorAll('#sp-fill-colors .cp-sw').forEach((sw) => {
      if (sw.classList.contains('cp-nofill')) sw.classList.toggle('cp-sel', d.fill === '');
      else sw.classList.toggle('cp-sel', !!fillCol && (sw.dataset.color || '').toLowerCase() === String(fillCol).toLowerCase());
    });
  }
  function positionShapePanel(el) {
    el = el || shapeSelectedEl(); if (!el) return; const node = nodes.get(el.id); if (!node) return;
    const cr = node.getClientRect(), box = stage.container().getBoundingClientRect();
    const pw = shapePanel.offsetWidth || 110, ph = shapePanel.offsetHeight || 48;
    let left = box.left + cr.x + cr.width / 2 - pw / 2, top = box.top + cr.y - ph - 14;
    if (top < 70) top = box.top + cr.y + cr.height + 14;
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    top = Math.max(70, Math.min(top, window.innerHeight - ph - 8));
    shapePanel.style.left = left + 'px'; shapePanel.style.top = top + 'px';
  }
  function showShapePanel(el) { renderShapePanel(); shapePanel.classList.remove('ps-hidden'); positionShapePanel(el); }
  function hideShapePanel() { if (!shapePanel.classList.contains('ps-hidden')) { closeShapePops(); shapePanel.classList.add('ps-hidden'); } }
  document.getElementById('sp-text-btn').addEventListener('click', (e) => { e.stopPropagation(); const el = shapeSelectedEl(); if (el) startShapeTextEdit(el); });

  // ── ТЕКСТ ВНУТРИ ФИГУРЫ (rect/ellipse/shape) — богатый DOM-текст поверх фигуры ──
  // Оверлей .shape-text на #widget-layer, масштаб через transform (как tbox). Правка
  // переиспользует панель #tbox-bar (activeTbox-совместимый item). Ссылки — кликабельны.
  const shapeTextItems = new Map();
  function shapeTextDefaults() { return { html: '', font: TEXT_FONT, fontSize: 18, color: '#1f2937', align: 'center', boxBg: '' }; }
  // Текст внутри фигуры размечает ссылки тем же кодом, что и остальной текст
  // доски. Раньше здесь лежала вторая, отдельная копия того же алгоритма — и
  // расходилась с первой: тут ссылки были кликабельными, а в обычном тексте нет.
  function linkifyClickable(html) { return linkifyHtml(sanitizeHtml(html || '')); }

  function ensureShapeTextItem(el) {
    let it = shapeTextItems.get(el.id); if (it) return it;
    const wrapper = document.createElement('div'); wrapper.className = 'shape-text';
    const ed = document.createElement('div'); ed.className = 'shape-text-in'; ed.setAttribute('spellcheck', 'false');
    wrapper.appendChild(ed); widgetLayerEl.appendChild(wrapper);
    it = { wrapper, ed, shapeId: el.id, editing: false, _wired: false };
    shapeTextItems.set(el.id, it);
    return it;
  }
  function removeShapeText(id) { const it = shapeTextItems.get(id); if (it) { it.wrapper.remove(); shapeTextItems.delete(id); } }
  function repositionShapeText(id) {
    const it = shapeTextItems.get(id); if (!it) return;
    const node = nodes.get(id); if (!node) { it.wrapper.style.display = 'none'; return; }
    it.wrapper.style.display = '';
    const s = stage.scaleX(), b = node.getClientRect({ relativeTo: layer });
    it.wrapper.style.transform = 'translate(' + (b.x * s + stage.x()) + 'px,' + (b.y * s + stage.y()) + 'px) scale(' + s + ')';
    it.wrapper.style.width = Math.max(8, b.width) + 'px'; it.wrapper.style.height = Math.max(8, b.height) + 'px';
  }
  function syncShapeText(el) {
    const it0 = shapeTextItems.get(el.id);
    const editing = it0 && it0.editing;
    const has = el.data.tb && (el.data.tb.html || '').trim();
    if (!has && !editing) { removeShapeText(el.id); return; }
    const it = ensureShapeTextItem(el);
    if (!it.editing) { applyTboxStyle(it.ed, el.data.tb || shapeTextDefaults()); if (document.activeElement !== it.ed) it.ed.innerHTML = linkifyClickable((el.data.tb || {}).html || ''); }
    repositionShapeText(el.id);
  }
  function startShapeTextEdit(el) {
    if (viewOnly || (el.data && el.data.locked)) return;
    clearSelection(); // прячем ручки/панель фигуры — при правке текста виден только тулбар
    const it = ensureShapeTextItem(el);
    if (!el.data.tb) el.data.tb = shapeTextDefaults();
    it.editing = true; it.editBefore = clone(el); it._realEl = el;
    it.wrapper.classList.add('editing');
    it.ed.setAttribute('contenteditable', 'true');
    applyTboxStyle(it.ed, el.data.tb);
    it.ed.innerHTML = sanitizeHtml(el.data.tb.html || ''); // сырой html (без кликабельных <a>) — для правки
    repositionShapeText(el.id);
    it.ed.focus();
    const r = document.createRange(); r.selectNodeContents(it.ed); r.collapse(false); const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
    activeTbox = { ed: it.ed, el: { id: el.id, data: el.data.tb }, _realEl: el, wrapper: it.wrapper, isShapeText: true, editing: true };
    it._active = activeTbox;
    if (!it._wired) { wireShapeTextEditing(it); it._wired = true; }
    showTboxBar(activeTbox);
  }
  function wireShapeTextEditing(it) {
    it.ed.addEventListener('input', () => { const el = it._realEl; if (el && el.data.tb) { el.data.tb.html = it.ed.innerHTML; if (it._active) tboxSyncSoon(it._active); } });
    it.ed.addEventListener('blur', () => setTimeout(() => {
      if (!it.editing || document.activeElement === it.ed || (tboxBar && tboxBar.contains(document.activeElement))) return;
      endShapeTextEdit(it);
    }, 0));
    it.ed.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); it.ed.blur(); } });
  }
  function endShapeTextEdit(it) {
    if (!it.editing) return; const el = it._realEl; it.editing = false;
    it.wrapper.classList.remove('editing'); it.ed.setAttribute('contenteditable', 'false');
    if (el && el.data.tb) el.data.tb.html = it.ed.innerHTML;
    if (activeTbox === it._active) activeTbox = null;
    hideTboxBar();
    if (el) {
      if (!(it.ed.textContent || '').trim()) delete el.data.tb; // пусто — убираем текст
      send({ action: 'element_update', element: el });
      if (it.editBefore) histUpd(it.editBefore, el);
      syncShapeText(el);
    }
  }

  function hideAllSettings() { pointSettings.classList.add('ps-hidden'); figureSettings.classList.add('ps-hidden'); closeSettingsMenu(); }
  function openPointPanel(mode) { psMode = mode; closeSettingsMenu(); figureSettings.classList.add('ps-hidden'); renderPointSettings(); pointSettings.classList.remove('ps-hidden'); }
  function openFigurePanel(type, mode) { fsType = type; fsMode = mode; closeSettingsMenu(); pointSettings.classList.add('ps-hidden'); renderFigureSettings(); figureSettings.classList.remove('ps-hidden'); }
  function anySettingsOpen() { return !settingsMenu.classList.contains('sm-hidden') || !pointSettings.classList.contains('ps-hidden') || !figureSettings.classList.contains('ps-hidden'); }
  // Клик по шестерёнке: есть выделение → сразу панель его типа; иначе → меню
  // (где пункт меняет ВСЕ объекты этого типа на доске).
  settingsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (anySettingsOpen()) { hideAllSettings(); return; }
    if (selectedPoints().length) { openPointPanel('selection'); return; }
    if (selectedOfTypes(['segment']).length) { openFigurePanel('segment', 'selection'); return; }
    if (selectedOfTypes(['angle']).length) { openFigurePanel('angle', 'selection'); return; }
    if (selectedOfTypes(CONSTRUCT_LINES.filter((t) => t !== 'segment')).length) { openFigurePanel('line', 'selection'); return; }
    if (selectedOfTypes(['circ']).length) { openFigurePanel('circle', 'selection'); return; }
    if (selectedOfTypes(['polygon', 'regpoly']).length) { openFigurePanel('polygon', 'selection'); return; }
    openSettingsMenu();
  });
  settingsMenu.querySelectorAll('button[data-target]').forEach((b) => b.addEventListener('click', (e) => {
    e.stopPropagation();
    if (b.disabled) return;
    closeSettingsMenu();
    // Панель «все …» открываем даже при пустой доске — чтобы задать дефолты для
    // новых объектов (изменения запишутся в typeDefaults и применятся к будущим).
    const t = b.dataset.target;
    if (t === 'point') openPointPanel('all');
    else if (t === 'line') openFigurePanel('line', 'all');
    else if (t === 'segment') openFigurePanel('segment', 'all');
    else if (t === 'angle') openFigurePanel('angle', 'all');
    else if (t === 'circle') openFigurePanel('circle', 'all');
    else if (t === 'polygon') openFigurePanel('polygon', 'all');
  }));
  pointSettings.addEventListener('click', (e) => e.stopPropagation());
  figureSettings.addEventListener('click', (e) => e.stopPropagation());
  document.addEventListener('click', (e) => {
    const onBtn = e.target === settingsBtn || settingsBtn.contains(e.target);
    if (onBtn || settingsMenu.contains(e.target)) return;
    closeSettingsMenu(); pointSettings.classList.add('ps-hidden'); figureSettings.classList.add('ps-hidden');
  });

  // Кнопку «очистить всё» убрали с панели инструментов: она стояла вплотную к
  // рабочим, и промах стоил всей доски. Привязку оставляем на случай, если
  // действие вернут в меню — но теперь не падаем, когда кнопки нет.
  const clearBtn = document.querySelector('[data-action="clear"]');
  if (clearBtn) clearBtn.addEventListener('click', () => {
    uiConfirm('Очистить всю доску? Это удалит все элементы у всех участников.', { danger: true, ok: 'Очистить' }).then((ok) => {
      if (!ok) return;
      const ids = Array.from(elements.keys());
      ids.forEach((id) => { const el = elements.get(id); if (el) histDel(el); send({ action: 'element_delete', id }); removeNode(id); });
    });
  });
  const undoBtn = document.querySelector('[data-action="undo"]');
  const redoBtn = document.querySelector('[data-action="redo"]');
  if (undoBtn) undoBtn.addEventListener('click', doUndo);
  if (redoBtn) redoBtn.addEventListener('click', doRedo);

  // Плавная панорама холста стрелками (камера: стрелка вниз → едем вниз).
  // Зажатые клавиши копят скорость; движение идёт в rAF-цикле и плавно
  // разгоняется/тормозит. Shift — быстрее. Работает в любом инструменте.
  const PAN_KEYS = { ArrowUp: 1, ArrowDown: 1, ArrowLeft: 1, ArrowRight: 1 };
  const PAN_SPEED = 750;   // макс. скорость, px/сек
  const PAN_EASE = 0.2;    // плавность разгона/торможения (0..1 за кадр)
  const heldKeys = new Set();
  let shiftHeld = false;
  let spaceHeld = false, panBeforeSpace = false;  // пробел — временная панорама
  let lastVAt = 0;                                // двойное «v» подряд — включить/выключить перемещение
  let panVX = 0, panVY = 0, panRAF = null, lastPanT = 0;

  function panDirection() {
    let x = 0, y = 0;
    if (heldKeys.has('ArrowLeft'))  x += 1;
    if (heldKeys.has('ArrowRight')) x -= 1;
    if (heldKeys.has('ArrowUp'))    y += 1;
    if (heldKeys.has('ArrowDown'))  y -= 1;
    if (x && y) { x *= Math.SQRT1_2; y *= Math.SQRT1_2; } // ровная диагональ
    return { x, y };
  }

  function panLoop(t) {
    const dt = lastPanT ? Math.min(0.05, (t - lastPanT) / 1000) : 0;
    lastPanT = t;
    const dir = panDirection();
    const speed = PAN_SPEED * (shiftHeld ? 2 : 1);
    // Скорость плавно стремится к целевой (разгон при зажатии, торможение при отпускании).
    panVX += (dir.x * speed - panVX) * PAN_EASE;
    panVY += (dir.y * speed - panVY) * PAN_EASE;
    if (!dir.x && !dir.y && Math.abs(panVX) < 1 && Math.abs(panVY) < 1) {
      panVX = panVY = 0; panRAF = null; lastPanT = 0; return; // остановились
    }
    stage.position({ x: stage.x() + panVX * dt, y: stage.y() + panVY * dt });
    redrawGrid();
    repositionCursors();
    panRAF = requestAnimationFrame(panLoop);
  }
  function ensurePanLoop() {
    if (panRAF == null) { lastPanT = 0; panRAF = requestAnimationFrame(panLoop); }
  }

  // Буква клавиши НЕЗАВИСИМО от раскладки. e.key — это напечатанный символ: в
  // русской раскладке та же клавиша шлёт «м» вместо v, «я» вместо z. Поэтому
  // берём e.code («KeyV»), он привязан к физической клавише. Запасной путь по
  // e.key — на случай раскладок, где code не приходит.
  function keyLetter(e) {
    const c = e.code || '';
    if (c.length === 4 && c.indexOf('Key') === 0) return c.charAt(3).toLowerCase();
    const k = (e.key || '').toLowerCase();
    return k.length === 1 ? k : '';
  }

  // Горячие клавиши.
  window.addEventListener('keydown', (e) => {
    if (e.target && e.target.matches && e.target.matches('input, textarea, [contenteditable], [contenteditable] *')) return;
    shiftHeld = e.shiftKey;
    // Открытая справка забирает Esc себе — иначе он сначала выключал бы режимы.
    if (keysHelpEl && e.key === 'Escape') { e.preventDefault(); toggleKeysHelp(); return; }

    // «Только просмотр»: блокируем правки (удаление/дубль/группа/скрыть/undo/redo),
    // оставляем навигацию (стрелки-панораму, Esc).
    const _L = keyLetter(e);
    if (viewOnly && (e.key === 'Delete' || e.key === 'Backspace' || ((e.ctrlKey || e.metaKey) && 'dgzy'.indexOf(_L) >= 0) || _L === 'h')) { e.preventDefault(); return; }

    // Многоугольник: Enter — замкнуть, Esc — отменить незавершённый.
    if (tool === 'polygon' && polyPicks.length) {
      if (e.key === 'Enter') { e.preventDefault(); finishPolygon(); return; }
      if (e.key === 'Escape') { e.preventDefault(); clearPolyPicks(); return; }
    }
    // Середина/центр масс: Enter — построить, Esc — отменить.
    if (tool === 'midpoint' && midPicks.length) {
      if (e.key === 'Enter') { e.preventDefault(); finishMidpoint(); return; }
      if (e.key === 'Escape') { e.preventDefault(); midPicks = []; boardHint('Отменено'); return; }
    }
    // Система неравенств: Enter — закрасить набранные условия, Esc — отменить.
    if (tool === 'regionsys' && regionParts.length) {
      if (e.key === 'Enter') { e.preventDefault(); finishRegionSys(); return; }
      if (e.key === 'Escape') { e.preventDefault(); regionParts = []; regionFrame = null; boardHint('Отменено'); return; }
    }
    // Преобразование: Esc — отменить выбор источников/параметров.
    if (XFORM_SPEC[tool] && e.key === 'Escape') { e.preventDefault(); cancelXform(); boardHint('Отменено'); return; }

    // Запись макроса: Enter — дальше/сохранить, Esc — отменить.
    if (tool === 'macro_record') {
      if (e.key === 'Enter') { e.preventDefault(); macroRecordEnter(); return; }
      if (e.key === 'Escape') { e.preventDefault(); cancelMacro(); setTool('select'); boardHint('Отменено'); return; }
    }
    if (tool === 'macro' && e.key === 'Escape') { e.preventDefault(); cancelMacro(); setTool('select'); return; }

    if ((e.key === 'Delete' || e.key === 'Backspace') && selected.size) {
      e.preventDefault();
      deleteSelected();
      return;
    }

    // H — скрыть выделенное; Shift+H — показать/спрятать все скрытые (режим просмотра).
    if (_L === 'h') {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      e.preventDefault();
      if (e.shiftKey) toggleRevealHidden();
      else if (selected.size) { const ids = Array.from(selected); const allHidden = ids.every((id) => { const el = elements.get(id); return el && el.data.hidden; }); setHidden(ids, !allHidden); }
      return;
    }

    // Ctrl/Cmd+A — выделить всё на доске.
    if (_L === 'a' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); selectAllElements(); return;
    }

    // Масштаб с клавиатуры: Ctrl+0 — вернуть 100%, Ctrl+«+»/«−» — крупнее/мельче.
    if ((e.ctrlKey || e.metaKey) && (e.key === '0' || e.key === '=' || e.key === '+' || e.key === '-' || e.key === '_')) {
      e.preventDefault();
      if (e.key === '0') zoomTo(1);
      else zoomTo(stage.scaleX() * ((e.key === '-' || e.key === '_') ? 0.8 : 1.25));
      return;
    }

    // Esc — общий отбой: сначала выйти из режима скрытия, потом вернуться к
    // стрелке, потом снять выделение. Незавершённые построения перехвачены выше.
    if (e.key === 'Escape') {
      e.preventDefault();
      if (revealHidden) { toggleRevealHidden(); return; }
      if (tool !== 'select') { setTool('select'); return; }
      if (selected.size) { clearSelection(); layer.batchDraw(); }
      return;
    }

    // «?» — показать список горячих клавиш. Их некуда было подсмотреть.
    if (e.key === '?' || (e.key === '/' && e.shiftKey)) { e.preventDefault(); toggleKeysHelp(); return; }

    // Пробел — панорама, пока держишь. Так устроены графические редакторы, и
    // это единственный способ подвинуть доску, не бросая инструмент из рук.
    if (e.code === 'Space' && !spaceHeld) {
      e.preventDefault(); spaceHeld = true; panBeforeSpace = panMode; setPanMode(true); return;
    }

    // Ctrl/Cmd+G — сгруппировать выделенное, +Shift — разгруппировать.
    if (_L === 'g' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (e.shiftKey) ungroupSelected(); else groupSelected();
      return;
    }

    // Ctrl/Cmd+C — скопировать выделенное, Ctrl/Cmd+X — вырезать.
    // Вставку не перехватываем: её ловит событие paste, иначе до содержимого
    // системного буфера не добраться.
    if (_L === 'c' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
      if (selected.size) { e.preventDefault(); copySelected(false); }
      return;
    }
    if (_L === 'x' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
      if (selected.size) { e.preventDefault(); copySelected(true); }
      return;
    }

    // Ctrl/Cmd+D — дублировать выделенное.
    if (_L === 'd' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); if (selected.size) duplicateSelected(); return;
    }

    // Ctrl/Cmd+Z — шаг назад, +Shift или Ctrl+Y — шаг вперёд.
    if (_L === 'z' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (e.shiftKey) doRedo(); else doUndo();
      return;
    }
    if (_L === 'y' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); doRedo(); return;
    }

    if (PAN_KEYS[e.key]) {
      e.preventDefault();
      heldKeys.add(e.key);
      ensurePanLoop();
      return;
    }

    // Буквы инструментов — только без модификаторов. Раньше проверки не было, и
    // Ctrl+P (печать) заодно переключал на карандаш, а Ctrl+A — на стрелку.
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    // M — режим перемещения доски. Это не инструмент: у него нет data-tool, и
    // через карту ниже его не повесить. Маркер поэтому переехал на K.
    if (_L === 'm') { e.preventDefault(); setPanMode(!panMode); return; }
    const map = {
      v: 'select',  p: 'pen',     k: 'marker',  e: 'eraser_full', q: 'laser',
      l: 'line',    a: 'arrow',   r: 'rect',    o: 'ellipse',     s: 'sticky',
      t: 'text_plain', f: 'latex', g: 'graph',  c: 'circ_cp',     d: 'point',
      w: 'frame',   b: 'table',
    };
    const k = _L;
    // Двойное «v» подряд — переключить перемещение доски (кроме английской
    // раскладки и клавиши M это ещё один способ, привычный по «v = стрелка»).
    if (k === 'v') {
      const now = Date.now();
      if (now - lastVAt < 400) { lastVAt = 0; e.preventDefault(); setPanMode(!panMode); return; }
      lastVAt = now;
    }
    if (map[k]) { e.preventDefault(); setTool(map[k]); }
  });
  window.addEventListener('keyup', (e) => {
    shiftHeld = e.shiftKey;
    if (PAN_KEYS[e.key]) { heldKeys.delete(e.key); ensurePanLoop(); }
    if (e.code === 'Space' && spaceHeld) { spaceHeld = false; setPanMode(panBeforeSpace); }
  });
  // Если окно потеряло фокус с зажатой клавишей — плавно останавливаемся.
  window.addEventListener('blur', () => { heldKeys.clear(); ensurePanLoop(); });

  // ── Справка по горячим клавишам ────────────────────────────────────────
  // Инструментов на панели почти восемьдесят; без списка о клавишах просто
  // неоткуда узнать. Собираем окно из JS, чтобы не плодить разметку.
  const KEYS_HELP = [
    ['Инструменты', [
      ['V', 'стрелка (выделение)'], ['P', 'карандаш'], ['K', 'маркер'],
      ['E', 'ластик'], ['Q', 'указка'], ['L', 'линия'], ['A', 'стрелка-объект'],
      ['R', 'прямоугольник'], ['O', 'овал'], ['C', 'окружность'], ['D', 'точка'],
      ['T', 'текст'], ['F', 'формула'], ['G', 'график'], ['S', 'стикер'],
      ['W', 'окно построения'], ['B', 'таблица'],
    ]],
    ['Правка', [
      ['Ctrl+Z', 'шаг назад'], ['Ctrl+Shift+Z', 'шаг вперёд'],
      ['Ctrl+C', 'копировать'], ['Ctrl+X', 'вырезать'],
      ['Ctrl+V', 'вставить: картинку, файл, текст или скопированные объекты'],
      ['Ctrl+D', 'дублировать'], ['Ctrl+G', 'сгруппировать'],
      ['Ctrl+Shift+G', 'разгруппировать'], ['Ctrl+A', 'выделить всё'],
      ['Del', 'удалить выделенное'],
    ]],
    ['Скрытие', [
      ['H', 'скрыть выделенное'],
      ['Shift+H', 'режим скрытия: щелчком прячем и возвращаем'],
    ]],
    ['Вид', [
      ['Пробел', 'держать — двигать доску'],
      ['M', 'режим перемещения доски (нажать ещё раз — выйти)'],
      ['Правая кнопка', 'тянуть — двигать доску при любом инструменте'],
      ['Стрелки', 'двигать доску'],
      ['Shift+стрелки', 'быстрее'], ['Ctrl+0', 'масштаб 100%'],
      ['Ctrl+«+» / Ctrl+«−»', 'крупнее / мельче'],
    ]],
    ['Прочее', [
      ['Esc', 'выйти из режима, вернуться к стрелке, снять выделение'],
      ['Правая кнопка', 'нажать и отпустить на месте — меню: по объекту действия с ним, по пустому месту меню доски'],
      ['?', 'этот список'],
    ]],
  ];
  let keysHelpEl = null;
  function toggleKeysHelp() {
    if (keysHelpEl) { keysHelpEl.remove(); keysHelpEl = null; return; }
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:fixed;inset:0;z-index:4000;background:rgba(20,20,28,.45);'
      + 'display:flex;align-items:center;justify-content:center;padding:24px;';
    let html = '<div style="background:#fff;border-radius:12px;max-width:760px;width:100%;'
      + 'max-height:86vh;overflow:auto;padding:22px 26px;box-shadow:0 10px 40px rgba(0,0,0,.28)">'
      + '<div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:14px">'
      + '<h2 style="margin:0;font-size:19px">Горячие клавиши</h2>'
      + '<button data-close style="border:1px solid #d9d9e0;background:#f0f0f4;border-radius:6px;'
      + 'padding:3px 10px;cursor:pointer;font-size:13px">Закрыть</button></div>';
    KEYS_HELP.forEach((grp) => {
      html += '<div style="margin:14px 0 6px;font-weight:600;font-size:13px;color:#6b6b76;'
        + 'text-transform:uppercase;letter-spacing:.04em">' + grp[0] + '</div>'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:4px 18px">';
      grp[1].forEach((row) => {
        html += '<div style="display:flex;gap:10px;align-items:baseline;font-size:14px">'
          + '<kbd style="flex:0 0 auto;min-width:96px;font:600 12px/1.6 ui-monospace,Consolas,monospace;'
          + 'background:#f2f2f6;border:1px solid #dededf;border-bottom-width:2px;border-radius:5px;'
          + 'padding:1px 7px;text-align:center;color:#33333b">' + row[0] + '</kbd>'
          + '<span style="color:#3a3a42">' + row[1] + '</span></div>';
      });
      html += '</div>';
    });
    html += '</div>';
    wrap.innerHTML = html;
    wrap.addEventListener('click', (ev) => {
      if (ev.target === wrap || (ev.target.closest && ev.target.closest('[data-close]'))) toggleKeysHelp();
    });
    document.body.appendChild(wrap);
    keysHelpEl = wrap;
  }

  // Копировать ссылку на доску.
  (function wireCopyCode() {
    const btn = document.getElementById('copy-code');
    if (!btn) return;
    const flash = (text) => {
      const prev = btn.textContent;
      btn.textContent = text;
      setTimeout(() => { btn.textContent = prev; }, 1500);
    };
    btn.addEventListener('click', () => {
      const link = location.href;
      const ok = () => flash('готово');
      // Запасной путь: браузер может не дать доступ к буферу (нет фокуса,
      // не https, старая версия). Тогда показываем ссылку выделенной, чтобы
      // её можно было скопировать руками, — молча отказывать нельзя.
      const fallback = () => {
        boardHint('Не удалось скопировать — ссылка показана, скопируйте вручную');
        uiPrompt('Ссылка на доску (Ctrl+C):', link, { readonly: true });
        flash('вручную');
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(link).then(ok).catch(fallback);
      } else {
        fallback();
      }
    });
  })();

  // ── Импорт (кнопка + скрытый file input) и панель управления PDF ────────
  (function () {
    const inp = document.getElementById('import-input'), btn = document.getElementById('import-btn');
    if (btn && inp) {
      btn.addEventListener('click', () => inp.click());
      inp.addEventListener('change', () => { if (inp.files && inp.files.length) importFiles(inp.files); inp.value = ''; });
    }
    const on = (id, fn) => { const b = document.getElementById(id); if (b) b.addEventListener('click', fn); };
    on('reveal-hidden', toggleRevealHidden);
    on('people-btn', () => togglePeoplePanel());
    on('people-close', () => togglePeoplePanel(false));
    on('lead-all-btn', () => setLeadAll(!leadAll));
    on('unfollow-btn', () => setFollowUid(null));
    on('board-menu-btn', () => toggleBoardMenu());
    const bgSeg = document.getElementById('bg-seg');
    if (bgSeg) bgSeg.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) setBoardBg(b.dataset.bg); });
    const bgCustom = document.getElementById('bg-color-custom');
    if (bgCustom) bgCustom.addEventListener('input', () => setBoardBgColor(bgCustom.value));
    const bgGridCustom = document.getElementById('bg-grid-color-custom');
    if (bgGridCustom) bgGridCustom.addEventListener('input', () => setBoardGridColor(bgGridCustom.value));
    // «По умолчанию» у всех плашек цвета (доска и матокно): один слушатель.
    document.querySelectorAll('.bmc-reset[data-cr]').forEach((b) => b.addEventListener('click', () => {
      const t = b.dataset.cr;
      if (t === 'bg') setBoardBgColor('');
      else if (t === 'grid') setBoardGridColor('');
      else if (t === 'fegrid') setFrameGridColor('');
    }));
    const curTgl = document.getElementById('cursors-toggle');
    if (curTgl) curTgl.addEventListener('change', () => setPeerCursors(curTgl.checked));
    const gdTgl = document.getElementById('guides-toggle');
    if (gdTgl) gdTgl.addEventListener('change', () => { guidesEnabled = gdTgl.checked; boardHint(guidesEnabled ? 'Направляющие включены' : 'Направляющие выключены'); });
    on('history-btn', () => { hideBoardMenu(); toggleHistoryPanel(true); });
    on('history-close', () => toggleHistoryPanel(false));
    on('clear-board-btn', () => { hideBoardMenu(); clearBoard(); });
    on('export-pdf-btn', () => { hideBoardMenu(); const d = document.getElementById('pdf-export-dialog'); if (d) d.hidden = false; });
    const pdfDlg = document.getElementById('pdf-export-dialog');
    if (pdfDlg) pdfDlg.addEventListener('click', (e) => {
      if (e.target === pdfDlg || e.target.closest('#pdf-x-cancel')) { pdfDlg.hidden = true; return; }
      const b = e.target.closest('.pdf-mode'); if (b) { pdfDlg.hidden = true; exportBoardPdf(b.dataset.mode); }
    });

    const erSize = document.getElementById('eraser-size');
    if (erSize) erSize.addEventListener('input', () => { eraserRadius = +erSize.value; const v = document.getElementById('eraser-size-val'); if (v) v.textContent = eraserRadius; });
    // Роль по ссылке (владелец): переключение сегмента.
    const apDefault = document.getElementById('ap-default');
    if (apDefault) apDefault.addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; boardDefaultRole = b.dataset.role; renderPeoplePanel(); send({ action: 'set_role', target: null, role: b.dataset.role }); });
    // Список участников: следовать, вести, роль, убрать.
    const apPeople = document.getElementById('pp-people');
    if (apPeople) apPeople.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      // Значки «следовать» и «вести» — переключатели: нажал ещё раз, выключил.
      if (b.dataset.follow) { const u = b.dataset.follow; setFollowUid(String(followUid) === u ? null : u); return; }
      if (b.dataset.lead) { const u = b.dataset.lead; setLead(u, !(leadAll || leadUids.has(u))); return; }
      // «Убрать»: спрашиваем подтверждение — действие видно всем и рвёт связь участнику.
      if (b.dataset.kick) {
        const строка = b.closest('.pp-row');   // имя лежит в верхней подстроке
        const name = ((строка && строка.querySelector('.pp-name')) || {}).textContent || 'участника';
        uiConfirm('Убрать ' + name + ' с доски?\n\nОн выйдет сейчас же и не сможет войти по ссылке, пока вы не вернёте доступ.', { danger: true, ok: 'Убрать' })
          .then((ok) => { if (ok) send({ action: 'member_remove', target: b.dataset.kick }); });
        return;
      }
      const seg = b.closest('.ap-seg'); if (!seg) return;
      const uid = seg.getAttribute('data-uid'), role = b.dataset.r;
      boardRoles[uid] = role; renderPeoplePanel(); send({ action: 'set_role', target: uid, role: role });
    });
    const apRemoved = document.getElementById('ap-removed');
    if (apRemoved) apRemoved.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b || !b.dataset.back) return;
      send({ action: 'member_restore', target: b.dataset.back });
    });
    on('pdf-prev', () => { const el = selectedPdf(); if (el) setPdfPage(el, (el.data.page || 1) - 1); });
    on('pdf-next', () => { const el = selectedPdf(); if (el) setPdfPage(el, (el.data.page || 1) + 1); });
    on('pdf-extract', () => { const el = selectedPdf(); if (el) extractPdfPage(el, el.data.page || 1); });
    on('pdf-extract-all', () => { const el = selectedPdf(); if (el) { const n = el.data.pages || 1; extractPdfPages(el, Array.from({ length: n }, (_, i) => i + 1), []); } });
    const pdfRangeInput = document.getElementById('pdf-page-range');
    function pdfExtractFromRange() {
      const el = selectedPdf(); if (!el || !pdfRangeInput) return;
      const parsed = parsePageRange(pdfRangeInput.value, el.data.pages || 1);
      if (!parsed.pages.length) { boardHint(parsed.bad.length ? 'Не понял список страниц: ' + parsed.bad.join(', ') : 'Укажите страницы, например 1-5, 8'); return; }
      extractPdfPages(el, parsed.pages, parsed.bad);
    }
    on('pdf-extract-range', pdfExtractFromRange);
    if (pdfRangeInput) {
      pdfRangeInput.addEventListener('focus', () => pdfRangeInput.select());
      pdfRangeInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); pdfExtractFromRange(); } });
    }
    // Клик по кнопке этой панели не должен оставлять на ней фокус: иначе
    // следующий Backspace/Delete прилетает доске и удаляет выделенный PDF, а
    // Пробел бьёт по той же кнопке ещё раз. Приём не новый — ровно так уже
    // защищены панели текста (строки ~10175, ~3743 этого же файла).
    document.querySelectorAll('#pdf-controls button').forEach((b) => b.addEventListener('mousedown', (e) => e.preventDefault()));
    // Мои инструменты (макросы).
    function closeMacroFly() { const f = document.querySelector('[data-flyout="macros"]'); if (f) f.classList.remove('open'); }
    on('macro-create', () => { closeMacroFly(); startMacroRecord(); });
    const mlist = document.getElementById('macro-list');
    if (mlist) mlist.addEventListener('click', (e) => {
      const del = e.target.closest('.macro-del');
      if (del) { e.stopPropagation(); const i = +del.dataset.macro; const list = loadMacros(); list.splice(i, 1); saveMacros(list); renderMacroTools(); return; }
      const t = e.target.closest('.macro-tool');
      if (t) { const list = loadMacros(); const m = list[+t.dataset.macro]; if (m) { closeMacroFly(); startMacroApply(m); } }
    });
    renderMacroTools();
  })();


  // ── Доступность с клавиатуры ──────────────────────────────────────────
  // Панель и палитры собраны из <div>. Для клавиатуры и программы чтения с
  // экрана такой элемент — пустое место. Переписывать 161 штуку в <button>
  // рискованно: на них висит перетаскивание на холст, сохраняемый порядок
  // панели и правила стилей. Поэтому объявляем их кнопками ПО РОЛИ.
  const A11Y_SEL = '#board-toolbar .tool, .cp-sw';
  function панельныеКнопки() {
    const bar = document.getElementById('board-toolbar'); if (!bar) return [];
    // offsetParent === null значит «скрыт»: свёрнутая всплывашка сюда не идёт.
    return Array.from(bar.querySelectorAll('.tool')).filter((el) => el.offsetParent !== null);
  }
  // Один вход в панель на всю табуляцию — активный инструмент. Если раздать
  // tabindex=0 всем 89 кнопкам, до холста пришлось бы жать Tab сто раз.
  function обновитьВходВПанель() {
    const bar = document.getElementById('board-toolbar'); if (!bar) return;
    const видимые = панельныеКнопки(); if (!видимые.length) return;
    const активный = bar.querySelector('.tool[data-tool].active');
    const цель = (активный && видимые.indexOf(активный) >= 0) ? активный : видимые[0];
    видимые.forEach((el) => el.setAttribute('tabindex', el === цель ? '0' : '-1'));
  }
  function оснаститьДоступность() {
    document.querySelectorAll(A11Y_SEL).forEach((el) => {
      if (el.tagName === 'BUTTON') return;          // настоящей кнопке это ни к чему
      if (!el.hasAttribute('role')) el.setAttribute('role', 'button');
      // Подпись. title есть у всех, но диктор его читать не обязан, а на
      // планшете подсказка не показывается вовсе.
      const t = el.getAttribute('title');
      if (t && !el.hasAttribute('aria-label')) el.setAttribute('aria-label', t);
      if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
    });
    обновитьВходВПанель();
  }
  // Образцы цвета и часть кнопок создаются на ходу, когда открывают панель.
  // Следим за теми узлами, где они появляются, — их немного и меняются они редко.
  (function следитьЗаНовыми() {
    if (typeof MutationObserver !== 'function') return;
    const н = new MutationObserver((записи) => {
      if (записи.some((з) => з.addedNodes && з.addedNodes.length)) оснаститьДоступность();
    });
    ['board-toolbar', 'color-palette', 'board-menu', 'dp-pop', 'figure-settings',
     'point-settings', 'stroke-panel', 'shape-panel', 'sticky-panel'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) н.observe(el, { childList: true, subtree: true });
    });
  })();
  оснаститьДоступность();
  // Панель прячется на узком экране, и тогда точку входа ставить не на что.
  // Повернули планшет в альбом — панель вернулась, вход надо пересчитать.
  window.addEventListener('resize', () => { if (typeof обновитьВходВПанель === 'function') обновитьВходВПанель(); });

  // Клавиши для «кнопок по роли». Ловим на СПУСКЕ (capture), чтобы опередить
  // общий разбор горячих клавиш, и глушим событие только когда действительно
  // обработали — иначе отняли бы Enter у построений.
  document.addEventListener('keydown', (e) => {
    const el = e.target;
    if (!el || !el.matches || el.tagName === 'BUTTON') return;
    if ((e.key === 'Enter' || e.key === ' ') && el.matches('[role="button"]')) {
      e.preventDefault(); e.stopPropagation(); el.click(); return;
    }
    if (!el.closest || !el.closest('#board-toolbar')) return;
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const список = панельныеКнопки();
    const i = список.indexOf(el); if (i < 0) return;
    const шаг = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1 : -1;
    const цель = список[(i + шаг + список.length) % список.length];
    if (цель) { e.preventDefault(); e.stopPropagation(); цель.focus(); }
  }, true);

  // ── Чужие курсоры ─────────────────────────────────────────────────────
  const cursors = new Map(); // userId → { el, x, y, color }
  let showPeerCursors = true; // тумблер «Курсоры участников» в меню доски
  const PALETTE = ['#e7505a', '#27ae60', '#8e44ad', '#e67e22', '#16a2b8', '#d63384'];
  function colorForUser(uid) {
    const n = Math.abs(String(uid).split('').reduce((a, c) => a + c.charCodeAt(0), 0));
    return PALETTE[n % PALETTE.length];
  }

  function showRemoteCursor(uid, label, wx, wy) {
    if (uid === myId || !showPeerCursors) return;
    let c = cursors.get(uid);
    if (!c) {
      const el = document.createElement('div');
      el.className = 'remote-cursor';
      const color = colorForUser(uid);
      el.innerHTML = '<span class="arrow"><svg width="16" height="16" viewBox="0 0 24 24" fill="'
        + color + '"><path d="M4 2l6.5 17 2.4-7 7-2.4z"/></svg></span>'
        + '<span class="name" style="background:' + color + '">' + escapeHtml(label || '?') + '</span>';
      cursorLayerEl.appendChild(el);
      c = { el, x: wx, y: wy };
      cursors.set(uid, c);
    }
    c.x = wx; c.y = wy;
    placeCursor(c, true);   // сосед двинул курсор — пусть скользит
  }

  // плавно = true — сосед действительно передвинул курсор, метке положено
  // скользить. плавно = false — сдвинулся ВИД доски, и метка обязана ехать
  // вместе с холстом мгновенно: холст перерисовывается сразу, а метка с
  // анимацией отставала бы на кадр и дёргалась, хотя сосед стоит на месте.
  function placeCursor(c, плавно) {
    // world → экран: умножаем на масштаб и прибавляем смещение сцены.
    const sx = c.x * stage.scaleX() + stage.x();
    const sy = c.y * stage.scaleY() + stage.y();
    if (!плавно) c.el.style.transition = 'none';
    c.el.style.left = sx + 'px';
    c.el.style.top = sy + 'px';
    if (!плавно) {
      // Заставляем браузер применить координаты ПРЯМО СЕЙЧАС, пока анимация
      // выключена. Без этого оба изменения стиля применились бы разом, уже
      // после возврата плавности, и метка всё равно поехала бы с анимацией.
      void c.el.offsetHeight;
      c.el.style.transition = '';
    }
  }
  function repositionCursors() { cursors.forEach((c) => placeCursor(c)); repositionGGB(); repositionWidgets(); if (activeFrameId) updateFuncEditor(); updatePdfControls(); sendView(); }

  // ── Лазер: гаснущий след (эфемерный, синхронизируется) ─────────────────
  // Рисуешь лазером — остаётся яркая линия, которая тает по возрасту точек
  // (хвост исчезает первым), полностью пропадая через LASER_TTL. Не сохраняется
  // на доске; точки рассылаются участникам, как курсор.
  const LASER_TTL = 1400; // мс жизни точки следа
  const laserTrails = new Map(); // uid → [{x,y,t,brk}]
  let laserDrawing = false, laserRAF = null, lastLaserSentAt = 0;
  const laserLayer = new Konva.Layer({ listening: false });
  stage.add(laserLayer);
  const laserShape = new Konva.Shape({ listening: false, sceneFunc: drawLasers });
  laserLayer.add(laserShape);
  function laserNow() { return Date.now(); }
  function addLaserPoint(uid, x, y, brk) {
    let pts = laserTrails.get(uid); if (!pts) { pts = []; laserTrails.set(uid, pts); }
    pts.push({ x: x, y: y, t: laserNow(), brk: !!brk });
    if (pts.length > 600) pts.shift();
    ensureLaserLoop();
  }
  function drawLasers(ctx) {
    const now = laserNow(), s = stage.scaleX();
    laserTrails.forEach((pts, uid) => {
      const col = colorForUser(uid);
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      for (let i = 1; i < pts.length; i++) {
        const p0 = pts[i - 1], p1 = pts[i];
        if (p1.brk) continue; // разрыв между отдельными штрихами
        const age = now - p1.t; if (age >= LASER_TTL) continue;
        const a = 1 - age / LASER_TTL;
        ctx.beginPath();
        ctx.strokeStyle = hexToRgba(col, Math.max(0, a));
        ctx.lineWidth = (1 + 4 * a) / s; // хвост тоньше, голова толще
        ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y);
        ctx.stroke();
      }
    });
  }
  function laserTick() {
    const now = laserNow(); let any = false;
    laserTrails.forEach((pts, uid) => {
      while (pts.length && (now - pts[0].t) >= LASER_TTL) pts.shift();
      if (pts.length) any = true; else laserTrails.delete(uid);
    });
    laserLayer.batchDraw();
    if (any || laserDrawing) laserRAF = requestAnimationFrame(laserTick);
    else { laserRAF = null; }
  }
  function ensureLaserLoop() { if (!laserRAF) laserRAF = requestAnimationFrame(laserTick); }
  function sendLaser(x, y, brk) {
    const now = laserNow(); if (!brk && now - lastLaserSentAt < 33) return; lastLaserSentAt = now;
    send({ action: 'laser', x: x, y: y, s: brk ? 1 : 0 });
  }
  function laserDown() { const p = worldPoint(); if (!p) return; laserDrawing = true; addLaserPoint(myId, p.x, p.y, true); sendLaser(p.x, p.y, true); }
  function laserMove() { if (!laserDrawing) return; const p = worldPoint(); if (!p) return; addLaserPoint(myId, p.x, p.y, false); sendLaser(p.x, p.y, false); }
  function laserUp() { laserDrawing = false; }

  // ── Живое занятие: режим ведущего, только-просмотр ─────────────────────
  // За кем слежу я (id участника или null), кого веду я, и кто сам объявил,
  // что следит за мной. Последнее нужно, чтобы понимать, стоит ли вообще
  // рассылать свой вид: если за мной никто не смотрит, в сеть не уходит ничего.
  let followUid = null;          // чей вид повторяю
  let followLabel = '';          // его имя — для подсказки
  const leadUids = new Set();    // кого веду поимённо
  // Кого вёл, но у него оборвалась связь. Отдельно от leadUids, потому что
  // рассылать вид ушедшему незачем, а вот вернуть его под ведение, когда он
  // войдёт снова (обычно это просто перезагрузка страницы), — правильно.
  const leadPending = new Set();
  let leadAll = false;           // веду всех сразу
  const myFollowers = new Set(); // кто объявил, что следит за мной
  let viewOnly = false, applyingView = false, lastViewAt = 0;
  function iBroadcastView() { return leadAll || leadUids.size > 0 || myFollowers.size > 0; }
  function sendView() {
    if (!iBroadcastView() || applyingView) return;
    const now = Date.now(); if (now - lastViewAt < 60) return; lastViewAt = now;
    send({ action: 'view', x: stage.x(), y: stage.y(), scale: stage.scaleX() });
  }
  function applyView(user, x, y, scale) {
    // Повторяем вид ТОЛЬКО того, за кем сами следим. Раньше годился любой
    // ведущий, и два человека, нажавшие «Вести», рвали ведомого на части.
    if (followUid === null || String(user) !== String(followUid)) return;
    applyingView = true; stage.scale({ x: scale, y: scale }); stage.position({ x: x, y: y }); applyingView = false;
    scheduleViewRedraw();
  }
  // Объявить соседям договорённость. mode: 'follow' — «я смотрю за тобой»,
  // 'lead' — «смотри за мной». target: id участника или 'all'.
  function sendViewLink(mode, target, on) {
    send({ action: 'viewlink', mode: mode, target: String(target), on: on ? 1 : 0 });
  }
  // Начать/перестать следить за участником. Одновременно следить за двумя
  // нельзя — вид один, поэтому прежняя подписка снимается.
  function setFollowUid(uid, тихо) {
    const был = followUid;
    const новый = (uid === null || uid === undefined) ? null : String(uid);
    if (был !== null && был !== новый) sendViewLink('follow', был, false);  // прежнего отпускаем
    followUid = новый;
    followLabel = новый === null ? '' : (peers.get(Number(новый)) || peers.get(новый) || 'участник');
    if (новый !== null && был !== новый) {
      // Пока я не объявлю, что смотрю за ним, он свой вид не рассылает.
      sendViewLink('follow', новый, true);
      if (!тихо) boardHint('Следуем за: ' + followLabel);
      // Вести и следовать одновременно бессмысленно — вид пошёл бы по кругу.
      stopLeading(true);
    } else if (новый === null && был !== null && !тихо) {
      boardHint('Смотрите доску самостоятельно');
    }
    renderPeoplePanel(); syncPeopleBtn();
  }
  // Вести участника: его доска повторяет мою.
  function setLead(uid, on) {
    if (on) {
      setFollowUid(null, true);      // ведущий не может одновременно следовать
      leadUids.add(String(uid));
      sendViewLink('lead', uid, true); sendView();
      boardHint('Ведёте: ' + (peers.get(Number(uid)) || peers.get(uid) || 'участник'));
    } else {
      leadUids.delete(String(uid)); leadPending.delete(String(uid));
      sendViewLink('lead', uid, false);
    }
    renderPeoplePanel(); syncPeopleBtn();
  }
  function setLeadAll(on) {
    if (on) {
      setFollowUid(null, true);
      leadAll = true; leadUids.clear();
      sendViewLink('lead', 'all', true); sendView();
      boardHint('Ведёте всех — их доска повторяет вашу');
    } else {
      leadAll = false;
      sendViewLink('lead', 'all', false);
      boardHint('Больше никого не ведёте');
    }
    renderPeoplePanel(); syncPeopleBtn();
  }
  function stopLeading(тихо) {
    if (leadAll) { leadAll = false; sendViewLink('lead', 'all', false); }
    Array.from(leadUids).forEach((u) => { leadUids.delete(u); sendViewLink('lead', u, false); });
    leadPending.clear();
    if (!тихо) boardHint('Больше никого не ведёте');
    renderPeoplePanel(); syncPeopleBtn();
  }
  // Пришла договорённость от соседа.
  function onViewLink(msg) {
    const from = String(msg.user), мне = String(myId);
    const цель = String(msg.target || '');
    if (msg.mode === 'follow') {
      // За мной начали (или перестали) следить — от этого зависит, рассылать ли вид.
      if (цель !== мне) return;
      if (msg.on) { myFollowers.add(from); sendView(); } else myFollowers.delete(from);
      renderPeoplePanel(); syncPeopleBtn();
      return;
    }
    if (msg.mode === 'lead') {
      if (цель !== мне && цель !== 'all') return;
      if (msg.on) {
        if (String(followUid) !== from) {
          setFollowUid(from, true);
          if (msg.label) followLabel = msg.label;   // список соседей мог ещё не наполниться
          syncPeopleBtn();
          boardHint((msg.label || 'Участник') + ' ведёт — ваша доска идёт за ним');
        }
      } else if (String(followUid) === from) {
        setFollowUid(null, true);
        boardHint((msg.label || 'Участник') + ' больше не ведёт');
      }
    }
  }
  // Участник ушёл — все договорённости с ним теряют силу.
  function forgetViewLinks(uid) {
    const u = String(uid);
    myFollowers.delete(u);
    // Ведение не забываем совсем, а откладываем: вернётся — снова поведём.
    if (leadUids.delete(u)) leadPending.add(u);
    if (String(followUid) === u) { followUid = null; followLabel = ''; }
    renderPeoplePanel(); syncPeopleBtn();
  }
  function setViewOnly(on) { if (roleViewer) on = true; viewOnly = on; const b = document.getElementById('viewonly-btn'); if (b) { b.classList.toggle('on', on); b.disabled = roleViewer; } setTool(on ? 'select' : tool); if (!roleViewer) boardHint(on ? 'Только просмотр — правки заблокированы' : 'Правки разрешены'); }

  // ── Роли доступа (серверные) ────────────────────────────────────────────
  // myRole приходит с сервера; наблюдатель («viewer») не может править — сервер
  // отклоняет его правки, а клиент запирает UI (view-only без права выключить).
  let boardIsOwner = false, myRole = 'editor', boardDefaultRole = 'editor', boardRoles = {}, roleViewer = false;
  let boardRemoved = [];   // [{id, label}] — кого владелец убрал с доски
  let iAmRemoved = false;  // меня убрали: не переподключаемся и не шлём правки
  function computeMyRole() { if (boardIsOwner) return 'editor'; const r = boardRoles[String(myId)]; return (r === 'viewer' || r === 'editor') ? r : boardDefaultRole; }
  function applyMyRole() {
    myRole = computeMyRole(); roleViewer = (myRole === 'viewer');
    const badge = document.getElementById('role-badge');
    if (badge) { if (boardIsOwner) { badge.hidden = true; } else { badge.hidden = false; badge.textContent = roleViewer ? 'Наблюдатель' : 'Редактор'; badge.classList.toggle('viewer', roleViewer); } }
    // Кнопка «Участники» нужна всем: вести и следовать может каждый. Роли и
    // пароль спрятаны внутри панели, в разделе владельца.
    renderPeoplePanel(); syncPeopleBtn();
    if (roleViewer) { setViewOnly(true); boardHint('Ваша роль — наблюдатель: можно только смотреть'); }
    else { const vb = document.getElementById('viewonly-btn'); if (vb) vb.disabled = false; setViewOnly(false); }
  }
  function peerLabels() { const m = {}; peers.forEach((lab, uid) => { m[String(uid)] = lab; }); return m; }
  // Кнопка в плашке: число людей на доске и зелёная подсветка, когда вид с
  // кем-то связан. Без подсветки «почему доска сама ездит» — загадка.
  function syncPeopleBtn() {
    const b = document.getElementById('people-btn'); if (!b) return;
    const c = document.getElementById('people-count');
    if (c) c.textContent = String(peers.size + 1);   // +1 — я сам
    b.classList.toggle('live', followUid !== null || iBroadcastView());
    let t = 'Участники: кто сейчас на доске, кого вести и за кем следовать';
    if (followUid !== null) t = 'Следуете за: ' + (followLabel || 'участником');
    else if (leadAll) t = 'Вы ведёте всех';
    else if (leadUids.size) t = 'Вы ведёте участников: ' + leadUids.size;
    b.title = t;
  }
  // Значки действий. Глаз — «смотреть его глазами»; экран со стрелкой внутрь —
  // «привести его к моему виду».
  const PP_FOLLOW_SVG = '<svg viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="2.7"/></svg>';
  const PP_LEAD_SVG = '<svg viewBox="0 0 24 24"><rect x="3" y="4.5" width="18" height="12.5" rx="2"/><path d="M12 17v3M8.5 20h7"/><path d="M8.5 10.7h5.5M11.8 8.4l2.7 2.3-2.7 2.3"/></svg>';
  function renderPeoplePanel() {
    const p = document.getElementById('people-panel'); if (!p || p.hidden) { syncPeopleBtn(); return; }
    // Раздел владельца: роли, пароль, убранные. Остальным его не показываем —
    // на общей доске чужие роли знать незачем.
    const own = document.getElementById('pp-owner'); if (own) own.hidden = !boardIsOwner;
    const seg = document.getElementById('ap-default');
    if (seg) seg.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.role === boardDefaultRole));
    const la = document.getElementById('lead-all-btn');
    if (la) { la.classList.toggle('on', leadAll); la.textContent = leadAll ? 'Не вести никого' : 'Вести всех'; la.disabled = peers.size === 0; }
    const uf = document.getElementById('unfollow-btn');
    if (uf) uf.disabled = (followUid === null);
    const box = document.getElementById('pp-people'); if (!box) return;
    const labels = peerLabels(), ids = [];
    peers.forEach((_, uid) => { if (String(uid) !== String(myId)) ids.push(String(uid)); });
    // Владельцу показываем и тех, кому назначена личная роль, даже если их
    // сейчас нет на доске: иначе роль некуда было бы вернуть.
    if (boardIsOwner) Object.keys(boardRoles).forEach((uid) => { if (uid !== String(myId) && ids.indexOf(uid) < 0) ids.push(uid); });
    let html = '<div class="pp-row"><div class="pp-line"><span class="pp-name">' + escapeHtml(myLabel || 'Вы')
      + ' <span class="pp-me">' + (boardIsOwner ? '· вы, владелец' : '· вы') + '</span></span></div></div>';
    if (!ids.length) html += '<div class="pp-empty">Больше на доске никого нет</div>';
    ids.forEach((uid) => {
      const тут = peers.has(Number(uid)) || peers.has(uid);
      const label = labels[uid] || ('участник #' + uid);
      const r = boardRoles[uid], eff = (r === 'viewer' || r === 'editor') ? r : boardDefaultRole;
      const слежу = String(followUid) === uid, веду = leadAll || leadUids.has(uid);
      // Верхняя строка — имя и значки видов (нужны всем), нижняя — роль и
      // «Убрать» (только владельцу). В одну строку имя было не разглядеть.
      html += '<div class="pp-row"><div class="pp-line"><span class="pp-name">' + escapeHtml(label)
        + (тут ? '' : ' <span class="pp-me">· не на доске</span>') + '</span>';
      if (тут) {
        html += '<button class="pp-act' + (слежу ? ' on' : '') + '" data-follow="' + uid + '" title="Следовать: ваша доска повторяет его вид">' + PP_FOLLOW_SVG + '</button>'
          + '<button class="pp-act' + (веду ? ' on' : '') + '" data-lead="' + uid + '" title="Вести: его доска повторяет ваш вид">' + PP_LEAD_SVG + '</button>';
      }
      html += '</div>';
      if (boardIsOwner) {
        html += '<div class="pp-line"><div class="ap-seg" data-uid="' + uid + '">'
          + '<button data-r="editor"' + (eff === 'editor' ? ' class="on"' : '') + '>Ред.</button>'
          + '<button data-r="viewer"' + (eff === 'viewer' ? ' class="on"' : '') + '>Набл.</button>'
          + '</div>'
          + '<button class="ap-kick" data-kick="' + uid + '" title="Убрать с доски: выйдет сейчас и не войдёт по ссылке">Убрать</button></div>';
      }
      html += '</div>';
    });
    box.innerHTML = html;
    renderRemovedPeople();
    syncPeopleBtn();
  }
  // Раздел «Убранные с доски»: показываем, только если кого-то убрали.
  function renderRemovedPeople() {
    const wrap = document.getElementById('ap-removed-wrap'), box = document.getElementById('ap-removed');
    if (!wrap || !box) return;
    if (!boardIsOwner || !boardRemoved.length) { wrap.hidden = true; box.innerHTML = ''; return; }
    wrap.hidden = false;
    box.innerHTML = boardRemoved.map((p) =>
      '<div class="ap-person"><span class="ap-name">' + escapeHtml(p.label || ('участник #' + p.id)) + '</span>'
      + '<button class="ap-back" data-back="' + p.id + '" title="Вернуть доступ к доске">Вернуть</button></div>'
    ).join('');
  }
  function togglePeoplePanel(force) {
    const p = document.getElementById('people-panel'), ab = document.getElementById('people-btn'); if (!p) return;
    const show = force === undefined ? p.hidden : force;
    p.hidden = !show; if (ab) ab.classList.toggle('on', show);
    if (show) renderPeoplePanel(); else syncPeopleBtn();
  }
  // Закрытие: крестик, щелчок мимо и Escape. Прежде у панели не было ни того,
  // ни другого — закрыть её можно было только повторным нажатием кнопки.
  document.addEventListener('mousedown', (e) => {
    const p = document.getElementById('people-panel');
    // closest() есть только у элементов: цель нажатия бывает и текстовым узлом,
    // и самим документом — без проверки такой случай ронял бы обработчик.
    const t = (e.target && e.target.closest) ? e.target : null; if (!t) return;
    if (p && !p.hidden && !t.closest('#people-panel') && !t.closest('#people-btn')) togglePeoplePanel(false);
  });
  function syncBgUI() {
    document.querySelectorAll('#bg-seg button').forEach((b) => b.classList.toggle('on', b.dataset.bg === boardBg));
    // Плашки цвета: образец красим текущим цветом (или значением по умолчанию),
    // системный выбор выставляем на тот же цвет.
    const sw = document.getElementById('bg-color-sw'), pick = document.getElementById('bg-color-custom');
    if (sw) sw.style.background = boardBgColor || '#fbfbfd';
    const cur = (boardBgColor || '').toLowerCase();
    if (pick && /^#[0-9a-f]{6}$/.test(cur)) pick.value = cur;
    const gsw = document.getElementById('bg-grid-color-sw'), gpick = document.getElementById('bg-grid-color-custom');
    if (gsw) gsw.style.background = boardGridColor || '#e2e2ea';
    const gcur = (boardGridColor || '').toLowerCase();
    if (gpick && /^#[0-9a-f]{6}$/.test(gcur)) gpick.value = gcur;
  }
  // ── Меню доски (три точки): вид, курсоры, выравнивание, история, очистка ──
  function hideBoardMenu() { const p = document.getElementById('board-menu'), b = document.getElementById('board-menu-btn'); if (p) p.hidden = true; if (b) b.classList.remove('on'); }
  function toggleBoardMenu() {
    const p = document.getElementById('board-menu'), b = document.getElementById('board-menu-btn'); if (!p) return;
    const show = p.hidden; p.hidden = !show; if (b) b.classList.toggle('on', show);
    if (show) { syncBgUI(); const c = document.getElementById('cursors-toggle'); if (c) c.checked = showPeerCursors; const g = document.getElementById('guides-toggle'); if (g) g.checked = guidesEnabled; }
  }
  // Клик мимо меню — закрыть.
  document.addEventListener('mousedown', (e) => { const m = document.getElementById('board-menu'); if (m && !m.hidden && !e.target.closest('#board-menu') && !e.target.closest('#board-menu-btn')) hideBoardMenu(); });
  // Показ курсоров участников (тумблер в меню).
  function setPeerCursors(on) {
    showPeerCursors = on;
    if (!on) { cursors.forEach((c) => { if (c.el) c.el.style.display = 'none'; }); }
    else { cursors.forEach((c) => { if (c.el) c.el.style.display = ''; }); }
  }
  function toggleHistoryPanel(show) {
    const p = document.getElementById('history-panel'); if (!p) return;
    p.hidden = !show; if (show) renderHistory();
  }
  function historyOpen() { const p = document.getElementById('history-panel'); return p && !p.hidden; }
  // ── Общая история доски (сервер): последние 200 действий всех участников ──
  let boardHistory = []; // [{id, action, eid, etype, label, ts, payload}] старые→новые
  function applyHistoryEntry(entry) {
    if (!entry) return;
    const i = boardHistory.findIndex((e) => e.id === entry.id);
    if (i >= 0) boardHistory[i] = entry; else boardHistory.push(entry);
    if (boardHistory.length > 200) boardHistory = boardHistory.slice(-200);
    if (historyOpen()) renderHistory();
  }
  function histActionWord(a) { return a === 'add' ? 'добавлен(а)' : a === 'delete' ? 'удалён(а)' : 'изменён(а)'; }
  // Время собиралось руками из getHours/getMinutes — то есть навязывало
  // 24-часовой вид всем. Intl знает, как принято у читателя.
  const HIST_TIME_FMT = (function () {
    try { return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }); }
    catch (e) { return null; }
  })();
  function histTime(ts) {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      if (HIST_TIME_FMT) return HIST_TIME_FMT.format(d);
      return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
    } catch (e) { return ''; }
  }
  function renderHistory() {
    const box = document.getElementById('history-list'); if (!box) return;
    if (!boardHistory.length) { box.innerHTML = '<div class="ap-hint">пока пусто</div>'; return; }
    let html = '';
    for (let i = boardHistory.length - 1; i >= 0; i--) {
      const e = boardHistory[i], t = TYPE_NAMES[e.etype] || 'объект', gone = e.action !== 'delete' && !elements.has(e.eid);
      const desc = histActionWord(e.action) + ' ' + t + (e.label ? ' · ' + e.label : '');
      const act = e.action === 'delete'
        ? '<button class="hist-restore" data-restore="' + e.id + '">Восстановить</button>'
        : '<span class="hist-i">' + histTime(e.ts) + '</span>';
      html += '<div class="hist-row' + (gone ? ' gone' : '') + '"' + (e.action !== 'delete' ? ' data-focus="' + escapeAttr(e.eid) + '"' : '') + '><span>' + escapeHtml(desc) + '</span>' + act + '</div>';
    }
    box.innerHTML = html;
  }
  function restoreFromHistory(hid) {
    const e = boardHistory.find((x) => x.id === +hid); if (!e || !e.payload) { boardHint('Нечего восстанавливать'); return; }
    if (roleViewer) { boardHint('Наблюдатель не может править доску'); return; }
    if (elements.has(e.payload.id)) { boardHint('Объект уже на доске'); focusElement(e.payload.id); return; }
    const el = { id: e.payload.id, type: e.payload.type, z: e.payload.z || 0, data: e.payload.data || {} };
    upsertNode(el); send({ action: 'element_add', element: el }); histAdd(el);
    reattachFuncs(); recomputeGeometry(); layer.batchDraw();
    boardHint('Восстановлено: ' + (TYPE_NAMES[el.type] || 'объект')); focusElement(el.id);
  }
  function focusElement(eid) {
    const el = elements.get(eid); if (!el) { boardHint('Объект уже удалён — можно восстановить из строки удаления'); return; }
    const n = nodes.get(eid); let cx, cy;
    if (el.type === 'frame') { cx = el.data.x + el.data.width / 2; cy = el.data.y + el.data.height / 2; }
    else if (n && typeof n.getClientRect === 'function') { const b = n.getClientRect({ relativeTo: layer }); cx = b.x + b.width / 2; cy = b.y + b.height / 2; }
    else if (el.data && el.data.x != null) { cx = el.data.x; cy = el.data.y; }
    if (cx != null) { const s = stage.scaleX(); stage.position({ x: stage.width() / 2 - cx * s, y: stage.height() / 2 - cy * s }); redrawGrid(); repositionCursors(); layer.batchDraw(); }
    if (nodes.has(eid) && !widgetItems.has(eid)) selectOnly(eid);
  }
  (function wireHistory() {
    const box = document.getElementById('history-list'); if (!box) return;
    box.addEventListener('click', (e) => {
      const rb = e.target.closest('.hist-restore');
      if (rb) { e.stopPropagation(); restoreFromHistory(rb.getAttribute('data-restore')); return; }
      const row = e.target.closest('.hist-row'); if (!row || row.dataset.focus == null) return;
      focusElement(row.dataset.focus);
    });
  })();
  // Очистить доску — удалить все элементы (кроме конфигурации фона). С подтверждением.
  function clearBoard() {
    if (roleViewer) { boardHint('Наблюдатель не может очищать доску'); return; }
    const ids = []; elements.forEach((el, id) => { if (el.type !== 'boardconfig') ids.push(id); });
    if (!ids.length) { boardHint('Доска уже пуста'); return; }
    uiConfirm('Удалить всё с доски (' + ids.length + ' объект(ов))? Действие можно отменить (Ctrl+Z).', { danger: true, ok: 'Удалить всё' }).then((ok) => {
      if (!ok) return;
      const ops = ids.map((id) => ({ kind: 'del', el: clone(elements.get(id)) }));
      ids.forEach((id) => { send({ action: 'element_delete', id: id }); removeNode(id); });
      histBatch(ops);
      clearSelection(); layer.batchDraw();
      boardHint('Доска очищена (' + ids.length + ')');
    });
  }

  // ── ГеоГебра: живые аплеты как DOM-оверлей в мировых координатах ───────
  // Аплет интерактивный (не картинка), поэтому живёт отдельным слоем поверх
  // холста и следует за панорамой/зумом. Синхронизируются позиция/размер и
  // (для восстановления после перезагрузки) base64 построения. Живой push
  // построения другим участникам в этом шаге не делаем, чтобы не сбивать руки.
  const ggbItems = new Map(); // id → { el, wrapper, api, saveTimer }
  const ggbLayerEl = document.getElementById('ggb-layer');

  function whenGGBReady(fn) {
    if (window.GGBApplet) fn();
    else setTimeout(() => whenGGBReady(fn), 100);
  }

  function repositionGGB() {
    if (!ggbItems.size) return;
    const s = stage.scaleX();
    ggbItems.forEach((item) => {
      const d = item.el.data;
      const x = (d.x || 0) * s + stage.x();
      const y = (d.y || 0) * s + stage.y();
      item.wrapper.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')';
    });
  }

  function upsertGGB(el) {
    let item = ggbItems.get(el.id);
    if (item) {
      // Обновляем только данные позиции/размера (построение не трогаем, чтобы
      // не сбить того, кто сейчас в нём работает).
      item.el = el;
      repositionGGB();
      return;
    }
    const d = el.data || {};
    const wrapper = document.createElement('div');
    wrapper.className = 'ggb-item';
    wrapper.style.width = (d.width || 600) + 'px';
    const bar = document.createElement('div');
    bar.className = 'ggb-bar';
    bar.innerHTML = '<span class="ggb-title">GeoGebra</span>'
      + '<button class="ggb-del" title="Удалить">'
      + '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg></button>';
    const appletDiv = document.createElement('div');
    appletDiv.className = 'ggb-applet';
    const appletId = 'ggb-applet-' + el.id;
    appletDiv.id = appletId;
    wrapper.appendChild(bar);
    wrapper.appendChild(appletDiv);
    ggbLayerEl.appendChild(wrapper);

    item = { el, wrapper, api: null, saveTimer: null };
    ggbItems.set(el.id, item);
    repositionGGB();

    bar.querySelector('.ggb-del').addEventListener('click', () => {
      send({ action: 'element_delete', id: el.id });
      removeGGB(el.id);
      elements.delete(el.id);
    });
    enableGGBDrag(item, bar);

    whenGGBReady(() => {
      const params = {
        appName: d.appName || 'graphing',
        width: d.width || 600, height: d.height || 420,
        showToolBar: true, showMenuBar: false, showAlgebraInput: true,
        showResetIcon: false, enableShiftDragZoom: true, errorDialogsActive: false,
        language: 'ru', borderColor: '#e3e3e8',
        ggbBase64: d.base64 || undefined,
        appletOnLoad: (api) => { item.api = api; registerGGBSave(item); },
      };
      new GGBApplet(params, true).inject(appletId);
    });
  }

  function registerGGBSave(item) {
    const api = item.api;
    if (!api || !api.registerUpdateListener) return;
    const save = () => {
      if (item.saveTimer) clearTimeout(item.saveTimer);
      item.saveTimer = setTimeout(() => {
        try {
          item.el.data.base64 = api.getBase64();
          send({ action: 'element_update', element: item.el });
        } catch (e) { /* ignore */ }
      }, 1200);
    };
    try {
      api.registerUpdateListener(save);
      api.registerAddListener(save);
      api.registerRemoveListener(save);
      api.registerClearListener(save);
    } catch (e) { /* ignore */ }
  }

  function enableGGBDrag(item, handle) {
    handle.addEventListener('mousedown', (e) => {
      if (e.target.closest('.ggb-del')) return;
      e.preventDefault();
      const s = stage.scaleX();
      const startX = e.clientX, startY = e.clientY;
      const ox = item.el.data.x || 0, oy = item.el.data.y || 0;
      const onMove = (ev) => {
        item.el.data.x = ox + (ev.clientX - startX) / s;
        item.el.data.y = oy + (ev.clientY - startY) / s;
        repositionGGB();
      };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        send({ action: 'element_update', element: item.el });
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  }

  function removeGGB(id) {
    const item = ggbItems.get(id);
    if (!item) return;
    if (item.saveTimer) clearTimeout(item.saveTimer);
    try { if (item.api && item.api.remove) item.api.remove(); } catch (e) { /* ignore */ }
    item.wrapper.remove();
    ggbItems.delete(id);
  }

  function insertGeoGebra() {
    const p = worldPoint();
    const el = { id: uuid(), type: 'geogebra', z: 0,
      data: { x: p.x, y: p.y, width: 600, height: 420, appName: 'graphing' } };
    upsertNode(el);
    send({ action: 'element_add', element: el });
    histAdd(el);
    setTool('select');
  }

  function removeCursor(uid) {
    const c = cursors.get(uid);
    if (c) { c.el.remove(); cursors.delete(uid); }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (m) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]
    ));
  }

  // ── Экспорт доски в PDF ────────────────────────────────────────────────
  // Холст — Konva-canvas, а текст/виджеты — DOM (#widget-layer). Чтобы собрать
  // и то, и другое, снимаем всю область через html2canvas, затем кладём в PDF
  // (jsPDF). Библиотеки грузим лениво — только при первом экспорте.
  let _exportLibs = null;
  function loadExportLibs() {
    if (_exportLibs) return _exportLibs;
    const load = (src) => new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('load ' + src)); document.head.appendChild(s); });
    _exportLibs = Promise.all([
      (typeof html2canvas !== 'undefined') ? Promise.resolve() : load(cfg.html2canvas),
      (window.jspdf) ? Promise.resolve() : load(cfg.jspdf),
    ]).catch((e) => { _exportLibs = null; throw e; });
    return _exportLibs;
  }
  function contentBBox() {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, any = false;
    nodes.forEach((n, id) => {
      const el = elements.get(id); if (el && el.data && el.data.hidden && !revealHidden) return;
      const b = n.getClientRect({ relativeTo: layer });
      if (b.width || b.height) { x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y); x1 = Math.max(x1, b.x + b.width); y1 = Math.max(y1, b.y + b.height); any = true; }
    });
    widgetItems.forEach((it) => { const d = it.el.data, w = it.wrapper.offsetWidth || 0, h = it.wrapper.offsetHeight || 0; if (w || h) { x0 = Math.min(x0, d.x || 0); y0 = Math.min(y0, d.y || 0); x1 = Math.max(x1, (d.x || 0) + w); y1 = Math.max(y1, (d.y || 0) + h); any = true; } });
    if (!any) return null;
    return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  }
  const EXPORT_HIDE_IDS = ['board-toolbar', 'board-topbar', 'board-head', 'board-menu', 'zoom-control', 'board-version', 'cursor-layer', 'tbox-bar', 'dp-pop', 'shape-panel', 'sticky-panel', 'stroke-panel', 'conn-panel', 'settings-btn', 'settings-menu', 'history-panel', 'people-panel', 'point-settings', 'figure-settings', 'func-editor', 'text-editor', 'conn-banner'];
  function exportIgnore(el) {
    if (!el) return false;
    if (el.id && EXPORT_HIDE_IDS.indexOf(el.id) >= 0) return true;
    return !!(el.classList && (el.classList.contains('tool-flyout') || el.classList.contains('cn-pop') || el.classList.contains('te-pop') || el.classList.contains('color-palette') || el.classList.contains('eraser-ring') || el.classList.contains('mtext-del')));
  }
  let _exporting = false;
  // Снимок области ЭКРАНА (screen-коорды) в картинку через html2canvas.
  async function pdfCapture(screenRect) {
    await new Promise((r) => setTimeout(r, 130)); // дать DOM/Konva перерисоваться
    const canvas = await html2canvas(document.body, {
      backgroundColor: boardBgColor || '#ffffff', scale: 2, logging: false, useCORS: true,
      ignoreElements: exportIgnore,
      x: screenRect.x, y: screenRect.y, width: screenRect.width, height: screenRect.height,
      windowWidth: document.documentElement.scrollWidth, windowHeight: document.documentElement.scrollHeight,
    });
    return { img: canvas.toDataURL('image/jpeg', 0.92), wpx: canvas.width, hpx: canvas.height };
  }
  // Вписать мировой прямоугольник (коорды layer) в вьюпорт холста; вернуть масштаб.
  function pdfFitStageTo(rect, pad) {
    const vw = stage.width(), vh = stage.height();
    let s = Math.min((vw - 2 * pad) / rect.width, (vh - 2 * pad) / rect.height); s = Math.max(0.05, Math.min(s, 4));
    stage.scale({ x: s, y: s });
    stage.position({ x: pad - rect.x * s + (vw - 2 * pad - rect.width * s) / 2, y: pad - rect.y * s + (vh - 2 * pad - rect.height * s) / 2 });
    redrawGrid(); repositionWidgets(); layer.draw();
    return s;
  }
  // Экранный прямоугольник мирового прямоугольника при текущем трансформе сцены.
  function pdfScreenRectOf(rect) {
    const c = stage.container().getBoundingClientRect(), s = stage.scaleX();
    return { x: c.left + rect.x * s + stage.x(), y: c.top + rect.y * s + stage.y(), width: rect.width * s, height: rect.height * s };
  }
  // BBox набора узлов (коорды layer), включая DOM-виджеты.
  function pdfNodesBBox(ids) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, any = false;
    ids.forEach((id) => {
      const n = nodes.get(id);
      if (n) { const b = n.getClientRect({ relativeTo: layer }); if (b.width || b.height) { x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y); x1 = Math.max(x1, b.x + b.width); y1 = Math.max(y1, b.y + b.height); any = true; } }
      const it = widgetItems.get(id);
      if (it) { const d = it.el.data, w = it.wrapper.offsetWidth || 0, h = it.wrapper.offsetHeight || 0; if (w || h) { x0 = Math.min(x0, d.x || 0); y0 = Math.min(y0, d.y || 0); x1 = Math.max(x1, (d.x || 0) + w); y1 = Math.max(y1, (d.y || 0) + h); any = true; } }
    });
    return any ? { x: x0, y: y0, width: x1 - x0, height: y1 - y0 } : null;
  }
  // Добавить снимок как страницу A4 (ориентация по пропорциям снимка), вписав по центру.
  function pdfAddPage(ref, cap) {
    const landscape = cap.wpx >= cap.hpx;
    if (!ref.pdf) { const jsPDF = window.jspdf.jsPDF; ref.pdf = new jsPDF({ orientation: landscape ? 'l' : 'p', unit: 'pt', format: 'a4' }); }
    else ref.pdf.addPage('a4', landscape ? 'l' : 'p');
    const pdf = ref.pdf, pw = pdf.internal.pageSize.getWidth(), ph = pdf.internal.pageSize.getHeight();
    const r = Math.min(pw / cap.wpx, ph / cap.hpx), dw = cap.wpx * r, dh = cap.hpx * r;
    pdf.addImage(cap.img, 'JPEG', (pw - dw) / 2, (ph - dh) / 2, dw, dh);
  }
  // Экспорт доски в PDF. mode: 'whole' (вся доска тайлами A4), 'frames' (по окну
  // на страницу), 'selection' (только выделенное — одна страница).
  async function exportBoardPdf(mode) {
    if (_exporting) return;
    mode = mode || 'whole';
    const selIds = Array.from(selected);
    if (mode === 'selection' && !selIds.length) { boardHint('Сначала выделите объекты'); return; }
    const frames = [];
    elements.forEach((e) => { if (e.type === 'frame') frames.push(e); });
    frames.sort((a, b) => (a.data.y - b.data.y) || (a.data.x - b.data.x)); // порядок чтения
    if (mode === 'frames' && !frames.length) { boardHint('На доске нет матокон'); return; }
    const bbox = contentBBox();
    if (!bbox) { boardHint('Доска пуста — нечего экспортировать'); return; }
    const selBox = (mode === 'selection') ? pdfNodesBBox(selIds) : null;
    if (mode === 'selection' && !selBox) { boardHint('Не удалось определить область выделения'); return; }
    _exporting = true; boardHint('Готовлю PDF…');
    // Экспорт рисует плитки синхронно — отсечение на это время выключаем,
    // иначе в плитку не попало бы то, что было за краем ПРЕДЫДУЩЕГО вида.
    setCulling(false);
    const save = { x: stage.x(), y: stage.y(), s: stage.scaleX() };
    const restore = () => {
      stage.scale({ x: save.s, y: save.s }); stage.position({ x: save.x, y: save.y });
      redrawGrid(); repositionWidgets();
      setCulling(true);          // обязательно: иначе доска осталась бы без отсечения
      layer.batchDraw();
    };
    clearSelection(); if (handlesGroup && handlesGroup.visible()) handlesGroup.hide(); if (connHandles && connHandles.visible()) connHandles.hide(); tr.nodes([]);
    const ref = { pdf: null };
    try {
      await loadExportLibs();
      if (mode === 'selection') {
        pdfFitStageTo(selBox, 24);
        pdfAddPage(ref, await pdfCapture(pdfScreenRectOf(selBox)));
      } else if (mode === 'frames') {
        for (let i = 0; i < frames.length; i++) {
          const fr = frames[i], wr = { x: fr.data.x, y: fr.data.y, width: fr.data.width, height: fr.data.height };
          pdfFitStageTo(wr, 18);
          boardHint('Страница ' + (i + 1) + ' из ' + frames.length + '…');
          pdfAddPage(ref, await pdfCapture(pdfScreenRectOf(wr)));
        }
      } else { // 'whole' — вся доска, тайлами A4 по текущему масштабу (крупно)
        const vw = stage.width(), vh = stage.height();
        let S = Math.max(0.06, save.s); // масштаб «как сейчас видно»
        let cols = Math.max(1, Math.ceil(bbox.width * S / vw)), rows = Math.max(1, Math.ceil(bbox.height * S / vh));
        while (cols * rows > 40 && S > 0.06) { S *= 0.8; cols = Math.max(1, Math.ceil(bbox.width * S / vw)); rows = Math.max(1, Math.ceil(bbox.height * S / vh)); }
        const cont = stage.container().getBoundingClientRect(), total = cols * rows;
        let page = 0;
        for (let r = 0; r < rows; r++) {
          for (let c = 0; c < cols; c++) {
            stage.scale({ x: S, y: S });
            stage.position({ x: -(bbox.x * S + c * vw), y: -(bbox.y * S + r * vh) });
            redrawGrid(); repositionWidgets(); layer.draw();
            page++; boardHint('Страница ' + page + ' из ' + total + '…');
            pdfAddPage(ref, await pdfCapture({ x: cont.left, y: cont.top, width: cont.width, height: cont.height }));
          }
        }
      }
      restore();
      if (!ref.pdf) { boardHint('Нечего экспортировать'); return; }
      const title = ((document.getElementById('board-title') || {}).textContent || 'Доска').trim() || 'Доска';
      ref.pdf.save(title + '.pdf');
      boardHint('PDF готов');
    } catch (e) {
      restore();
      boardHint('Не удалось сделать PDF (проверьте связь для загрузки библиотек)');
      try { console.error('export pdf', e); } catch (_) {}
    } finally { _exporting = false; }
  }

  // ── Голосовая связь ────────────────────────────────────────────────────
  // Звук идёт НАПРЯМУЮ между браузерами участников, минуя наш сервер: он лишь
  // пересылает служебные сообщения, которыми браузеры «знакомятся». Поэтому
  // нагрузки на сервер почти нет, а задержка минимальная.
  //
  // Чего ждать честно: примерно у одного участника из пяти домашний роутер или
  // мобильный оператор прямое соединение не пропустит. Лечится это отдельным
  // сервером-ретранслятором (TURN) — его сюда можно добавить одной строкой в
  // VOICE_ICE, когда и если понадобится.

  // Список серверов связи присылает сервер (см. board/turn.py): пропуск к
  // ретранслятору временный, а состав списка — вопрос настройки, а не кода.
  // Запасной вариант нужен только на случай, если сервер ничего не прислал.
  const VOICE_ICE = (cfg && cfg.iceServers && cfg.iceServers.length)
    ? cfg.iceServers
    : [{ urls: ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302'] }];
  // Есть ли в списке сервер-ретранслятор. Без него примерно у каждого пятого
  // домашний роутер прямую связь не пропускает — и человеку стоит сказать
  // именно это, а не «не удалось соединиться».
  const HAS_TURN = VOICE_ICE.some((s) => [].concat(s.urls || s.url || []).some((u) => /^turns?:/i.test(String(u))));
  // Сейчас все соединяются со всеми — при двух-трёх это лучший вариант. Дальше
  // растёт квадратично, поэтому честно предупреждаем, а не молча тормозим.
  const MESH_SOFT_LIMIT = 5;
  // Браузер не даёт играть звуку на странице, где человек ничего не нажимал.
  // Слушателю нажимать незачем, поэтому ловим отказ и играем с первого щелчка.
  let audioBlocked = false;

  let myPeer = null;              // id этого соединения (вкладки), приходит с сервера
  let voiceOn = false;            // мы в разговоре
  let voiceMuted = false;         // микрофон выключен (но разговор идёт)
  let localStream = null;
  let voiceCtx = null;            // для определения, кто сейчас говорит
  let voiceTimer = null;
  const voicePeers = new Map();   // peerId → { pc, label, audio, analyser, buf, pending, speaking }

  function rtcSend(kind, to, data) { send({ action: 'rtc', kind: kind, to: to || null, data: data || null }); }

  function voiceBtn() { return document.getElementById('voice-btn'); }
  function voicePanel() { return document.getElementById('voice-panel'); }

  // ── Кто сейчас говорит ────────────────────────────────────────────────
  // Считаем громкость дорожки: так видно, что микрофон жив и кто говорит.
  function watchLevel(holder, stream) {
    try {
      if (!voiceCtx) voiceCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (voiceCtx.state === 'suspended') voiceCtx.resume();
      const src = voiceCtx.createMediaStreamSource(stream);
      const an = voiceCtx.createAnalyser();
      an.fftSize = 1024; an.smoothingTimeConstant = 0.4;
      src.connect(an);
      holder.analyser = an;
      // Буфер под ВОЛНУ (не спектр): длина равна fftSize.
      holder.buf = new Uint8Array(an.fftSize);
    } catch (e) { /* без индикатора обойдёмся */ }
  }
  // Громкость считаем по звуковой ВОЛНЕ, а не по усреднённому спектру: усреднение
  // по всем частотам занижает результат в разы (энергия голоса сидит в узкой
  // полосе и тонет среди пустых частот), и индикатор молчал бы даже при крике.
  function levelOf(holder) {
    if (!holder || !holder.analyser) return 0;
    holder.analyser.getByteTimeDomainData(holder.buf);
    let sum = 0;
    for (let i = 0; i < holder.buf.length; i++) {
      const v = (holder.buf[i] - 128) / 128;   // отклонение от тишины, −1…+1
      sum += v * v;
    }
    return Math.sqrt(sum / holder.buf.length); // среднеквадратичная громкость
  }
  function startVoiceMeter() {
    if (voiceTimer) return;
    voiceTimer = setInterval(() => {
      let changed = false;
      const me = { analyser: localHolder.analyser, buf: localHolder.buf };
      const lvlMe = voiceMuted ? 0 : levelOf(me);
      const spMe = lvlMe > SPEAK_LEVEL;
      if (spMe !== localHolder.speaking) { localHolder.speaking = spMe; changed = true; }
      voicePeers.forEach((p) => {
        const sp = levelOf(p) > SPEAK_LEVEL;
        if (sp !== p.speaking) { p.speaking = sp; changed = true; }
        // Подпись меняется и сама по себе — когда сосед наконец включил
        // микрофон и пошёл звук. Без этой проверки список бы не обновился.
        const t = peerStateText(p);
        if (t !== p._shownState) { p._shownState = t; changed = true; }
      });
      if (changed) renderVoiceList();
    }, 180);
  }
  function stopVoiceMeter() { if (voiceTimer) { clearInterval(voiceTimer); voiceTimer = null; } }
  const localHolder = { analyser: null, buf: null, speaking: false };
  const SPEAK_LEVEL = 0.03;   // порог «говорит»: тише — считаем тишиной

  // Соединение с одним участником.
  //
  // Переговоры ведём по схеме «идеальных переговоров»: любая сторона может в
  // любой момент добавить дорожку (включить микрофон, начать показ экрана), и
  // браузер сам попросит переспросить состав связи. Если обе стороны заговорят
  // одновременно, «вежливая» (та, у кого id меньше) уступает и переспрашивает
  // заново. Без этого показ экрана посреди разговора рвал бы соединение.
  // Своё описание связи БЕЗ АРГУМЕНТА: браузер сам решает, предложение сейчас
  // уместно или ответ. Именно этого не хватало — обработчик «нужны переговоры»
  // готовил предложение заранее и пытался применить его уже после того, как
  // принято чужое, а браузер отвечал «не в том состоянии».
  function setLocalAuto(pc) {
    try {
      const p = pc.setLocalDescription();
      if (p && typeof p.then === 'function') return p;
    } catch (e) { /* старый браузер: без аргумента нельзя */ }
    return (pc.signalingState === 'have-remote-offer' ? pc.createAnswer() : pc.createOffer())
      .then((d) => pc.setLocalDescription(d));
  }
  function sendLocalDesc(pid, pc) {
    const d = pc.localDescription;
    if (!d) return;
    rtcSend(d.type === 'answer' ? 'answer' : 'offer', pid, { type: d.type, sdp: d.sdp });
  }
  function ensurePeer(pid, label) {
    let p = voicePeers.get(pid);
    if (p) { if (label) p.label = label; return p; }
    let pc;
    try { pc = new RTCPeerConnection({ iceServers: VOICE_ICE }); }
    catch (e) { boardHint('Браузер не поддерживает прямую связь'); return null; }
    p = {
      pc: pc, pid: pid, label: label || 'участник',
      audio: null, analyser: null, buf: null, pending: [], speaking: false,
      state: 'связываемся',
      polite: (myPeer < pid), makingOffer: false, ignoreOffer: false,
      senders: {},          // вид дорожки → отправитель (чтобы убирать по одной)
    };
    voicePeers.set(pid, p);

    if (localStream) localStream.getTracks().forEach((t) => addTrackTo(p, t, localStream, 'mic'));
    if (screenStream) screenStream.getTracks().forEach((t) => addTrackTo(p, t, screenStream, 'screen'));

    pc.onicecandidate = (e) => { if (e.candidate) rtcSend('ice', pid, e.candidate.toJSON ? e.candidate.toJSON() : e.candidate); };
    pc.onnegotiationneeded = () => {
      p.makingOffer = true;
      setLocalAuto(pc)
        .then(() => sendLocalDesc(pid, pc))
        .catch((e) => { try { console.warn('голос: не удалось предложить связь', e); } catch (_) {} })
        .then(() => { p.makingOffer = false; });
    };
    pc.ontrack = (e) => {
      const stream = (e.streams && e.streams[0]) || new MediaStream([e.track]);
      if (e.track.kind === 'video') { attachRemoteScreen(pid, stream, e.track); return; }
      if (!p.audio) {
        const a = document.createElement('audio');
        a.autoplay = true; a.playsInline = true;
        document.getElementById('voice-audio').appendChild(a);
        p.audio = a;
      }
      p.audio.srcObject = stream;
      p.hasAudio = true;
      playPeerAudio(p);
      watchLevel(p, stream);
    };
    pc.onconnectionstatechange = () => {
      const st = pc.connectionState;
      p.state = (st === 'connected') ? 'на связи' : (st === 'connecting' ? 'связываемся' : st);
      if (st === 'failed') {
        // Одна попытка пересобрать маршрут: обрыв часто лечится этим сам.
        if (!p.retried && pc.restartIce) {
          p.retried = true; p.state = 'пересобираем связь';
          try { pc.restartIce(); } catch (e) {}
          boardHint('Связь с «' + p.label + '» оборвалась — пробуем ещё раз');
        } else {
          p.state = 'не удалось соединиться';
          boardHint(HAS_TURN
            ? ('С участником «' + p.label + '» не удалось соединиться')
            : ('С участником «' + p.label + '» нет прямой связи. На сервере не настроен ретранслятор (TURN) — без него примерно у каждого пятого домашний интернет прямую связь не пропускает'));
        }
      }
      if (st === 'closed') closePeer(pid);
      renderVoiceList();
    };

    if (voicePeers.size === MESH_SOFT_LIMIT) {
      boardHint('Участников много — на слабом интернете возможны заминки');
    }
    renderVoiceList();
    return p;
  }

  // Попытка включить звук собеседника. Отказ — не поломка: браузер запрещает
  // звук на странице, где человек ещё ничего не нажимал. Запоминаем это и
  // включаем с первого же щелчка по доске.
  function playPeerAudio(p) {
    if (!p.audio) return;
    const go = p.audio.play();
    if (go && go.catch) go.catch(() => {
      audioBlocked = true; p.needsClick = true;
      boardHint('Браузер не пускает звук — щёлкните по доске, чтобы услышать');
      renderVoiceList();
    });
  }
  document.addEventListener('click', () => {
    if (!audioBlocked) return;
    audioBlocked = false;
    voicePeers.forEach((p) => { p.needsClick = false; if (p.audio) { const g = p.audio.play(); if (g && g.catch) g.catch(() => {}); } });
    renderVoiceList();
  }, true);

  // Добавить/убрать дорожку у ВСЕХ собеседников. kind — 'mic' или 'screen',
  // чтобы потом снять именно её, не трогая остальные.
  function addTrackTo(p, track, stream, kind) {
    try {
      const s = p.pc.addTrack(track, stream);
      (p.senders[kind] = p.senders[kind] || []).push(s);
    } catch (e) { /* дорожка уже добавлена */ }
  }
  function addTrackEverywhere(track, stream, kind) {
    voicePeers.forEach((p) => addTrackTo(p, track, stream, kind));
  }
  function removeTracksEverywhere(kind) {
    voicePeers.forEach((p) => {
      (p.senders[kind] || []).forEach((s) => { try { p.pc.removeTrack(s); } catch (e) {} });
      p.senders[kind] = [];
    });
  }

  function closePeer(pid) {
    const p = voicePeers.get(pid); if (!p) return;
    try { p.pc.close(); } catch (e) {}
    if (p.audio) { try { p.audio.srcObject = null; } catch (e) {} p.audio.remove(); }
    voicePeers.delete(pid);
    dropRemoteScreen(pid);
    renderVoiceList();
  }
  function closeAllPeers() { Array.from(voicePeers.keys()).forEach(closePeer); }

  // Кандидаты сети могут прийти раньше описания связи — придерживаем их.
  function addIce(p, cand) {
    if (!p.pc.remoteDescription || !p.pc.remoteDescription.type) { p.pending.push(cand); return; }
    p.pc.addIceCandidate(new RTCIceCandidate(cand)).catch(() => {});
  }
  function flushIce(p) {
    const q = p.pending.splice(0, p.pending.length);
    q.forEach((c) => p.pc.addIceCandidate(new RTCIceCandidate(c)).catch(() => {}));
  }

  // Есть ли нам что передавать (голос или экран).
  function rtcSending() { return voiceOn || screenOn; }
  // Объявиться всем: «я готов к прямой связи». Соединение поднимется у всех,
  // кто это услышит, — даже если сами они ничего не передают, ведь принимать
  // показ экрана они должны.
  function rtcAnnounce() { rtcSend('ready', null, null); sendMicState(null); }
  // Сказать соседям (или одному), включён ли у нас микрофон. Без этого сосед,
  // который просто открыл доску и голос не включал, значился в списке «на
  // связи» — соединение-то есть, оно нужно и для показа экрана, — и было
  // непонятно, почему тишина.
  function sendMicState(to) { rtcSend('mic', to || null, { on: !!(voiceOn && !voiceMuted) }); }

  function handleRtc(m) {
    if (!m || !m.peer || m.peer === myPeer) return;
    if (m.to && m.to !== myPeer) return;          // сообщение адресовано не нам
    const pid = m.peer;

    if (m.kind === 'bye') { closePeer(pid); return; }
    if (m.kind === 'ready') {
      // На общий вызов отвечаем лично, чтобы собеседник узнал о нас. На личный
      // ответ уже не отвечаем — иначе получилась бы бесконечная перекличка.
      if (!m.to) rtcSend('ready', pid, null);
      ensurePeer(pid, m.label);
      sendMicState(pid);   // и сразу говорим, включён ли у нас микрофон
      return;
    }
    if (m.kind === 'mic') {
      const p0 = voicePeers.get(pid);
      if (p0) { p0.micOn = !!(m.data && m.data.on); renderVoiceList(); }
      return;
    }
    // Дальше — служебные сообщения переговоров. Отвечаем на них всегда: даже
    // если сами ничего не передаём, нам могут показывать экран.
    const p = ensurePeer(pid, m.label);
    if (!p) return;
    const pc = p.pc;

    if (m.kind === 'offer' || m.kind === 'answer') {
      const desc = m.data;
      const collision = (m.kind === 'offer') && (p.makingOffer || pc.signalingState !== 'stable');
      p.ignoreOffer = !p.polite && collision;
      if (p.ignoreOffer) return;                  // невежливый игнорирует чужое предложение
      // Ручного отката больше нет: приём чужого предложения откатывает своё
      // сам. Прежний откат вручную открывал окно, в которое успевал вклиниться
      // обработчик «нужны переговоры», и браузер отказывал.
      Promise.resolve()
        .then(() => pc.setRemoteDescription(new RTCSessionDescription(desc)))
        .then(() => {
          flushIce(p);
          if (m.kind !== 'offer') return null;
          return setLocalAuto(pc).then(() => sendLocalDesc(pid, pc));
        })
        .catch((e) => {
          // Молчать нельзя: именно проглоченная ошибка и прятала поломку.
          try { console.warn('голос: переговоры сорвались', e); } catch (_) {}
          p.state = 'ошибка связи'; renderVoiceList();
        });
      return;
    }
    if (m.kind === 'ice') addIce(p, m.data);
  }

  // ── Демонстрация экрана ────────────────────────────────────────────────
  // Показ живёт отдельно от голоса: можно показать экран молча. Картинка идёт
  // тем же прямым соединением, что и звук, а на доске появляется объект-экран,
  // который все могут двигать и растягивать.
  //
  // Сам объект синхронизируется как обычный (положение, размер), а картинка —
  // живой поток: она не хранится и не переживает перезагрузку у показывающего.
  let screenOn = false, screenStream = null, screenElId = null;
  const remoteScreens = new Map();   // peerId → MediaStream (пришедшая картинка)

  function screenSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia);
  }

  function startScreenShare() {
    if (screenOn) { stopScreenShare(); return; }
    if (!screenSupported()) {
      boardHint('Показ экрана недоступен: с телефона браузеры этого не умеют');
      return;
    }
    navigator.mediaDevices.getDisplayMedia({
      // Низкая частота кадров и высокое разрешение — ради ЧЁТКОГО ТЕКСТА.
      // По умолчанию браузер жертвует резкостью ради плавности, и мелкие буквы
      // расплываются; документу плавность не нужна.
      video: { frameRate: { ideal: 8, max: 15 }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: false,
    }).then((stream) => {
      screenStream = stream;
      screenOn = true;
      const track = stream.getVideoTracks()[0];
      if (track && 'contentHint' in track) track.contentHint = 'detail';   // резкость важнее плавности
      // Остановка кнопкой самого браузера — тоже конец показа.
      if (track) track.onended = () => stopScreenShare();

      addTrackEverywhere(track, stream, 'screen');
      rtcAnnounce();                       // поднять связь с теми, кого ещё нет
      createScreenElement(track);
      updateScreenUI();
      boardHint('Показ экрана включён — объект появился на доске');
    }).catch((err) => {
      const n = (err && err.name) || '';
      if (n !== 'NotAllowedError') boardHint('Не удалось начать показ экрана');
    });
  }

  function stopScreenShare() {
    if (!screenOn) return;
    screenOn = false;
    removeTracksEverywhere('screen');
    if (screenStream) { screenStream.getTracks().forEach((t) => { try { t.stop(); } catch (e) {} }); screenStream = null; }
    if (screenElId) {
      send({ action: 'element_delete', id: screenElId });
      removeNode(screenElId);
      screenElId = null;
    }
    if (!voiceOn) { rtcSend('bye', null, null); closeAllPeers(); }
    updateScreenUI();
    boardHint('Показ экрана выключен');
  }

  // Объект-экран на доске. Размер берём по пропорциям картинки.
  function createScreenElement(track) {
    const s = (track && track.getSettings) ? track.getSettings() : {};
    const ratio = (s.width && s.height) ? (s.width / s.height) : (16 / 9);
    const W = 640, H = Math.round(W / ratio);
    const p = viewportCenterWorld();
    const el = {
      id: uuid(), type: 'screen', z: 0,
      data: {
        x: p.x - W / 2, y: p.y - H / 2, width: W, height: H,
        ratio: ratio, by: myPeer, label: myLabel || 'участник',
      },
    };
    screenElId = el.id;
    upsertNode(el);
    send({ action: 'element_add', element: el });
  }

  // Картинка пришла от участника: показать её в его объекте-экране.
  function attachRemoteScreen(pid, stream, track) {
    remoteScreens.set(pid, stream);
    if (track) track.onended = () => dropRemoteScreen(pid);
    widgetItems.forEach((it) => {
      if (it.el.type === 'screen' && it.el.data.by === pid && it._video) bindScreenVideo(it);
    });
  }
  function dropRemoteScreen(pid) {
    remoteScreens.delete(pid);
    widgetItems.forEach((it) => {
      if (it.el.type === 'screen' && it.el.data.by === pid && it._render) it._render();
    });
  }
  function bindScreenVideo(it) {
    const d = it.el.data, v = it._video;
    if (!v) return;
    const mine = (d.by === myPeer);
    const stream = mine ? screenStream : remoteScreens.get(d.by);
    if (!stream) { it.wrapper.classList.add('waiting'); v.srcObject = null; return; }
    it.wrapper.classList.remove('waiting');
    if (v.srcObject !== stream) v.srcObject = stream;
    v.muted = true;                       // свой же звук обратно слушать не надо
    const go = v.play(); if (go && go.catch) go.catch(() => {});
  }

  function buildScreen(it) {
    const render = () => {
      const d = it.el.data;
      it.body.innerHTML = '<div class="scr-box"><video class="scr-video" playsinline autoplay muted></video>'
        + '<div class="scr-wait">Ожидаем картинку…</div>'
        + '<div class="scr-grip" title="Потяните — размер меняется пропорционально"></div></div>';
      const box = it.body.querySelector('.scr-box');
      it._video = it.body.querySelector('.scr-video');
      it.bar.querySelector('.wgt-title').textContent = 'Экран · ' + (d.label || 'участник');
      applyScreenSize();
      bindScreenVideo(it);
      wireGrip(it.body.querySelector('.scr-grip'));
      return box;
    };
    function applyScreenSize() {
      const d = it.el.data;
      const w = Math.max(200, d.width || 640);
      const h = Math.max(120, d.height || Math.round(w / (d.ratio || 16 / 9)));
      const box = it.body.querySelector('.scr-box');
      if (box) { box.style.width = w + 'px'; box.style.height = h + 'px'; }
      it.wrapper.style.width = w + 'px';
    }
    // Растягивание СТРОГО пропорционально: экран с искажёнными пропорциями
    // читается хуже, а пользы от произвольного размера нет.
    function wireGrip(grip) {
      if (!grip) return;
      grip.addEventListener('mousedown', (e) => {
        e.preventDefault(); e.stopPropagation();
        const d = it.el.data, s = stage.scaleX();
        const sx = e.clientX, w0 = d.width || 640;
        const ratio = d.ratio || (16 / 9);
        const before = clone(it.el);
        const mv = (ev) => {
          const w = Math.max(200, Math.round(w0 + (ev.clientX - sx) / s));
          d.width = w; d.height = Math.round(w / ratio);
          applyScreenSize();
        };
        const up = () => {
          document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up);
          syncWidget(it); histUpd(before, it.el); syncConnectorsOf([it.el.id]);
        };
        document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
      });
    }
    it._render = render;
    it.update = render;
    render();
  }

  function updateScreenUI() {
    const b = document.getElementById('screen-btn');
    if (b) { b.classList.toggle('on', screenOn); b.textContent = screenOn ? 'Остановить показ' : 'Показать экран'; }
    const t = document.querySelector('#board-toolbar .tool[data-tool="screen"]');
    if (t) t.classList.toggle('active', screenOn);
  }
  (function initScreenShare() {
    const b = document.getElementById('screen-btn');
    if (b) b.addEventListener('click', startScreenShare);
    window.addEventListener('pagehide', () => { if (screenOn) { try { stopScreenShare(); } catch (e) {} } });
    updateScreenUI();
  })();

  // ── Вход и выход из разговора ──────────────────────────────────────────
  // Почему не вышло взять микрофон. Отдельно назван самый частый у нас случай:
  // микрофон держит другое приложение (Zoom) — из общего «не удалось» человек
  // причину не понимал и не знал, что делать.
  function micErrText(err) {
    const name = (err && err.name) || '';
    if (name === 'NotAllowedError') return 'Доступ к микрофону запрещён — разрешите его в браузере';
    if (name === 'NotFoundError') return 'Микрофон не найден';
    if (name === 'NotReadableError' || name === 'AbortError') return 'Микрофон занят другим приложением (например, Zoom). Закройте его и нажмите «Переподключить микрофон»';
    return 'Не удалось включить микрофон';
  }
  const MIC_REQ = { audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false };
  // Общая настройка свежей дорожки: учитываем «выключен кнопкой» и замечаем,
  // когда устройство отняли (наушники вынули, приложение забрало) — дорожка
  // тогда кончается, и молчать об этом нельзя.
  function setupMicTrack(track) {
    if (!track) return;
    track.enabled = !voiceMuted;
    track.addEventListener('ended', () => {
      if (voiceOn) boardHint('Микрофон отключился — нажмите «Переподключить микрофон»');
    });
  }
  function voiceStart() {
    if (voiceOn) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      boardHint('Браузер не даёт доступ к микрофону (нужен https)');
      return;
    }
    navigator.mediaDevices.getUserMedia(MIC_REQ).then((stream) => {
      localStream = stream;
      voiceOn = true; voiceMuted = false;
      stream.getAudioTracks().forEach(setupMicTrack);
      watchLevel(localHolder, stream);
      startVoiceMeter();
      updateVoiceUI();
      localStream.getTracks().forEach((t) => addTrackEverywhere(t, localStream, 'mic'));
      rtcAnnounce();   // объявляемся всем, кто уже на связи
      boardHint('Вы в разговоре');
    }).catch((err) => boardHint(micErrText(err)));
  }
  // Взять микрофон ЗАНОВО, НЕ выходя из разговора. Ради этого всё и затевалось:
  // дорожка, взятая пока микрофон держал Zoom, звука не даёт и сама не оживает,
  // даже когда Zoom закрыли. Подменяем её у всех собеседников через
  // replaceTrack — связь при этом не пересогласуется и разговор не рвётся.
  function voiceReacquire() {
    if (!voiceOn) { boardHint('Сначала включите голос'); return; }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      boardHint('Браузер не даёт доступ к микрофону (нужен https)');
      return;
    }
    navigator.mediaDevices.getUserMedia(MIC_REQ).then((stream) => {
      const track = stream.getAudioTracks()[0];
      if (!track) { try { stream.getTracks().forEach((t) => t.stop()); } catch (e) {} boardHint('Микрофон не дал дорожку'); return; }
      setupMicTrack(track);
      voicePeers.forEach((p) => {
        const list = p.senders.mic || [];
        // Собеседнику, который подключился, когда дорожки ещё не было, её
        // просто добавляем — подменять там нечего.
        if (list.length) list.forEach((snd) => { try { snd.replaceTrack(track); } catch (e) {} });
        else addTrackTo(p, track, stream, 'mic');
      });
      if (localStream) localStream.getTracks().forEach((t) => { try { t.stop(); } catch (e) {} });
      localStream = stream;
      watchLevel(localHolder, stream);
      sendMicState(null);
      updateVoiceUI();
      boardHint('Микрофон переподключён');
    }).catch((err) => boardHint(micErrText(err)));
  }
  function voiceStop() {
    if (!voiceOn) return;
    voiceOn = false;             // чтобы соседям ушло честное «микрофон выключен»
    sendMicState(null);
    removeTracksEverywhere('mic');
    // Соединение рвём, только если и экран не показываем: иначе показ оборвётся.
    if (!screenOn) { rtcSend('bye', null, null); closeAllPeers(); }
    stopVoiceMeter();
    if (localStream) { localStream.getTracks().forEach((t) => { try { t.stop(); } catch (e) {} }); localStream = null; }
    localHolder.analyser = null; localHolder.speaking = false;
    voiceMuted = false;          // voiceOn сброшен в начале, до рассылки состояния
    updateVoiceUI();
    boardHint('Вы вышли из разговора');
  }
  function voiceToggleMute() {
    if (!voiceOn || !localStream) return;
    voiceMuted = !voiceMuted;
    localStream.getAudioTracks().forEach((t) => { t.enabled = !voiceMuted; });
    sendMicState(null);   // выключенный кнопкой микрофон по трафику неотличим от речи
    updateVoiceUI();
  }

  // ── Оформление ────────────────────────────────────────────────────────
  function updateVoiceUI() {
    const b = voiceBtn(), p = voicePanel();
    if (b) {
      b.classList.toggle('on', voiceOn);
      b.textContent = voiceOn ? (voiceMuted ? 'Голос (микрофон выкл.)' : 'Голос') : 'Голос';
    }
    if (p) p.hidden = !voiceOn;
    const mute = document.getElementById('vp-mute');
    if (mute) { mute.textContent = voiceMuted ? 'Включить микрофон' : 'Выключить микрофон'; mute.classList.toggle('off', voiceMuted); }
    renderVoiceList();
  }
  // Что написать про соседа. Соединение поднимается и у того, кто голос не
  // включал (оно нужно и для показа экрана), поэтому «на связи» само по себе
  // ничего не обещало: человек видел «на связи» и не понимал, почему тишина.
  function peerStateText(p) {
    if (p.needsClick) return 'щёлкните по доске, чтобы услышать';
    const st = p.pc ? p.pc.connectionState : '';
    if (st !== 'connected') return p.state || 'связываемся';
    // Состояние микрофона сосед сообщает сам (kind: 'mic'). Определять его по
    // принятой дорожке я пробовал — признак muted врёт: соединение принимало
    // сотни килобайт звука, а дорожка всё равно числилась заглушённой.
    if (p.micOn === false) return 'микрофон выключен';
    return 'на связи';
  }
  function renderVoiceList() {
    const box = document.getElementById('vp-list');
    if (!box || !voiceOn) return;
    let html = '<div class="vp-person' + (localHolder.speaking ? ' talking' : '') + '">'
      + '<span class="vp-dot"></span><span class="vp-name">Вы</span>'
      + '<span class="vp-state">' + (voiceMuted ? 'микрофон выкл.' : 'на связи') + '</span></div>';
    voicePeers.forEach((p) => {
      html += '<div class="vp-person' + (p.speaking ? ' talking' : '') + '">'
        + '<span class="vp-dot"></span><span class="vp-name">' + escapeHtml(p.label) + '</span>'
        + '<span class="vp-state">' + escapeHtml(peerStateText(p)) + '</span></div>';
    });
    if (!voicePeers.size) html += '<div class="vp-empty">Ждём, пока кто-нибудь тоже включит голос</div>';
    box.innerHTML = html;
  }

  (function initVoice() {
    const b = voiceBtn();
    if (b) b.addEventListener('click', () => { if (voiceOn) voiceStop(); else voiceStart(); });
    const mute = document.getElementById('vp-mute');
    if (mute) mute.addEventListener('click', voiceToggleMute);
    const leave = document.getElementById('vp-leave');
    if (leave) leave.addEventListener('click', voiceStop);
    const again = document.getElementById('vp-reacquire');
    if (again) again.addEventListener('click', voiceReacquire);
    // Уходим со страницы — вежливо прощаемся, чтобы у соседей не висел «мертвец».
    window.addEventListener('pagehide', () => { if (voiceOn) { try { rtcSend('bye', null, null); } catch (e) {} closeAllPeers(); } });
  })();

  // ── Связь по WebSocket ────────────────────────────────────────────────
  let ws = null;
  let lastCursorAt = 0;
  const connDot = document.getElementById('conn-dot');
  const peersEl = document.getElementById('peers');
  const peers = new Map(); // userId → label

  let reconnectDelay = 1000, reconnectTimer = null;
  // Сердцебиение: раз в 25 секунд шлём «ping», сервер отвечает «pong». Без
  // этого обмена молчаливое соединение закрывает посредник — nginx рвёт по
  // умолчанию через 60 секунд тишины, у мобильных операторов бывает и меньше.
  // 25 секунд выбраны с запасом: даже если один ответ потеряется, до предела
  // останется время на второй.
  const BEAT_MS = 25000;
  let beatTimer = null, lastCloseCode = 0;
  function startBeat() {
    stopBeat();
    beatTimer = setInterval(() => {
      if (!ws || ws.readyState !== 1) return;
      try { ws.send(JSON.stringify({ action: 'ping' })); } catch (e) {}
    }, BEAT_MS);
  }
  function stopBeat() { if (beatTimer) { clearInterval(beatTimer); beatTimer = null; } }
  let connBanner = null;
  const pendingOps = []; // правки, сделанные при разрыве связи — досылаем при реконнекте
  function setConnState(online) {
    if (connDot) {
      connDot.classList.toggle('online', online);
      // Код закрытия виден в подсказке: 1006 — оборвал посредник (таймаут сети),
      // 1001 — ушли со страницы, 1011 — упал сервер. Без кода причину не найти.
      connDot.title = online ? 'Связь есть'
        : ('Связь потеряна — переподключаемся…' + (lastCloseCode ? ' (код ' + lastCloseCode + ')' : ''));
    }
    if (online) { if (connBanner) connBanner.style.display = 'none'; }
    else {
      if (!connBanner) { connBanner = document.createElement('div'); connBanner.id = 'conn-banner'; connBanner.textContent = 'Связь потеряна — переподключаемся…'; document.body.appendChild(connBanner); }
      connBanner.style.display = 'block';
    }
  }
  function scheduleReconnect() {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(15000, Math.round(reconnectDelay * 1.7)); // бэкофф до 15с
  }
  function connect() {
    if (iAmRemoved) return;
    clearTimeout(reconnectTimer);
    const url = cfg.wsScheme + '://' + location.host + '/ws/board/' + cfg.code + '/';
    try { ws = new WebSocket(url); } catch (e) { scheduleReconnect(); return; }
    ws.onopen = () => { reconnectDelay = 1000; setConnState(true); startBeat(); };
    ws.onclose = (ev) => {
      stopBeat();
      lastCloseCode = (ev && ev.code) || 0;
      setConnState(false);
      // 4403 — сервер отказал в доступе (убрали с доски или её удалили).
      // Переподключаться бессмысленно: молча стучались бы вечно.
      if (iAmRemoved || (ev && ev.code === 4403)) { clearTimeout(reconnectTimer); return; }
      scheduleReconnect();
    };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
    ws.onmessage = (ev) => { let m; try { m = JSON.parse(ev.data); } catch (e) { return; } handleMessage(m); };
  }
  // Мгновенный реконнект при возврате сети/вкладки (не ждём таймер бэкоффа).
  window.addEventListener('online', () => { reconnectDelay = 1000; if (!ws || ws.readyState > 1) connect(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && (!ws || ws.readyState > 1)) { reconnectDelay = 1000; connect(); } });

  const PERSIST_ACTIONS = { element_add: 1, element_update: 1, element_delete: 1 };
  function send(obj) {
    // Наблюдатель не шлёт правки — сервер их всё равно отклонит; так чище и без
    // лишнего трафика (UI правок у наблюдателя и так заблокирован ролью).
    if ((roleViewer || iAmRemoved) && obj && PERSIST_ACTIONS[obj.action]) return;
    if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify(obj)); return; }
    // Оффлайн: копим правки холста, чтобы не потерять (курсоры/лазер/вид — эфемерные, не копим).
    if (obj && PERSIST_ACTIONS[obj.action]) queueOp(obj);
  }
  function queueOp(obj) {
    const id = obj.id || (obj.element && obj.element.id);
    if (id) {
      if (obj.action === 'element_delete') {
        for (let i = pendingOps.length - 1; i >= 0; i--) { const o = pendingOps[i]; if ((o.id || (o.element && o.element.id)) === id) pendingOps.splice(i, 1); }
      } else {
        const idx = pendingOps.findIndex((o) => o.action !== 'element_delete' && o.element && o.element.id === id);
        if (idx >= 0) { pendingOps[idx] = obj; return; } // заменяем прежнюю правку того же элемента
      }
    }
    pendingOps.push(obj);
    if (pendingOps.length > 5000) pendingOps.shift();
  }
  // Досылаем накопленное ЧАСТЯМИ. Сервер принимает не больше 250 сообщений в
  // секунду и лишнее молча отбрасывает: залп из тысяч правок после долгой
  // работы без сети означал бы тихую потерю части нарисованного.
  const FLUSH_CHUNK = 100, FLUSH_PAUSE = 500;   // 200 сообщений/сек — с запасом
  let flushTimer = null;
  function flushPending() {
    clearTimeout(flushTimer);
    if (!pendingOps.length || !ws || ws.readyState !== WebSocket.OPEN) return;
    const q = pendingOps.splice(0, FLUSH_CHUNK);
    q.forEach((o) => { try { ws.send(JSON.stringify(o)); } catch (e) { pendingOps.unshift(o); } });
    if (pendingOps.length) flushTimer = setTimeout(flushPending, FLUSH_PAUSE);
  }

  function sendCursor() {
    const now = Date.now();
    if (now - lastCursorAt < 40) return;
    lastCursorAt = now;
    const p = worldPoint();
    send({ action: 'cursor', x: p.x, y: p.y });
  }

  function handleMessage(msg) {
    switch (msg.action) {
      // Сервер не принял объект. Прежде он в таких случаях просто молчал, и
      // человек узнавал о потере только после перезагрузки страницы.
      case 'rejected':
        boardHint(msg.reason === 'too_big'
          ? 'Объект слишком большой — сервер его не сохранил'
          : (msg.reason === 'too_fast'
            ? 'Слишком много правок разом — часть не прошла. Обновите страницу, чтобы свериться с соседом'
            : 'Сервер не принял изменение'));
        return;
      case 'pong': break;   // сердцебиение: ответ получен, соединение живо
      case 'init':
        myId = msg.me;
        myLabel = msg.label || myLabel;
        // Новый id соединения: прежние голосовые связи к нему уже не относятся.
        if (myPeer && myPeer !== msg.peer) closeAllPeers();
        myPeer = msg.peer || null;
        if (rtcSending()) rtcAnnounce();   // после переподключения объявляемся заново
        boardIsOwner = !!msg.is_owner;
        boardDefaultRole = msg.default_role || 'editor';
        boardRoles = msg.roles || {};
        boardRemoved = msg.removed || [];
        (msg.elements || []).forEach(upsertNode);
        // Состояние доски приходит порциями: пересчитывать геометрию и ехать по
        // якорю есть смысл только когда пришла последняя.
        if (!msg.more) finishInit();
        applyMyRole();   // он же перерисует панель участников
        // Переподключение: у соседей наши договорённости о видах не сохранились
        // (они живут только в памяти вкладки), поэтому объявляем их заново —
        // иначе «следовать» после обрыва связи тихо переставало работать.
        if (followUid !== null) sendViewLink('follow', followUid, true);
        if (leadAll) sendViewLink('lead', 'all', true);
        leadUids.forEach((u) => sendViewLink('lead', u, true));
        boardHistory = msg.history || [];
        if (historyOpen()) renderHistory();
        flushPending(); // досылаем правки, накопленные в оффлайне (при переподключении)
        break;
      case 'init_more':
        (msg.elements || []).forEach(upsertNode);
        if (msg.done) finishInit();
        break;
      case 'history':
        applyHistoryEntry(msg.entry);
        break;
      case 'members_update':
        boardRoles = msg.roles || {};
        boardRemoved = msg.removed || [];
        if (msg.kicked && String(msg.target) === String(myId)) { showRemovedFromBoard(); break; }
        if (msg.kicked) { peers.delete(Number(msg.target)); peers.delete(msg.target); removeCursor(msg.target); forgetViewLinks(msg.target); renderPeers(); }
        applyMyRole();   // он же перерисует панель участников
        break;
      case 'rtc':
        handleRtc(msg);
        break;
      case 'roles_update':
        boardDefaultRole = msg.default_role || boardDefaultRole;
        boardRoles = msg.roles || {};
        applyMyRole();   // он же перерисует панель участников
        break;
      case 'element_add':
      case 'element_update':
        upsertNode(msg.element);
        break;
      case 'element_delete':
        removeNode(msg.id);
        break;
      case 'cursor':
        showRemoteCursor(msg.user, msg.label, msg.x, msg.y);
        if (msg.user !== myId && !peers.has(msg.user)) {
          peers.set(msg.user, msg.label); renderPeers();
        }
        break;
      case 'presence':
        if ((msg.event === 'join' || msg.event === 'here') && msg.user !== myId) {
          peers.set(msg.user, msg.label); renderPeers();
        }
        if (msg.event === 'join' && msg.user !== myId) {
          // Отзываемся, чтобы вошедший узнал, что мы здесь: сам он об этом
          // ниоткуда не узнаёт — сообщение о входе рассылается только в момент
          // входа, и пришедший вторым не видел никого.
          send({ action: 'hello' });
          // Если мы уже в разговоре или показываем экран — объявляемся и ему.
          // Раньше объявление уходило только в момент включения голоса, и
          // вошедший позже про разговор не знал вовсе.
          if (rtcSending()) rtcAnnounce();
          // Вошедший не слышал прежнего «веду всех»: объявляем заново,
          // иначе он один остался бы со своим видом. То же и для поимённого
          // ведения: у человека могла просто моргнуть связь, и возвращаться он
          // должен туда же, куда его вели.
          if (leadAll) { sendViewLink('lead', 'all', true); sendView(); }
          else if (leadUids.has(String(msg.user)) || leadPending.delete(String(msg.user))) {
            leadUids.add(String(msg.user));
            sendViewLink('lead', msg.user, true); sendView();
          }
        }
        if (msg.event === 'leave') { peers.delete(msg.user); removeCursor(msg.user); laserTrails.delete(msg.user); forgetViewLinks(msg.user); if (msg.peer) { closePeer(msg.peer); dropRemoteScreen(msg.peer);
          // Показывающий ушёл — объект-экран без картинки не нужен.
          elements.forEach((el) => { if (el.type === 'screen' && el.data.by === msg.peer) { send({ action: 'element_delete', id: el.id }); removeNode(el.id); } }); } renderPeers(); }
        break;
      case 'laser':
        if (msg.user !== myId) addLaserPoint(msg.user, msg.x, msg.y, !!msg.s);
        break;
      case 'view':
        if (msg.user !== myId) applyView(msg.user, msg.x, msg.y, msg.scale);
        break;
      case 'viewlink':
        if (msg.user !== myId) onViewLink(msg);
        break;
    }
  }

  // Владелец убрал нас с доски: запираем правки, показываем объяснение и
  // прекращаем попытки переподключиться (иначе клиент вечно стучался бы в дверь,
  // на которую ему уже не откроют).
  function showRemovedFromBoard() {
    iAmRemoved = true;
    try { if (ws) ws.close(); } catch (e) {}
    clearTimeout(reconnectTimer);
    setViewOnly(true);
    if (!connBanner) { connBanner = document.createElement('div'); connBanner.id = 'conn-banner'; document.body.appendChild(connBanner); }
    connBanner.textContent = 'Владелец убрал вас с доски. Если вернёт — обновите страницу';
    connBanner.style.display = 'block';
  }

  function renderPeers() {
    if (peers.size === 0) { peersEl.textContent = ''; }
    else peersEl.textContent = '· с вами: ' + Array.from(peers.values()).join(', ');
    renderPeoplePanel(); syncPeopleBtn();
  }

  // ── Панель инструментов для телефона и планшета ────────────────────────
  // Лист собирается из ТОЙ ЖЕ панели, что и на компьютере: кнопки копируются, а
  // клик переадресуется оригиналу. Значит, любой инструмент, добавленный в
  // разметку панели, появится и здесь — дублировать логику не нужно.
  const mobSheet = document.getElementById('mobile-sheet');
  const mobFab = document.getElementById('mobile-fab');
  const mobBackdrop = document.getElementById('mobile-backdrop');
  const FAB_PLUS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';

  function closeMobileSheet() {
    if (!mobSheet) return;
    mobSheet.classList.remove('open');
    if (mobBackdrop) mobBackdrop.hidden = true;
    if (mobFab) mobFab.classList.remove('on');
  }
  function openMobileSheet() {
    if (!mobSheet) return;
    syncMobileSheetActive();
    mobSheet.classList.add('open');
    if (mobBackdrop) mobBackdrop.hidden = false;
    if (mobFab) mobFab.classList.add('on');
  }
  function toggleMobileSheet() {
    if (!mobSheet) return;
    if (mobSheet.classList.contains('open')) closeMobileSheet(); else openMobileSheet();
  }
  // Подсветка выбранного инструмента в листе.
  function syncMobileSheetActive() {
    if (!mobSheet) return;
    mobSheet.querySelectorAll('.ms-item[data-tool]').forEach((b) => {
      b.classList.toggle('active', b.dataset.tool === tool);
    });
  }
  // На кнопке «+» показываем значок текущего инструмента — видно, чем рисуешь,
  // не открывая лист.
  function syncMobileFab() {
    if (!mobFab) return;
    syncMobileSheetActive();
    const src = document.querySelector('#board-toolbar .tool[data-tool="' + tool + '"] svg');
    mobFab.innerHTML = src ? src.outerHTML : FAB_PLUS;
  }

  (function buildMobileSheet() {
    const bar = document.getElementById('board-toolbar');
    const body = mobSheet && mobSheet.querySelector('.ms-body');
    if (!bar || !body) return;

    function mkItem(src, caption) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'ms-item';
      if (src.dataset.tool) b.dataset.tool = src.dataset.tool;
      const svg = src.querySelector('svg');
      b.innerHTML = svg ? svg.outerHTML : '';
      const cap = document.createElement('span');
      cap.className = 'ms-cap';
      cap.textContent = caption || toolShortTitle(src) || (src.textContent || '').trim();
      b.appendChild(cap);
      b.title = src.getAttribute('title') || cap.textContent;
      // Клик переадресуем оригиналу — вся прежняя логика остаётся на месте.
      b.addEventListener('click', () => { src.click(); closeMobileSheet(); });
      return b;
    }
    function mkSection(label) {
      const sec = document.createElement('div');
      sec.className = 'ms-sec';
      const l = document.createElement('div');
      l.className = 'ms-sec-lbl';
      l.textContent = label;
      const g = document.createElement('div');
      g.className = 'ms-grid';
      sec.appendChild(l); sec.appendChild(g);
      body.appendChild(sec);
      return g;
    }

    // 1. Инструменты — по группам исходной панели.
    Array.from(bar.children).forEach((child) => {
      if (!child.classList) return;
      // Скрытый раздел панели не должен всплывать в мобильном листе: лист
      // собирается из живой разметки, но про hidden сам не знает и дал бы
      // пустой заголовок.
      if (child.hidden) return;
      if (child.classList.contains('tool-group')) {
        const fly = child.querySelector('.tool-flyout');
        if (!fly) return;
        const subs = fly.querySelectorAll('.flyout-section');
        if (subs.length) {
          // Например, «Математика»: у неё внутри свои подписанные разделы.
          subs.forEach((sub) => {
            const lbl = sub.querySelector('.flyout-label');
            const grid = mkSection(toolShortTitle(child) + ' · ' + ((lbl && lbl.textContent.trim()) || ''));
            sub.querySelectorAll('.tool[data-tool]').forEach((t) => grid.appendChild(mkItem(t)));
          });
        } else {
          const grid = mkSection(toolShortTitle(child));
          fly.querySelectorAll('.tool[data-tool]').forEach((t) => grid.appendChild(mkItem(t)));
        }
      }
    });

    // 2. Выделение и действия (отмена/повтор/очистка) — прямые кнопки панели.
    const actGrid = mkSection('Действия');
    bar.querySelectorAll(':scope > .tool[data-tool], :scope > .tool[data-action]').forEach((t) => {
      actGrid.appendChild(mkItem(t));
    });

    // 3. Занятие: кнопки верхней плашки, которым не хватает места на узком экране.
    // «Участники» сюда не дублируем: эта кнопка теперь видна в плашке и на
    // узком экране — вести и следовать нужны как раз на планшете.
    const topIds = ['import-btn', 'reveal-hidden'];
    const liveGrid = mkSection('Занятие');
    topIds.forEach((id) => {
      const src = document.getElementById(id);
      if (!src) return;
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'ms-item';
      b.innerHTML = '<span class="ms-cap">' + escapeHtml((src.textContent || '').trim()) + '</span>';
      b.title = src.getAttribute('title') || '';
      b.addEventListener('click', () => { src.click(); closeMobileSheet(); });
      b.dataset.mirrors = id;   // чтобы подсвечивать включённые режимы
      liveGrid.appendChild(b);
    });

    // 4. Цвет и толщина — переиспользуем существующие элементы управления.
    const styleSec = document.createElement('div');
    styleSec.className = 'ms-sec';
    styleSec.innerHTML = '<div class="ms-sec-lbl">Цвет и толщина</div>';
    const row = document.createElement('div');
    row.className = 'ms-wide';
    const colorBtn = document.getElementById('color-btn');
    const sw = document.createElement('button');
    sw.type = 'button'; sw.className = 'ms-swatch';
    sw.title = 'Цвет';
    function syncSwatch() { if (colorBtn) sw.style.background = colorBtn.style.background || '#1f2937'; }
    syncSwatch();
    sw.addEventListener('click', () => { closeMobileSheet(); if (colorBtn) colorBtn.click(); });
    // Ползунок толщины ведёт к настоящему полю настроек пера (#dp-thick).
    // Раньше он искал #stroke-width — поля с таким именем в разметке нет уже
    // давно, обработчик выходил на первой же строке, и на планшете ползунок
    // двигался вхолостую. Границы и шаг копируем с оригинала, иначе новую
    // тонкую единицу 1.5 через него было бы не выставить.
    const widthSrc = document.getElementById('dp-thick');
    const rng = document.createElement('input');
    rng.type = 'range';
    rng.min = widthSrc ? widthSrc.min : '0.5';
    rng.max = widthSrc ? widthSrc.max : '24';
    rng.step = widthSrc ? (widthSrc.step || '0.5') : '0.5';
    rng.title = 'Толщина';
    rng.value = widthSrc ? widthSrc.value : '3';
    rng.addEventListener('input', () => {
      if (!widthSrc) return;
      widthSrc.value = rng.value;
      widthSrc.dispatchEvent(new Event('input', { bubbles: true }));
    });
    row.appendChild(sw); row.appendChild(rng);
    styleSec.appendChild(row);
    const hint = document.createElement('div');
    hint.className = 'ms-hint';
    hint.textContent = 'Инструмент можно не только нажать, но и перетащить прямо на доску.';
    styleSec.appendChild(hint);
    body.appendChild(styleSec);

    // Перетаскивание на холст работает и отсюда — тем же кодом, что на компьютере.
    enableToolDragToCanvas(mobSheet);

    if (mobFab) mobFab.addEventListener('click', toggleMobileSheet);
    if (mobBackdrop) mobBackdrop.addEventListener('click', closeMobileSheet);
    const closeBtn = mobSheet.querySelector('.ms-close');
    if (closeBtn) closeBtn.addEventListener('click', closeMobileSheet);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMobileSheet(); });
    // Свайп вниз по «ручке» — закрыть лист.
    const grip = mobSheet.querySelector('.ms-grip');
    if (grip) {
      let y0 = null;
      grip.addEventListener('pointerdown', (e) => { y0 = e.clientY; });
      grip.addEventListener('pointerup', (e) => { if (y0 != null && e.clientY - y0 > 24) closeMobileSheet(); y0 = null; });
    }
    syncMobileFab();
  })();

  // ── Старт ─────────────────────────────────────────────────────────────
  setTool('pen');
  redrawGrid();
  updateDebug();
  connect();
})();
