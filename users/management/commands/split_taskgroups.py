# -*- coding: utf-8 -*-
"""
Management command: разбивает «слипшиеся» TaskGroup на пятёрки (одна группа =
один связный вариант из 5 подзадач T1..T5, разделяющих общий контекст).

Идемпотентность: если все группы уже разбиты (по 5 или 4 подзадач) —
команда ничего не делает.

Что считается «сбалансированной» группой:
    • N = 5·k подзадач, k > 1
    • каждый t_type встречается ровно k раз (T1*k, T2*k, ..., T5*k)
    • t_type'ы из множества {T1, T2, T3, T4, T5}

Для несбалансированных групп команда ничего не делает и выводит
предупреждение. Это сигнал поправить t_type через fix_oge15_ttypes
(или вручную в админке).

Что происходит при разбиении группы с N=k·5:
    • создаются k новых TaskGroup в том же lesson;
    • каждая получает копию context_html и fipi_ctx_id;
    • title нового варианта = «<старый title> · вариант i» (i от 1 до k);
    • подзадачи перераспределяются: i-я по счёту подзадача каждого t_type
      попадает в i-ю новую группу с order = 1..5 (по T-номеру);
    • старая группа удаляется (после переноса подзадач у неё уже нет связей);
    • order'ы в lesson перенумеровываются подряд (1, 2, 3, ...).

Usage:
    python manage.py split_taskgroups --dry-run    # показать что будет
    python manage.py split_taskgroups              # реальное разбиение
"""

from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import TaskGroup


T_TYPES = ('T1', 'T2', 'T3', 'T4', 'T5')


def _classify(tg):
    sqs = list(tg.sub_questions.all())
    n = len(sqs)
    if n in (4, 5):
        return 'ok-5', None
    c = Counter(sq.t_type for sq in sqs)
    if set(c.keys()) != set(T_TYPES):
        return 'unbalanced', dict(c)
    counts = set(c.values())
    if len(counts) != 1:
        return 'unbalanced', dict(c)
    k = counts.pop()
    if k * 5 != n:
        return 'unbalanced', dict(c)
    return 'balanced', k


class Command(BaseCommand):
    help = 'Разбивает сбалансированные TaskGroup на пятёрки.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts['dry_run']

        to_split = []
        unbalanced = []

        for tg in TaskGroup.objects.all():
            kind, info = _classify(tg)
            if kind == 'balanced':
                to_split.append((tg, info))
            elif kind == 'unbalanced':
                unbalanced.append((tg, info))

        self.stdout.write(self.style.SUCCESS(
            f'\nК разбиению: {len(to_split)} групп → '
            f'{sum(k for _, k in to_split)} новых пятёрок'
        ))
        for tg, k in to_split:
            self.stdout.write(
                f'  [{tg.lesson.title}] {tg.title[:50]} ({k*5} подзадач) → {k} пятёрок'
            )

        if unbalanced:
            self.stdout.write(self.style.WARNING(
                f'\n⚠ Не подходят (нужна правка t_type): {len(unbalanced)} групп'
            ))
            for tg, c in unbalanced:
                self.stdout.write(
                    f'  [{tg.lesson.title}] {tg.title[:50]}: {c}'
                )

        if dry:
            self.stdout.write(self.style.WARNING('\nDRY-RUN: ничего не записано.'))
            return

        if not to_split:
            self.stdout.write('\nНечего разбивать.')
            return

        for tg, k in to_split:
            self._split_one(tg, k)

        touched_lessons = {tg.lesson for tg, _ in to_split}
        for lesson in touched_lessons:
            self._renumber(lesson)

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово. Разбито {len(to_split)} групп, '
            f'создано {sum(k for _, k in to_split)} пятёрок.'
        ))

    def _split_one(self, tg, k):
        by_type = defaultdict(list)
        for sq in tg.sub_questions.order_by('order'):
            by_type[sq.t_type].append(sq)

        max_order = (
            TaskGroup.objects.filter(lesson=tg.lesson)
            .order_by('-order').values_list('order', flat=True).first()
            or 0
        )

        for i in range(k):
            new_tg = TaskGroup.objects.create(
                lesson=tg.lesson,
                title=f'{tg.title} · вариант {i + 1}',
                context_html=tg.context_html,
                order=max_order + 1 + i,
                fipi_ctx_id=tg.fipi_ctx_id,
            )
            for t_idx, t in enumerate(T_TYPES, start=1):
                sq = by_type[t][i]
                sq.group = new_tg
                sq.order = t_idx
                sq.save(update_fields=['group', 'order'])

        tg.delete()

    def _renumber(self, lesson):
        groups = list(TaskGroup.objects.filter(lesson=lesson).order_by('order', 'id'))
        # Двойной проход: сначала во временные большие order'ы, затем в финальные.
        for i, tg in enumerate(groups):
            tg.order = 1000 + i
            tg.save(update_fields=['order'])
        for i, tg in enumerate(groups, start=1):
            tg.order = i
            tg.save(update_fields=['order'])
