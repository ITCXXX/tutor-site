# users/models.py
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import URLValidator
from django.utils import timezone

from .uploads import validate_homework_file

# --------------------------------------------------
# Существующие модели пользователей (оставляем как есть)
# --------------------------------------------------
class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('Требуется указать username')
        
        user = self.model(
            username=username,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, password, **extra_fields)

class User(AbstractBaseUser):
    # Основные поля
    username = models.CharField('Логин', max_length=50, unique=True)

    # Дублёр пароля в открытом виде — чтобы преподаватель мог напомнить ученику.
    # Заполняется автоматически при каждом set_password().
    plaintext_password = models.CharField('Пароль (видно админу)', max_length=128, blank=True)

    # Роли
    ROLE_CHOICES = [
        ('student', 'Ученик'),
        ('teacher', 'Преподаватель'),
        ('admin', 'Администратор'),
    ]
    role = models.CharField('Роль', max_length=10, choices=ROLE_CHOICES, default='student')

    # Статусы
    is_active = models.BooleanField('Активен', default=True)
    is_staff = models.BooleanField('Персонал', default=False)
    is_superuser = models.BooleanField('Суперпользователь', default=False)

    # Доступ к разделу игр (UTTT и т.п.)
    can_play_games = models.BooleanField(
        'Доступ к разделу игр', default=False,
        help_text='Если включено, пользователь видит /games/ и может создавать/'
                  'играть партии. Не влияет на учебные курсы.',
    )
    gamer_nickname = models.CharField(
        'Ник для игр', max_length=30, blank=True, default='',
        help_text='Имя, под которым пользователь будет виден сопернику в '
                  'разделе игр. Если пусто — используется username.',
    )

    # Даты
    date_joined = models.DateTimeField('Дата регистрации', default=timezone.now)
    last_login = models.DateTimeField('Последний вход', auto_now=True)

    # Менеджер
    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-date_joined']

    def set_password(self, raw_password):
        super().set_password(raw_password)
        # plaintext-копия пароля нужна только для УЧЕНИКОВ:
        # преподаватель может подсмотреть в админке, если ученик забыл.
        # Для админов/преподавателей хранить открытый пароль — лишний риск
        # (утечка БД = утечка административных паролей), поэтому пусто.
        if self.is_staff or self.is_superuser:
            self.plaintext_password = ''
        else:
            self.plaintext_password = raw_password or ''

    @property
    def display(self):
        """Как звать человека в интерфейсе: имя из профиля, иначе логин.

        Профиля может не быть вовсе (например, у администратора), а
        display_name может оказаться пустой строкой — оба случая ведут к логину.
        """
        for имя in ('student_profile', 'teacher_profile'):
            try:
                p = getattr(self, имя)
            except ObjectDoesNotExist:
                continue
            if p and (p.display_name or '').strip():
                return p.display_name.strip()
        return self.username

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def has_perm(self, perm, obj=None):
        return self.is_superuser
    
    def has_module_perms(self, app_label):
        return self.is_superuser

class StudentProfile(models.Model):
    """Профиль ученика"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile',
                                limit_choices_to={'role': 'student'})
    display_name = models.CharField('Имя для отображения', max_length=100)
    real_name = models.CharField('Полное имя', max_length=200, blank=True)

    grade = models.CharField('Класс/Курс', max_length=20, blank=True)
    goals = models.TextField('Цели обучения', blank=True)
    notes = models.TextField('Заметки репетитора', blank=True)
    level = models.CharField('Уровень', max_length=50, blank=True, default='начальный')

    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='students',
        limit_choices_to={'role': 'teacher'},
        verbose_name='Преподаватель',
    )

    class Meta:
        verbose_name = 'Профиль ученика'
        verbose_name_plural = 'Профили учеников'

    def __str__(self):
        return self.display_name


class TeacherProfile(models.Model):
    """Профиль преподавателя"""
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='teacher_profile',
        limit_choices_to={'role': 'teacher'},
    )
    display_name = models.CharField('Имя для отображения', max_length=100)
    real_name = models.CharField('Полное имя', max_length=200, blank=True)
    bio = models.TextField('О себе', blank=True)
    specialization = models.CharField('Специализация', max_length=200, blank=True,
                                      help_text='Например: математика, физика, ЕГЭ профильная')

    class Meta:
        verbose_name = 'Профиль преподавателя'
        verbose_name_plural = 'Профили преподавателей'

    def __str__(self):
        return self.display_name

# --------------------------------------------------
# НОВЫЕ МОДЕЛИ ДЛЯ КУРСОВ (добавляем в конец)
# --------------------------------------------------
class StudentLink(models.Model):
    """Ссылка, которую преподаватель кладёт ученику в кабинет.

    student заполнен — ссылка личная, видит только он.
    student пуст — общая: её видят все ученики этого преподавателя. Так
    «ссылка на нашу доску» заводится один раз, а не по разу на каждого.
    """
    teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='given_links',
        limit_choices_to={'role': 'teacher'}, verbose_name='Преподаватель',
    )
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='links',
        null=True, blank=True, limit_choices_to={'role': 'student'},
        verbose_name='Ученик',
        help_text='Пусто — ссылку увидят все ученики этого преподавателя.',
    )
    title = models.CharField('Заголовок', max_length=120)
    # Только http и https. Django по умолчанию пропускает ещё ftp, а без
    # проверки вовсе в поле прошёл бы javascript: — и ссылка выполняла бы
    # чужой код в браузере ученика.
    url = models.URLField(
        'Адрес', max_length=500,
        validators=[URLValidator(schemes=['http', 'https'])],
    )
    order = models.IntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Добавлена', auto_now_add=True)

    class Meta:
        verbose_name = 'Ссылка для ученика'
        verbose_name_plural = 'Ссылки для учеников'
        ordering = ['order', 'id']

    def __str__(self):
        кому = self.student.username if self.student_id else 'всем'
        return f'{self.title} ({кому})'


class Course(models.Model):
    """Основная модель курса"""
    TRACKING_AUTO = 'auto'
    TRACKING_MANUAL = 'manual'
    TRACKING_HOMEWORK = 'homework'
    TRACKING_CHOICES = [
        (TRACKING_AUTO, 'Автоматически (ученики решают на сайте)'),
        (TRACKING_MANUAL, 'Задачник (преподаватель отмечает)'),
        (TRACKING_HOMEWORK, 'Курс с ДЗ (преподаватель добавляет задачи, ученик вводит ответ)'),
    ]

    title = models.CharField('Название курса', max_length=200)
    slug = models.SlugField('URL-адрес', unique=True, help_text='Например: geometry-9-class')
    short_description = models.TextField('Краткое описание', max_length=300, blank=True)
    full_description = models.TextField('Подробное описание', blank=True)
    cover_image = models.ImageField('Обложка курса', upload_to='courses/covers/', blank=True, null=True)
    is_active = models.BooleanField('Активен', default=False)
    order = models.IntegerField('Порядок отображения', default=0)
    tracking_mode = models.CharField(
        'Режим прогресса', max_length=10, choices=TRACKING_CHOICES, default=TRACKING_AUTO,
        help_text='manual — задачник, преподаватель сам отмечает решённые задачи',
    )
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_courses',
        limit_choices_to={'role': 'teacher'},
        verbose_name='Владелец',
        help_text='Для задачников — преподаватель, который ведёт курс. У общих курсов пусто.',
    )
    is_public = models.BooleanField(
        'Публичный (в общем каталоге)', default=False,
        help_text='True — виден всем в каталоге, открытая запись (общие ОГЭ-курсы). '
                  'False — приватный: только владелец и записанные им ученики.',
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title

    @property
    def is_manual(self):
        return self.tracking_mode == self.TRACKING_MANUAL

    @property
    def is_homework(self):
        return self.tracking_mode == self.TRACKING_HOMEWORK

    @property
    def is_owned(self):
        """Приватный курс: скрыт от публичного каталога, привязан к владельцу."""
        return not self.is_public

class Module(models.Model):
    """Модуль курса (раздел)"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField('Название модуля', max_length=200)
    description = models.TextField('Описание модуля', blank=True)
    order = models.IntegerField('Порядок в курсе', default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Lesson(models.Model):
    """Урок в модуле"""
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField('Название урока', max_length=200)
    lesson_type = models.CharField('Тип урока', max_length=20, choices=[
        ('video', 'Видеоурок'),
        ('text', 'Текстовый урок'),
        ('hybrid', 'Гибридный (видео + текст)'),
        ('practice', 'Практическое занятие'),
    ], default='hybrid')
    content = models.TextField('Теоретический материал (текст)', blank=True)
    video_url = models.URLField('Ссылка на видео (YouTube/Vimeo)', blank=True)
    duration = models.IntegerField('Длительность (минут)', default=0, help_text='Для видеоуроков')
    order = models.IntegerField('Порядок в модуле', default=0)
    is_free = models.BooleanField('Бесплатный урок', default=False)
    # Срок сдачи домашки. На уроке, а не на задаче: домашка задаётся уроком
    # целиком. Дата без времени — репетитор думает днями, а лишняя точность
    # притащила бы вопросы про часовые пояса.
    due_date = models.DateField(
        'Срок сдачи', null=True, blank=True,
        help_text='Только для курсов с ДЗ. Пусто — без срока.',
    )
    # Мягкий срок выше говорит «поздно», эта дата говорит «поздно, всё».
    # После неё сервер работу не принимает вовсе.
    cutoff_date = models.DateField(
        'Приём закрыт после', null=True, blank=True,
        help_text='После этой даты работу уже не принять. Пусто — принимаем и с опозданием.',
    )

    def accepts_submissions(self, today=None):
        """Можно ли ещё сдавать. Отсечка включительно: указан день — до
        конца этого дня принимаем."""
        if not self.cutoff_date:
            return True
        from django.utils import timezone as _tz
        return (today or _tz.localdate()) <= self.cutoff_date

    def is_late(self, when=None):
        """Считается ли сдача в этот день опозданием."""
        if not self.due_date:
            return False
        from django.utils import timezone as _tz
        return (when or _tz.localdate()) > self.due_date

    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.title

# Сначала объявляем MaterialCategory и Material, чтобы Assignment мог ссылаться на них
class MaterialCategory(models.Model):
    """Категория методических материалов"""
    title = models.CharField('Название категории', max_length=200)
    slug = models.SlugField('URL-адрес', unique=True)
    description = models.TextField('Описание', blank=True)
    icon = models.CharField('Иконка', max_length=50, default='📚', 
                           help_text='Эмодзи или название класса иконки')
    order = models.IntegerField('Порядок отображения', default=0)
    
    class Meta:
        verbose_name = 'Категория материалов'
        verbose_name_plural = 'Категории материалов'
        ordering = ['order', 'title']
    
    def __str__(self):
        return self.title

class Material(models.Model):
    """Методический материал"""
    category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, 
                                 related_name='materials', verbose_name='Категория')
    title = models.CharField('Название материала', max_length=200)
    description = models.TextField('Описание', blank=True)
    file = models.FileField('Файл', upload_to='materials/files/', blank=True, null=True)
    external_url = models.URLField('Внешняя ссылка', blank=True, 
                                   help_text='Если материал расположен на другом сайте')
    material_type = models.CharField('Тип материала', max_length=20, choices=[
        ('pdf', 'PDF документ'),
        ('video', 'Видео'),
        ('article', 'Статья'),
        ('presentation', 'Презентация'),
        ('other', 'Другое'),
    ], default='pdf')
    is_free = models.BooleanField('Бесплатный', default=False)
    order = models.IntegerField('Порядок в категории', default=0)
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)
    page_count = models.IntegerField('Количество страниц', default=0, blank=True)
    thumbnail = models.ImageField('Миниатюра', upload_to='materials/thumbnails/', 
                                  blank=True, null=True)
    
    class Meta:
        verbose_name = 'Методический материал'
        verbose_name_plural = 'Методические материалы'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return self.title

# Объявляем ProblemGenerator перед Assignment
class ProblemGenerator(models.Model):
    """
    Модель для хранения информации о генераторе задач.
    Каждый генератор связан с одним прототипом задачи.
    """
    # Типы генераторов (для будущего расширения)
    GENERATOR_TYPES = [
        ('python_function', 'Python функция'),
        ('template_based', 'Шаблон с подстановкой'),
    ]
    
    name = models.CharField('Название генератора', max_length=200)
    generator_type = models.CharField('Тип генератора', max_length=20, choices=GENERATOR_TYPES, default='python_function')
    
    # Python код генератора (если тип 'python_function')
    python_code = models.TextField(
        'Код Python генератора', 
        blank=True,
        help_text='Функция должна возвращать словарь с параметрами задачи'
    )
    
    # Или шаблон (если тип 'template_based')
    template_text = models.TextField('Шаблон задачи', blank=True)
    
    # Конфигурация (параметры для генерации)
    config = models.JSONField('Конфигурация', default=dict, blank=True)
    
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
    
    class Meta:
        verbose_name = 'Генератор задач'
        verbose_name_plural = 'Генераторы задач'
    
    def __str__(self):
        return self.name
    
    def execute_generator(self, student=None, selected_generators=None):
        """Выполняет генератор и возвращает данные задачи.

        Код генераторов вынесен из БД в репозиторий (users/generators/g<id>.py)
        и вызывается по id — БЕЗ exec() кода из БД (пункт 6). Поле python_code
        сохранено как бэкап/для admin, но больше НЕ исполняется: источник истины
        для исполнения — файлы users/generators/. Новые генераторы добавлять
        файлом g<id>.py с функцией generate_task().

        selected_generators оставлен для совместимости со старыми вызовами.
        """
        if self.generator_type == 'python_function':
            from .generators import get_generator
            try:
                return get_generator(self.id)()
            except Exception as e:
                # Тестовая задача, если генератор недоступен/сломан
                # (например, legacy-генератор без generate_task).
                return {
                    'error': str(e),
                    'test_data': {
                        'numbers': (1, 2),
                        'denominator': 10,
                        'fractions': [(3, 10), (5, 10), (7, 10), (9, 10)],
                        'correct_answer': 1,
                        'condition': 'Тестовая задача (генератор не работает)'
                    }
                }
        else:
            # Для шаблонных генераторов
            return {'template': self.template_text, 'config': self.config}
        
# Теперь объявляем Assignment, который может ссылаться на Material и ProblemGenerator
class Assignment(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Урок',
    )
    title = models.CharField('Название задания', max_length=200)
    description = models.TextField('Описание')
    assignment_type = models.CharField(
        'Тип задания',
        max_length=20,
        choices=[
            ('test', 'Тест'),
            ('text_input', 'Текстовый ответ'),
            ('file_upload', 'Загрузка файла'),
            ('code', 'Код'),
        ],
        default='test',
    )
    points = models.IntegerField('Баллы', default=1)
    order = models.IntegerField('Порядок в уроке', default=0)

    # НОВЫЕ ПОЛЯ:
    problem_generator = models.ForeignKey(
        ProblemGenerator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
        verbose_name='Генератор задач',
        help_text='Если задание использует генератор задач',
    )

    ANSWER_TYPE_CHOICES = [
        ('single_choice', 'Выбор ответа 1-4'),
        ('decimal_input', 'Ввод десятичной дроби'),
        ('text_input', 'Текстовый ответ'),
    ]
    answer_type = models.CharField(
        'Тип ответа',
        max_length=20,
        choices=ANSWER_TYPE_CHOICES,
        default='decimal_input',
    )

    required_correct = models.IntegerField(
        'Требуется правильных решений',
        default=10,
        help_text='Сколько задач нужно решить правильно для прохождения',
    )

    correct_answer = models.CharField(
        'Правильный ответ (для ДЗ)',
        max_length=255, blank=True,
        help_text='Используется в курсах с ДЗ. Сравнение числовое, если число; иначе строкой.',
    )

    image = models.ImageField(
        'Картинка к задаче (для ДЗ)',
        upload_to='hw/', blank=True, null=True,
        help_text='Рисунок/чертёж к условию. Показывается над текстом условия.',
    )

    requires_review = models.BooleanField(
        'Требует ручной проверки',
        default=False,
        help_text='Если включено — ученик отправляет развёрнутое решение (текст/фото), '
                  'правильный ответ не нужен, задачу проверяет преподаватель.',
    )

    theory_material = models.ForeignKey(
        Material, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Теоретический материал'
    )
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Задание'
        verbose_name_plural = 'Задания'

    def __str__(self):
        return self.title

class TestQuestion(models.Model):
    """Вопрос для теста (автопроверка)"""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField('Текст вопроса')
    image_svg = models.TextField('SVG иллюстрация', blank=True,
                                 help_text='Встроенный SVG-код для задач с картинкой')
    image = models.ImageField('Картинка к вопросу', upload_to='prototypes/',
                              blank=True, null=True,
                              help_text='Загруженная картинка (приоритетнее image_svg).')
    question_type = models.CharField('Тип вопроса', max_length=20, choices=[
        ('single_choice', 'Один правильный ответ'),
        ('multiple_choice', 'Несколько правильных ответов'),
        ('true_false', 'Верно/Неверно'),
        ('number', 'Числовой ответ'),
    ], default='single_choice')
    explanation = models.TextField('Объяснение ответа', blank=True,
                                   help_text='Показывается после ответа')
    order = models.IntegerField('Порядок в задании', default=0)
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Вопрос теста'
        verbose_name_plural = 'Вопросы тестов'
    
    def __str__(self):
        return f"Вопрос: {self.question_text[:50]}..."

class AnswerOption(models.Model):
    """Вариант ответа для вопроса"""
    question = models.ForeignKey(TestQuestion, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField('Текст ответа', max_length=500)
    is_correct = models.BooleanField('Правильный ответ', default=False)
    order = models.IntegerField('Порядок отображения', default=0)
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
    
    def __str__(self):
        return f"{self.text[:50]}... ({'✓' if self.is_correct else '✗'})"
    
class Enrollment(models.Model):
    """Запись ученика на курс"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments',
                                limit_choices_to={'role': 'student'})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField('Дата записи', auto_now_add=True)
    is_active = models.BooleanField('Активна', default=True)
    progress = models.IntegerField('Прогресс (%)', default=0, help_text='Процент прохождения курса')
    last_accessed = models.DateTimeField('Последний доступ', auto_now=True)
    
    class Meta:
        verbose_name = 'Запись на курс'
        verbose_name_plural = 'Записи на курсы'
        unique_together = ['student', 'course']  # один ученик может записаться на курс только один раз
    
    def __str__(self):
        return f'{self.student} -> {self.course}'

# =========== МОДЕЛИ ДЛЯ ФУНКЦИЙ PDF-ПРОСМОТРЩИКА ===========

class PDFBookmark(models.Model):
    """
    Закладка пользователя на конкретной странице PDF-материала.
    Один пользователь может иметь только одну закладку на страницу в каждом материале.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='pdf_bookmarks'  # Обратная связь: user.pdf_bookmarks.all()
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        verbose_name='Материал',
        related_name='bookmarks'  # Обратная связь: material.bookmarks.all()
    )
    page_number = models.IntegerField('Номер страницы')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    comment = models.TextField('Комментарий', blank=True, null=True, help_text='Необязательная заметка к закладке')

    class Meta:
        verbose_name = 'Закладка в PDF'
        verbose_name_plural = 'Закладки в PDF'
        # Уникальная связка: пользователь + материал + страница
        unique_together = ['user', 'material', 'page_number']
        ordering = ['material', 'page_number']

    def __str__(self):
        return f'Закладка: {self.user.username} -> {self.material.title} (стр. {self.page_number})'


class PDFAnnotation(models.Model):
    """
    Аннотация пользователя (выделение текста, рисование, текстовая заметка) в PDF.
    Содержимое аннотации хранится в гибком JSON-формате.
    """
    # Константы для типов аннотаций
    TYPE_HIGHLIGHT = 'highlight'
    TYPE_NOTE = 'note'
    TYPE_DRAWING = 'drawing'
    ANNOTATION_TYPES = [
        (TYPE_HIGHLIGHT, 'Выделение текста'),
        (TYPE_NOTE, 'Текстовая заметка'),
        (TYPE_DRAWING, 'Рисунок или пометка'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='pdf_annotations'
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        verbose_name='Материал',
        related_name='annotations'
    )
    page_number = models.IntegerField('Номер страницы')
    annotation_type = models.CharField(
        'Тип аннотации',
        max_length=20,
        choices=ANNOTATION_TYPES,
        default=TYPE_HIGHLIGHT
    )
    # JSONField позволяет хранить координаты (x, y, width, height), цвет, текст заметки и т.д.
    content = models.JSONField('Содержание аннотации', default=dict)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Аннотация в PDF'
        verbose_name_plural = 'Аннотации в PDF'
        ordering = ['material', 'page_number', 'created_at']

    def __str__(self):
        return f'{self.get_annotation_type_display()}: {self.user.username} -> {self.material.title}'
        
class GeneratedProblem(models.Model):
    """
    Конкретная сгенерированная задача для ученика.
    Каждый ученик получает свою уникальную задачу.
    """
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='generated_problems',
        verbose_name='Прототип задания'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='generated_problems',
        verbose_name='Ученик',
        limit_choices_to={'role': 'student'}
    )
    
    # Данные задачи (параметры, сгенерированные генератором)
    task_data = models.JSONField(
        'Данные задачи',
        default=dict,
        help_text='JSON с параметрами сгенерированной задачи'
    )
    
    # Текст условия (для отображения)
    condition_text = models.TextField(
        'Текст условия',
        blank=True,
        help_text='Человекочитаемый текст условия задачи'
    )
    
    # Правильный ответ (может быть числом, строкой или списком)
    correct_answer = models.JSONField(
        'Правильный ответ',
        help_text='Правильный ответ в формате JSON'
    )
    
    # Статистика решения
    attempts_count = models.IntegerField('Количество попыток', default=0)
    correct_attempts = models.IntegerField('Правильные попытки', default=0)
    
    # Статус задачи
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('solved', 'Решена'),
        ('failed', 'Не решена'),
    ]
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Временные метки
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    last_attempt_at = models.DateTimeField('Последняя попытка', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Сгенерированная задача'
        verbose_name_plural = 'Сгенерированные задачи'
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['assignment', 'student']),
        ]
    
    def __str__(self):
        return f"Задача {self.id} для {self.student.username}"
    
    def get_progress_percentage(self):
        """Возвращает процент правильных решений"""
        if self.attempts_count == 0:
            return 0
        return (self.correct_attempts / self.attempts_count) * 100
    
    def is_completed(self):
        """Проверяет, пройдено ли задание"""
        return self.correct_attempts >= self.assignment.required_correct

class ProblemAttempt(models.Model):
    """
    Попытка решения задачи учеником.
    Хранится для статистики и анализа ошибок.
    """
    problem = models.ForeignKey(
        GeneratedProblem,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Задача'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Ученик'
    )
    
    # Ответ ученика
    user_answer = models.TextField('Ответ ученика')
    
    # Проверенный ответ (после нормализации)
    normalized_answer = models.JSONField(
        'Нормализованный ответ',
        null=True,
        blank=True
    )
    
    # Результат проверки
    is_correct = models.BooleanField('Правильно', default=False)
    
    # Дополнительная информация
    time_spent_seconds = models.IntegerField('Время решения (сек)', default=0)
    created_at = models.DateTimeField('Время попытки', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Попытка решения'
        verbose_name_plural = 'Попытки решения'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Попытка {self.id} ({'✓' if self.is_correct else '✗'})"

class StudentProgress(models.Model):
    """
    Прогресс ученика по прототипу (Assignment).
    Считаем, сколько задач решено правильно.
    """
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='progress_records',
        verbose_name='Ученик',
        limit_choices_to={'role': 'student'}
    )
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='student_progress',
        verbose_name='Прототип задания'
    )
    
    # Статистика
    total_attempts = models.IntegerField('Всего попыток', default=0)
    correct_attempts = models.IntegerField('Правильных попыток', default=0)
    
    # Прогресс
    is_completed = models.BooleanField('Пройдено', default=False)
    completed_at = models.DateTimeField('Завершено', null=True, blank=True)
    
    # Временные метки
    started_at = models.DateTimeField('Начало изучения', auto_now_add=True)
    updated_at = models.DateTimeField('Последнее обновление', auto_now=True)
    
    class Meta:
        verbose_name = 'Прогресс ученика'
        verbose_name_plural = 'Прогресс учеников'
        unique_together = ['student', 'assignment']
    
    def __str__(self):
        return f"{self.student.username} - {self.assignment.title}"
    
    def get_percentage(self):
        """Процент выполнения: сколько правильных ответов из required_correct (обрезано до 100%)."""
        required = self.assignment.required_correct or 1
        if self.correct_attempts <= 0:
            return 0
        ratio = self.correct_attempts / required
        if ratio > 1:
            ratio = 1
        return ratio * 100

    
    def update_progress(self, is_correct):
        """Обновляет прогресс после попытки (только путь генератора задач).

        ВНИМАНИЕ: это ТРЕТЬЕ место, где решается судьба зачёта, и оно
        считает иначе, чем users/progress.mark_progress: там «сколько
        РАЗНЫХ задач сдано из набора», а здесь «сколько верных ответов
        дано всего». Для генератора это осмысленно — он каждый раз выдаёт
        новую задачу, — поэтому сводить их механически нельзя: у уже
        занимающихся учеников прогресс пересчитался бы задним числом.

        Если будете сводить, делать это надо вместе с переносом данных.
        """
        self.total_attempts += 1
        if is_correct:
            self.correct_attempts += 1

        # Проверяем, достигнут ли требуемый уровень
        if self.correct_attempts >= self.assignment.required_correct:
            self.is_completed = True
            if not self.completed_at:
                self.completed_at = timezone.now()

        self.save()


class Notification(models.Model):
    """Уведомление в кабинете. Кому, о чём и куда вести."""

    KIND_SUBMITTED = 'submitted'   # ученик прислал работу — преподавателю
    KIND_REVIEWED = 'reviewed'     # работу проверили — ученику
    KIND_MESSAGE = 'message'       # написали в чат — тому, кого нет на сайте
    KIND_DUE_SOON = 'due_soon'     # срок домашки подходит — ученику
    KIND_DUE_PASSED = 'due_passed'  # срок вышел (или приём закрыт) — ученику
    KIND_DIGEST = 'digest'         # сводка за день — преподавателю
    KIND_CHOICES = [
        (KIND_SUBMITTED, 'Прислали работу'),
        (KIND_REVIEWED, 'Работу проверили'),
        (KIND_MESSAGE, 'Новое сообщение'),
        (KIND_DUE_SOON, 'Срок подходит'),
        (KIND_DUE_PASSED, 'Срок вышел'),
        (KIND_DIGEST, 'Сводка за день'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications',
        verbose_name='Кому',
    )
    kind = models.CharField('Событие', max_length=20, choices=KIND_CHOICES)
    text = models.CharField('Текст', max_length=300)
    # Куда ведёт. Храним готовый путь, а не тип с номером: адрес считается в
    # момент события, когда под рукой и курс, и урок, и роль читателя.
    url = models.CharField('Ссылка', max_length=500, blank=True)
    # Ключ повторности: «про что» это уведомление. Пустой — обычное разовое.
    # Непустой вместе с (кем, видом) уникален, и это даёт две вещи сразу:
    # напоминание о сроке не уйдёт дважды, а сообщения в одной ветке
    # складываются в ОДНУ запись, а не сыплются по штуке на реплику.
    key = models.CharField('Ключ повторности', max_length=120, blank=True)
    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Когда', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        # Счётчик непрочитанных считается на КАЖДОЙ странице, поэтому индекс
        # именно под этот запрос.
        indexes = [models.Index(fields=['user', 'is_read', '-created_at'])]
        constraints = [
            # Уникальность только у ПОМЕЧЕННЫХ ключом. Пустой ключ — у обычных
            # разовых уведомлений, их может быть сколько угодно.
            models.UniqueConstraint(
                fields=['user', 'kind', 'key'],
                condition=~Q(key=''),
                name='uniq_notification_key',
            ),
        ]

    def __str__(self):
        return f'{self.user.username}: {self.text[:40]}'


class HomeworkExtension(models.Model):
    """Личное продление срока по домашке одному ученику.

    Пустая дата означает «как у всех»: можно продлить только приём, не трогая
    срок, и наоборот. Общие даты урока при этом не меняются — в этом весь
    смысл, иначе пришлось бы двигать срок остальным.
    """
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name='extensions',
        verbose_name='Домашка',
    )
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='hw_extensions',
        limit_choices_to={'role': 'student'}, verbose_name='Ученик',
    )
    due_date = models.DateField('Личный срок', null=True, blank=True)
    cutoff_date = models.DateField('Личный приём до', null=True, blank=True)
    reason = models.CharField(
        'Причина', max_length=200, blank=True,
        help_text='Через месяц вы сами не вспомните, почему у него срок другой.',
    )
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', limit_choices_to={'role': 'teacher'},
        verbose_name='Кто продлил',
    )
    created_at = models.DateTimeField('Когда', auto_now_add=True)

    class Meta:
        verbose_name = 'Продление срока'
        verbose_name_plural = 'Продления сроков'
        unique_together = ('lesson', 'student')
        indexes = [models.Index(fields=['lesson', 'student'])]

    def __str__(self):
        return f'{self.student.username} · {self.lesson.title} → {self.due_date or "как у всех"}'


class LessonProgress(models.Model):
    """Отметка ученика «урок прочитан» для теоретических (текстовых) уроков.

    Используется в курсах-методичках: ученик открывает Lesson.content,
    нажимает кнопку «Прочитано», создаётся запись. Прогресс по теории
    отображается рядом с уроком на странице курса.
    """
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='lesson_progress',
        limit_choices_to={'role': 'student'}, verbose_name='Ученик',
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name='read_progress',
        verbose_name='Урок',
    )
    is_read = models.BooleanField('Прочитан', default=False)
    read_at = models.DateTimeField('Дата отметки', null=True, blank=True)

    class Meta:
        verbose_name = 'Прогресс по уроку (теория)'
        verbose_name_plural = 'Прогресс по урокам (теория)'
        unique_together = ('student', 'lesson')
        indexes = [models.Index(fields=['student', 'lesson'])]

    def __str__(self):
        mark = '✓' if self.is_read else '·'
        return f"{self.student.username} · {self.lesson.title} {mark}"


class ManualMark(models.Model):
    """Отметка преподавателя о решённой задаче ученика в manual-курсе.

    Хранится одна запись на пару (student, assignment). Отсутствие записи
    означает «не решено».
    """
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='manual_marks',
        limit_choices_to={'role': 'student'}, verbose_name='Ученик',
    )
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name='manual_marks',
        verbose_name='Прототип',
    )
    is_completed = models.BooleanField('Решено', default=False)
    marked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', limit_choices_to={'role': 'teacher'},
        verbose_name='Кто отметил',
    )
    marked_at = models.DateTimeField('Дата отметки', auto_now=True)

    class Meta:
        verbose_name = 'Отметка (manual)'
        verbose_name_plural = 'Отметки (manual)'
        unique_together = ('student', 'assignment')
        indexes = [models.Index(fields=['student', 'assignment'])]

    def __str__(self):
        return f"{self.student.username} · {self.assignment.title} = {'✓' if self.is_completed else '·'}"


class StudentSubmission(models.Model):
    """Развёрнутое решение, отправленное учеником на проверку преподавателю.
    Используется для задач Assignment.requires_review=True."""
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'На проверке'),
        (STATUS_ACCEPTED, 'Принято'),
        (STATUS_REJECTED, 'Вернуть на доработку'),
    ]

    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='submissions',
        limit_choices_to={'role': 'student'},
    )
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name='submissions',
    )
    # Номер попытки, начиная с 1. Вместе с is_latest заменяет прежнее
    # ограничение «одна запись на задачу», из-за которого доработка затирала
    # и текст ученика, и комментарий преподавателя.
    attempt = models.PositiveIntegerField('Номер попытки', default=1)
    is_latest = models.BooleanField('Текущая попытка', default=True)
    text = models.TextField('Текст решения', blank=True)
    file = models.FileField(
        'Прикреплённый файл (фото/PDF)',
        upload_to='hw/submissions/', blank=True, null=True,
        # Та же проверка, что и во вью: сюда файл может попасть и из админки.
        validators=[validate_homework_file],
    )
    status = models.CharField(
        'Статус', max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    teacher_comment = models.TextField('Комментарий преподавателя', blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', limit_choices_to={'role': 'teacher'},
    )

    class Meta:
        verbose_name = 'Решение ученика'
        verbose_name_plural = 'Решения учеников'
        ordering = ['-submitted_at']
        # Прежнее unique_together('student', 'assignment') снято: теперь строк
        # столько, сколько было попыток. Уникальна пара «задача + номер».
        unique_together = ('student', 'assignment', 'attempt')
        indexes = [
            models.Index(fields=['student', 'assignment']),
            models.Index(fields=['student', 'assignment', 'is_latest']),
        ]

    def __str__(self):
        return (f"{self.student.username} → {self.assignment.title} "
                f"[попытка {self.attempt}, {self.status}]")


class HomeworkAttempt(models.Model):
    """История попыток ученика ответить на задачу в курсе с ДЗ.
    Сохраняется при каждом нажатии «Проверить» — позволяет
    преподавателю увидеть, что именно ученик пробовал."""
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='hw_attempts',
        limit_choices_to={'role': 'student'},
    )
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name='hw_attempts',
    )
    answer = models.CharField('Ответ ученика', max_length=255)
    is_correct = models.BooleanField('Правильно', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Попытка ученика'
        verbose_name_plural = 'Попытки учеников'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['student', 'assignment'])]

    def __str__(self):
        return f"{self.student.username} · {self.assignment} → {self.answer} ({'✓' if self.is_correct else '✗'})"


# ──────────────────────────────────────────────────────────────────────────────
# Модели для ОГЭ №1-5 (составные группы из 5 связанных задач с общим контекстом)
# ──────────────────────────────────────────────────────────────────────────────

class TaskGroup(models.Model):
    """Группа из 5 связанных задач с общим контекстом (ОГЭ №1-5).

    Принадлежит уроку (тема — Бумага / Шины / Дороги / ...).
    Все 5 подзадач выводятся ученику на одном экране вместе с контекстом.
    """
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='task_groups',
        verbose_name='Урок (тема)',
    )
    title = models.CharField('Название группы', max_length=200,
                             help_text='Например: «Вариант 1» или «Антоновка»')
    context_html = models.TextField('HTML контекста',
                                    help_text='Общий текст + картинка (через <img>)')
    order = models.IntegerField('Порядок в уроке', default=0)
    fipi_ctx_id = models.CharField('ID контекста на ФИПИ', max_length=64,
                                   blank=True, db_index=True,
                                   help_text='Для отслеживания происхождения')

    class Meta:
        ordering = ['order']
        verbose_name = 'Группа задач (ОГЭ №1-5)'
        verbose_name_plural = 'Группы задач (ОГЭ №1-5)'
        # Идемпотентность импорта: в одном уроке две группы не могут
        # занимать один и тот же порядок.
        constraints = [
            models.UniqueConstraint(
                fields=['lesson', 'order'],
                name='unique_taskgroup_lesson_order',
            ),
        ]

    def __str__(self):
        return f"{self.lesson.title} → {self.title}"


class GroupSubQuestion(models.Model):
    """Одна из 5 подзадач внутри TaskGroup."""

    T_TYPE_CHOICES = [
        ('T1', 'T1 — соответствие / идентификация'),
        ('T2', 'T2'),
        ('T3', 'T3'),
        ('T4', 'T4'),
        ('T5', 'T5 — оптимизация / сравнение'),
    ]

    group = models.ForeignKey(
        TaskGroup,
        on_delete=models.CASCADE,
        related_name='sub_questions',
        verbose_name='Группа',
    )
    question_html = models.TextField('HTML вопроса',
                                     help_text='Текст с возможными таблицами/картинками')
    correct_answer = models.CharField('Правильный ответ', max_length=200,
                                      help_text='Точное соответствие (с запятой для десятичных)')
    t_type = models.CharField('Тип задания', max_length=5,
                              choices=T_TYPE_CHOICES, blank=True)
    order = models.IntegerField('Порядок в группе', default=0,
                                help_text='Обычно 1..5')
    fipi_task_id = models.CharField('ID задачи на ФИПИ', max_length=32,
                                    blank=True, db_index=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Подзадача группы'
        verbose_name_plural = 'Подзадачи групп'
        # Идемпотентность импорта: в одной группе две подзадачи не могут
        # занимать один и тот же порядок.
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'order'],
                name='unique_subquestion_group_order',
            ),
        ]

    def __str__(self):
        return f"{self.group.title} #{self.order} ({self.t_type or '?'})"


class ExamVariant(models.Model):
    """Сохранённый вариант экзамена ОГЭ, собранный конструктором.

    Содержит ссылки на слоты задач (ExamVariantSlot). Для слотов 1-5 хранит
    общий контекст (картинка/таблица) и ссылку на исходный TaskGroup.
    Слоты 6-19 — отдельные задачи с зафиксированным условием и ответом.
    """
    KIND_FULL = 'full'
    KIND_SHORT = 'short'
    KIND_CHOICES = [
        (KIND_FULL, 'Полный вариант (1–19)'),
        (KIND_SHORT, 'Только задания 1–5'),
    ]

    code = models.CharField('Код варианта', max_length=10, unique=True, db_index=True)
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='exam_variants', verbose_name='Создатель',
    )
    kind = models.CharField('Тип', max_length=10, choices=KIND_CHOICES, default=KIND_FULL)

    # Общий контекст для слотов 1-5 (HTML — картинка/таблица).
    block_1_5_context_html = models.TextField('Контекст 1–5', blank=True)
    block_1_5_source = models.ForeignKey(
        TaskGroup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Исходная группа 1–5',
    )

    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Вариант экзамена'
        verbose_name_plural = 'Варианты экзамена'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['code'])]

    def __str__(self):
        return f'Вариант {self.code} ({self.get_kind_display()})'


class ExamVariantSlot(models.Model):
    """Один слот (задача) в варианте.

    Хранит зафиксированное условие и правильный ответ — чтобы при возврате
    к варианту по ссылке ученик видел те же задачи, даже если генераторы
    эволюционировали.
    """
    variant = models.ForeignKey(
        ExamVariant, on_delete=models.CASCADE, related_name='slots',
        verbose_name='Вариант',
    )
    slot = models.IntegerField('Номер слота (1..19)')

    question_html = models.TextField('HTML условия')
    correct_answer = models.CharField('Правильный ответ', max_length=255)
    # Для задач с выбором (single_choice): 4 варианта ответа.
    # Пусто для decimal_input и TaskGroup-подзадач.
    choices = models.JSONField('Варианты ответа (для single_choice)',
                               default=list, blank=True)
    # Тип ответа: text / single_choice — определяет рендер.
    answer_type = models.CharField('Тип ответа', max_length=20, blank=True, default='')
    # Номер задания ОГЭ (1..19). Для слотов 1-5 это и есть номер вопроса;
    # для пользовательских вариантов с count>1 — номер задания, к которому
    # относится этот слот.
    task_number = models.IntegerField('Номер задания ОГЭ', null=True, blank=True)

    sub_question = models.ForeignKey(
        GroupSubQuestion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Источник: подзадача (для 1–5)',
    )
    assignment = models.ForeignKey(
        Assignment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Источник: задание (для 6–19)',
    )

    class Meta:
        verbose_name = 'Слот варианта'
        verbose_name_plural = 'Слоты вариантов'
        unique_together = ('variant', 'slot')
        ordering = ['slot']
        indexes = [models.Index(fields=['variant', 'slot'])]

    def __str__(self):
        return f'{self.variant.code} #{self.slot}'


class ExamVariantAnswer(models.Model):
    """Ответ конкретного ученика на слот варианта.

    Вынесено со слота (ExamVariantSlot), чтобы один вариант (по коду) могли
    решать несколько учеников, не затирая ответы друг друга.
    """
    slot = models.ForeignKey(
        ExamVariantSlot, on_delete=models.CASCADE, related_name='answers',
        verbose_name='Слот',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='exam_variant_answers',
        verbose_name='Ученик',
    )
    user_answer = models.CharField('Ответ ученика', max_length=255, blank=True)
    is_correct = models.BooleanField('Верно', null=True, blank=True)
    answered_at = models.DateTimeField('Время ответа', auto_now=True)

    class Meta:
        verbose_name = 'Ответ по варианту'
        verbose_name_plural = 'Ответы по варианту'
        constraints = [
            models.UniqueConstraint(fields=['slot', 'user'],
                                    name='uniq_variant_slot_user'),
        ]

    def __str__(self):
        return f'{self.user_id} · слот {self.slot_id}: {self.user_answer}'


class GroupAttempt(models.Model):
    """Попытка ученика по одной подзадаче TaskGroup."""
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='group_attempts',
    )
    sub_question = models.ForeignKey(
        GroupSubQuestion,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    answer = models.CharField('Ответ ученика', max_length=255)
    is_correct = models.BooleanField('Правильно', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Попытка по подзадаче (№1-5)'
        verbose_name_plural = 'Попытки по подзадачам (№1-5)'
        indexes = [models.Index(fields=['student', 'sub_question'])]

    def __str__(self):
        return f"{self.student.user.username} · {self.sub_question} → {self.answer}"


# --------------------------------------------------
# Чат преподавателя с учеником
# --------------------------------------------------
class Thread(models.Model):
    """Ветка переписки. Сейчас — одна общая на пару «преподаватель — ученик».

    Поле lesson заведено на вырост и пока всегда пустое: когда понадобятся
    обсуждения при конкретной домашке, они лягут сюда же, и различать их будет
    одно поле, а не отдельная таблица.
    """

    teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='threads_as_teacher',
        limit_choices_to={'role': 'teacher'}, verbose_name='Преподаватель',
    )
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='threads_as_student',
        limit_choices_to={'role': 'student'}, verbose_name='Ученик',
    )
    # Пусто — общая ветка; заполнено — обсуждение конкретной домашки.
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, null=True, blank=True,
        related_name='threads', verbose_name='Урок (если обсуждение домашки)',
    )
    created_at = models.DateTimeField('Заведена', auto_now_add=True)
    # Время последнего сообщения — по нему список веток сортируется у преподавателя.
    updated_at = models.DateTimeField('Последнее сообщение', auto_now_add=True)

    class Meta:
        verbose_name = 'Ветка переписки'
        verbose_name_plural = 'Ветки переписки'
        ordering = ['-updated_at']
        constraints = [
            # Общая ветка на пару — ровно одна. unique_together тут не годится:
            # в SQL два NULL не равны друг другу, и пустой lesson не помешал бы
            # завести вторую такую же ветку.
            models.UniqueConstraint(
                fields=['teacher', 'student'],
                condition=Q(lesson__isnull=True),
                name='uniq_general_thread_per_pair',
            ),
            models.UniqueConstraint(
                fields=['teacher', 'student', 'lesson'],
                condition=Q(lesson__isnull=False),
                name='uniq_lesson_thread_per_pair',
            ),
        ]
        indexes = [
            models.Index(fields=['teacher', '-updated_at']),
            models.Index(fields=['student', '-updated_at']),
        ]

    def __str__(self):
        куда = self.lesson.title if self.lesson_id else 'общая'
        return f"{self.teacher} ↔ {self.student} ({куда})"

    def other_side(self, user):
        """Собеседник для этого пользователя (или None, если он не участник)."""
        if user.id == self.teacher_id:
            return self.student
        if user.id == self.student_id:
            return self.teacher
        return None

    def has_access(self, user):
        return bool(user and user.is_authenticated
                    and user.id in (self.teacher_id, self.student_id))


class Message(models.Model):
    """Одно сообщение в ветке.

    Хранится всегда, независимо от того, был ли собеседник на сайте: лента —
    это история, а не эфир. Вложений пока нет намеренно: файлы уже умеет
    домашка, и второй тракт загрузки заводить рано.
    """

    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name='messages',
        verbose_name='Ветка',
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='chat_messages',
        verbose_name='Автор',
    )
    text = models.TextField('Текст')
    created_at = models.DateTimeField('Когда', auto_now_add=True)
    # Пусто — собеседник ещё не читал. По этому полю считается «непрочитанных: 3».
    read_at = models.DateTimeField('Прочитано', null=True, blank=True)

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at']),
            # Непрочитанные ищем по ветке и пустой отметке прочтения.
            models.Index(fields=['thread', 'read_at']),
        ]

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"
