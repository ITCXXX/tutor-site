# -*- coding: utf-8 -*-
"""Утилиты раздела игр."""


def display_for_games(user):
    """Имя игрока для UI: gamer_nickname, либо username."""
    nick = (getattr(user, 'gamer_nickname', '') or '').strip()
    if nick:
        return nick
    return user.username
