# -*- coding: utf-8 -*-
"""
Сетевая партия целиком: создание с выбором цвета, посадка второго игрока,
очередь ходов, сдача и отмена.

Проверяется именно поведение сервера, а не браузера: клиент рисует подсказки,
но кто, чем и когда вправе ходить, решает только этот код.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from games.models import SiteSetting
from quoridor import engine
from quoridor.models import QuoridorGame

User = get_user_model()


class OnlineGameTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        SiteSetting.objects.update_or_create(pk=1, defaults={'games_enabled': True})
        cls.red = User.objects.create_user('игрок1', password='x', can_play_games=True)
        cls.blue = User.objects.create_user('игрок2', password='x', can_play_games=True)
        cls.other = User.objects.create_user('игрок3', password='x', can_play_games=True)

    def url(self, name, code=None):
        return reverse('quoridor:' + name, kwargs={'code': code} if code else None)

    def create(self, user, side='red'):
        self.client.force_login(user)
        res = self.client.post(self.url('create'), {'side': side})
        self.assertEqual(res.status_code, 302)
        return QuoridorGame.objects.get(code=res.url.rstrip('/').split('/')[-1])

    def post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    # ── выбор цвета ──

    def test_new_page_offers_colors(self):
        self.client.force_login(self.red)
        res = self.client.get(self.url('create'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'value="red"')
        self.assertContains(res, 'value="blue"')
        self.assertContains(res, 'value="random"')

    def test_create_as_red(self):
        game = self.create(self.red, 'red')
        self.assertEqual(game.red_player, self.red)
        self.assertIsNone(game.blue_player)
        self.assertEqual(game.free_side(), engine.BLUE)
        self.assertEqual(game.status, QuoridorGame.STATUS_WAITING)

    def test_create_as_blue(self):
        """Создатель вправе отдать первый ход: тогда ждём как раз красного."""
        game = self.create(self.blue, 'blue')
        self.assertEqual(game.blue_player, self.blue)
        self.assertIsNone(game.red_player)
        self.assertEqual(game.free_side(), engine.RED)
        self.assertEqual(game.state['turn'], engine.RED)

    def test_create_random_picks_a_side(self):
        game = self.create(self.red, 'random')
        self.assertIn(game.player_side(self.red), (engine.RED, engine.BLUE))
        self.assertIsNotNone(game.free_side())

    def test_create_with_garbage_side_falls_back_to_red(self):
        game = self.create(self.red, 'зелёный')
        self.assertEqual(game.player_side(self.red), engine.RED)

    # ── посадка второго игрока ──

    def test_guest_takes_the_free_seat(self):
        game = self.create(self.red)
        self.client.force_login(self.blue)
        res = self.client.post(self.url('join', game.code),
                               HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['took'], engine.BLUE)
        self.assertEqual(data['status'], QuoridorGame.STATUS_ACTIVE)

        game.refresh_from_db()
        self.assertEqual(game.blue_player, self.blue)
        self.assertEqual(game.status, QuoridorGame.STATUS_ACTIVE)

    def test_guest_takes_red_seat_when_creator_chose_blue(self):
        game = self.create(self.blue, 'blue')
        self.client.force_login(self.red)
        data = self.client.post(self.url('join', game.code),
                                HTTP_X_REQUESTED_WITH='fetch').json()
        self.assertEqual(data['took'], engine.RED)
        self.assertEqual(data['my_side'], engine.RED)

    def test_second_guest_only_watches(self):
        game = self.create(self.red)
        self.client.force_login(self.blue)
        self.client.post(self.url('join', game.code), HTTP_X_REQUESTED_WITH='fetch')

        self.client.force_login(self.other)
        data = self.client.post(self.url('join', game.code),
                                HTTP_X_REQUESTED_WITH='fetch').json()
        self.assertEqual(data['took'], '')
        self.assertEqual(data['my_side'], '')
        game.refresh_from_db()
        self.assertEqual(game.blue_player, self.blue)

    def test_creator_cannot_take_both_seats(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        data = self.client.post(self.url('join', game.code),
                                HTTP_X_REQUESTED_WITH='fetch').json()
        self.assertEqual(data['took'], '')
        game.refresh_from_db()
        self.assertIsNone(game.blue_player)
        self.assertEqual(game.status, QuoridorGame.STATUS_WAITING)

    def test_join_without_js_redirects(self):
        """Запасной путь: обычная форма без заголовка fetch."""
        game = self.create(self.red)
        self.client.force_login(self.blue)
        res = self.client.post(self.url('join', game.code))
        self.assertEqual(res.status_code, 302)
        game.refresh_from_db()
        self.assertEqual(game.blue_player, self.blue)

    def test_state_tells_guest_he_may_sit(self):
        game = self.create(self.red)
        self.client.force_login(self.blue)
        data = self.client.get(self.url('state', game.code)).json()
        self.assertTrue(data['can_seat'])
        self.assertEqual(data['free_side'], engine.BLUE)

        self.client.force_login(self.red)
        data = self.client.get(self.url('state', game.code)).json()
        self.assertFalse(data['can_seat'])

    # ── ходы ──

    def start(self):
        game = self.create(self.red)
        self.client.force_login(self.blue)
        self.client.post(self.url('join', game.code), HTTP_X_REQUESTED_WITH='fetch')
        game.refresh_from_db()
        return game

    def test_turn_order_and_rejections(self):
        game = self.start()

        self.client.force_login(self.blue)
        res = self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 1, 'c': 4})
        self.assertEqual(res.status_code, 400)

        self.client.force_login(self.other)
        res = self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.assertEqual(res.status_code, 403)

        self.client.force_login(self.red)
        res = self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['state']['turn'], engine.BLUE)

    def test_no_moves_before_opponent_arrives(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        res = self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.assertEqual(res.status_code, 400)

    # ── сдача и отмена ──

    def test_resign_gives_win_to_opponent(self):
        game = self.start()
        self.client.force_login(self.red)
        self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.client.force_login(self.red)
        data = self.client.post(self.url('resign', game.code)).json()

        self.assertEqual(data['winner'], engine.BLUE)
        self.assertEqual(data['status'], QuoridorGame.STATUS_FINISHED)
        self.assertEqual(data['last_move']['kind'], 'resign')
        self.assertEqual(data['last_move']['side'], engine.RED)
        # победа записана и в состояние — движок больше не примет ходов
        self.assertEqual(data['state']['winner'], engine.BLUE)

        game.refresh_from_db()
        self.assertEqual(game.winner, engine.BLUE)
        res = self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.assertEqual(res.status_code, 400)

    def test_opponent_sees_resignation_by_polling(self):
        game = self.start()
        self.client.force_login(self.red)
        self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.client.force_login(self.blue)
        before = self.client.get(self.url('state', game.code)).json()
        self.assertEqual(before['status'], QuoridorGame.STATUS_ACTIVE)

        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))

        self.client.force_login(self.blue)
        after = self.client.get(self.url('state', game.code)).json()
        self.assertEqual(after['winner'], engine.BLUE)
        self.assertEqual(after['last_move']['kind'], 'resign')

    def test_guest_may_leave_before_the_first_move(self):
        """
        Место занимается автоматически — значит и освобождаться должно легко,
        иначе заглянувший на партию остаётся в ней навсегда.
        """
        game = self.start()
        self.client.force_login(self.blue)
        data = self.client.post(self.url('resign', game.code)).json()

        self.assertEqual(data['outcome'], 'left')
        self.assertEqual(data['status'], QuoridorGame.STATUS_WAITING)
        self.assertEqual(data['winner'], '')
        self.assertEqual(data['last_move']['kind'], 'left')

        game.refresh_from_db()
        self.assertIsNone(game.blue_player)
        self.assertEqual(game.red_player, self.red)
        self.assertTrue(game.can_seat(self.other))     # место снова свободно

    def test_leaving_is_no_longer_possible_after_a_move(self):
        game = self.start()
        self.client.force_login(self.red)
        self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})

        self.client.force_login(self.blue)
        data = self.client.post(self.url('resign', game.code)).json()
        self.assertEqual(data['outcome'], 'resign')
        self.assertEqual(data['winner'], engine.RED)

    def test_freed_seat_can_be_taken_again(self):
        game = self.start()
        self.client.force_login(self.blue)
        self.client.post(self.url('resign', game.code))

        self.client.force_login(self.other)
        data = self.client.post(self.url('join', game.code),
                                HTTP_X_REQUESTED_WITH='fetch').json()
        self.assertEqual(data['took'], engine.BLUE)
        self.assertEqual(data['status'], QuoridorGame.STATUS_ACTIVE)

    def test_resign_before_start_cancels(self):
        """До первого хода соперника нет — записывать ему победу не за что."""
        game = self.create(self.red)
        self.client.force_login(self.red)
        data = self.client.post(self.url('resign', game.code)).json()

        self.assertEqual(data['outcome'], 'cancel')
        self.assertEqual(data['status'], QuoridorGame.STATUS_CANCELLED)
        self.assertEqual(data['winner'], '')
        self.assertEqual(data['last_move']['kind'], 'cancel')

        game.refresh_from_db()
        self.assertEqual(game.status, QuoridorGame.STATUS_CANCELLED)
        # в отменённую партию больше не сядешь
        self.client.force_login(self.blue)
        self.assertFalse(game.can_seat(self.blue))
        self.client.post(self.url('join', game.code), HTTP_X_REQUESTED_WITH='fetch')
        game.refresh_from_db()
        self.assertIsNone(game.blue_player)

    def test_outsider_cannot_resign(self):
        game = self.start()
        self.client.force_login(self.other)
        res = self.client.post(self.url('resign', game.code))
        self.assertEqual(res.status_code, 403)
        game.refresh_from_db()
        self.assertEqual(game.status, QuoridorGame.STATUS_ACTIVE)

    def test_resign_twice_is_refused(self):
        game = self.start()
        self.client.force_login(self.red)
        self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))
        res = self.client.post(self.url('resign', game.code))
        self.assertEqual(res.status_code, 400)

    def test_resign_requires_post(self):
        game = self.start()
        self.client.force_login(self.red)
        self.assertEqual(self.client.get(self.url('resign', game.code)).status_code, 405)

    # ── лобби ──

    def test_lobby_lists_open_game_of_either_colour(self):
        blue_side_game = self.create(self.blue, 'blue')
        red_side_game = self.create(self.red, 'red')

        self.client.force_login(self.other)
        codes = {g.code for g in self.client.get(self.url('play')).context['open_games']}
        self.assertIn(blue_side_game.code, codes)
        self.assertIn(red_side_game.code, codes)

    def test_lobby_hides_own_games_from_the_open_list(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        codes = {g.code for g in self.client.get(self.url('play')).context['open_games']}
        self.assertNotIn(game.code, codes)
        mine = {g.code for g in self.client.get(self.url('play')).context['my_games']}
        self.assertIn(game.code, mine)

    def test_cancelled_game_leaves_the_open_list(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))

        self.client.force_login(self.blue)
        codes = {g.code for g in self.client.get(self.url('play')).context['open_games']}
        self.assertNotIn(game.code, codes)

    # ── доступ ──

    def test_anonymous_is_sent_to_login(self):
        game = self.create(self.red)
        self.client.logout()
        for name in ('play', 'create'):
            res = self.client.get(self.url(name))
            self.assertEqual(res.status_code, 302)
        res = self.client.get(self.url('game', game.code))
        self.assertEqual(res.status_code, 302)
        res = self.client.post(self.url('resign', game.code))
        self.assertEqual(res.status_code, 302)

    def test_player_without_flag_is_refused(self):
        game = self.create(self.red)
        plain = User.objects.create_user('без_доступа', password='x')
        self.client.force_login(plain)
        self.assertEqual(self.client.get(self.url('game', game.code)).status_code, 403)
        self.assertEqual(self.client.post(self.url('join', game.code)).status_code, 403)
