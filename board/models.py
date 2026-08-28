# -*- coding: utf-8 -*-
"""
board/models.py

Модели раздела «Доска» — совместный бесконечный холст для занятий.

  • Board        — одна доска (комната) с кодом, владельцем и участниками.
  • BoardElement — один объект на холсте (штрих, фигура, текст, формула,
                   ГеоГебра-аплет…). Хранится отдельной строкой, чтобы
                   синхронизировать изменения по одному элементу (дельтами),
                   а не пересылать весь холст целиком.

Идея кодов комнат и доступа повторяет раздел games для единообразия.
"""

import secrets
import string

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.db import models


def gen_board_code(length=6):
    """Короткий код для URL вида /board/q7r2zh/.
    Без 0/O/l/1 — чтобы было удобно диктовать вслух."""
    alphabet = ''.join(
        c for c in (string.ascii_lowercase + string.digits)
        if c not in '01lo'
    )
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Board(models.Model):
    """Доска-комната. Участвовать могут владелец и присоединившиеся по коду."""

    # Сколько досок разрешено ИМЕТЬ одному пользователю. Считаются только
    # собственные: доски, куда вы зашли по чужой ссылке, квоту не занимают —
    # иначе активный ученик выбрал бы её чужими досками.
    # Упёрлись в потолок — удалите ненужную старую доску (правой кнопкой в списке).
    MAX_PER_OWNER = 50

    # Роли доступа. Комментариев у нас нет, поэтому ролей две (как «viewer» и
    # «editor» в Miro): наблюдатель — только смотрит, редактор — может менять холст.
    ROLE_VIEWER = 'viewer'
    ROLE_EDITOR = 'editor'
    ROLE_CHOICES = [
        (ROLE_VIEWER, 'Наблюдатель'),
        (ROLE_EDITOR, 'Редактор'),
    ]

    code = models.CharField('Код доски', max_length=10, unique=True, db_index=True)
    title = models.CharField('Название', max_length=120, blank=True, default='')

    # Роль по умолчанию для всех, кто заходит по ссылке (без личного назначения).
    default_role = models.CharField(
        'Роль по ссылке', max_length=8, choices=ROLE_CHOICES, default=ROLE_EDITOR,
        help_text='Что могут делать зашедшие по ссылке, если им не назначена личная роль.',
    )
    # Личные назначения ролей: {"<user_id>": "viewer"|"editor"}. Переопределяют
    # роль по умолчанию для конкретных участников. Владелец всегда редактор.
    roles = models.JSONField('Личные роли', default=dict, blank=True)

    # Кого владелец явно убрал с доски (id пользователей строками, как в roles).
    # Без этого списка кнопка «Убрать» была бы фикцией: вход на доску по ссылке
    # снова автоматически делает человека участником (см. board_room). Здесь же
    # хранится решение владельца — оно переживает и перезаход, и перезагрузку.
    banned = models.JSONField('Убранные с доски', default=list, blank=True)

    # Пароль доски (необязательный). Храним ТОЛЬКО хеш; включён/выключен — отдельным
    # флагом, чтобы владелец мог явно снять пароль. Пароль решает «кто вообще войдёт»
    # (в дополнение к ролям, которые решают «что участник может делать внутри»).
    password_hash = models.CharField('Пароль (хеш)', max_length=256, blank=True, default='')
    password_enabled = models.BooleanField('Требовать пароль при входе', default=False)

    # PROTECT, а не CASCADE: удаление учётки уносило вместе с ней ВСЕ её доски
    # со всем содержимым, молча и без спроса. Достаточно было отчислить старого
    # ученика, который когда-то сам создал доску. Теперь админка сначала
    # покажет, что мешает, и удаление придётся сделать осознанно.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='boards_owned', verbose_name='Владелец',
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='boards_joined',
        blank=True, verbose_name='Участники',
        help_text='Пользователи, присоединившиеся к доске по коду.',
    )

    # Необязательная привязка к уроку LMS — пригодится во Фазе 3.
    lesson = models.ForeignKey(
        'users.Lesson', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='boards', verbose_name='Урок (необязательно)',
    )

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Доска'
        verbose_name_plural = 'Доски'
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['code'])]

    def __str__(self):
        return self.title or f'Доска {self.code}'

    @classmethod
    def owned_count(cls, user):
        """Сколько досок у пользователя уже есть (только свои)."""
        if not (user and user.is_authenticated):
            return 0
        return cls.objects.filter(owner=user).count()

    @classmethod
    def quota_left(cls, user):
        """Сколько досок ещё можно создать. 0 — потолок достигнут."""
        return max(0, cls.MAX_PER_OWNER - cls.owned_count(user))

    @classmethod
    def create_for(cls, owner, *, title='', lesson=None):
        """Создать доску с уникальным кодом."""
        for _attempt in range(20):
            code = gen_board_code()
            if not cls.objects.filter(code=code).exists():
                break
        else:
            raise RuntimeError('Не удалось сгенерировать уникальный код доски')
        return cls.objects.create(owner=owner, code=code, title=title, lesson=lesson)

    def is_banned(self, user):
        """Убрал ли владелец этого человека с доски.
        Владельца и суперпользователя убрать нельзя."""
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or self.owner_id == user.pk:
            return False
        return str(user.pk) in [str(x) for x in (self.banned or [])]

    def can_access(self, user):
        """Может ли пользователь видеть/редактировать доску.
        Владелец, участник или суперпользователь — и только если не убран."""
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or self.owner_id == user.pk:
            return True
        if self.is_banned(user):
            return False
        return self.members.filter(pk=user.pk).exists()

    def set_password(self, raw):
        """Задать пароль доски; пустая строка — снять пароль."""
        raw = (raw or '').strip()
        if raw:
            self.password_hash = make_password(raw)
            self.password_enabled = True
        else:
            self.password_hash = ''
            self.password_enabled = False

    def verify_password(self, raw):
        """Верен ли введённый пароль (учитывается, только когда пароль включён)."""
        return bool(self.password_enabled and self.password_hash
                    and check_password((raw or '').strip(), self.password_hash))

    def needs_password(self, user):
        """Нужно ли этому пользователю ввести пароль перед входом.
        Владельца, суперюзера и уже присоединившихся участников не спрашиваем —
        пароль ограждает только НОВЫХ, кто ещё не в доске."""
        if not self.password_enabled:
            return False
        if not (user and user.is_authenticated):
            return True
        if user.is_superuser or self.owner_id == user.pk:
            return False
        return not self.members.filter(pk=user.pk).exists()

    def label_for(self, user):
        """Подпись участника для отображения соседям (ник/имя/логин)."""
        if not (user and user.is_authenticated):
            return 'Гость'
        nick = getattr(user, 'gamer_nickname', '') or ''
        return nick.strip() or user.username

    def role_for(self, user):
        """Действующая роль пользователя: владелец/суперюзер — всегда редактор;
        иначе личное назначение (self.roles), иначе роль по умолчанию."""
        if not (user and user.is_authenticated):
            return self.ROLE_VIEWER
        if user.is_superuser or self.owner_id == user.pk:
            return self.ROLE_EDITOR
        r = (self.roles or {}).get(str(user.pk))
        if r in (self.ROLE_VIEWER, self.ROLE_EDITOR):
            return r
        return self.default_role

    def can_edit(self, user):
        """Может ли пользователь менять холст (создавать/править/удалять)."""
        return self.role_for(user) == self.ROLE_EDITOR


class BoardElement(models.Model):
    """Один объект на холсте."""

    # Полный перечень типов объектов, которые кладёт на холст board.js.
    # Список нужен только для человекочитаемых подписей в админке — сам холст
    # присылает тип строкой и в этот список не заглядывает. Добавили на доске
    # новый инструмент — допишите строку сюда, иначе в админке будет сырой код.
    TYPE_CHOICES = [
        # рисование и оформление
        ('freehand', 'Рисунок от руки'),
        ('xcurve', 'Образ кривой при инверсии'),
        ('line', 'Линия'),
        ('arrow', 'Стрелка'),
        ('rect', 'Прямоугольник'),
        ('ellipse', 'Эллипс'),
        ('shape', 'Фигура'),
        # тексты и формулы
        ('text', 'Текст с формулами'),
        ('textbox', 'Обычный текст'),
        ('latex', 'Формула (LaTeX)'),
        # геометрия по точкам
        ('point', 'Точка'),
        ('segment', 'Отрезок'),
        ('ray', 'Луч'),
        ('gline', 'Прямая'),
        ('vector', 'Вектор'),
        ('perp', 'Перпендикуляр'),
        ('parallel', 'Параллель'),
        ('perpbis', 'Серединный перпендикуляр'),
        ('bisector', 'Биссектриса'),
        ('circle', 'Окружность'),
        ('circ', 'Окружность по точкам'),
        ('conic', 'Коника по 5 точкам'),
        ('polygon', 'Многоугольник'),
        ('regpoly', 'Правильный многоугольник'),
        ('angle', 'Угол'),
        ('mark', 'Пометка (засечки, прямой угол)'),
        ('venn', 'Диаграмма Венна'),
        ('measure', 'Измерение'),
        # координатное окно и функции
        ('frame', 'Математическое окно'),
        ('func', 'График функции'),
        ('implicit', 'Неявная кривая'),
        ('region', 'Область неравенства'),
        ('ftangent', 'Касательная'),
        ('farea', 'Площадь под графиком'),
        ('fintersect', 'Пересечение графиков'),
        # материалы и виджеты
        ('image', 'Изображение'),
        ('pdf', 'Страница PDF'),
        ('geogebra', 'ГеоГебра'),
        ('embed', 'Встроенная страница'),
        ('poll', 'Голосование'),
        ('screen', 'Демонстрация экрана'),
        ('table', 'Таблица'),
        ('kanban', 'Канбан'),
        ('timer', 'Таймер'),
        ('wheel', 'Колесо'),
        ('slider', 'Ползунок-параметр'),
        ('sticky', 'Стикер'),
        ('card', 'Карточка'),
        # служебное
        ('boardconfig', 'Настройки доски (фон)'),
    ]

    # Длина поля должна совпадать с проверкой в consumers.MAX_TYPE_LEN. Если
    # поле короче проверки, объект с длинным типом пройдёт контроль на сервере
    # и упадёт уже при записи в PostgreSQL — причём только на проде: SQLite
    # длину строк не проверяет и локально такую ошибку не покажет.
    MAX_TYPE_LEN = 24

    board = models.ForeignKey(
        Board, on_delete=models.CASCADE, related_name='elements',
        verbose_name='Доска',
    )
    # Идентификатор элемента, сгенерированный клиентом (UUID). По нему клиенты
    # ссылаются на элемент при обновлении/удалении — без round-trip к серверу.
    element_id = models.CharField('ID элемента', max_length=40, db_index=True)

    type = models.CharField('Тип', max_length=MAX_TYPE_LEN, choices=TYPE_CHOICES)
    # Вся геометрия и стиль: координаты, точки, цвет, толщина, текст, latex…
    data = models.JSONField('Данные', default=dict)
    z_index = models.IntegerField('Слой (z)', default=0)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='board_elements',
        verbose_name='Автор',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Элемент доски'
        verbose_name_plural = 'Элементы доски'
        ordering = ['z_index', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['board', 'element_id'],
                name='uniq_board_element_id',
            ),
        ]
        indexes = [models.Index(fields=['board', 'element_id'])]

    def __str__(self):
        return f'{self.get_type_display()} #{self.element_id} на {self.board}'

    def to_payload(self):
        """Представление для отправки клиенту по WebSocket."""
        return {
            'id': self.element_id,
            'type': self.type,
            'data': self.data,
            'z': self.z_index,
            'author': self.author_id,
        }


class BoardHistory(models.Model):
    """Общая сохраняемая история действий на доске (последние ~200 на доску).

    Каждая запись — одно действие любого участника: добавление, изменение или
    удаление элемента. Для удалённых храним payload, чтобы можно было восстановить.
    Показывается всем участникам и переживает перезагрузку.
    """

    ADD = 'add'
    UPDATE = 'update'
    DELETE = 'delete'
    ACTION_CHOICES = [(ADD, 'Добавлено'), (UPDATE, 'Изменено'), (DELETE, 'Удалено')]
    MAX_PER_BOARD = 200

    board = models.ForeignKey(
        Board, on_delete=models.CASCADE, related_name='history', verbose_name='Доска',
    )
    action = models.CharField('Действие', max_length=8, choices=ACTION_CHOICES)
    element_id = models.CharField('ID элемента', max_length=40, db_index=True)
    # Та же ёмкость, что у типа самого элемента. Иначе тип длиной 17–24
    # символа проходит проверку сервера, элемент сохраняется, а запись в
    # историю падает — и только на PostgreSQL: SQLite длину не проверяет,
    # локально такое не воспроизводится.
    element_type = models.CharField('Тип элемента', max_length=BoardElement.MAX_TYPE_LEN,
                                    blank=True, default='')
    # Полный payload элемента — нужен для ВОССТАНОВЛЕНИЯ удалённого (для add/update null).
    payload = models.JSONField('Снимок (для восстановления)', null=True, blank=True)
    by = models.IntegerField('Кто (user id)', null=True, blank=True)
    label = models.CharField('Кто (подпись)', max_length=80, blank=True, default='')
    created_at = models.DateTimeField('Когда', auto_now_add=True)

    class Meta:
        verbose_name = 'История доски'
        verbose_name_plural = 'История доски'
        ordering = ['id']
        indexes = [models.Index(fields=['board', 'id'])]

    def to_payload(self):
        return {
            'id': self.id,
            'action': self.action,
            'eid': self.element_id,
            'etype': self.element_type,
            'label': self.label,
            'ts': self.created_at.isoformat() if self.created_at else None,
            # payload отдаём только для удалённых (чтобы восстановить); иначе не грузим канал.
            'payload': self.payload if self.action == self.DELETE else None,
        }
