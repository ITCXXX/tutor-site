# -*- coding: utf-8 -*-
"""
Management command: корректирует t_type у подзадач в темах
«Печи для бани», «Форматы листов бумаги», «План квартиры».

Причина: в исходных populate_oge15-*.py разметка t_type была расставлена
неверно. Корректная разметка нужна для конструктора вариантов, который
выбирает подзадачи по t_type из каждой группы.

Правила (из обсуждения с преподавателем):

  • Печи для бани:
        задача про радиус закругления арки кожуха печи — это всегда T5.
        Сейчас они помечены как T1 → переставляем в T5.

  • Форматы листов бумаги:
        задача на отношение сторон A0–A6 — это T3.
        Сейчас они помечены как T5 → переставляем в T3.

  • План квартиры:
        чёткая разбивка по ключевым словам:
          T1 — «Для объектов, указанных в таблице, определите, какими цифрами…»
          T2 — паркет/плитка для пола.
          T3 — «Найдите площадь …».
          T4 — «На сколько процентов площадь … больше …».
          T5 — стиральная машина / интернет / подключение услуг.

Usage:
    python manage.py fix_oge15_ttypes
    python manage.py fix_oge15_ttypes --dry-run  # показать, что произойдёт
"""

import re
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import TaskGroup, GroupSubQuestion


def _strip(html):
    """HTML → плоский текст для поиска ключевых слов."""
    txt = re.sub(r'<[^>]+>', ' ', html or '')
    return re.sub(r'\s+', ' ', txt).strip().lower()


# План квартиры: определение t_type по содержанию.
def detect_ttype_kvartira(text):
    text = text.lower()
    if 'для объектов, указанных в таблице' in text:
        return 'T1'
    if 'паркетная доска' in text or 'плитка для пола' in text:
        return 'T2'
    if 'найдите площадь' in text:
        return 'T3'
    if 'на сколько процентов площадь' in text:
        return 'T4'
    if ('стиральн' in text or 'интернет' in text
            or 'тариф' in text or 'подключ' in text):
        return 'T5'
    return None   # не сопоставлено


class Command(BaseCommand):
    help = 'Корректирует t_type для Печи / Форматы / План квартиры.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать что произойдёт, без записи в БД.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts['dry_run']

        changes = []

        # ── 1. Печи: T1 → T5 ─────────────────────────────────────────────
        for tg in TaskGroup.objects.filter(lesson__title='Печи для бани'):
            for sq in tg.sub_questions.filter(t_type='T1'):
                changes.append((sq, 'T1', 'T5'))

        # ── 2. Форматы листов бумаги: T5 → T3 ─────────────────────────────
        for tg in TaskGroup.objects.filter(lesson__title='Форматы листов бумаги'):
            for sq in tg.sub_questions.filter(t_type='T5'):
                changes.append((sq, 'T5', 'T3'))

        # ── 3. План квартиры: по ключевым словам ──────────────────────────
        unmatched = []
        for tg in TaskGroup.objects.filter(lesson__title='План квартиры'):
            for sq in tg.sub_questions.all():
                text = _strip(sq.question_html)
                new_t = detect_ttype_kvartira(text)
                if new_t is None:
                    unmatched.append(sq)
                    continue
                if new_t != sq.t_type:
                    changes.append((sq, sq.t_type, new_t))

        # ── Отчёт ─────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f'\nИзменений: {len(changes)}'
        ))
        by_lesson = Counter()
        for sq, _old, _new in changes:
            by_lesson[sq.group.lesson.title] += 1
        for lesson, n in by_lesson.most_common():
            self.stdout.write(f'  • {lesson}: {n}')

        if unmatched:
            self.stdout.write(self.style.WARNING(
                f'\nНе удалось определить t_type для {len(unmatched)} подзадач:'
            ))
            for sq in unmatched[:5]:
                txt = _strip(sq.question_html)[:90]
                self.stdout.write(f'  ! [{sq.group.title}] #{sq.order}: {txt}')

        # Подсчёт распределения после правки
        self.stdout.write(self.style.SUCCESS('\nРаспределение после правки:'))
        # эмулируем — применяем changes к копии в памяти
        proposed = {sq.id: new for sq, _old, new in changes}
        for title in ('Печи для бани', 'Форматы листов бумаги', 'План квартиры'):
            for tg in TaskGroup.objects.filter(lesson__title=title):
                cnt = Counter()
                for sq in tg.sub_questions.all():
                    cnt[proposed.get(sq.id, sq.t_type)] += 1
                self.stdout.write(
                    f'  {title} ({tg.sub_questions.count()} подзадач): '
                    + ', '.join(f'{k}={v}' for k, v in sorted(cnt.items()))
                )

        if dry:
            self.stdout.write(self.style.WARNING('\nDRY-RUN: ничего не записано.'))
            return

        # ── Применяем ─────────────────────────────────────────────────────
        for sq, old, new in changes:
            sq.t_type = new
            sq.save(update_fields=['t_type'])
        self.stdout.write(self.style.SUCCESS(
            f'\nПрименено: {len(changes)} изменений.'
        ))
