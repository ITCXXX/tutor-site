# -*- coding: utf-8 -*-
"""
quoridor/views.py

Две ветки игры:

  • локальная — вдвоём за одним экраном или против компьютера. Целиком в
    браузере, сервер не участвует, партии в базу не пишутся;
  • сетевая — партия живёт в базе, сервер авторитетен: правила проверяются
    здесь, в quoridor/engine.py, а клиент только рисует и опрашивает.

Устроено по образцу раздела games: короткий код для приглашения, опрос
состояния, ходы через POST. Доступ у всех страниц тот же, что у раздела игр.
"""

import json
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

# Игра живёт внутри раздела игр, значит и правила доступа у неё те же.
# Зависимость от games намеренная: иначе прямой адрес был бы чёрным ходом
# мимо флага games_enabled и личного can_play_games.
from games.views import games_section_required
from games.utils import display_for_games

from . import engine
from .models import QuoridorGame


def asset_version():
    """
    Версия для ссылок на статику: в разработке меняется, в проде пустая.
    Иначе браузер кэширует JS и правки молча не применяются.
    """
    return str(int(time.time())) if settings.DEBUG else ''


# ────────────────────────── страницы ──────────────────────────

@login_required
@games_section_required
def lobby(request):
    """Выбор режима и список своих сетевых партий."""
    user = request.user
    my_games = QuoridorGame.objects.filter(
        Q(red_player=user) | Q(blue_player=user)
    ).order_by('-updated_at')[:20]

    open_games = QuoridorGame.objects.filter(
        status=QuoridorGame.STATUS_WAITING, blue_player__isnull=True,
    ).exclude(red_player=user).order_by('-created_at')[:10]

    return render(request, 'quoridor/lobby.html', {
        'my_games': my_games,
        'open_games': open_games,
        'display_name': display_for_games(user),
        'asset_v': asset_version(),
    })


@login_required
@games_section_required
def play_local(request):
    """Локальная игра: вдвоём за экраном или против компьютера."""
    return render(request, 'quoridor/play.html', {'asset_v': asset_version()})


@login_required
@games_section_required
@require_POST
def game_create(request):
    game = QuoridorGame.create_for(red_player=request.user)
    return redirect('quoridor:game', code=game.code)


@login_required
@games_section_required
def game_detail(request, code):
    """Страница сетевой партии."""
    game = get_object_or_404(QuoridorGame, code=code)
    side = game.player_side(request.user)
    can_join = (
        side is None
        and game.status == QuoridorGame.STATUS_WAITING
        and game.blue_player_id is None
        and game.red_player_id != request.user.id
    )
    return render(request, 'quoridor/online.html', {
        'game': game,
        'my_side': side or '',
        'can_join': can_join,
        'red_label': game.label_for(engine.RED),
        'blue_label': game.label_for(engine.BLUE),
        'asset_v': asset_version(),
    })


@login_required
@games_section_required
@require_POST
def game_join(request, code):
    """
    Войти в партию вторым игроком.

    Занятие места идёт в транзакции с блокировкой строки: иначе два человека,
    открывшие ссылку одновременно, оба увидели бы «партия свободна» и второй
    затёр бы первого.
    """
    user = request.user
    with transaction.atomic():
        game = get_object_or_404(
            QuoridorGame.objects.select_for_update(), code=code
        )
        if game.blue_player_id is None and game.red_player_id != user.id \
                and game.status == QuoridorGame.STATUS_WAITING:
            game.blue_player = user
            game.status = QuoridorGame.STATUS_ACTIVE
            game.save(update_fields=['blue_player', 'status', 'updated_at'])
    return redirect('quoridor:game', code=code)


# ────────────────────────── обмен ──────────────────────────

def _state_payload(game, user):
    st = game.state or engine.initial_state()
    return {
        'code': game.code,
        'status': game.status,
        'state': st,
        'winner': game.winner,
        'last_move': game.last_move,
        'my_side': game.player_side(user) or '',
        'red_label': game.label_for(engine.RED),
        'blue_label': game.label_for(engine.BLUE),
        'paths': {
            engine.RED: engine.shortest_path(
                st['walls'], st['pawns'][engine.RED], st['goalRow'][engine.RED]),
            engine.BLUE: engine.shortest_path(
                st['walls'], st['pawns'][engine.BLUE], st['goalRow'][engine.BLUE]),
        },
        'updated_at': game.updated_at.isoformat(),
    }


@login_required
@games_section_required
def game_state(request, code):
    """Опрос состояния партии."""
    game = get_object_or_404(QuoridorGame, code=code)
    return JsonResponse(_state_payload(game, request.user))


@login_required
@games_section_required
@require_POST
def game_move(request, code):
    """
    Ход: {"kind": "move", "r": int, "c": int}
      или {"kind": "wall", "wr": int, "wc": int, "orient": "h"|"v"}.

    Правила проверяются здесь и только здесь. Клиенту не верим: он показывает
    подсказки, но решение о допустимости хода принимает сервер.
    """
    user = request.user
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат хода.'}, status=400)

    with transaction.atomic():
        game = get_object_or_404(
            QuoridorGame.objects.select_for_update(), code=code
        )
        side = game.player_side(user)
        if side is None:
            return JsonResponse({'error': 'Вы не участник этой партии.'}, status=403)
        if game.status != QuoridorGame.STATUS_ACTIVE:
            return JsonResponse({'error': 'Партия не активна.'}, status=400)

        state = game.state or engine.initial_state()
        if state.get('turn') != side:
            return JsonResponse({'error': 'Сейчас не ваш ход.'}, status=400)

        kind = data.get('kind')
        try:
            if kind == 'move':
                r, c = int(data['r']), int(data['c'])
                new_state, err = engine.apply_move(state, side, r, c)
                move = {'kind': 'move', 'side': side, 'r': r, 'c': c,
                        'name': engine.cell_name(r, c)}
            elif kind == 'wall':
                wr, wc = int(data['wr']), int(data['wc'])
                orient = data.get('orient')
                new_state, err = engine.apply_wall(state, side, wr, wc, orient)
                move = {'kind': 'wall', 'side': side, 'wr': wr, 'wc': wc,
                        'orient': orient, 'name': engine.wall_name(wr, wc, orient)}
            else:
                return JsonResponse({'error': 'Неизвестный вид хода.'}, status=400)
        except (KeyError, TypeError, ValueError):
            return JsonResponse({'error': 'Неверный формат хода.'}, status=400)

        if err:
            return JsonResponse({'error': err}, status=400)

        game.apply_state(new_state, move)
        game.save()
        payload = _state_payload(game, user)

    payload['ok'] = True
    return JsonResponse(payload)
