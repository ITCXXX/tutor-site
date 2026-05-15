# users/views_exam.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db import IntegrityError
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST
import json
import random
import time
from collections import OrderedDict
from .models import (
    Assignment, GeneratedProblem, ProblemAttempt,
    StudentProgress, Enrollment, TestQuestion, Lesson,
)


def assignment_practice(request, assignment_id):
    """
    Страница для решения задач по прототипу (Assignment).
    Если у задания есть вопросы в БД (без генератора) — DB-режим: все задачи сразу.
    Доступно всем: анонимные пользователи могут решать, но прогресс не сохраняется.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)
    is_student = request.user.is_authenticated and request.user.role == 'student'

    # Авто-запись на курс — только для залогиненных учеников
    if is_student and not Enrollment.objects.filter(
        student=request.user,
        course=assignment.lesson.module.course,
        is_active=True
    ).exists():
        Enrollment.objects.create(
            student=request.user,
            course=assignment.lesson.module.course
        )

    # ── DB-режим: показываем все вопросы сразу ────────────────────────────
    if assignment.questions.exists() and not assignment.problem_generator:
        return _db_assignment_view(request, assignment)

    # ── Режим генератора ──────────────────────────────────────────────────
    is_practice = bool(assignment.problem_generator)

    if is_practice:
        progress = None
        stats_key = f'session_stats_{assignment.id}'
        request.session[stats_key] = {'attempted': 0, 'correct': 0}
        session_stats = {'attempted': 0, 'correct': 0}
    elif is_student:
        progress, _ = StudentProgress.objects.get_or_create(
            student=request.user,
            assignment=assignment
        )
        session_stats = None
    else:
        progress = None
        session_stats = None

    problem = None
    if is_student:
        problem = GeneratedProblem.objects.filter(
            student=request.user,
            assignment=assignment,
            status__in=['new', 'failed']
        ).first()

        if not problem:
            try:
                problem = generate_new_problem_for_student(request.user, assignment)
            except IntegrityError:
                problem = GeneratedProblem.objects.filter(
                    student=request.user,
                    assignment=assignment
                ).order_by('-created_at').first()

    choices = []
    if assignment.answer_type == 'single_choice' and problem and problem.task_data:
        choices = problem.task_data.get('choices', [])

    generators_config = {}
    selected_generators = None
    if assignment.problem_generator:
        generators_config = (assignment.problem_generator.config or {}).get('generators', {})
        if generators_config:
            session_key = f'gen_{assignment.id}'
            selected_generators = request.session.get(session_key, list(generators_config.keys()))

    nav_items, prev_assignment, next_assignment = _build_lesson_nav(request.user, assignment)

    return render(request, 'users/assignment_practice.html', {
        'assignment': assignment,
        'problem': problem,
        'progress': progress,
        'is_practice': is_practice,
        'is_db_mode': False,
        'session_stats': session_stats,
        'choices': choices,
        'generators_config': generators_config,
        'selected_generators': selected_generators or [],
        'lesson_nav_items': nav_items,
        'prev_assignment': prev_assignment,
        'next_assignment': next_assignment,
        'title': f'{"Тренировка" if is_practice else "Задание"}: {assignment.title}'
    })


def _db_assignment_view(request, assignment):
    """Рендер страницы с ВСЕМИ вопросами прототипа из БД."""
    questions = list(
        assignment.questions.prefetch_related('answers').order_by('order')
    )

    is_student = request.user.is_authenticated and request.user.role == 'student'

    # Словарь: question_id → GeneratedProblem (solved). Для анонимов — пусто.
    solved_problems = {}
    if is_student:
        solved_problems = {
            p.task_data.get('db_question_id'): p
            for p in GeneratedProblem.objects.filter(
                student=request.user,
                assignment=assignment,
                status='solved'
            )
            if p.task_data
        }

    questions_data = []
    for q in questions:
        correct_opt = q.answers.filter(is_correct=True).first()
        is_solved = q.id in solved_problems
        questions_data.append({
            'id': q.id,
            'order': q.order,
            'text': q.question_text,
            'image_svg': q.image_svg,
            'solved': is_solved,
            # Для уже решённых показываем правильный ответ (нужен для lock-режима)
            'correct_answer': solved_problems[q.id].correct_answer if is_solved else '',
        })

    solved_count = len(solved_problems)
    total_count = len(questions)
    progress_pct = round(solved_count / total_count * 100) if total_count else 0

    nav_items, prev_assignment, next_assignment = _build_lesson_nav(request.user, assignment)

    return render(request, 'users/assignment_practice.html', {
        'assignment': assignment,
        'is_db_mode': True,
        'is_practice': False,
        'questions_data': questions_data,
        'solved_count': solved_count,
        'total_count': total_count,
        'progress_pct': progress_pct,
        'lesson_nav_items': nav_items,
        'prev_assignment': prev_assignment,
        'next_assignment': next_assignment,
        'title': f'Задание: {assignment.title}',
    })


def _build_lesson_nav(user, assignment):
    """
    Возвращает список прототипов текущего урока с информацией о прогрессе пользователя,
    плюс ссылки на предыдущий/следующий прототипы.
    """
    all_assignments = list(
        assignment.lesson.assignments.prefetch_related('questions').order_by('order')
    )

    # Прогресс по DB-прототипам: id assignment → (solved_count, total_count).
    # Для анонимов (user=None или не student) — везде 0.
    is_student = (user is not None
                  and getattr(user, 'is_authenticated', False)
                  and getattr(user, 'role', None) == 'student')
    db_progress = {}
    for a in all_assignments:
        total = a.questions.count()
        if total == 0 or a.problem_generator_id or not is_student:
            db_progress[a.id] = (0, total)
            continue
        solved_q_ids = GeneratedProblem.objects.filter(
            student=user,
            assignment=a,
            status='solved',
        ).values_list('task_data__db_question_id', flat=True)
        solved = sum(1 for qid in solved_q_ids if qid is not None)
        db_progress[a.id] = (solved, total)

    nav_items = []
    for a in all_assignments:
        solved, total = db_progress.get(a.id, (0, 0))
        nav_items.append({
            'id': a.id,
            'order': a.order,
            'title': a.title,
            'is_current': a.id == assignment.id,
            'is_complete': total > 0 and solved == total,
            'solved': solved,
            'total': total,
        })

    current_idx = next((i for i, a in enumerate(all_assignments) if a.id == assignment.id), 0)
    prev_assignment = all_assignments[current_idx - 1] if current_idx > 0 else None
    next_assignment = all_assignments[current_idx + 1] if current_idx < len(all_assignments) - 1 else None

    return nav_items, prev_assignment, next_assignment


@require_POST
def check_db_question_answer(request, assignment_id, question_id):
    """Проверка ответа на конкретный вопрос из БД (AJAX, DB-режим).
    Анонимы получают только результат проверки, без записи в БД."""
    assignment = get_object_or_404(Assignment, id=assignment_id)
    question = get_object_or_404(TestQuestion, id=question_id, assignment=assignment)

    data = json.loads(request.body)
    user_answer = data.get('answer', '').strip()

    if not user_answer:
        return JsonResponse({'error': 'Ответ не может быть пустым'}, status=400)

    from .answer_check import check_answer

    correct_opt = question.answers.filter(is_correct=True).first()
    correct_answer = correct_opt.text if correct_opt else '0'

    course = assignment.lesson.module.course
    allow_fracs = not (course.slug or '').startswith('oge')
    is_correct, message = check_answer(
        user_answer, correct_answer, allow_fractions=allow_fracs,
    )

    # Анонимам / не-ученикам — только результат, без записи прогресса.
    is_student = request.user.is_authenticated and request.user.role == 'student'
    if not is_student:
        total_count = assignment.questions.count()
        return JsonResponse({
            'correct': is_correct,
            'message': message,
            'correct_answer': correct_answer,
            'was_solved': False,
            'solved_count': 0,
            'total_count': total_count,
            'progress_pct': 0,
            'anonymous': True,
        })

    # Найти или создать GeneratedProblem для этого конкретного вопроса
    problem = GeneratedProblem.objects.filter(
        student=request.user,
        assignment=assignment,
        task_data__db_question_id=question.id
    ).first()

    if not problem:
        problem = GeneratedProblem.objects.create(
            student=request.user,
            assignment=assignment,
            task_data={
                'condition_text': question.question_text,
                'correct_answer': correct_answer,
                'db_question_id': question.id,
            },
            condition_text=f'<p>{question.question_text}</p>',
            correct_answer=correct_answer,
            status='new',
        )

    was_solved = (problem.status == 'solved')
    problem.attempts_count += 1
    if is_correct:
        problem.correct_attempts += 1
        problem.status = 'solved'
    problem.last_attempt_at = timezone.now()
    problem.save()

    ProblemAttempt.objects.create(
        problem=problem,
        student=request.user,
        user_answer=user_answer,
        is_correct=is_correct,
    )

    solved_count = GeneratedProblem.objects.filter(
        student=request.user,
        assignment=assignment,
        status='solved'
    ).count()
    total_count = assignment.questions.count()

    # Синхронизируем StudentProgress, чтобы экран прогресса
    # (teacher_student_workbook / student_course_progress) видел сданные прототипы.
    sp, _ = StudentProgress.objects.get_or_create(
        student=request.user, assignment=assignment,
    )
    sp.correct_attempts = solved_count
    sp.total_attempts = (sp.total_attempts or 0) + 1
    required = assignment.required_correct or total_count or 1
    was_completed = sp.is_completed
    sp.is_completed = total_count > 0 and solved_count >= min(required, total_count)
    if sp.is_completed and not was_completed:
        sp.completed_at = timezone.now()
    sp.save()

    return JsonResponse({
        'correct': is_correct,
        'message': message,
        'correct_answer': correct_answer,
        'was_solved': was_solved,
        'solved_count': solved_count,
        'total_count': total_count,
        'progress_pct': round(solved_count / total_count * 100) if total_count else 0,
    })


@require_POST
def reset_db_assignment(request, assignment_id):
    """Сброс прогресса по прототипу из БД (AJAX). Анонимам — no-op."""
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.user.is_authenticated and request.user.role == 'student':
        GeneratedProblem.objects.filter(
            student=request.user,
            assignment=assignment
        ).delete()
        StudentProgress.objects.filter(
            student=request.user,
            assignment=assignment
        ).delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def check_problem_answer(request, problem_id):
    """Проверка ответа на задачу (AJAX, режим генератора)."""
    from .answer_check import check_answer

    problem = get_object_or_404(GeneratedProblem, id=problem_id, student=request.user)

    data = json.loads(request.body)
    user_answer = data.get('answer', '').strip()

    if not user_answer:
        return JsonResponse({'error': 'Ответ не может быть пустым'}, status=400)

    correct_answer = problem.correct_answer
    answer_type = problem.assignment.answer_type
    message = None

    if answer_type == 'single_choice':
        try:
            is_correct = (int(user_answer) == int(correct_answer))
        except (ValueError, TypeError):
            is_correct = False
    else:
        course = problem.assignment.lesson.module.course
        allow_fracs = not (course.slug or '').startswith('oge')
        is_correct, message = check_answer(
            user_answer, correct_answer, allow_fractions=allow_fracs,
        )

    ProblemAttempt.objects.create(
        problem=problem,
        student=request.user,
        user_answer=user_answer,
        is_correct=is_correct
    )

    problem.attempts_count += 1
    if is_correct:
        problem.correct_attempts += 1
        problem.status = 'solved'
    elif problem.attempts_count >= 3:
        problem.status = 'failed'
    problem.last_attempt_at = timezone.now()
    problem.save()

    is_practice = bool(problem.assignment.problem_generator)
    if is_practice:
        stats_key = f'session_stats_{problem.assignment.id}'
        stats = request.session.get(stats_key, {'attempted': 0, 'correct': 0})
        stats['attempted'] += 1
        if is_correct:
            stats['correct'] += 1
        request.session[stats_key] = stats
        request.session.modified = True
        progress_data = {
            'session_attempted': stats['attempted'],
            'session_correct': stats['correct'],
        }
    else:
        progress, _ = StudentProgress.objects.get_or_create(
            student=request.user,
            assignment=problem.assignment
        )
        progress.update_progress(is_correct)
        progress_data = {
            'progress_correct_attempts': progress.correct_attempts,
            'total_attempts': progress.total_attempts,
            'progress_percentage': progress.get_percentage(),
            'is_completed': progress.is_completed,
        }

    return JsonResponse({
        'correct': is_correct,
        'message': message,
        'correct_answer': problem.correct_answer,
        'attempts_count': problem.attempts_count,
        'problem_correct_attempts': problem.correct_attempts,
        'is_practice': is_practice,
        **progress_data,
    })


@login_required
@require_POST
def generate_new_problem(request, assignment_id):
    """Генерация новой задачи того же типа (AJAX, режим генератора)."""
    assignment = get_object_or_404(Assignment, id=assignment_id)

    generators_config = (assignment.problem_generator.config or {}).get('generators', {}) \
        if assignment.problem_generator else {}
    session_key = f'gen_{assignment_id}'
    selected_generators = request.session.get(session_key, list(generators_config.keys())) \
        if generators_config else None

    problem = generate_new_problem_for_student(request.user, assignment, selected_generators)
    task_data = problem.task_data

    return JsonResponse({
        'success': True,
        'problem_id': problem.id,
        'condition_html': format_problem_for_display(task_data),
        'choices': task_data.get('choices', []),
    })


@login_required
@require_POST
def save_generator_selection(request, assignment_id):
    """Сохраняет выбор генераторов ученика в сессии (AJAX)."""
    data = json.loads(request.body)
    selected = data.get('selected_generators', [])
    if not selected:
        return JsonResponse({'error': 'Нужно выбрать хотя бы один тип задач'}, status=400)
    request.session[f'gen_{assignment_id}'] = selected
    return JsonResponse({'success': True})


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _task_data_from_db_question(assignment):
    questions = list(assignment.questions.prefetch_related('answers').all())
    if not questions:
        return {'condition_text': 'Нет вопросов в базе', 'correct_answer': '0', 'choices': []}

    question = random.choice(questions)

    if assignment.answer_type == 'decimal_input':
        correct_option = question.answers.filter(is_correct=True).first()
        return {
            'condition_text': question.question_text,
            'correct_answer': correct_option.text if correct_option else '0',
            'choices': [],
            'db_question_id': question.id,
        }

    options = list(question.answers.order_by('order'))
    random.shuffle(options)
    choices = []
    correct_idx = 0
    for i, opt in enumerate(options):
        choices.append(opt.text)
        if opt.is_correct:
            correct_idx = i
    return {
        'condition_text': question.question_text,
        'choices': choices,
        'correct_answer': str(correct_idx),
        'db_question_id': question.id,
    }


def generate_new_problem_for_student(student, assignment, selected_generators=None):
    import time
    if assignment.problem_generator:
        task_data = assignment.problem_generator.execute_generator(student, selected_generators)
    elif assignment.questions.exists():
        task_data = _task_data_from_db_question(assignment)
    else:
        task_data = {
            'condition_text': 'Источник задач не настроен',
            'correct_answer': '0',
        }
    condition_text = format_problem_for_display(task_data)
    task_data['_unique_id'] = f"{time.time()}_{random.randint(1000, 9999)}"

    return GeneratedProblem.objects.create(
        student=student,
        assignment=assignment,
        task_data=task_data,
        condition_text=condition_text,
        correct_answer=task_data.get('correct_answer', 1),
        status='new'
    )


def format_problem_for_display(task_data):
    condition_text = task_data.get('condition_text', 'Условие задачи не задано')
    return f'<p>{condition_text}</p>'


# ──────────────────────────────────────────────────────────────────────────────
# Единый экран практики для урока: одна задача за раз, генератор выбирается
# случайно из активных в сайдбаре.
# ──────────────────────────────────────────────────────────────────────────────

def _lesson_session_key(lesson_id):
    return f'lesson_active_gens_{lesson_id}'


_GROUP_PREFIX = 'group: '
_DEFAULT_GROUP = 'Прочее'


def _group_assignments(assignments):
    """Группирует список Assignment по полю description ('group: <название>').
    Возвращает список (group_name, [assignments]) в порядке встречаемости.
    """
    groups = OrderedDict()
    for a in assignments:
        desc = (a.description or '').strip()
        name = desc[len(_GROUP_PREFIX):] if desc.startswith(_GROUP_PREFIX) else _DEFAULT_GROUP
        groups.setdefault(name, []).append(a)
    return list(groups.items())


def _pick_random_assignment(lesson, request):
    """Возвращает (chosen_assignment, all_generators, active_ids)
    или (None, [], []) если в уроке нет генераторов."""
    generators = list(
        lesson.assignments.filter(problem_generator__isnull=False).order_by('order')
    )
    if not generators:
        return None, [], []

    key = _lesson_session_key(lesson.id)
    saved = request.session.get(key)
    if saved is None:
        active_ids = [a.id for a in generators]
    else:
        active_ids = [int(x) for x in saved if int(x) in {a.id for a in generators}]
        if not active_ids:
            active_ids = [a.id for a in generators]

    pool = [a for a in generators if a.id in active_ids]
    chosen = random.choice(pool)
    return chosen, generators, active_ids


def lesson_practice(request, lesson_id):
    """Единая страница практики для урока (генераторный режим)."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.module.course

    chosen, generators, active_ids = _pick_random_assignment(lesson, request)
    if chosen is None:
        # В уроке нет генераторов — отдаём страницу с информацией.
        return render(request, 'users/lesson_practice.html', {
            'lesson': lesson,
            'course': course,
            'generators': [],
            'grouped_generators': [],
            'active_ids': [],
            'no_generators': True,
            'title': lesson.title,
        })

    is_student = request.user.is_authenticated and request.user.role == 'student'

    # Авто-запись на курс — только для учеников
    if is_student and not Enrollment.objects.filter(
        student=request.user, course=course, is_active=True
    ).exists():
        Enrollment.objects.create(student=request.user, course=course)

    # Создаём GeneratedProblem (только для учеников)
    problem = None
    task_data = None
    if is_student:
        problem = generate_new_problem_for_student(request.user, chosen)
        task_data = problem.task_data
    else:
        # Аноним — генерируем «на лету» без сохранения
        if chosen.problem_generator:
            task_data = chosen.problem_generator.execute_generator(None)
        elif chosen.questions.exists():
            task_data = _task_data_from_db_question(chosen)

    return render(request, 'users/lesson_practice.html', {
        'lesson': lesson,
        'course': course,
        'generators': generators,
        'grouped_generators': _group_assignments(generators),
        'active_ids': active_ids,
        'chosen_assignment': chosen,
        'problem': problem,
        'task_data': task_data,
        'no_generators': False,
        'is_oge': (course.slug or '').startswith('oge'),
        'title': lesson.title,
    })


@require_POST
def lesson_set_active_generators(request, lesson_id):
    """AJAX: сохранить список активных генераторов в сессии."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    try:
        data = json.loads(request.body)
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'bad json'}, status=400)

    active = data.get('active') or []
    valid_ids = set(
        lesson.assignments.filter(problem_generator__isnull=False)
        .values_list('id', flat=True)
    )
    cleaned = [int(x) for x in active if isinstance(x, (int, str))
               and str(x).isdigit() and int(x) in valid_ids]
    request.session[_lesson_session_key(lesson.id)] = cleaned
    request.session.modified = True
    return JsonResponse({'ok': True, 'active': cleaned})


def lesson_next_problem(request, lesson_id):
    """AJAX: вернуть данные новой задачи (случайный генератор из активных)."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    chosen, generators, active_ids = _pick_random_assignment(lesson, request)
    if chosen is None:
        return JsonResponse({'error': 'no_generators'}, status=400)

    is_student = request.user.is_authenticated and request.user.role == 'student'
    if is_student:
        problem = generate_new_problem_for_student(request.user, chosen)
        task_data = problem.task_data
        problem_id = problem.id
    else:
        if chosen.problem_generator:
            task_data = chosen.problem_generator.execute_generator(None)
        elif chosen.questions.exists():
            task_data = _task_data_from_db_question(chosen)
        else:
            task_data = {'condition_text': '—', 'correct_answer': '0'}
        problem_id = None

    return JsonResponse({
        'condition_text': task_data.get('condition_text', ''),
        'condition_html': format_problem_for_display(task_data),
        'correct_answer': task_data.get('correct_answer', ''),
        'choices': task_data.get('choices', []),
        'assignment_id': chosen.id,
        'assignment_title': chosen.title,
        'answer_type': chosen.answer_type,
        'problem_id': problem_id,
    })
