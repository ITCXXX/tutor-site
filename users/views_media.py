# -*- coding: utf-8 -*-
"""Проверка права на скачивание загруженных файлов.

Каталог media/ отдаёт nginx напрямую, минуя Django — так быстрее, и для обложек
курсов это правильно. Но там же лежат методические материалы и сданные учениками
работы: их мог скачать кто угодно, зная или подобрав адрес, а проверка на
странице материала при этом просто обходилась стороной.

Чтобы не переписывать все ссылки в шаблонах, спрашиваем разрешение через
auth_request: nginx перед выдачей приватного файла дёргает этот адрес, а мы
отвечаем 200 (можно) или 403 (нельзя). Сам файл по-прежнему отдаёт nginx.

Правило доступа к материалам — ровно то же, что на странице материала
(users/views_materials.py): бесплатные видны всем, платные — только вошедшим.
Иначе получилось бы, что через прямую ссылку доступно больше, чем через сайт.
"""
from urllib.parse import unquote, urlparse

from django.http import HttpResponse, HttpResponseForbidden

from .models import Material, StudentSubmission


def _requested_path(request):
    """Путь запрошенного файла относительно MEDIA_ROOT.

    nginx кладёт исходный адрес в X-Original-URI. Значение приходит снаружи,
    поэтому обращаемся с ним как с недоверенным: отрезаем запрос и якорь,
    раскодируем и убираем «..», чтобы нельзя было выйти за media/.
    """
    uri = request.META.get('HTTP_X_ORIGINAL_URI', '')
    path = unquote(urlparse(uri).path or '')
    prefix = '/media/'
    if not path.startswith(prefix):
        return ''
    rel = path[len(prefix):]
    if not rel or '..' in rel.split('/'):
        return ''
    return rel


def media_guard(request):
    """Отвечает nginx-у, можно ли отдать файл. Тело ответа не используется."""
    rel = _requested_path(request)
    if not rel:
        return HttpResponseForbidden('bad path')
    user = request.user

    # Сданные работы: своё видит ученик, чужое — только преподаватель.
    if rel.startswith('hw/submissions/'):
        if not user.is_authenticated:
            return HttpResponseForbidden('login required')
        if user.is_superuser or getattr(user, 'role', '') == 'teacher':
            return HttpResponse('ok')
        owns = StudentSubmission.objects.filter(student=user, file=rel).exists()
        return HttpResponse('ok') if owns else HttpResponseForbidden('not yours')

    # Методические материалы: как на странице материала.
    if rel.startswith('materials/files/'):
        material = Material.objects.filter(file=rel).only('is_free').first()
        if material is None:
            # Файла нет в базе — значит он осиротел. Отдавать такое незачем.
            return HttpResponseForbidden('unknown file')
        if material.is_free:
            return HttpResponse('ok')
        return (HttpResponse('ok') if user.is_authenticated
                else HttpResponseForbidden('login required'))

    # Всё прочее (обложки курсов, картинки заданий, файлы досок) не приватно:
    # nginx их сюда и не присылает, но на случай ошибки в конфиге — разрешаем.
    return HttpResponse('ok')
