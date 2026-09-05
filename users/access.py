# -*- coding: utf-8 -*-
"""Кто и что может открыть: окно записи и условия доступа к уроку.

ОДНО МЕСТО НА ВСЁ. Правило зачёта в этом проекте разъехалось по трём файлам, и
разбирать это до сих пор дорого. Здесь того же не повторяем.

Сюда ходят: страница урока, приём развёрнутого решения, приём короткого ответа,
отметка «прочитано», переписка («спросить по задаче») и ночная рассылка
напоминаний. Первые четыре пришли не сразу: сначала я закрыл только показ
страницы, и аудит справедливо назвал это «замок на двери при открытых окнах» —
отправку легко повторить мимо страницы, а отметка «прочитано» вообще отпирала
следующий урок сама.

Чего здесь ПОКА НЕТ и о чём надо помнить: страницы практики (users/views_exam.py)
и блочные задачи ОГЭ (users/views_oge1_5.py) держат свою проверку доступа. Это
чужая незаконченная работа, трогать её сейчас нельзя; когда она закончится, её
надо перевести сюда же.

Правил всего три, и порядок между ними такой:

  1. ОКНО ЗАПИСИ. Записан, но доступ ещё не начался или уже кончился — закрыто
     всё, независимо от уроков.
  2. ДАТА ОТКРЫТИЯ УРОКА. «Откроется с» — общая для всех.
  3. ПРЕДШЕСТВЕННИК. Либо явная связка (unlock_after), либо последовательный
     курс, где каждый урок ждёт предыдущего.

Бесплатный урок (is_free) — витрина, он открыт всегда и ни одного из правил не
слушает: иначе на курс нельзя было бы заглянуть до записи.
"""

from django.utils import timezone

from .models import Assignment, Enrollment, Lesson, LessonProgress
from .progress import done_assignment_ids


# ─────────────────────────── окно записи ───────────────────────────

def enrollment_open(enr, today=None):
    """Действует ли запись ПРЯМО СЕЙЧАС.

    is_active — это «не отчислен», а окно — «доступ открыт в этот день». Разные
    вещи: ученик, записанный в июне на сентябрьский курс, числится и виден в
    списках, но открыть курс ещё не может.
    """
    if enr is None or not enr.is_active:
        return False
    today = today or timezone.localdate()
    if enr.starts_at and today < enr.starts_at:
        return False
    if enr.ends_at and today > enr.ends_at:   # день включительно
        return False
    return True


def enrollment_of(student, course):
    return Enrollment.objects.filter(student=student, course=course).first()


# ─────────────────────── пройден ли урок ───────────────────────

def lesson_done(lesson, student, готовые=None):
    """Пройден ли урок целиком.

    Урок с задачами пройден, когда пройдены ВСЕ его задачи. Урок без задач
    (теория, методичка) — когда отмечен прочитанным: другого следа он не
    оставляет.

    готовые — заранее посчитанное множество id сделанных задач, чтобы список
    уроков не превращался в запрос на урок.
    """
    ids = list(Assignment.objects.filter(lesson=lesson).values_list('id', flat=True)) \
        if готовые is None else [a.id for a in lesson.assignments.all()]
    if готовые is None:
        готовые = done_assignment_ids(student, ids, lesson.module.course)
    if not ids:
        return LessonProgress.objects.filter(
            student=student, lesson=lesson, is_read=True).exists()
    return all(i in готовые for i in ids)


# ─────────────────────── доступ к уроку ───────────────────────

def lock_reason_with(lesson, enr, today, пройден):
    """Та же проверка, но на ГОТОВЫХ данных — для списков.

    Правило записано здесь один раз, а входов к нему два: страница урока
    (lesson_lock_reason сама сходит в базу) и списки вроде сводки домашек, где
    запись и пройденность уже посчитаны пачкой. Иначе список пришлось бы
    считать своим кодом — и правило разъехалось бы на второй же неделе.

    пройден — функция(урок) → bool: список отвечает из памяти, страница
    запросом.
    """
    if getattr(lesson, 'is_free', False):
        return None
    if enr is None:
        return 'Вы не записаны на этот курс.'
    if not enr.is_active:
        return 'Запись на курс приостановлена.'
    if enr.starts_at and today < enr.starts_at:
        return 'Курс откроется %s.' % enr.starts_at.strftime('%d.%m.%Y')
    if enr.ends_at and today > enr.ends_at:
        return 'Доступ к курсу закончился %s.' % enr.ends_at.strftime('%d.%m.%Y')
    if lesson.available_from and today < lesson.available_from:
        return 'Урок откроется %s.' % lesson.available_from.strftime('%d.%m.%Y')
    предшественник = _предшественник(lesson)
    if предшественник is not None and not пройден(предшественник):
        return 'Сначала нужно пройти «%s».' % предшественник.title
    return None


def lesson_lock_reason(lesson, student, today=None):
    """Почему урок закрыт для этого ученика. None — открыт.

    Возвращает не True/False, а ПРИЧИНУ: «закрыто» без объяснения ученик читает
    как поломку сайта и пишет преподавателю. Строку показываем как есть.
    """
    if getattr(lesson, 'is_free', False):
        return None
    today = today or timezone.localdate()
    enr = enrollment_of(student, lesson.module.course)
    return lock_reason_with(lesson, enr, today,
                            lambda l: lesson_done(l, student))


def _предшественник(lesson):
    """Урок, который надо пройти раньше этого. None — такого нет.

    Явная связка старше последовательности: если преподаватель связал уроки
    руками, он имел в виду именно это, а не «предыдущий по порядку».
    """
    if lesson.unlock_after_id:
        return lesson.unlock_after
    if not lesson.module.course.sequential:
        return None
    # Предыдущий по порядку внутри курса: сначала в своём модуле, а если урок
    # первый в модуле — последний из предыдущего модуля.
    свой = (Lesson.objects
            .filter(module=lesson.module, order__lt=lesson.order)
            .order_by('-order').first())
    if свой is not None:
        return свой
    прошлый_модуль = (lesson.module.course.modules
                      .filter(order__lt=lesson.module.order)
                      .order_by('-order').first())
    if прошлый_модуль is None:
        return None
    return (Lesson.objects.filter(module=прошлый_модуль)
            .order_by('-order').first())


def lesson_open(lesson, student, today=None):
    return lesson_lock_reason(lesson, student, today) is None
