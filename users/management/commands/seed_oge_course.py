# -*- coding: utf-8 -*-
"""Создаёт сам курс ОГЭ — то, с чего начинаются все остальные seed-команды.

Зачем отдельная команда. Уроки, задания и генераторы описаны кодом
(`populate_oge15_*`, `seed_oge16…19`, `seed_oge20…25`), но каждая из этих команд
начинается с поиска курса по slug и молча отказывается работать, если его нет:

    Курс ОГЭ (slug=oge-maths) не найден.

Сам курс до сих пор заводился руками через админку, и на новом сервере
получалась курица без яйца: контент есть в репозитории, а положить его некуда.
Теперь курс тоже описан кодом, и DEPLOY.md не врёт, обещая репозиторий
единственным источником правды.

Запуск:

    python manage.py seed_oge_course           # создать, если нет
    python manage.py seed_oge_course --list    # показать, какие курсы уже есть

Команду можно запускать сколько угодно раз: существующий курс она не трогает —
ни названия, ни описания, ни настроек. Название и обложку правьте в админке,
повторный запуск их не затрёт.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module

SLUG = 'oge-maths'
НАЗВАНИЕ = 'ОГЭ'
ОПИСАНИЕ = 'Подготовка к ОГЭ по математике: все задания первой и второй части.'

# Порядок модулей тот же, что на рабочей машине: сначала задания 1–5 (они идут
# блоком с общим условием), потом остальная первая часть, потом вторая.
МОДУЛИ = [
    (0, 'Задания 1-5'),
    (1, 'Первая часть'),
    (2, 'Вторая часть'),
]


class Command(BaseCommand):
    help = 'Создать курс ОГЭ (slug=oge-maths) с тремя модулями, если его ещё нет'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list', dest='показать', action='store_true',
            help='Только показать существующие курсы и выйти.',
        )

    def handle(self, *args, **параметры):
        if параметры.get('показать'):
            self._показать_курсы()
            return

        существующий = Course.objects.filter(slug=SLUG).first()
        if существующий:
            self.stdout.write('Курс уже есть: «%s» (slug=%s).'
                              % (существующий.title, существующий.slug))
            курс = существующий
        else:
            # Курс общий: без владельца и публичный, как остальные учебные
            # курсы сайта. Приватные курсы преподаватель заводит сам через
            # кабинет — у них другой slug и другой смысл.
            курс = Course.objects.create(
                slug=SLUG, title=НАЗВАНИЕ, short_description=ОПИСАНИЕ,
                tracking_mode=Course.TRACKING_AUTO,
                is_public=True, is_active=True, order=0,
            )
            self.stdout.write(self.style.SUCCESS(
                'Курс создан: «%s» (slug=%s).' % (курс.title, курс.slug)))

        with transaction.atomic():
            for порядок, название in МОДУЛИ:
                модуль, создан = Module.objects.get_or_create(
                    course=курс, title=название,
                    defaults={'order': порядок, 'description': ''},
                )
                self.stdout.write('  модуль «%s»%s'
                                  % (модуль.title, ' (создан)' if создан else ''))

        self.stdout.write('')
        self.stdout.write('Дальше — наполнение:')
        self.stdout.write('  manage.py populate_oge15_run_all      # задания 1–5')
        self.stdout.write('  manage.py seed_oge16 … seed_oge19     # первая часть')
        self.stdout.write('  manage.py seed_oge20 … seed_oge25     # вторая часть')

    def _показать_курсы(self):
        курсы = Course.objects.all().order_by('order', 'id')
        if not курсы:
            self.stdout.write('Курсов нет вообще.')
            return
        self.stdout.write('%-24s %-32s %-8s %s'
                          % ('slug', 'название', 'публ.', 'модулей'))
        for курс in курсы:
            self.stdout.write('%-24s %-32s %-8s %d'
                              % (курс.slug, курс.title[:32],
                                 'да' if курс.is_public else 'нет',
                                 курс.modules.count()))
