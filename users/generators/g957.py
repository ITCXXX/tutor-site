# -*- coding: utf-8 -*-
"""№21 ОГЭ, тип 7: средняя скорость: две половины.

Файл-обёртка: платформа исполняет генераторы из users/generators/g<id>.py,
а сама математика живёт в users/oge21_generators.py — там же, где её
проверяет oge21_setup/verify_oge21.py. Здесь только вызов.
"""
from users.oge21_generators import as_task


def generate_task():
    return as_task(7)
