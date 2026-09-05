# -*- coding: utf-8 -*-
"""Установка сайта на домашний экран: манифест, service worker, офлайн-страница.

Зачем: карточки повторяют каждый день и с телефона. Из браузерной вкладки это
делают через раз — приложение на экране запускается одним нажатием и открывается
сразу на нужном разделе.

Почему через Django, а не файлами в static:

* **sw.js обязан лежать в корне сайта.** Service worker управляет только теми
  адресами, что «ниже» него; отданный из `/static/js/sw.js`, он видел бы лишь
  `/static/js/…` и был бы бесполезен.
* **Имена файлов на проде с хешем** (whitenoise + ManifestStaticFilesStorage).
  Список для предзагрузки должен собираться на сервере через `static()`, иначе
  после первой же выкладки service worker будет просить несуществующие адреса.
* **Версия кэша считается из этого же списка.** Поменялся любой файл оболочки —
  сменился хеш имени, сменилась версия, старый кэш выбрасывается сам. Руками
  номер версии никто бы не двигал, и пользователи месяцами сидели бы на
  устаревшем CSS.
"""

import hashlib
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control

# Что кладём в кэш при установке. Только оболочка: то, без чего страница не
# соберётся. MathJax тяжёлый (2 МБ), но именно он рисует формулы — без него
# офлайн-карточки по математике бессмысленны.
ФАЙЛЫ_ОБОЛОЧКИ = [
    'vendor/bootstrap-5.1.3/bootstrap.min.css',
    'vendor/bootstrap-5.1.3/bootstrap.bundle.min.js',
    'css/tokens.css',
    'css/components.css',
    'vendor/mathjax-3.2.2/tex-svg.js',
    'js/cards_modes.js',
    'js/lightbox.js',
    'img/icon-192.png',
]

НАЗВАНИЕ = 'Иван Зенченко — учёба'
КОРОТКО = 'Учёба'
ЦВЕТ_ТЕМЫ = '#4c1d95'
ЦВЕТ_ФОНА = '#ffffff'


def _адреса():
    """Адреса файлов оболочки. Пропавшие пропускаем, а не роняем сайт."""
    готовые = []
    for путь in ФАЙЛЫ_ОБОЛОЧКИ:
        try:
            готовые.append(static(путь))
        except ValueError:
            # На проде static() спотыкается о файл, которого нет в манифесте
            # collectstatic. Тогда лучше кэшировать меньше, чем не отдать
            # service worker вовсе.
            continue
    return готовые


def _версия(адреса):
    return hashlib.sha1('|'.join(адреса).encode('utf-8')).hexdigest()[:12]


def manifest(request):
    """Описание приложения для браузера."""
    return JsonResponse({
        'name': НАЗВАНИЕ,
        'short_name': КОРОТКО,
        'description': 'Курсы, домашние задания и карточки для заучивания.',
        'lang': 'ru',
        'dir': 'ltr',
        # Открываемся сразу на карточках: это то, ради чего значок появляется
        # на домашнем экране. Остальной сайт доступен через меню.
        'start_url': reverse('cards:list'),
        'scope': '/',
        'display': 'standalone',
        'orientation': 'portrait-primary',
        'theme_color': ЦВЕТ_ТЕМЫ,
        'background_color': ЦВЕТ_ФОНА,
        'icons': [
            {'src': static('img/icon-192.png'), 'sizes': '192x192',
             'type': 'image/png', 'purpose': 'any'},
            {'src': static('img/icon-512.png'), 'sizes': '512x512',
             'type': 'image/png', 'purpose': 'any'},
            {'src': static('img/icon-maskable-512.png'), 'sizes': '512x512',
             'type': 'image/png', 'purpose': 'maskable'},
        ],
        'shortcuts': [
            {'name': 'Карточки', 'url': reverse('cards:list')},
        ],
    }, json_dumps_params={'ensure_ascii': False})


@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker(request):
    """Сам service worker. Отдаётся из корня, иначе не увидит весь сайт."""
    адреса = _адреса()
    # Список отдаём готовым JSON, а не циклом по шаблону: фильтр escapejs
    # экранирует и дефисы (`bootstrap-5.1.3`) — браузеру всё равно, а
    # человек в отладчике такой файл читать не сможет.
    ответ = render(request, 'users/sw.js', {
        'версия': _версия(адреса),
        'оболочка_json': json.dumps(адреса + [reverse('offline')],
                                    ensure_ascii=False, indent=4),
        'офлайн_json': json.dumps(reverse('offline')),
    }, content_type='application/javascript; charset=utf-8')
    # Разрешаем область действия шире папки, из которой файл отдан. Здесь это
    # и так корень, но заголовок оставляем: он спасёт, если адрес когда-нибудь
    # переедет.
    ответ['Service-Worker-Allowed'] = '/'
    return ответ


def offline(request):
    """Страница, которую видно вместо ненайденной в кэше, когда сети нет."""
    return render(request, 'users/offline.html')
