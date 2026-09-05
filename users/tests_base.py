# -*- coding: utf-8 -*-
"""Общая заготовка данных для тестов кабинета.

Одна на все файлы тестов намеренно. Заведи каждый файл свою — и через месяц
«ученик» в одном тесте будет с профилем и преподавателем, а в другом без, и
падение теста перестанет что-либо означать. Ровно так в этом проекте разъехалось
правило зачёта.

Здесь только СБОРКА данных. Никаких проверок и никаких утверждений о том, как
система должна себя вести: это дело самих тестов.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (Assignment, Course, Enrollment, Lesson, Module,
                     StudentProfile, StudentSubmission, TeacherProfile)

User = get_user_model()


def сделать_преподавателя(username='prepod', display='Пётр Учитель'):
    u = User.objects.create_user(username=username, password='x', role='teacher')
    TeacherProfile.objects.create(user=u, display_name=display)
    return u


def сделать_ученика(username='uchenik', display='Аня Ученица', teacher=None):
    """Ученик ВСЕГДА с профилем: без него нет ни имени, ни преподавателя,
    а половина тракта кабинета опирается именно на профиль."""
    u = User.objects.create_user(username=username, password='x', role='student')
    StudentProfile.objects.create(user=u, display_name=display, teacher=teacher)
    return u


def сделать_курс(owner, title='Курс', slug='kurs', tracking='homework'):
    return Course.objects.create(title=title, slug=slug, owner=owner,
                                 is_active=True, tracking_mode=tracking)


def сделать_урок(course, title='Урок', order=1, due=None, cutoff=None):
    module = Module.objects.filter(course=course).first() \
        or Module.objects.create(course=course, title='Модуль', order=1)
    return Lesson.objects.create(module=module, title=title, order=order,
                                 due_date=due, cutoff_date=cutoff)


def сделать_задачу(lesson, title='Задача', points=1, order=1,
                   requires_review=True, required_correct=1):
    return Assignment.objects.create(
        lesson=lesson, title=title, description='—', order=order,
        points=points, requires_review=requires_review,
        required_correct=required_correct)


def записать(student, course):
    return Enrollment.objects.create(student=student, course=course, is_active=True)


def сдать(student, assignment, text='решение', status=None, attempt=1):
    """Одна сдача. attempt нужен доработкам: у сдач уникальна тройка
    «ученик — задача — попытка», и вторая сдача с тем же номером не заведётся."""
    return StudentSubmission.objects.create(
        student=student, assignment=assignment, text=text, is_latest=True,
        attempt=attempt, status=status or StudentSubmission.STATUS_PENDING)


class КабинетTestCase(TestCase):
    """Готовая связка: преподаватель, его ученик, курс с уроком и двумя задачами.

    Ученик записан на курс. Этого хватает почти всем проверкам кабинета, а кому
    не хватает — дописывает своё поверх, не переделывая общее.
    """

    def setUp(self):
        self.преподаватель = сделать_преподавателя()
        self.ученик = сделать_ученика(teacher=self.преподаватель)
        self.курс = сделать_курс(self.преподаватель)
        self.урок = сделать_урок(self.курс)
        self.задача1 = сделать_задачу(self.урок, 'Задача 1', points=10, order=1)
        self.задача2 = сделать_задачу(self.урок, 'Задача 2', points=1, order=2)
        записать(self.ученик, self.курс)
