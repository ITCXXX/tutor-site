# users/views.py
from django.db.models import Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
import os
from .models import Course, Module, Lesson, Assignment, MaterialCategory, Material, Enrollment, User  # <-- Добавить Assignment
from .pdf_utils import get_pdf_info, generate_pdf_thumbnail
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
import json

def home_view(request):
    """Главная страница"""
    return render(request, 'users/home.html')

def login_view(request):
    """Страница входа"""
    if request.user.is_authenticated:
        if request.user.role == 'student':
            return redirect('student_dashboard')
        elif request.user.role == 'parent':
            return redirect('parent_dashboard')
        else:
            return redirect('/admin/')
    
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            error = "Пожалуйста, заполните все поля"
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    if user.role == 'student':
                        messages.success(request, f"Добро пожаловать, {user.username}!")
                        return redirect('student_dashboard')
                    elif user.role == 'parent':
                        messages.success(request, f"Добро пожаловать, {user.username}!")
                        return redirect('parent_dashboard')
                    else:
                        return redirect('/admin/')
                else:
                    error = "Аккаунт отключен. Обратитесь к администратору."
            else:
                error = "Неверный логин или пароль"
    
    return render(request, 'users/login.html', {'error': error})

# users/views.py - функция student_dashboard

@login_required
def student_dashboard(request):
    """Личный кабинет ученика"""
    if request.user.role != 'student':
        messages.error(request, 'Доступ только для учеников')
        return redirect('login')
    
    # Получаем статистику по курсам
    enrollments = Enrollment.objects.filter(student=request.user, is_active=True)
    total_courses = enrollments.count()
    completed_courses = enrollments.filter(progress=100).count()
    average_progress = enrollments.aggregate(avg=Avg('progress'))['avg'] or 0
    
    # Получаем последние активности
    recent_enrollments = enrollments.order_by('-last_accessed')[:3]
    
    # ========== НОВЫЙ КОД: задания с генераторами ==========
    # Получаем все задания с генераторами, на которые записан ученик
    assignments_with_generators = Assignment.objects.filter(
        lesson__module__course__enrollments__student=request.user,
        problem_generator__isnull=False
    ).distinct()[:5]
    # ========== КОНЕЦ НОВОГО КОДА ==========
    
    return render(request, 'users/dashboard.html', {
        'user': request.user,
        'role': 'ученика',
        'title': 'Личный кабинет ученика',
        'total_courses': total_courses,
        'completed_courses': completed_courses,
        'average_progress': round(average_progress, 1),
        'recent_enrollments': recent_enrollments,
        'assignments_with_generators': assignments_with_generators,  # <-- Добавляем
    })

@login_required
def parent_dashboard(request):
    """Личный кабинет родителя"""
    if request.user.role != 'parent':
        messages.error(request, 'Доступ только для родителей')
        return redirect('login')
    
    # Получаем связанных учеников
    linked_students = request.user.linked_students.all()
    
    # Получаем статистику по каждому ученику
    students_data = []
    for student in linked_students:
        enrollments = Enrollment.objects.filter(student=student, is_active=True)
        total_courses = enrollments.count()
        avg_progress = enrollments.aggregate(avg=Avg('progress'))['avg'] or 0
        
        students_data.append({
            'student': student,
            'total_courses': total_courses,
            'average_progress': round(avg_progress, 1),
            'last_login': student.last_login,
        })
    
    return render(request, 'users/parent_dashboard.html', {
        'user': request.user,
        'role': 'родителя',
        'title': 'Личный кабинет родителя',
        'linked_students': linked_students,
        'students_data': students_data,
    })

def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.success(request, "Вы успешно вышли из системы")
    return redirect('login')

def courses_list(request):
    """Каталог курсов"""
    courses = Course.objects.filter(is_active=True).order_by('order')
    
    # Статистика
    total_courses = courses.count()
    free_courses_count = courses.annotate(
        free_lessons_count=Count('modules__lessons', filter=Q(modules__lessons__is_free=True))
    ).filter(free_lessons_count__gt=0).count()
    
    return render(request, 'users/courses_list.html', {
        'courses': courses,
        'title': 'Каталог курсов по математике',
        'courses_count': total_courses,
        'free_courses_count': free_courses_count,
    })

def course_detail(request, slug):
    """Детальная страница курса"""
    course = get_object_or_404(Course, slug=slug, is_active=True)
    modules = course.modules.all().order_by('order').prefetch_related('lessons')
    
    total_lessons = 0
    total_duration = 0
    free_lessons = 0
    
    for module in modules:
        lessons = module.lessons.all()
        total_lessons += lessons.count()
        free_lessons += lessons.filter(is_free=True).count()
        total_duration += sum(lesson.duration for lesson in lessons)
    
    # Проверяем, записан ли текущий пользователь на курс
    user_enrolled = False
    enrollment = None
    if request.user.is_authenticated and request.user.role == 'student':
        enrollment = Enrollment.objects.filter(
            student=request.user, 
            course=course, 
            is_active=True
        ).first()
        user_enrolled = enrollment is not None
    
    return render(request, 'users/course_detail.html', {
        'course': course,
        'modules': modules,
        'title': f'{course.title} - Курс по математике',
        'total_lessons': total_lessons,
        'total_duration': total_duration,
        'free_lessons': free_lessons,
        'user_enrolled': user_enrolled,
        'enrollment': enrollment,
    })

@login_required
def enroll_to_course(request, course_id):
    """Запись на курс"""
    if request.user.role != 'student':
        messages.error(request, 'Только ученики могут записываться на курсы')
        return redirect('courses_list')
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Проверяем, не записан ли уже
    if Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.warning(request, f'Вы уже записаны на курс "{course.title}"')
    else:
        Enrollment.objects.create(student=request.user, course=course)
        messages.success(request, f'Вы успешно записаны на курс "{course.title}"')
    
    return redirect('student_courses')

@login_required
def student_courses(request):
    """Список курсов, на которые записан ученик"""
    if request.user.role != 'student':
        messages.error(request, 'Доступ только для учеников')
        return redirect('login')
    
    enrollments = Enrollment.objects.filter(
        student=request.user, 
        is_active=True
    ).select_related('course').order_by('-last_accessed')
    
    return render(request, 'users/student_courses.html', {
        'enrollments': enrollments,
        'title': 'Мои курсы'
    })

@login_required
def unenroll_from_course(request, enrollment_id):
    """Отписаться от курса"""
    if request.user.role != 'student':
        messages.error(request, 'Доступ только для учеников')
        return redirect('login')
    
    enrollment = get_object_or_404(
        Enrollment, 
        id=enrollment_id, 
        student=request.user,
        is_active=True
    )
    
    course_title = enrollment.course.title
    enrollment.delete()
    
    messages.success(request, f'Вы отписались от курса "{course_title}"')
    return redirect('student_courses')

def materials_list(request):
    """Список категорий материалов"""
    categories = MaterialCategory.objects.all().prefetch_related('materials')
    
    # Считаем общее количество материалов
    total_materials = Material.objects.count()
    free_materials = Material.objects.filter(is_free=True).count()
    
    return render(request, 'users/materials_list.html', {
        'categories': categories,
        'title': 'Методические материалы',
        'total_materials': total_materials,
        'free_materials': free_materials,
    })

def material_category_detail(request, slug):
    """Материалы конкретной категории"""
    category = get_object_or_404(MaterialCategory, slug=slug)
    materials = category.materials.all().order_by('order', '-created_at')
    
    # Статистика по типам материалов
    material_types = materials.values('material_type').annotate(
        count=Count('id')
    ).order_by('material_type')
    
    return render(request, 'users/material_category.html', {
        'category': category,
        'materials': materials,
        'title': f'Материалы: {category.title}',
        'material_types': material_types,
        'materials_count': materials.count(),
    })

def material_view(request, material_id):
    """Страница просмотра материала с улучшенным просмотрщиком"""
    material = get_object_or_404(Material, id=material_id)
    
    # Проверяем, что файл существует
    if not material.file:
        messages.error(request, "Файл не найден")
        return redirect('material_category_detail', slug=material.category.slug)
    
    # Проверяем, является ли файл PDF
    filename = material.file.name.lower()
    is_pdf = filename.endswith('.pdf')
    
    # Для PDF файлов обновляем информацию о страницах
    if is_pdf and material.file and os.path.exists(material.file.path):
        if material.page_count == 0:
            pdf_info = get_pdf_info(material.file.path)
            material.page_count = pdf_info['page_count']
            
            # Генерируем миниатюру для первой страницы, если её нет
            if not material.thumbnail:
                generate_pdf_thumbnail(material.file.path, material, page_number=0)
            material.save()
    
    # Получаем номер страницы из GET-параметра
    page = request.GET.get('page', '1')
    try:
        current_page = int(page)
        if current_page < 1:
            current_page = 1
        elif material.page_count > 0 and current_page > material.page_count:
            current_page = material.page_count
    except ValueError:
        current_page = 1
    
    # Формируем URL для PDF с нужной страницей
    pdf_url = f"{material.file.url}"
    if is_pdf and current_page > 1:
        pdf_url += f"#page={current_page}"
    
    # Проверяем доступность материала
    can_access = True
    if not material.is_free and request.user.is_authenticated:
        # Проверяем, купил ли пользователь материал или имеет доступ через курс
        # Здесь можно добавить логику проверки доступа
        pass
    
    return render(request, 'users/material_viewer.html', {
        'material': material,
        'title': f'Просмотр: {material.title}',
        'current_page': current_page,
        'pdf_url': pdf_url,
        'total_pages': material.page_count or 1,
        'is_pdf': is_pdf,
        'can_access': can_access,
        'file_extension': filename.split('.')[-1] if '.' in filename else 'file',
    })

@login_required
@require_GET
def get_material_thumbnails(request, material_id):
    """API для получения миниатюр страниц PDF"""
    material = get_object_or_404(Material, id=material_id)
    
    if not material.file or not material.file.path.endswith('.pdf'):
        return JsonResponse({'error': 'Файл не является PDF'}, status=400)
    
    # В реальном приложении здесь бы генерировались миниатюры для всех страниц
    # Для простоты возвращаем фиктивные данные
    
    thumbnails = []
    for i in range(1, min(material.page_count + 1, 11)):  # Ограничиваем 10 миниатюрами
        thumbnails.append({
            'page': i,
            'url': f'/static/img/pdf-thumb-placeholder.png',  # Замените на реальные миниатюры
            'width': 100,
            'height': 140,
        })
    
    return JsonResponse({
        'material_id': material.id,
        'title': material.title,
        'total_pages': material.page_count,
        'thumbnails': thumbnails,
    })

@login_required
@require_POST
def save_material_settings(request):
    """Сохранение пользовательских настроек просмотрщика"""
    try:
        data = json.loads(request.body)
        material_id = data.get('material_id')
        settings = data.get('settings', {})
        
        # Здесь можно сохранять настройки в БД
        # Пока просто возвращаем успешный ответ
        
        return JsonResponse({
            'success': True,
            'message': 'Настройки сохранены',
            'material_id': material_id,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def search_materials(request):
    """Поиск материалов"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return redirect('materials_list')
    
    # Ищем материалы по названию и описанию
    materials = Material.objects.filter(
        Q(title__icontains=query) | 
        Q(description__icontains=query)
    ).select_related('category').order_by('-created_at')
    
    # Ищем категории
    categories = MaterialCategory.objects.filter(
        Q(title__icontains=query) | 
        Q(description__icontains=query)
    )
    
    return render(request, 'users/search_results.html', {
        'query': query,
        'materials': materials,
        'categories': categories,
        'title': f'Результаты поиска: "{query}"',
        'materials_count': materials.count(),
        'categories_count': categories.count(),
    })

@login_required
def toggle_material_access(request, material_id):
    """Переключение доступа к материалу (для администраторов)"""
    if not request.user.is_superuser:
        messages.error(request, 'Доступ только для администраторов')
        return redirect('material_category_detail', slug='all')
    
    material = get_object_or_404(Material, id=material_id)
    material.is_free = not material.is_free
    material.save()
    
    status = "бесплатным" if material.is_free else "платным"
    messages.success(request, f'Материал "{material.title}" теперь {status}')
    
    return redirect('material_view', material_id=material_id)

def download_material(request, material_id):
    """Скачивание материала"""
    material = get_object_or_404(Material, id=material_id)
    
    if not material.file:
        messages.error(request, "Файл не найден")
        return redirect('material_category_detail', slug=material.category.slug)
    
    # Проверяем доступ
    if not material.is_free and not request.user.is_authenticated:
        messages.error(request, "Для скачивания этого материала необходимо авторизоваться")
        return redirect('login')
    
    # Увеличиваем счетчик скачиваний (если добавите поле download_count в модель)
    # material.download_count += 1
    # material.save()
    
    return redirect(material.file.url)

@login_required
def user_profile(request):
    """Профиль пользователя"""
    user = request.user
    
    # Получаем профиль в зависимости от роли
    profile = None
    if user.role == 'student':
        profile = getattr(user, 'student_profile', None)
    elif user.role == 'parent':
        profile = getattr(user, 'parent_profile', None)
    
    return render(request, 'users/profile.html', {
        'user': user,
        'profile': profile,
        'title': 'Мой профиль'
    })

@login_required
def update_profile(request):
    """Обновление профиля"""
    if request.method == 'POST':
        user = request.user
        
        # Обновляем основные поля
        if 'email' in request.POST:
            user.email = request.POST['email']
        if 'phone' in request.POST:
            user.phone = request.POST['phone']
        
        # Обновляем профиль в зависимости от роли
        if user.role == 'student' and hasattr(user, 'student_profile'):
            profile = user.student_profile
            if 'display_name' in request.POST:
                profile.display_name = request.POST['display_name']
            if 'real_name' in request.POST:
                profile.real_name = request.POST['real_name']
            if 'grade' in request.POST:
                profile.grade = request.POST['grade']
            if 'school' in request.POST:
                profile.school = request.POST['school']
            if 'goals' in request.POST:
                profile.goals = request.POST['goals']
            profile.save()
        
        elif user.role == 'parent' and hasattr(user, 'parent_profile'):
            profile = user.parent_profile
            if 'display_name' in request.POST:
                profile.display_name = request.POST['display_name']
            if 'real_name' in request.POST:
                profile.real_name = request.POST['real_name']
            profile.save()
        
        user.save()
        messages.success(request, 'Профиль успешно обновлен')
    
    return redirect('user_profile')

def handler404(request, exception):
    """Обработчик 404 ошибки"""
    return render(request, 'users/404.html', status=404)

def handler500(request):
    """Обработчик 500 ошибки"""
    return render(request, 'users/500.html', status=500)

# =========== API ДЛЯ PDF-ПРОСМОТРЩИКА ===========

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import PDFBookmark, PDFAnnotation, Material
from .serializers import PDFBookmarkSerializer, PDFAnnotationSerializer

class PDFBookmarkViewSet(viewsets.ModelViewSet):
    """
    API для работы с закладками пользователя в PDF.
    Пользователь видит и управляет только своими закладками.
    """
    serializer_class = PDFBookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Возвращаем только закладки текущего пользователя"""
        return PDFBookmark.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Создаем закладку для текущего пользователя"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def by_material(self, request):
        """Получить все закладки пользователя для конкретного материала"""
        material_id = request.query_params.get('material_id')
        if not material_id:
            return Response(
                {'error': 'Не указан material_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        bookmarks = self.get_queryset().filter(material_id=material_id)
        serializer = self.get_serializer(bookmarks, many=True)
        return Response(serializer.data)


class PDFAnnotationViewSet(viewsets.ModelViewSet):
    """
    API для работы с аннотациями пользователя в PDF.
    """
    serializer_class = PDFAnnotationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Возвращаем только аннотации текущего пользователя"""
        return PDFAnnotation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Создаем аннотацию для текущего пользователя"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def by_material(self, request):
        """Получить все аннотации пользователя для конкретного материала"""
        material_id = request.query_params.get('material_id')
        if not material_id:
            return Response(
                {'error': 'Не указан material_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        annotations = self.get_queryset().filter(material_id=material_id)
        serializer = self.get_serializer(annotations, many=True)
        return Response(serializer.data)