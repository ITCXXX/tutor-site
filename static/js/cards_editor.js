/*
 * Визуальный редактор колоды: строки карточек и форматирование текста.
 *
 * Форматирование делает document.execCommand. Он давно помечен устаревшим, но
 * поддержан всеми браузерами и решает задачу в одну строку; замена ему —
 * ручная возня с Range и Selection на несколько сотен строк, которая на
 * выделении из двух абзацев ведёт себя хуже. Разметку, которую он выдаёт,
 * сервер всё равно приводит к своему узкому списку (cards/richtext.py),
 * поэтому разнобой между браузерами до базы не доходит.
 */
(function () {
    'use strict';

    var корень = document.getElementById('редактор');
    if (!корень) { return; }

    var список = document.getElementById('карточки');
    var шаблон = document.getElementById('шаблон-строки');
    var поле = document.getElementById('поле-карточек');
    var форма = document.getElementById('форма-колоды');
    var счётчик = document.getElementById('счётчик-карточек');
    var последнее = null;          // куда применять форматирование

    /* ── Строки ──────────────────────────────────────────────────────── */

    function добавить(данные, поставитьКурсор) {
        var строка = шаблон.content.firstElementChild.cloneNode(true);
        данные = данные || {};
        if (данные.id) { строка.dataset.id = данные.id; }
        строка.querySelector('[data-поле="front"]').innerHTML = данные.front || '';
        строка.querySelector('[data-поле="back"]').innerHTML = данные.back || '';
        строка.querySelector('[data-поле="hint"]').innerHTML = данные.hint || '';
        список.appendChild(строка);
        обновитьНомера();
        запомнить();
        if (поставитьКурсор) {
            строка.querySelector('[data-поле="front"]').focus();
            строка.scrollIntoView({block: 'nearest'});
        }
        return строка;
    }

    function обновитьНомера() {
        var строки = список.querySelectorAll('.карточка-строка');
        for (var i = 0; i < строки.length; i++) {
            строки[i].querySelector('.номер').textContent = i + 1;
        }
        счётчик.textContent = строки.length;
    }

    function собрать() {
        var итог = [];
        var строки = список.querySelectorAll('.карточка-строка');
        for (var i = 0; i < строки.length; i++) {
            var строка = строки[i];
            var лицо = строка.querySelector('[data-поле="front"]').innerHTML.trim();
            var оборот = строка.querySelector('[data-поле="back"]').innerHTML.trim();
            var подсказка = строка.querySelector('[data-поле="hint"]').innerHTML.trim();
            if (!голый(лицо) && !голый(оборот)) { continue; }
            итог.push({
                id: строка.dataset.id ? parseInt(строка.dataset.id, 10) : null,
                front: лицо, back: оборот, hint: подсказка
            });
        }
        return итог;
    }

    // Текст без разметки: строка из одних тегов и пробелов — пустая.
    function голый(html) {
        var времянка = document.createElement('div');
        времянка.innerHTML = html;
        return (времянка.textContent || '').trim();
    }

    /* ── Форматирование ──────────────────────────────────────────────── */

    // Запоминаем последнее редактируемое поле: нажатие на кнопку панели
    // снимает выделение, и без этого форматировать было бы нечего.
    список.addEventListener('focusin', function (e) {
        if (e.target.classList.contains('поле-текста')) { последнее = e.target; }
    });

    // Начертание просим тегами, цвет — через style. Со styleWithCSS жирный
    // выходит как «<span style="font-weight: bold">», а из свойств оформления
    // сервер оставляет только цвета — начертание пропало бы при сохранении.
    var ЧЕРЕЗ_СТИЛЬ = {foreColor: true, hiliteColor: true, backColor: true};

    function применить(команда, значение) {
        if (!последнее) { return; }
        последнее.focus();
        try {
            document.execCommand('styleWithCSS', false, !!ЧЕРЕЗ_СТИЛЬ[команда]);
            document.execCommand(команда, false, значение || null);
        } catch (e) { /* браузер не умеет — молча ничего не делаем */ }
    }

    корень.querySelectorAll('[data-команда]').forEach(function (кнопка) {
        // mousedown вместо click: иначе поле теряет выделение раньше, чем мы
        // успеем применить команду.
        кнопка.addEventListener('mousedown', function (e) {
            e.preventDefault();
            применить(кнопка.dataset.команда, кнопка.dataset.значение);
        });
    });

    /* ── Кнопки строк ────────────────────────────────────────────────── */

    список.addEventListener('click', function (e) {
        var удалить = e.target.closest('.удалить-строку');
        if (удалить) {
            var строка = удалить.closest('.карточка-строка');
            if (голый(строка.querySelector('[data-поле="front"]').innerHTML) ||
                голый(строка.querySelector('[data-поле="back"]').innerHTML)) {
                if (!confirm('Удалить карточку?')) { return; }
            }
            строка.remove();
            обновитьНомера();
            запомнить();
        }
    });

    document.getElementById('кнопка-добавить').addEventListener('click', function () {
        добавить({}, true);
    });

    // Enter в поле — не перевод строки, а переход к следующему полю: карточка
    // почти всегда однострочная, а многострочную можно набрать через Shift+Enter.
    список.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' || e.shiftKey) { return; }
        if (!e.target.classList.contains('поле-текста')) { return; }
        e.preventDefault();
        var строка = e.target.closest('.карточка-строка');
        if (e.target.dataset.поле === 'front') {
            строка.querySelector('[data-поле="back"]').focus();
        } else {
            var следующая = строка.nextElementSibling;
            if (следующая) { следующая.querySelector('[data-поле="front"]').focus(); }
            else { добавить({}, true); }
        }
    });

    /* ── Вставка и отправка ──────────────────────────────────────────── */

    // Вставляем как текст: иначе из буфера приезжает вся вёрстка страницы,
    // откуда копировали, и сервер потом выбрасывает её целиком.
    список.addEventListener('paste', function (e) {
        if (!e.target.classList.contains('поле-текста')) { return; }
        e.preventDefault();
        var текст = (e.clipboardData || window.clipboardData).getData('text/plain');
        document.execCommand('insertText', false, текст);
    });

    /*
     * Скрытое поле держим в согласии с редактором постоянно, а не собираем в
     * последний момент. Отправка формы бывает не только по кнопке — её делает
     * и Enter в заголовке, и восстановление вкладки браузером, — а событие
     * submit при этом может не дойти. Собранное заранее переживает все эти пути.
     */
    function запомнить() {
        поле.value = JSON.stringify(собрать());
    }

    список.addEventListener('input', запомнить);
    список.addEventListener('blur', запомнить, true);
    форма.addEventListener('submit', запомнить);

    /* ── Запуск ──────────────────────────────────────────────────────── */

    var начальные = JSON.parse(document.getElementById('начальные').textContent);
    начальные.forEach(function (к) { добавить(к, false); });
    // Пустая колода открывается с тремя строками — чтобы было видно, что
    // делать, и не пришлось искать плюс.
    var сколько = Math.max(0, 3 - начальные.length);
    for (var i = 0; i < сколько; i++) { добавить({}, false); }
    обновитьНомера();
})();
