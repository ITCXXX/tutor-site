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

    # Две настройки планировщика, которые действительно нужны репетитору.
    # Остальные 21 весов FSRS трогать незачем — см. cards/srs.py.
    desired_retention = models.FloatField(
        'Желаемая прочность', default=0.9,
        help_text='Доля карточек, которые ученик должен помнить к моменту '
                  'повторения. Больше — надёжнее, но повторений больше.',
    )
    exam_date = models.DateField(
        'Дата экзамена', null=True, blank=True,
        help_text='Если указана, карточка никогда не назначается на «после» неё. '
                  'Без этого интервалы дорастают до десятков лет.',
    )

    # Дневные потолки. Без них колода в 300 карточек вываливает всё в первый
    # день, ученик тонет и бросает — это самая частая причина, по которой люди
    # уходят из Anki.
    new_per_day = models.IntegerField(
        'Новых карточек в день', default=20,
        help_text='Сколько незнакомых карточек показывать за сутки.',
    )
    reviews_per_day = models.IntegerField(
        'Повторений в день', default=200,
        help_text='Потолок на уже начатые карточки. 0 — без ограничения.',
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

    Поля state, step, stability, difficulty, due, last_review — ровно те, что
    просит планировщик FSRS; они кладутся в его объект Card и забираются
    обратно без переводчиков. reps и lapses он не использует, они для
    статистики и для отлова «пиявок» — карточек, которые ученик забывает снова
    и снова.
    """

    ПРЯМОЕ = 0
    ОБРАТНОЕ = 1
    DIRECTION_CHOICES = [
        (ПРЯМОЕ, 'Лицо → оборот'),
        (ОБРАТНОЕ, 'Оборот → лицо'),
    ]

    # Числа совпадают с fsrs.State, чтобы не переводить туда-сюда.
    ИЗУЧЕНИЕ = 1
    ПОВТОРЕНИЕ = 2
    ПЕРЕУЧИВАНИЕ = 3
    STATE_CHOICES = [
        (ИЗУЧЕНИЕ, 'Изучается'),
        (ПОВТОРЕНИЕ, 'На повторении'),
        (ПЕРЕУЧИВАНИЕ, 'Переучивается'),
    ]

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

    state = models.SmallIntegerField('Стадия', choices=STATE_CHOICES, default=ИЗУЧЕНИЕ)
    step = models.SmallIntegerField('Шаг обучения', null=True, blank=True, default=0)
    stability = models.FloatField('Прочность', null=True, blank=True)
    difficulty = models.FloatField('Трудность', null=True, blank=True)
    due = models.DateTimeField('Показать не раньше', default=timezone.now)
    last_review = models.DateTimeField('Последний показ', null=True, blank=True)

    reps = models.IntegerField('Показов', default=0)
    lapses = models.IntegerField('Забываний', default=0)
    # Когда карточку показали впервые. По этому полю считается дневной потолок
    # новых карточек — иначе пришлось бы каждый раз искать первую запись в
    # журнале.
    started_at = models.DateTimeField('Впервые показана', null=True, blank=True)
    suspended = models.BooleanField(
        'Отложена', default=False,
        help_text='Карточка не показывается, пока её не вернут в оборот.',
    )

    class Meta:
        verbose_name = 'Состояние карточки'
        verbose_name_plural = 'Состояния карточек'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'card', 'direction'], name='cards_state_unique',
            ),
        ]
        indexes = [
            # Главный запрос раздела: «что показать этому ученику сейчас».
            models.Index(fields=['user', 'due'], name='cards_state_due_idx'),
        ]

    def __str__(self):
        return '%s — %s' % (self.user, self.card)


class CardReview(models.Model):
    """Журнал повторений — по записи на каждый показ.

    Нужен не для отчётов: на этих записях обучается оптимизатор FSRS, который
    подгоняет 21 вес модели под конкретного ученика. Ему требуется минимум 512
    повторений И проставленная длительность ответа — если её не писать с
    первого дня, через полгода окажется, что настраивать не на чем.
    """

    ОПЯТЬ = 1
    ТРУДНО = 2
    ХОРОШО = 3
    ЛЕГКО = 4
    RATING_CHOICES = [
        (ОПЯТЬ, 'Опять'),
        (ТРУДНО, 'Трудно'),
        (ХОРОШО, 'Хорошо'),
        (ЛЕГКО, 'Легко'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='card_reviews', verbose_name='Ученик',
    )
    card = models.ForeignKey(
        Card, on_delete=models.CASCADE, related_name='reviews', verbose_name='Карточка',
    )
    direction = models.SmallIntegerField(
        'Направление', choices=CardState.DIRECTION_CHOICES, default=CardState.ПРЯМОЕ,
    )
    rating = models.SmallIntegerField('Оценка', choices=RATING_CHOICES)
    reviewed_at = models.DateTimeField('Когда', default=timezone.now)
    duration_ms = models.IntegerField(
        'Сколько думал, мс', null=True, blank=True,
        help_text='Нужно оптимизатору весов. Пишется автоматически.',
    )
    # Что ученик набрал, если колода просит вводить ответ. Хранится, чтобы
    # преподаватель видел, на чём именно спотыкаются.
    typed = models.CharField('Введённый ответ', max_length=300, blank=True)

    class Meta:
        verbose_name = 'Повторение'
        verbose_name_plural = 'Журнал повторений'
        ordering = ['-reviewed_at']
        indexes = [
            models.Index(fields=['user', 'reviewed_at'], name='cards_review_when_idx'),
        ]

    def __str__(self):
        return '%s: %s' % (self.card, self.get_rating_display())


class SchedulerWeights(models.Model):
    """Веса планировщика, подогнанные под конкретного ученика.

    FSRS идёт со стандартными весами, обученными на чужой большой выборке. По
    личной истории повторений их можно пересчитать: оптимизатор смотрит, где
    предсказание разошлось с тем, что ученик на самом деле вспомнил, и сдвигает
    21 число модели.

    Пока записи нет, планировщик берёт стандартные веса — это рабочее
    состояние, а не поломка. Считать своё имеет смысл от 512 повторений; на
    меньшем оптимизатор возвращает те же стандартные значения, и заводить
    запись незачем.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='scheduler_weights', verbose_name='Ученик',
    )
    parameters = models.JSONField('Веса модели', default=list)
    reviews_used = models.IntegerField('На скольких повторениях обучено', default=0)
    updated_at = models.DateTimeField('Пересчитано', auto_now=True)
    note = models.CharField('Пометка', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Веса планировщика'
        verbose_name_plural = 'Веса планировщика'

    def __str__(self):
        return 'Веса для %s (%d повторений)' % (self.user, self.reviews_used)
