# -*- coding: utf-8 -*-
"""Уведомления: создание и счётчик.

Точка создания ОДНА — notify(). Разложить создание по вьюхам значит завести
несколько версий текста и правил, которые со временем разойдутся; в этом
проекте так уже случилось с правилом зачёта.
"""
from django.urls import reverse

from .models import Notification


def notify(user, kind, text, url=''):
    """Создать уведомление. Себе не шлём — это шум, а не польза."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return Notification.objects.create(
        user=user, kind=kind, text=text[:300], url=url[:500])


def notify_submitted(submission):
    """Ученик прислал работу — сообщаем преподавателю."""
    profile = getattr(submission.student, 'student_profile', None)
    teacher = getattr(profile, 'teacher', None)
    if not teacher or teacher.id == submission.student_id:
        return None
    попытка = ('' if submission.attempt <= 1
               else ' (попытка №%d)' % submission.attempt)
    # Имя стоит в именительном падеже и отделено тире. Ни род, ни склонение
    # русского имени программно не угадать: «Аня прислал» и «от Аня Петрова»
    # одинаково режут глаз, а строить склонятель ради уведомления незачем.
    return notify(
        teacher, Notification.KIND_SUBMITTED,
        '%s — новая работа: %s%s' % (
            submission.student.display,
            submission.assignment.lesson.title,
            попытка),
        reverse('teacher_submissions'),
    )


def notify_reviewed(submission):
    """Работу проверили — сообщаем ученику. Текст разный: «принято» и
    «вернули» требуют от него разного, и одинаковой строкой это не сказать."""
    course = submission.assignment.lesson.module.course
    if submission.status == submission.STATUS_ACCEPTED:
        text = 'Работа принята: %s' % submission.assignment.lesson.title
    else:
        text = 'Вернули на доработку: %s' % submission.assignment.lesson.title
    if submission.teacher_comment:
        text += ' — %s' % submission.teacher_comment
    return notify(
        submission.student, Notification.KIND_REVIEWED, text,
        reverse('student_course_progress', args=[course.slug]),
    )


def unread_count(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return 0
    return Notification.objects.filter(user=user, is_read=False).count()


def badge(request):
    """Контекст-процессор: счётчик непрочитанных на каждой странице.

    Один COUNT по индексу и только для вошедших — на анонимных страницах
    запроса не будет вовсе.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    return {'unread_notifications': unread_count(user)}
