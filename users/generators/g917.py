# -*- coding: utf-8 -*-
"""№20 ОГЭ, тип 17: x²/(x − a) ≤ x.

Файл-обёртка: платформа исполняет генераторы из users/generators/g<id>.py,
а сама математика живёт в users/oge20_generators.py — там же, где её
проверяют самотесты. Здесь только вызов.
"""
from users.oge20_generators import as_task


def generate_task():
    return as_task(17)
