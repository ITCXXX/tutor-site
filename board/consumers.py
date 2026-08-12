# -*- coding: utf-8 -*-
"""
board/consumers.py

WebSocket-«потребитель» одной доски. На каждое соединение приходится один
участник; все соединения одной доски объединены в группу board_<code>, и
любое изменение мгновенно рассылается всей группе.

Протокол (JSON):

  Клиент → Сервер:
    {action: 'element_add',    element: {id, type, data, z}}
    {action: 'element_update', element: {id, type, data, z}}
    {action: 'element_delete', id: '<uuid>'}
    {action: 'cursor',         x: <float>, y: <float>}   # эфемерно, не в БД

  Сервер → Клиент:
    {action: 'init',     elements: [...], me: <id>, label: '<имя>'}
    {action: 'element_add'/'element_update', element: {...}, author: <id>}
    {action: 'element_delete', id: '<uuid>', author: <id>}
    {action: 'cursor',   x, y, user: <id>, label: '<имя>'}
    {action: 'presence', event: 'join'|'leave', user: <id>, label: '<имя>'}

Элементы сохраняются в БД (BoardElement) — доска переживает перезагрузку.
Курсоры и presence — эфемерные, в БД не пишутся.
"""

import json
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Board, BoardElement, BoardHistory

# Какие действия меняют сохраняемое состояние холста.
_PERSIST_ACTIONS = {'element_add', 'element_update', 'element_delete'}

# Лимиты защиты (DoS / раздувание БД). Обычное рисование шлёт ~33 правки/с и
# элементы небольшие — эти пороги заведомо выше нормы, но режут злоупотребления.
_MAX_ELEMENT_BYTES = 256 * 1024   # один элемент (data) не больше 256 КБ
_MAX_ELEMENTS = 20000             # потолок объектов на доску
_RATE_MAX = 250                   # не больше N правок в окне
_RATE_WINDOW = 1.0                # окно троттлинга, сек


class BoardConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.code = self.scope['url_route']['kwargs']['code']
        self.user = self.scope.get('user')
        self.group = f'board_{self.code}'

        board = await self._get_board(self.code)
        if board is None or not await self._can_access(board, self.user):
            # Нет доски или нет доступа — закрываем без присоединения к группе.
            await self.close(code=4403)
            return

        self.board_id = board.id
        self.label = await database_sync_to_async(board.label_for)(self.user)
        self.user_id = getattr(self.user, 'pk', None)
        self.is_owner = (board.owner_id == getattr(self.user, 'pk', None)) or bool(getattr(self.user, 'is_superuser', False))
        self.role = await database_sync_to_async(board.role_for)(self.user)
        self._rate = []  # метки времени последних правок (троттлинг)

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        # Отдаём новому участнику текущее состояние холста + его роль и (владельцу)
        # текущие настройки доступа, чтобы нарисовать панель управления ролями.
        elements = await self._load_elements(self.board_id)
        history = await self._recent_history(self.board_id)
        await self.send_json({
            'action': 'init',
            'elements': elements,
            'me': self.user_id,
            'label': self.label,
            'role': self.role,
            'is_owner': self.is_owner,
            'default_role': board.default_role,
            'roles': board.roles or {},
            'password_enabled': board.password_enabled,
            'history': history,
        })

        # Сообщаем остальным, что кто-то вошёл.
        await self._broadcast({
            'action': 'presence',
            'event': 'join',
            'user': self.user_id,
            'label': self.label,
        })

    async def disconnect(self, code):
        if getattr(self, 'group', None) and getattr(self, 'board_id', None):
            await self._broadcast({
                'action': 'presence',
                'event': 'leave',
                'user': self.user_id,
                'label': self.label,
            })
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')

        if action == 'cursor':
            # Эфемерно: просто пересылаем соседям, в БД не пишем.
            await self._broadcast({
                'action': 'cursor',
                'x': content.get('x'),
                'y': content.get('y'),
                'user': self.user_id,
                'label': self.label,
            })
            return

        # Управление ролями — только владелец. target=None → роль по ссылке;
        # иначе личная роль участника (role='default' убирает личное назначение).
        if action == 'set_role':
            if not getattr(self, 'is_owner', False):
                return
            target = content.get('target')
            role = content.get('role')
            default_role, roles = await self._apply_role(self.board_id, target, role)
            if default_role is None:
                return
            await self._broadcast({
                'action': 'roles_update',
                'default_role': default_role,
                'roles': roles,
                'by': self.user_id,
            })
            return

        # Эфемерные сообщения занятия (в БД не пишем, просто пересылаем):
        #   laser — точка гаснущего следа (x,y, s=начало штриха);
        #   view  — вид ведущего (x,y,scale).
        if action in ('laser', 'view'):
            payload = {
                'action': action,
                'user': self.user_id,
                'label': self.label,
                'x': content.get('x'),
                'y': content.get('y'),
            }
            if action == 'laser':
                payload['s'] = 1 if content.get('s') else 0
            else:
                payload['scale'] = content.get('scale')
            await self._broadcast(payload)
            return

        # Правки холста разрешены только редакторам. Наблюдателю сервер молча
        # отказывает (клиент и так блокирует UI — это защита от обхода).
        if action in _PERSIST_ACTIONS and getattr(self, 'role', None) != Board.ROLE_EDITOR:
            return

        # Троттлинг правок: тихо отбрасываем всё сверх порога (защита от флуда).
        if action in _PERSIST_ACTIONS:
            now = time.monotonic()
            rate = getattr(self, '_rate', None)
            if rate is None:
                self._rate = rate = []
            cutoff = now - _RATE_WINDOW
            while rate and rate[0] < cutoff:
                rate.pop(0)
            if len(rate) >= _RATE_MAX:
                return
            rate.append(now)

        if action in ('element_add', 'element_update'):
            element = content.get('element') or {}
            saved, hist = await self._upsert_element(self.board_id, element, self.user_id)
            if saved is None:
                return
            await self._broadcast({
                'action': action,
                'element': saved,
                'author': self.user_id,
            })
            if hist:  # None если правка «склеилась» с предыдущей (не спамим историю)
                await self._broadcast({'action': 'history', 'entry': hist})
            return

        if action == 'element_delete':
            element_id = content.get('id')
            if not element_id:
                return
            hist = await self._delete_element(self.board_id, element_id)
            await self._broadcast({
                'action': 'element_delete',
                'id': element_id,
                'author': self.user_id,
            })
            if hist:
                await self._broadcast({'action': 'history', 'entry': hist})
            return

        # Неизвестное действие — игнорируем.

    # ── Рассылка в группу ───────────────────────────────────────────────

    async def _broadcast(self, payload):
        """Отправить payload всем в группе. Себе — не дублируем."""
        await self.channel_layer.group_send(self.group, {
            'type': 'board.event',
            'payload': payload,
            'sender': self.channel_name,
        })

    async def board_event(self, event):
        """Хендлер group_send: доставляем сообщение клиенту.
        Свои же события не эхоим (клиент уже применил их локально)."""
        payload = event['payload']
        # Смена ролей меняет права ЭТОГО соединения на лету — обновляем свою
        # роль для серверной проверки правок (даже если событие пришло от нас).
        if payload.get('action') == 'roles_update':
            self.role = self._role_from(payload.get('default_role'), payload.get('roles') or {})
        # Историю доставляем ВСЕМ, включая автора (у него панель истории общая, а не
        # локальная). Обычные эхо-события себе не дублируем.
        if event.get('sender') == self.channel_name and payload.get('action') != 'history':
            return
        await self.send_json(payload)

    def _role_from(self, default_role, roles):
        """Действующая роль этого пользователя по свежим настройкам доступа."""
        if getattr(self, 'is_owner', False):
            return Board.ROLE_EDITOR
        r = roles.get(str(self.user_id))
        if r in (Board.ROLE_VIEWER, Board.ROLE_EDITOR):
            return r
        return default_role if default_role in (Board.ROLE_VIEWER, Board.ROLE_EDITOR) else Board.ROLE_VIEWER

    # ── Работа с БД (в async-контексте — через database_sync_to_async) ──

    @database_sync_to_async
    def _get_board(self, code):
        return Board.objects.filter(code=code).first()

    @database_sync_to_async
    def _can_access(self, board, user):
        return board.can_access(user)

    @database_sync_to_async
    def _load_elements(self, board_id):
        qs = BoardElement.objects.filter(board_id=board_id).order_by('z_index', 'id')
        return [el.to_payload() for el in qs]

    @database_sync_to_async
    def _upsert_element(self, board_id, element, author_id):
        element_id = element.get('id')
        el_type = element.get('type')
        if not element_id or not el_type:
            return None, None
        if not isinstance(element_id, str) or len(element_id) > 40 or len(str(el_type)) > 16:
            return None, None
        data = element.get('data') or {}
        # Ограничение размера одного элемента (защита от раздувания БД/памяти).
        try:
            if len(json.dumps(data)) > _MAX_ELEMENT_BYTES:
                return None, None
        except (TypeError, ValueError):
            return None, None
        # Потолок числа объектов на доску — только для НОВЫХ (существующие правим всегда).
        exists = BoardElement.objects.filter(board_id=board_id, element_id=element_id).exists()
        if not exists and BoardElement.objects.filter(board_id=board_id).count() >= _MAX_ELEMENTS:
            return None, None
        # boardconfig — служебная настройка доски (фон), в историю не пишем.
        if el_type == 'boardconfig':
            obj, _c = BoardElement.objects.update_or_create(
                board_id=board_id, element_id=element_id,
                defaults={'type': el_type, 'data': element.get('data') or {},
                          'z_index': int(element.get('z') or 0), 'author_id': author_id})
            return obj.to_payload(), None
        obj, created = BoardElement.objects.update_or_create(
            board_id=board_id, element_id=element_id,
            defaults={
                'type': el_type,
                'data': element.get('data') or {},
                'z_index': int(element.get('z') or 0),
                'author_id': author_id,
            },
        )
        hist = self._log_history(
            board_id, BoardHistory.ADD if created else BoardHistory.UPDATE,
            element_id, el_type, None,
        )
        return obj.to_payload(), hist

    @database_sync_to_async
    def _delete_element(self, board_id, element_id):
        obj = BoardElement.objects.filter(
            board_id=board_id, element_id=element_id,
        ).first()
        prev = obj.to_payload() if obj else None
        etype = (prev.get('type') if prev else '') or ''
        if obj:
            obj.delete()
        if etype == 'boardconfig':
            return None
        return self._log_history(board_id, BoardHistory.DELETE, element_id, etype, prev)

    def _log_history(self, board_id, action, element_id, element_type, payload):
        """Записать действие в историю доски (внутри sync-контекста). Подряд идущие
        правки одного элемента одним пользователем «склеиваем» (не плодим строки) —
        возвращаем None, чтобы не рассылать повтор. Обрезаем до последних 200."""
        if action == BoardHistory.UPDATE:
            last = BoardHistory.objects.filter(board_id=board_id).order_by('-id').first()
            if (last and last.action == BoardHistory.UPDATE
                    and last.element_id == element_id and last.by == self.user_id):
                return None
        row = BoardHistory.objects.create(
            board_id=board_id, action=action, element_id=element_id or '',
            element_type=element_type or '', payload=payload,
            by=self.user_id, label=self.label,
        )
        over = list(BoardHistory.objects.filter(board_id=board_id)
                    .order_by('-id').values_list('id', flat=True)[BoardHistory.MAX_PER_BOARD:])
        if over:
            BoardHistory.objects.filter(id__in=over).delete()
        return row.to_payload()

    @database_sync_to_async
    def _recent_history(self, board_id):
        qs = list(BoardHistory.objects.filter(board_id=board_id)
                  .order_by('-id')[:BoardHistory.MAX_PER_BOARD])
        return [h.to_payload() for h in reversed(qs)]  # старые → новые

    @database_sync_to_async
    def _apply_role(self, board_id, target, role):
        """Изменить настройки доступа доски. target=None → роль по ссылке;
        иначе личная роль участника. role='default' убирает личное назначение.
        Возвращает (default_role, roles) или (None, None) при неверных данных."""
        board = Board.objects.filter(id=board_id).first()
        if board is None:
            return None, None
        if target is None:
            if role not in (Board.ROLE_VIEWER, Board.ROLE_EDITOR):
                return None, None
            board.default_role = role
            board.save(update_fields=['default_role', 'updated_at'])
            return board.default_role, board.roles or {}
        # Личная роль: нельзя менять роль владельца (он всегда редактор).
        key = str(target)
        if str(board.owner_id) == key:
            return board.default_role, board.roles or {}
        roles = dict(board.roles or {})
        if role == 'default':
            roles.pop(key, None)
        elif role in (Board.ROLE_VIEWER, Board.ROLE_EDITOR):
            roles[key] = role
        else:
            return None, None
        board.roles = roles
        board.save(update_fields=['roles', 'updated_at'])
        return board.default_role, roles
