# -*- coding: utf-8 -*-
"""
games/models.py

Модели для раздела игр (Ultimate Tic Tac Toe).

  • SiteSetting — глобальные настройки раздела (флажок включения).
  • Game        — одна партия UTTT с её состоянием и игроками.
"""

import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

from .engine import initial_state


class SiteSetting(models.Model):
    """Сингл-объект с настройками раздела игр."""

    games_enabled = models.BooleanField(
        'Раздел игр включён', default=False,
        help_text='Если выключено — /games/ отдаёт 404 для всех, кроме '
                  'суперпользователей. Меняется без рестарта сервера.',
    )
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Настройки раздела игр'
        verbose_name_plural = 'Настройки раздела игр'

    def __str__(self):
        return 'Настройки раздела игр'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def _gen_game_code(length=6):
    """Короткий код для URL вида /games/q7r2zh/.
    Без 0/O/l/1 — чтобы было удобно диктовать вслух."""
    alphabet = ''.join(
        c for c in (string.ascii_lowercase + string.digits)
        if c not in '01lo'
    )
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Game(models.Model):
    STATUS_WAITING = 'waiting'
    STATUS_ACTIVE = 'active'
    STATUS_FINISHED = 'finished'
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Ждёт соперника'),
        (STATUS_ACTIVE, 'Идёт'),
        (STATUS_FINISHED, 'Завершена'),
    ]

    code = models.CharField('Код партии', max_length=10, unique=True, db_index=True)
    x_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='games_as_x',
        verbose_name='Игрок X',
    )
    o_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='games_as_o',
        verbose_name='Игрок O',
    )

    board = models.JSONField('Доска (9×9)', default=list)
    big_board = models.JSONField('Большое поле', default=list)
    next_local = models.IntegerField('Куда обязан ходить', null=True, blank=True)
    current = models.CharField('Чей сейчас ход', max_length=1, default='X')
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default=STATUS_WAITING)
    winner = models.CharField(
        'Победитель', max_length=4, blank=True, default='',
        help_text='X, O, D (ничья) или пусто (партия не завершена).',
    )
    last_move = models.JSONField('Последний ход', null=True, blank=True)

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Партия UTTT'
        verbose_name_plural = 'Партии UTTT'
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['code'])]

    def __str__(self):
        return f'Партия {self.code} ({self.get_status_display()})'

    @classmethod
    def create_for(cls, x_player):
        state = initial_state()
        for _attempt in range(20):
            code = _gen_game_code()
            if not cls.objects.filter(code=code).exists():
                break
        else:
            raise RuntimeError('Не удалось сгенерировать уникальный код партии')
        return cls.objects.create(
            code=code,
            x_player=x_player,
            board=state['board'],
            big_board=state['big_board'],
            next_local=state['next_local'],
            current=state['current'],
            status=cls.STATUS_WAITING,
            winner='',
            last_move=None,
        )

    def state_dict(self):
        return {
            'board': self.board,
            'big_board': self.big_board,
            'next_local': self.next_local,
            'current': self.current,
            'status': self.status,
            'winner': self.winner,
            'last_move': self.last_move,
        }

    def apply_state(self, state):
        self.board = state['board']
        self.big_board = state['big_board']
        self.next_local = state['next_local']
        self.current = state['current']
        if self.status != self.STATUS_WAITING:
            self.status = state['status']
        self.winner = state['winner']
        self.last_move = state['last_move']
        self.updated_at = timezone.now()

    def player_side(self, user):
        if user.is_authenticated and self.x_player_id == user.id:
            return 'X'
        if user.is_authenticated and self.o_player_id == user.id:
            return 'O'
        return None

    def is_participant(self, user):
        return self.player_side(user) is not None

    def label_for(self, side):
        from .utils import display_for_games
        user = self.x_player if side == 'X' else self.o_player
        if user is None:
            return 'ждём…'
        return display_for_games(user)
