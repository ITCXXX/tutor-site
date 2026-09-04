# -*- coding: utf-8 -*-
"""Оценки: расчёт итога ДВУМЯ способами сразу.

Владелец сайта считает балл двумя способами, и это не «или-или»:

  • сумма к сумме — набранное по всем номерам делить на максимум по всем.
    Крупный номер весит больше мелкого;
  • среднее процентов — процент за каждый номер, потом среднее.
    Все номера весят одинаково.

Числа расходятся, и заметно. Номер на 10 баллов, решённый наполовину, и номер
на 1 балл, решённый целиком: первый способ даёт 55%, второй — 75%. Поэтому не
выбираем, а храним атом (балл за номер) и показываем обе цифры.

ЧТО В ЗНАМЕНАТЕЛЕ. Считаем по ПРОВЕРЕННЫМ работам, а рядом говорим, сколько
номеров всего. Иначе ученик, сдавший половину и ждущий проверки, видел бы
низкий процент не потому, что решил плохо, а потому, что до него ещё не дошли
руки. Когда проверено всё, разницы нет.

Единственное место, где эти правила записаны: расчёт, разъехавшийся по двум
шаблонам, в этом проекте уже случался — с правилом зачёта.
"""

from django.db.models import Prefetch

from .models import Assignment, Grade, StudentSubmission


def _пусто(total=0):
    return {
        'earned': 0.0, 'maximum': 0.0,
        'by_sum': None, 'by_avg': None,
        'graded': 0, 'total': total, 'has_any': False,
    }


def _свод(оценки, total):
    """Собрать обе цифры из списка оценок за номера."""
    if not оценки:
        return _пусто(total)
    earned = sum(float(g.final) for g in оценки)
    maximum = sum(float(g.max_value) for g in оценки)
    проценты = [g.percent for g in оценки if g.percent is not None]
    return {
        'earned': round(earned, 2),
        'maximum': round(maximum, 2),
        # Сумма к сумме: крупный номер весит больше.
        'by_sum': round(earned * 100.0 / maximum, 1) if maximum else None,
        # Среднее процентов: все номера весят одинаково.
        'by_avg': round(sum(проценты) / len(проценты), 1) if проценты else None,
        'graded': len(оценки),
        'total': total,
        'has_any': True,
    }


def lesson_score(student, lesson):
    """Итог ученика по одному уроку (домашке)."""
    total = Assignment.objects.filter(lesson=lesson).count()
    оценки = [
        s.grade for s in StudentSubmission.objects
        .filter(student=student, assignment__lesson=lesson, is_latest=True)
        .select_related('grade')
        if getattr(s, 'grade', None) is not None
    ]
    return _свод(оценки, total)


def course_score(student, course):
    """Итог ученика по всему курсу — «отношение всего ко всему»."""
    total = Assignment.objects.filter(lesson__module__course=course).count()
    оценки = [
        s.grade for s in StudentSubmission.objects
        .filter(student=student, assignment__lesson__module__course=course,
                is_latest=True)
        .select_related('grade')
        if getattr(s, 'grade', None) is not None
    ]
    return _свод(оценки, total)


def grades_for_lesson(lesson, students):
    """Итоги всех учеников по уроку — для сводки преподавателя.

    Одним проходом, а не запросом на ученика: в классе их бывает десятки.
    """
    total = Assignment.objects.filter(lesson=lesson).count()
    по_ученикам = {s.id: [] for s in students}
    subs = (StudentSubmission.objects
            .filter(student__in=students, assignment__lesson=lesson, is_latest=True)
            .select_related('grade'))
    for s in subs:
        g = getattr(s, 'grade', None)
        if g is not None and s.student_id in по_ученикам:
            по_ученикам[s.student_id].append(g)
    return {sid: _свод(gs, total) for sid, gs in по_ученикам.items()}
