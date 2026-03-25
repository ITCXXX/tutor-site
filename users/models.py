# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone

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
    email = models.EmailField('Email', blank=True, null=True)
    phone = models.CharField('Телефон', max_length=20, blank=True, null=True)
    
    # Роли
    ROLE_CHOICES = [
        ('student', 'Ученик'),
        ('parent', 'Родитель'),
        ('admin', 'Администратор'),
    ]
    role = models.CharField('Роль', max_length=10, choices=ROLE_CHOICES, default='student')
    
    # Статусы
    is_active = models.BooleanField('Активен', default=True)
    is_staff = models.BooleanField('Персонал', default=False)
    is_superuser = models.BooleanField('Суперпользователь', default=False)
    
    # Даты
    date_joined = models.DateTimeField('Дата регистрации', default=timezone.now)
    last_login = models.DateTimeField('Последний вход', auto_now=True)
    
    # Связи
    linked_students = models.ManyToManyField('self', symmetrical=False, blank=True, 
                                             limit_choices_to={'role': 'student'})
    
    # Менеджер
    objects = UserManager()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-date_joined']
    
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
    school = models.CharField('Школа/ВУЗ', max_length=200, blank=True)
    goals = models.TextField('Цели обучения', blank=True)
    notes = models.TextField('Заметки репетитора', blank=True)
    level = models.CharField('Уровень', max_length=50, blank=True, default='начальный')
    
    class Meta:
        verbose_name = 'Профиль ученика'
        verbose_name_plural = 'Профили учеников'
    
    def __str__(self):
        return self.display_name

class ParentProfile(models.Model):
    """Профиль родителя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile',
                                limit_choices_to={'role': 'parent'})
    display_name = models.CharField('Имя для отображения', max_length=100)
    real_name = models.CharField('Полное имя', max_length=200, blank=True)
    
    class Meta:
        verbose_name = 'Профиль родителя'
        verbose_name_plural = 'Профили родителей'
    
    def __str__(self):
        return self.display_name

# --------------------------------------------------
# НОВЫЕ МОДЕЛИ ДЛЯ КУРСОВ (добавляем в конец)
# --------------------------------------------------
class Course(models.Model):
    """Основная модель курса"""
    title = models.CharField('Название курса', max_length=200)
    slug = models.SlugField('URL-адрес', unique=True, help_text='Например: geometry-9-class')
    short_description = models.TextField('Краткое описание', max_length=300)
    full_description = models.TextField('Подробное описание', blank=True)
    cover_image = models.ImageField('Обложка курса', upload_to='courses/covers/', blank=True, null=True)
    is_active = models.BooleanField('Активен', default=False)
    order = models.IntegerField('Порядок отображения', default=0)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return self.title

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
    
    def execute_generator(self, student=None):
        """Выполняет генератор и возвращает данные задачи"""
        if self.generator_type == 'python_function':
            try:
                # Создаем локальное пространство имен для безопасного выполнения
                local_vars = {}
                
                # Импортируем random и передаем в globals
                import random
                import math
                
                # Простая версия - передаем только random и math
                exec(self.python_code, {'random': random, 'math': math}, local_vars)
                
                if 'generate_task' in local_vars:
                    return local_vars['generate_task']()
                else:
                    raise ValueError("Генератор должен содержать функцию generate_task()")
            except Exception as e:
                # Возвращаем тестовую задачу в случае ошибки
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
    question_type = models.CharField('Тип вопроса', max_length=20, choices=[
        ('single_choice', 'Один правильный ответ'),
        ('multiple_choice', 'Несколько правильных ответов'),
        ('true_false', 'Верно/Неверно'),
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
        """Обновляет прогресс после попытки"""
        self.total_attempts += 1
        if is_correct:
            self.correct_attempts += 1
        
        # Проверяем, достигнут ли требуемый уровень
        if self.correct_attempts >= self.assignment.required_correct:
            self.is_completed = True
            if not self.completed_at:
                self.completed_at = timezone.now()
        
        self.save()