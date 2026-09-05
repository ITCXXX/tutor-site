# -*- coding: utf-8 -*-
"""№24 ОГЭ, сюжет 18: две высоты остроугольного треугольника, равные углы.

Файл-обёртка: платформа исполняет генераторы из users/generators/g<id>.py,
а условия, доказательства и чертежи живут в users/oge24_generators.py —
там же, где их проверяет oge24_setup/verify_oge24.py. Здесь только вызов.
"""
from users.oge24_generators import as_task


def generate_task():
    return as_task(18)
