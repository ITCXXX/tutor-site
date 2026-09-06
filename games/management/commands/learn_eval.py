# -*- coding: utf-8 -*-
"""Подобрать веса оценки по данным самоигры.

    manage.py learn_eval --data games/selfplay_data.csv

Чем это отличается от arena_tune. Там веса подбирались матчами: потомок против
чемпиона, двести партий, кто убедительно лучше. Способ честный, но слепой и
дорогой — двести партий на одно сравнение, и различить перевес в 2% стоит
тысяч партий. Восемь чисел так подобрать можно, сотню нельзя.

Здесь задача другая и решается прямо. У нас есть позиции и то, чем партия
кончилась; надо найти веса, при которых оценка лучше всего предсказывает исход.
Это логистическая регрессия, и для полутора десятков признаков она решается
методом Ньютона за десяток шагов — секунды, а не часы.

Что важно не перепутать. Хорошее предсказание исхода и сильная игра — не одно
и то же. Оценка, которая точнее угадывает победителя в среднем по всем
позициям, может хуже различать близкие ходы, а перебору важно именно это.
Поэтому команда печатает качество предсказания, но НЕ объявляет победителя:
последнее слово за матчем на стенде.

Свободного члена в модели нет, и это не забывчивость. Признаки антисимметричны,
метки тоже: если поменять игроков местами, вектор меняет знак, а метка
превращается в единицу минус себя. Свободный член такую симметрию нарушил бы —
он означал бы «одна из сторон выигрывает чаще просто так».
"""

import json

from django.core.management.base import BaseCommand, CommandError

from games import bot, features, selfplay

ФАЙЛ_ВЕСОВ = 'games/learned_weights.json'

# Оценка используется перебором как число, а не как вероятность, поэтому
# логарифм шансов можно умножить на что угодно — выбор хода не изменится.
# Сотня взята ради читаемости: веса выходят того же порядка, что прежние.
МАСШТАБ = 100.0


def _логпотери(z, y):
    """Средние логистические потери. Считается устойчиво к большим |z|."""
    import numpy as np
    # log(1+e^z) без переполнения
    мягкий = np.logaddexp(0.0, z)
    return float(np.mean(мягкий - y * z))


def _обучить(X, y, l2, шагов=25):
    """Логистическая регрессия методом Ньютона. Возвращает веса."""
    import numpy as np

    n, m = X.shape
    w = np.zeros(m)
    for шаг in range(шагов):
        z = X @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        градиент = X.T @ (p - y) / n + l2 * w
        вес_точки = np.clip(p * (1.0 - p), 1e-9, None)
        гессиан = (X.T * вес_точки) @ X / n + l2 * np.eye(m)
        try:
            шаг_вектор = np.linalg.solve(гессиан, градиент)
        except np.linalg.LinAlgError:            # pragma: no cover
            шаг_вектор = np.linalg.lstsq(гессиан, градиент, rcond=None)[0]
        w = w - шаг_вектор
        if np.max(np.abs(шаг_вектор)) < 1e-10:
            break
    return w


def _подогнать_масштаб(z, y, шагов=40):
    """Один множитель к готовой оценке — чтобы сравнивать честно.

    Прежние веса подобраны матчами, их абсолютная величина случайна. Сравнивать
    их логпотери с обученными без подгонки масштаба значило бы наказать их за
    то, к чему их никто не подбирал.
    """
    import numpy as np
    a = 1e-3
    for _ in range(шагов):
        zz = a * z
        p = 1.0 / (1.0 + np.exp(-np.clip(zz, -30, 30)))
        g = float(np.mean((p - y) * z))
        h = float(np.mean(np.clip(p * (1 - p), 1e-12, None) * z * z))
        if h <= 0:                                # pragma: no cover
            break
        шаг = g / h
        a -= шаг
        if abs(шаг) < 1e-12:
            break
    return a


class Command(BaseCommand):
    help = 'Подобрать веса оценки логистической регрессией по данным самоигры.'

    def add_arguments(self, parser):
        parser.add_argument('--data', dest='данные',
                            default='games/selfplay_data.csv')
        parser.add_argument('--out', dest='файл', default=ФАЙЛ_ВЕСОВ)
        parser.add_argument('--l2', dest='l2', type=float, default=1e-6,
                            help='штраф за большие веса')
        parser.add_argument('--holdout', dest='отложить', type=float,
                            default=0.2, help='доля данных на проверку')
        parser.add_argument('--scale', dest='масштаб', type=float,
                            default=МАСШТАБ)

    def handle(self, *args, **п):
        try:
            import numpy as np
        except ImportError:                       # pragma: no cover
            raise CommandError(
                'нужен numpy: venv\\Scripts\\python.exe -m pip install '
                '-r requirements-dev.txt')

        try:
            имена, X, y = selfplay.прочитать(п['данные'])
        except OSError as беда:
            raise CommandError('не читается %s: %s' % (п['данные'], беда))
        except ValueError as беда:
            raise CommandError(str(беда))

        n = X.shape[0]
        self.stdout.write('Данных: %d позиций, признаков %d' % (n, X.shape[1]))

        # Разделение по порядку не годится: строки идут партиями, и в конце
        # файла лежат позиции тех же партий, что в начале. Перемешиваем.
        rng = np.random.default_rng(20260906)
        порядок = rng.permutation(n)
        X, y = X[порядок], y[порядок]
        граница = int(n * (1 - п['отложить']))
        Xтр, yтр = X[:граница], y[:граница]
        Xпр, yпр = X[граница:], y[граница:]
        self.stdout.write('  обучение %d, проверка %d' % (len(yтр), len(yпр)))

        # Масштабирование по среднеквадратичному, БЕЗ вычитания среднего:
        # вычитание сдвинуло бы нуль и потребовало свободного члена, которого
        # по симметрии быть не должно.
        ско = np.sqrt(np.mean(Xтр * Xтр, axis=0))
        пустые = ско < 1e-12
        if пустые.any():
            self.stdout.write(self.style.WARNING(
                'Признаки, ни разу не встретившиеся: %s'
                % ', '.join(имена[i] for i in np.nonzero(пустые)[0])))
        ско[пустые] = 1.0

        w_масшт = _обучить(Xтр / ско, yтр, п['l2'])
        w = w_масшт / ско

        # Что было до обучения — с честно подогнанным множителем.
        w_старые = np.array([bot.ВЕСА.get(имя, 0.0) for имя in имена])
        a = _подогнать_масштаб(Xтр @ w_старые, yтр)

        было = _логпотери(a * (Xпр @ w_старые), yпр)
        стало = _логпотери(Xпр @ w, yпр)
        монетка = _логпотери(np.zeros(len(yпр)), yпр)

        def доля_угаданных(z):
            есть = yпр != 0.5
            return float(np.mean((z[есть] > 0) == (yпр[есть] > 0.5)))

        self.stdout.write('')
        self.stdout.write('На отложенных данных (меньше — лучше):')
        self.stdout.write('  наугад            логпотери %.4f' % монетка)
        self.stdout.write('  прежние веса      логпотери %.4f, угадано %.1f%%'
                          % (было, 100 * доля_угаданных(a * (Xпр @ w_старые))))
        self.stdout.write('  обученные веса    логпотери %.4f, угадано %.1f%%'
                          % (стало, 100 * доля_угаданных(Xпр @ w)))

        w = w * п['масштаб'] / max(1e-12, float(np.max(np.abs(w))))
        готовые = {имя: round(float(з), 4) for имя, з in zip(имена, w)}
        with open(п['файл'], 'w', encoding='utf-8') as файл:
            json.dump(готовые, файл, ensure_ascii=False, indent=2)

        self.stdout.write('')
        self.stdout.write('Веса (нормированы так, чтобы наибольший был %g):'
                          % п['масштаб'])
        for имя in features.ПРИЗНАКИ:
            self.stdout.write('  %-18s %10.3f' % (имя, готовые[имя]))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Записано: %s' % п['файл']))
        self.stdout.write(self.style.WARNING(
            'Логпотери — не сила игры. Последнее слово за матчем:'))
        self.stdout.write('  manage.py arena --a-weights %s --a hard --b hard '
                          '--games 400' % п['файл'])
