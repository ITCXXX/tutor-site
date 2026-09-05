# -*- coding: utf-8 -*-
"""Зачёт задания — одно правило на все виды курсов.

Задача может приходить из трёх источников: генератора, банка вопросов и
поля «правильный ответ» у самого задания (курсы с ДЗ). Считается решённое
в каждом случае по-своему, а вот РЕШЕНИЕ о зачёте — общее, и держать его
надо в одном месте: раньше оно было написано дважды и копии разошлись.
"""
from django.db.models import F
from django.utils import timezone

from .models import StudentProgress


def mark_progress(student, assignment, solved, needed, count_attempt=True):
    """Обновить прогресс ученика по заданию и вернуть запись.

    solved  — сколько уже решено (что это значит, решает вызывающий);
    needed  — сколько нужно для зачёта;
    count_attempt — считать ли эту попытку (у пересчётов без ответа не надо).

    Счётчик попыток увеличивается выражением F(): при двух одновременных
    ответах обычное сложение в Python теряло бы один инкремент.
    """
    sp, _ = StudentProgress.objects.get_or_create(student=student, assignment=assignment)

    if count_attempt:
        sp.total_attempts = F('total_attempts') + 1
    # Пишем ровно то, что насчитал вызывающий. Соблазн «не уменьшать» здесь
    # вреден: флаг зачёта всё равно пересчитывается от solved, и счётчик с
    # флагом разъехались бы — в базе «решено 3», а зачёта нет.
    sp.correct_attempts = solved

    было = sp.is_completed
    sp.is_completed = solved >= max(1, needed or 1)
    if sp.is_completed and not было:
        sp.completed_at = timezone.now()
    sp.save()
    return sp


def needed_for(assignment, pool_size=None):
    """Сколько решённых нужно для зачёта этого задания.

    pool_size — сколько задач вообще доступно (вопросов в банке, задач у
    генератора). Требовать больше, чем есть, нельзя: иначе задание нельзя
    сдать в принципе. Для курсов с ДЗ набора нет — там нужно ровно то, что
    записано в задании (обычно один верный ответ).
    """
    нужно = assignment.required_correct or pool_size or 1
    if pool_size:
        нужно = min(нужно, pool_size)
    return max(1, нужно)

def done_assignment_ids(student, assignment_ids, course):
    """Какие из этих задач ученик уже прошёл. Одним запросом.

    Правило «задача пройдена» у нас зависит от вида курса: в задачнике его
    ставит преподаватель (ManualMark), в остальных считает система
    (StudentProgress). Развилка записана ЗДЕСЬ, чтобы её не переписывали в
    каждом новом месте.

    Долг, который стоит помнить: ту же развилку до сих пор считают своими руками
    _build_paragraphs в users/views.py и homework_for в users/homework.py. Их
    надо перевести на эту функцию — тогда правило станет одним по-настоящему.
    """
    from .models import ManualMark, StudentProgress
    ids = list(assignment_ids)
    if not ids:
        return set()
    if getattr(course, 'is_manual', False):
        return {m.assignment_id for m in ManualMark.objects.filter(
            student=student, assignment_id__in=ids, is_completed=True)}
    return set(StudentProgress.objects.filter(
        student=student, assignment_id__in=ids, is_completed=True,
    ).values_list('assignment_id', flat=True))
