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
from .models import GroupAttempt, TaskGroup


def task_group_practice(request, group_id):
    """Страница практики по группе ОГЭ №1-5.

    Доступно всем (аноним тоже может решать, но GroupAttempt не сохранится).
    """
    group = get_object_or_404(TaskGroup, pk=group_id)
    sub_questions = list(group.sub_questions.all())
    return render(request, 'users/task_group_practice.html', {
        'group': group,
        'sub_questions': sub_questions,
        'title': f'{group.lesson.title} → {group.title}',
    })


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
        and hasattr(request.user, 'student_profile')
    )
    student_profile = request.user.student_profile if is_student else None

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
        if student_profile is not None and user_answer:
            GroupAttempt.objects.create(
                student=student_profile,
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
    return render(request, 'users/task_group_result.html', {
        'group': group,
        'results': results,
        'correct_count': correct_count,
        'total': total,
        'percent': round(correct_count / total * 100) if total else 0,
        'title': f'Результат: {group.lesson.title} → {group.title}',
    })
