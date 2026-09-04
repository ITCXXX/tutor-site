# -*- coding: utf-8 -*-
"""Чат преподавателя с учеником: страницы.

Сообщения ходят по WebSocket (users/consumers.py), здесь только показ ленты и
разрешение доступа. История приходит уже из обработчика, поэтому вид не тянет
сообщения сам — иначе они пришли бы дважды.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render

from .models import Message, Thread, User


def _общая_ветка(teacher, student):
    """Общая ветка пары. Заводится при первом заходе, одна на двоих."""
    thread, _ = Thread.objects.get_or_create(
        teacher=teacher, student=student, lesson=None)
    return thread


@login_required
def chat_home(request):
    """Вход в переписку.

    Ученику открывать нечего, кроме разговора со своим преподавателем, — ведём
    прямо в него. Преподавателю показываем список учеников: у него их много.
    """
    user = request.user

    if user.role == 'student':
        профиль = getattr(user, 'student_profile', None)
        преподаватель = профиль.teacher if профиль else None
        if преподаватель is None:
            # Честно говорим, почему пусто: списывать это на «ошибку» нельзя,
            # человек ничего не сломал — ему просто ещё не назначили преподавателя.
            return render(request, 'users/chat_list.html', {
                'title': 'Переписка',
                'threads': [],
                'нет_преподавателя': True,
            })
        return redirect('chat_thread', thread_id=_общая_ветка(преподаватель, user).id)

    # Преподаватель: список учеников, сверху — где есть непрочитанное.
    ветки = (Thread.objects
             .filter(teacher=user, lesson__isnull=True)
             .select_related('student', 'student__student_profile')
             .annotate(непрочитано=Count(
                 'messages',
                 filter=Q(messages__read_at__isnull=True) & ~Q(messages__author=user)))
             .order_by('-updated_at'))

    # Ученики, с которыми переписки ещё не было: без них список пуст в самом
    # начале, и непонятно, кому вообще можно написать.
    свои = User.objects.filter(student_profile__teacher=user, role='student')
    есть = {t.student_id for t in ветки}
    новые = [s for s in свои if s.id not in есть]

    return render(request, 'users/chat_list.html', {
        'title': 'Переписка',
        'threads': ветки,
        'новые': новые,
        'нет_преподавателя': False,
    })


@login_required
def chat_start(request, student_id):
    """Преподаватель начинает переписку с учеником из списка."""
    if request.user.role != 'teacher':
        raise Http404
    student = User.objects.filter(pk=student_id, role='student').first()
    if student is None:
        raise Http404
    return redirect('chat_thread', thread_id=_общая_ветка(request.user, student).id)


@login_required
def chat_thread(request, thread_id):
    """Одна лента переписки."""
    thread = (Thread.objects
              .select_related('teacher', 'student', 'lesson')
              .filter(pk=thread_id).first())
    if thread is None or not thread.has_access(request.user):
        # Не «нет доступа», а именно 404: чужая переписка не должна выдавать
        # даже факт своего существования.
        raise Http404

    собеседник = thread.other_side(request.user)
    return render(request, 'users/chat.html', {
        'title': f'Переписка · {собеседник.display if собеседник else ""}',
        'thread': thread,
        'собеседник': собеседник,
        'непрочитано': Message.objects.filter(
            thread=thread, read_at__isnull=True).exclude(author=request.user).count(),
    })
