# -*- coding: utf-8 -*-
"""Во сколько запросов к базе обходятся страницы курса.

Проверка не на скорость, а на УСТРОЙСТВО: число запросов не должно расти
вместе с курсом. Такое ломается тихо — содержимое страницы остаётся верным, и
обычные тесты ничего не замечают, а у ученика с настоящим курсом страница
встаёт.

Так уже было дважды, и оба раза одинаково — предзагрузка была, но её теряли.

  * На странице курса шаблон спрашивал у каждого урока `assignments.count`,
    `assignments.all` и `task_groups.all`, а вьюха подгружала только уроки:
    30 запросов на курсе из трёх уроков и 256 на курсе из сорока.

  * На странице прогресса стояло `lesson.assignments.all().order_by('order')`.
    Предзагрузка была, но `.order_by()` строит НОВЫЙ запрос и кэш выбрасывает,
    поэтому каждый урок снова шёл в базу: 17 запросов против 62.

Второй случай коварнее первого: в коде предзагрузка написана и глазами видна,
а работать перестаёт от одного вызова следом.
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from users.models import (Assignment, Course, Enrollment, Lesson, Module,
                          User)


class ЦенаСтраницКурса(TestCase):

    ПРЕДЕЛ = 30

    def setUp(self):
        self.ученик = User.objects.create_user('ученик', 'пароль')
        self.client.force_login(self.ученик)

    def _курс(self, номер, модулей, уроков, заданий):
        курс = Course.objects.create(title='Курс %d' % номер,
                                     slug='kurs-%d' % номер, is_active=True)
        for м in range(модулей):
            модуль = Module.objects.create(course=курс, title='Модуль %d' % м,
                                           order=м)
            for у in range(уроков):
                урок = Lesson.objects.create(module=модуль, order=у,
                                             title='Урок %d.%d' % (м, у),
                                             content='Теория')
                Assignment.objects.bulk_create([
                    Assignment(lesson=урок, title='Задание %d' % з,
                               description='Условие', order=з)
                    for з in range(заданий)
                ])
        Enrollment.objects.create(student=self.ученик, course=курс,
                                  is_active=True)
        return курс

    def _запросов(self, адрес):
        with CaptureQueriesContext(connection) as запросы:
            ответ = self.client.get(адрес)
        self.assertEqual(ответ.status_code, 200, адрес)
        return len(запросы)

    def _сравнить(self, имя_маршрута, подпись):
        маленький = self._курс(1, модулей=1, уроков=3, заданий=2)
        большой = self._курс(2, модулей=4, уроков=10, заданий=3)
        мало = self._запросов(reverse(имя_маршрута, args=[маленький.slug]))
        много = self._запросов(reverse(имя_маршрута, args=[большой.slug]))
        self.assertEqual(
            мало, много,
            '%s: %d запросов на курсе из 3 уроков и %d на курсе из 40 — '
            'значит, запрос уходит в цикле' % (подпись, мало, много))
        self.assertLess(мало, self.ПРЕДЕЛ,
                        '%s: запросов и так многовато — %d' % (подпись, мало))

    def test_страница_курса_не_растёт(self):
        self._сравнить('course_detail', 'страница курса')

    def test_страница_прогресса_не_растёт(self):
        self._сравнить('student_course_progress', 'прогресс по курсу')
