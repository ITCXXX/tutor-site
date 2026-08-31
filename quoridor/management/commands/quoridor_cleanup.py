# -*- coding: utf-8 -*-
"""
Убрать из базы отыгранные и брошенные партии «Заборов».

Обычно уборка делается сама, по дороге, когда кто-нибудь открывает лобби
(quoridor.views.sweep_old_games). Эта команда нужна для двух случаев: когда
в лобби давно никто не заходил, а база уже разрослась, и когда уборку хочется
повесить на cron, не полагаясь на посетителей.

    python manage.py quoridor_cleanup            # удалить, что просрочено
    python manage.py quoridor_cleanup --dry-run  # только посчитать
    python manage.py quoridor_cleanup --all      # снести все сыгранные сразу

Брошенные партии под --all не попадают намеренно: та, у которой срок ещё не
вышел, — это живое приглашение, которого кто-то ждёт.
"""

from django.core.management.base import BaseCommand

from quoridor.models import QuoridorGame


class Command(BaseCommand):
    help = 'Удалить сыгранные и брошенные партии «Заборов»'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='показать, что было бы удалено')
        parser.add_argument('--all', action='store_true',
                            help='удалить все сыгранные партии, не глядя на срок')

    def handle(self, *args, **opts):
        # Предпросмотр и удаление спрашивают об одном и том же у одного и того
        # же метода: если бы они считали каждый по-своему, «покажи, что удалишь»
        # однажды соврало бы — а извиняться было бы уже не перед кем.
        dead, abandoned = QuoridorGame.expired(ignore_age=opts['all'])

        if opts['dry_run']:
            self.stdout.write(
                'под удаление: сыгранных %d, брошенных %d; всего в базе %d'
                % (dead.count(), abandoned.count(), QuoridorGame.objects.count())
            )
            return

        removed = QuoridorGame.purge_old(ignore_age=opts['all'])
        self.stdout.write(self.style.SUCCESS(
            'удалено: сыгранных %d, брошенных %d; осталось %d'
            % (removed['сыгранные'], removed['брошенные'],
               QuoridorGame.objects.count())
        ))
