# -*- coding: utf-8 -*-
"""Условия доступа: окно записи и «откроется после».

Цена ошибки здесь двусторонняя, и обе стороны неприятны. Пустишь лишнего —
ученик видит материал, который ему ещё не открыли, а на курсе с оплатой по
месяцам это прямой убыток. Не пустишь своего — человек упирается в «нет
доступа» и пишет посреди вечера, что сайт сломался.

Поэтому почти каждая проверка ниже сравнивает не «пустило/не пустило», а
ПРИЧИНУ: закрытый урок обязан объяснять себя.
"""

import datetime

from django.utils import timezone

from .access import lesson_lock_reason, lesson_open, lesson_done
from .homework import homework_for
from .models import Enrollment, LessonProgress, ManualMark, StudentProgress
from .tests_base import (КабинетTestCase, записать, сделать_задачу,
                         сделать_курс, сделать_преподавателя, сделать_ученика,
                         сделать_урок)


def дата(сдвиг):
    return timezone.localdate() + datetime.timedelta(days=сдвиг)


def пройти(ученик, задача):
    """Отметить задачу пройденной так, как это делает обычный курс."""
    StudentProgress.objects.update_or_create(
        student=ученик, assignment=задача,
        defaults={'is_completed': True, 'correct_attempts': 1,
                  'total_attempts': 1})


class ОкноЗаписиTests(КабинетTestCase):
    """Доступ как окно, а не как галочка."""

    def запись(self, **поля):
        Enrollment.objects.filter(student=self.ученик, course=self.курс).update(**поля)

    def test_внутри_окна_открыто(self):
        self.запись(starts_at=дата(-5), ends_at=дата(5))
        self.assertIsNone(lesson_lock_reason(self.урок, self.ученик))

    def test_до_начала_закрыто_и_названа_дата(self):
        """Записался в июне на сентябрьский курс: числится, но открыть не может."""
        self.запись(starts_at=дата(10))
        причина = lesson_lock_reason(self.урок, self.ученик)
        self.assertIsNotNone(причина)
        self.assertIn('откроется', причина.lower())
        self.assertIn(дата(10).strftime('%d.%m.%Y'), причина)

    def test_после_конца_закрыто(self):
        """Оплачено до конца мая: первого июня доступ закрывается сам."""
        self.запись(ends_at=дата(-1))
        причина = lesson_lock_reason(self.урок, self.ученик)
        self.assertIsNotNone(причина)
        self.assertIn('закончился', причина.lower())

    def test_последний_день_ещё_открыт(self):
        """Граница включительно: «доступ по 5-е» значит, что 5-го ещё можно."""
        self.запись(ends_at=дата(0))
        self.assertTrue(lesson_open(self.урок, self.ученик))

    def test_приостановленная_запись_закрыта(self):
        self.запись(is_active=False)
        причина = lesson_lock_reason(self.урок, self.ученик)
        self.assertIn('приостановлена', причина.lower())

    def test_без_записи_закрыто(self):
        чужой = сделать_ученика(username='chuzhoy', display='Чужой',
                                teacher=self.преподаватель)
        причина = lesson_lock_reason(self.урок, чужой)
        self.assertIn('не записаны', причина.lower())


class ОткроетсяСДатыTests(КабинетTestCase):

    def test_до_даты_закрыто(self):
        self.урок.available_from = дата(3)
        self.урок.save(update_fields=['available_from'])
        причина = lesson_lock_reason(self.урок, self.ученик)
        self.assertIn(дата(3).strftime('%d.%m.%Y'), причина)

    def test_в_сам_день_уже_открыто(self):
        self.урок.available_from = дата(0)
        self.урок.save(update_fields=['available_from'])
        self.assertTrue(lesson_open(self.урок, self.ученик))

    def test_бесплатный_урок_не_слушает_дату(self):
        """Витрина. Иначе на курс нельзя было бы заглянуть до записи."""
        self.урок.available_from = дата(30)
        self.урок.is_free = True
        self.урок.save(update_fields=['available_from', 'is_free'])
        self.assertTrue(lesson_open(self.урок, self.ученик))


class ПоследовательныйКурсTests(КабинетTestCase):
    """Следующий урок открывается, когда пройден предыдущий."""

    def setUp(self):
        super().setUp()
        self.курс.sequential = True
        self.курс.save(update_fields=['sequential'])
        self.урок2 = сделать_урок(self.курс, 'Урок 2', order=2)
        self.задача3 = сделать_задачу(self.урок2, 'Задача 3', order=1)

    def test_первый_урок_открыт_сразу(self):
        self.assertTrue(lesson_open(self.урок, self.ученик))

    def test_второй_закрыт_пока_первый_не_сдан(self):
        причина = lesson_lock_reason(self.урок2, self.ученик)
        self.assertIsNotNone(причина)
        self.assertIn(self.урок.title, причина)

    def test_половина_первого_урока_не_открывает_второй(self):
        """Сдал одну задачу из двух — рано. Урок пройден, когда пройдены ВСЕ."""
        пройти(self.ученик, self.задача1)
        self.assertFalse(lesson_open(self.урок2, self.ученик))

    def test_после_всех_задач_второй_открывается(self):
        пройти(self.ученик, self.задача1)
        пройти(self.ученик, self.задача2)
        self.assertTrue(lesson_open(self.урок2, self.ученик))

    def test_обычный_курс_ничего_не_запирает(self):
        self.курс.sequential = False
        self.курс.save(update_fields=['sequential'])
        self.assertTrue(lesson_open(self.урок2, self.ученик))


class ЯвнаяСвязкаTests(КабинетTestCase):
    """unlock_after — точечная связка, для ветвлений вроде «повторение перед КР»."""

    def test_работает_и_на_непоследовательном_курсе(self):
        урок2 = сделать_урок(self.курс, 'Контрольная', order=5)
        сделать_задачу(урок2, 'КР', order=1)
        урок2.unlock_after = self.урок
        урок2.save(update_fields=['unlock_after'])

        self.assertFalse(lesson_open(урок2, self.ученик))
        пройти(self.ученик, self.задача1)
        пройти(self.ученик, self.задача2)
        self.assertTrue(lesson_open(урок2, self.ученик))

    def test_связка_старше_последовательности(self):
        """Связали руками — значит имели в виду именно это, а не «предыдущий»."""
        self.курс.sequential = True
        self.курс.save(update_fields=['sequential'])
        промежуточный = сделать_урок(self.курс, 'Промежуточный', order=2)
        сделать_задачу(промежуточный, 'Задача', order=1)
        третий = сделать_урок(self.курс, 'Третий', order=3)
        сделать_задачу(третий, 'Задача', order=1)
        третий.unlock_after = self.урок          # мимо промежуточного
        третий.save(update_fields=['unlock_after'])

        пройти(self.ученик, self.задача1)
        пройти(self.ученик, self.задача2)
        # промежуточный НЕ пройден, но третий ждёт не его
        self.assertTrue(lesson_open(третий, self.ученик))


class ТеорияБезЗадачTests(КабинетTestCase):
    """Урок без задач считается пройденным по отметке «прочитано»."""

    def test_прочитанная_теория_открывает_следующий(self):
        self.курс.sequential = True
        self.курс.save(update_fields=['sequential'])
        теория = сделать_урок(self.курс, 'Теория', order=0)
        следующий = self.урок

        self.assertFalse(lesson_done(теория, self.ученик))
        LessonProgress.objects.create(student=self.ученик, lesson=теория,
                                      is_read=True)
        self.assertTrue(lesson_done(теория, self.ученик))
        self.assertTrue(lesson_open(следующий, self.ученик))


class СводкаНеЗовётВЗакрытоеTests(КабинетTestCase):
    """Напоминание про урок, который нельзя открыть, — худший вид напоминания.

    Человек получает «сдай домашку», идёт сдавать и упирается в замок. Дальше он
    решает, что сломался сайт, и пишет об этом вечером.
    """

    def test_закрытый_урок_не_попадает_в_сводку(self):
        self.курс.tracking_mode = 'homework'
        self.курс.save(update_fields=['tracking_mode'])
        урок2 = сделать_урок(self.курс, 'Урок 2', order=2, due=дата(1))
        сделать_задачу(урок2, 'Задача 3', order=1)
        урок2.available_from = дата(10)
        урок2.save(update_fields=['available_from'])

        уроки = {r['lesson'].id for r in homework_for(self.ученик)}
        self.assertIn(self.урок.id, уроки)
        self.assertNotIn(урок2.id, уроки)

    def test_после_открытия_урок_появляется(self):
        self.курс.tracking_mode = 'homework'
        self.курс.save(update_fields=['tracking_mode'])
        урок2 = сделать_урок(self.курс, 'Урок 2', order=2, due=дата(1))
        сделать_задачу(урок2, 'Задача 3', order=1)
        урок2.available_from = дата(-1)
        урок2.save(update_fields=['available_from'])

        уроки = {r['lesson'].id for r in homework_for(self.ученик)}
        self.assertIn(урок2.id, уроки)
