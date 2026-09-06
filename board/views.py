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
import shutil
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
# Потолок на доску целиком. Диск сервера — 15 ГБ, и на нём же живёт база, так
# что без потолка десяток досок со сканами учебников выбирает всё место, а
# кончившееся место роняет весь сайт, а не только загрузку.
# Потолок по ЧИСЛУ файлов почти ничего не защищал: место на диске съедают
# мегабайты, а не количество, и его сторожит _BOARD_BYTES_MAX ниже. Зато счётчик
# упирался первым — курс из тридцати занятий, где каждую задачу приносят
# фотографией, выбирал шестьдесят штук за месяц, и доска молча переставала
# принимать файлы прямо посреди урока.
#
# Настоящее лекарство не в цифре, а ниже — в _ужать_картинку(): фотография с
# телефона весит 3–12 МБ при четырёх тысячах пикселей по стороне, а на доске её
# показывают в восемьсот. После сжатия те же 150 МБ вмещают примерно вдесятеро
# больше файлов, и в число упереться станет незачем.
_BOARD_FILES_MAX = 400              # файлов на одну доску
# 150 МБ: досок у одного человека может быть до 50 (Board.MAX_PER_OWNER), и
# каждую можно скопировать вместе с файлами — потолок повыше в пределе съел бы
# весь диск. Это защита от накопления и оплошности, а не от злого умысла:
# аккаунты здесь заводятся вручную.
_BOARD_BYTES_MAX = 150 * 1024 * 1024

# Версия клиента доски. Берём из времени последней правки его файлов, а не пишем
# руками: тогда при любом изменении сама меняется и метка в адресе (?v=…),
# и подпись в углу доски. Браузер видит новый адрес и подтягивает свежий файл —
# ученик не остаётся со старой версией из кеша, а забыть «поднять номер» нельзя.
# ФАЙЛОВ ТЕПЕРЬ НЕСКОЛЬКО, и это важно. Пока клиент был одним board.js, метки
# хватало с него. Как только рядом появился smartdraw.js, правка ТОЛЬКО в нём
# метку бы не сдвинула — адрес остался бы прежним, и ученик сидел бы со старым
# распознаванием из кеша, пока не почистит браузер. Поэтому берём самое позднее
# время правки по всему списку.
_BOARD_FILES = [
    os.path.join(settings.BASE_DIR, 'static', 'board', name)
    for name in ('board.js', 'smartdraw.js')
]


# ── Сжатие картинок при загрузке ────────────────────────────────────────────
# Фотография с телефона — это 3–12 МБ и четыре тысячи пикселей по стороне. На
# доске её показывают в семьсот-восемьсот, и даже при сильном увеличении больше
# двух тысяч не нужно. Разница в весе — раз в десять, и именно она упирала доску
# в потолок за месяц занятий.
_КАРТИНКИ_СЖИМАЕМ = {'.jpg', '.jpeg', '.png'}
_МАКС_СТОРОНА = 2200        # пикселей; при зуме доски этого хватает с запасом
_КАЧЕСТВО = 82              # на глаз неотличимо от исходного, вес втрое меньше
_НЕ_ТРОГАТЬ_МЕНЬШЕ = 300 * 1024   # мелочь ужимать незачем, только портить


def _ужать_картинку(путь, ext, исходный_размер):
    """Уменьшить и пережать картинку на месте. Возвращает (имя, размер).

    ЧТО НЕ ТРОГАЕМ И ПОЧЕМУ:
      • PDF — там страницы, а не пиксели, и сжимать их отдельная история;
      • GIF — может быть анимацией, и пережатие её убьёт;
      • картинки с прозрачностью — прозрачность на доске значащая (вырезанный
        чертёж поверх клетчатого фона), а JPEG её не умеет: станет чёрный квадрат;
      • всё мельче 300 КБ — выигрыш копеечный, риск испортить настоящий.

    ЛЮБАЯ ОШИБКА — оставляем оригинал. Пользователь принёс файл на урок; потерять
    его из-за неудачного сжатия гораздо хуже, чем не сэкономить место.
    """
    if ext not in _КАРТИНКИ_СЖИМАЕМ or исходный_размер < _НЕ_ТРОГАТЬ_МЕНЬШЕ:
        return os.path.basename(путь), исходный_размер
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return os.path.basename(путь), исходный_размер

    try:
        with Image.open(путь) as im:
            # Поворот по метке EXIF: снятое боком фото иначе ляжет на доску
            # набок, и человек будет крутить головой.
            im = ImageOps.exif_transpose(im)
            прозрачность = (im.mode in ('RGBA', 'LA', 'P')
                            and 'transparency' in im.info) or im.mode in ('RGBA', 'LA')
            if прозрачность:
                return os.path.basename(путь), исходный_размер

            ш, в = im.size
            if max(ш, в) > _МАКС_СТОРОНА:
                k = _МАКС_СТОРОНА / float(max(ш, в))
                im = im.resize((max(1, int(ш * k)), max(1, int(в * k))),
                               Image.LANCZOS)
            if im.mode != 'RGB':
                im = im.convert('RGB')

            новое_имя = os.path.splitext(os.path.basename(путь))[0] + '.jpg'
            новый_путь = os.path.join(os.path.dirname(путь), новое_имя)
            im.save(новый_путь, 'JPEG', quality=_КАЧЕСТВО, optimize=True,
                    progressive=True)
    except Exception:
        # Битый файл, незнакомый формат, нехватка памяти — оригинал остаётся.
        return os.path.basename(путь), исходный_размер

    новый_размер = os.path.getsize(новый_путь)
    if новый_размер >= исходный_размер:
        # Пережали в плюс (так бывает с уже сжатыми картинками) — толку нет.
        if новый_путь != путь:
            try:
                os.remove(новый_путь)
            except OSError:
                pass
        return os.path.basename(путь), исходный_размер

    if новый_путь != путь:
        try:
            os.remove(путь)
        except OSError:
            pass
    return новое_имя, новый_размер


def board_client_version():
    """Короткая метка версии клиента доски, например 260820-1447."""
    времена = []
    for путь in _BOARD_FILES:
        try:
            времена.append(os.path.getmtime(путь))
        except OSError:
            pass  # файла нет (собранная статика) — не роняем страницу
    if not времена:
        return 'dev'
    return time.strftime('%y%m%d-%H%M', time.localtime(max(времена)))


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

    # Пароль доски. Пока он не введён в этом браузере, страница доски не
    # отдаётся вовсе — человек видит только окно ввода и даже не знает, что на
    # доске нарисовано. Раньше пароль спрашивали лишь у тех, кто ещё не в
    # участниках: достаточно было один раз войти по ссылке ДО того, как пароль
    # включили, — и он не спрашивался больше никогда.
    if not board.password_passed(user, request.session):
        error = ''
        if request.method == 'POST':
            if board.verify_password(request.POST.get('password')):
                # Пропуск живёт в сессии этого браузера и обесценивается сам,
                # как только владелец сменит пароль (см. Board.password_key).
                request.session['board_pw_' + board.code] = board.password_key()
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
    # password_set_at обязателен в списке: именно он служит пропуском в сессии.
    # Без него смена пароля не доезжала до базы, и старый пропуск продолжал
    # годиться — то есть сменить пароль было нельзя.
    board.save(update_fields=['password_hash', 'password_enabled', 'password_set_at', 'updated_at'])
    return JsonResponse({'ok': True, 'enabled': board.password_enabled})


@login_required
@require_POST
def board_delete(request, code):
    """Удалить доску навсегда (только владелец). Каскадно удалит элементы и историю."""
    board = get_object_or_404(Board, code=code)
    if board.owner_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({'error': 'Удалить может только владелец'}, status=403)
    code_to_drop = board.code
    board.delete()
    # Файлы за доской не удалялись никогда: сигналов удаления в проекте нет.
    # Копия доски получает собственные файлы (см. board_duplicate), поэтому
    # осиротить её этим нельзя.
    _drop_board_media(code_to_drop)
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
    # Наблюдателю копия не положена: иначе тот, кому доску дали «только
    # посмотреть», забирает себе весь разбор урока и становится его владельцем.
    if board.role_for(request.user) != Board.ROLE_EDITOR:
        return JsonResponse({'error': 'Копировать доску может только участник '
                                      'с правом правки'}, status=403)
    if Board.quota_left(request.user) <= 0:
        return JsonResponse({'error': 'Достигнут потолок в %d досок — удалите '
                                      'ненужную старую.' % Board.MAX_PER_OWNER}, status=400)
    new = Board.create_for(owner=request.user, title=(board.title or 'Доска') + ' (копия)')
    # Картинки и PDF копируем ФИЗИЧЕСКИ, а не ссылками на файлы оригинала:
    # иначе удаление исходной доски оставило бы копию с битыми картинками.
    src_dir = _board_media_dir(board.code)
    dst_dir = _board_media_dir(new.code)
    src_prefix = settings.MEDIA_URL + 'board/' + board.code + '/'
    els = []
    for e in board.elements.all():
        data = e.data
        url = data.get('url') if isinstance(data, dict) else None
        if url and src_dir and dst_dir and url.startswith(src_prefix):
            name = os.path.basename(url)
            src = os.path.join(src_dir, name)
            if os.path.isfile(src):
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src, os.path.join(dst_dir, name))
                data = dict(data)
                data['url'] = settings.MEDIA_URL + 'board/' + new.code + '/' + name
        els.append(BoardElement(board=new, element_id=e.element_id, type=e.type,
                                data=data, z_index=e.z_index, author=request.user))
    if els:
        BoardElement.objects.bulk_create(els)
    return JsonResponse({'ok': True, 'code': new.code})


def _board_media_dir(code):
    """Каталог с файлами доски. code приходит из адреса, поэтому берём только
    само имя папки — иначе подставленные «..» увели бы нас в чужой каталог."""
    safe = os.path.basename((code or '').strip())
    if not safe or safe in ('.', '..'):
        return None
    return os.path.join(settings.MEDIA_ROOT, 'board', safe)


def _board_files_usage(code):
    """Сколько файлов у доски и сколько они весят."""
    d = _board_media_dir(code)
    if not d or not os.path.isdir(d):
        return 0, 0
    n = total = 0
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            n += 1
            total += os.path.getsize(p)
    return n, total


def _drop_board_media(code):
    """Убрать каталог доски. Вызывается только при удалении самой доски."""
    d = _board_media_dir(code)
    if not d or not os.path.isdir(d):
        return
    # Страховка от ошибки в вычислении пути: удаляем только то, что лежит
    # внутри media/board/, и ничего выше.
    root = os.path.join(settings.MEDIA_ROOT, 'board')
    if os.path.commonpath([os.path.abspath(d), os.path.abspath(root)]) != os.path.abspath(root):
        return
    shutil.rmtree(d, ignore_errors=True)


@login_required
@require_POST
def board_upload(request, code):
    """Загрузка картинки или PDF на доску. Сохраняем в media/board/<code>/,
    возвращаем URL — его клиент кладёт в элемент image/pdf и синхронизирует по WS.
    Сам файл в БД не храним (только ссылку), поэтому доска остаётся лёгкой."""
    board = get_object_or_404(Board, code=code)
    if not board.can_access(request.user):
        raise Http404('Нет доступа к доске.')
    # Наблюдателю рисовать нельзя — значит и приносить на доску файлы тоже.
    # Клиент кнопку прячет, но на неё можно не смотреть, а слать запрос напрямую.
    if board.role_for(request.user) != Board.ROLE_EDITOR:
        return JsonResponse({'error': 'Только участники с правом правки могут '
                                      'загружать файлы'}, status=403)
    f = request.FILES.get('file')
    if f is None:
        return JsonResponse({'error': 'Файл не передан'}, status=400)
    if f.size > _UPLOAD_MAX:
        return JsonResponse({'error': 'Файл больше 30 МБ'}, status=400)
    used_n, used_b = _board_files_usage(board.code)
    if used_n >= _BOARD_FILES_MAX:
        return JsonResponse({'error': 'На доске уже %d файлов — это предел. '
                                      'Удалите ненужные или заведите новую доску.'
                                      % _BOARD_FILES_MAX}, status=400)
    if used_b + f.size > _BOARD_BYTES_MAX:
        # Говорим, сколько занято и сколько осталось: «превышен лимит» без цифр
        # человек читает как поломку и идёт спрашивать, а с цифрами сразу видно,
        # что делать — удалить пару сканов или завести новую доску.
        return JsonResponse({'error':
            'Файлы этой доски заняли бы больше %d МБ — это предел. '
            'Сейчас занято %.1f МБ в %d файлах.'
            % (_BOARD_BYTES_MAX // (1024 * 1024), used_b / 1048576.0, used_n)},
            status=400)
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

    # Ужимаем ПОСЛЕ записи, а не на лету: если что-то пойдёт не так, на диске
    # уже лежит целый оригинал, и человек не теряет фотографию.
    итог_имя, итог_размер = _ужать_картинку(dest, ext, f.size)
    if итог_имя != fname:
        rel = os.path.join('board', code, итог_имя)

    url = settings.MEDIA_URL + rel.replace('\\', '/')
    return JsonResponse({
        'url': url,
        'name': f.name,
        'size': итог_размер,
        'kind': 'pdf' if ext == '.pdf' else 'image',
    })
