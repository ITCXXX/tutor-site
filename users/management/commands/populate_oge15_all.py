# -*- coding: utf-8 -*-
"""Создаёт TaskGroup-ы для всех групп ОГЭ №1-5 из oge15_all_groups.json.

JSON формат:
  {
    "<gid>": {
      "theme": "shiny|dorogi|bumaga|...",
      "ctx_text":  "<текст контекста>",
      "ctx_img":   "oge15_<gid>.<ext>",   # имя файла в media/oge15/
      "ctx_tables": [[<row>, <row>, ...], ...],   # каждая таблица — список строк-списков
      "tasks": [
        {
          "no": 1, "tid": "...",
          "text": "<текст задачи без префикса>",
          "answer": "<правильный ответ>",
          "tables": [[<row>, ...], ...],    # таблицы внутри задачи
        }, ...
      ]
    }, ...
  }

Запуск:
    python manage.py populate_oge15_all --clear
"""

import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion


THEME_TITLES = {
    'dorogi':    'Дороги',
    'slozhnye':  'Сложные дороги',
    'uchastki':  'Участки',
    'kvartiry':  'Квартиры',
    'shiny':     'Шины',
    'pechi':     'Печи',
    'bumaga':    'Бумага',
    'mobilny':   'Мобильный интернет',
}
LESSON_ORDER = {
    'dorogi': 1, 'slozhnye': 2, 'uchastki': 3, 'kvartiry': 4,
    'shiny': 5, 'pechi': 6, 'bumaga': 7, 'mobilny': 8,
}


def render_table(rows):
    """rows: список списков строк → HTML таблица.
    Эвристики:
      * Первая строка → <thead> (заголовки), если в ней нет пустых ячеек
      * Если первая ячейка строки тоже жирная (заголовок), оставляем как <th>
    Стили: border, padding, фон у заголовков.
    """
    if not rows:
        return ''
    # Удаляем пустые строки в конце
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ''
    out = ['<table style="border-collapse:collapse;margin:0.5em 0;">']
    for ri, row in enumerate(rows):
        out.append('<tr>')
        for ci, cell in enumerate(row):
            is_header = ri == 0 or (ci == 0 and len(row) > 1 and not cell.replace(',', '').replace('.', '').replace(' ', '').replace('—', '').replace('-', '').isdigit())
            tag = 'th' if is_header else 'td'
            bg = ';background:#eef' if is_header else ''
            style = f'border:1px solid #999;padding:0.4em 0.7em;text-align:center{bg}'
            txt = cell.strip() or '&nbsp;'
            out.append(f'<{tag} style="{style}">{txt}</{tag}>')
        out.append('</tr>')
    out.append('</table>')
    return ''.join(out)


def clean_text(s):
    s = s or ''
    # Удалить мусор от ShowPicture
    s = s.replace('ShowPicture', '').strip()
    # Удалить префиксы FIPI
    s = s.replace('Прочитайте текст и выполните задания.', '').strip()
    s = s.replace('Прочитайте внимательно текст и выполните задания 1–5.', '').strip()
    s = s.replace('Прочитайте внимательно текст и выполните задания 1– 5.', '').strip()
    s = s.replace('Прочитайте внимательно текст и выполните задания 1 – 5.', '').strip()
    s = s.replace('Прочитайте внимательно текст и выполните задания.', '').strip()
    # Удалить префикс задачи
    import re
    s = re.sub(r'^Задание №\d+\.\s*Впишите правильный ответ\.\s*', '', s)
    s = re.sub(r'^Задание №\d+\.\s*Дайте развернутый ответ\.\s*', '', s)
    s = re.sub(r'^Задание №\d+\.\s*Выберите правильный ответ\.\s*', '', s)
    s = re.sub(r'^Задание №\d+\.\s*Установите соответствие и впишите ответ\.\s*', '', s)
    s = re.sub(r'^Задание №\d+\.\s*', '', s)
    return s.strip()


def make_ctx_html(group):
    """Контекст: текст + картинка + таблицы (если есть в контексте)."""
    parts = []
    parts.append(f'<div class="oge15-context">')
    text = clean_text(group.get('ctx_text', ''))
    if text:
        # Просто как один абзац (ученик увидит весь текст)
        parts.append(f'<p>{text}</p>')
    img = group.get('ctx_img')
    if img:
        parts.append(f'<img src="/media/oge15/{img}" alt="ФИПИ" '
                     f'style="max-width:480px;display:block;margin:0.8em auto;">')
    for tbl in group.get('ctx_tables', []):
        parts.append(render_table(tbl))
    parts.append('</div>')
    return '\n'.join(parts)


def make_task_html(task, exclude_text_in_table=True):
    """Задача: текст вопроса + её таблицы."""
    parts = []
    text = clean_text(task.get('text', ''))
    if text:
        parts.append(f'<p>{text}</p>')
    # Таблицы — пропускаем первую строку, если она дублирует текст
    for tbl in task.get('tables', []):
        # Уберём строки, в которых содержится исходный текст полностью
        clean_tbl = [r for r in tbl if not (len(r) == 1 and r[0] == text)]
        # Иногда первая строка имеет всё в одной ячейке (мусор)
        if clean_tbl and len(clean_tbl[0]) > 0 and len(clean_tbl[0][0]) > 200:
            clean_tbl = clean_tbl[1:]
        if clean_tbl:
            parts.append(render_table(clean_tbl))
    return '\n'.join(parts)


class Command(BaseCommand):
    help = "Создаёт TaskGroup-ы для всех групп №1-5 из oge15_all_groups.json"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true')
        parser.add_argument('--json',
                            default=os.path.join(settings.BASE_DIR, 'oge1_5_setup', 'oge15_all_groups.json'))

    def handle(self, *args, **opts):
        path = opts['json']
        if not os.path.exists(path):
            self.stdout.write(self.style.ERROR(f"JSON не найден: {path}"))
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        try:
            course = Course.objects.get(slug='oge-maths')
        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR("Курс oge-maths не найден"))
            return

        module, _ = Module.objects.get_or_create(
            course=course, title='Задания 1-5',
            defaults={'order': 1, 'description': ''},
        )

        # Группируем по темам
        by_theme = {}
        for gid, g in data.items():
            by_theme.setdefault(g.get('theme', 'dorogi'), []).append((gid, g))

        for theme, items in by_theme.items():
            title = THEME_TITLES.get(theme, theme.capitalize())
            order = LESSON_ORDER.get(theme, 99)
            lesson, _ = Lesson.objects.get_or_create(
                module=module, title=title,
                defaults={'lesson_type': 'practice', 'order': order, 'content': '', 'is_free': False},
            )
            if opts['clear']:
                n, _ = TaskGroup.objects.filter(lesson=lesson).delete()
                if n:
                    self.stdout.write(self.style.WARNING(f"  Очищен Lesson {title}: -{n}"))

            self.stdout.write(self.style.NOTICE(f"\n=== {title} ({len(items)} групп) ==="))
            for idx, (gid, g) in enumerate(items, 1):
                group, created = TaskGroup.objects.update_or_create(
                    lesson=lesson, fipi_ctx_id=gid,
                    defaults={
                        'title': gid,
                        'context_html': make_ctx_html(g),
                        'order': idx,
                    },
                )
                if not created:
                    group.sub_questions.all().delete()
                for i, t in enumerate(g['tasks'], 1):
                    GroupSubQuestion.objects.create(
                        group=group,
                        question_html=make_task_html(t),
                        correct_answer=t.get('answer', '') or '',
                        t_type='',
                        fipi_task_id=t.get('tid', ''),
                        order=i,
                    )
                ans_ok = sum(1 for t in g['tasks'] if t.get('answer'))
                self.stdout.write(f"  {gid:>8s}: {len(g['tasks'])} задач, ответы {ans_ok}/{len(g['tasks'])}")

        total = TaskGroup.objects.filter(lesson__module=module).count()
        subq = GroupSubQuestion.objects.filter(group__lesson__module=module).count()
        self.stdout.write(self.style.SUCCESS(f"\nГотово: {total} групп, {subq} подзадач."))
