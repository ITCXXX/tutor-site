# -*- coding: utf-8 -*-
"""Переписка поверх WebSocket: личная и групповая.

СВОЙ обработчик и СВОЙ маршрут. В board/consumers.py не лезем: доска — рабочий
инструмент на занятиях, и поломка там дороже любого чата.

Что берём у доски готовым (там это обкатано на живых занятиях):
  • сердцебиение ping/pong — чтобы посредник (nginx, оператор связи) не счёл
    молчащее соединение брошенным и не оборвал его;
  • ограничитель частоты с честным отказом, а не молчанием;
  • работа с базой через database_sync_to_async.

Чего у доски нет и что здесь своё: присутствие в ветке. Кто сейчас смотрит на
переписку, тому уведомление не нужно — он и так видит сообщение.

ПРО ПРОВЕРКИ ВХОДЯЩЕГО. Обработчик получает не только текст: номер сообщения,
на которое отвечают, и номер задания, о котором спрашивают. И то и другое —
числа из браузера, то есть из рук человека, который может подставить любое.
Поэтому оба проверяются: цитата обязана быть из ЭТОЙ ветки, а задание — из
курса, куда человек записан. Иначе подстановкой чужого номера вытягивается
чужой текст, а это утечка, а не шалость.
"""

import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.urls import reverse
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
        self.members = thread['members']       # id всех участников, включая себя
        self.my_name = thread['name']          # взято в синхронном месте, см. _get_thread
        self.group = f'chat_{self.thread_id}'
        self._rate = []

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        _online.setdefault(self.thread_id, set()).add(self.user.id)

        await self.send_json({
            'action': 'history',
            'messages': await self._history(self.thread_id, self.user.id),
            'me': self.user.id,
            'readers': await self._read_state(self.thread_id),
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
        if action == 'resolve':
            # Пометить вопрос закрытым (или снова открыть) — вручную.
            итог = await self._toggle_answered(
                self.thread_id, content.get('id'), bool(content.get('done')))
            if итог is not None:
                await self.channel_layer.group_send(self.group, {
                    'type': 'chat.answered', 'id': итог['id'],
                    'answered': итог['answered']})
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
        about = content.get('about')          # номер задания, если вопрос по задаче
        if not text and not about:
            return
        text = text[:MAX_LEN]

        msg = await self._save(
            self.thread_id, self.user.id, text,
            content.get('reply_to'), about, bool(content.get('question')))
        if msg is None:
            await self.send_json({'action': 'rejected', 'reason': 'bad_ref'})
            return

        await self.channel_layer.group_send(
            self.group, {'type': 'chat.message', 'message': msg})
        if msg.get('closes'):
            # Ответом на вопрос вопрос и закрывается: отдельной кнопки для
            # обычного случая быть не должно, иначе её просто не нажимают.
            await self.channel_layer.group_send(self.group, {
                'type': 'chat.answered', 'id': msg['closes'], 'answered': True})

        # Кого нет в ветке — тем уведомление. Уведомление ОДНО на ветку:
        # ключ не даёт расплодить их по числу реплик.
        сейчас_тут = _online.get(self.thread_id, set())
        нет_на_месте = [uid for uid in self.members
                        if uid != self.user.id and uid not in сейчас_тут]
        if нет_на_месте:
            await self._notify(self.thread_id, нет_на_месте, self.user.id,
                               text or 'вопрос по задаче')

    # ── Исходящие (из группы) ──────────────────────────────────────────
    async def chat_message(self, event):
        await self.send_json({'action': 'message', 'message': event['message']})

    async def chat_read(self, event):
        # Собеседник дочитал докуда-то. Своё же прочтение себе не шлём — оно
        # ничего не меняет: свои сообщения читателем считаешь не ты.
        if event.get('by') != getattr(self.user, 'id', None):
            await self.send_json({'action': 'read', 'by': event['by'],
                                  'name': event.get('name', ''), 'at': event['at']})

    async def chat_answered(self, event):
        await self.send_json({'action': 'answered', 'id': event['id'],
                              'answered': event['answered']})

    # ── Прочтение ──────────────────────────────────────────────────────
    async def _read_all(self):
        сколько = await self._mark_read(self.thread_id, self.user.id)
        if not сколько:
            return
        await self.channel_layer.group_send(self.group, {
            'type': 'chat.read',
            'by': self.user.id,
            'name': getattr(self, 'my_name', ''),
            'at': timezone.now().isoformat(),
        })

    # ── База ───────────────────────────────────────────────────────────
    @database_sync_to_async
    def _get_thread(self, raw, user):
        from .models import Thread, ThreadMember
        if not (user and user.is_authenticated):
            return None
        try:
            tid = int(raw)
        except (TypeError, ValueError):
            return None
        t = Thread.objects.filter(pk=tid).first()
        if t is None:
            return None
        участники = list(ThreadMember.objects.filter(thread=t)
                         .values_list('user_id', flat=True))
        if user.id not in участники:
            return None
        # Имя забираем ЗДЕСЬ, пока мы в синхронном месте. Свойство display лезет
        # в базу за профилем, и вызов его позже, из асинхронного обработчика,
        # роняет соединение целиком — проверено, падало на входе в переписку.
        return {'id': t.id, 'members': участники,
                'name': (getattr(user, 'display', '') or user.username)}

    @database_sync_to_async
    def _read_state(self, thread_id):
        """Докуда дочитал КАЖДЫЙ участник: [{id, name, at}].

        Отдаём список целиком, а не готовый ответ «прочитано / нет». Решает
        браузер, сравнивая время сообщения с отметками, — и тогда одна и та же
        запись обслуживает и личную переписку («прочитано»), и группу
        («прочитали двое из трёх»), и подпись с именами. Считать это на сервере
        для каждого сообщения значило бы гонять полсотни одинаковых сравнений
        и всё равно не знать, что именно захочет показать страница.
        """
        from .models import ThreadMember
        строки = (ThreadMember.objects.filter(thread_id=thread_id)
                  .select_related('user'))
        return [{
            'id': m.user_id,
            'name': (getattr(m.user, 'display', '') or m.user.username),
            'at': m.last_read_at.isoformat() if m.last_read_at else None,
        } for m in строки]

    @database_sync_to_async
    def _history(self, thread_id, me):
        # Порога здесь больше нет: «прочитано» считает страница по списку
        # отметок (см. _read_state). Один расчёт вместо двух — иначе сервер и
        # браузер однажды ответили бы по-разному на один и тот же вопрос.
        from .models import Message
        порог = None
        qs = (Message.objects.filter(thread_id=thread_id)
              .select_related('author', 'reply_to', 'reply_to__author',
                              'about_assignment', 'about_assignment__lesson')
              .order_by('-created_at')[:HISTORY])
        return [_as_dict(m, порог) for m in reversed(list(qs))]

    @database_sync_to_async
    def _save(self, thread_id, author_id, text, reply_to, about, question):
        from .models import Assignment, Message, Thread, User
        from .views import _can_access_lesson

        # Цитата — только из этой же ветки. Иначе номером чужого сообщения
        # вытягивается чужой текст: он поедет в ленту как цитата.
        источник = None
        if reply_to:
            источник = (Message.objects
                        .filter(pk=reply_to, thread_id=thread_id)
                        .select_related('author').first())
            if источник is None:
                return None

        # Задание — только из курса, куда человек допущен. Проверку берём ту же,
        # что у страницы урока: два разных правила доступа к одному уроку — это
        # заявка на дыру.
        задание = None
        if about:
            задание = (Assignment.objects
                       .filter(pk=about)
                       .select_related('lesson', 'lesson__module',
                                       'lesson__module__course').first())
            автор = User.objects.filter(pk=author_id).first()
            if задание is None or автор is None or not _can_access_lesson(
                    автор, задание.lesson):
                return None

        m = Message.objects.create(
            thread_id=thread_id, author_id=author_id, text=text,
            reply_to=источник, about_assignment=задание,
            is_question=bool(question or задание is not None),
        )
        # Свежесть ветки — по ней сортируется список.
        Thread.objects.filter(pk=thread_id).update(updated_at=m.created_at)

        # Ответили на чужой вопрос — вопрос закрыт. Своим ответом на свой же
        # вопрос ничего не закрывается: человек часто дописывает мысль.
        закрыт = None
        if (источник is not None and источник.is_question
                and источник.answered_at is None
                and источник.author_id != author_id):
            источник.answered_at = m.created_at
            источник.save(update_fields=['answered_at'])
            закрыт = источник.id

        d = _as_dict(m, None)
        d['closes'] = закрыт
        return d

    @database_sync_to_async
    def _toggle_answered(self, thread_id, msg_id, done):
        from .models import Message
        m = Message.objects.filter(pk=msg_id, thread_id=thread_id,
                                   is_question=True).first()
        if m is None:
            return None
        m.answered_at = timezone.now() if done else None
        m.save(update_fields=['answered_at'])
        return {'id': m.id, 'answered': bool(m.answered_at)}

    @database_sync_to_async
    def _mark_read(self, thread_id, reader_id):
        from .chat import mark_read
        from .models import Notification, Thread, User
        t = Thread.objects.filter(pk=thread_id).first()
        u = User.objects.filter(pk=reader_id).first()
        if t is None or u is None:
            return 0
        n = mark_read(t, u)
        if n:
            # Прочитал переписку — гасим и уведомление о ней.
            Notification.objects.filter(
                user_id=reader_id, kind=Notification.KIND_MESSAGE,
                key=f'thread:{thread_id}').update(is_read=True)
        return n

    @database_sync_to_async
    def _notify(self, thread_id, кому, author_id, text):
        from .models import Notification, Thread, User
        автор = User.objects.filter(pk=author_id).first()
        имя = (автор.display if автор else '') or 'Собеседник'
        ветка = Thread.objects.filter(pk=thread_id).first()
        где = ''
        if ветка is not None and ветка.kind == Thread.KIND_GROUP:
            где = ' (%s)' % (ветка.title or 'группа')
        for uid in кому:
            Notification.objects.update_or_create(
                user_id=uid,
                kind=Notification.KIND_MESSAGE,
                key=f'thread:{thread_id}',
                defaults={
                    'text': f'{имя}{где}: {text[:120]}',
                    'url': reverse('chat_thread', args=[thread_id]),
                    'is_read': False,
                },
            )


def _as_dict(m, порог):
    """Сообщение для отправки в браузер.

    «Прочитано» больше не хранится на сообщении: у каждого участника своя
    отметка «докуда дочитал». Прочитанным считаем то, что раньше отметки
    самого отстающего — в группе «прочитано» должно значить «прочитали все»,
    а не «хоть кто-то».
    """
    d = {
        'id': m.id,
        'author': m.author_id,
        'name': (getattr(m.author, 'display', '') or m.author.username),
        'text': m.text,
        'at': m.created_at.isoformat(),
        'read': bool(порог and m.created_at <= порог),
        'question': m.is_question,
        'answered': bool(m.answered_at),
    }
    if m.reply_to_id and m.reply_to is not None:
        d['reply'] = {
            'id': m.reply_to_id,
            'name': (getattr(m.reply_to.author, 'display', '')
                     or m.reply_to.author.username),
            'text': m.reply_to.text[:160],
        }
    if m.about_assignment_id and m.about_assignment is not None:
        з = m.about_assignment
        d['about'] = {
            'id': з.id,
            'title': з.title,
            'lesson': з.lesson.title if з.lesson_id else '',
            'url': reverse('lesson_detail', args=[з.lesson_id]) if з.lesson_id else '',
        }
    return d
