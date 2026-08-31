# users/views_exam.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.utils import timezone

from .progress import mark_progress, needed_for
from django.db import IntegrityError
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST
import json
import random
import time
import string
from collections import OrderedDict
from .models import (
    Assignment, GeneratedProblem, ProblemAttempt,
    StudentProgress, Enrollment, TestQuestion, Lesson,
    ExamVariant, ExamVariantSlot, ExamVariantAnswer, TaskGroup,
)
from .answer_check import check_answer


def _assignment_access_ok(request, course):
    """Приватный курс: доступ к задачам только владельцу и записанным ученикам."""
    u = request.user
    return u.is_authenticated and (
        course.owner_id == u.id
        or Enrollment.objects.filter(
            course=course, student=u, is_active=True).exists()
    )


def _require_course_access(request, course):
    """404 для приватного курса, если пользователь не владелец и не записан."""
    if not course.is_public and not _assignment_access_ok(request, course):
        raise Http404()


def assignment_practice(request, assignment_id):
    """
    Страница для решения задач по прототипу (Assignment).
    Если у задания есть вопросы в БД (без генератора) — DB-режим: все задачи сразу.
    Публичные курсы — доступны всем (аноним решает без сохранения прогресса);
    приватные — только владельцу и записанным ученикам.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)
    course = assignment.lesson.module.course
    _require_course_access(request, course)
    is_student = request.user.is_authenticated and request.user.role == 'student'

    # Авто-запись на курс — только для залогиненных учеников.
    # get_or_create + реактивация: если запись существует, но неактивна
    # (препод снял ученика), обычный create() упал бы на unique_together.
    if is_student:
        enr, created = Enrollment.objects.get_or_create(
            student=request.user,
            course=assignment.lesson.module.course,
            defaults={'is_active': True},
        )
        if not created and not enr.is_active:
            enr.is_active = True
            enr.save(update_fields=['is_active'])

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
    elif is_practice:
        # Аноним/не-ученик: генерируем задачу «на лету», без сохранения в БД,
        # иначе карточка условия была бы пустой.
        try:
            _td = assignment.problem_generator.execute_generator(None)
            problem = GeneratedProblem(
                assignment=assignment,
                task_data=_td,
                condition_text=format_problem_for_display(_td),
                correct_answer=str(_td.get('correct_answer', '')),
                status='new',
            )
        except Exception:
            problem = None

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
        is_solved = q.id in solved_problems
        opts = list(q.answers.order_by('order'))
        questions_data.append({
            'id': q.id,
            'order': q.order,
            'text': q.question_text,
            'type': q.question_type,
            'image_svg': q.image_svg,
            'image_url': q.image.url if q.image else '',
            'choices': [o.text for o in opts] if q.question_type == 'single_choice' else [],
            'solved': is_solved,
            # Для уже решённых показываем правильный ответ (нужен для lock-режима)
            'correct_answer': solved_problems[q.id].correct_answer if is_solved else '',
        })

    # Считаем решёнными только среди ТЕКУЩИХ вопросов (осиротевший прогресс
    # удалённых вопросов не должен завышать счётчик >100%).
    solved_count = sum(1 for q in questions if q.id in solved_problems)
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
        # Если title — короткая цифровая строка (как в задачнике Поповой),
        # показываем её вместо локального order'a в параграфе:
        # тогда у Поповой получается сквозная нумерация через весь задачник.
        title_clean = (a.title or '').strip()
        display_num = title_clean if title_clean.isdigit() and len(title_clean) <= 5 else str(a.order)
        nav_items.append({
            'id': a.id,
            'order': a.order,
            'title': a.title,
            'display_num': display_num,
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
    _require_course_access(request, assignment.lesson.module.course)
    question = get_object_or_404(TestQuestion, id=question_id, assignment=assignment)

    data = json.loads(request.body)
    user_answer = data.get('answer', '').strip()

    if not user_answer:
        return JsonResponse({'error': 'Ответ не может быть пустым'}, status=400)


    if question.question_type == 'single_choice':
        # Правильный ответ — 1-based позиция верного варианта среди options (по order):
        # ровно тот индекс, что шлёт фронт при клике по варианту.
        opts = list(question.answers.order_by('order'))
        correct_idx = next((i for i, o in enumerate(opts, 1) if o.is_correct), 0)
        correct_answer = str(correct_idx)
        is_correct = (user_answer.strip() == correct_answer)
        message = ''
    else:
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
    solved_count = min(solved_count, total_count)  # осиротевший прогресс не завышает счётчик

    # Синхронизируем StudentProgress, чтобы экран прогресса
    # (teacher_student_workbook / student_course_progress) видел сданные прототипы.
    # Правило зачёта — общее с курсами с ДЗ (users/progress.py): держать его в
    # двух местах уже приводило к расхождению.
    if total_count > 0:
        mark_progress(request.user, assignment, solved_count,
                      needed_for(assignment, pool_size=total_count))

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
    _require_course_access(request, assignment.lesson.module.course)
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

    problem = get_object_or_404(GeneratedProblem, id=problem_id, student=request.user)
    _require_course_access(request, problem.assignment.lesson.module.course)

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
    _require_course_access(request, assignment.lesson.module.course)

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
    _require_course_access(request, course)

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

    # Авто-запись на курс — только для учеников (get_or_create + реактивация,
    # иначе create() при существующей неактивной записи упадёт на unique_together).
    if is_student:
        enr, created = Enrollment.objects.get_or_create(
            student=request.user, course=course, defaults={'is_active': True},
        )
        if not created and not enr.is_active:
            enr.is_active = True
            enr.save(update_fields=['is_active'])

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

    # Соседние уроки в этом же модуле — для навигации «предыдущее / следующее задание».
    siblings = list(lesson.module.lessons.order_by('order', 'id'))
    try:
        idx = siblings.index(lesson)
    except ValueError:
        idx = 0
    prev_lesson = siblings[idx - 1] if idx > 0 else None
    next_lesson = siblings[idx + 1] if idx + 1 < len(siblings) else None

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
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
    })


@require_POST
def lesson_set_active_generators(request, lesson_id):
    """AJAX: сохранить список активных генераторов в сессии."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    _require_course_access(request, lesson.module.course)
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


# ──────────────────────────────────────────────────────────────────────────────
# Конструктор вариантов ОГЭ
# ──────────────────────────────────────────────────────────────────────────────

import random as _rnd
import secrets as _secrets


def _gen_variant_code(length=6):
    """Короткий читаемый код варианта."""
    alphabet = ''.join(
        c for c in (string.ascii_lowercase + string.digits) if c not in '01lo'
    )
    return ''.join(_secrets.choice(alphabet) for _ in range(length))


def _generate_slot_from_assignment(a, owner):
    """Возвращает dict с полями для ExamVariantSlot, сгенерированный из одного
    Assignment'а (через problem_generator или БД-вопросы)."""
    text = ''
    correct = ''
    choices = []

    if a.problem_generator:
        try:
            data = a.problem_generator.execute_generator(student=owner)
        except Exception:
            data = {}
        text = data.get('condition_text') or '(условие недоступно)'
        correct = str(data.get('correct_answer', ''))
        choices = list(data.get('choices') or [])
    elif a.questions.exists():
        q = _rnd.choice(list(a.questions.prefetch_related('answers').all()))
        text = q.question_text or ''
        if a.answer_type == 'decimal_input':
            opt = q.answers.filter(is_correct=True).first()
            correct = (opt.text if opt else '0')
        else:
            opts = list(q.answers.order_by('order'))
            correct_idx = next((i for i, o in enumerate(opts) if o.is_correct), 0)
            # Сохраняем 1-based, чтобы в шаблоне ученик вводил 1..N.
            correct = str(correct_idx + 1)
            choices = [o.text for o in opts]
    else:
        text = '(нет источника задач)'

    # Нормализация для single_choice: переводим 0-based индекс в 1-based,
    # если генератор отдал индекс < len(choices). Если генератор уже 1-based
    # или вернул нестандартное — не трогаем.
    if a.answer_type == 'single_choice' and choices and correct:
        try:
            idx = int(correct)
            if 0 <= idx < len(choices):
                correct = str(idx + 1)
        except ValueError:
            pass

    return {
        'question_html': text,
        'correct_answer': correct,
        'choices': choices,
        'answer_type': a.answer_type or '',
        'assignment': a,
    }


def _build_variant(owner, kind, spec=None):
    """Создаёт ExamVariant + слоты.

    spec — None: «обычная» генерация (full/short).
    spec — dict:
        {
            'block_1_5': {'enabled': True, 'tg_pool_ids': [...]},  # tg_pool пуст → все
            'tasks': {
                '6': {'count': 1, 'assignment_ids': [...]},   # пусто → все прототипы
                '7': {'count': 2, 'assignment_ids': [...]},
                ...
            }
        }
    """

    for _ in range(20):
        code = _gen_variant_code()
        if not ExamVariant.objects.filter(code=code).exists():
            break

    # Готовим параметры из spec / kind.
    if spec is None:
        block_enabled = True
        block_tg_ids = None
        tasks_spec = {}
        if kind == ExamVariant.KIND_FULL:
            tasks_spec = {n: {'count': 1, 'assignment_ids': None} for n in range(6, 20)}
        # Для KIND_SHORT tasks_spec пустой.
    else:
        b = spec.get('block_1_5') or {}
        block_enabled = bool(b.get('enabled', True))
        block_tg_ids = b.get('tg_pool_ids') or None
        tasks_spec = {}
        for n_str, item in (spec.get('tasks') or {}).items():
            try:
                n = int(n_str)
            except (TypeError, ValueError):
                continue
            count = int(item.get('count') or 0)
            if count <= 0:
                continue
            aids = item.get('assignment_ids') or None
            tasks_spec[n] = {'count': count, 'assignment_ids': aids}

    # ── Блок 1-5 ─────────────────────────────────────────────────────────
    block_1_5_context = ''
    block_1_5_source = None
    if block_enabled:
        tg_qs = TaskGroup.objects.filter(lesson__module__title='Задания 1-5')
        if block_tg_ids:
            tg_qs = tg_qs.filter(id__in=block_tg_ids)
        tg_pool = list(tg_qs)
        if tg_pool:
            tg = _rnd.choice(tg_pool)
            block_1_5_context = tg.context_html
            block_1_5_source = tg

    variant = ExamVariant.objects.create(
        code=code,
        owner=owner if (owner and owner.is_authenticated) else None,
        kind=kind,
        block_1_5_context_html=block_1_5_context,
        block_1_5_source=block_1_5_source,
    )

    next_slot = 1
    if block_1_5_source:
        # Для каждого типа задачи (T1..T5) берём ОДНУ случайную подзадачу.
        # У одной TaskGroup может быть несколько подзадач одного типа — это варианты.
        sqs_by_type = {}
        for sq in block_1_5_source.sub_questions.all():
            sqs_by_type.setdefault(sq.t_type, []).append(sq)
        for t in ('T1', 'T2', 'T3', 'T4', 'T5'):
            pool = sqs_by_type.get(t)
            if not pool:
                continue
            sq = _rnd.choice(pool)
            ExamVariantSlot.objects.create(
                variant=variant,
                slot=next_slot,
                task_number=next_slot,    # 1..5 — это номер задания ОГЭ
                question_html=sq.question_html,
                correct_answer=sq.correct_answer,
                answer_type='decimal_input',
                sub_question=sq,
            )
            next_slot += 1

    # ── Задания 6-19 (по spec) ───────────────────────────────────────────
    for n in sorted(tasks_spec.keys()):
        cfg = tasks_spec[n]
        lesson = Lesson.objects.filter(
            module__course__slug='oge-maths',
            title=f'Задание {n}',
        ).first()
        if lesson is None:
            continue
        aqs = lesson.assignments.all()
        if cfg['assignment_ids']:
            aqs = aqs.filter(id__in=cfg['assignment_ids'])
        assignments = list(aqs)
        if not assignments:
            continue
        # count повторов; каждый раз случайный Assignment (с возвратом).
        for _i in range(cfg['count']):
            a = _rnd.choice(assignments)
            data = _generate_slot_from_assignment(a, owner)
            ExamVariantSlot.objects.create(
                variant=variant,
                slot=next_slot,
                task_number=n,
                **data,
            )
            next_slot += 1

    return variant


@login_required
@require_POST
def exam_constructor_build(request):
    """POST из формы конструктора на странице курса. Принимает spec и создаёт
    вариант, редиректит на /exam/variant/<code>/.

    Body — обычная form-data (НЕ JSON), потому что форма у нас простая HTML.
    Поля:
        block_1_5_enabled      'on' (чекбокс) — включать ли блок 1-5
        block_1_5_tg[]         id выбранных тем (TaskGroup)
        task_<N>_count         число задач для задания N (6..19)
        task_<N>_assignments[] id выбранных прототипов задания N
    """
    POST = request.POST

    spec = {
        'block_1_5': {
            'enabled': bool(POST.get('block_1_5_enabled')),
            'tg_pool_ids': [int(x) for x in POST.getlist('block_1_5_tg') if x.isdigit()],
        },
        'tasks': {},
    }
    for n in range(6, 20):
        cnt_raw = (POST.get(f'task_{n}_count') or '').strip()
        try:
            cnt = max(0, int(cnt_raw))
        except ValueError:
            cnt = 0
        if cnt == 0:
            continue
        aids = [int(x) for x in POST.getlist(f'task_{n}_assignments') if x.isdigit()]
        spec['tasks'][str(n)] = {'count': cnt, 'assignment_ids': aids}

    variant = _build_variant(
        owner=request.user, kind=ExamVariant.KIND_FULL, spec=spec,
    )
    return redirect('exam_variant_detail', code=variant.code)


@login_required
def exam_variant_detail(request, code):
    """Страница прохождения варианта.

    Ответы храним пер-ученик (ExamVariantAnswer), поэтому один вариант по коду
    независимо решают разные ученики. На слот вешаем ответ текущего пользователя
    как атрибуты инстанса — шаблон читает slot.user_answer / slot.is_correct.
    """
    variant = get_object_or_404(ExamVariant, code=code)
    slots = list(variant.slots.order_by('slot'))
    answers = {
        a.slot_id: a
        for a in ExamVariantAnswer.objects.filter(
            slot__variant=variant, user=request.user,
        )
    }
    for sl in slots:
        a = answers.get(sl.id)
        sl.user_answer = a.user_answer if a else ''
        sl.is_correct = a.is_correct if a else None
        sl.answered_at = a.answered_at if a else None
    return render(request, 'users/exam_variant.html', {
        'variant': variant,
        'slots': slots,
        'title': f'Вариант {variant.code}',
    })


@login_required
@require_POST
def exam_variant_check(request, code, slot):
    """AJAX: проверка ответа в конкретном слоте варианта.

    Body: {"answer": "..."}.
    Ответ: {"correct": bool, "correct_answer": "..."}.
    Сохраняется пер-ученик (ExamVariantAnswer) — без затирания чужих ответов.
    """

    variant = get_object_or_404(ExamVariant, code=code)
    sl = get_object_or_404(ExamVariantSlot, variant=variant, slot=int(slot))

    try:
        data = json.loads(request.body or '{}')
        ua = (data.get('answer') or '').strip()
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'bad json'}, status=400)
    if not ua:
        return JsonResponse({'error': 'empty'}, status=400)

    is_correct, _ = check_answer(ua, sl.correct_answer)

    ExamVariantAnswer.objects.update_or_create(
        slot=sl, user=request.user,
        defaults={'user_answer': ua, 'is_correct': is_correct},
    )

    return JsonResponse({
        'correct': bool(is_correct),
        'correct_answer': sl.correct_answer,
    })


# ──────────────────────────────────────────────────────────────────────────────


def lesson_next_problem(request, lesson_id):
    """AJAX: вернуть данные новой задачи (случайный генератор из активных)."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    _require_course_access(request, lesson.module.course)
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
        'multi_answer': bool(task_data.get('multi_answer')),
    })
