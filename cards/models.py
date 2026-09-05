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

from django.conf import settings
from django.db import models
from django.utils import timezone


class Deck(models.Model):
    """Колода — набор карточек по одной теме."""

    # Кто видит колоду. Пользователей на сайте немного, поэтому промежуточных
    # степеней («по ссылке», «моей группе») не завожу: они потребовали бы
    # токенов и таблицы доступов ради шести человек.
    ЛИЧНАЯ = 'private'
    ОБЩАЯ = 'shared'
    ОТКРЫТАЯ = 'public'
    VISIBILITY_CHOICES = [
        (ЛИЧНАЯ, 'Личная — вижу только я'),
        (ОБЩАЯ, 'Общая — видят все, кто вошёл на сайт'),
        (ОТКРЫТАЯ, 'Открытая — видна и гостям'),
    ]

    # Вид материала решает две вещи: какой клавиатурой набирать ответ и как его
    # проверять. Математику проверяет users/answer_check.py (понимает дроби,
    # корни, промежутки), остальное — сравнение строк с прощением опечаток.
    МАТЕМАТИКА = 'math'
    ТЕКСТ = 'text'
    KIND_CHOICES = [
        (МАТЕМАТИКА, 'Математика — ответ проверяется как формула'),
        (ТЕКСТ, 'Обычный текст — слова, определения, перевод'),
    ]

    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='decks', verbose_name='Автор',
    )
    visibility = models.CharField(
        'Кому видна', max_length=10, choices=VISIBILITY_CHOICES, default=ЛИЧНАЯ,
    )
    kind = models.CharField(
        'Вид материала', max_length=10, choices=KIND_CHOICES, default=ТЕКСТ,
    )

    # Колода может жить сама по себе, а может быть частью урока: тогда она
    # показывается на странице урока и попадает в список ученика вместе с ним.
    lesson = models.ForeignKey(
        'users.Lesson', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='decks', verbose_name='Урок',
        help_text='Пусто — колода живёт в разделе карточек сама по себе.',
    )

    reverse_enabled = models.BooleanField(
        'Спрашивать и в обратную сторону', default=False,
        help_text='Кроме «лицо → оборот» появится «оборот → лицо». '
                  'Полезно для слов и переводов, вредно для определений.',
    )

    # Как задаётся вопрос. Три способа, потому что они тренируют разное:
    # переворот — узнавание, выбор — различение похожих, ввод — припоминание
    # с нуля. Для формул ввод почти всегда мучение, для слов — самое ценное.
    ПЕРЕВОРОТ = 'flip'
    ВЫБОР = 'choice'
    ВВОД = 'typed'
    ASK_CHOICES = [
        (ПЕРЕВОРОТ, 'Переворот — вспомнил и оценил себя'),
        (ВЫБОР, 'Выбор из вариантов'),
        (ВВОД, 'Ввод ответа'),
    ]
    ask_mode = models.CharField(
        'Как спрашивать', max_length=10, choices=ASK_CHOICES, default=ПЕРЕВОРОТ,
    )

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

    # Язык сторон. Нужен не для красоты: браузер по нему выбирает шрифт
    # (без этого китайские иероглифы рисуются японскими начертаниями),
    # отключает подстановку слов и правильно читает текст вслух.
    ЯЗЫКИ = [
        ('', 'Не указан'),
        ('ru', 'Русский'),
        ('en', 'Английский'),
        ('zh', 'Китайский'),
        ('de', 'Немецкий'),
        ('fr', 'Французский'),
        ('es', 'Испанский'),
        ('la', 'Латынь'),
    ]
    front_lang = models.CharField(
        'Язык лицевой стороны', max_length=8, choices=ЯЗЫКИ, blank=True, default='',
    )
    back_lang = models.CharField(
        'Язык оборота', max_length=8, choices=ЯЗЫКИ, blank=True, default='',
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

    def виден(self, user):
        """Может ли пользователь открыть колоду."""
        if self.visibility == self.ОТКРЫТАЯ:
            return True
        if not (user and user.is_authenticated):
            return False
        if self.visibility == self.ОБЩАЯ:
            return True
        return self.owner_id == user.id

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

    def язык_вопроса(self, направление):
        return self.front_lang if направление == CardState.ПРЯМОЕ else self.back_lang

    def язык_ответа(self, направление):
        return self.back_lang if направление == CardState.ПРЯМОЕ else self.front_lang


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

    def __str__(self):
        коротко = self.front.replace('\n', ' ')
        return коротко[:60] + ('…' if len(коротко) > 60 else '')

    def варианты_ответа(self, направление):
        """Все написания, которые засчитываются при данном направлении."""
        эталон = self.back if направление == CardState.ПРЯМОЕ else self.front
        ещё = [с.strip() for с in self.accepted.splitlines() if с.strip()]
        # Дополнительные написания относятся к обороту: в обратную сторону
        # спрашивают лицевую, и они там ни при чём.
        return [эталон] + (ещё if направление == CardState.ПРЯМОЕ else [])

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
