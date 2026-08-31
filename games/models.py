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

from .bot import ALL_LEVELS, DEFAULT_LEVEL, LEVELS, level_title
from .engine import initial_state, score as engine_score, ALL_VARIANTS, VARIANT_CLASSIC, VARIANT_LONG


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

    VARIANT_CHOICES = [
        (VARIANT_CLASSIC, 'Классика'),
        (VARIANT_LONG, 'Долгая дорога'),
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

    variant = models.CharField(
        'Вариант правил', max_length=10, choices=VARIANT_CHOICES,
        default=VARIANT_CLASSIC,
    )
    bot_side = models.CharField(
        'Сторона компьютера', max_length=1, blank=True, default='',
        help_text='X или O, если соперник — компьютер. Пусто у обычных партий.',
    )
    bot_level = models.CharField(
        'Уровень компьютера', max_length=10, blank=True, default='',
        choices=[(k, v['title']) for k, v in LEVELS.items()],
    )

    is_local = models.BooleanField(
        'Локальная (hot-seat)', default=False,
        help_text='Два игрока за одним компьютером. Ходы делает один и тот же '
                  'пользователь, joining не требуется.',
    )
    parent_game = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rematches', verbose_name='Партия-предок (реванш)',
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
    def create_for(cls, x_player, *, variant=VARIANT_CLASSIC, is_local=False,
                   o_player=None, parent_game=None, bot_side='', bot_level=''):
        """Создать новую партию.

        x_player    — создатель (всегда сторона X в новой партии).
        variant     — 'classic' или 'long'.
        is_local    — hot-seat (оба хода с одного аккаунта).
        o_player    — для реванша: уже известный соперник; партия сразу active.
        parent_game — ссылка на предыдущую партию серии.
        """
        if variant not in ALL_VARIANTS:
            variant = VARIANT_CLASSIC

        state = initial_state()
        for _attempt in range(20):
            code = _gen_game_code()
            if not cls.objects.filter(code=code).exists():
                break
        else:
            raise RuntimeError('Не удалось сгенерировать уникальный код партии')

        # Локальная, реванш с известным O или партия с компьютером — сразу active.
        if is_local:
            o_player = x_player
            status = cls.STATUS_ACTIVE
        elif o_player is not None:
            status = cls.STATUS_ACTIVE
        else:
            status = cls.STATUS_WAITING

        if bot_side in ('X', 'O'):
            # Место компьютера остаётся пустым: он не пользователь, и заводить
            # ему учётную запись только ради колонки в базе — плохая сделка.
            # Кто именно за него играет, знает bot_side.
            human = x_player
            x_player = None if bot_side == 'X' else human
            o_player = None if bot_side == 'O' else human
            status = cls.STATUS_ACTIVE
            if bot_level not in ALL_LEVELS:
                bot_level = DEFAULT_LEVEL
        else:
            bot_side = ''
            bot_level = ''

        return cls.objects.create(
            code=code,
            x_player=x_player,
            o_player=o_player,
            bot_side=bot_side,
            bot_level=bot_level,
            variant=variant,
            is_local=is_local,
            parent_game=parent_game,
            board=state['board'],
            big_board=state['big_board'],
            next_local=state['next_local'],
            current=state['current'],
            status=status,
            winner='',
            last_move=None,
        )

    def make_rematch(self, requester):
        """Создать партию-реванш. Стороны меняются:
            бывший O становится X, бывший X становится O.
        Если кто-то из участников был None — оставляем None.
        Реванш создаётся только для завершённых партий.
        """
        new_x = self.o_player
        new_o = self.x_player
        # Если запрос пришёл от того, кто был O — он стал X, что справедливо.
        # Если запросил X — он стал O. (Стороны всегда меняются.)
        # Если это локальная партия — и x и o = creator, всё ок.
        if self.is_bot_game:
            # Стороны меняются и здесь: играл первым — теперь ходит компьютер.
            return Game.create_for(
                x_player=requester,
                variant=self.variant,
                parent_game=self,
                bot_side='X' if self.bot_side == 'O' else 'O',
                bot_level=self.bot_level,
            )

        return Game.create_for(
            x_player=new_x or requester,
            o_player=new_o,
            variant=self.variant,
            is_local=self.is_local,
            parent_game=self,
        )

    @property
    def is_bot_game(self):
        return self.bot_side in ('X', 'O')

    @property
    def bot_title(self):
        return level_title(self.bot_level)

    @property
    def score_x(self):
        sx, _ = engine_score(self.big_board)
        return sx

    @property
    def score_o(self):
        _, so = engine_score(self.big_board)
        return so

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
        """Какой стороной играет данный пользователь.

        В локальной партии один и тот же user — и X, и O; возвращаем
        'X' или 'O' в зависимости от текущего хода (current). Это позволяет
        view game_move без переписывания принять ход от обоих сторон
        с одной сессии.
        """
        if not user.is_authenticated:
            return None
        if self.is_local:
            if self.x_player_id == user.id:
                return self.current
            return None
        if self.x_player_id == user.id:
            return 'X'
        if self.o_player_id == user.id:
            return 'O'
        return None

    def is_participant(self, user):
        return self.player_side(user) is not None

    def label_for(self, side):
        from .utils import display_for_games
        if self.bot_side == side:
            return 'Компьютер (%s)' % self.bot_title
        user = self.x_player if side == 'X' else self.o_player
        if user is None:
            return 'ждём…'
        return display_for_games(user)
