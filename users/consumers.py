# -*- coding: utf-8 -*-
"""Чат преподавателя с учеником поверх WebSocket.

СВОЙ обработчик и СВОЙ маршрут. В board/consumers.py не лезем: доска — рабочий
инструмент на занятиях, и поломка там дороже любого чата.

Что берём у доски готовым (там это обкатано на живых занятиях):
  • сердцебиение ping/pong — чтобы посредник (nginx, оператор связи) не счёл
    молчащее соединение брошенным и не оборвал его;
  • ограничитель частоты с честным отказом, а не молчанием;
  • работа с базой через database_sync_to_async.

Чего у доски нет и что здесь своё: присутствие в ветке. Если собеседник сейчас
смотрит на переписку, уведомление ему не нужно — он и так видит сообщение.
"""

import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

HISTORY = 50        # сколько последних сообщений отдаём при входе
MAX_LEN = 4000      # длиннее в чат не пишут; заодно защита от вставки книги
_RATE_MAX = 20      # сообщений в окне
_RATE_WINDOW = 10.0

# Кто сейчас держит ветку открытой: {thread_id: {user_id, ...}}.
# Живёт в памяти процесса, и это осознанно: служба tutor-ws у нас одна (тот же
# daphne, что и доска). Если процессов станет несколько, присутствие придётся
# держать в общем месте — иначе уведомления начнут приходить тем, кто и так
# смотрит на переписку.
_online = {}


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Одна ветка переписки = одна группа Channels."""

    # ── Подключение ────────────────────────────────────────────────────
    async def connect(self):
        self.user = self.scope.get('user')
        raw = self.scope['url_route']['kwargs']['thread_id']
        thread = await self._get_thread(raw, self.user)
        if thread is None:
            # Нет ветки или человек не её участник — закрываем, не присоединяясь.
            await self.close(code=4403)
            return

        self.thread_id = thread['id']
        self.other_id = thread['other_id']
        self.group = f'chat_{self.thread_id}'
        self._rate = []

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        _online.setdefault(self.thread_id, set()).add(self.user.id)

        await self.send_json({
            'action': 'history',
            'messages': await self._history(self.thread_id),
            'me': self.user.id,
        })
        # Вошёл — значит прочитал то, что накопилось.
        await self._read_all()

    async def disconnect(self, code):
        tid = getattr(self, 'thread_id', None)
        if tid is None:
            return
        люди = _online.get(tid)
        if люди:
            люди.discard(getattr(self.user, 'id', None))
            if not люди:
                _online.pop(tid, None)
        await self.channel_layer.group_discard(self.group, self.channel_name)

    # ── Входящие ───────────────────────────────────────────────────────
    async def receive_json(self, content, **kwargs):
        action = content.get('action')

        if action == 'ping':
            await self.send_json({'action': 'pong'})
            return
        if action == 'read':
            await self._read_all()
            return
        if action != 'send':
            return

        # Ограничитель частоты. Молчать нельзя: человек должен знать, что его
        # сообщение не ушло, иначе он решит, что собеседник его игнорирует.
        now = time.monotonic()
        while self._rate and self._rate[0] < now - _RATE_WINDOW:
            self._rate.pop(0)
        if len(self._rate) >= _RATE_MAX:
            await self.send_json({'action': 'rejected', 'reason': 'too_fast'})
            return
        self._rate.append(now)

        text = (content.get('text') or '').strip()
        if not text:
            return
        text = text[:MAX_LEN]

        msg = await self._save(self.thread_id, self.user.id, text)
        await self.channel_layer.group_send(
            self.group, {'type': 'chat.message', 'message': msg})

        # Собеседника нет в ветке — пусть узнает из уведомлений. Уведомление
        # ОДНО на ветку: ключ не даёт расплодить их по числу реплик.
        if self.other_id not in _online.get(self.thread_id, set()):
            await self._notify_other(self.thread_id, self.other_id, self.user.id, text)

    # ── Исходящие (из группы) ──────────────────────────────────────────
    async def chat_message(self, event):
        await self.send_json({'action': 'message', 'message': event['message']})

    async def chat_read(self, event):
        # Собеседник прочитал: у автора галочка становится «прочитано».
        if event.get('by') != getattr(self.user, 'id', None):
            await self.send_json({'action': 'read', 'by': event['by'], 'at': event['at']})

    # ── Прочтение ──────────────────────────────────────────────────────
    async def _read_all(self):
        сколько = await self._mark_read(self.thread_id, self.user.id)
        if not сколько:
            return
        await self.channel_layer.group_send(self.group, {
            'type': 'chat.read',
            'by': self.user.id,
            'at': timezone.now().isoformat(),
        })

    # ── База ───────────────────────────────────────────────────────────
    @database_sync_to_async
    def _get_thread(self, raw, user):
        from .models import Thread
        if not (user and user.is_authenticated):
            return None
        try:
            tid = int(raw)
        except (TypeError, ValueError):
            return None
        t = Thread.objects.filter(pk=tid).first()
        if t is None or not t.has_access(user):
            return None
        other = t.other_side(user)
        return {'id': t.id, 'other_id': other.id if other else None}

    @database_sync_to_async
    def _history(self, thread_id):
        from .models import Message
        qs = (Message.objects.filter(thread_id=thread_id)
              .select_related('author').order_by('-created_at')[:HISTORY])
        return [_as_dict(m) for m in reversed(list(qs))]

    @database_sync_to_async
    def _save(self, thread_id, author_id, text):
        from .models import Message, Thread
        m = Message.objects.create(thread_id=thread_id, author_id=author_id, text=text)
        # Свежесть ветки — по ней сортируется список у преподавателя.
        Thread.objects.filter(pk=thread_id).update(updated_at=m.created_at)
        return _as_dict(m)

    @database_sync_to_async
    def _mark_read(self, thread_id, reader_id):
        from .models import Message, Notification
        n = (Message.objects.filter(thread_id=thread_id, read_at__isnull=True)
             .exclude(author_id=reader_id).update(read_at=timezone.now()))
        if n:
            # Прочитал переписку — гасим и уведомление о ней.
            Notification.objects.filter(
                user_id=reader_id, kind=Notification.KIND_MESSAGE,
                key=f'thread:{thread_id}').update(is_read=True)
        return n

    @database_sync_to_async
    def _notify_other(self, thread_id, other_id, author_id, text):
        from .models import Notification, User
        if not other_id:
            return
        автор = User.objects.filter(pk=author_id).first()
        имя = (автор.display if автор else '') or 'Собеседник'
        Notification.objects.update_or_create(
            user_id=other_id,
            kind=Notification.KIND_MESSAGE,
            key=f'thread:{thread_id}',
            defaults={
                'text': f'{имя}: {text[:120]}',
                'url': f'/chat/{thread_id}/',
                'is_read': False,
            },
        )


def _as_dict(m):
    """Сообщение для отправки в браузер."""
    return {
        'id': m.id,
        'author': m.author_id,
        'name': (getattr(m.author, 'display', '') or m.author.username),
        'text': m.text,
        'at': m.created_at.isoformat(),
        'read': bool(m.read_at),
    }
