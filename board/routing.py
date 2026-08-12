# -*- coding: utf-8 -*-
"""
board/routing.py

WebSocket-маршруты раздела досок. Подключаются в tutor_core/asgi.py.
Код доски — те же символы, что и в HTTP-URL (буквы/цифры).
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/board/(?P<code>[A-Za-z0-9]+)/$', consumers.BoardConsumer.as_asgi()),
]
