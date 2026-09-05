# -*- coding: utf-8 -*-
"""Пересчёт весов планировщика под конкретного ученика.

FSRS идёт со стандартными весами, обученными на большой чужой выборке. По
личной истории повторений их можно подогнать: оптимизатор смотрит, где
предсказание модели разошлось с тем, что ученик на самом деле вспомнил, и
двигает 21 число.

Запуск:

    venv\\Scripts\\python.exe manage.py fsrs_optimize            — все ученики
    venv\\Scripts\\python.exe manage.py fsrs_optimize --user петя
    venv\\Scripts\\python.exe manage.py fsrs_optimize --dry-run   — только посчитать

Две честные оговорки.

**Нужен torch.** Оптимизатор — единственная часть библиотеки с тяжёлыми
зависимостями; сама библиотека их не тянет. Ставится отдельно:
`venv\\Scripts\\python.exe -m pip install "fsrs[optimizer]"` (около 2,5 ГБ).
На боевой сервер это ставить незачем — считать веса можно на рабочей машине по
выгрузке базы, а в прод класть уже результат.

**Нужна история.** Ниже 512 повторений оптимизатор возвращает ровно те же
стандартные веса — считать нечего. Команда в этом случае ничего не записывает
и говорит, сколько ещё не хватает.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from cards.models import CardReview, SchedulerWeights
from cards.srs import ПОРОГ_ОБУЧЕНИЯ


class Command(BaseCommand):
    help = 'Пересчитать веса FSRS по истории повторений ученика'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user', dest='логин', default=None,
            help='Логин ученика. Без него — все, у кого есть история.',
        )
        parser.add_argument(
            '--dry-run', dest='вхолостую', action='store_true',
            help='Посчитать и показать, но в базу не записывать.',
        )

    def handle(self, *args, **параметры):
        User = get_user_model()
        логин = параметры.get('логин')

        ученики = User.objects.filter(username=логин) if логин else (
            User.objects.filter(
                pk__in=CardReview.objects.values_list('user', flat=True).distinct()
            )
        )
        ученики = list(ученики.order_by('username'))
        if not ученики:
            self.stdout.write('Ни у кого нет истории повторений — считать нечего.')
            return

        оптимизатор = self._оптимизатор()

        for ученик in ученики:
            записей = CardReview.objects.filter(user=ученик).count()
            подпись = 'ученик %s: %d повторени%s' % (
                ученик.username, записей,
                'е' if записей % 10 == 1 and записей % 100 != 11 else 'й',
            )

            if записей < ПОРОГ_ОБУЧЕНИЯ:
                self.stdout.write(
                    '%s — мало, нужно %d. Остаётся на стандартных весах.'
                    % (подпись, ПОРОГ_ОБУЧЕНИЯ)
                )
                continue

            if оптимизатор is None:
                self.stderr.write(
                    '%s — истории хватает, но оптимизатор не установлен.\n'
                    'Поставьте его: venv\\Scripts\\python.exe -m pip install '
                    '"fsrs[optimizer]"' % подпись
                )
                return

            self.stdout.write('%s — считаю…' % подпись)
            новые = self._посчитать(оптимизатор, ученик)
            if новые is None:
                continue

            self.stdout.write('  веса: %s' % ', '.join('%.4f' % в for в in новые))
            if параметры.get('вхолостую'):
                self.stdout.write(self.style.WARNING('  вхолостую — не записываю'))
                continue

            SchedulerWeights.objects.update_or_create(
                user=ученик,
                defaults={'parameters': list(новые), 'reviews_used': записей,
                          'note': 'fsrs_optimize'},
            )
            self.stdout.write(self.style.SUCCESS('  записано'))

    def _оптимизатор(self):
        """Класс оптимизатора или None, если torch не установлен."""
        try:
            from fsrs import Optimizer
        except ImportError:
            return None
        try:
            # Библиотека подменяет класс заглушкой, если torch отсутствует;
            # заглушка ругается только при создании объекта, поэтому проверяем
            # так, а не по наличию имени.
            Optimizer([])
        except ImportError:
            return None
        except Exception:
            # Пустая история — законный отказ, класс на месте.
            pass
        return Optimizer

    def _посчитать(self, Optimizer, ученик):
        """Собрать журнал ученика в вид, понятный библиотеке, и обучить веса."""
        from fsrs import Rating, ReviewLog

        # Прямое и обратное направления — для оптимизатора разные карточки:
        # у них своя история и своя прочность. Склеив их под одним номером, мы
        # научили бы модель на смеси двух разных кривых забывания.
        журнал = [
            ReviewLog(
                card_id=отметка.card_id * 10 + отметка.direction,
                rating=Rating(отметка.rating),
                review_datetime=отметка.reviewed_at,
                review_duration=отметка.duration_ms,
            )
            for отметка in CardReview.objects
            .filter(user=ученик).order_by('reviewed_at')
        ]
        try:
            return Optimizer(журнал).compute_optimal_parameters()
        except Exception as беда:                      # pragma: no cover
            self.stderr.write('  не вышло: %s' % беда)
            return None
