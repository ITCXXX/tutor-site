# -*- coding: utf-8 -*-
"""
Ручная проверка realtime-доски без браузера.
Запуск:  venv/Scripts/python.exe board/_verify_realtime.py
Создаёт временные данные и удаляет их в конце.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutor_core.settings')
django.setup()

import asyncio
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

import board.routing
from board.models import Board, BoardElement

U = get_user_model()


async def main():
    app = URLRouter(board.routing.websocket_urlpatterns)

    # Временные пользователи и доска.
    teacher = await U.objects.acreate(username='_vrt_teacher', role='teacher')
    student = await U.objects.acreate(username='_vrt_student', role='student')
    b = await Board.objects.acreate(code='vrt123', owner=teacher, title='verify')
    await b.members.aadd(student)

    ok = True

    def check(cond, label):
        nonlocal ok
        print(('  ✅' if cond else '  ❌'), label)
        ok = ok and cond

    # Два клиента подключаются к одной комнате.
    c1 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c1.scope['user'] = teacher
    c2 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c2.scope['user'] = student

    conn1, _ = await c1.connect()
    check(conn1, 'учитель подключился')
    init1 = await c1.receive_json_from()
    check(init1['action'] == 'init' and init1['elements'] == [], 'учитель получил пустой init')

    conn2, _ = await c2.connect()
    check(conn2, 'ученик подключился')
    init2 = await c2.receive_json_from()
    check(init2['action'] == 'init', 'ученик получил init')

    # Учитель должен увидеть presence-join ученика.
    pres = await c1.receive_json_from()
    check(pres['action'] == 'presence' and pres['event'] == 'join', 'учитель видит вход ученика')

    # Учитель рисует элемент → ученик должен получить element_add.
    el = {'id': 'abc', 'type': 'rect', 'z': 0,
          'data': {'x': 10, 'y': 20, 'width': 100, 'height': 50, 'stroke': '#000', 'strokeWidth': 3}}
    await c1.send_json_to({'action': 'element_add', 'element': el})
    got = await c2.receive_json_from()
    check(got['action'] == 'element_add' and got['element']['id'] == 'abc', 'ученик получил элемент учителя')

    # Элемент сохранён в БД.
    saved = await BoardElement.objects.filter(board=b, element_id='abc').acount()
    check(saved == 1, 'элемент сохранён в БД')

    # Курсор учителя → ученику.
    await c1.send_json_to({'action': 'cursor', 'x': 5, 'y': 6})
    cur = await c2.receive_json_from()
    check(cur['action'] == 'cursor' and cur['x'] == 5, 'курсор учителя дошёл до ученика')

    # Новый клиент при подключении получает уже нарисованный элемент.
    c3 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c3.scope['user'] = teacher
    await c3.connect()
    init3 = await c3.receive_json_from()
    check(init3['action'] == 'init' and len(init3['elements']) == 1,
          'новый клиент получил существующий элемент в init')

    # Подключение c3 разослало presence-join — вычитаем его у c1 и c2,
    # чтобы он не «съел» очередь перед проверкой удаления ниже.
    await c1.receive_json_from()
    await c2.receive_json_from()

    # Удаление.
    await c1.send_json_to({'action': 'element_delete', 'id': 'abc'})
    deln = await c2.receive_json_from()
    check(deln['action'] == 'element_delete' and deln['id'] == 'abc', 'удаление дошло до ученика')
    gone = await BoardElement.objects.filter(board=b, element_id='abc').acount()
    check(gone == 0, 'элемент удалён из БД')

    # Доступ постороннего отклоняется.
    outsider = await U.objects.acreate(username='_vrt_outsider', role='student')
    c4 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c4.scope['user'] = outsider
    conn4, code4 = await c4.connect()
    check(not conn4, 'посторонний НЕ подключился (нет доступа)')

    await c1.disconnect(); await c2.disconnect(); await c3.disconnect()

    # Чистка.
    await BoardElement.objects.filter(board=b).adelete()
    await b.adelete()
    await U.objects.filter(username__startswith='_vrt_').adelete()

    print('\nИТОГ:', 'ВСЁ РАБОТАЕТ ✅' if ok else 'ЕСТЬ ПРОБЛЕМЫ ❌')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
