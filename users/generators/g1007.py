# -*- coding: utf-8 -*-
"""№22 ОГЭ, тип 7: гипербола с выколотой точкой, прямая y = m без общих точек.

Файл-обёртка: платформа исполняет генераторы из users/generators/g<id>.py,
а сама математика живёт в users/oge22_generators.py — там же, где её
проверяет oge22_setup/verify_oge22.py. Здесь только вызов.
"""
from users.oge22_generators import as_task


def generate_task():
    return as_task(7)
