# -*- coding: utf-8 -*-
"""
Сетевая партия целиком: создание с выбором цвета и доступа, посадка второго
игрока, очередь ходов, наблюдение, сдача, отмена и уборка базы.

Проверяется именно поведение сервера, а не браузера: клиент рисует подсказки,
но кто, чем и когда вправе ходить, решает только этот код.
"""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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

    def create(self, user, side='red', access=None):
        self.client.force_login(user)
        data = {'side': side}
        if access:
            data['access'] = access
        res = self.client.post(self.url('create'), data)
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
        blue_side_game = self.create(self.blue, 'blue', access='open')
        red_side_game = self.create(self.red, 'red', access='open')

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

    # ── уровни компьютера и заборы пальцем ──

    def test_lobby_offers_three_levels(self):
        self.client.force_login(self.red)
        body = self.client.get(self.url('play')).content.decode()
        for level in ('easy', 'medium', 'hard'):
            self.assertIn('level=%s' % level, body)

    def test_local_page_has_level_picker_and_wall_strip(self):
        self.client.force_login(self.red)
        res = self.client.get(self.url('local'))
        self.assertContains(res, 'id="qLevel"')
        for level in ('easy', 'medium', 'hard'):
            self.assertContains(res, 'value="%s"' % level)
        # полоска подтверждения нужна и здесь, и в сетевой партии: без неё
        # палец не сможет ни повернуть забор, ни поставить его
        self.assertContains(res, 'id="qWallTool"')
        self.assertContains(res, 'id="qWallRotate"')
        self.assertContains(res, 'id="qWallPlace"')

    def test_online_page_has_wall_strip(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        res = self.client.get(self.url('game', game.code))
        self.assertContains(res, 'id="qWallTool"')
        self.assertContains(res, 'id="qWallPlace"')

    # ── приватные и открытые партии ──

    def test_games_are_private_by_default(self):
        """Ссылку отправляют конкретному человеку — посторонним партия не видна."""
        game = self.create(self.red)
        self.assertEqual(game.access, QuoridorGame.ACCESS_LINK)
        self.assertFalse(game.is_open)

        self.client.force_login(self.other)
        codes = {g.code for g in self.client.get(self.url('play')).context['open_games']}
        self.assertNotIn(game.code, codes)

    def test_open_game_is_listed(self):
        game = self.create(self.red, access='open')
        self.assertTrue(game.is_open)

        self.client.force_login(self.other)
        codes = {g.code for g in self.client.get(self.url('play')).context['open_games']}
        self.assertIn(game.code, codes)

    def test_private_game_still_opens_by_link(self):
        """Приватность прячет партию из списка, но ссылка работает как раньше."""
        game = self.create(self.red)
        self.client.force_login(self.blue)
        res = self.client.get(self.url('game', game.code))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['can_join'])

        data = self.client.post(self.url('join', game.code),
                                HTTP_X_REQUESTED_WITH='fetch').json()
        self.assertEqual(data['took'], engine.BLUE)

    def test_garbage_access_falls_back_to_private(self):
        game = self.create(self.red, access='весь мир')
        self.assertEqual(game.access, QuoridorGame.ACCESS_LINK)

    def test_limit_on_pending_games_keeps_the_access_choice(self):
        """Ошибка про лимит не должна стирать уже сделанный выбор доступа."""
        for _ in range(5):
            self.create(self.red, access='open')

        self.client.force_login(self.red)
        res = self.client.post(self.url('create'), {'side': 'red', 'access': 'open'})
        self.assertEqual(res.status_code, 400)
        self.assertContains(res, 'Слишком много партий', status_code=400)
        self.assertContains(res, 'value="open" checked', status_code=400)
        self.assertEqual(QuoridorGame.objects.filter(red_player=self.red).count(), 5)

    # ── наблюдатель ──

    def test_watch_link_does_not_seat(self):
        game = self.create(self.red)
        self.client.force_login(self.blue)
        res = self.client.get(self.url('game', game.code) + '?watch=1')

        self.assertTrue(res.context['watching'])
        self.assertFalse(res.context['can_join'])   # скрипт не станет садиться
        self.assertTrue(res.context['can_seat'])    # но место всё ещё свободно

        game.refresh_from_db()
        self.assertIsNone(game.blue_player)
        self.assertEqual(game.status, QuoridorGame.STATUS_WAITING)

    def test_watch_page_has_no_join_form(self):
        """Зрителю не подсовывают ни форму входа, ни ссылку «позови соперника»."""
        game = self.create(self.red)
        self.client.force_login(self.blue)
        res = self.client.get(self.url('game', game.code) + '?watch=1')
        self.assertNotContains(res, 'id="qJoinForm"')
        # блоки приглашений в разметке есть, но приходят скрытыми: показывать их
        # или нет, решает скрипт по тому, стал ли человек игроком
        self.assertContains(res, 'id="qSeatInvite" hidden')
        self.assertContains(res, 'id="qWatchBlock" hidden')

    def test_page_has_no_leaked_template_comments(self):
        """
        {# … #} в Django однострочный: растянутый на несколько строк он не
        комментарий, а текст, и вылезает игроку прямо в шапку партии.
        """
        game = self.create(self.red)
        for url in (self.url('game', game.code),
                    self.url('game', game.code) + '?watch=1',
                    self.url('create'),
                    self.url('play')):
            body = self.client.get(url).content.decode()
            self.assertNotIn('{#', body, url)
            self.assertNotIn('#}', body, url)
            self.assertNotIn('{%', body, url)

    def test_watcher_may_sit_down_later(self):
        """Передумал смотреть — садится тем же входом, что и обычный гость."""
        game = self.create(self.red)
        self.client.force_login(self.blue)
        self.client.get(self.url('game', game.code) + '?watch=1')

        data = self.client.post(self.url('join', game.code),
                                HTTP_X_REQUESTED_WITH='fetch').json()
        self.assertEqual(data['took'], engine.BLUE)

    def test_watcher_of_a_full_game_sees_all_but_may_not_move(self):
        game = self.start()
        self.client.force_login(self.other)
        data = self.client.get(self.url('state', game.code)).json()

        self.assertEqual(data['my_side'], '')
        self.assertFalse(data['can_seat'])
        self.assertEqual(data['state']['pawns']['red'], {'r': 8, 'c': 4})
        self.assertEqual(data['red_label'], 'игрок1')

        res = self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.assertEqual(res.status_code, 403)

    # ── уборка базы ──

    def age(self, game, **delta):
        """Состарить партию: updated_at стоит auto_now, обычным save не сдвинуть."""
        QuoridorGame.objects.filter(pk=game.pk).update(
            updated_at=timezone.now() - timedelta(**delta))

    def test_finished_games_are_removed_after_a_while(self):
        game = self.start()
        self.client.force_login(self.red)
        self.post_json(self.url('move', game.code), {'kind': 'move', 'r': 7, 'c': 4})
        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))

        # только что сыгранную не трогаем: победитель ещё смотрит на итог
        QuoridorGame.purge_old()
        self.assertTrue(QuoridorGame.objects.filter(pk=game.pk).exists())

        self.age(game, hours=7)
        removed = QuoridorGame.purge_old()
        self.assertEqual(removed['сыгранные'], 1)
        self.assertFalse(QuoridorGame.objects.filter(pk=game.pk).exists())

    def test_cancelled_games_are_removed_too(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))
        self.age(game, hours=7)

        QuoridorGame.purge_old()
        self.assertFalse(QuoridorGame.objects.filter(pk=game.pk).exists())

    def test_abandoned_games_live_longer_but_go_too(self):
        game = self.create(self.red)
        self.age(game, hours=7)
        QuoridorGame.purge_old()
        self.assertTrue(QuoridorGame.objects.filter(pk=game.pk).exists())

        self.age(game, days=3)
        removed = QuoridorGame.purge_old()
        self.assertEqual(removed['брошенные'], 1)
        self.assertFalse(QuoridorGame.objects.filter(pk=game.pk).exists())

    def test_live_games_are_never_touched(self):
        game = self.start()
        self.age(game, days=30)                    # хоть месяц — партия идёт
        QuoridorGame.purge_old()
        self.assertTrue(QuoridorGame.objects.filter(pk=game.pk).exists())

    def test_lobby_sweeps_on_its_own(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))
        self.age(game, hours=7)

        cache.delete('quoridor:swept')             # уборка бывает раз в 10 минут
        self.client.get(self.url('play'))
        self.assertFalse(QuoridorGame.objects.filter(pk=game.pk).exists())

    def test_cleanup_command_reports_and_deletes(self):
        game = self.create(self.red)
        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))
        self.age(game, hours=7)

        call_command('quoridor_cleanup', '--dry-run')
        self.assertTrue(QuoridorGame.objects.filter(pk=game.pk).exists())

        call_command('quoridor_cleanup')
        self.assertFalse(QuoridorGame.objects.filter(pk=game.pk).exists())

    def test_cleanup_all_ignores_the_grace_period(self):
        """Явная просьба «снести всё» не оглядывается на срок хранения."""
        game = self.create(self.red)
        self.client.force_login(self.red)
        self.client.post(self.url('resign', game.code))     # только что отменена

        call_command('quoridor_cleanup')                    # обычная уборка её щадит
        self.assertTrue(QuoridorGame.objects.filter(pk=game.pk).exists())

        call_command('quoridor_cleanup', '--all')
        self.assertFalse(QuoridorGame.objects.filter(pk=game.pk).exists())

    def test_all_flag_never_touches_pending_invitations(self):
        """«Снести всё» про сыгранные. Брошенная партия — это чьё-то приглашение."""
        fresh = self.create(self.red)                     # ждёт соперника прямо сейчас
        dead, alive = QuoridorGame.expired(ignore_age=True)
        self.assertEqual(alive.count(), 0)
        self.assertNotIn(fresh.pk, [g.pk for g in dead])

        call_command('quoridor_cleanup', '--all')
        self.assertTrue(QuoridorGame.objects.filter(pk=fresh.pk).exists())

    def test_preview_matches_what_cleanup_actually_deletes(self):
        """У необратимой команды предпросмотр обязан совпадать с действием."""
        played = self.create(self.red)
        self.client.force_login(self.red)
        self.client.post(self.url('resign', played.code))  # только что отменена
        abandoned = self.create(self.blue, 'blue')
        self.age(abandoned, days=3)

        for ignore_age in (False, True):
            dead, waiting = QuoridorGame.expired(ignore_age=ignore_age)
            обещано = dead.count() + waiting.count()
            было = QuoridorGame.objects.count()
            removed = QuoridorGame.purge_old(ignore_age=ignore_age)
            self.assertEqual(removed['сыгранные'] + removed['брошенные'], обещано)
            self.assertEqual(QuoridorGame.objects.count(), было - обещано)

    def test_state_of_a_removed_game_is_404(self):
        """Страница может остаться открытой — клиенту нужен внятный ответ."""
        game = self.start()
        code = game.code
        game.delete()

        self.client.force_login(self.red)
        self.assertEqual(self.client.get(self.url('state', code)).status_code, 404)

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
