# -*- coding: utf-8 -*-
"""Views для блочных задач ОГЭ №1-5 (модель TaskGroup + GroupSubQuestion).

UX:
- task_group_practice — страница с общим контекстом и всеми подзадачами в столбик.
- task_group_submit — POST-обработчик: проверяет ответы, сохраняет GroupAttempt
  для авторизованного ученика, рендерит страницу с результатом.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .answer_check import check_answer
from .models import GroupAttempt, Lesson, TaskGroup


def _variant_nav(group):
    """Навигация по группе ОГЭ №1-5.

    Варианты одной задачи — это TaskGroup'ы с общим fipi_ctx_id в одном уроке.
    Возвращает соседние варианты (prev_group/next_group), а на краях —
    соседние ЗАДАНИЯ урока (prev_task/next_task, первый вариант соседней темы).
    """
    siblings = list(
        TaskGroup.objects.filter(
            lesson=group.lesson, fipi_ctx_id=group.fipi_ctx_id
        ).order_by('order', 'id')
    )
    ids = [g.id for g in siblings]
    idx = ids.index(group.id) if group.id in ids else 0

    # Соседние задания урока (другие fipi_ctx_id), в порядке их появления.
    lesson_groups = list(
        TaskGroup.objects.filter(lesson=group.lesson).order_by('order', 'id')
    )
    topics, seen = [], set()
    for g in lesson_groups:
        if g.fipi_ctx_id not in seen:
            seen.add(g.fipi_ctx_id)
            topics.append(g.fipi_ctx_id)

    prev_task = next_task = None
    if group.fipi_ctx_id in topics:
        tpos = topics.index(group.fipi_ctx_id)
        if tpos > 0:
            prev_task = next(
                (g for g in lesson_groups if g.fipi_ctx_id == topics[tpos - 1]), None)
        if tpos < len(topics) - 1:
            next_task = next(
                (g for g in lesson_groups if g.fipi_ctx_id == topics[tpos + 1]), None)

    # На краях урока — соседний УРОК модуля (его первое задание).
    mlessons = list(
        Lesson.objects.filter(module=group.lesson.module).order_by('order', 'id')
    )
    lids = [l.id for l in mlessons]
    lpos = lids.index(group.lesson.id) if group.lesson.id in lids else -1

    def _lesson_jump(direction):
        i = lpos + direction
        while lpos >= 0 and 0 <= i < len(mlessons):
            fg = (TaskGroup.objects.filter(lesson=mlessons[i])
                  .order_by('order', 'id').first())
            if fg:
                return mlessons[i], fg
            i += direction
        return None, None

    prev_lesson, prev_lesson_group = _lesson_jump(-1)
    next_lesson, next_lesson_group = _lesson_jump(1)

    return {
        'variant_total': len(siblings),
        'variant_num': idx + 1,
        'prev_group': siblings[idx - 1] if idx > 0 else None,
        'next_group': siblings[idx + 1] if idx < len(siblings) - 1 else None,
        'prev_task': prev_task,
        'next_task': next_task,
        'prev_lesson': prev_lesson,
        'prev_lesson_group': prev_lesson_group,
        'next_lesson': next_lesson,
        'next_lesson_group': next_lesson_group,
    }


def task_group_practice(request, group_id):
    """Страница практики по группе ОГЭ №1-5.

    Доступно всем (аноним тоже может решать, но GroupAttempt не сохранится).
    """
    group = get_object_or_404(TaskGroup, pk=group_id)
    sub_questions = list(group.sub_questions.all())
    ctx = {
        'group': group,
        'sub_questions': sub_questions,
        'title': f'{group.lesson.title} → {group.title}',
    }
    ctx.update(_variant_nav(group))
    return render(request, 'users/task_group_practice.html', ctx)


def task_group_submit(request, group_id):
    """POST: проверяет все ответы группы и рендерит результат."""
    group = get_object_or_404(TaskGroup, pk=group_id)
    if request.method != 'POST':
        return redirect('task_group_practice', group_id=group.id)

    sub_questions = list(group.sub_questions.all())
    results = []
    correct_count = 0

    # Сохраняем GroupAttempt только для залогиненных учеников.
    is_student = (
        request.user.is_authenticated
        and getattr(request.user, 'role', None) == 'student'
    )

    # Курс ОГЭ → запрещаем дробный ввод (как в остальных местах).
    course = group.lesson.module.course
    allow_fracs = not (course.slug or '').startswith('oge')

    for sq in sub_questions:
        user_answer = (request.POST.get(f'answer_{sq.id}') or '').strip()
        if user_answer:
            is_correct, message = check_answer(
                user_answer, sq.correct_answer, allow_fractions=allow_fracs,
            )
        else:
            is_correct, message = False, None
        if is_correct:
            correct_count += 1
        if is_student and user_answer:
            GroupAttempt.objects.create(
                student=request.user,
                sub_question=sq,
                answer=user_answer,
                is_correct=is_correct,
            )
        results.append({
            'sq': sq,
            'user_answer': user_answer,
            'is_correct': is_correct,
            'message': message,
        })

    total = len(results)
    ctx = {
        'group': group,
        'results': results,
        'correct_count': correct_count,
        'total': total,
        'percent': round(correct_count / total * 100) if total else 0,
        'title': f'Результат: {group.lesson.title} → {group.title}',
    }
    ctx.update(_variant_nav(group))
    return render(request, 'users/task_group_result.html', ctx)
