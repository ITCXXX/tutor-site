# -*- coding: utf-8 -*-
"""Тег «стоит ли на этой задаче пометка вопроса».

Почему тегом, а не переменной в контексте: страницу задачи рисуют несколько
разных видов (обычное задание, банк прототипов, урок целиком), и один из них
сейчас содержит незаконченную чужую работу — вписывать туда свою переменную
значило бы смешать правки. Тег ни от какого вида не зависит и работает всюду,
где в шаблоне есть задание.

Запрос он делает один и только для ученика; преподавателю пометка не нужна —
он видит вопросы отдельным списком на экране проверки работ.
"""

from django import template

from ..chat import question_of

register = template.Library()


@register.simple_tag
def question_open(user, assignment):
    """True, если ученик пометил эту задачу вопросом и на него ещё не ответили."""
    if not (user and user.is_authenticated and getattr(user, 'role', '') == 'student'):
        return False
    if assignment is None:
        return False
    return question_of(user, assignment) is not None
