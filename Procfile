# Этот файл НЕ используется при нашем развёртывании: на сервере всё
# поднимает systemd (deploy/tutor.service.example и tutor-ws.service.example).
# Оставлен на случай запуска на платформе вроде Heroku и исправлен, потому
# что прежняя строка описывала запуск ТОЛЬКО сайта: доска работает по
# WebSocket через ASGI, и по старому Procfile не заработала бы вовсе.
web: gunicorn tutor_core.wsgi
ws: daphne -b 0.0.0.0 -p 8001 tutor_core.asgi:application
