/*
 * Service worker сайта. Отдаётся Django из корня (см. users/views_pwa.py),
 * поэтому управляет всеми адресами, а не только папкой статики.
 *
 * Что он делает и чего намеренно не делает:
 *
 * — Оболочку (CSS, скрипты, MathJax) кладёт в кэш при установке и дальше берёт
 *   оттуда. Это и ускоряет открытие, и даёт формулам рисоваться без сети.
 * — Страницы забирает сначала из сети и лишь при неудаче достаёт из кэша.
 *   Наоборот делать нельзя: ученик увидел бы вчерашнюю очередь повторений и
 *   не понял бы, почему карточки не кончаются.
 * — POST не трогает вовсе. Ответы на карточки уходят на сервер как есть, а
 *   когда сети нет, их придерживает сама страница повторения — она знает про
 *   очередь, а service worker не знает.
 */

const ВЕРСИЯ = '{{ версия|escapejs }}';
const КЭШ_ОБОЛОЧКИ = 'оболочка-' + ВЕРСИЯ;
const КЭШ_СТРАНИЦ = 'страницы-' + ВЕРСИЯ;
const ОФЛАЙН = {{ офлайн_json|safe }};

const ОБОЛОЧКА = {{ оболочка_json|safe }};

// Разделы, которые в кэш не попадают никогда: админка меняет данные, медиа
// весит гигабайты, доска живёт на веб-сокетах и от кэша только ломается.
const МИМО = ['/admin/', '/media/', '/board/', '/ws/'];

self.addEventListener('install', function (событие) {
    событие.waitUntil(
        caches.open(КЭШ_ОБОЛОЧКИ)
            .then(function (кэш) { return кэш.addAll(ОБОЛОЧКА); })
            // Один недоступный файл не должен отменять установку целиком.
            .catch(function () { return null; })
            .then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function (событие) {
    событие.waitUntil(
        caches.keys().then(function (имена) {
            return Promise.all(имена.map(function (имя) {
                if (имя !== КЭШ_ОБОЛОЧКИ && имя !== КЭШ_СТРАНИЦ) {
                    return caches.delete(имя);
                }
                return null;
            }));
        }).then(function () { return self.clients.claim(); })
    );
});

function мимоКэша(адрес) {
    return МИМО.some(function (кусок) { return адрес.pathname.indexOf(кусок) === 0; });
}

function годится(ответ) {
    return ответ && ответ.status === 200 && ответ.type === 'basic';
}

self.addEventListener('fetch', function (событие) {
    const запрос = событие.request;
    if (запрос.method !== 'GET') { return; }

    const адрес = new URL(запрос.url);
    if (адрес.origin !== self.location.origin) { return; }
    if (мимоКэша(адрес)) { return; }

    // Статика: сначала кэш. Имена файлов на проде с хешем, поэтому устареть
    // содержимое не может — меняется имя, а не файл.
    if (адрес.pathname.indexOf('/static/') === 0) {
        событие.respondWith(
            caches.match(запрос).then(function (изКэша) {
                return изКэша || fetch(запрос).then(function (ответ) {
                    if (годится(ответ)) {
                        const копия = ответ.clone();
                        caches.open(КЭШ_ОБОЛОЧКИ).then(function (кэш) {
                            кэш.put(запрос, копия);
                        });
                    }
                    return ответ;
                });
            })
        );
        return;
    }

    // Страницы: сначала сеть, кэш — запасной выход.
    if (запрос.mode === 'navigate') {
        событие.respondWith(
            fetch(запрос).then(function (ответ) {
                if (годится(ответ)) {
                    const копия = ответ.clone();
                    caches.open(КЭШ_СТРАНИЦ).then(function (кэш) {
                        кэш.put(запрос, копия);
                    });
                }
                return ответ;
            }).catch(function () {
                return caches.match(запрос).then(function (изКэша) {
                    return изКэша || caches.match(ОФЛАЙН);
                });
            })
        );
    }
});
