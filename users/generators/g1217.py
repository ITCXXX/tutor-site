# -*- coding: utf-8 -*-
"""№23 ОГЭ, тип 17.

Файл-обёртка: платформа исполняет генераторы из users/generators/g<id>.py,
а математика живёт в users/oge23_generators.py — там же, где её проверяет
oge23_setup/verify_geom.py (по координатам). Здесь только вызов.
"""
from users.oge23_generators import as_task


def generate_task():
    return as_task(17)
