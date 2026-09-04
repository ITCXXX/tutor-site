# -*- coding: utf-8 -*-
"""WebSocket-маршруты кабинета. Подключаются в tutor_core/asgi.py.

Отдельно от board/routing.py: чат и доска — разные подсистемы, и общий
обработчик им не нужен.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/chat/(?P<thread_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
]
