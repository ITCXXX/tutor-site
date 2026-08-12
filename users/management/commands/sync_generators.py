# -*- coding: utf-8 -*-
"""Выгружает python_code всех ProblemGenerator в users/generators/g<id>.py.

Пункт 6: генераторы исполняются из репозитория (users/generators/), а не через
exec() кода из БД. Эта команда пересобирает файлы из поля python_code — запускать
ПОСЛЕ seed_oge*/изменений генераторов в БД, чтобы репо-файлы (источник истины для
ИСПОЛНЕНИЯ) не разошлись с БД.

    python manage.py sync_generators
    python manage.py sync_generators --check   # только показать расхождения, не писать
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from users.models import ProblemGenerator

HEADER = (
    "# -*- coding: utf-8 -*-\n"
    "# AUTO-GENERATED из ProblemGenerator id={id}: {name}\n"
    "# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).\n"
    "# random / math / Fraction добавлены в шапку — часть генераторов\n"
    "# полагалась на инъекцию этих имён старым execute_generator().\n"
    "import random  # noqa: F401\n"
    "import math  # noqa: F401\n"
    "from fractions import Fraction  # noqa: F401\n"
    "\n\n"
)


def _module_body(g):
    code = (g.python_code or '').replace('\r\n', '\n').replace('\r', '\n')
    name = (g.name or '').replace('\n', ' ').strip()
    body = HEADER.format(id=g.id, name=name) + code
    if not body.endswith('\n'):
        body += '\n'
    return body


class Command(BaseCommand):
    help = 'Пересобирает users/generators/g<id>.py из ProblemGenerator.python_code'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check', action='store_true',
            help='Только показать, какие файлы устарели/отсутствуют, ничего не писать',
        )

    def handle(self, *args, **opts):
        out_dir = os.path.join(settings.BASE_DIR, 'users', 'generators')
        os.makedirs(out_dir, exist_ok=True)
        check_only = opts['check']

        written = stale = 0
        for g in ProblemGenerator.objects.all().order_by('id'):
            path = os.path.join(out_dir, f'g{g.id}.py')
            body = _module_body(g)
            current = None
            if os.path.exists(path):
                with open(path, encoding='utf-8') as f:
                    current = f.read()
            if current == body:
                continue
            stale += 1
            if check_only:
                self.stdout.write(f'  устарел/новый: g{g.id}.py ({g.name[:50]})')
                continue
            with open(path, 'w', encoding='utf-8') as f:
                f.write(body)
            written += 1

        if check_only:
            self.stdout.write(self.style.WARNING(
                f'Расхождений с БД: {stale}') if stale
                else self.style.SUCCESS('Файлы генераторов синхронны с БД'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Записано/обновлено файлов: {written}'))
