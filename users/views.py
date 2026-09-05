# users/views.py
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, Max, F
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from .models import (
    Course, Module, Lesson, Assignment,
    Enrollment, User, StudentProfile, LessonProgress,
    StudentProgress, ManualMark, StudentSubmission, HomeworkAttempt, StudentLink,
    HomeworkExtension, Notification, Grade,
    TestQuestion, AnswerOption, ProblemGenerator, GeneratedProblem,
)
from django.http import JsonResponse, HttpResponse, Http404
from urllib.parse import quote
from django.views.decorators.http import require_POST
from .decorators import student_required, teacher_required
from .answer_check import check_answer
from .progress import mark_progress, needed_for
from .grades import course_score
from .uploads import validate_homework_file
from .notifications import notify_submitted, notify_reviewed
from .homework import (homework_for, lesson_report, dates_for,
                       accepts_from)
from django.db import transaction
from django.utils.text import slugify
import datetime
import json
import re
from collections import defaultdict

def home_view(request):
    """Главная страница"""
    return render(request, 'users/home.html')

def login_view(request):
    """Страница входа.

    Уважает ?next= (с проверкой url_has_allowed_host_and_scheme от open-redirect):
    ученик по ссылке на вариант → /login/?next=/exam/variant/CODE/ → после входа
    возвращается на вариант, а не на дашборд.
    """
    next_url = request.POST.get('next') or request.GET.get('next') or ''

    def _redirect_after(user):
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        if user.role == 'student':
            return redirect('student_dashboard')
        elif user.role == 'teacher':
            return redirect('teacher_dashboard')
        return redirect('/admin/')

    if request.user.is_authenticated:
        return _redirect_after(request.user)

    error = None
    if request.method == 'POST':
        # Логин обрезаем: с телефона он приходит с пробелом на конце — клавиатура
        # добавляет его вслед за подсказкой, а сравнение точное, и вход
        # отвергался. Пароль НЕ трогаем: пробелы в нём могут быть значащими.
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        if not username or not password:
            error = "Пожалуйста, заполните все поля"
        else:
            user = authenticate(request, username=username, password=password)
            if user is None:
                # Вторая попытка — без учёта регистра (телефон делает первую
                # букву заглавной). Только если такой логин РОВНО ОДИН: если в
                # базе есть и «аня», и «Аня», угадывать за человека нельзя.
                # Сравниваем в Python, а не через __iexact: SQLite приводит
                # регистр только у латиницы, и локально логин «Полина» вёл бы
                # себя не так, как на боевом PostgreSQL. Перебор недорог —
                # учеников на таком сайте десятки, и только при неудачном входе.
                folded = username.casefold()
                same = [u for u in User.objects.only('id', 'username')
                        if u.username.casefold() == folded]
                if len(same) == 1:
                    user = authenticate(request, username=same[0].username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    return _redirect_after(user)
                else:
                    error = "Аккаунт отключен. Обратитесь к администратору."
            else:
                error = "Неверный логин или пароль"

    return render(request, 'users/login.html', {'error': error, 'next': next_url})

# users/views.py - функция student_dashboard

def course_progress_percent(student, course):
    """Процент прохождения курса учеником (0..100), считается на лету.

    По заданиям: manual-курс — по отметкам преподавателя (ManualMark),
    иначе — по авто-прогрессу (StudentProgress). Если заданий в курсе нет
    (курс-методичка) — по прочитанным теоретическим урокам (LessonProgress).
    Опора на поле Enrollment.progress убрана: оно нигде не заполнялось → 0%.
    """

    assignment_ids = list(
        Assignment.objects.filter(lesson__module__course=course)
        .values_list('id', flat=True)
    )
    total = len(assignment_ids)
    if total:
        if course.is_manual:
            done = ManualMark.objects.filter(
                student=student, assignment_id__in=assignment_ids, is_completed=True,
            ).count()
        else:
            done = StudentProgress.objects.filter(
                student=student, assignment_id__in=assignment_ids, is_completed=True,
            ).count()
        return round(done / total * 100)

    # Курс без заданий — считаем по прочитанным теоретическим урокам.
    lesson_ids = list(
        Lesson.objects.filter(module__course=course).values_list('id', flat=True)
    )
    if not lesson_ids:
        return 0
    read = LessonProgress.objects.filter(
        student=student, lesson_id__in=lesson_ids, is_read=True,
    ).count()
    return round(read / len(lesson_ids) * 100)


@student_required
def student_dashboard(request):
    """Личный кабинет ученика."""

    enrollments = (Enrollment.objects
                   .filter(student=request.user, is_active=True)
                   .select_related('course'))
    percents = [course_progress_percent(request.user, e.course) for e in enrollments]
    courses_count = len(percents)
    progress_pct = round(sum(percents) / courses_count) if courses_count else 0

    # Ссылки от преподавателя: личные плюс общие (те, что он положил всем).
    # Профиля может не быть — тогда преподаватель неизвестен и общих нет.
    профиль = getattr(request.user, 'student_profile', None)
    условие = Q(student=request.user)
    if профиль and профиль.teacher_id:
        условие |= Q(student__isnull=True, teacher_id=профиль.teacher_id)
    links = list(StudentLink.objects.filter(условие).order_by('order', 'id'))

    homework = homework_for(request.user)

    return render(request, 'users/dashboard.html', {
        'homework': homework,
        'overdue_count': sum(1 for h in homework if h['overdue']),
        'user': request.user,
        'title': 'Личный кабинет',
        'has_courses': courses_count > 0,
        'courses_count': courses_count,
        'progress_pct': progress_pct,
        'links': links,
    })

def _teacher_course_stats(teacher, course):
    """Считает (n_students_from_teacher, avg_progress_percent) для курса."""
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
        records = (StudentProgress.objects
                   .filter(student__in=students, assignment__in=assignments)
                   .select_related('assignment'))
        total_pct = 0
        for r in records:
            req = r.assignment.required_correct or 1
            total_pct += min(r.correct_attempts / req, 1.0) * 100
        max_completable = n * len(assignments)
        avg = (total_pct / max_completable) if max_completable else 0
    return n, round(avg, 1)


@teacher_required
def teacher_dashboard(request):
    """Кабинет преподавателя: список учеников + список курсов."""

    profiles = list(StudentProfile.objects
                    .filter(teacher=request.user)
                    .select_related('user')
                    .order_by('display_name'))
    student_ids = [p.user_id for p in profiles]

    # ── Прогресс учеников считаем БАТЧЕМ (без N+1) ────────────────────────
    enrollments = list(Enrollment.objects.filter(
        student_id__in=student_ids, is_active=True).select_related('course'))
    courses_of = defaultdict(list)          # student_id -> [Course]
    course_ids = set()
    for e in enrollments:
        courses_of[e.student_id].append(e.course)
        course_ids.add(e.course_id)
    student_course_ids = {sid: {c.id for c in cs} for sid, cs in courses_of.items()}

    # course_id -> [assignment_id]; assignment_id -> course_id
    course_assignments = defaultdict(list)
    assignment_course = {}
    for aid, cid in Assignment.objects.filter(
            lesson__module__course_id__in=course_ids
    ).values_list('id', 'lesson__module__course_id'):
        course_assignments[cid].append(aid)
        assignment_course[aid] = cid
    all_assignment_ids = list(assignment_course)

    # course_id -> число уроков (для курсов без заданий); lesson_id -> course_id
    course_lesson_count = defaultdict(int)
    lesson_course = {}
    for lid, cid in Lesson.objects.filter(
            module__course_id__in=course_ids).values_list('id', 'module__course_id'):
        course_lesson_count[cid] += 1
        lesson_course[lid] = cid

    # StudentProgress: завершённые по (ученик, курс)
    sp_done = defaultdict(int)          # (student_id, course_id) -> completed
    for sid, aid in StudentProgress.objects.filter(
            student_id__in=student_ids, assignment_id__in=all_assignment_ids,
            is_completed=True,
    ).values_list('student_id', 'assignment_id'):
        sp_done[(sid, assignment_course[aid])] += 1

    # ManualMark: завершённые по (ученик, курс)
    mm_done = defaultdict(int)
    for sid, aid in ManualMark.objects.filter(
            student_id__in=student_ids, is_completed=True,
            assignment_id__in=all_assignment_ids
    ).values_list('student_id', 'assignment_id'):
        mm_done[(sid, assignment_course[aid])] += 1

    # LessonProgress: прочитанные уроки по (ученик, курс) — для курсов без заданий
    lp_read = defaultdict(int)
    for sid, lid in LessonProgress.objects.filter(
            student_id__in=student_ids, is_read=True,
            lesson_id__in=list(lesson_course)
    ).values_list('student_id', 'lesson_id'):
        lp_read[(sid, lesson_course[lid])] += 1

    def _percent(sid, course):
        aids = course_assignments.get(course.id, [])
        if aids:
            done = (mm_done if course.is_manual else sp_done).get((sid, course.id), 0)
            return round(done / len(aids) * 100)
        n_lessons = course_lesson_count.get(course.id, 0)
        if not n_lessons:
            return 0
        return round(lp_read.get((sid, course.id), 0) / n_lessons * 100)

    students_data = []
    total_enrollments = 0
    for sp in profiles:
        sid = sp.user_id
        my_courses = courses_of.get(sid, [])
        total_courses = len(my_courses)
        _percents = [_percent(sid, c) for c in my_courses]
        avg_course = round(sum(_percents) / len(_percents), 1) if _percents else 0
        # «Решено X из Y»: числитель и знаменатель — по одному набору (все задания
        # курсов ученика), иначе счётчик мог давать >100% или вид N/0.
        total_proto = 0
        completed_proto = 0
        for c in my_courses:
            total_proto += len(course_assignments.get(c.id, []))
            completed_proto += (mm_done if c.is_manual else sp_done).get((sid, c.id), 0)
        total_enrollments += total_courses
        students_data.append({
            'profile': sp,
            'student': sp.user,
            'total_courses': total_courses,
            'average_progress': avg_course,
            'total_proto': total_proto,
            'completed_proto': completed_proto,
            'last_login': sp.user.last_login,
        })

    # Auto-курсы: показываются те, на которые записаны ученики преподавателя.
    # Manual-курсы (задачники): показываются ВСЕ принадлежащие этому преподавателю,
    # даже без учеников.
    teacher_students = User.objects.filter(student_profile__teacher=request.user)

    auto_qs = (Course.objects
               .filter(is_public=True,
                       enrollments__student__in=teacher_students,
                       enrollments__is_active=True)
               .distinct()
               .order_by('order', 'title'))
    # «Мои курсы» преподавателя — все курсы, где владелец = он (включая приватные auto)
    owned_qs = (Course.objects
                .filter(owner=request.user)
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
            'kind': ('ОГЭ-курс' if c.tracking_mode == Course.TRACKING_AUTO
                     else 'курс с ДЗ' if c.is_homework else 'задачник'),
            'is_oge': c.tracking_mode == Course.TRACKING_AUTO,
        })

    pending_count = StudentSubmission.objects.filter(
        is_latest=True,
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


@teacher_required
def teacher_course_progress(request, slug):
    """Сводка по курсу для преподавателя.
    Auto-курсы: таблица «ученик × прототип» с процентами.
    Manual-курсы: список учеников с прогрессом и ссылкой на «отметки»."""


    course = get_object_or_404(Course, slug=slug)
    if not course.is_public and course.owner_id != request.user.id:
        messages.error(request, 'Это не ваш курс.')
        return redirect('teacher_dashboard')
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
                    'due': lesson.due_date,
                    'overdue': bool(lesson.due_date and lesson.due_date < timezone.localdate()),
                    'cutoff': lesson.cutoff_date,
                    'closed': not lesson.accepts_submissions(),
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
        ).select_related('assignment')
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
            is_latest=True,
        )
    }
    # Сколько всего попыток было по каждой задаче — чтобы показать ученику,
    # что прежние никуда не делись.
    attempts_map = {}
    for aid, n in (StudentSubmission.objects
                   .filter(student=student, assignment_id__in=course_assignment_ids)
                   .values_list('assignment_id')
                   .annotate(n=Count('id'))):
        attempts_map[aid] = n

    paragraphs = []
    total_done, total_all = 0, 0
    for lesson in lessons:
        tasks = list(lesson.assignments.all().order_by('order'))
        for t in tasks:
            t.is_done = t.id in done_set
            t.percent = percent_map.get(t.id, 0)
            t.submission = submissions_map.get(t.id)
            t.attempts = attempts_map.get(t.id, 0)
            # Если title — короткое число (как в задачнике Поповой), показать его
            # в квадратике вместо forloop.counter → получится сквозная нумерация.
            title_clean = (t.title or '').strip()
            t.display_num = title_clean if title_clean.isdigit() and len(title_clean) <= 5 else None
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


@teacher_required
def teacher_student_workbook(request, slug, student_id):
    """Раскрывающиеся параграфы с задачами для одного ученика.
    Для manual-курсов — клик по квадратику переключает отметку.
    Для auto-курсов — квадратики отображают прогресс по прототипу (read-only)."""


    course = get_object_or_404(Course, slug=slug)
    if not course.is_public and course.owner_id != request.user.id:
        messages.error(request, 'Это не ваш курс.')
        return redirect('teacher_dashboard')
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


@student_required
def student_course_progress(request, slug):
    """Прогресс ученика по курсу — то же UI, что и у преподавателя,
    но для текущего ученика и read-only."""


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
        # Итог по баллам — ОБЕ цифры сразу: сумма к сумме и среднее процентов.
        # Они расходятся, когда номера разного веса, и выбирать за человека
        # одну из них — значит спрятать половину правды.
        'score': course_score(request.user, course),
        'overall_percent': round(total_done / total_all * 100) if total_all else 0,
        'is_manual': course.is_manual,
        'is_homework': course.is_homework,
        'title': f'{course.title} — мой прогресс',
    })


@teacher_required
@require_POST
def teacher_toggle_mark(request):
    """AJAX-endpoint: переключить отметку `решено / не решено` на (student, assignment).
    POST: student_id, assignment_id."""


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


@teacher_required
def teacher_student_detail(request, student_id):
    """Карточка ученика для преподавателя: заметки, история ответов на ДЗ,
    список курсов, кнопка-ссылка на запись на курсы."""


    student = get_object_or_404(
        User, id=student_id, role='student',
        student_profile__teacher=request.user,
    )
    profile = student.student_profile

    if request.method == 'POST' and 'save_notes' in request.POST:
        profile.notes = (request.POST.get('notes') or '').strip()
        profile.save(update_fields=['notes'])
        return redirect('teacher_student_detail', student_id=student.id)

    # ── Ссылки в кабинет ученика ─────────────────────────────────────────
    if request.method == 'POST' and 'add_link' in request.POST:
        title = (request.POST.get('link_title') or '').strip()[:120]
        url = (request.POST.get('link_url') or '').strip()
        всем = bool(request.POST.get('link_all'))
        if not title or not url:
            messages.error(request, 'Нужны и заголовок, и адрес.')
        else:
            ссылка = StudentLink(
                teacher=request.user,
                student=None if всем else student,
                title=title, url=url,
            )
            try:
                # full_clean проверит схему адреса: только http и https.
                ссылка.full_clean()
                ссылка.save()
            except ValidationError:
                messages.error(request, 'Адрес должен начинаться с http:// или https://')
        return redirect('teacher_student_detail', student_id=student.id)

    if request.method == 'POST' and 'del_link' in request.POST:
        # teacher=request.user в фильтре обязателен: без него чужую ссылку
        # можно было бы удалить, подставив её номер.
        StudentLink.objects.filter(
            id=request.POST.get('del_link'), teacher=request.user).delete()
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

    links = list(StudentLink.objects
                 .filter(Q(student=student) | Q(student__isnull=True), teacher=request.user)
                 .order_by('order', 'id'))

    return render(request, 'users/teacher_student_detail.html', {
        'student': student,
        'profile': profile,
        'enrollments': enrollments,
        'attempts_by_course': attempts_by_course,
        'links': links,
        'title': profile.display_name,
    })


@teacher_required
def teacher_student_new(request):
    """Создание нового ученика прямо из ЛК преподавателя."""


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

        with transaction.atomic():
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


@teacher_required
def teacher_student_enroll(request, student_id):
    """Запись/отписка ученика на курсы. Видны курсы, доступные преподавателю
    (общие + его задачники)."""

    student = get_object_or_404(
        User, id=student_id, role='student',
        student_profile__teacher=request.user,
    )

    # Список курсов: все активные общие + авторские курсы этого преподавателя
    available_courses = Course.objects.filter(is_active=True).filter(
        Q(is_public=True) | Q(owner=request.user)
    ).order_by('order', 'title')

    if request.method == 'POST':
        selected_ids = {int(x) for x in request.POST.getlist('courses') if x.isdigit()}
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


@teacher_required
def teacher_workbook_new(request):
    """Создание нового задачника (manual-курса) с модулями и диапазонами номеров задач."""


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
                elif e - s + 1 > 1000:
                    errors.append(f'Модуль «{name}»: слишком большой диапазон ({e - s + 1} задач), максимум 1000.')
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


@teacher_required
def teacher_hw_course_new(request):
    """Создание нового курса с ДЗ. Под одного ученика — основная история."""


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


@teacher_required
def teacher_oge_course_new(request):
    """Создание своего закрытого курса ОГЭ-типа.

    Движок — auto (ученики решают на сайте, автопроверка, как в общем ОГЭ),
    но курс приватный: is_public=False, owner=препод. Виден только владельцу и
    записанным им ученикам. Наполнение темами/задачами — отдельно (Фаза 2)."""
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()

        if not title:
            messages.error(request, 'Введите название курса.')
            return render(request, 'users/teacher_oge_course_new.html', {
                'title': 'Новый ОГЭ-курс',
                'form_data': request.POST,
            })

        base_slug = slugify(title, allow_unicode=False) or 'oge-course'
        slug = base_slug
        n = 2
        while Course.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{request.user.id}-{n}'
            n += 1

        course = Course.objects.create(
            title=title,
            slug=slug,
            short_description=description[:300],
            tracking_mode=Course.TRACKING_AUTO,
            is_public=False,
            owner=request.user,
            is_active=True,
            order=100,
        )
        # Стартовый модуль-обёртка, внутрь Фаза 2 будет класть темы (Lesson)
        Module.objects.create(course=course, order=1, title='Задания')

        messages.success(
            request, f'Курс «{title}» создан. Добавьте темы и задачи.')
        return redirect('teacher_course_edit', slug=course.slug)

    return render(request, 'users/teacher_oge_course_new.html', {
        'title': 'Новый ОГЭ-курс',
        'form_data': {},
    })


# ─── Управление своим ОГЭ-курсом (Фаза 2A): темы и прототипы ────────────────

@teacher_required
def teacher_course_edit(request, slug):
    """Страница управления курсом: темы (Lesson) и прототипы (Assignment)."""
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    module = course.modules.order_by('order').first()
    if module is None:
        module = Module.objects.create(course=course, order=1, title='Задания')

    themes = []
    for lesson in module.lessons.order_by('order'):
        prototypes = list(
            lesson.assignments.annotate(q_count=Count('questions')).order_by('order')
        )
        themes.append({'lesson': lesson, 'prototypes': prototypes})

    return render(request, 'users/teacher_course_edit.html', {
        'title': f'Управление: {course.title}',
        'course': course,
        'themes': themes,
    })


@teacher_required
@require_POST
def teacher_theme_new(request, slug):
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    module = course.modules.order_by('order').first()
    if module is None:
        module = Module.objects.create(course=course, order=1, title='Задания')
    name = (request.POST.get('name') or '').strip()
    if name:
        nxt = (module.lessons.aggregate(m=Max('order'))['m'] or 0) + 1
        Lesson.objects.create(module=module, order=nxt, title=name,
                              lesson_type='practice')
        messages.success(request, f'Тема «{name}» добавлена.')
    else:
        messages.error(request, 'Введите название темы.')
    return redirect('teacher_course_edit', slug=slug)


@teacher_required
@require_POST
def teacher_theme_rename(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
    name = (request.POST.get('name') or '').strip()
    if name:
        lesson.title = name
        lesson.save(update_fields=['title'])
    return redirect('teacher_course_edit', slug=slug)


@teacher_required
@require_POST
def teacher_theme_delete(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
    lesson.delete()
    messages.success(request, 'Тема удалена.')
    return redirect('teacher_course_edit', slug=slug)


def _prototype_question_indices(request):
    """Индексы вопросов из POST (поля q{i}_text) в порядке возрастания."""
    return sorted({
        int(m.group(1))
        for k in request.POST
        for m in [re.match(r'q(\d+)_text$', k)] if m
    })


def _parse_prototype_questions(request):
    """Разбор формы прототипа: числовые и single_choice вопросы.

    Поля индексированы по номеру вопроса i: q{i}_text, q{i}_type,
    q{i}_answer (число), q{i}_opt1..4 + q{i}_correct (выбор),
    файл q{i}_image, q{i}_existing_image, q{i}_image_clear.
    Возвращает (questions, errors).
    """
    questions, errors = [], []
    pos = 0
    for i in _prototype_question_indices(request):
        text = (request.POST.get(f'q{i}_text') or '').strip()
        qtype = request.POST.get(f'q{i}_type') or 'number'
        answer = (request.POST.get(f'q{i}_answer') or '').strip()
        opts = [(request.POST.get(f'q{i}_opt{j}') or '').strip() for j in range(1, 5)]
        if not text and not answer and not any(opts):
            continue  # полностью пустая строка
        pos += 1
        if not text:
            errors.append(f'Вопрос {pos}: укажите текст.')
            continue
        common = {
            'text': text,
            'qid': (request.POST.get(f'q{i}_qid') or '').strip(),
            'image': request.FILES.get(f'q{i}_image'),
            'existing_image': (request.POST.get(f'q{i}_existing_image') or '').strip(),
            'clear_image': request.POST.get(f'q{i}_image_clear') == '1',
        }
        if qtype == 'single_choice':
            if len([o for o in opts if o]) < 2:
                errors.append(f'Вопрос {pos}: нужно минимум 2 варианта ответа.')
                continue
            correct = request.POST.get(f'q{i}_correct') or ''
            if not (correct.isdigit() and 1 <= int(correct) <= 4):
                errors.append(f'Вопрос {pos}: отметьте правильный вариант.')
                continue
            correct = int(correct)
            if not opts[correct - 1]:
                errors.append(f'Вопрос {pos}: правильный вариант не заполнен.')
                continue
            questions.append({**common, 'type': 'single_choice',
                              'options': opts, 'correct': correct})
        else:
            if not answer:
                errors.append(f'Вопрос {pos}: укажите числовой ответ.')
                continue
            questions.append({**common, 'type': 'number', 'answer': answer})
    if not questions and not errors:
        errors.append('Добавьте хотя бы один вопрос.')
    return questions, errors


def _prototype_rows(assignment=None, request=None):
    """Строки для формы: из POST (при ошибке) или из существующего прототипа (edit GET)."""
    rows = []
    if request is not None:
        for i in _prototype_question_indices(request):
            rows.append({
                'qid': request.POST.get(f'q{i}_qid', ''),
                'text': request.POST.get(f'q{i}_text', ''),
                'type': request.POST.get(f'q{i}_type', 'number'),
                'answer': request.POST.get(f'q{i}_answer', ''),
                'options': [request.POST.get(f'q{i}_opt{j}', '') for j in range(1, 5)],
                'correct': request.POST.get(f'q{i}_correct', ''),
                'existing_image': request.POST.get(f'q{i}_existing_image', ''),
            })
    elif assignment is not None:
        for q in assignment.questions.order_by('order'):
            opts = list(q.answers.order_by('order'))
            if q.question_type == 'single_choice':
                options = ([o.text for o in opts] + ['', '', '', ''])[:4]
                correct = next((str(k) for k, o in enumerate(opts, 1) if o.is_correct), '')
                rows.append({'qid': q.id, 'text': q.question_text, 'type': 'single_choice',
                             'answer': '', 'options': options, 'correct': correct,
                             'existing_image': q.image.name if q.image else ''})
            else:
                rows.append({'qid': q.id, 'text': q.question_text, 'type': 'number',
                             'answer': (opts[0].text if opts else ''),
                             'options': ['', '', '', ''], 'correct': '',
                             'existing_image': q.image.name if q.image else ''})
    if not rows:
        rows = [{'qid': '', 'text': '', 'type': 'number', 'answer': '',
                 'options': ['', '', '', ''], 'correct': '', 'existing_image': ''}]
    return rows


def _save_prototype_questions(assignment, questions):
    """Сохраняет вопросы прототипа с сопоставлением по id (скрытое поле q{i}_qid).

    Существующий вопрос обновляется по своему id (прогресс/картинка сохраняются,
    даже при удалении/перестановке в середине), новый (без id) — создаётся,
    отсутствующий в форме — удаляется вместе со своим прогрессом (GeneratedProblem
    по db_question_id), чтобы solved_count не превышал число вопросов.
    """
    existing_by_id = {q.id: q for q in assignment.questions.all()}
    kept_ids = set()
    for i, q in enumerate(questions, 1):
        qid = q.get('qid') or ''
        tq = existing_by_id.get(int(qid)) if qid.isdigit() else None
        if tq is None:
            tq = TestQuestion(assignment=assignment)
        tq.question_text = q['text']
        tq.question_type = q['type']
        tq.order = i
        if q.get('image'):
            tq.image = q['image']
        elif q.get('clear_image'):
            tq.image = None
        tq.save()
        kept_ids.add(tq.id)
        tq.answers.all().delete()  # на варианты ничто не ссылается — пересоздаём
        if q['type'] == 'single_choice':
            order = 0
            for j, opt in enumerate(q['options'], 1):  # j — слот 1..4
                if not opt.strip():
                    continue
                order += 1
                AnswerOption.objects.create(
                    question=tq, text=opt, is_correct=(j == q['correct']), order=order)
        else:
            AnswerOption.objects.create(
                question=tq, text=q['answer'], is_correct=True, order=1)
    # Удаляем вопросы, которых больше нет в форме, вместе с их прогрессом
    for qid, tq in existing_by_id.items():
        if qid not in kept_ids:
            GeneratedProblem.objects.filter(
                assignment=assignment, task_data__db_question_id=qid).delete()
            tq.delete()


@teacher_required
def teacher_prototype_new(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        questions, errors = _parse_prototype_questions(request)
        if not title:
            errors.insert(0, 'Введите название прототипа.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'users/teacher_prototype_edit.html', {
                'title': 'Новый прототип', 'course': course, 'lesson': lesson,
                'form_data': request.POST, 'rows': _prototype_rows(request=request),
                'is_edit': False,
            })
        nxt = (lesson.assignments.aggregate(m=Max('order'))['m'] or 0) + 1
        assignment = Assignment.objects.create(
            lesson=lesson, order=nxt, title=title,
            answer_type='decimal_input', required_correct=len(questions),
        )
        _save_prototype_questions(assignment, questions)
        messages.success(request, f'Прототип «{title}» добавлен ({len(questions)} вопр.).')
        return redirect('teacher_course_edit', slug=slug)

    return render(request, 'users/teacher_prototype_edit.html', {
        'title': 'Новый прототип', 'course': course, 'lesson': lesson,
        'form_data': {}, 'rows': _prototype_rows(), 'is_edit': False,
    })


@teacher_required
def teacher_prototype_edit(request, slug, lesson_id, assignment_id):
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
    assignment = get_object_or_404(Assignment, id=assignment_id, lesson=lesson)
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        questions, errors = _parse_prototype_questions(request)
        if not title:
            errors.insert(0, 'Введите название прототипа.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'users/teacher_prototype_edit.html', {
                'title': 'Редактирование прототипа', 'course': course, 'lesson': lesson,
                'form_data': request.POST, 'rows': _prototype_rows(request=request),
                'is_edit': True, 'assignment': assignment,
            })
        assignment.title = title
        assignment.required_correct = len(questions)
        assignment.save(update_fields=['title', 'required_correct'])
        _save_prototype_questions(assignment, questions)
        messages.success(request, 'Прототип обновлён.')
        return redirect('teacher_course_edit', slug=slug)

    return render(request, 'users/teacher_prototype_edit.html', {
        'title': 'Редактирование прототипа', 'course': course, 'lesson': lesson,
        'form_data': {'title': assignment.title},
        'rows': _prototype_rows(assignment=assignment),
        'is_edit': True, 'assignment': assignment,
    })


@teacher_required
@require_POST
def teacher_prototype_delete(request, slug, lesson_id, assignment_id):
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    assignment = get_object_or_404(
        Assignment, id=assignment_id, lesson__module__course=course)
    assignment.delete()
    messages.success(request, 'Прототип удалён.')
    return redirect('teacher_course_edit', slug=slug)


@teacher_required
def teacher_prototype_from_bank(request, slug, lesson_id):
    """Добавить в тему прототипы из общего банка генераторов.

    Создаёт Assignment, ссылающийся на существующий ProblemGenerator (генератор
    общий, не копируется). answer_type/required берём у существующего задания
    с этим генератором (иначе — дефолты)."""
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)

    if request.method == 'POST':
        ids = [int(x) for x in request.POST.getlist('generators') if x.isdigit()]
        nxt = (lesson.assignments.aggregate(m=Max('order'))['m'] or 0)
        created = 0
        for g in ProblemGenerator.objects.filter(id__in=ids):
            nxt += 1
            src = Assignment.objects.filter(problem_generator=g).first()
            Assignment.objects.create(
                lesson=lesson, order=nxt, title=(g.name or 'Прототип')[:200],
                problem_generator=g,
                answer_type=(src.answer_type if src else 'decimal_input'),
                required_correct=(src.required_correct if src else 10),
            )
            created += 1
        if created:
            messages.success(request, f'Добавлено прототипов из банка: {created}.')
        else:
            messages.error(request, 'Ничего не выбрано.')
        return redirect('teacher_course_edit', slug=slug)

    q = (request.GET.get('q') or '').strip()
    gens = ProblemGenerator.objects.all().order_by('name')
    if q:
        gens = gens.filter(name__icontains=q)
    return render(request, 'users/teacher_prototype_bank.html', {
        'title': 'Добавить из банка', 'course': course, 'lesson': lesson,
        'generators': list(gens[:200]), 'q': q,
        'total': ProblemGenerator.objects.count(),
    })


@teacher_required
def teacher_course_enroll(request, slug):
    """Управление составом курса: записать/отписать своих учеников (course-centric)."""
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    profiles = (StudentProfile.objects.filter(teacher=request.user)
                .select_related('user').order_by('display_name'))
    if request.method == 'POST':
        selected = {int(x) for x in request.POST.getlist('students') if x.isdigit()}
        for sp in profiles:
            student = sp.user
            enr = Enrollment.objects.filter(course=course, student=student).first()
            if student.id in selected:
                if enr:
                    if not enr.is_active:
                        enr.is_active = True
                        enr.save(update_fields=['is_active'])
                else:
                    Enrollment.objects.create(
                        course=course, student=student, is_active=True)
            elif enr and enr.is_active:
                enr.is_active = False
                enr.save(update_fields=['is_active'])
        messages.success(request, 'Список учеников курса обновлён.')
        return redirect('teacher_course_edit', slug=slug)

    enrolled_ids = set(
        Enrollment.objects.filter(course=course, is_active=True)
        .values_list('student_id', flat=True)
    )
    students = [{'profile': p, 'enrolled': p.user_id in enrolled_ids} for p in profiles]
    return render(request, 'users/teacher_course_enroll.html', {
        'title': f'Ученики курса: {course.title}',
        'course': course, 'students': students,
    })


def _parse_due(raw):
    """Дата из поля формы. Пустое или мусор — без срока, а не ошибка:
    срок необязателен, и ронять из-за него сохранение домашки незачем."""
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_cutoff(raw, due_raw):
    """Дата отсечки. Раньше срока она бессмысленна — тогда работу нельзя было
    бы сдать вовремя, — поэтому такую молча не принимаем."""
    cutoff = _parse_due(raw)
    due = _parse_due(due_raw)
    if cutoff and due and cutoff < due:
        return None
    return cutoff


def _parse_hw_tasks(request):
    """Собрать (tasks, errors, raw_rows) из POST.
    tasks — список словарей {condition, answer, image, remove_image, requires_review}.
    raw_rows — то же для повторного рендера формы при ошибке."""
    conditions = request.POST.getlist('task_condition')
    answers = request.POST.getlist('task_answer')
    ids = request.POST.getlist('task_id')
    tasks = []
    errors = []
    raw_rows = []
    for i, (cond, ans) in enumerate(zip(conditions, answers)):
        cond = cond.strip()
        ans = ans.strip()
        tid = ids[i] if i < len(ids) else ''
        requires_review = request.POST.get(f'task_review_{i}') == '1'
        raw_rows.append({
            'condition': cond, 'answer': ans, 'image_url': '',
            'requires_review': requires_review, 'task_id': tid,
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
            'requires_review': requires_review, 'id': tid,
        })
    if not tasks and not errors:
        errors.append('Добавьте хотя бы одну задачу.')
    return tasks, errors, raw_rows


@teacher_required
def teacher_hw_lesson_new(request, slug):
    """Добавить новое ДЗ (Lesson + Assignments) в курс с ДЗ."""

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
                'due_value': (request.POST.get('due_date') or ''),
                'cutoff_value': (request.POST.get('cutoff_date') or ''),
                'rows': raw_rows or [{'condition': '', 'answer': '', 'image_url': '', 'requires_review': False}],
                'is_edit': False,
                'lesson_intro': '',
            })

        next_order = (wrapper.lessons.aggregate(m=Max('order'))['m'] or 0) + 1
        lesson = Lesson.objects.create(
            module=wrapper, order=next_order, title=lesson_title,
            content=lesson_intro,
            lesson_type='practice',
            due_date=_parse_due(request.POST.get('due_date')),
            cutoff_date=_parse_cutoff(request.POST.get('cutoff_date'),
                                      request.POST.get('due_date')),
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
        'lesson_intro': '',
    })


@teacher_required
def teacher_hw_lesson_edit(request, slug, lesson_id):
    """Редактирование существующего ДЗ. Сохраняет старые Assignment'ы там, где
    задача с тем же порядковым номером осталась — чтобы не терять прогресс ученика."""

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
                'lesson_intro': lesson.content,
            })

        lesson.title = lesson_title
        lesson.content = lesson_intro
        lesson.due_date = _parse_due(request.POST.get('due_date'))
        lesson.cutoff_date = _parse_cutoff(request.POST.get('cutoff_date'),
                                           request.POST.get('due_date'))
        lesson.save(update_fields=['title', 'content', 'due_date', 'cutoff_date'])

        # Diff по стабильному id: задачу с тем же Assignment.id обновляем,
        # новые (без id) создаём, отсутствующие в форме — удаляем. Так прогресс
        # ученика не «съезжает» при вставке/удалении/перестановке задач.
        existing_by_id = {a.id: a for a in lesson.assignments.all()}
        kept_ids = set()
        for i, t in enumerate(tasks, 1):
            tid = (t.get('id') or '')
            a = existing_by_id.get(int(tid)) if tid.isdigit() else None
            if a is not None:
                a.order = i
                a.title = str(i)
                a.description = t['condition']
                a.correct_answer = t['answer']
                a.requires_review = t['requires_review']
                if t['image']:
                    a.image = t['image']
                elif t['remove_image']:
                    a.image = None
                a.save()
                kept_ids.add(a.id)
            else:
                Assignment.objects.create(
                    lesson=lesson, order=i, title=str(i),
                    description=t['condition'],
                    answer_type='decimal_input', required_correct=1,
                    correct_answer=t['answer'],
                    image=t['image'] or None,
                    requires_review=t['requires_review'],
                )
        # Удаляем задачи, которых больше нет в форме (их id не пришёл).
        for a_id, a in existing_by_id.items():
            if a_id not in kept_ids:
                a.delete()  # каскадно удалит прогресс по удалённой задаче

        messages.success(request, f'ДЗ «{lesson_title}» сохранено.')
        return redirect('teacher_course_progress', slug=course.slug)

    rows = [
        {
            'task_id': a.id,
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
        # Формат для <input type="date"> строго ГГГГ-ММ-ДД, поэтому готовим
        # значение здесь, а не в шаблоне: локализованная дата туда не встанет.
        'due_value': lesson.due_date.isoformat() if lesson.due_date else '',
        'cutoff_value': lesson.cutoff_date.isoformat() if lesson.cutoff_date else '',
        'lesson_intro': lesson.content,
        'rows': rows,
        'is_edit': True,
    })


@teacher_required
def teacher_hw_lesson_report(request, slug, lesson_id):
    """Сводка по одной домашке: кто сдал и какие задачи не даются."""
    course = get_object_or_404(Course, slug=slug, owner=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)

    # Продлить срок лично ученику. Общие даты урока при этом не трогаем —
    # в этом весь смысл, иначе пришлось бы двигать срок остальным.
    if request.method == 'POST' and 'grant_ext' in request.POST:
        student = get_object_or_404(
            User, id=request.POST.get('grant_ext'), role='student',
            student_profile__teacher=request.user)
        due = _parse_due(request.POST.get('ext_due'))
        cut = _parse_cutoff(request.POST.get('ext_cutoff'), request.POST.get('ext_due'))
        if not due and not cut:
            HomeworkExtension.objects.filter(lesson=lesson, student=student).delete()
            messages.success(request, 'Продление снято.')
        else:
            HomeworkExtension.objects.update_or_create(
                lesson=lesson, student=student,
                defaults={'due_date': due, 'cutoff_date': cut,
                          'reason': (request.POST.get('ext_reason') or '').strip()[:200],
                          'granted_by': request.user},
            )
            messages.success(request, 'Срок продлён лично.')
        return redirect('teacher_hw_lesson_report', slug=slug, lesson_id=lesson.id)

    # Только свои ученики и только записанные на этот курс: чужих в сводке
    # быть не должно, даже если они на курсе.
    students = list(User.objects.filter(
        role='student',
        student_profile__teacher=request.user,
        enrollments__course=course, enrollments__is_active=True,
    ).select_related('student_profile').distinct().order_by('student_profile__display_name'))

    by_student, by_task = lesson_report(lesson, students)
    return render(request, 'users/teacher_hw_report.html', {
        'course': course,
        'lesson': lesson,
        'by_student': by_student,
        'by_task': by_task,
        'not_finished': sum(1 for r in by_student if not r['finished']),
        'overdue': sum(1 for r in by_student if r['overdue']),
        'title': f'{lesson.title} — сводка',
    })


@teacher_required
@require_POST
def teacher_hw_lesson_delete(request, slug, lesson_id):
    """Удаление ДЗ вместе со всеми задачами и прогрессом по ним."""

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


@teacher_required
@require_POST
def teacher_hw_lesson_duplicate(request, slug, lesson_id):
    """Копия ДЗ в том же курсе. Прогресс учеников по новой копии — пустой."""

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


@teacher_required
def teacher_hw_lesson_export(request, slug, lesson_id):
    """Скачать ДЗ в виде JSON-файла. Картинки в файл не пакуются."""

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


@teacher_required
def teacher_hw_lesson_import(request, slug):
    """Загрузить JSON и создать новое ДЗ в курсе из его содержимого."""

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

        if not isinstance(data, dict):
            messages.error(request, 'Ожидался JSON-объект с полями lesson_title и tasks.')
            return redirect('teacher_hw_lesson_import', slug=course.slug)

        title = (data.get('lesson_title') or '').strip()
        intro = (data.get('lesson_intro') or '').strip()
        raw_tasks = data.get('tasks')
        if not isinstance(raw_tasks, list):
            raw_tasks = []
        if not title or not raw_tasks:
            messages.error(request, 'В файле не хватает названия ДЗ или задач.')
            return redirect('teacher_hw_lesson_import', slug=course.slug)

        valid_tasks = []
        for i, t in enumerate(raw_tasks, 1):
            if not isinstance(t, dict):
                continue
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


@student_required
@require_POST
def submit_hw_solution(request, assignment_id):
    """Ученик отправляет развёрнутое решение на проверку преподавателю
    (для задач с requires_review=True)."""


    assignment = get_object_or_404(Assignment, id=assignment_id, requires_review=True)
    course = assignment.lesson.module.course
    if not course.is_homework:
        messages.error(request, 'Это не курс с ДЗ.')
        return redirect('student_courses')
    if not Enrollment.objects.filter(
        course=course, student=request.user, is_active=True
    ).exists():
        messages.error(request, 'Вы не записаны на этот курс.')
        return redirect('student_courses')

    # Отсечка. Проверка серверная и это принципиально: спрятать форму мало,
    # отправку легко повторить в обход страницы.
    if not accepts_from(assignment.lesson, request.user):
        _, закрыт = dates_for(assignment.lesson, request.user)
        messages.error(request, 'Приём этой домашки закрыт %s.'
                       % закрыт.strftime('%d.%m.%Y'))
        return redirect('student_course_progress', slug=course.slug)

    text = (request.POST.get('text') or '').strip()
    file = request.FILES.get('file')

    if not text and not file:
        messages.error(request, 'Добавьте текст решения или прикрепите файл.')
        return redirect('student_course_progress', slug=course.slug)

    # Файл проверяем ДО сохранения: иначе мусор уже лежал бы на диске, а
    # чистить его было бы нечем.
    if file:
        try:
            validate_homework_file(file)
        except ValidationError as e:
            messages.error(request, '; '.join(e.messages))
            return redirect('student_course_progress', slug=course.slug)

    # Текущая попытка, если она есть.
    sub = (StudentSubmission.objects
           .filter(student=request.user, assignment=assignment, is_latest=True)
           .first())

    if sub and sub.status == StudentSubmission.STATUS_ACCEPTED:
        messages.warning(request, 'Это решение уже принято.')
        return redirect('student_course_progress', slug=course.slug)

    # Новая работа — это первая отправка или новая попытка после возврата.
    # Правка ещё не прочитанного черновика новой работой не считается.
    была_новая = (sub is None or sub.status == StudentSubmission.STATUS_REJECTED)

    if sub and sub.status == StudentSubmission.STATUS_REJECTED:
        # Работу вернули на доработку — заводим НОВУЮ попытку, а прежнюю
        # оставляем как есть. Раньше здесь текст ученика и комментарий
        # преподавателя затирались безвозвратно.
        sub.is_latest = False
        sub.save(update_fields=['is_latest'])
        sub = StudentSubmission(
            student=request.user, assignment=assignment,
            attempt=sub.attempt + 1, is_latest=True,
        )
    elif sub is None:
        sub = StudentSubmission(
            student=request.user, assignment=assignment,
            attempt=1, is_latest=True,
        )
    # Иначе попытка ещё ждёт проверки — правим её же: преподаватель ничего
    # не писал, терять нечего.

    sub.text = text
    if file:
        sub.file = file
    sub.status = StudentSubmission.STATUS_PENDING
    sub.teacher_comment = ''
    sub.reviewed_at = None
    sub.reviewed_by = None
    sub.save()

    # Сообщаем преподавателю только о НОВОЙ работе, а не о каждой правке
    # черновика: ученик может поправить текст пять раз подряд, и пять
    # одинаковых уведомлений — это шум, из-за которого перестают читать все.
    if была_новая:
        notify_submitted(sub)

    if sub.attempt > 1:
        messages.success(request, 'Отправлено. Это попытка №%d — прежняя сохранена.' % sub.attempt)
    return redirect('student_course_progress', slug=course.slug)


@teacher_required
def teacher_submissions(request):
    """Решения учеников преподавателя — с фильтром по статусу.
    По умолчанию показываются ожидающие проверки."""


    # Только текущие попытки: список проверки — про то, что делать сейчас,
    # а не про историю. Историю видно в карточке задачи.
    base_qs = (StudentSubmission.objects
               .filter(student__student_profile__teacher=request.user, is_latest=True)
               .select_related('student__student_profile',
                               'assignment__lesson__module__course',
                               'grade'))

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

    # Вопросы — ОТДЕЛЬНОЙ полкой, а не колонкой в списке сдач. Причина простая:
    # спрашивают обычно про задачу, которую ещё НЕ сдали, — в списке сдач её
    # нет вовсе, и колонка про неё промолчала бы.
    from .chat import open_questions_for
    return render(request, 'users/teacher_submissions.html', {
        'submissions': submissions_qs,
        'status': status,
        'counts': counts,
        'вопросы': open_questions_for(request.user),
        'title': 'Решения учеников',
    })


@teacher_required
@require_POST
def teacher_review_submission(request, sub_id):
    """Принять/вернуть на доработку развёрнутое решение."""


    sub = get_object_or_404(
        StudentSubmission, id=sub_id,
        student__student_profile__teacher=request.user,
    )
    action = request.POST.get('action')
    comment = (request.POST.get('comment') or '').strip()

    # Балл за номер. Пустое поле — оценки не ставим вовсе: «не оценено» и
    # «оценено в ноль» — разные вещи, и путать их нельзя.
    сырой = (request.POST.get('score') or '').strip().replace(',', '.')
    if сырой:
        потолок = Decimal(str(sub.assignment.points or 1))
        try:
            балл = Decimal(сырой)
        except (InvalidOperation, ValueError):
            балл = None
        if балл is not None:
            # Зажимаем в границы: отрицательный балл и балл выше потолка —
            # это опечатка, а не намерение.
            балл = max(Decimal('0'), min(балл, потолок))
            Grade.objects.update_or_create(
                submission=sub,
                defaults={'value': балл, 'max_value': потолок,
                          'graded_by': request.user},
            )

    if action == 'accept':
        sub.status = StudentSubmission.STATUS_ACCEPTED
        sub.teacher_comment = comment
        sub.reviewed_at = timezone.now()
        sub.reviewed_by = request.user
        sub.save()
        # Принятое решение — это и есть зачёт задачи. Считаем тем же
        # правилом, что и обычный ответ, чтобы не появилась третья копия.
        mark_progress(sub.student, sub.assignment,
                      solved=needed_for(sub.assignment),
                      needed=needed_for(sub.assignment),
                      count_attempt=False)
    elif action == 'reject':
        sub.status = StudentSubmission.STATUS_REJECTED
        sub.teacher_comment = comment
        sub.reviewed_at = timezone.now()
        sub.reviewed_by = request.user
        sub.save()
    if action in ('accept', 'reject'):
        notify_reviewed(sub)
    return redirect('teacher_submissions')


@require_POST
def check_hw_answer(request, assignment_id):
    """AJAX-проверка ответа ученика на задачу из курса с ДЗ.
    Анонимам — только результат, без записи прогресса."""

    assignment = get_object_or_404(Assignment, id=assignment_id)
    course = assignment.lesson.module.course
    if not course.is_homework:
        return JsonResponse({'error': 'not_homework'}, status=400)
    if assignment.requires_review:
        return JsonResponse(
            {'error': 'Эта задача требует развёрнутого решения, а не короткого ответа.'},
            status=400,
        )

    # Курс с ДЗ приватный — проверять ответ может только владелец или записанный ученик
    u = request.user
    if not (u.is_authenticated and (
            course.owner_id == u.id
            or Enrollment.objects.filter(
                course=course, student=u, is_active=True).exists())):
        return JsonResponse({'error': 'forbidden'}, status=403)

    # Та же отсечка, что и у развёрнутых решений: тракта приёма два, а
    # правило одно, и держать его надо в обоих.
    if not accepts_from(assignment.lesson, request.user):
        _, закрыт = dates_for(assignment.lesson, request.user)
        return JsonResponse(
            {'error': 'Приём этой домашки закрыт %s.' % закрыт.strftime('%d.%m.%Y')},
            status=400)

    user_answer = (request.POST.get('answer') or '').strip()
    if not user_answer:
        return JsonResponse({'error': 'Введите ответ'}, status=400)

    expected = (assignment.correct_answer or '').strip()
    is_correct, message = check_answer(user_answer, expected)

    is_student = request.user.is_authenticated and request.user.role == 'student'
    if not is_student:
        return JsonResponse({'correct': is_correct, 'message': message, 'anonymous': True})

    HomeworkAttempt.objects.create(
        student=request.user, assignment=assignment,
        answer=user_answer, is_correct=is_correct,
    )

    # Сколько раз ученик уже верно ответил на эту задачу. Обычно нужен один
    # раз, но required_correct позволяет требовать больше — и теперь это
    # поле здесь работает, а не игнорируется, как было.
    решено = HomeworkAttempt.objects.filter(
        student=request.user, assignment=assignment, is_correct=True,
    ).count()
    нужно = needed_for(assignment)
    mark_progress(request.user, assignment, решено, нужно)

    return JsonResponse({
        'correct': is_correct, 'message': message,
        'solved': min(решено, нужно), 'needed': нужно,
    })


@login_required
def notifications_view(request):
    """Список уведомлений. Открыл — значит прочитал.

    Помечаем прочитанными ИМЕННО показанные записи, а не все подряд: пока
    человек читает страницу, могло прийти новое, и гасить его не показав
    было бы потерей.
    """
    показанные = list(Notification.objects.filter(user=request.user)[:100])
    if request.method == 'POST':
        Notification.objects.filter(
            user=request.user, id__in=[n.id for n in показанные], is_read=False,
        ).update(is_read=True)
        return redirect('notifications')

    непрочитанных = sum(1 for n in показанные if not n.is_read)
    return render(request, 'users/notifications.html', {
        'items': показанные,
        'unread_here': непрочитанных,
        'title': 'Уведомления',
    })


@require_POST
def logout_view(request):
    """Выход из системы"""
    logout(request)
    return redirect('login')

def courses_list(request):
    """Каталог курсов. Авторские курсы (задачники + ДЗ) скрываются от всех, кроме их владельца.
    Ученикам, записанным на конкретный авторский курс, он тоже виден."""
    courses = Course.objects.filter(is_active=True).order_by('order')
    if request.user.is_authenticated and request.user.role == 'teacher':
        # Скрываем чужие приватные курсы; свои (в т.ч. приватные) остаются видны
        courses = courses.exclude(
            Q(is_public=False) & ~Q(owner=request.user)
        )
    elif request.user.is_authenticated and request.user.role == 'student':
        # Ученик видит публичные курсы + приватные, на которые записан
        courses = courses.filter(
            Q(is_public=True)
            | Q(is_public=False,
                enrollments__student=request.user, enrollments__is_active=True)
        ).distinct()
    else:
        courses = courses.filter(is_public=True)
    
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
    # Приватный курс виден только владельцу и записанным ученикам
    if not course.is_public:
        u = request.user
        is_owner = u.is_authenticated and course.owner_id == u.id
        is_enrolled = u.is_authenticated and Enrollment.objects.filter(
            course=course, student=u, is_active=True).exists()
        if not (is_owner or is_enrolled):
            raise Http404()
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
    
    # ── Контекст для блока «Создать вариант» (только для курсов с TaskGroup) ──
    exam_constructor = None
    block_1_5_module = course.modules.filter(title='Задания 1-5').first()
    if block_1_5_module:
        # Темы 1-5: уроки этого модуля, у которых есть TaskGroup
        themes = []
        for l in block_1_5_module.lessons.order_by('order'):
            tg_count = l.task_groups.count()
            if tg_count > 0:
                themes.append({
                    'lesson_id': l.id,
                    'title': l.title,
                    'tg_count': tg_count,
                    'tg_ids': list(l.task_groups.values_list('id', flat=True)),
                })

        # Задания 6-19: уроки из модуля «Первая часть»
        tasks = []
        first_module = course.modules.filter(title='Первая часть').first()
        if first_module:
            for n in range(6, 20):
                l = first_module.lessons.filter(title=f'Задание {n}').first()
                if l is None:
                    continue
                assignments = list(l.assignments.order_by('order'))
                if not assignments:
                    continue
                tasks.append({
                    'n': n,
                    'lesson_id': l.id,
                    'assignments': [
                        {'id': a.id, 'title': a.title or f'Прототип {a.order}',
                         'order': a.order}
                        for a in assignments
                    ],
                })

        if themes or tasks:
            exam_constructor = {'themes': themes, 'tasks': tasks}

    # Прогресс ученика по DB-прототипам курса — для прогресс-баров на карточках
    # ({assignment_id: (correct_attempts, required_correct)}); ключи — int (assignment.id).
    student_progress_map = {}
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'student':
        for aid, correct, req in StudentProgress.objects.filter(
                student=request.user,
                assignment__lesson__module__course=course,
        ).values_list('assignment_id', 'correct_attempts', 'assignment__required_correct'):
            student_progress_map[aid] = (correct, req or 1)

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
        'exam_constructor': exam_constructor,
        'student_progress_map': student_progress_map,
    })

@student_required
@require_POST
def enroll_to_course(request, course_id):
    """Запись на курс"""
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    # На приватный курс ученик сам записаться не может — только преподаватель
    if not course.is_public:
        messages.error(request, 'На этот курс записывает преподаватель.')
        return redirect('student_courses')

    # Проверяем, не записан ли уже; деактивированную запись — реактивируем
    enr = Enrollment.objects.filter(student=request.user, course=course).first()
    if enr and enr.is_active:
        messages.warning(request, f'Вы уже записаны на курс "{course.title}"')
    elif enr:
        enr.is_active = True
        enr.save(update_fields=['is_active'])
        messages.success(request, f'Вы снова записаны на курс "{course.title}"')
    else:
        Enrollment.objects.create(student=request.user, course=course)

    return redirect('student_courses')

@student_required
def student_courses(request):
    """Список курсов, на которые записан ученик"""
    
    enrollments = Enrollment.objects.filter(
        student=request.user,
        is_active=True
    ).select_related('course').order_by('-last_accessed')

    courses = [
        {'enrollment': e, 'percent': course_progress_percent(request.user, e.course)}
        for e in enrollments
    ]

    return render(request, 'users/student_courses.html', {
        'courses': courses,
        'title': 'Мои курсы'
    })

@student_required
@require_POST
def unenroll_from_course(request, enrollment_id):
    """Отписаться от курса"""
    
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

def _can_access_lesson(user, lesson):
    """Доступ к уроку: бесплатный — всем; иначе нужен вход и активная запись
    на курс (либо владелец курса / администратор)."""
    course = lesson.module.course
    if getattr(lesson, 'is_free', False):
        return True
    if not user.is_authenticated:
        return False
    if user.is_superuser or getattr(course, 'owner_id', None) == user.id:
        return True
    return Enrollment.objects.filter(
        course=course, student=user, is_active=True
    ).exists()


def lesson_detail(request, lesson_id):
    """Страница теоретического урока (методичка)."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.module.course

    if not _can_access_lesson(request.user, lesson):
        messages.error(request, 'Этот урок доступен только записанным на курс.')
        return redirect('course_detail', slug=course.slug)

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


@student_required
@require_POST
def mark_lesson_read(request, lesson_id):
    """AJAX: отметить теоретический урок как прочитанный."""
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