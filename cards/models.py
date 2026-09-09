# -*- coding: utf-8 -*-
"""Модели раздела карточек — аналога Quizlet и Anki.

Почему отдельные модели, а не расширение Assignment: задание намертво привязано
к уроку (обязательный внешний ключ на Lesson), и колода карточек потребовала бы
фиктивных курса, модуля и урока. Но главное — ни одна существующая модель не
хранит того единственного, ради чего затевается интервальное повторение: КОГДА
показать эту карточку этому ученику снова. StudentProgress и GeneratedProblem
считают «сколько раз», а нужно «когда».

Устройство почти как в Anki, только без лишнего слоя:

    Deck ── Card ── CardState (у каждого ученика своё) ── CardReview (журнал)

Card — это «заметка»: лицевая и оборотная стороны, один факт. Направление
(лицо→оборот или оборот→лицо) не отдельная запись, а поле в CardState, поэтому
обратные карточки не удваивают таблицу карточек и правятся в одном месте.
"""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .richtext import очистить, текстом


class Deck(models.Model):
    """Колода — набор карточек по одной теме."""

    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='decks', verbose_name='Автор',
    )
    # Доступ по ссылке вместо степеней видимости. Ссылку дают тому, кому надо,
    # и это покрывает всё, ради чего заводили «личная / общая / открытая»:
    # своё видно автору, чужое — тому, кому дали ссылку.
    share_token = models.CharField(
        'Ключ ссылки', max_length=22, unique=True, blank=True,
        help_text='Часть адреса, по которому колоду открывают другие.',
    )

    reverse_enabled = models.BooleanField(
        'Спрашивать и в обратную сторону', default=False,
        help_text='Кроме «лицо → оборот» появится «оборот → лицо». '
                  'Полезно для слов и переводов, вредно для определений.',
    )

    # Способ вопроса — переворот, выбор или ввод — колода не назначает: его
    # выбирает тот, кто садится заниматься, и меняет посреди захода. Значения
    # живут в cards/views.py рядом с экраном, которому они нужны.

    # Кто выносит вердикт по набранному ответу. Автоматическая проверка строга
    # и не знает синонимов; на определениях и переводах она чаще мешает, чем
    # помогает, — там честнее показать эталон и спросить самого ученика.
    АВТОМАТ = 'auto'
    САМ = 'self'
    CHECK_CHOICES = [
        (АВТОМАТ, 'Сверяет сайт'),
        (САМ, 'Показать верный ответ, ученик решает сам'),
    ]
    check_mode = models.CharField(
        'Кто проверяет ввод', max_length=10, choices=CHECK_CHOICES, default=АВТОМАТ,
        help_text='Имеет значение только при вводе ответа.',
    )

    # Сколько карточек за один подход. Семь — потому что столько человек
    # держит в голове разом и столько помещается на экран телефона; но число
    # оставлено настраиваемым, потому что у списка из двадцати слов и у списка
    # из двухсот формул разный удобный шаг.
    round_size = models.IntegerField(
        'Карточек за раунд', default=7,
        help_text='Сколько карточек показывать за один подход. '
                  'В просмотре и тесте раундов нет.',
    )

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Изменена', auto_now=True)

    class Meta:
        verbose_name = 'Колода карточек'
        verbose_name_plural = 'Колоды карточек'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.share_token:
            # 22 символа base64 — это 128 бит случайности. Ссылку нельзя
            # подобрать перебором, а длина такая же, как у обычного адреса.
            self.share_token = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    def виден(self, user):
        """Может ли пользователь открыть колоду без ключа из ссылки.

        Ключ проверяется отдельно, в самой вьюхе: он приходит из адреса, а не
        из пользователя.
        """
        if not (user and user.is_authenticated):
            return False
        if self.owner_id == user.id:
            return True
        return DeckShare.objects.filter(deck=self, user=user).exists()

    def правит(self, user):
        """Может ли пользователь менять колоду и её карточки."""
        if not (user and user.is_authenticated):
            return False
        return self.owner_id == user.id or user.is_superuser

    @property
    def направления(self):
        """Сколько карточек порождает одна заметка: одна или две."""
        return (CardState.ПРЯМОЕ, CardState.ОБРАТНОЕ) if self.reverse_enabled \
            else (CardState.ПРЯМОЕ,)


class DeckShare(models.Model):
    """Кому колода открылась по ссылке.

    Без этой записи ссылка работала бы ровно один раз: ученик открыл, позанимался,
    закрыл вкладку — и колода снова недоступна, потому что в списке она у него не
    появляется. Запись заводится в тот момент, когда человек впервые открыл
    правильную ссылку, и дальше колода просто лежит у него в разделе.
    """

    deck = models.ForeignKey(
        Deck, on_delete=models.CASCADE, related_name='shares', verbose_name='Колода',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='deck_shares', verbose_name='Кому открыта',
    )
    opened_at = models.DateTimeField('Открыта', auto_now_add=True)

    class Meta:
        verbose_name = 'Доступ по ссылке'
        verbose_name_plural = 'Доступы по ссылке'
        constraints = [
            models.UniqueConstraint(fields=['deck', 'user'], name='cards_share_unique'),
        ]

    def __str__(self):
        return '%s → %s' % (self.deck, self.user)


class Card(models.Model):
    """Одна карточка: лицевая сторона, оборот и необязательная подсказка."""

    deck = models.ForeignKey(
        Deck, on_delete=models.CASCADE, related_name='cards', verbose_name='Колода',
    )
    front = models.TextField(
        'Лицевая сторона', help_text='Вопрос. Формулы — в долларах: $x^2$.',
    )
    back = models.TextField('Оборот', help_text='Ответ. Коротко, один факт.')
    hint = models.TextField(
        'Подсказка', blank=True,
        help_text='Необязательно: пример, уточнение или разбор.',
    )
    # Дополнительные написания ответа, которые тоже засчитываются. По одному в
    # строке. Нужны там, где ответ верен в нескольких формах: «биссектриса» и
    # «биссектриса угла».
    accepted = models.TextField(
        'Ещё засчитывать', blank=True,
        help_text='Другие верные написания ответа, по одному в строке.',
    )
    # Заведомо неверные ответы для вопроса с вариантами. Свои неверные ответы
    # ценнее случайных из колоды: правдоподобная ошибка проверяет, отличает ли
    # ученик её от правильного, а чужая тема отсеивается на глаз.
    distractors = models.TextField(
        'Неверные варианты', blank=True,
        help_text='Для вопросов с выбором. По одному в строке, сколько угодно.',
    )
    order = models.IntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Карточка'
        verbose_name_plural = 'Карточки'
        ordering = ['order', 'id']

    def save(self, *args, **kwargs):
        """Единственная точка, где разметка карточки становится безопасной.

        Чистить при показе было бы легче забыть: шаблонов много, а save() один.
        Массовое добавление идёт мимо save() (bulk_create), поэтому там чистка
        вызывается явно — см. cards/views.py.
        """
        self.front = очистить(self.front)
        self.back = очистить(self.back)
        self.hint = очистить(self.hint)
        self.distractors = '\n'.join(
            очистить(с) for с in (self.distractors or '').splitlines() if с.strip()
        )
        super().save(*args, **kwargs)

    def __str__(self):
        коротко = текстом(self.front).replace('\n', ' ')
        return коротко[:60] + ('…' if len(коротко) > 60 else '')

    def варианты_ответа(self, направление):
        """Все написания, которые засчитываются при данном направлении.

        Возвращается голый текст: проверка ответа не должна знать, что слово
        было выделено жирным. Ученик набирает «Париж», а в базе может лежать
        «<b>Париж</b>».
        """
        эталон = self.back if направление == CardState.ПРЯМОЕ else self.front
        ещё = [с.strip() for с in self.accepted.splitlines() if с.strip()]
        # Дополнительные написания относятся к обороту: в обратную сторону
        # спрашивают лицевую, и они там ни при чём.
        всё = [эталон] + (ещё if направление == CardState.ПРЯМОЕ else [])
        return [текстом(в) for в in всё]

    def неверные(self):
        """Заведомо неверные ответы, заданные автором карточки."""
        return [с.strip() for с in self.distractors.splitlines() if с.strip()]


class CardState(models.Model):
    """Что сайт помнит про пару «ученик — карточка».

    Помнит немного и намеренно: в какой секции карточка лежит и два счётчика.
    Раскладывает по секциям сам ученик, кнопками. Раньше здесь жил планировщик
    со сроками и прочностью памяти — он решал за ученика, когда показать
    карточку снова, и объяснял это интервалами вида «через 10 минут». От этого
    отказались: человек лучше знает, что ему трудно, а «через сколько минут»
    ему знать незачем.
    """

    ПРЯМОЕ = 0
    ОБРАТНОЕ = 1
    DIRECTION_CHOICES = [
        (ПРЯМОЕ, 'Лицо → оборот'),
        (ОБРАТНОЕ, 'Оборот → лицо'),
    ]

    # Секции. Ноль — «ещё не разбирал»: там лежат все карточки, пока ученик
    # их не разложил. Дальше от трудного к лёгкому; повторение берёт две
    # трудные, заучивание начинает с самой трудной.
    НЕ_РАЗОБРАНА = 0
    ТРУДНО = 1
    СЛОЖНО = 2
    НОРМАЛЬНО = 3
    ЛЕГКО = 4
    SECTION_CHOICES = [
        (НЕ_РАЗОБРАНА, 'Не разобрано'),
        (ТРУДНО, 'Трудно'),
        (СЛОЖНО, 'Сложно'),
        (НОРМАЛЬНО, 'Нормально'),
        (ЛЕГКО, 'Легко'),
    ]
    # Секции, из которых берёт повторение.
    ТРУДНЫЕ = (ТРУДНО, СЛОЖНО)
    # Порядок показа в заучивании: сначала самое трудное, неразобранное следом.
    ПОРЯДОК_ЗАУЧИВАНИЯ = (ТРУДНО, СЛОЖНО, НЕ_РАЗОБРАНА, НОРМАЛЬНО, ЛЕГКО)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='card_states', verbose_name='Ученик',
    )
    card = models.ForeignKey(
        Card, on_delete=models.CASCADE, related_name='states', verbose_name='Карточка',
    )
    direction = models.SmallIntegerField(
        'Направление', choices=DIRECTION_CHOICES, default=ПРЯМОЕ,
    )

    section = models.SmallIntegerField(
        'Секция', choices=SECTION_CHOICES, default=НЕ_РАЗОБРАНА,
    )
    shows = models.IntegerField('Показов', default=0)
    misses = models.IntegerField('Ошибок', default=0)

    class Meta:
        verbose_name = 'Состояние карточки'
        verbose_name_plural = 'Состояния карточек'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'card', 'direction'], name='cards_state_unique',
            ),
        ]
        indexes = [
            # Главный запрос раздела: «что у этого ученика лежит в этой секции».
            models.Index(fields=['user', 'section'], name='cards_state_sect_idx'),
        ]

    def __str__(self):
        return '%s — %s' % (self.user, self.card)
