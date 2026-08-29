# -*- coding: utf-8 -*-
"""
quoridor/views.py

Игра целиком живёт в браузере: правила, бот и отрисовка — на клиенте.
Серверу тут делать нечего, поэтому ни моделей, ни миграций у приложения нет.
Если однажды понадобится игра по сети, добавится модель партии — по образцу
приложения games.
"""

import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Игра живёт внутри раздела игр, значит и правила доступа у неё те же.
# Зависимость от games намеренная: иначе прямой адрес /games/zabory/ был бы
# чёрным ходом мимо флага games_enabled и личного can_play_games.
from games.views import games_section_required


def asset_version():
    """
    Версия для ссылок на статику: в разработке меняется, в проде пустая.
    Иначе браузер кэширует JS и правки молча не применяются.
    """
    return str(int(time.time())) if settings.DEBUG else ''


@login_required
@games_section_required
def play(request):
    return render(request, 'quoridor/play.html', {'asset_v': asset_version()})
