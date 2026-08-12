# -*- coding: utf-8 -*-
"""Реестр генераторов задач, вынесенных из БД (пункт 6: без exec).

`ProblemGenerator.execute_generator()` зовёт get_generator(id) и вызывает
функцию generate_task() из соответствующего модуля g<id>.py вместо exec()
кода из поля python_code. Модули импортируются лениво и кэшируются.

Источник истины для ИСПОЛНЕНИЯ теперь — эти файлы. Поле python_code в БД
сохранено как бэкап/для admin, но НЕ исполняется. Новые генераторы добавлять
файлом g<id>.py с функцией generate_task().
"""
import importlib

_cache = {}


def get_generator(gen_id):
    """Функция generate_task для генератора gen_id.

    ModuleNotFoundError — если файла нет; AttributeError — если в модуле
    отсутствует generate_task (как у legacy-генератора id=2).
    """
    fn = _cache.get(gen_id)
    if fn is None:
        mod = importlib.import_module(f'.g{gen_id}', __name__)
        fn = mod.generate_task
        _cache[gen_id] = fn
    return fn
