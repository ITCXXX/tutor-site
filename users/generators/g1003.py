# -*- coding: utf-8 -*-
"""№22 ОГЭ, тип 3: парабола ветвями вниз и убывающая прямая, ровно две точки.

Файл-обёртка: платформа исполняет генераторы из users/generators/g<id>.py,
а сама математика живёт в users/oge22_generators.py — там же, где её
проверяет oge22_setup/verify_oge22.py. Здесь только вызов.
"""
from users.oge22_generators import as_task


def generate_task():
    return as_task(3)
