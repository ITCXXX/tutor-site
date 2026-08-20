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


async def recv(c):
    """Следующее содержательное сообщение клиента.

    Сервер вместе с правкой рассылает ещё и запись в общую историю доски
    (action='history'). Проверкам она не нужна, но если её не вычитывать, она
    остаётся в очереди и сдвигает все последующие ожидания на шаг — проверки
    начинают ложно падать. Поэтому такие кадры здесь пропускаем.
    """
    while True:
        m = await c.receive_json_from()
        if m.get('action') != 'history':
            return m


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
    init1 = await recv(c1)
    check(init1['action'] == 'init' and init1['elements'] == [], 'учитель получил пустой init')

    conn2, _ = await c2.connect()
    check(conn2, 'ученик подключился')
    init2 = await recv(c2)
    check(init2['action'] == 'init', 'ученик получил init')

    # Учитель должен увидеть presence-join ученика.
    pres = await recv(c1)
    check(pres['action'] == 'presence' and pres['event'] == 'join', 'учитель видит вход ученика')

    # Учитель рисует элемент → ученик должен получить element_add.
    el = {'id': 'abc', 'type': 'rect', 'z': 0,
          'data': {'x': 10, 'y': 20, 'width': 100, 'height': 50, 'stroke': '#000', 'strokeWidth': 3}}
    await c1.send_json_to({'action': 'element_add', 'element': el})
    got = await recv(c2)
    check(got['action'] == 'element_add' and got['element']['id'] == 'abc', 'ученик получил элемент учителя')

    # Элемент сохранён в БД.
    saved = await BoardElement.objects.filter(board=b, element_id='abc').acount()
    check(saved == 1, 'элемент сохранён в БД')

    # Курсор учителя → ученику.
    await c1.send_json_to({'action': 'cursor', 'x': 5, 'y': 6})
    cur = await recv(c2)
    check(cur['action'] == 'cursor' and cur['x'] == 5, 'курсор учителя дошёл до ученика')

    # Новый клиент при подключении получает уже нарисованный элемент.
    c3 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c3.scope['user'] = teacher
    await c3.connect()
    init3 = await recv(c3)
    check(init3['action'] == 'init' and len(init3['elements']) == 1,
          'новый клиент получил существующий элемент в init')

    # Подключение c3 разослало presence-join — вычитаем его у c1 и c2,
    # чтобы он не «съел» очередь перед проверкой удаления ниже.
    await recv(c1)
    await recv(c2)

    # Удаление.
    await c1.send_json_to({'action': 'element_delete', 'id': 'abc'})
    deln = await recv(c2)
    check(deln['action'] == 'element_delete' and deln['id'] == 'abc', 'удаление дошло до ученика')
    gone = await BoardElement.objects.filter(board=b, element_id='abc').acount()
    check(gone == 0, 'элемент удалён из БД')

    # Встроенные страницы: в базу должны попадать только обычные веб-адреса.
    # Адрес вида javascript:… выполнился бы в браузере других участников от
    # имени нашего сайта, поэтому сервер обязан отсекать такие элементы сам,
    # не полагаясь на проверку в интерфейсе.
    async def embed_saved(url, eid):
        await c1.send_json_to({'action': 'element_add', 'element': {
            'id': eid, 'type': 'embed', 'z': 0, 'data': {'x': 0, 'y': 0, 'url': url}}})
        await asyncio.sleep(0.2)
        return await BoardElement.objects.filter(board=b, element_id=eid).acount()

    check(await embed_saved('javascript:alert(1)', 'emb1') == 0, 'встроенная страница: javascript: отвергнут')
    check(await embed_saved('data:text/html,x', 'emb2') == 0, 'встроенная страница: data: отвергнут')
    check(await embed_saved(12345, 'emb3') == 0, 'встроенная страница: нестроковый адрес отвергнут')
    check(await embed_saved('https://example.org/', 'emb4') == 1, 'встроенная страница: обычная ссылка принята')
    # Принятый элемент разошёлся ученику — вычитываем и добавление, и удаление,
    # иначе эти сообщения сдвинут очередь следующим проверкам.
    await recv(c2)
    await c1.send_json_to({'action': 'element_delete', 'id': 'emb4'})
    await recv(c2)

    # Владелец убирает ученика с доски.
    await c1.send_json_to({'action': 'member_remove', 'target': student.pk})
    ev = await recv(c2)
    check(ev['action'] == 'members_update' and ev['kicked']
          and ev['target'] == str(student.pk), 'убранный получил уведомление')
    ev = await recv(c1)
    check(ev['action'] == 'members_update'
          and [p['id'] for p in ev['removed']] == [str(student.pk)],
          'владелец видит ученика в списке убранных')

    # Войти заново нельзя — иначе кнопка «Убрать» была бы бесполезной.
    c5 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c5.scope['user'] = student
    conn5, _ = await c5.connect()
    check(not conn5, 'убранный не может подключиться заново')

    # Владелец возвращает доступ — и ученик снова входит.
    await c1.send_json_to({'action': 'member_restore', 'target': student.pk})
    ev = await recv(c1)
    check(ev['action'] == 'members_update' and ev['removed'] == [],
          'список убранных очистился')
    c6 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c6.scope['user'] = student
    conn6, _ = await c6.connect()
    check(conn6, 'возвращённый снова подключается')
    if conn6:
        await c6.disconnect()

    # Ученик не может убрать никого — это право только владельца.
    c7 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c7.scope['user'] = student
    await c7.connect()
    await recv(c7)  # init
    await c7.send_json_to({'action': 'member_remove', 'target': teacher.pk})
    await b.arefresh_from_db()
    check(list(b.banned or []) == [], 'ученик не смог убрать владельца')
    await c7.disconnect()

    # Доступ постороннего отклоняется.
    outsider = await U.objects.acreate(username='_vrt_outsider', role='student')
    c4 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c4.scope['user'] = outsider
    conn4, code4 = await c4.connect()
    check(not conn4, 'посторонний НЕ подключился (нет доступа)')

    # Голосовая связь: сервер только ПЕРЕСЫЛАЕТ служебные сообщения, которыми
    # браузеры «знакомятся». Проверяем на паре свежих соединений.
    c8 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c8.scope['user'] = teacher
    await c8.connect()
    init8 = await recv(c8)
    # Ученика делаем НАБЛЮДАТЕЛЕМ: правки ему запрещены, а голосовать он должен.
    b.default_role = 'viewer'
    await b.asave(update_fields=['default_role'])

    c9 = WebsocketCommunicator(app, '/ws/board/vrt123/')
    c9.scope['user'] = student
    await c9.connect()
    init9 = await recv(c9)
    check(bool(init8.get('peer')) and init8['peer'] != init9.get('peer'),
          'у каждого соединения свой голосовой id')
    await recv(c8)  # presence о входе c9

    # ── Голосование ────────────────────────────────────────────────────────
    await c8.send_json_to({'action': 'element_add', 'element': {
        'id': 'poll1', 'type': 'poll', 'z': 0,
        'data': {'x': 0, 'y': 0, 'options': ['да', 'нет'], 'votes': {}}}})
    await recv(c9)

    # Наблюдатель НЕ может править доску...
    await c9.send_json_to({'action': 'element_add', 'element': {
        'id': 'nope', 'type': 'rect', 'z': 0, 'data': {'x': 0, 'y': 0}}})
    await asyncio.sleep(0.2)
    check(await BoardElement.objects.filter(board=b, element_id='nope').acount() == 0,
          'наблюдателю правки запрещены')

    # ...но голосовать может.
    await c9.send_json_to({'action': 'poll_vote', 'id': 'poll1', 'choice': 1})
    await recv(c8)
    row = await BoardElement.objects.filter(board=b, element_id='poll1').afirst()
    check((row.data.get('votes') or {}) == {str(student.pk): 1}, 'наблюдатель проголосовал')

    # Голос записывается ТОЛЬКО за себя: чужой ключ подделать нечем.
    check(list((row.data.get('votes') or {}).keys()) == [str(student.pk)],
          'записан только собственный голос')

    # Несуществующий вариант отвергаем.
    await c9.send_json_to({'action': 'poll_vote', 'id': 'poll1', 'choice': 99})
    await asyncio.sleep(0.2)
    row = await BoardElement.objects.filter(board=b, element_id='poll1').afirst()
    check((row.data.get('votes') or {}) == {str(student.pk): 1}, 'несуществующий вариант отвергнут')

    # Повторный голос заменяет прежний, а не добавляется.
    await c9.send_json_to({'action': 'poll_vote', 'id': 'poll1', 'choice': 0})
    await recv(c8)
    row = await BoardElement.objects.filter(board=b, element_id='poll1').afirst()
    check((row.data.get('votes') or {}) == {str(student.pk): 0}, 'переголосование заменяет голос')

    # Итоги нельзя переписать обычной правкой объекта. Голоса меняет только
    # действие poll_vote; element_update их не трогает, даже от редактора.
    await c8.send_json_to({'action': 'element_update', 'element': {
        'id': 'poll1', 'type': 'poll', 'z': 0,
        'data': {'x': 5, 'y': 5, 'options': ['да', 'нет'],
                 'votes': {'901': 0, '902': 0, '903': 0}}}})
    await recv(c9)   # правка разошлась — вычитываем, чтобы не сдвинуть очередь
    row = await BoardElement.objects.filter(board=b, element_id='poll1').afirst()
    check((row.data.get('votes') or {}) == {str(student.pk): 0},
          'итоги голосования нельзя подделать правкой объекта')
    check(round(row.data.get('x') or 0) == 5,
          'при этом остальные поля объекта правятся как обычно')

    # Тип существующего объекта менять нельзя. Через это обходилась защита
    # голосов: правка под видом другого типа проносила поддельные итоги, а
    # следующая правка возвращала тип обратно.
    await c8.send_json_to({'action': 'element_update', 'element': {
        'id': 'poll1', 'type': 'card', 'z': 0,
        'data': {'x': 7, 'y': 7, 'options': ['да', 'нет'],
                 'votes': {'801': 1, '802': 1}}}})
    await recv(c9)
    row = await BoardElement.objects.filter(board=b, element_id='poll1').afirst()
    check(row.type == 'poll', 'тип существующего объекта сменить нельзя')
    check((row.data.get('votes') or {}) == {str(student.pk): 0},
          'подмена типа не проносит поддельные итоги')

    b.default_role = 'editor'
    await b.asave(update_fields=['default_role'])

    await c8.send_json_to({'action': 'rtc', 'kind': 'ready', 'to': None, 'data': None})
    got = await recv(c9)
    check(got.get('action') == 'rtc' and got.get('kind') == 'ready'
          and got.get('peer') == init8['peer'] and got.get('to') is None,
          'общий вызов «я в разговоре» дошёл до собеседника')

    await c9.send_json_to({'action': 'rtc', 'kind': 'offer', 'to': init8['peer'],
                           'data': {'type': 'offer', 'sdp': 'v=0'}})
    got = await recv(c8)
    check(got.get('kind') == 'offer' and got.get('to') == init8['peer']
          and (got.get('data') or {}).get('sdp') == 'v=0',
          'адресное сообщение дошло и сохранило адресата')

    # Слишком большое сообщение отбрасываем: канал доски общий с рисованием.
    await c9.send_json_to({'action': 'rtc', 'kind': 'offer', 'to': init8['peer'],
                           'data': {'sdp': 'x' * 70000}})
    await c8.send_json_to({'action': 'rtc', 'kind': 'ready', 'to': None, 'data': None})
    got = await recv(c9)
    check(got.get('kind') == 'ready', 'раздутое служебное сообщение отброшено')

    await c8.disconnect(); await c9.disconnect()

    for c in (c1, c2, c3):
        try:
            await c.disconnect()
        except Exception:
            pass

    # Чистка.
    await BoardElement.objects.filter(board=b).adelete()
    await b.adelete()
    await U.objects.filter(username__startswith='_vrt_').adelete()

    print('\nИТОГ:', 'ВСЁ РАБОТАЕТ ✅' if ok else 'ЕСТЬ ПРОБЛЕМЫ ❌')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
