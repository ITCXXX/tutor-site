# -*- coding: utf-8 -*-
"""
board/views.py

HTTP-страницы раздела досок. Сам realtime идёт по WebSocket (см. consumers.py);
здесь — только список досок, создание, вход по коду и рендер страницы-комнаты.

Доступ: любой авторизованный пользователь может создать доску и открыть свои.
Открыв чужую доску по коду-ссылке, пользователь автоматически становится её
участником (удобно для пары учитель↔ученик: дал код — зашли).
"""

import os
import secrets
import string
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Board, BoardElement
from .turn import ice_servers

# Разрешённые к загрузке файлы (картинки + PDF) и лимит размера.
_UPLOAD_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf'}  # .svg исключён: может нести скрипт
_UPLOAD_MAX = 30 * 1024 * 1024  # 30 МБ

# Версия клиента доски. Берём из времени последней правки board.js, а не пишем
# руками: тогда при любом изменении файла сама меняется и метка в адресе (?v=…),
# и подпись в углу доски. Браузер видит новый адрес и подтягивает свежий файл —
# ученик не остаётся со старой версией из кеша, а забыть «поднять номер» нельзя.
_BOARD_JS = os.path.join(settings.BASE_DIR, 'static', 'board', 'board.js')


def board_client_version():
    """Короткая метка версии клиента доски, например 260820-1447."""
    try:
        return time.strftime('%y%m%d-%H%M', time.localtime(os.path.getmtime(_BOARD_JS)))
    except OSError:
        return 'dev'  # файла нет (собранная статика) — не роняем страницу


def _elem_id():
    """Короткий id элемента (как у клиента — uuid-подобный)."""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(20))


def _seed_template(board, template):
    """Наполнить новую доску стартовыми элементами по выбранному шаблону.

    plane  — одно математическое окно с осями и сеткой (координатная плоскость);
    plane2 — два окна рядом (например, «было / стало»);
    остальное («blank») — пустая доска.
    """
    def frame(x, y, w, h, unit=40):
        return BoardElement(
            board=board, element_id=_elem_id(), type='frame', z_index=0,
            data={'x': x, 'y': y, 'width': w, 'height': h,
                  'cx': 0, 'cy': 0, 'unit': unit},
        )

    bulk = []
    if template == 'plane':
        bulk.append(frame(120, 90, 640, 460))
    elif template == 'plane2':
        bulk.append(frame(80, 90, 430, 460))
        bulk.append(frame(540, 90, 430, 460))
    if bulk:
        BoardElement.objects.bulk_create(bulk)


@login_required
def boards_list(request):
    """Мои доски (созданные мной + те, к которым присоединился) и форма входа по коду."""
    user = request.user
    # Показываем ВСЕ доски пользователя. Раньше список обрезался на 50 — доски
    # сверх этого молча пропадали из вида, хотя продолжали существовать.
    # Теперь ограничение стоит на СОЗДАНИИ (Board.MAX_PER_OWNER), поэтому своих
    # досок физически не может быть больше потолка, и обрезать нечего.
    boards = Board.objects.filter(
        Q(owner=user) | Q(members=user)
    ).distinct().order_by('-updated_at')
    return render(request, 'board/boards_list.html', {
        'boards': boards,
        'owned_count': Board.owned_count(user),
        'board_limit': Board.MAX_PER_OWNER,
        'quota_left': Board.quota_left(user),
    })


@login_required
@require_POST
def board_create(request):
    """Создать новую доску и сразу открыть её."""
    if Board.quota_left(request.user) <= 0:
        messages.error(request, (
            'Достигнут потолок в %d досок. Удалите ненужную старую доску '
            '(правая кнопка мыши по строке в списке → «Удалить»), '
            'и можно будет создать новую.' % Board.MAX_PER_OWNER
        ))
        return redirect('board:list')
    title = (request.POST.get('title') or '').strip()[:120]
    template = (request.POST.get('template') or 'blank').strip()
    board = Board.create_for(owner=request.user, title=title)
    _seed_template(board, template)
    return redirect('board:room', code=board.code)


@login_required
@require_POST
def board_join(request, code=None):
    """Войти в доску по коду (из формы списка)."""
    code = (code or request.POST.get('code') or '').strip()
    board = Board.objects.filter(code=code).first()
    if board is None:
        raise Http404('Доска с таким кодом не найдена.')
    return redirect('board:room', code=board.code)


@login_required
@ensure_csrf_cookie  # чтобы загрузка файлов (fetch) могла прислать CSRF-токен
def board_room(request, code):
    """Страница-комната: рисуется холст, JS подключается по WebSocket."""
    board = get_object_or_404(Board, code=code)
    user = request.user

    # Убранных владельцем не пускаем — и, что важно, не даём автоприсоединению
    # ниже молча вернуть их в участники при следующем открытии ссылки.
    if board.is_banned(user):
        return render(request, 'board/board_no_access.html', {'board': board}, status=403)

    # Пароль доски: спрашиваем только у новых (не владелец/участник/суперюзер).
    # Верный пароль присоединяет к доске — дальше вход как обычно.
    if board.needs_password(user):
        error = ''
        if request.method == 'POST':
            if board.verify_password(request.POST.get('password')):
                board.members.add(user)
                return redirect('board:room', code=board.code)
            error = 'Неверный пароль'
        return render(request, 'board/board_password.html', {'board': board, 'error': error})

    # Автоприсоединение по ссылке: не владелец и ещё не участник — добавляем.
    if (board.owner_id != user.id
            and not board.members.filter(pk=user.pk).exists()):
        board.members.add(user)

    return render(request, 'board/board_room.html', {
        'board': board,
        'is_owner': board.owner_id == user.id,
        'password_enabled': board.password_enabled,
        'board_ver': board_client_version(),
        # Папку со шрифтами pdf.js через {% static %} не получить (это каталог,
        # а не файл), поэтому адрес собираем здесь.
        'pdf_fonts_url': settings.STATIC_URL + 'vendor/pdfjs-3.11.174/standard_fonts/',
        # Серверы для голосовой связи. Пропуск к ретранслятору временный,
        # поэтому выдаётся здесь, а не лежит в статике.
        'ice_servers': ice_servers(user),
    })


@login_required
@require_POST
def board_rename(request, code):
    """Переименовать доску (только владелец)."""
    board = get_object_or_404(Board, code=code)
    if board.owner_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({'error': 'Переименовать может только владелец'}, status=403)
    board.title = (request.POST.get('title') or '').strip()[:120]
    board.save(update_fields=['title', 'updated_at'])
    return JsonResponse({'ok': True, 'title': board.title})


@login_required
@require_POST
def board_set_password(request, code):
    """Задать / сменить / снять пароль доски (только владелец). Пустое поле — снять."""
    board = get_object_or_404(Board, code=code)
    if board.owner_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({'error': 'Пароль может менять только владелец'}, status=403)
    board.set_password(request.POST.get('password'))
    board.save(update_fields=['password_hash', 'password_enabled', 'updated_at'])
    return JsonResponse({'ok': True, 'enabled': board.password_enabled})


@login_required
@require_POST
def board_delete(request, code):
    """Удалить доску навсегда (только владелец). Каскадно удалит элементы и историю."""
    board = get_object_or_404(Board, code=code)
    if board.owner_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({'error': 'Удалить может только владелец'}, status=403)
    board.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def board_leave(request, code):
    """Выйти из чужой доски (убрать себя из участников). Владелец выйти не может."""
    board = get_object_or_404(Board, code=code)
    if board.owner_id == request.user.id:
        return JsonResponse({'error': 'Владелец не может выйти — удалите доску'}, status=400)
    board.members.remove(request.user)
    return JsonResponse({'ok': True})


@login_required
@require_POST
def board_duplicate(request, code):
    """Сделать копию доски (со всем содержимым) — новым владельцем становится тот,
    кто дублирует. Удобно как «шаблон урока»."""
    board = get_object_or_404(Board, code=code)
    if not board.can_access(request.user):
        raise Http404('Нет доступа к доске.')
    if Board.quota_left(request.user) <= 0:
        return JsonResponse({'error': 'Достигнут потолок в %d досок — удалите '
                                      'ненужную старую.' % Board.MAX_PER_OWNER}, status=400)
    new = Board.create_for(owner=request.user, title=(board.title or 'Доска') + ' (копия)')
    els = [
        BoardElement(board=new, element_id=e.element_id, type=e.type,
                     data=e.data, z_index=e.z_index, author=request.user)
        for e in board.elements.all()
    ]
    if els:
        BoardElement.objects.bulk_create(els)
    return JsonResponse({'ok': True, 'code': new.code})


@login_required
@require_POST
def board_upload(request, code):
    """Загрузка картинки или PDF на доску. Сохраняем в media/board/<code>/,
    возвращаем URL — его клиент кладёт в элемент image/pdf и синхронизирует по WS.
    Сам файл в БД не храним (только ссылку), поэтому доска остаётся лёгкой."""
    board = get_object_or_404(Board, code=code)
    if not board.can_access(request.user):
        raise Http404('Нет доступа к доске.')
    f = request.FILES.get('file')
    if f is None:
        return JsonResponse({'error': 'Файл не передан'}, status=400)
    if f.size > _UPLOAD_MAX:
        return JsonResponse({'error': 'Файл больше 30 МБ'}, status=400)
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in _UPLOAD_EXT:
        return JsonResponse({'error': 'Неподдерживаемый тип файла'}, status=400)
    fname = secrets.token_hex(16) + ext
    rel = os.path.join('board', code, fname)
    dest = os.path.join(settings.MEDIA_ROOT, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as out:
        for chunk in f.chunks():
            out.write(chunk)
    url = settings.MEDIA_URL + rel.replace('\\', '/')
    return JsonResponse({
        'url': url,
        'name': f.name,
        'size': f.size,
        'kind': 'pdf' if ext == '.pdf' else 'image',
    })
