# -*- coding: utf-8 -*-
"""
board/turn.py

Адреса серверов, через которые браузеры устанавливают голосовую связь.

Зачем это на сервере, а не в JS. Во-первых, пропуск к ретранслятору должен
быть ВРЕМЕННЫМ: постоянный пароль, вшитый в страницу, любой желающий вытащил
бы за минуту и гонял бы через ваш сервер свой трафик. Во-вторых, список
адресов выдаёт сервер — значит, когда (и если) появится медиасервер для
групповых занятий, поменяется только этот файл, а браузерную часть трогать
не придётся.

Как устроен временный пропуск (это стандарт, coturn понимает его «из коробки»):
    логин  = «<время, когда пропуск протухнет>:<кто>»
    пароль = подпись этого логина общим секретом
Сервер-ретранслятор знает тот же секрет, поэтому может проверить подпись сам —
хранить где-то список выданных паролей не нужно.
"""

import base64
import hashlib
import hmac
import time

from django.conf import settings


def ice_servers(user=None):
    """Список серверов связи для передачи в браузер.

    Всегда отдаёт STUN (он бесплатный и нужен почти всем). TURN добавляется,
    только если в окружении заданы и адреса, и секрет — иначе голос просто
    работает без ретранслятора, как и раньше.
    """
    servers = []

    stun = [u for u in getattr(settings, 'TURN_STUN_URLS', []) if u]
    if stun:
        servers.append({'urls': stun})

    turn = [u for u in getattr(settings, 'TURN_URLS', []) if u]
    secret = (getattr(settings, 'TURN_SECRET', '') or '').strip()
    if turn and secret:
        ttl = int(getattr(settings, 'TURN_TTL', 3600) or 3600)
        who = getattr(user, 'pk', None) or 'guest'
        username = '%d:%s' % (int(time.time()) + ttl, who)
        digest = hmac.new(secret.encode('utf-8'), username.encode('utf-8'), hashlib.sha1).digest()
        servers.append({
            'urls': turn,
            'username': username,
            'credential': base64.b64encode(digest).decode('ascii'),
        })

    return servers
