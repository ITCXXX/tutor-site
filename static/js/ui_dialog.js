/*
 * Экранные окна вместо системных alert / confirm / prompt.
 *
 * Системное окно браузера подписано «Сайт localhost сообщает…», выглядит
 * чужеродно и на телефоне занимает пол-экрана; ученик читает не текст, а
 * предупреждение браузера. Свои окна — в оформлении сайта, на его цветах.
 *
 * Впервые появились на доске (static/board/board.js) и жили внутри неё.
 * Вынесены сюда, чтобы второй такой же не пришлось писать заново.
 *
 * Возвращают промис:
 *     Диалог.подтвердить('Удалить карточку?', {опасно: true}) → true / false
 *     Диалог.сообщить('Не получилось сохранить')             → true
 *     Диалог.спросить('Вставьте список', '', {многострочно: true}) → строка / null
 */
(function (window) {
    'use strict';

    function окно(настройки) {
        return new Promise(function (готово) {
            var фон = document.createElement('div');
            фон.className = 'ui-dialog-back';

            var карточка = document.createElement('div');
            карточка.className = 'ui-dialog';
            карточка.setAttribute('role', 'dialog');
            карточка.setAttribute('aria-modal', 'true');

            if (настройки.заголовок) {
                var шапка = document.createElement('div');
                шапка.className = 'ui-dialog-title';
                шапка.textContent = настройки.заголовок;
                карточка.appendChild(шапка);
            }
            if (настройки.текст) {
                var текст = document.createElement('div');
                текст.className = 'ui-dialog-msg';
                текст.textContent = настройки.текст;
                карточка.appendChild(текст);
            }

            var поле = null;
            if (настройки.вид === 'ввод') {
                поле = document.createElement(настройки.многострочно ? 'textarea' : 'input');
                поле.className = 'ui-dialog-input';
                if (!настройки.многострочно) { поле.type = 'text'; }
                поле.value = настройки.начальное != null ? String(настройки.начальное) : '';
                if (настройки.подпись) { поле.placeholder = настройки.подпись; }
                карточка.appendChild(поле);
            }

            var кнопки = document.createElement('div');
            кнопки.className = 'ui-dialog-btns';
            var отмена = null;
            if (настройки.вид !== 'сообщение') {
                отмена = document.createElement('button');
                отмена.type = 'button';
                отмена.className = 'ui-dialog-btn';
                отмена.textContent = настройки.отменаТекст || 'Отмена';
                кнопки.appendChild(отмена);
            }
            var согласие = document.createElement('button');
            согласие.type = 'button';
            согласие.className = 'ui-dialog-btn primary' + (настройки.опасно ? ' danger' : '');
            согласие.textContent = настройки.окТекст || 'ОК';
            кнопки.appendChild(согласие);
            карточка.appendChild(кнопки);

            фон.appendChild(карточка);
            document.body.appendChild(фон);

            var былВФокусе = document.activeElement;

            function да() { return настройки.вид === 'ввод' ? (поле ? поле.value : '') : true; }
            function нет() { return настройки.вид === 'ввод' ? null : false; }

            function закрыть(значение) {
                document.removeEventListener('keydown', поКлавише, true);
                if (фон.parentNode) { фон.remove(); }
                if (былВФокусе && былВФокусе.focus) { былВФокусе.focus(); }
                готово(значение);
            }

            согласие.addEventListener('click', function () { закрыть(да()); });
            if (отмена) { отмена.addEventListener('click', function () { закрыть(нет()); }); }
            фон.addEventListener('mousedown', function (e) {
                if (e.target === фон) { закрыть(нет()); }
            });

            // Клавиши ловим в фазе перехвата и гасим: иначе Enter и Escape
            // уйдут в горячие клавиши страницы под окном — на экране повторения
            // Enter раскрывает карточку, и она раскрылась бы прямо под окном.
            function поКлавише(e) {
                if (e.key === 'Escape') {
                    e.preventDefault(); e.stopPropagation(); закрыть(нет());
                } else if (e.key === 'Enter'
                           && !(настройки.вид === 'ввод' && настройки.многострочно)) {
                    e.preventDefault(); e.stopPropagation(); закрыть(да());
                }
            }
            document.addEventListener('keydown', поКлавише, true);

            setTimeout(function () {
                if (поле) { поле.focus(); if (поле.select) { поле.select(); } }
                else { согласие.focus(); }
            }, 30);
        });
    }

    window.Диалог = {
        сообщить: function (текст, настройки) {
            настройки = настройки || {};
            return окно({вид: 'сообщение', текст: текст, заголовок: настройки.заголовок,
                         окТекст: настройки.ок});
        },
        подтвердить: function (текст, настройки) {
            настройки = настройки || {};
            return окно({вид: 'вопрос', текст: текст, заголовок: настройки.заголовок,
                         окТекст: настройки.ок, отменаТекст: настройки.отмена,
                         опасно: настройки.опасно});
        },
        спросить: function (текст, начальное, настройки) {
            настройки = настройки || {};
            return окно({вид: 'ввод', текст: текст, начальное: начальное,
                         заголовок: настройки.заголовок, подпись: настройки.подпись,
                         многострочно: настройки.многострочно,
                         окТекст: настройки.ок, отменаТекст: настройки.отмена});
        },
    };

    /*
     * Формы с подтверждением: вместо onsubmit="return confirm(...)" достаточно
     * атрибута data-спросить. Так подтверждение не приходится расписывать в
     * каждом шаблоне, и ни одно не останется системным по недосмотру.
     */
    document.addEventListener('submit', function (e) {
        var форма = e.target;
        if (!форма.dataset || !форма.dataset.спросить || форма.dataset.подтверждено) { return; }
        e.preventDefault();
        window.Диалог.подтвердить(форма.dataset.спросить, {
            опасно: форма.dataset.опасно !== undefined,
            ок: форма.dataset.окТекст || 'Удалить',
        }).then(function (да) {
            if (!да) { return; }
            форма.dataset.подтверждено = '1';
            форма.submit();
        });
    }, true);
})(window);
