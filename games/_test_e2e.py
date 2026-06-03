# -*- coding: utf-8 -*-
"""E2E-тесты раздела игр: classic + long + local + rematch.

Запуск:
    python manage.py shell -c "from games import _test_e2e; _test_e2e.run()"
"""

import json
from django.test import Client
from users.models import User
from games.models import Game, SiteSetting


HDR = {'HTTP_HOST': 'localhost'}


def _setup():
    ss = SiteSetting.get(); ss.games_enabled = True; ss.save()
    for username in ('_e2e_alice', '_e2e_bob'):
        User.objects.filter(username=username).delete()
    a = User.objects.create(username='_e2e_alice')
    a.set_password('x'); a.is_active = True; a.can_play_games = True
    a.gamer_nickname = 'Алиса'; a.save()
    b = User.objects.create(username='_e2e_bob')
    b.set_password('x'); b.is_active = True; b.can_play_games = True
    b.gamer_nickname = 'Боб'; b.save()
    return a, b


def run():
    a, b = _setup()
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        if cond:
            print(f"  [OK] {name}")
            ok += 1
        else:
            print(f"  [FAIL] {name}")
            fail += 1

    ca = Client(); ca.login(username='_e2e_alice', password='x')
    cb = Client(); cb.login(username='_e2e_bob', password='x')

    # 1. Классическая онлайн-партия
    r = ca.post('/games/new/', data={'variant': 'classic', 'mode': 'online'}, **HDR)
    chk("classic-create: 302", r.status_code == 302)
    g = Game.objects.filter(x_player=a).order_by('-id').first()
    chk("classic-create: variant=classic", g.variant == 'classic')
    chk("classic-create: not local", not g.is_local)
    chk("classic-create: status waiting", g.status == 'waiting')

    cb.post(f'/games/{g.code}/join/', **HDR)
    r = ca.post(f'/games/{g.code}/move/', data=json.dumps({'big': 4, 'small': 4}),
                content_type='application/json', **HDR)
    chk("classic-move: 200", r.status_code == 200)
    data = r.json()
    chk("classic-move: score_x=0", data['score_x'] == 0)

    # 2. Локальная партия
    r = ca.post('/games/new/', data={'variant': 'classic', 'mode': 'local'}, **HDR)
    local_g = Game.objects.filter(x_player=a, is_local=True).order_by('-id').first()
    chk("local-create: is_local True", local_g.is_local is True)
    chk("local-create: o = creator", local_g.o_player_id == a.id)
    chk("local-create: status active сразу", local_g.status == 'active')

    r = ca.post(f'/games/{local_g.code}/move/', data=json.dumps({'big': 4, 'small': 0}),
                content_type='application/json', **HDR)
    chk("local-move-X: 200", r.status_code == 200)
    r = ca.post(f'/games/{local_g.code}/move/', data=json.dumps({'big': 0, 'small': 4}),
                content_type='application/json', **HDR)
    chk("local-move-O: 200 (та же сессия за оба)", r.status_code == 200)
    local_g.refresh_from_db()
    chk("local: current=X после двух ходов", local_g.current == 'X')

    r = cb.post(f'/games/{local_g.code}/move/', data=json.dumps({'big': 4, 'small': 1}),
                content_type='application/json', **HDR)
    chk("local: чужой не может ходить (403)", r.status_code == 403)

    # 3. Long-партия
    r = ca.post('/games/new/', data={'variant': 'long', 'mode': 'local'}, **HDR)
    long_g = Game.objects.filter(x_player=a, variant='long').order_by('-id').first()
    chk("long-create: variant=long", long_g.variant == 'long')

    r = ca.get(f'/games/{long_g.code}/state/', **HDR)
    st = r.json()
    chk("long-state: variant", st.get('variant') == 'long')
    chk("long-state: is_local", st.get('is_local') is True)
    chk("long-state: score_x/o", 'score_x' in st and 'score_o' in st)

    # 4. Рематч
    fin_g = Game.create_for(a, variant='long', o_player=b)
    fin_g.status = Game.STATUS_FINISHED
    fin_g.winner = 'X'
    fin_g.save()
    r = ca.post(f'/games/{fin_g.code}/rematch/', **HDR)
    chk("rematch: 302", r.status_code == 302)
    rematch_g = Game.objects.filter(parent_game=fin_g).first()
    chk("rematch: создана", rematch_g is not None)
    chk("rematch: стороны поменялись (X=Боб, O=Алиса)",
        rematch_g.x_player_id == b.id and rematch_g.o_player_id == a.id)
    chk("rematch: вариант сохранён (long)", rematch_g.variant == 'long')
    chk("rematch: parent_game ссылается на fin_g",
        rematch_g.parent_game_id == fin_g.id)

    fin_g2 = Game.create_for(a, variant='classic', o_player=b)
    r = ca.post(f'/games/{fin_g2.code}/rematch/', **HDR)
    chk("rematch: для активной — редирект, без создания",
        r.status_code == 302 and Game.objects.filter(parent_game=fin_g2).count() == 0)

    # 5. Список игр
    r = ca.get('/games/', **HDR)
    body = r.content.decode('utf-8')
    chk("list: страница 200", r.status_code == 200)
    chk("list: форма с вариантом", 'Долгая дорога' in body)
    chk("list: hot-seat", 'Локально' in body)

    # Cleanup
    Game.objects.filter(code__in=[
        g.code, local_g.code, long_g.code,
        fin_g.code, rematch_g.code, fin_g2.code,
    ]).delete()
    a.delete()
    b.delete()

    print(f"\nИтого: {ok} OK, {fail} FAIL")
    return ok, fail
