# -*- coding: utf-8 -*-
"""
Соперник-компьютер в UTTT: сам движок бота и его встройка в партию.

Две группы проверок:

  • bot.Position — быстрая копия правил, по которой идёт перебор. У неё та же
    беда, что у «Заборов»: правил стало два экземпляра, и разойтись они могут
    молча. Поэтому здесь тот же приём — прогон случайных партий, где каждый ход
    делается и в Position, и в настоящем engine.apply_move, а результат
    сверяется клетка в клетку;
  • сама партия: создание, ответный ход в том же запросе, реванш, доступ.
"""

import json
import random
import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from games import arena, bot, engine
from games.engine import VARIANT_CLASSIC
from games.models import Game, SiteSetting

User = get_user_model()


class SureThing:
    """Генератор без случайности: нарочные ошибки выключены, ничьи решаются первым."""

    def random(self):
        return 1.0

    def randrange(self, n):
        return 0

    def choice(self, seq):
        return seq[0]


class PositionMirrorsEngineTests(TestCase):
    """Быстрое представление доски обязано совпадать с настоящими правилами."""

    def replay(self, variant, seed, plies=60):
        rng = random.Random(seed)
        state = engine.initial_state()
        pos = bot.Position(state, variant)

        for step in range(plies):
            if state['status'] != 'active':
                break
            moves = engine.legal_moves(state)
            self.assertEqual(
                sorted(pos.moves()), sorted(moves),
                'наборы ходов разошлись на полуходе %d (%s)' % (step, variant),
            )

            big, small = rng.choice(moves)
            player = state['current']
            state, err = engine.apply_move(state, player, big, small, variant=variant)
            self.assertIsNone(err, err)

            pos.play(big, small)

            mark = {'': bot.EMPTY, 'X': bot.X, 'O': bot.O, 'D': bot.DRAW}
            self.assertEqual(
                pos.cells,
                [mark[c] for row in state['board'] for c in row],
                'клетки разошлись на полуходе %d (%s)' % (step, variant),
            )
            self.assertEqual(pos.boards, [mark[v] for v in state['big_board']],
                             'малые поля разошлись на полуходе %d' % step)
            if state['status'] == 'active':
                self.assertEqual(pos.next_local, state['next_local'],
                                 'обязательное поле разошлось на полуходе %d' % step)
                self.assertEqual('X' if pos.turn == bot.X else 'O', state['current'],
                                 'очередь разошлась на полуходе %d' % step)

    def test_classic_matches_engine(self):
        for seed in range(12):
            self.replay(engine.VARIANT_CLASSIC, seed)

    def test_long_matches_engine(self):
        for seed in range(8):
            self.replay(engine.VARIANT_LONG, seed)

    def test_undo_restores_position(self):
        """Перебор ходит и откатывает на месте — откат обязан быть точным."""
        rng = random.Random(3)
        state = engine.initial_state()
        for _ in range(10):
            state, _ = engine.apply_move(state, state['current'],
                                         *rng.choice(engine.legal_moves(state)))
        pos = bot.Position(state, engine.VARIANT_CLASSIC)

        for big, small in pos.moves():
            before = (list(pos.cells), list(pos.boards), pos.next_local,
                      pos.turn, pos.winner)
            won_before = pos.boards[big]
            rec = pos.play(big, small)
            pos.undo(rec, won_before)
            self.assertEqual(
                (pos.cells, pos.boards, pos.next_local, pos.turn, pos.winner),
                before, 'откат не вернул позицию после хода %d/%d' % (big, small),
            )


class BotPlayTests(TestCase):

    def test_bot_moves_are_always_legal(self):
        """Ход бота проходит через настоящие правила без единой ошибки."""
        for variant in (engine.VARIANT_CLASSIC, engine.VARIANT_LONG):
            for level in bot.ALL_LEVELS:
                rng = random.Random(5)
                state = engine.initial_state()
                plies = 0
                while state['status'] == 'active' and plies < 120:
                    move = bot.choose_move(state, variant, level, rng)
                    self.assertIsNotNone(move, 'бот не нашёл хода (%s)' % level)
                    state, err = engine.apply_move(
                        state, state['current'], move[0], move[1], variant=variant)
                    self.assertIsNone(err, '%s: %s' % (level, err))
                    plies += 1
                self.assertEqual(state['status'], 'finished',
                                 'партия %s/%s не закончилась' % (variant, level))

    def test_bot_takes_a_win_in_one(self):
        """
        Выигрыш в один ход обязан находиться на любом уровне.

        Играем без случайности: слабому уровню положено ошибаться в трети
        ходов, и с обычным генератором тест ловил бы именно эту ошибку.
        """
        state = engine.initial_state()
        # X закрыл два поля из ряда 0-1-2 и стоит перед третьим.
        state['big_board'] = ['X', 'X', '', '', '', '', '', '', '']
        state['board'][2] = ['X', 'X', '', 'O', 'O', '', '', '', '']
        state['next_local'] = 2
        state['current'] = 'X'

        for level in bot.ALL_LEVELS:
            move = bot.choose_move(state, engine.VARIANT_CLASSIC, level, SureThing())
            self.assertEqual(move, (2, 2), 'уровень %s не увидел выигрыш' % level)

    def test_bot_does_not_hand_over_the_game(self):
        """
        В UTTT угроза опаснее не сама по себе, а тем, куда отправляет ход.

        У O собраны два поля из ряда и две клетки в третьем: чтобы выиграть
        партию, ему нужно попасть в поле 2. Сам X туда не ходит — он ходит в
        поле 5, — но клетка, которую он там займёт, определяет, куда пойдёт
        соперник. Занять клетку 2 значит послать O ровно туда, где тот выигрывает.
        """
        state = engine.initial_state()
        state['big_board'] = ['O', 'O', '', '', '', '', '', '', '']
        state['board'][2] = ['O', 'O', '', '', '', '', '', '', '']
        state['next_local'] = 5
        state['current'] = 'X'

        for level in ('medium', 'hard'):
            move = bot.choose_move(state, engine.VARIANT_CLASSIC, level, SureThing())
            self.assertNotEqual(move, (5, 2),
                                'уровень %s отдал партию своим же ходом' % level)

    def test_strong_level_answers_within_its_budget(self):
        """
        Время ответа — это время запроса игрока, поэтому у бота срок, а не
        глубина. Порог здесь с большим запасом: он ловит зависание, а не
        медленную машину.
        """
        state = engine.initial_state()
        started = time.monotonic()
        bot.choose_move(state, engine.VARIANT_CLASSIC, 'hard', random.Random(1))
        spent = time.monotonic() - started
        self.assertLess(spent, 2.0, 'сильный уровень думал %.1f с' % spent)


class BotGameTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        SiteSetting.objects.update_or_create(pk=1, defaults={'games_enabled': True})
        cls.user = User.objects.create_user('игрок', password='x',
                                            can_play_games=True,
                                            gamer_nickname='Игрок')
        cls.other = User.objects.create_user('другой', password='x',
                                             can_play_games=True,
                                             gamer_nickname='Другой')

    def create(self, **post):
        self.client.force_login(self.user)
        data = {'mode': 'bot', 'variant': 'classic', 'level': 'easy'}
        data.update(post)
        res = self.client.post(reverse('games:create'), data)
        self.assertEqual(res.status_code, 302)
        return Game.objects.get(code=res.url.rstrip('/').split('/')[-1])

    def move(self, game, big, small):
        return self.client.post(
            reverse('games:move', kwargs={'code': game.code}),
            json.dumps({'big': big, 'small': small}),
            content_type='application/json',
        )

    def test_human_plays_x_by_default(self):
        game = self.create()
        self.assertEqual(game.bot_side, 'O')
        self.assertEqual(game.bot_level, 'easy')
        self.assertEqual(game.x_player, self.user)
        self.assertIsNone(game.o_player)
        self.assertEqual(game.status, Game.STATUS_ACTIVE)
        self.assertEqual(game.current, 'X')          # ход человека
        self.assertEqual(game.label_for('O'), 'Компьютер (слабый)')

    def test_bot_can_move_first(self):
        game = self.create(first='bot')
        self.assertEqual(game.bot_side, 'X')
        self.assertEqual(game.o_player, self.user)
        self.assertIsNone(game.x_player)
        # первый ход уже сделан — доска не пустая, очередь человека
        self.assertEqual(game.current, 'O')
        self.assertEqual(sum(1 for row in game.board for c in row if c), 1)

    def test_bot_answers_in_the_same_request(self):
        game = self.create()
        res = self.move(game, 4, 4)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # В ответе уже стоит и наш ход, и ответ компьютера.
        self.assertEqual(data['current'], 'X')
        self.assertEqual(data['last_move']['by'], 'O')
        marks = sum(1 for row in data['board'] for c in row if c)
        self.assertEqual(marks, 2)

    def test_unknown_level_falls_back_to_default(self):
        game = self.create(level='гроссмейстер')
        self.assertEqual(game.bot_level, bot.DEFAULT_LEVEL)

    def test_nobody_can_join_a_bot_game(self):
        game = self.create()
        self.client.force_login(self.other)
        self.client.post(reverse('games:join', kwargs={'code': game.code}))
        game.refresh_from_db()
        self.assertIsNone(game.o_player)
        self.assertEqual(game.bot_side, 'O')

    def test_outsider_cannot_move_in_a_bot_game(self):
        game = self.create()
        self.client.force_login(self.other)
        res = self.move(game, 4, 4)
        self.assertEqual(res.status_code, 403)

    def test_rematch_keeps_the_bot_and_swaps_sides(self):
        game = self.create(level='medium')
        game.status = Game.STATUS_FINISHED
        game.winner = 'X'
        game.save(update_fields=['status', 'winner'])

        self.client.force_login(self.user)
        res = self.client.post(reverse('games:rematch', kwargs={'code': game.code}))
        new = Game.objects.get(code=res.url.rstrip('/').split('/')[-1])

        self.assertEqual(new.bot_side, 'X')          # стороны поменялись
        self.assertEqual(new.bot_level, 'medium')
        self.assertEqual(new.o_player, self.user)
        self.assertEqual(new.current, 'O')           # компьютер уже сходил

    def test_ordinary_games_are_untouched(self):
        self.client.force_login(self.user)
        res = self.client.post(reverse('games:create'),
                               {'mode': 'online', 'variant': 'classic'})
        game = Game.objects.get(code=res.url.rstrip('/').split('/')[-1])
        self.assertEqual(game.bot_side, '')
        self.assertEqual(game.bot_level, '')
        self.assertFalse(game.is_bot_game)
        self.assertEqual(game.status, Game.STATUS_WAITING)

    def test_games_list_survives_a_bot_on_either_side(self):
        """
        Место компьютера в базе пустое, и шаблон списка спотыкался об это:
        когда компьютер играл X, страница падала целиком.
        """
        self.create(level='hard')                 # компьютер за O
        self.create(first='bot', level='easy')    # и за X

        self.client.force_login(self.user)
        res = self.client.get(reverse('games:list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Компьютер (сильный)')
        self.assertContains(res, 'Компьютер (слабый)')

    def test_pages_do_not_leak_template_comments(self):
        """
        {# … #} в Django однострочный: растянутый на несколько строк он не
        комментарий, а текст, и вылезает игроку прямо на страницу.
        """
        game = self.create()
        self.client.force_login(self.user)
        for url in (reverse('games:list'),
                    reverse('games:hub'),
                    reverse('games:detail', kwargs={'code': game.code})):
            body = self.client.get(url).content.decode()
            self.assertNotIn('{#', body, url)
            self.assertNotIn('#}', body, url)

    def test_game_page_names_the_computer(self):
        game = self.create(level='hard')
        self.client.force_login(self.user)
        res = self.client.get(reverse('games:detail', kwargs={'code': game.code}))
        self.assertContains(res, 'Компьютер (сильный)')


class ТурнирныйСтенд(TestCase):
    """Стенд нужен, чтобы «стало сильнее» было измеримым.

    Отдельное внимание статистике: она единственная часть, которая может врать
    незаметно. Матч, объявляющий победителем того, кто выиграл на две партии из
    двухсот, увёл бы весь отбор за случайностью.
    """

    def test_доля_очков_считается_как_в_шахматах(self):
        итог = arena.Итог(победы=6, ничьи=2, поражения=2)
        self.assertEqual(итог.партий, 10)
        self.assertEqual(итог.очки, 7.0)          # ничья — половина очка
        self.assertAlmostEqual(итог.доля, 0.7)

    def test_ровный_счёт_объявляется_незначимым(self):
        итог = arena.Итог(победы=52, ничьи=0, поражения=48)
        self.assertFalse(итог.значимо)
        self.assertIn('неотличима от случайности', итог.словами('A', 'B'))

    def test_разгром_объявляется_значимым(self):
        итог = arena.Итог(победы=90, ничьи=0, поражения=10)
        self.assertTrue(итог.значимо)
        self.assertIn('от равной игры', итог.словами('A', 'B'))

    def test_погрешность_падает_с_числом_партий(self):
        мало = arena.Итог(победы=14, ничьи=0, поражения=6)
        много = arena.Итог(победы=140, ничьи=0, поражения=60)
        self.assertAlmostEqual(мало.доля, много.доля)
        self.assertLess(много.погрешность, мало.погрешность)
        # Вчетверо больше партий — вдвое уже интервал.
        self.assertAlmostEqual(много.погрешность, мало.погрешность / (10 ** 0.5),
                               places=2)

    def test_ничьи_сужают_интервал(self):
        """Разброс считается по результатам, а не по формуле для монетки."""
        поровну = arena.Итог(победы=50, ничьи=0, поражения=50)
        все_ничьи = arena.Итог(победы=0, ничьи=100, поражения=0)
        self.assertAlmostEqual(поровну.доля, все_ничьи.доля)
        self.assertLess(все_ничьи.погрешность, поровну.погрешность)

    def test_дебют_случайный_но_воспроизводимый(self):
        первый = arena._случайный_дебют(7)
        второй = arena._случайный_дебют(7)
        другой = arena._случайный_дебют(8)
        self.assertEqual(первый, второй)
        self.assertNotEqual(первый, другой)
        self.assertFalse(первый.get('winner'))     # движок пишет '' , а не None

    def test_партия_доигрывается_до_конца(self):
        слабый = arena.Игрок('слабый', 'easy')
        итог = arena.сыграть(слабый, слабый, arena._случайный_дебют(1), seed=1)
        self.assertIn(итог, ('X', 'O', 'D'))

    def test_матч_идёт_парами_туда_и_обратно(self):
        """Первый ход стоит дорого: без смены цветов измеришь не силу, а выступку."""
        слабый = arena.Игрок('слабый', 'easy')
        итог = arena.матч(слабый, слабый, партий=6, ядер=1, seed=3)
        self.assertEqual(итог.партий, 6)
        self.assertEqual(итог.партий % 2, 0)

    def test_сильный_обыгрывает_слабого_значимо(self):
        итог = arena.матч(arena.Игрок('средний', 'medium'),
                          arena.Игрок('слабый', 'easy'),
                          партий=30, ядер=1, seed=5)
        self.assertGreater(итог.доля, 0.5)
        self.assertTrue(итог.значимо)

    def test_свои_веса_доезжают_до_оценки(self):
        """Иначе отбор шёл бы, а играли бы всё время одни и те же веса."""
        обычные = dict(bot.ВЕСА)
        странные = dict(bot.ВЕСА)
        # Цена одиночного знака в малом поле: она участвует в любой позиции,
        # где сделан хоть один ход, — в отличие от цены выигранного поля или
        # свободного выбора, которых в дебюте может не быть вовсе.
        странные['малая_одна'] = 5000

        позиция = arena._случайный_дебют(11)
        поз = bot.Position(позиция, VARIANT_CLASSIC)
        сторона = поз.turn
        self.assertNotEqual(bot.evaluate(поз, сторона, обычные),
                            bot.evaluate(поз, сторона, странные))

        игрок = arena.игрок_из_весов('свои', странные, 'easy')
        self.assertEqual(игрок.как_словарь()['малая_одна'], 5000)

    def test_веса_по_умолчанию_не_меняют_игру(self):
        """Вынос чисел в набор не должен был ничего сдвинуть."""
        позиция = arena._случайный_дебют(13)
        поз = bot.Position(позиция, VARIANT_CLASSIC)
        self.assertEqual(bot.evaluate(поз, поз.turn),
                         bot.evaluate(поз, поз.turn, dict(bot.ВЕСА)))

    def test_перчатка_считает_общую_долю(self):
        итоги, общая = arena.перчатка(
            arena.Игрок('средний', 'medium'),
            [arena.Игрок('слабый', 'easy')],
            партий=10, ядер=1, seed=2,
        )
        self.assertEqual(len(итоги), 1)
        self.assertGreater(общая, 0.5)

