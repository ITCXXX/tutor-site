# -*- coding: utf-8 -*-
"""Декораторы разграничения доступа для личных кабинетов.

Единая точка проверки роли вместо копипаста
`if request.user.role != ...: messages.error(); redirect(...)` в каждой вьюхе.

    @student_required   — только для учеников (и уже вошедших)
    @teacher_required   — только для преподавателей

Оба включают login_required: анонимного отправят на LOGIN_URL (главную),
залогиненного с чужой ролью — на главную с сообщением.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def _role_required(role, error_text):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if getattr(request.user, 'role', None) != role:
                messages.error(request, error_text)
                return redirect('home')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


student_required = _role_required('student', 'Доступ только для учеников')
teacher_required = _role_required('teacher', 'Доступ только для преподавателей')
