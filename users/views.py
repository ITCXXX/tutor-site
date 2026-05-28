# users/views.py
from django.db.models import Avg, Count, Q, Max
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import (
    Course, Module, Lesson, Assignment,
    Enrollment, User, StudentProfile, LessonProgress,
)
from django.http import JsonResponse, HttpResponse
from urllib.parse import quote
from django.views.decorators.http import require_POST
import json

def home_view(request):
    """Главная страница"""
    return render(request, 'users/home.html')

def login_view(request):
    """Страница входа"""
    if request.user.is_authenticated:
        if request.user.role == 'student':
            return redirect('student_dashboard')
        elif request.user.role == 'teacher':
            return redirect('teacher_dashboard')
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
                        return redirect('student_dashboard')
                    elif user.role == 'teacher':
                        return redirect('teacher_dashboard')
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
    """Личный кабинет ученика."""
    if request.user.role != 'student':
        messages.error(request, 'Доступ только для учеников')
        return redirect('login')

    from .models import StudentProgress, ManualMark

    enrollments = Enrollment.objects.filter(student=request.user, is_active=True)
    course_ids = list(enrollments.values_list('course_id', flat=True))

    # Все задания из курсов, на которые записан ученик
    all_assignments = Assignment.objects.filter(
        lesson__module__course_id__in=course_ids
    )
    total_assignments = all_assignments.count()

    # Сколько заданий ученик закрыл: auto-курсы по StudentProgress, manual — по ManualMark
    auto_done = StudentProgress.objects.filter(
        student=request.user,
        assignment__in=all_assignments,
        is_completed=True,
    ).count()
    manual_done = ManualMark.objects.filter(
        student=request.user,
        assignment__in=all_assignments,
        is_completed=True,
    ).count()
    completed_assignments = auto_done + manual_done

    progress_pct = (
        round(completed_assignments / total_assignments * 100)
        if total_assignments else 0
    )

    return render(request, 'users/dashboard.html', {
        'user': request.user,
        'title': 'Личный кабинет',
        'total_assignments': total_assignments,
        'completed_assignments': completed_assignments,
        'progress_pct': progress_pct,
    })

def _teacher_course_stats(teacher, course):
    """Считает (n_students_from_teacher, avg_progress_percent) для курса."""
    from .models import StudentProgress, Assignment, ManualMark
    students = User.objects.filter(student_profile__teacher=teacher,
                                   enrollments__course=course,
                                   enrollments__is_active=True).distinct()
    n = students.count()
    if n == 0:
        return 0, 0

    assignments = list(Assignment.objects.filter(lesson__module__course=course))
    if not assignments:
        return n, 0

    if course.is_manual:
        completed = ManualMark.objects.filter(
            student__in=students, assignment__in=assignments, is_completed=True
        ).count()
        max_completable = n * len(assignments)
        avg = (completed / max_completable * 100) if max_completable else 0
    else:
        # Сумма correct_attempts/required по всем (student, assignment) парам, делим на n*len(assign)
        records = StudentProgress.objects.filter(student__in=students, assignment__in=assignments)
        total_pct = 0
        for r in records:
            req = r.assignment.required_correct or 1
            total_pct += min(r.correct_attempts / req, 1.0) * 100
        max_completable = n * len(assignments)
        avg = (total_pct / max_completable) if max_completable else 0
    return n, round(avg, 1)


@login_required
def teacher_dashboard(request):
    """Кабинет преподавателя: список учеников + список курсов."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from .models import StudentProfile, StudentProgress, Course, ManualMark
    profiles = (StudentProfile.objects
                .filter(teacher=request.user)
                .select_related('user')
                .order_by('display_name'))

    students_data = []
    total_enrollments = 0
    for sp in profiles:
        student = sp.user
        enrollments = Enrollment.objects.filter(student=student, is_active=True)
        total_courses = enrollments.count()
        avg_course = enrollments.aggregate(avg=Avg('progress'))['avg'] or 0

        progress_records = StudentProgress.objects.filter(student=student)
        total_proto = progress_records.count()
        completed_proto = progress_records.filter(is_completed=True).count()

        # Дополнительно учитываем manual-marks
        manual_done = ManualMark.objects.filter(student=student, is_completed=True).count()

        total_enrollments += total_courses

        students_data.append({
            'profile': sp,
            'student': student,
            'total_courses': total_courses,
            'average_progress': round(avg_course, 1),
            'total_proto': total_proto,
            'completed_proto': completed_proto + manual_done,
            'last_login': student.last_login,
        })

    # Auto-курсы: показываются те, на которые записаны ученики преподавателя.
    # Manual-курсы (задачники): показываются ВСЕ принадлежащие этому преподавателю,
    # даже без учеников.
    teacher_students = User.objects.filter(student_profile__teacher=request.user)

    auto_qs = (Course.objects
               .filter(tracking_mode=Course.TRACKING_AUTO,
                       enrollments__student__in=teacher_students,
                       enrollments__is_active=True)
               .distinct()
               .order_by('order', 'title'))
    # «Мои курсы» преподавателя — задачники + курсы с ДЗ, владелец = он
    owned_qs = (Course.objects
                .filter(tracking_mode__in=[Course.TRACKING_MANUAL, Course.TRACKING_HOMEWORK],
                        owner=request.user)
                .order_by('order', 'title'))

    courses_data = []
    for c in auto_qs:
        n, avg = _teacher_course_stats(request.user, c)
        courses_data.append({'course': c, 'students_count': n, 'avg_progress': avg})

    owned_data = []
    for c in owned_qs:
        n, avg = _teacher_course_stats(request.user, c)
        owned_data.append({
            'course': c, 'students_count': n, 'avg_progress': avg,
            'is_homework': c.is_homework,
        })

    from .models import StudentSubmission
    pending_count = StudentSubmission.objects.filter(
        status=StudentSubmission.STATUS_PENDING,
        student__student_profile__teacher=request.user,
    ).count()

    return render(request, 'users/teacher_dashboard.html', {
        'user': request.user,
        'title': 'Кабинет преподавателя',
        'students_data': students_data,
        'students_count': len(students_data),
        'total_enrollments': total_enrollments,
        'courses_data': courses_data,
        'owned_data': owned_data,
        'pending_submissions_count': pending_count,
    })


@login_required
def teacher_course_progress(request, slug):
    """Сводка по курсу для преподавателя.
    Auto-курсы: таблица «ученик × прототип» с процентами.
    Manual-курсы: список учеников с прогрессом и ссылкой на «отметки»."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from .models import (Course, StudentProgress, Assignment, ManualMark)

    course = get_object_or_404(Course, slug=slug)
    teacher_students = (User.objects
                        .filter(student_profile__teacher=request.user)
                        .select_related('student_profile')
                        .filter(enrollments__course=course, enrollments__is_active=True)
                        .distinct()
                        .order_by('student_profile__display_name'))

    assignments = list(
        Assignment.objects.filter(lesson__module__course=course)
        .select_related('lesson')
        .order_by('lesson__order', 'order')
    )

    total_tasks = len(assignments)

    if course.is_manual:
        marks = ManualMark.objects.filter(
            student__in=teacher_students,
            assignment__in=assignments,
            is_completed=True,
        ).values('student_id').annotate(done=Count('id'))
        done_by_student = {m['student_id']: m['done'] for m in marks}
    else:
        # Для auto считаем «сданные прототипы» — у которых is_completed=True
        progress = StudentProgress.objects.filter(
            student__in=teacher_students, assignment__in=assignments,
            is_completed=True,
        ).values('student_id').annotate(done=Count('id'))
        done_by_student = {p['student_id']: p['done'] for p in progress}

    rows = []
    for s in teacher_students:
        done = done_by_student.get(s.id, 0)
        rows.append({
            'student': s,
            'profile': s.student_profile,
            'completed_count': done,
            'total': total_tasks,
            'percent': round(done / total_tasks * 100) if total_tasks else 0,
        })

    hw_lessons = []
    if course.is_homework:
        for module in course.modules.all().order_by('order'):
            for lesson in module.lessons.all().order_by('-order'):
                hw_lessons.append({
                    'lesson': lesson,
                    'tasks_count': lesson.assignments.count(),
                })

    return render(request, 'users/teacher_course_progress.html', {
        'course': course,
        'rows': rows,
        'is_manual': course.is_manual,
        'is_homework': course.is_homework,
        'total_tasks': total_tasks,
        'hw_lessons': hw_lessons,
        'title': f'{course.title} — прогресс группы',
    })


def _build_paragraphs(course, student):
    """Собирает список параграфов (Lessons) с задачами и состоянием прогресса
    для конкретного ученика. Работает и для auto, и для manual курсов.
    Каждая задача получает атрибуты is_done, percent, submission (для review-задач)."""
    from .models import ManualMark, StudentProgress, StudentSubmission

    lessons = []
    for module in course.modules.all().order_by('order'):
        lessons.extend(
            module.lessons.all().prefetch_related('assignments').order_by('order')
        )

    course_assignment_ids = [
        a.id for lesson in lessons for a in lesson.assignments.all()
    ]

    if course.is_manual:
        marks = ManualMark.objects.filter(
            student=student, assignment_id__in=course_assignment_ids,
        )
        done_set = {m.assignment_id for m in marks if m.is_completed}
        percent_map = {a_id: 100 for a_id in done_set}
    else:
        progress = StudentProgress.objects.filter(
            student=student, assignment_id__in=course_assignment_ids,
        )
        done_set = {p.assignment_id for p in progress if p.is_completed}
        percent_map = {}
        for p in progress:
            req = p.assignment.required_correct or 1
            percent_map[p.assignment_id] = round(min(p.correct_attempts / req, 1.0) * 100)

    # Развёрнутые решения (submissions) — индекс по assignment_id
    submissions_map = {
        s.assignment_id: s
        for s in StudentSubmission.objects.filter(
            student=student, assignment_id__in=course_assignment_ids,
        )
    }

    paragraphs = []
    total_done, total_all = 0, 0
    for lesson in lessons:
        tasks = list(lesson.assignments.all().order_by('order'))
        for t in tasks:
            t.is_done = t.id in done_set
            t.percent = percent_map.get(t.id, 0)
            t.submission = submissions_map.get(t.id)
        done_count = sum(1 for t in tasks if t.is_done)
        total_done += done_count
        total_all += len(tasks)
        paragraphs.append({
            'lesson': lesson,
            'tasks': tasks,
            'done': done_count,
            'total': len(tasks),
            'percent': round(done_count / len(tasks) * 100) if tasks else 0,
        })

    return paragraphs, total_done, total_all


@login_required
def teacher_student_workbook(request, slug, student_id):
    """Раскрывающиеся параграфы с задачами для одного ученика.
    Для manual-курсов — клик по квадратику переключает отметку.
    Для auto-курсов — квадратики отображают прогресс по прототипу (read-only)."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from .models import Course

    course = get_object_or_404(Course, slug=slug)
    student = get_object_or_404(
        User,
        id=student_id,
        role='student',
        student_profile__teacher=request.user,
        enrollments__course=course,
        enrollments__is_active=True,
    )

    paragraphs, total_done, total_all = _build_paragraphs(course, student)

    return render(request, 'users/teacher_student_workbook.html', {
        'course': course,
        'student': student,
        'profile': student.student_profile,
        'paragraphs': paragraphs,
        'total_done': total_done,
        'total_all': total_all,
        'overall_percent': round(total_done / total_all * 100) if total_all else 0,
        'is_manual': course.is_manual,
        'title': f'{student.student_profile.display_name} — {course.title}',
    })


@login_required
def student_course_progress(request, slug):
    """Прогресс ученика по курсу — то же UI, что и у преподавателя,
    но для текущего ученика и read-only."""
    if request.user.role != 'student':
        messages.error(request, 'Доступ только для учеников')
        return redirect('login')

    from .models import Course

    course = get_object_or_404(Course, slug=slug)
    enrollment = Enrollment.objects.filter(
        student=request.user, course=course, is_active=True,
    ).first()
    if not enrollment:
        messages.error(request, 'Вы не записаны на этот курс.')
        return redirect('student_courses')

    paragraphs, total_done, total_all = _build_paragraphs(course, request.user)

    return render(request, 'users/student_course_progress.html', {
        'course': course,
        'paragraphs': paragraphs,
        'total_done': total_done,
        'total_all': total_all,
        'overall_percent': round(total_done / total_all * 100) if total_all else 0,
        'is_manual': course.is_manual,
        'is_homework': course.is_homework,
        'title': f'{course.title} — мой прогресс',
    })


@login_required
def teacher_toggle_mark(request):
    """AJAX-endpoint: переключить отметку `решено / не решено` на (student, assignment).
    POST: student_id, assignment_id."""
    if request.user.role != 'teacher':
        return JsonResponse({'error': 'forbidden'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)

    from .models import ManualMark, Assignment, StudentProfile, Course

    student_id = request.POST.get('student_id')
    assignment_id = request.POST.get('assignment_id')
    if not student_id or not assignment_id:
        return JsonResponse({'error': 'missing'}, status=400)

    # Проверка прав: ученик принадлежит этому преподавателю
    if not StudentProfile.objects.filter(user_id=student_id, teacher=request.user).exists():
        return JsonResponse({'error': 'forbidden'}, status=403)

    # Проверка что задание относится к manual-курсу
    assignment = get_object_or_404(Assignment, id=assignment_id)
    course = assignment.lesson.module.course
    if not course.is_manual:
        return JsonResponse({'error': 'not_manual'}, status=400)

    mark, created = ManualMark.objects.get_or_create(
        student_id=student_id, assignment_id=assignment_id,
        defaults={'is_completed': True, 'marked_by': request.user},
    )
    if not created:
        mark.is_completed = not mark.is_completed
        mark.marked_by = request.user
        mark.save()

    return JsonResponse({'is_completed': mark.is_completed})


@login_required
def teacher_student_detail(request, student_id):
    """Карточка ученика для преподавателя: заметки, история ответов на ДЗ,
    список курсов, кнопка-ссылка на запись на курсы."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from .models import HomeworkAttempt

    student = get_object_or_404(
        User, id=student_id, role='student',
        student_profile__teacher=request.user,
    )
    profile = student.student_profile

    if request.method == 'POST' and 'save_notes' in request.POST:
        profile.notes = (request.POST.get('notes') or '').strip()
        profile.save(update_fields=['notes'])
        return redirect('teacher_student_detail', student_id=student.id)

    enrollments = (Enrollment.objects.filter(student=student, is_active=True)
                   .select_related('course')
                   .order_by('course__order', 'course__title'))

    # История попыток на ДЗ — группируем по курсу
    attempts = (HomeworkAttempt.objects.filter(student=student)
                .select_related('assignment__lesson__module__course')
                .order_by('-created_at')[:200])

    by_course = {}
    for a in attempts:
        course = a.assignment.lesson.module.course
        by_course.setdefault(course.id, {'course': course, 'items': []})['items'].append(a)
    attempts_by_course = list(by_course.values())

    return render(request, 'users/teacher_student_detail.html', {
        'student': student,
        'profile': profile,
        'enrollments': enrollments,
        'attempts_by_course': attempts_by_course,
        'title': profile.display_name,
    })


@login_required
def teacher_student_new(request):
    """Создание нового ученика прямо из ЛК преподавателя."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from .models import StudentProfile

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = (request.POST.get('password') or '').strip()
        display_name = (request.POST.get('display_name') or '').strip() or username
        real_name = (request.POST.get('real_name') or '').strip()
        grade = (request.POST.get('grade') or '').strip()
        notes = (request.POST.get('notes') or '').strip()

        errors = []
        if not username:
            errors.append('Введите логин ученика.')
        elif User.objects.filter(username=username).exists():
            errors.append(f'Логин «{username}» уже занят.')
        if not password or len(password) < 4:
            errors.append('Пароль должен быть не короче 4 символов.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'users/teacher_student_new.html', {
                'title': 'Новый ученик',
                'form_data': request.POST,
            })

        student = User.objects.create_user(
            username=username, password=password, role='student',
        )
        StudentProfile.objects.create(
            user=student,
            display_name=display_name,
            real_name=real_name,
            grade=grade,
            notes=notes,
            teacher=request.user,
        )
        messages.success(request, f'Ученик «{display_name}» создан и привязан к вам.')
        return redirect('teacher_student_enroll', student_id=student.id)

    return render(request, 'users/teacher_student_new.html', {
        'title': 'Новый ученик',
        'form_data': {},
    })


@login_required
def teacher_student_enroll(request, student_id):
    """Запись/отписка ученика на курсы. Видны курсы, доступные преподавателю
    (общие + его задачники)."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    student = get_object_or_404(
        User, id=student_id, role='student',
        student_profile__teacher=request.user,
    )

    # Список курсов: все активные общие + авторские курсы этого преподавателя
    available_courses = Course.objects.filter(is_active=True).filter(
        Q(tracking_mode=Course.TRACKING_AUTO)
        | Q(tracking_mode__in=[Course.TRACKING_MANUAL, Course.TRACKING_HOMEWORK],
            owner=request.user)
    ).order_by('order', 'title')

    if request.method == 'POST':
        selected_ids = set(map(int, request.POST.getlist('courses')))
        for c in available_courses:
            enrolled = Enrollment.objects.filter(student=student, course=c).first()
            if c.id in selected_ids:
                if enrolled:
                    if not enrolled.is_active:
                        enrolled.is_active = True
                        enrolled.save()
                else:
                    Enrollment.objects.create(student=student, course=c)
            else:
                if enrolled and enrolled.is_active:
                    enrolled.is_active = False
                    enrolled.save()
        messages.success(request, f'Записи ученика «{student.student_profile.display_name}» обновлены.')
        return redirect('teacher_dashboard')

    enrolled_ids = set(
        Enrollment.objects.filter(student=student, is_active=True)
        .values_list('course_id', flat=True)
    )

    return render(request, 'users/teacher_student_enroll.html', {
        'title': f'Запись на курсы — {student.student_profile.display_name}',
        'student': student,
        'profile': student.student_profile,
        'courses': available_courses,
        'enrolled_ids': enrolled_ids,
    })


@login_required
def teacher_workbook_new(request):
    """Создание нового задачника (manual-курса) с модулями и диапазонами номеров задач."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from django.utils.text import slugify
    import re

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()

        # Параллельные массивы: имя модуля, начальный №, конечный №
        names = request.POST.getlist('module_name')
        starts = request.POST.getlist('module_start')
        ends = request.POST.getlist('module_end')

        errors = []
        if not title:
            errors.append('Введите название задачника.')

        modules_data = []
        for i, (name, start, end) in enumerate(zip(names, starts, ends), 1):
            name = name.strip()
            if not name and not start and not end:
                continue  # пустая строка — пропускаем
            if not name:
                errors.append(f'Модуль {i}: укажите название.')
                continue
            try:
                s, e = int(start), int(end)
                if s > e:
                    errors.append(f'Модуль «{name}»: начальный номер ({s}) больше конечного ({e}).')
                elif s < 1:
                    errors.append(f'Модуль «{name}»: номер должен быть ≥ 1.')
                else:
                    modules_data.append((name, s, e))
            except (TypeError, ValueError):
                errors.append(f'Модуль «{name}»: укажите числовые начальный и конечный номера.')

        if not modules_data:
            errors.append('Добавьте хотя бы один модуль с задачами.')

        if errors:
            for er in errors:
                messages.error(request, er)
            return render(request, 'users/teacher_workbook_new.html', {
                'title': 'Новый задачник',
                'form_data': request.POST,
                'rows': list(zip(names, starts, ends)) or [('', '', '')],
            })

        # Уникальный slug на основе title + id владельца
        base_slug = slugify(title, allow_unicode=False)
        if not base_slug:
            # На случай кириллического title — генерим из транслита
            base_slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-') or 'workbook'
        slug = f"{base_slug}-{request.user.id}"
        n = 2
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{request.user.id}-{n}"
            n += 1

        course = Course.objects.create(
            title=title,
            slug=slug,
            short_description=description,
            tracking_mode=Course.TRACKING_MANUAL,
            owner=request.user,
            is_active=True,
            order=100,
        )
        # Один модуль "Задачник", внутри — Lesson по каждому "модулю"-параграфу
        wrapper = Module.objects.create(course=course, order=1, title='Задачник')
        total_tasks = 0
        for i, (name, start, end) in enumerate(modules_data, 1):
            lesson = Lesson.objects.create(
                module=wrapper, order=i, title=name, lesson_type='practice',
            )
            assignments = [
                Assignment(
                    lesson=lesson, order=n - start + 1,
                    title=str(n), description='',
                    answer_type='decimal_input', required_correct=1,
                )
                for n in range(start, end + 1)
            ]
            Assignment.objects.bulk_create(assignments)
            total_tasks += len(assignments)

        messages.success(request, f'Задачник «{title}» создан ({total_tasks} задач).')
        return redirect('teacher_course_progress', slug=course.slug)

    return render(request, 'users/teacher_workbook_new.html', {
        'title': 'Новый задачник',
        'form_data': {},
        'rows': [('', '', '')] * 3,  # три пустые строки для модулей
    })


@login_required
def teacher_hw_course_new(request):
    """Создание нового курса с ДЗ. Под одного ученика — основная история."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from django.utils.text import slugify
    import re

    # Список учеников этого преподавателя — для поля «Кому курс»
    student_profiles = (
        StudentProfile.objects.filter(teacher=request.user)
        .select_related('user')
        .order_by('display_name')
    )

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        student_id = request.POST.get('student_id') or ''

        errors = []
        if not title:
            errors.append('Введите название курса.')

        student = None
        if student_id:
            student = User.objects.filter(
                id=student_id, role='student',
                student_profile__teacher=request.user,
            ).first()
            if not student:
                errors.append('Ученик не найден.')

        if errors:
            for er in errors:
                messages.error(request, er)
            return render(request, 'users/teacher_hw_course_new.html', {
                'title': 'Новый курс с ДЗ',
                'form_data': request.POST,
                'students': student_profiles,
            })

        # Уникальный slug
        base_slug = slugify(title, allow_unicode=False)
        if not base_slug:
            base_slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-') or 'hw-course'
        slug = f"{base_slug}-{request.user.id}"
        n = 2
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{request.user.id}-{n}"
            n += 1

        course = Course.objects.create(
            title=title,
            slug=slug,
            tracking_mode=Course.TRACKING_HOMEWORK,
            owner=request.user,
            is_active=True,
            order=100,
        )
        # Один обёртывающий модуль — внутрь будут добавляться Lessons (ДЗ)
        Module.objects.create(course=course, order=1, title='ДЗ')

        if student:
            Enrollment.objects.get_or_create(student=student, course=course)

        return redirect('teacher_hw_lesson_new', slug=course.slug)

    return render(request, 'users/teacher_hw_course_new.html', {
        'title': 'Новый курс с ДЗ',
        'form_data': {},
        'students': student_profiles,
    })


def _parse_hw_tasks(request):
    """Собрать (tasks, errors, raw_rows) из POST.
    tasks — список словарей {condition, answer, image, remove_image, requires_review}.
    raw_rows — то же для повторного рендера формы при ошибке."""
    conditions = request.POST.getlist('task_condition')
    answers = request.POST.getlist('task_answer')
    tasks = []
    errors = []
    raw_rows = []
    for i, (cond, ans) in enumerate(zip(conditions, answers)):
        cond = cond.strip()
        ans = ans.strip()
        requires_review = request.POST.get(f'task_review_{i}') == '1'
        raw_rows.append({
            'condition': cond, 'answer': ans, 'image_url': '',
            'requires_review': requires_review,
        })
        idx_human = i + 1
        if not cond and not ans and not requires_review:
            continue
        if not cond:
            errors.append(f'Задача {idx_human}: укажите условие.')
            continue
        if not requires_review and not ans:
            errors.append(f'Задача {idx_human}: укажите правильный ответ '
                          f'(или включите «требует проверки преподавателем»).')
            continue
        image = request.FILES.get(f'task_image_{i}')
        remove_image = request.POST.get(f'task_remove_image_{i}') == '1'
        tasks.append({
            'condition': cond, 'answer': ans if not requires_review else '',
            'image': image, 'remove_image': remove_image,
            'requires_review': requires_review,
        })
    if not tasks and not errors:
        errors.append('Добавьте хотя бы одну задачу.')
    return tasks, errors, raw_rows


@login_required
def teacher_hw_lesson_new(request, slug):
    """Добавить новое ДЗ (Lesson + Assignments) в курс с ДЗ."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    course = get_object_or_404(
        Course, slug=slug,
        tracking_mode=Course.TRACKING_HOMEWORK,
        owner=request.user,
    )
    wrapper = course.modules.first()
    if not wrapper:
        wrapper = Module.objects.create(course=course, order=1, title='ДЗ')

    if request.method == 'POST':
        lesson_title = (request.POST.get('lesson_title') or '').strip()
        lesson_intro = (request.POST.get('lesson_intro') or '').strip()
        tasks, errors, raw_rows = _parse_hw_tasks(request)
        if not lesson_title:
            errors.insert(0, 'Введите название ДЗ.')

        if errors:
            for er in errors:
                messages.error(request, er)
            return render(request, 'users/teacher_hw_lesson_new.html', {
                'title': 'Новое ДЗ',
                'course': course,
                'form_data': request.POST,
                'rows': raw_rows or [{'condition': '', 'answer': '', 'image_url': '', 'requires_review': False}],
                'is_edit': False,
            })

        next_order = (wrapper.lessons.aggregate(m=Max('order'))['m'] or 0) + 1
        lesson = Lesson.objects.create(
            module=wrapper, order=next_order, title=lesson_title,
            content=lesson_intro,
            lesson_type='practice',
        )
        for i, t in enumerate(tasks, 1):
            Assignment.objects.create(
                lesson=lesson, order=i, title=str(i),
                description=t['condition'],
                answer_type='decimal_input', required_correct=1,
                correct_answer=t['answer'],
                image=t['image'] or None,
                requires_review=t['requires_review'],
            )

        messages.success(request, f'ДЗ «{lesson_title}» добавлено ({len(tasks)} задач).')
        return redirect('teacher_course_progress', slug=course.slug)

    return render(request, 'users/teacher_hw_lesson_new.html', {
        'title': 'Новое ДЗ',
        'course': course,
        'form_data': {},
        'rows': [{'condition': '', 'answer': '', 'image_url': '', 'requires_review': False} for _ in range(3)],
        'is_edit': False,
    })


@login_required
def teacher_hw_lesson_edit(request, slug, lesson_id):
    """Редактирование существующего ДЗ. Сохраняет старые Assignment'ы там, где
    задача с тем же порядковым номером осталась — чтобы не терять прогресс ученика."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    course = get_object_or_404(
        Course, slug=slug,
        tracking_mode=Course.TRACKING_HOMEWORK,
        owner=request.user,
    )
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)

    if request.method == 'POST':
        lesson_title = (request.POST.get('lesson_title') or '').strip()
        lesson_intro = (request.POST.get('lesson_intro') or '').strip()
        tasks, errors, raw_rows = _parse_hw_tasks(request)
        if not lesson_title:
            errors.insert(0, 'Введите название ДЗ.')

        if errors:
            for er in errors:
                messages.error(request, er)
            return render(request, 'users/teacher_hw_lesson_new.html', {
                'title': 'Редактировать ДЗ',
                'course': course,
                'lesson': lesson,
                'form_data': request.POST,
                'rows': raw_rows or [{'condition': '', 'answer': '', 'image_url': '', 'requires_review': False}],
                'is_edit': True,
            })

        lesson.title = lesson_title
        lesson.content = lesson_intro
        lesson.save(update_fields=['title', 'content'])

        # Diff: обновляем по порядку, добавляем новые, удаляем лишние.
        existing = list(lesson.assignments.order_by('order'))
        for i, t in enumerate(tasks, 1):
            if i <= len(existing):
                a = existing[i - 1]
                a.title = str(i)
                a.description = t['condition']
                a.correct_answer = t['answer']
                a.requires_review = t['requires_review']
                if t['image']:
                    a.image = t['image']
                elif t['remove_image']:
                    a.image = None
                a.save()
            else:
                Assignment.objects.create(
                    lesson=lesson, order=i, title=str(i),
                    description=t['condition'],
                    answer_type='decimal_input', required_correct=1,
                    correct_answer=t['answer'],
                    image=t['image'] or None,
                    requires_review=t['requires_review'],
                )
        if len(tasks) < len(existing):
            for a in existing[len(tasks):]:
                a.delete()  # каскадно удалит StudentProgress по этой задаче

        messages.success(request, f'ДЗ «{lesson_title}» сохранено.')
        return redirect('teacher_course_progress', slug=course.slug)

    rows = [
        {
            'condition': a.description,
            'answer': a.correct_answer,
            'image_url': a.image.url if a.image else '',
            'requires_review': a.requires_review,
        }
        for a in lesson.assignments.order_by('order')
    ]
    if not rows:
        rows = [{'condition': '', 'answer': '', 'image_url': '', 'requires_review': False}]
    return render(request, 'users/teacher_hw_lesson_new.html', {
        'title': 'Редактировать ДЗ',
        'course': course,
        'lesson': lesson,
        'form_data': {'lesson_title': lesson.title},
        'lesson_intro': lesson.content,
        'rows': rows,
        'is_edit': True,
    })


@login_required
@require_POST
def teacher_hw_lesson_delete(request, slug, lesson_id):
    """Удаление ДЗ вместе со всеми задачами и прогрессом по ним."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    course = get_object_or_404(
        Course, slug=slug,
        tracking_mode=Course.TRACKING_HOMEWORK,
        owner=request.user,
    )
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
    title = lesson.title
    lesson.delete()
    messages.success(request, f'ДЗ «{title}» удалено.')
    return redirect('teacher_course_progress', slug=course.slug)


@login_required
@require_POST
def teacher_hw_lesson_duplicate(request, slug, lesson_id):
    """Копия ДЗ в том же курсе. Прогресс учеников по новой копии — пустой."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    course = get_object_or_404(
        Course, slug=slug,
        tracking_mode=Course.TRACKING_HOMEWORK,
        owner=request.user,
    )
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)

    next_order = (lesson.module.lessons.aggregate(m=Max('order'))['m'] or 0) + 1
    new_lesson = Lesson.objects.create(
        module=lesson.module,
        order=next_order,
        title=f'{lesson.title} (копия)',
        content=lesson.content,
        lesson_type=lesson.lesson_type,
    )
    for a in lesson.assignments.order_by('order'):
        Assignment.objects.create(
            lesson=new_lesson, order=a.order, title=a.title,
            description=a.description,
            answer_type=a.answer_type,
            required_correct=a.required_correct,
            correct_answer=a.correct_answer,
            image=a.image,  # ссылка на тот же файл
            requires_review=a.requires_review,
        )

    messages.success(request, f'ДЗ «{lesson.title}» скопировано.')
    return redirect('teacher_hw_lesson_edit', slug=course.slug, lesson_id=new_lesson.id)


@login_required
def teacher_hw_lesson_export(request, slug, lesson_id):
    """Скачать ДЗ в виде JSON-файла. Картинки в файл не пакуются."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    course = get_object_or_404(
        Course, slug=slug,
        tracking_mode=Course.TRACKING_HOMEWORK,
        owner=request.user,
    )
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)

    payload = {
        'version': 1,
        'lesson_title': lesson.title,
        'lesson_intro': lesson.content,
        'tasks': [
            {
                'condition': a.description,
                'answer': a.correct_answer,
                'requires_review': a.requires_review,
            }
            for a in lesson.assignments.order_by('order')
        ],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    safe_title = lesson.title.replace('/', '-').replace('\\', '-')[:80]
    response = HttpResponse(body, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename*=UTF-8\'\'{quote(safe_title)}.json'
    )
    return response


@login_required
def teacher_hw_lesson_import(request, slug):
    """Загрузить JSON и создать новое ДЗ в курсе из его содержимого."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    course = get_object_or_404(
        Course, slug=slug,
        tracking_mode=Course.TRACKING_HOMEWORK,
        owner=request.user,
    )

    if request.method == 'POST':
        f = request.FILES.get('file')
        if not f:
            messages.error(request, 'Выберите JSON-файл.')
            return redirect('teacher_hw_lesson_import', slug=course.slug)

        try:
            data = json.loads(f.read().decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            messages.error(request, f'Не удалось разобрать JSON: {e}')
            return redirect('teacher_hw_lesson_import', slug=course.slug)

        title = (data.get('lesson_title') or '').strip()
        intro = (data.get('lesson_intro') or '').strip()
        raw_tasks = data.get('tasks') or []
        if not title or not raw_tasks:
            messages.error(request, 'В файле не хватает названия ДЗ или задач.')
            return redirect('teacher_hw_lesson_import', slug=course.slug)

        valid_tasks = []
        for i, t in enumerate(raw_tasks, 1):
            cond = (t.get('condition') or '').strip()
            ans = (t.get('answer') or '').strip()
            req = bool(t.get('requires_review'))
            if not cond:
                continue
            if not req and not ans:
                continue
            valid_tasks.append((cond, ans if not req else '', req))
        if not valid_tasks:
            messages.error(request, 'В файле нет задач, которые можно импортировать.')
            return redirect('teacher_hw_lesson_import', slug=course.slug)

        wrapper = course.modules.first()
        if not wrapper:
            wrapper = Module.objects.create(course=course, order=1, title='ДЗ')
        next_order = (wrapper.lessons.aggregate(m=Max('order'))['m'] or 0) + 1

        new_lesson = Lesson.objects.create(
            module=wrapper, order=next_order, title=title,
            content=intro, lesson_type='practice',
        )
        for i, (cond, ans, req) in enumerate(valid_tasks, 1):
            Assignment.objects.create(
                lesson=new_lesson, order=i, title=str(i),
                description=cond,
                answer_type='decimal_input', required_correct=1,
                correct_answer=ans,
                requires_review=req,
            )

        messages.success(request, f'Импортировано ДЗ «{title}» ({len(valid_tasks)} задач).')
        return redirect('teacher_hw_lesson_edit', slug=course.slug, lesson_id=new_lesson.id)

    return render(request, 'users/teacher_hw_lesson_import.html', {
        'course': course,
        'title': 'Импорт ДЗ',
    })


@login_required
@require_POST
def submit_hw_solution(request, assignment_id):
    """Ученик отправляет развёрнутое решение на проверку преподавателю
    (для задач с requires_review=True)."""
    if request.user.role != 'student':
        messages.error(request, 'Доступ только для учеников')
        return redirect('login')

    from .models import StudentSubmission

    assignment = get_object_or_404(Assignment, id=assignment_id, requires_review=True)
    course = assignment.lesson.module.course
    if not course.is_homework:
        messages.error(request, 'Это не курс с ДЗ.')
        return redirect('student_courses')

    text = (request.POST.get('text') or '').strip()
    file = request.FILES.get('file')

    if not text and not file:
        messages.error(request, 'Добавьте текст решения или прикрепите файл.')
        return redirect('student_course_progress', slug=course.slug)

    sub, _ = StudentSubmission.objects.get_or_create(
        student=request.user, assignment=assignment,
        defaults={'status': StudentSubmission.STATUS_PENDING},
    )
    # Если уже принято — больше ничего менять нельзя.
    if sub.status == StudentSubmission.STATUS_ACCEPTED:
        messages.warning(request, 'Это решение уже принято.')
        return redirect('student_course_progress', slug=course.slug)

    sub.text = text
    if file:
        sub.file = file
    sub.status = StudentSubmission.STATUS_PENDING
    sub.teacher_comment = ''
    sub.reviewed_at = None
    sub.reviewed_by = None
    sub.save()

    return redirect('student_course_progress', slug=course.slug)


@login_required
def teacher_submissions(request):
    """Решения учеников преподавателя — с фильтром по статусу.
    По умолчанию показываются ожидающие проверки."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from .models import StudentSubmission

    base_qs = (StudentSubmission.objects
               .filter(student__student_profile__teacher=request.user)
               .select_related('student__student_profile',
                               'assignment__lesson__module__course'))

    counts = {
        'pending': base_qs.filter(status=StudentSubmission.STATUS_PENDING).count(),
        'accepted': base_qs.filter(status=StudentSubmission.STATUS_ACCEPTED).count(),
        'rejected': base_qs.filter(status=StudentSubmission.STATUS_REJECTED).count(),
    }

    status = request.GET.get('status') or 'pending'
    if status not in ('pending', 'accepted', 'rejected', 'all'):
        status = 'pending'

    submissions_qs = base_qs
    if status != 'all':
        submissions_qs = submissions_qs.filter(status=status)

    if status == 'pending':
        submissions_qs = submissions_qs.order_by('submitted_at')
    else:
        submissions_qs = submissions_qs.order_by('-reviewed_at', '-submitted_at')

    return render(request, 'users/teacher_submissions.html', {
        'submissions': submissions_qs,
        'status': status,
        'counts': counts,
        'title': 'Решения учеников',
    })


@login_required
@require_POST
def teacher_review_submission(request, sub_id):
    """Принять/вернуть на доработку развёрнутое решение."""
    if request.user.role != 'teacher':
        messages.error(request, 'Доступ только для преподавателей')
        return redirect('login')

    from .models import StudentSubmission, StudentProgress

    sub = get_object_or_404(
        StudentSubmission, id=sub_id,
        student__student_profile__teacher=request.user,
    )
    action = request.POST.get('action')
    comment = (request.POST.get('comment') or '').strip()

    if action == 'accept':
        sub.status = StudentSubmission.STATUS_ACCEPTED
        sub.teacher_comment = comment
        sub.reviewed_at = timezone.now()
        sub.reviewed_by = request.user
        sub.save()
        # Засчитываем задачу как выполненную
        sp, _ = StudentProgress.objects.get_or_create(
            student=sub.student, assignment=sub.assignment,
        )
        if not sp.is_completed:
            sp.is_completed = True
            sp.completed_at = timezone.now()
        sp.correct_attempts = max(sp.correct_attempts or 0, 1)
        sp.save()
    elif action == 'reject':
        sub.status = StudentSubmission.STATUS_REJECTED
        sub.teacher_comment = comment
        sub.reviewed_at = timezone.now()
        sub.reviewed_by = request.user
        sub.save()
    return redirect('teacher_submissions')


@require_POST
def check_hw_answer(request, assignment_id):
    """AJAX-проверка ответа ученика на задачу из курса с ДЗ.
    Анонимам — только результат, без записи прогресса."""
    from .models import StudentProgress
    from .answer_check import check_answer

    assignment = get_object_or_404(Assignment, id=assignment_id)
    course = assignment.lesson.module.course
    if not course.is_homework:
        return JsonResponse({'error': 'not_homework'}, status=400)
    if assignment.requires_review:
        return JsonResponse(
            {'error': 'Эта задача требует развёрнутого решения, а не короткого ответа.'},
            status=400,
        )

    user_answer = (request.POST.get('answer') or '').strip()
    if not user_answer:
        return JsonResponse({'error': 'Введите ответ'}, status=400)

    expected = (assignment.correct_answer or '').strip()
    is_correct, message = check_answer(user_answer, expected)

    is_student = request.user.is_authenticated and request.user.role == 'student'
    if not is_student:
        return JsonResponse({'correct': is_correct, 'message': message, 'anonymous': True})

    from .models import HomeworkAttempt
    HomeworkAttempt.objects.create(
        student=request.user, assignment=assignment,
        answer=user_answer, is_correct=is_correct,
    )

    sp, _ = StudentProgress.objects.get_or_create(
        student=request.user, assignment=assignment,
    )
    sp.total_attempts = (sp.total_attempts or 0) + 1
    if is_correct:
        sp.correct_attempts = max(sp.correct_attempts or 0, 1)
        if not sp.is_completed:
            sp.is_completed = True
            sp.completed_at = timezone.now()
    sp.save()

    return JsonResponse({'correct': is_correct, 'message': message})


def logout_view(request):
    """Выход из системы"""
    logout(request)
    return redirect('login')

def courses_list(request):
    """Каталог курсов. Авторские курсы (задачники + ДЗ) скрываются от всех, кроме их владельца.
    Ученикам, записанным на конкретный авторский курс, он тоже виден."""
    courses = Course.objects.filter(is_active=True).order_by('order')
    owned_modes = [Course.TRACKING_MANUAL, Course.TRACKING_HOMEWORK]
    if request.user.is_authenticated and request.user.role == 'teacher':
        courses = courses.exclude(
            Q(tracking_mode__in=owned_modes) & ~Q(owner=request.user)
        )
    elif request.user.is_authenticated and request.user.role == 'student':
        # Ученик видит общие курсы + те, на которые он записан
        courses = courses.filter(
            Q(tracking_mode=Course.TRACKING_AUTO)
            | Q(tracking_mode__in=owned_modes,
                enrollments__student=request.user, enrollments__is_active=True)
        ).distinct()
    else:
        courses = courses.exclude(tracking_mode__in=owned_modes)
    
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

    # ID уроков, в которых есть хотя бы один Assignment с генератором —
    # для них в шаблоне делаем клик-переход на единый экран практики.
    generator_lesson_ids = set(
        Assignment.objects.filter(
            lesson__module__course=course,
            problem_generator__isnull=False,
        ).values_list('lesson_id', flat=True).distinct()
    )

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
        'generator_lesson_ids': generator_lesson_ids,
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
    
    enrollment.delete()
    return redirect('student_courses')

# ──────────────────────────────────────────────────────────────────────────────
# Теоретический (текстовый) урок-методичка с кнопкой «Прочитано».
# Используется для уроков типа text/hybrid, у которых есть Lesson.content,
# но нет Assignment'ов и TaskGroup. Прогресс — модель LessonProgress.
# ──────────────────────────────────────────────────────────────────────────────

def lesson_detail(request, lesson_id):
    """Страница теоретического урока (методичка)."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.module.course

    is_read = False
    if request.user.is_authenticated and request.user.role == 'student':
        is_read = LessonProgress.objects.filter(
            student=request.user, lesson=lesson, is_read=True,
        ).exists()

    # Соседние уроки внутри того же модуля для навигации «← Назад / Вперёд →».
    siblings = list(lesson.module.lessons.order_by('order', 'id'))
    try:
        idx = siblings.index(lesson)
    except ValueError:
        idx = 0
    prev_lesson = siblings[idx - 1] if idx > 0 else None
    next_lesson = siblings[idx + 1] if idx + 1 < len(siblings) else None

    return render(request, 'users/lesson_detail.html', {
        'lesson': lesson,
        'course': course,
        'is_read': is_read,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
        'title': lesson.title,
    })


@login_required
@require_POST
def mark_lesson_read(request, lesson_id):
    """AJAX: отметить теоретический урок как прочитанный."""
    if request.user.role != 'student':
        return JsonResponse({'error': 'only students'}, status=403)
    lesson = get_object_or_404(Lesson, id=lesson_id)
    progress, _ = LessonProgress.objects.get_or_create(
        student=request.user, lesson=lesson,
    )
    progress.is_read = True
    progress.read_at = timezone.now()
    progress.save()
    return JsonResponse({'ok': True, 'is_read': True})


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
from .models import PDFBookmark, PDFAnnotation
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