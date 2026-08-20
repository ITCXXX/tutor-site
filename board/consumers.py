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
import secrets
import time

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Board, BoardElement, BoardHistory

# Какие действия меняют сохраняемое состояние холста.
_PERSIST_ACTIONS = {'element_add', 'element_update', 'element_delete'}
# Ограничитель применяется ко ВСЕМ действиям — см. начало receive_json.

# Лимиты защиты (DoS / раздувание БД). Обычное рисование шлёт ~33 правки/с и
# элементы небольшие — эти пороги заведомо выше нормы, но режут злоупотребления.
_MAX_ELEMENT_BYTES = 256 * 1024   # один элемент (data) не больше 256 КБ
_MAX_ELEMENTS = 20000             # потолок объектов на доску
_RATE_MAX = 250                   # не больше N правок в окне
_RATE_WINDOW = 1.0                # окно троттлинга, сек
_MAX_RTC_BYTES = 64 * 1024        # одно служебное сообщение голоса (описание связи)


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
        # Идентификатор этого соединения (не пользователя): для голосовой связи
        # важно различать вкладки: две вкладки одного человека — два собеседника.
        self.peer_id = secrets.token_hex(8)
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
            'peer': self.peer_id,
            'label': self.label,
            'role': self.role,
            'is_owner': self.is_owner,
            'default_role': board.default_role,
            'roles': board.roles or {},
            'password_enabled': board.password_enabled,
            'removed': await self._removed_people(self.board_id),
            'history': history,
        })

        # Сообщаем остальным, что кто-то вошёл.
        await self._broadcast({
            'action': 'presence',
            'event': 'join',
            'user': self.user_id,
            'peer': self.peer_id,
            'label': self.label,
        })

    async def disconnect(self, code):
        if getattr(self, 'group', None) and getattr(self, 'board_id', None):
            await self._broadcast({
                'action': 'presence',
                'event': 'leave',
                'user': self.user_id,
                'peer': getattr(self, 'peer_id', None),
                'label': self.label,
            })
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')

        # Ограничитель частоты стоит ПЕРВЫМ и покрывает все действия. Раньше он
        # стоял ниже, и всё, что обрабатывалось выше — курсоры, лазер, вид и
        # служебные сообщения голоса — лимита не знало вовсе. Голос опаснее
        # прочих: одно сообщение весит до 64 КБ и рассылается всей комнате.
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

        # Убрать участника с доски / вернуть обратно — только владелец.
        # «Убрать» = выкинуть из участников, снять личную роль и запретить вход
        # (иначе он вернётся сам, просто открыв ссылку). Если он сейчас на доске —
        # его соединение закрывается сразу, см. board_event.
        if action in ('member_remove', 'member_restore'):
            if not getattr(self, 'is_owner', False):
                return
            target = content.get('target')
            state = await self._set_member_removed(
                self.board_id, target, action == 'member_remove')
            if state is None:
                return
            await self._broadcast({
                'action': 'members_update',
                'removed': state['removed'],
                'roles': state['roles'],
                'target': str(target),
                'kicked': action == 'member_remove',
                'by': self.user_id,
            })
            return

        # Голосовая связь. Сам звук через сервер НЕ идёт — браузеры соединяются
        # напрямую. Здесь мы только пересылаем служебные сообщения, которыми они
        # «знакомятся» (описания связи и сетевые адреса). Адресат указан в поле
        # to; остальные участники такие сообщения просто игнорируют.
        if action == 'rtc':
            payload = content.get('data')
            try:
                if payload is not None and len(json.dumps(payload)) > _MAX_RTC_BYTES:
                    return
            except (TypeError, ValueError):
                return
            await self._broadcast({
                'action': 'rtc',
                'kind': content.get('kind'),
                'to': content.get('to'),
                'data': payload,
                'peer': self.peer_id,
                'user': self.user_id,
                'label': self.label,
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

        # Голос в опросе. Отдельное действие, а не обычная правка: голосовать
        # должны все, включая наблюдателей, а трогать при этом можно ТОЛЬКО свой
        # голос — за чужой никто расписаться не сможет даже в обход интерфейса.
        if action == 'poll_vote':
            saved = await self._poll_vote(self.board_id, content.get('id'), content.get('choice'))
            if saved is None:
                return
            await self._broadcast({
                'action': 'element_update',
                'element': saved,
                'author': self.user_id,
            })
            return

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
        # Убрали именно этого участника — сообщаем и рвём соединение, чтобы он
        # не продолжал править доску до перезагрузки страницы.
        if (payload.get('action') == 'members_update' and payload.get('kicked')
                and str(self.user_id) == payload.get('target')):
            await self.send_json(payload)
            await self.close(code=4403)
            return
        # Историю доставляем ВСЕМ, включая автора (у него панель истории общая, а не
        # локальная). Обычные эхо-события себе не дублируем.
        # Историю и списки участников доставляем ВСЕМ, включая автора действия:
        # у него панель должна показать результат сразу, а не после перезагрузки.
        # Обычные эхо-события себе не дублируем.
        if event.get('sender') == self.channel_name and payload.get('action') not in ('history', 'members_update'):
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
        # Длину типа сверяем с ЁМКОСТЬЮ ПОЛЯ в модели, а не с числом «на глаз»:
        # иначе проверка и база расходятся, и слишком длинный тип падает уже
        # при записи (на проде, где PostgreSQL, — а локально на SQLite молчит).
        if (not isinstance(element_id, str) or len(element_id) > 40
                or len(str(el_type)) > BoardElement.MAX_TYPE_LEN):
            return None, None
        data = element.get('data') or {}
        # Ограничение размера одного элемента (защита от раздувания БД/памяти).
        try:
            if len(json.dumps(data)) > _MAX_ELEMENT_BYTES:
                return None, None
        except (TypeError, ValueError):
            return None, None
        # Тип и прежние данные существующего объекта читаем из базы одним
        # запросом. Тип клиент задаёт ТОЛЬКО при создании: позволить менять его
        # правкой — значит позволить обойти любую проверку, привязанную к типу.
        # Так и было с итогами голосования: правка под видом карточки проносила
        # поддельные голоса, а следующая правка возвращала тип обратно.
        prev = BoardElement.objects.filter(
            board_id=board_id, element_id=element_id,
        ).values('type', 'data').first()
        exists = prev is not None
        if exists:
            el_type = prev['type']
        if not exists and BoardElement.objects.filter(board_id=board_id).count() >= _MAX_ELEMENTS:
            return None, None
        # Встроенная страница: адрес обязан быть обычной веб-ссылкой. Адрес вида
        # javascript:… выполнился бы в браузере ДРУГИХ участников от имени нашего
        # сайта, поэтому отсекаем такие элементы ещё на входе, до записи в базу.
        if el_type == 'embed':
            url = (data or {}).get('url')
            if not isinstance(url, str) or not url.lower().startswith(('http://', 'https://')):
                return None, None

        # Голосование: итоги живут в data['votes'] и меняются ТОЛЬКО отдельным
        # действием poll_vote, где сервер записывает голос за отправителя.
        # Обычная правка объекта (подвинули, переименовали вопрос, сменили
        # варианты) поле голосов не трогает — берём прежнее значение из базы.
        # Иначе любой участник переписывал бы итоги целиком, отправив
        # element_update с готовым списком.
        if el_type == 'poll' and exists:
            data = dict(data)
            data['votes'] = (prev.get('data') or {}).get('votes') or {}
            element = dict(element)
            element['data'] = data

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
    def _poll_vote(self, board_id, element_id, choice):
        """Записать голос ЭТОГО пользователя в опрос. Возвращает элемент или None."""
        if not element_id or self.user_id is None:
            return None
        obj = BoardElement.objects.filter(
            board_id=board_id, element_id=element_id, type='poll',
        ).first()
        if obj is None:
            return None
        data = dict(obj.data or {})
        options = data.get('options') or []
        votes = dict(data.get('votes') or {})
        key = str(self.user_id)
        if choice is None:
            votes.pop(key, None)          # снять свой голос
        else:
            try:
                idx = int(choice)
            except (TypeError, ValueError):
                return None
            if idx < 0 or idx >= len(options):
                return None
            votes[key] = idx
        data['votes'] = votes
        obj.data = data
        obj.save(update_fields=['data', 'updated_at'])
        return obj.to_payload()

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
    def _removed_people(self, board_id):
        """Убранные с доски: [{id, label}] — чтобы владелец видел, кого вернуть."""
        board = Board.objects.filter(id=board_id).first()
        if board is None:
            return []
        ids = [str(x) for x in (board.banned or [])]
        if not ids:
            return []
        users = get_user_model().objects.filter(pk__in=ids)
        found = {str(u.pk): board.label_for(u) for u in users}
        return [{'id': i, 'label': found.get(i, 'участник #' + i)} for i in ids]

    @database_sync_to_async
    def _set_member_removed(self, board_id, target, removed):
        """Убрать участника с доски или вернуть его. Владельца трогать нельзя.
        Возвращает {'removed': [...], 'roles': {...}} или None при неверных данных."""
        board = Board.objects.filter(id=board_id).first()
        if board is None or target is None:
            return None
        key = str(target)
        if key == str(board.owner_id):
            return None
        ids = [str(x) for x in (board.banned or [])]
        roles = dict(board.roles or {})
        user = get_user_model().objects.filter(pk=key).first()
        if removed:
            if key not in ids:
                ids.append(key)
            roles.pop(key, None)          # личная роль убранному больше не нужна
            if user is not None:
                board.members.remove(user)
        else:
            ids = [i for i in ids if i != key]
            if user is not None:
                board.members.add(user)   # возвращаем в участники, а не только снимаем запрет
        board.banned = ids
        board.roles = roles
        board.save(update_fields=['banned', 'roles', 'updated_at'])
        found = {}
        if ids:
            found = {str(u.pk): board.label_for(u)
                     for u in get_user_model().objects.filter(pk__in=ids)}
        return {
            'removed': [{'id': i, 'label': found.get(i, 'участник #' + i)} for i in ids],
            'roles': roles,
        }

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
