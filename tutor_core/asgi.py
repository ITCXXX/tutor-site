"""
ASGI config for tutor_core project.

Здесь развилка протоколов:
  • "http"      → обычные Django-вью (как и раньше);
  • "websocket" → Channels-роутинг досок (раздел board) с проверкой сессии
                  и защитой от посторонних источников.

Важно: вызываем get_asgi_application() ДО импорта routing-модулей,
чтобы Django успел загрузить приложения (apps registry) — иначе импорт
consumers упадёт.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutor_core.settings')

# Инициализируем Django до импорта потребителей (consumers).
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack          # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

import board.routing  # noqa: E402
import users.routing  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            # Маршруты складываются: доска и чат кабинета — разные подсистемы,
            # каждая со своим обработчиком.
            URLRouter(board.routing.websocket_urlpatterns
                      + users.routing.websocket_urlpatterns)
        )
    ),
})
