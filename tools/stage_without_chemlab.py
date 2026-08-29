# -*- coding: utf-8 -*-
"""
Готовит tutor_core/settings.py и tutor_core/urls.py к коммиту без строк chemlab.

Зачем это нужно
---------------
Виртуальная химлаборатория живёт только на рабочей машине: каталог `chemlab/`
в репозиторий не входит. Но чтобы её открыть локально, приложение прописано в
INSTALLED_APPS и в корневых маршрутах. Закоммитишь эти две строки — на сервере
после `git pull` Django не найдёт модуль и не поднимется вообще ни одна
страница сайта, а не только лаборатория.

Как это устроено
----------------
Скрипт не трогает рабочую копию. Он берёт файл с диска, выбрасывает строки с
`chemlab` и кладёт результат прямо в индекс git через hash-object. Прошлый
подход — «испортить файл, добавить, вернуть обратно» — однажды уже оставил
после себя settings.py в неверной кодировке: сломаться посреди дела ему было
негде, а вот записать файл заново он мог как угодно. Здесь ломаться нечему:
на диске файл остаётся ровно тем же байт в байт.

Запуск из корня проекта, после обычного `git add` остальных файлов:

    venv\\Scripts\\python.exe tools\\stage_without_chemlab.py

Если каталог chemlab когда-нибудь попадёт в репозиторий, скрипт станет
безвредным: он честно скажет, что вычёркивать нечего.
"""

import os
import subprocess
import sys
import tempfile

PATHS = ['tutor_core/settings.py', 'tutor_core/urls.py']
MARK = b'chemlab'


def stage(path):
    with open(path, 'rb') as fh:
        raw = fh.read()
    lines = raw.split(b'\n')
    kept = [ln for ln in lines if MARK not in ln.lower()]

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.py')
    try:
        tmp.write(b'\n'.join(kept))
        tmp.close()
        # --path подсказывает git, по каким правилам чистить файл (у проекта
        # core.autocrlf=true, в репозитории строки должны кончаться на LF).
        sha = subprocess.run(
            ['git', 'hash-object', '-w', '--path', path, tmp.name],
            capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(
            ['git', 'update-index', '--add', '--cacheinfo',
             '100644,%s,%s' % (sha, path)], check=True)
    finally:
        os.unlink(tmp.name)

    dropped = len(lines) - len(kept)
    return dropped


def main():
    for path in PATHS:
        if not os.path.exists(path):
            sys.exit('нет файла %s — запускайте из корня проекта' % path)
        dropped = stage(path)
        print('%s: в индекс без %d строк(и) chemlab' % (path, dropped))

    # Последняя проверка: в индексе не должно остаться ни одного упоминания.
    for path in PATHS:
        blob = subprocess.run(['git', 'show', ':' + path],
                              capture_output=True, check=True).stdout
        if MARK in blob.lower():
            sys.exit('в индексе остался chemlab (%s) — коммит делать нельзя' % path)
    print('проверено: в индексе chemlab нет')


if __name__ == '__main__':
    main()
