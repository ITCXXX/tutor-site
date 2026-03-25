# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, StudentProfile, ParentProfile, 
    Course, Module, Lesson, Assignment, TestQuestion, AnswerOption,
    MaterialCategory, Material, Enrollment,
    # Новые модели для экзаменационной подготовки
    ProblemGenerator, GeneratedProblem, ProblemAttempt, StudentProgress
)

# --------------------------------------------------
# Существующие модели пользователей (не изменяем)
# --------------------------------------------------
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'role', 'email', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email')

    readonly_fields = ('last_login', 'date_joined')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личная информация', {'fields': ('email', 'phone', 'role')}),
        ('Разрешения', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'linked_students'),
        }),
        ('Важные даты', {
            'fields': ('last_login', 'date_joined'),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'email'),
        }),
    )

    filter_horizontal = ('linked_students',)

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'grade', 'school')
    search_fields = ('display_name', 'real_name', 'user__username')

@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'real_name')
    search_fields = ('display_name', 'real_name', 'user__username')

# --------------------------------------------------
# НОВЫЕ МОДЕЛИ ДЛЯ ЭКЗАМЕНАЦИОННОЙ ПОДГОТОВКИ
# --------------------------------------------------

@admin.register(ProblemGenerator)
class ProblemGeneratorAdmin(admin.ModelAdmin):
    list_display = ('name', 'generator_type', 'created_at')
    list_filter = ('generator_type',)
    search_fields = ('name',)
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'generator_type')
        }),
        ('Код генератора', {
            'fields': ('python_code',),
            'classes': ('collapse',),
            'description': 'Вставьте Python код с функцией generate_task()'
        }),
        ('Или шаблон', {
            'fields': ('template_text',),
            'classes': ('collapse',)
        }),
        ('Конфигурация', {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
    )

@admin.register(GeneratedProblem)
class GeneratedProblemAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'assignment', 'status', 'attempts_count', 'correct_attempts', 'created_at')
    list_filter = ('status', 'assignment', 'created_at')
    search_fields = ('student__username', 'assignment__title')
    readonly_fields = ('created_at', 'last_attempt_at')
    fieldsets = (
        ('Основное', {
            'fields': ('assignment', 'student', 'status')
        }),
        ('Данные задачи', {
            'fields': ('task_data', 'condition_text', 'correct_answer'),
            'classes': ('collapse',)
        }),
        ('Статистика', {
            'fields': ('attempts_count', 'correct_attempts', 'created_at', 'last_attempt_at')
        }),
    )

@admin.register(ProblemAttempt)
class ProblemAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'problem', 'is_correct', 'created_at')
    list_filter = ('is_correct', 'created_at')
    search_fields = ('student__username', 'problem__assignment__title')
    readonly_fields = ('created_at',)

@admin.register(StudentProgress)
class StudentProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'get_percentage', 'is_completed', 'updated_at')
    list_filter = ('is_completed', 'assignment')
    search_fields = ('student__username', 'assignment__title')
    readonly_fields = ('started_at', 'updated_at', 'completed_at')
    
    def get_percentage(self, obj):
        return f"{obj.get_percentage():.1f}%"
    get_percentage.short_description = 'Процент правильных'

# --------------------------------------------------
# Вложенные админки для курсов (обновленные)
# --------------------------------------------------

class AnswerOptionInline(admin.TabularInline):
    """Варианты ответов для вопросов"""
    model = AnswerOption
    extra = 4
    min_num = 2
    max_num = 6
    ordering = ['order']

class TestQuestionInline(admin.TabularInline):
    """Вопросы для заданий"""
    model = TestQuestion
    extra = 1
    show_change_link = True
    fields = ['question_text', 'question_type', 'order']
    ordering = ['order']

@admin.register(TestQuestion)
class TestQuestionAdmin(admin.ModelAdmin):
    """Админка вопросов с вариантами ответов"""
    inlines = [AnswerOptionInline]
    list_display = ['id', 'question_text_short', 'assignment', 'question_type']
    list_filter = ['question_type', 'assignment__lesson__module__course']
    search_fields = ['question_text', 'assignment__title']
    list_select_related = ['assignment']
    
    def question_text_short(self, obj):
        return obj.question_text[:80] + '...' if len(obj.question_text) > 80 else obj.question_text
    question_text_short.short_description = 'Вопрос'

class AssignmentInline(admin.TabularInline):
    """Задания для уроков"""
    model = Assignment
    extra = 1
    show_change_link = True
    fields = ['title', 'assignment_type', 'points', 'order']
    ordering = ['order']

# ОБНОВЛЕННАЯ АДМИНКА ДЛЯ ASSIGNMENT
@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    """Админка заданий с вопросами и генераторами"""
    inlines = [TestQuestionInline]
    list_display = ['title', 'lesson', 'assignment_type', 'answer_type', 'problem_generator', 'points', 'questions_count']
    list_filter = ['assignment_type', 'answer_type', 'lesson__module__course']
    search_fields = ['title', 'description']
    list_select_related = ['lesson']
    raw_id_fields = ['problem_generator', 'theory_material']
    
    fieldsets = (
        ('Основное', {
            'fields': ('lesson', 'title', 'description', 'order')
        }),
        ('Тип задания', {
            'fields': ('assignment_type', 'points')
        }),
        ('Для экзаменационных задач', {
            'fields': ('problem_generator', 'answer_type', 'required_correct', 'theory_material'),
            'classes': ('collapse',)  # Сворачиваемый блок
        }),
    )
    
    def questions_count(self, obj):
        return obj.questions.count()
    questions_count.short_description = 'Вопросов'

class LessonInline(admin.TabularInline):
    """Уроки для модулей"""
    model = Lesson
    extra = 1
    show_change_link = True
    fields = ['title', 'lesson_type', 'duration', 'order', 'is_free']
    ordering = ['order']

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Админка уроков с заданиями"""
    inlines = [AssignmentInline]
    list_display = ['title', 'module', 'lesson_type', 'duration', 'order', 'is_free', 'assignments_count']
    list_filter = ['lesson_type', 'is_free', 'module__course']
    search_fields = ['title', 'content']
    list_editable = ['order', 'is_free']
    list_select_related = ['module']
    
    def assignments_count(self, obj):
        return obj.assignments.count()
    assignments_count.short_description = 'Заданий'

class ModuleInline(admin.TabularInline):
    """Модули для курсов"""
    model = Module
    extra = 1
    show_change_link = True
    fields = ['title', 'order', 'lesson_count']
    readonly_fields = ['lesson_count']
    ordering = ['order']
    
    def lesson_count(self, obj):
        return obj.lessons.count()
    lesson_count.short_description = 'Уроков'

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """Админка модулей с уроками"""
    inlines = [LessonInline]
    list_display = ['title', 'course', 'order', 'lessons_count']
    list_filter = ['course']
    search_fields = ['title', 'description']
    list_editable = ['order']
    list_select_related = ['course']
    
    def lessons_count(self, obj):
        return obj.lessons.count()
    lessons_count.short_description = 'Уроков'

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Главная админка курсов"""
    inlines = [ModuleInline]
    list_display = ['title', 'slug', 'is_active', 'modules_count', 'order', 'created_at']
    list_editable = ['is_active', 'order']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'short_description', 'full_description']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'short_description', 'full_description', 'cover_image')
        }),
        ('Настройки', {
            'fields': ('is_active', 'order')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def modules_count(self, obj):
        return obj.modules.count()
    modules_count.short_description = 'Модулей'
    
@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'order', 'materials_count')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('title',)}
    
    def materials_count(self, obj):
        return obj.materials.count()
    materials_count.short_description = 'Материалов'

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'material_type', 'is_free', 'order')
    list_filter = ('category', 'material_type', 'is_free')
    list_editable = ('order', 'is_free')
    search_fields = ('title', 'description')

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'progress', 'is_active')
    list_filter = ('is_active', 'course')
    search_fields = ('student__username', 'course__title')
    list_select_related = ('student', 'course')

# --------------------------------------------------
# Регистрация основной модели User
# --------------------------------------------------
admin.site.register(User, CustomUserAdmin)