# -*- coding: utf-8 -*-
"""
games/views.py

Все view раздела игр. Доступ закрыт, если SiteSetting.games_enabled = False
(кроме суперпользователя). Игроки должны быть авторизованы и иметь флаг
User.can_play_games (либо быть суперпользователем).
"""

import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .engine import apply_move, ALL_VARIANTS, VARIANT_CLASSIC
from .models import Game, SiteSetting
from .utils import display_for_games


# ── Доступ ───────────────────────────────────────────────────────────────────

def _section_open(user):
    """Раздел игр в принципе доступен этому пользователю?
    Суперпользователь — всегда, остальные — если SiteSetting.games_enabled."""
    if user.is_authenticated and user.is_superuser:
        return True
    return SiteSetting.get().games_enabled


def _can_play(user):
    """Может ли пользователь играть (видеть и создавать партии)?
    Учитываем глобальный флаг раздела + личный can_play_games."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not _section_open(user):
        return False
    return bool(getattr(user, 'can_play_games', False))


def games_section_required(view_func):
    """Декоратор: 404 если раздел выключен; 403 если пользователю не выдан флаг.

    Должен идти ПОСЛЕ @login_required (тогда request.user уже аутентифицирован).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not _section_open(request.user):
            raise Http404
        if not _can_play(request.user):
            return HttpResponseForbidden('У вас нет доступа к разделу игр.')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Страницы ────────────────────────────────────────────────────────────────


@login_required
@games_section_required
def games_hub(request):
    """
    Единый вход в раздел игр: отсюда выбирают, во что играть.

    Раньше на /games/ сразу открывался список партий УТТТ. Игр стало две,
    и списку партий место внутри своей игры, а не на входе в раздел.
    Доступ у хаба тот же, что у всего раздела, — иначе выбор игр видели бы
    те, кому играть не разрешено.
    """
    return render(request, 'games/hub.html', {
        'display_name': display_for_games(request.user),
    })


@login_required
@games_section_required
def games_list(request):
    """Список своих партий + кнопка «Новая партия». Также форма ника, если он
    не задан — без ника создавать партии не имеет смысла."""
    user = request.user
    my_games = Game.objects.filter(
        Q(x_player=user) | Q(o_player=user)
    ).order_by('-updated_at')[:30]

    has_nickname = bool((user.gamer_nickname or '').strip())

    return render(request, 'games/games_list.html', {
        'my_games': my_games,
        'has_nickname': has_nickname,
        'nickname': user.gamer_nickname or '',
        'display_name': display_for_games(user),
    })


@login_required
@games_section_required
@require_POST
def game_create(request):
    """Создать новую партию. Параметры (опциональны):
       variant=classic|long, mode=online|local."""
    variant = request.POST.get('variant', VARIANT_CLASSIC)
    if variant not in ALL_VARIANTS:
        variant = VARIANT_CLASSIC
    is_local = (request.POST.get('mode') == 'local')
    game = Game.create_for(
        x_player=request.user,
        variant=variant,
        is_local=is_local,
    )
    return redirect('games:detail', code=game.code)


@login_required
@games_section_required
@require_POST
def game_rematch(request, code):
    """Создать партию-реванш на основе завершённой партии. Стороны меняются."""
    prev = get_object_or_404(Game, code=code)
    if prev.status != Game.STATUS_FINISHED:
        return redirect('games:detail', code=code)
    # Только участники могут просить реванш.
    if not prev.is_participant(request.user):
        return HttpResponseForbidden('Только участники могут запросить реванш.')
    new_game = prev.make_rematch(request.user)
    return redirect('games:detail', code=new_game.code)


@login_required
@games_section_required
def game_detail(request, code):
    """Страница партии: рисуется доска и подключается JS-polling."""
    game = get_object_or_404(Game, code=code)
    user = request.user

    side = game.player_side(user)
    can_join = (
        side is None
        and game.status == Game.STATUS_WAITING
        and game.o_player_id is None
        and game.x_player_id != user.id
    )

    return render(request, 'games/game_detail.html', {
        'game': game,
        'my_side': side,
        'can_join': can_join,
        'x_label': game.label_for('X'),
        'o_label': game.label_for('O'),
        'score_x': game.score_x,
        'score_o': game.score_o,
    })


@login_required
@games_section_required
@require_POST
def game_join(request, code):
    """Войти в партию вторым игроком (O)."""
    game = get_object_or_404(Game, code=code)
    user = request.user
    if game.status != Game.STATUS_WAITING or game.o_player_id is not None:
        return redirect('games:detail', code=code)
    if game.x_player_id == user.id:
        return redirect('games:detail', code=code)
    game.o_player = user
    game.status = Game.STATUS_ACTIVE
    game.save(update_fields=['o_player', 'status', 'updated_at'])
    return redirect('games:detail', code=code)


@login_required
@games_section_required
def game_state(request, code):
    """AJAX: вернуть текущее состояние партии. Используется polling-ом."""
    game = get_object_or_404(Game, code=code)
    user = request.user
    return JsonResponse({
        'code': game.code,
        'status': game.status,
        'current': game.current,
        'winner': game.winner,
        'next_local': game.next_local,
        'board': game.board,
        'big_board': game.big_board,
        'last_move': game.last_move,
        'my_side': game.player_side(user),
        'x_label': game.label_for('X'),
        'o_label': game.label_for('O'),
        'variant': game.variant,
        'is_local': game.is_local,
        'score_x': game.score_x,
        'score_o': game.score_o,
        'updated_at': game.updated_at.isoformat(),
    })


@login_required
@games_section_required
@require_POST
def game_move(request, code):
    """AJAX: сделать ход. Body = {"big": int, "small": int}."""
    game = get_object_or_404(Game, code=code)
    user = request.user
    side = game.player_side(user)
    if side is None:
        return JsonResponse({'error': 'Вы не участник этой партии.'}, status=403)
    if game.status != Game.STATUS_ACTIVE:
        return JsonResponse({'error': 'Партия не активна.'}, status=400)
    if side != game.current:
        return JsonResponse({'error': 'Сейчас не ваш ход.'}, status=400)

    try:
        data = json.loads(request.body or '{}')
        big = int(data.get('big'))
        small = int(data.get('small'))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Неверный формат хода.'}, status=400)

    new_state, err = apply_move(
        game.state_dict(), side, big, small, variant=game.variant,
    )
    if err:
        return JsonResponse({'error': err}, status=400)

    game.apply_state(new_state)
    game.save()
    return JsonResponse({
        'ok': True,
        'status': game.status,
        'current': game.current,
        'winner': game.winner,
        'next_local': game.next_local,
        'big_board': game.big_board,
        'board': game.board,
        'last_move': game.last_move,
        'score_x': game.score_x,
        'score_o': game.score_o,
    })


@login_required
@games_section_required
@require_POST
def set_nickname(request):
    """Обновить gamer_nickname текущего пользователя."""
    nick = (request.POST.get('nickname') or '').strip()
    if not nick:
        return redirect('games:list')
    if len(nick) > 30:
        nick = nick[:30]
    user = request.user
    user.gamer_nickname = nick
    user.save(update_fields=['gamer_nickname'])
    return redirect('games:list')
