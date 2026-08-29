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
import secrets
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

# Игра живёт внутри раздела игр, значит и правила доступа у неё те же.
# Зависимость от games намеренная: иначе прямой адрес был бы чёрным ходом
# мимо флага games_enabled и личного can_play_games.
from games.views import games_section_required
from games.utils import display_for_games

from . import engine
from .models import QuoridorGame


OPEN_GAMES_LIMIT = 5      # сколько партий один человек вправе держать в ожидании


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

    # Свободным может быть любое из двух мест: создатель выбирает цвет сам,
    # так что ждать соперника может и синий.
    open_games = QuoridorGame.objects.filter(
        Q(status=QuoridorGame.STATUS_WAITING)
        & (Q(red_player__isnull=True) | Q(blue_player__isnull=True))
    ).exclude(red_player=user).exclude(blue_player=user).order_by('-created_at')[:10]

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
def game_create(request):
    """
    Выбор цвета, а затем создание партии.

    Цвет решает не только внешний вид: красный ходит первым, и в «Заборах»
    это заметное преимущество. Поэтому сначала спрашиваем, а не сажаем молча.
    """
    # Брошенные партии копятся в лобби и мешают всем остальным, поэтому
    # больше пяти неначатых партий одновременно держать нельзя.
    pending = QuoridorGame.objects.filter(
        Q(red_player=request.user) | Q(blue_player=request.user),
        status=QuoridorGame.STATUS_WAITING,
    ).count()

    if request.method != 'POST':
        return render(request, 'quoridor/new.html', {
            'asset_v': asset_version(),
            'pending': pending,
            'limit': OPEN_GAMES_LIMIT,
        })

    if pending >= OPEN_GAMES_LIMIT:
        return render(request, 'quoridor/new.html', {
            'asset_v': asset_version(),
            'pending': pending,
            'limit': OPEN_GAMES_LIMIT,
            'error': 'Слишком много партий ждут соперника. Закройте лишние — '
                     'кнопкой «Отменить партию» на их страницах.',
        }, status=400)

    side = request.POST.get('side')
    if side == 'random':
        side = secrets.choice([engine.RED, engine.BLUE])
    elif side not in (engine.RED, engine.BLUE):
        side = engine.RED

    game = QuoridorGame.create_for(request.user, side)
    return redirect('quoridor:game', code=game.code)


@login_required
@games_section_required
def game_detail(request, code):
    """Страница сетевой партии."""
    game = get_object_or_404(QuoridorGame, code=code)
    side = game.player_side(request.user)
    return render(request, 'quoridor/online.html', {
        'game': game,
        'my_side': side or '',
        'can_join': game.can_seat(request.user),
        'free_side': game.free_side() or '',
        'red_label': game.label_for(engine.RED),
        'blue_label': game.label_for(engine.BLUE),
        'asset_v': asset_version(),
    })


@never_cache
@login_required
@games_section_required
@require_POST
def game_join(request, code):
    """
    Занять свободное место в партии.

    Место занимается в транзакции с блокировкой строки: иначе два человека,
    открывшие ссылку одновременно, оба увидели бы «место свободно» и второй
    затёр бы первого.

    Отвечает либо редиректом (обычная форма — запасной путь на случай, когда
    JS не работает), либо состоянием партии, если попросили JSON: страница
    сажает гостя сама, как только он открыл ссылку.
    """
    user = request.user
    with transaction.atomic():
        game = get_object_or_404(
            QuoridorGame.objects.select_for_update(), code=code
        )
        took = game.seat(user)
        if took:
            game.save(update_fields=['red_player', 'blue_player',
                                     'status', 'updated_at'])
        payload = _state_payload(game, user)

    if request.headers.get('X-Requested-With') == 'fetch':
        payload['ok'] = True
        payload['took'] = took or ''
        return JsonResponse(payload)
    return redirect('quoridor:game', code=code)


@never_cache
@login_required
@games_section_required
@require_POST
def game_resign(request, code):
    """
    Уйти из партии: до первого хода — освободить место, дальше — сдаться.

    Уход — такое же событие партии, как ход: он попадает в last_move, и второй
    игрок узнаёт о нём обычным опросом, ничего не обновляя руками.
    """
    user = request.user
    with transaction.atomic():
        game = get_object_or_404(
            QuoridorGame.objects.select_for_update(), code=code
        )
        side = game.player_side(user)
        if side is None:
            return JsonResponse({'error': 'Вы не участник этой партии.'}, status=403)

        outcome = game.resign(side)
        if outcome is None:
            return JsonResponse({'error': 'Эта партия уже закончена.'}, status=400)
        game.save()
        payload = _state_payload(game, user)

    payload['ok'] = True
    payload['outcome'] = outcome      # 'left' | 'cancel' | 'resign'
    return JsonResponse(payload)


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
        'can_seat': game.can_seat(user),
        'free_side': game.free_side() or '',
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


@never_cache
@login_required
@games_section_required
def game_state(request, code):
    """Опрос состояния партии."""
    game = get_object_or_404(QuoridorGame, code=code)
    return JsonResponse(_state_payload(game, request.user))


@never_cache
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
