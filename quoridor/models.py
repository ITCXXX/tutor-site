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

from .engine import RED, BLUE, initial_state


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
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Ждёт соперника'),
        (STATUS_ACTIVE, 'Идёт'),
        (STATUS_FINISHED, 'Завершена'),
    ]

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
    def create_for(cls, red_player):
        """Создать партию. Создатель играет красными и ходит первым."""
        for _attempt in range(20):
            code = _gen_code()
            if not cls.objects.filter(code=code).exists():
                break
        else:
            raise RuntimeError('Не удалось сгенерировать уникальный код партии')

        return cls.objects.create(
            code=code,
            red_player=red_player,
            state=initial_state(),
            status=cls.STATUS_WAITING,
        )

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
        from games.utils import display_for_games
        user = self.red_player if side == RED else self.blue_player
        return 'ждём…' if user is None else display_for_games(user)
