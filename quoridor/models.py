# -*- coding: utf-8 -*-
"""
quoridor/models.py

Партия «Заборов» по сети. Устроена по образцу games.Game: короткий код для
приглашения, два игрока, состояние в JSON, опрос состояния клиентом.

Локальные партии (вдвоём за экраном и против компьютера) в базу не попадают
вовсе — они целиком в браузере, серверу там делать нечего.
"""

import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

from .engine import RED, BLUE, initial_state, other


def _gen_code(length=6):
    """Код партии для URL. Без 0/O/l/1 — чтобы его можно было продиктовать."""
    alphabet = ''.join(
        ch for ch in (string.ascii_lowercase + string.digits) if ch not in '01lo'
    )
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class QuoridorGame(models.Model):
    STATUS_WAITING = 'waiting'
    STATUS_ACTIVE = 'active'
    STATUS_FINISHED = 'finished'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Ждёт соперника'),
        (STATUS_ACTIVE, 'Идёт'),
        (STATUS_FINISHED, 'Завершена'),
        (STATUS_CANCELLED, 'Отменена'),
    ]

    # Партия, из которой ушли до первого хода, не «завершена»: победителя в ней
    # нет и показывать её как проигранную нечестно. Поэтому отдельный статус.
    LIVE_STATUSES = (STATUS_WAITING, STATUS_ACTIVE)

    code = models.CharField('Код партии', max_length=10, unique=True, db_index=True)
    red_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='quoridor_as_red',
        verbose_name='Красный',
    )
    blue_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='quoridor_as_blue',
        verbose_name='Синий',
    )

    state = models.JSONField('Состояние партии', default=dict)
    status = models.CharField('Статус', max_length=10,
                              choices=STATUS_CHOICES, default=STATUS_WAITING)
    winner = models.CharField(
        'Победитель', max_length=4, blank=True, default='',
        help_text="red, blue или пусто, если партия не завершена.",
    )
    last_move = models.JSONField('Последний ход', null=True, blank=True)

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Партия «Заборы»'
        verbose_name_plural = 'Партии «Заборы»'
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['code'])]

    def __str__(self):
        return f'Заборы {self.code} ({self.get_status_display()})'

    @classmethod
    def create_for(cls, user, side=RED):
        """
        Создать партию, посадив создателя выбранным цветом.

        Красный ходит первым — поэтому цвет это не только вид фишки, и выбор
        отдан игроку, а не назначается молча.
        """
        if side not in (RED, BLUE):
            side = RED

        for _attempt in range(20):
            code = _gen_code()
            if not cls.objects.filter(code=code).exists():
                break
        else:
            raise RuntimeError('Не удалось сгенерировать уникальный код партии')

        seat = {'red_player': user} if side == RED else {'blue_player': user}
        return cls.objects.create(
            code=code,
            state=initial_state(),
            status=cls.STATUS_WAITING,
            **seat
        )

    def free_side(self):
        """Свободный цвет или None, если оба места заняты."""
        if self.red_player_id is None:
            return RED
        if self.blue_player_id is None:
            return BLUE
        return None

    def can_seat(self, user):
        """Может ли этот пользователь сесть за свободное место."""
        return (
            self.status == self.STATUS_WAITING
            and self.free_side() is not None
            and self.player_side(user) is None
        )

    def seat(self, user):
        """
        Посадить игрока на свободное место. Возвращает цвет или None.

        Сохранение оставлено вызывающему коду: место занимают внутри
        транзакции с блокировкой строки, и решать, когда писать, должен он.
        """
        if not self.can_seat(user):
            return None
        side = self.free_side()
        if side == RED:
            self.red_player = user
        else:
            self.blue_player = user
        self.status = self.STATUS_ACTIVE
        return side

    def has_started(self):
        """Сделан ли хотя бы один ход."""
        return bool(self.last_move) or (self.state or {}).get('moveNo', 1) > 1

    def leave(self, side):
        """
        Встать из-за стола до первого хода — место снова свободно.

        Нужно потому, что место занимается само, стоит открыть ссылку. Без
        обратного хода любой, кто заглянул на партию посмотреть, оставался бы
        в ней навсегда, а выйти мог бы только записав себе поражение.
        """
        if side == RED:
            self.red_player = None
        else:
            self.blue_player = None

        if self.red_player_id is None and self.blue_player_id is None:
            self.status = self.STATUS_CANCELLED
            self.last_move = {'kind': 'cancel', 'side': side, 'name': 'партия отменена'}
        else:
            self.status = self.STATUS_WAITING
            self.last_move = {'kind': 'left', 'side': side, 'name': 'вышел из партии'}
        return self.last_move['kind']

    def resign(self, side):
        """
        Уйти из партии. Что это значит, зависит от того, началась ли игра.

        До первого хода поражения не бывает: играть ещё не начали, и записывать
        победу сопернику не за что — человек просто освобождает место (а если
        он в партии один, партия отменяется). После первого хода это уже сдача.

        Победа записывается и в state: тогда и клиент, и движок одинаково
        видят законченную партию и не примут в ней ходов.
        """
        if self.status not in self.LIVE_STATUSES:
            return None

        if not self.has_started():
            return self.leave(side)

        self.winner = other(side)
        self.status = self.STATUS_FINISHED
        state = self.state or initial_state()
        state['winner'] = self.winner
        self.state = state
        self.last_move = {'kind': 'resign', 'side': side, 'name': 'сдался'}
        return 'resign' 

    def apply_state(self, state, move=None):
        self.state = state
        self.winner = state.get('winner') or ''
        if self.winner:
            self.status = self.STATUS_FINISHED
        if move is not None:
            self.last_move = move
        self.updated_at = timezone.now()

    def player_side(self, user):
        """Каким цветом играет этот пользователь, либо None."""
        if not user.is_authenticated:
            return None
        if self.red_player_id == user.id:
            return RED
        if self.blue_player_id == user.id:
            return BLUE
        return None

    def is_participant(self, user):
        return self.player_side(user) is not None

    def label_for(self, side):
        """
        Как подписать место: игровым ником, а не логином.

        Ник для игр заведён затем, чтобы соперник не видел логин, и остальной
        раздел игр это уважает — значит и «Заборы» обязаны.
        """
        from games.utils import display_for_games
        user = self.red_player if side == RED else self.blue_player
        if user is not None:
            return display_for_games(user)
        # Пустое место ждёт игрока только в живой партии; в отменённой ждать
        # уже некого, и «ждём…» там читается как незаконченное действие.
        return 'ждём…' if self.status == self.STATUS_WAITING else '—'

    # Свойства для шаблонов: label_for принимает аргумент, а шаблон не умеет
    # вызывать методы с аргументами.
    @property
    def red_label(self):
        return self.label_for(RED)

    @property
    def blue_label(self):
        return self.label_for(BLUE)
