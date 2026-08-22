#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Дописывает в ЖИВОЙ конфиг nginx две вещи, которых там нет после certbot.

Зачем отдельный скрипт. deploy/nginx.conf.example — это образец, с которого
конфиг копируется при первой установке. Дальше certbot переписывает живой файл
под себя, и правки образца туда уже не попадают. Руками вставлять двадцать
строк в работающий сайт рискованно, поэтому вставляем скриптом: с резервной
копией, проверкой и откатом.

Что добавляется:
  1. Канонический адрес — всё с www уходит на голый домен. Django привязывает
     куку сессии к точному имени хоста, поэтому вход на www не действует на
     zenchenkoim.ru: человека снова встречает страница входа.
  2. Проверка прав на сданные работы и методические материалы. Django-часть уже
     на сервере (адрес /media-guard/), осталось научить nginx её спрашивать.

Запуск (под root):
    python3 /opt/tutor/deploy/apply_nginx_prod.py

Повторный запуск безопасен: уже вставленное не дублируется.
"""
import datetime
import io
import os
import shutil
import subprocess
import sys

CONF = '/etc/nginx/sites-available/tutor'

# ── что вставляем ────────────────────────────────────────────────────────

ANCHOR_ACME = """    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }
"""

CANONICAL = """
    # Канонический адрес — без www.
    # Django привязывает куку сессии к ТОЧНОМУ имени хоста, поэтому вход на
    # www.zenchenkoim.ru не действует на zenchenkoim.ru и наоборот: человека
    # снова встречает страница входа. Кнопка «копировать» на доске берёт адрес
    # из адресной строки как есть, так что преподаватель, сидящий на www,
    # раздаёт ученикам «другой» сайт, сам того не замечая.
    if ($host ~* ^www\\.(.+)$) {
        return 301 $scheme://$1$request_uri;
    }
"""

ANCHOR_MEDIA = """    location /media/ {
        alias /opt/tutor/media/;
"""

GUARD = """    # Сданные работы учеников и методические материалы — только по праву.
    # Спрашиваем разрешение у Django, а сам файл по-прежнему отдаёт nginx.
    # Правило то же, что на сайте: бесплатное всем, платное — вошедшим,
    # работу видит её автор и преподаватель.
    location = /media-guard/ {
        internal;
        proxy_pass http://unix:/run/tutor/tutor.sock;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header X-Original-URI $request_uri;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~ ^/media/(hw/submissions|materials/files)/ {
        auth_request /media-guard/;
        root /opt/tutor;
        # Приватное не кэшируем у посредников: иначе прокси отдаст файл
        # следующему, уже не спрашивая разрешения.
        expires -1;
        add_header Cache-Control "private, no-store" always;
        add_header X-Content-Type-Options "nosniff" always;
        error_page 401 403 = @media_denied;
    }
    location @media_denied {
        default_type text/plain;
        charset utf-8;
        return 403 "Нет доступа к этому файлу";
    }

"""


def main():
    if os.geteuid() != 0:
        print('Запускать под root: sudo python3 ' + __file__)
        return 1
    if not os.path.isfile(CONF):
        print('Не найден конфиг: ' + CONF)
        return 1

    src = io.open(CONF, encoding='utf-8').read()
    orig = src
    done, skipped = [], []

    # 1. Канонический адрес
    if 'www\\.(.+)$' in src or '^www\\.' in src:
        skipped.append('канонический адрес (уже есть)')
    elif ANCHOR_ACME in src:
        src = src.replace(ANCHOR_ACME, ANCHOR_ACME + CANONICAL, 1)
        done.append('канонический адрес: www → без www')
    else:
        print('ОШИБКА: не нашёл блок acme-challenge — конфиг не такой, как ожидалось.')
        return 1

    # 2. Проверка прав на приватные файлы
    if '/media-guard/' in src:
        skipped.append('проверка прав на файлы (уже есть)')
    elif ANCHOR_MEDIA in src:
        src = src.replace(ANCHOR_MEDIA, GUARD + ANCHOR_MEDIA, 1)
        done.append('проверка прав на сданные работы и материалы')
    else:
        print('ОШИБКА: не нашёл блок location /media/ — конфиг не такой, как ожидалось.')
        return 1

    for s in skipped:
        print('  пропущено: ' + s)
    if src == orig:
        print('Всё уже на месте, менять нечего.')
        return 0

    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    backup = '/root/tutor-nginx-%s.conf' % stamp
    shutil.copy2(CONF, backup)
    print('  резервная копия: ' + backup)

    io.open(CONF, 'w', encoding='utf-8').write(src)
    for s in done:
        print('  добавлено: ' + s)

    # Проверка. Не прошла — возвращаем как было, сайт не трогаем.
    check = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    if check.returncode != 0:
        shutil.copy2(backup, CONF)
        print('')
        print('nginx не принял конфиг — вернул как было. Вывод проверки:')
        print(check.stderr.strip())
        return 1
    print('  nginx -t: конфиг верный')

    reload_ = subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True, text=True)
    if reload_.returncode != 0:
        shutil.copy2(backup, CONF)
        subprocess.run(['systemctl', 'reload', 'nginx'])
        print('Перезагрузка nginx не удалась — вернул как было.')
        print(reload_.stderr.strip())
        return 1

    print('  nginx перечитал конфиг')
    print('')
    print('Готово. Проверить снаружи:')
    print('  curl -sI https://www.zenchenkoim.ru/ | head -1        (ждём 301)')
    print('  curl -sI https://zenchenkoim.ru/media/hw/submissions/x.pdf | head -1   (ждём 403)')
    print('')
    print('И что обновление сертификата не сломалось:')
    print('  certbot renew --dry-run')
    return 0


if __name__ == '__main__':
    sys.exit(main())
