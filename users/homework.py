# -*- coding: utf-8 -*-
"""Что задано ученику: сводка по всем курсам с ДЗ сразу.

Отдельный модуль, потому что этим пользуются два разных экрана — кабинет
ученика и (позже) сводка преподавателя, — а логика «сколько осталось» должна
быть одна.

Всё считается пачками. Наивная версия в цикле по урокам делала бы на десятке
курсов сотни запросов и заметно тормозила бы кабинет.
"""
from collections import Counter, defaultdict

from django.utils import timezone

from .models import (
    Assignment, Course, Enrollment, HomeworkAttempt, HomeworkExtension, Lesson,
    StudentProgress, StudentSubmission,
)


def homework_for(student, limit=None):
    """Незакрытые домашки ученика: список словарей, сначала просроченные.

    Строка содержит урок, курс, сколько задач всего и сколько осталось,
    сколько уже ждёт проверки преподавателя, срок и признак просрочки.
    Уроки, где всё сдано, в список не попадают.
    """
    course_ids = list(Enrollment.objects
                      .filter(student=student, is_active=True)
                      .values_list('course_id', flat=True))
    if not course_ids:
        return []

    lessons = list(Lesson.objects
                   .filter(module__course_id__in=course_ids,
                           module__course__tracking_mode=Course.TRACKING_HOMEWORK)
                   .select_related('module__course'))
    if not lessons:
        return []

    lesson_ids = [l.id for l in lessons]
    всего = defaultdict(int)          # урок -> сколько задач
    урок_задачи = {}                  # задача -> урок
    for aid, lid in Assignment.objects.filter(
            lesson_id__in=lesson_ids).values_list('id', 'lesson_id'):
        всего[lid] += 1
        урок_задачи[aid] = lid
    if not урок_задачи:
        return []

    задачи = list(урок_задачи)
    сдано = defaultdict(int)
    for aid in StudentProgress.objects.filter(
            student=student, assignment_id__in=задачи, is_completed=True,
    ).values_list('assignment_id', flat=True):
        сдано[урок_задачи[aid]] += 1

    на_проверке = defaultdict(int)
    for aid in StudentSubmission.objects.filter(
            student=student, assignment_id__in=задачи, is_latest=True,
            status=StudentSubmission.STATUS_PENDING,
    ).values_list('assignment_id', flat=True):
        на_проверке[урок_задачи[aid]] += 1

    сегодня = timezone.localdate()
    # Личные продления — одним запросом на весь список.
    продления = extensions_map(lesson_ids, [student.id])
    строки = []
    for l in lessons:
        n = всего.get(l.id, 0)
        if not n:
            continue                       # урок без задач — задавать нечего
        осталось = n - сдано.get(l.id, 0)
        if осталось <= 0:
            continue                       # всё сдано, показывать незачем
        ext = продления.get((l.id, student.id))
        срок, приём_до = dates_for(l, student, ext)
        строки.append({
            'lesson': l,
            'course': l.module.course,
            'total': n,
            'left': осталось,
            'pending': на_проверке.get(l.id, 0),
            'due': срок,
            'overdue': bool(срок and срок < сегодня),
            'days_left': (срок - сегодня).days if срок else None,
            # Приём закрыт — работу уже не сдать. Из списка такое НЕ убираем:
            # ученик должен видеть, что упустил, а не гадать, куда делось.
            'closed': not accepts_from(l, student, сегодня, ext),
            'cutoff': приём_до,
            # Ученику важно знать, что срок у него личный, — иначе он решит,
            # что видит чужую дату или ошибку.
            'extended': bool(ext and (ext.due_date or ext.cutoff_date)),
        })

    # Сначала просроченные, потом ближайшие по сроку, потом бессрочные.
    строки.sort(key=lambda r: (
        not r['overdue'],
        r['due'] is None,
        r['due'] or сегодня,
    ))
    return строки[:limit] if limit else строки


# ──────────────────────────────────────────────────────────────────────────
# Сводка по одной домашке для преподавателя
# ──────────────────────────────────────────────────────────────────────────

def lesson_report(lesson, students):
    """Кто как сдал эту домашку и какие задачи не даются.

    Возвращает (по_ученикам, по_задачам). Оба списка считаются тремя
    запросами на весь экран, сколько бы ни было учеников и задач: наивная
    версия ходила бы в базу на каждую клетку таблицы.
    """
    задачи = list(lesson.assignments.all().order_by('order', 'id'))
    if not задачи or not students:
        return [], []

    ids_задач = [a.id for a in задачи]
    ids_учеников = [s.id for s in students]

    # Кто что сдал и когда. Время нужно, чтобы отличить сданное вовремя от
    # сданного после срока: в этом и смысл мягкого срока — работу приняли,
    # но факт опоздания виден.
    сдал = set()
    сдано_когда = {}
    for sid, aid, когда in StudentProgress.objects.filter(
            student_id__in=ids_учеников, assignment_id__in=ids_задач,
            is_completed=True).values_list('student_id', 'assignment_id', 'completed_at'):
        сдал.add((sid, aid))
        if когда:
            сдано_когда[(sid, aid)] = timezone.localtime(когда).date()

    # Что ждёт проверки.
    ждёт = set()
    for sid, aid in StudentSubmission.objects.filter(
            student_id__in=ids_учеников, assignment_id__in=ids_задач,
            is_latest=True, status=StudentSubmission.STATUS_PENDING,
    ).values_list('student_id', 'assignment_id'):
        ждёт.add((sid, aid))

    # Все попытки: нужны и для «с первой попытки», и для частой ошибки.
    попытки = defaultdict(list)          # задача -> [(ученик, верно, ответ)]
    for aid, sid, ok, ans in HomeworkAttempt.objects.filter(
            student_id__in=ids_учеников, assignment_id__in=ids_задач,
    ).order_by('created_at').values_list(
            'assignment_id', 'student_id', 'is_correct', 'answer'):
        попытки[aid].append((sid, ok, ans))

    сегодня = timezone.localdate()
    продления = extensions_map([lesson.id], ids_учеников)

    по_ученикам = []
    for s in students:
        ext = продления.get((lesson.id, s.id))
        срок, приём_до = dates_for(lesson, s, ext)
        просрочено = bool(срок and срок < сегодня)
        готово = sum(1 for a in задачи if (s.id, a.id) in сдал)
        на_проверке = sum(1 for a in задачи if (s.id, a.id) in ждёт)
        # Опоздание считаем по ЛИЧНОМУ сроку: у кого продление, тот не опоздал.
        поздно = sum(1 for a in задачи
                     if (s.id, a.id) in сдано_когда
                     and is_late_for(lesson, s, сдано_когда[(s.id, a.id)], ext))
        по_ученикам.append({
            'student': s,
            'done': готово,
            'total': len(задачи),
            'left': len(задачи) - готово,
            'pending': на_проверке,
            'late': поздно,
            'ext': ext,
            'due': срок,
            'cutoff': приём_до,
            'finished': готово == len(задачи),
            # Просрочка — только у тех, кто ещё не закончил: сдавшему вовремя
            # красная метка ни к чему.
            'overdue': просрочено and готово < len(задачи),
        })
    # Сначала те, с кем надо разбираться.
    по_ученикам.sort(key=lambda r: (r['finished'], -r['left'], r['student'].username))

    по_задачам = []
    for a in задачи:
        строки = попытки.get(a.id, [])
        первые = {}                       # ученик -> верна ли ПЕРВАЯ попытка
        неверные = Counter()
        for sid, ok, ans in строки:
            if sid not in первые:
                первые[sid] = ok
            if not ok and ans:
                неверные[ans.strip()] += 1
        решили = sum(1 for s in students if (s.id, a.id) in сдал)
        частая = неверные.most_common(1)[0] if неверные else None
        по_задачам.append({
            'assignment': a,
            'solved': решили,
            'tried': len(первые),
            'first_try': sum(1 for v in первые.values() if v),
            'wrong_total': sum(неверные.values()),
            'common_wrong': частая[0] if частая else '',
            'common_wrong_n': частая[1] if частая else 0,
            # Задача «трудная», если её пробовали и больше половины
            # ошиблись с первой попытки. Порог грубый, зато честный.
            'hard': bool(первые) and sum(1 for v in первые.values() if v) * 2 < len(первые),
        })
    return по_ученикам, по_задачам


# ──────────────────────────────────────────────────────────────────────────
# Сроки конкретного ученика
# ──────────────────────────────────────────────────────────────────────────
# ВСЕ проверки сроков ходят сюда. В этом проекте правило зачёта однажды уже
# разошлось по трём местам и копии перестали совпадать — со сроками повторять
# нельзя, поэтому точка одна.

# «Продление не передавали» и «продления нет» — РАЗНЫЕ вещи, и различать их
# обязательно. Пока обе значили None, пакетная загрузка не работала вовсе: для
# урока без продления карта отдавала None, dates_for считала, что ей ничего не
# передали, и шла в базу сама. Замер до починки: шесть уроков без единого
# продления — восемнадцать запросов, тринадцать из них про продления.
НЕ_ПЕРЕДАНО = object()


def dates_for(lesson, student, ext=НЕ_ПЕРЕДАНО):
    """(срок, приём до) для конкретного ученика с учётом личного продления.

    ext можно передать заранее — тогда запроса не будет (нужно для списков).
    Передать можно и None: это значит «продления у него нет, я проверил».
    Пустое поле в самом продлении означает «как у всех».
    """
    if ext is НЕ_ПЕРЕДАНО:
        ext = (HomeworkExtension.objects
               .filter(lesson=lesson, student=student).first())
    due = (ext.due_date if ext and ext.due_date else lesson.due_date)
    cut = (ext.cutoff_date if ext and ext.cutoff_date else lesson.cutoff_date)
    # Если продлили только срок, общая отсечка могла остаться РАНЬШЕ него —
    # тогда продление было бы пустым обещанием. Держим тот же порядок, что и
    # при вводе: приём не может закрыться раньше срока.
    if cut and due and cut < due:
        cut = due
    return due, cut


def accepts_from(lesson, student, today=None, ext=НЕ_ПЕРЕДАНО):
    """Принимаем ли ещё работу ИМЕННО от этого ученика."""
    _, cut = dates_for(lesson, student, ext)
    if not cut:
        return True
    return (today or timezone.localdate()) <= cut


def is_late_for(lesson, student, when, ext=НЕ_ПЕРЕДАНО):
    """Считается ли сдача этого ученика в этот день опозданием."""
    due, _ = dates_for(lesson, student, ext)
    if not due or not when:
        return False
    return when > due


def extensions_map(lesson_ids, student_ids):
    """Продления пачкой: (урок, ученик) → продление. Для списков и сводок."""
    out = {}
    for e in HomeworkExtension.objects.filter(
            lesson_id__in=lesson_ids, student_id__in=student_ids):
        out[(e.lesson_id, e.student_id)] = e
    return out
