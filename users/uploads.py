# -*- coding: utf-8 -*-
"""Проверка файлов, присылаемых учениками.

Отдельный модуль, потому что проверка нужна в двух местах — во вью и в самой
модели, — а правило должно быть одно. Складывать такое в views.py значит
однажды получить вторую копию, которая разойдётся с первой.
"""
import math
import os

from django.core.exceptions import ValidationError

# Только то, что преподаватель сможет ОТКРЫТЬ в браузере. .docx и .heic сюда
# намеренно не входят: ученик был бы уверен, что сдал, а посмотреть работу
# было бы нечем.
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf'}

# 15 МБ. Фотография страницы тетради — это 2-5 МБ, скан многостраничной работы
# редко больше десяти. Диск на сервере 15 ГБ и делится с базой.
MAX_BYTES = 15 * 1024 * 1024

# Первые байты настоящего файла. Расширение ничего не доказывает: переименовать
# что угодно во что угодно умеет любой школьник.
SIGNATURES = {
    '.jpg':  [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.png':  [b'\x89PNG\r\n\x1a\n'],
    '.gif':  [b'GIF87a', b'GIF89a'],
    '.pdf':  [b'%PDF-'],
    # WebP: RIFF, четыре байта длины, затем WEBP — проверяем особо.
    '.webp': [],
}


def _looks_like(head, ext):
    """Похоже ли начало файла на объявленный тип."""
    if ext == '.webp':
        return head[:4] == b'RIFF' and head[8:12] == b'WEBP'
    return any(head.startswith(sig) for sig in SIGNATURES.get(ext, []))


def validate_homework_file(f):
    """Проверить присланный файл. Бросает ValidationError с внятным текстом.

    Текст сообщения пишем для ученика, а не для журнала: он должен понять, что
    делать дальше, а не «загрузка не удалась».
    """
    if not f:
        return

    ext = os.path.splitext(getattr(f, 'name', '') or '')[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValidationError(
            'Можно прислать фотографию (JPG, PNG, WebP, GIF) или PDF. '
            'Формат «%s» мы показать не сможем.' % (ext or 'без расширения'))

    size = getattr(f, 'size', 0) or 0
    if size > MAX_BYTES:
        # Округляем ВВЕРХ: файл на байт больше предела иначе показывался бы
        # как «15.0 МБ, а можно до 15 МБ» — читается как противоречие.
        мб = math.ceil(size / 1048576 * 10) / 10
        raise ValidationError(
            'Файл великоват: %s МБ, а можно до %d МБ. '
            'Сфотографируйте с меньшим разрешением или сожмите PDF.'
            % (('%.1f' % мб).rstrip('0').rstrip('.'), MAX_BYTES // 1048576))
    if size == 0:
        raise ValidationError('Файл пустой — похоже, он не догрузился.')

    # Содержимое. Читаем начало и возвращаем указатель на место: файл после
    # нас ещё будут сохранять.
    try:
        pos = f.tell()
    except (AttributeError, OSError):
        pos = None
    head = f.read(16)
    if pos is not None:
        try:
            f.seek(pos)
        except (AttributeError, OSError):
            pass
    else:
        try:
            f.seek(0)
        except (AttributeError, OSError):
            pass

    if not _looks_like(head, ext):
        raise ValidationError(
            'Содержимое файла не похоже на %s. Если вы переименовали файл '
            'вручную, пришлите исходный — иначе его не откроет и преподаватель.'
            % ext.lstrip('.').upper())
