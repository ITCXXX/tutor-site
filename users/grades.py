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

from .models import Assignment, Grade


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


# Оценки берутся НАПРЯМУЮ, а не через сдачи. Раньше ходили через них — и это
# было не просто длиннее, а неверно: оценка за контрольную на бумаге или за
# устный ответ сдачи не имеет, и такой проход её терял. Теперь оценка висит на
# паре «ученик — задача», и запрос стал и проще, и полнее.


def lesson_score(student, lesson):
    """Итог ученика по одному уроку (домашке)."""
    total = Assignment.objects.filter(lesson=lesson).count()
    оценки = list(Grade.objects.filter(student=student, assignment__lesson=lesson))
    return _свод(оценки, total)


def course_score(student, course):
    """Итог ученика по всему курсу — «отношение всего ко всему»."""
    total = Assignment.objects.filter(lesson__module__course=course).count()
    оценки = list(Grade.objects.filter(
        student=student, assignment__lesson__module__course=course))
    return _свод(оценки, total)


def grades_for_lesson(lesson, students):
    """Итоги всех учеников по уроку — для сводки преподавателя.

    Одним запросом на весь класс, а не запросом на ученика: их бывает десятки.
    """
    total = Assignment.objects.filter(lesson=lesson).count()
    по_ученикам = {s.id: [] for s in students}
    for g in Grade.objects.filter(student__in=students, assignment__lesson=lesson):
        if g.student_id in по_ученикам:
            по_ученикам[g.student_id].append(g)
    return {sid: _свод(gs, total) for sid, gs in по_ученикам.items()}


def grades_by_task(student, assignments):
    """{id задачи: оценка} для списка задач — одним запросом.

    Нужен экранам, которые показывают балл рядом с каждым номером: без этого
    там был бы запрос на строку.
    """
    ids = [a.id if hasattr(a, 'id') else a for a in assignments]
    return {g.assignment_id: g
            for g in Grade.objects.filter(student=student, assignment_id__in=ids)}
