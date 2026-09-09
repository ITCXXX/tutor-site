# -*- coding: utf-8 -*-
"""Проверки раздела карточек.

Главное внимание — разбору вставленного текста и планировщику. Это два места,
где ошибка тихая: разбор молча потеряет половину списка, планировщик молча
назначит повторение не туда, и заметить это по внешнему виду нельзя.
"""

import json
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from users.models import User

from . import views
from .ai_prompt import собрать
from .models import Card, CardState, Deck
from .parsing import разобрать
from .richtext import очистить, текстом
from .templatetags.cards_extras import слово


class РазборСписка(TestCase):
    """Что именно понимается из вставленного текста."""

    def test_вертикальная_черта(self):
        карточки, замечания = разобрать('Площадь круга | S = pi R^2')
        self.assertEqual(len(карточки), 1)
        self.assertEqual(карточки[0]['front'], 'Площадь круга')
        self.assertEqual(карточки[0]['back'], 'S = pi R^2')
        self.assertFalse(замечания)

    def test_табуляция_из_таблицы(self):
        карточки, _ = разобрать('Синус\tотношение катета к гипотенузе\n'
                                'Тангенс\tотношение катетов')
        self.assertEqual(len(карточки), 2)
        self.assertEqual(карточки[1]['front'], 'Тангенс')

    def test_шапка_таблицы_не_становится_карточкой(self):
        карточки, _ = разобрать('Термин\tОпределение\nСинус\tотношение')
        self.assertEqual(len(карточки), 1)
        self.assertEqual(карточки[0]['front'], 'Синус')

    def test_нумерация_и_жирный_шрифт(self):
        текст = ('1. **Метафора** | скрытое сравнение\n'
                 '2) *Эпитет* | образное определение\n'
                 '- Гипербола | преувеличение')
        карточки, _ = разобрать(текст)
        self.assertEqual([к['front'] for к in карточки],
                         ['Метафора', '*Эпитет*', 'Гипербола'])

    def test_таблица_markdown(self):
        текст = ('| Термин | Определение |\n'
                 '|---|---|\n'
                 '| Синус | отношение противолежащего катета к гипотенузе |')
        карточки, _ = разобрать(текст)
        self.assertEqual(len(карточки), 1)
        self.assertEqual(карточки[0]['front'], 'Синус')

    def test_формула_с_модулем_не_режется(self):
        """Вертикальная черта внутри формулы — это модуль, а не разделитель."""
        карточки, _ = разобрать(r'Решите $|x - 3| = 5$ | $x = 8$ или $x = -2$')
        self.assertEqual(len(карточки), 1)
        self.assertEqual(карточки[0]['front'], r'Решите $|x - 3| = 5$')
        self.assertEqual(карточки[0]['back'], r'$x = 8$ или $x = -2$')

    def test_длинное_тире(self):
        карточки, _ = разобрать('Медиана — отрезок от вершины к середине стороны')
        self.assertEqual(len(карточки), 1)
        self.assertEqual(карточки[0]['back'],
                         'отрезок от вершины к середине стороны')

    def test_третий_столбец_становится_подсказкой(self):
        карточки, _ = разобрать('Теорема Пифагора | $c^2=a^2+b^2$ | только для прямоугольного')
        self.assertEqual(карточки[0]['hint'], 'только для прямоугольного')

    def test_ограждение_и_вступление(self):
        """Нейросеть добавляет ```-ограждение; строки без разделителя видны в замечаниях."""
        текст = ('```\n'
                 'Конечно! Вот список карточек:\n'
                 'Синус | отношение\n'
                 '```')
        карточки, замечания = разобрать(текст)
        self.assertEqual(len(карточки), 1)
        self.assertEqual(len(замечания), 1)
        self.assertIn('Конечно', замечания[0])

    def test_повтор_не_добавляется_дважды(self):
        карточки, замечания = разобрать(
            'Синус | отношение\nСинус | другое', уже_есть=(),
        )
        self.assertEqual(len(карточки), 1)
        self.assertTrue(any('уже есть' in з for з in замечания))

    def test_повтор_с_тем_что_в_колоде(self):
        карточки, замечания = разобрать('Синус | отношение', уже_есть=['синус'])
        self.assertEqual(карточки, [])
        self.assertTrue(замечания)


class ПравилоДляНейросети(TestCase):
    """Это правило формата, а не задание.

    Ни темы, ни количества карточек в нём быть не должно: задание ставит
    человек, он уже сидит в чате со своим материалом, а сколько карточек выйдет
    — зависит от материала, а не от круглого числа.
    """

    def test_правило_не_задаёт_тему_и_количество(self):
        текст = собрать('text')
        for лишнее in ('тем', 'карточек:', 'ровно', 'Сделай'):
            self.assertNotIn(лишнее, текст, лишнее)

    def test_формат_описан(self):
        текст = собрать('text')
        self.assertIn('лицевая сторона | оборотная сторона', текст)
        self.assertIn('восклицательным знаком', текст)
        self.assertIn('подсказка', текст)

    def test_правило_формул_только_для_математики(self):
        self.assertIn('LaTeX', собрать('math'))
        self.assertNotIn('LaTeX', собрать('text'))

    def test_пример_разбирается_тем_же_разбором(self):
        """Главная проверка: то, что мы просим у нейросети, сайт понимает."""
        for вид in ('text', 'math'):
            строки = собрать(вид).split('Пример:')[1].strip().splitlines()
            карточки, замечания = разобрать('\n'.join(строки))
            self.assertEqual(len(карточки), 3, вид)
            self.assertFalse(замечания, вид)
            # В каждом примере есть карточка с неверными вариантами.
            self.assertTrue(any(к['distractors'] for к in карточки), вид)
            self.assertTrue(any(к['hint'] for к in карточки), вид)

    def test_неизвестный_вид_не_роняет_страницу(self):
        ответ = self.client.get(reverse('cards:prompt'), {'вид': 'ерунда'})
        self.assertEqual(ответ.status_code, 200)
        self.assertEqual(ответ.context['вид'], 'text')


class Страницы(TestCase):

    def setUp(self):
        self.автор = User.objects.create_user('автор', 'пароль')
        self.чужой = User.objects.create_user('чужой', 'пароль')
        self.колода = Deck.objects.create(title='Формулы', owner=self.автор)
        Card.objects.create(deck=self.колода, front='Площадь круга', back='pi R^2')

    def test_чужая_колода_без_ссылки_не_открывается(self):
        self.client.force_login(self.чужой)
        ответ = self.client.get(reverse('cards:deck', args=[self.колода.pk]))
        self.assertEqual(ответ.status_code, 404)

    def test_ссылка_с_ключом_открывает_и_запоминается(self):
        """Открыв ссылку один раз, ученик находит колоду у себя в разделе.

        Иначе ссылку пришлось бы хранить в закладках и доставать перед каждым
        занятием.
        """
        self.client.force_login(self.чужой)
        адрес = reverse('cards:deck', args=[self.колода.pk])
        ответ = self.client.get(адрес, {'k': self.колода.share_token})
        self.assertEqual(ответ.status_code, 200)

        # Второй раз — уже без ключа.
        self.assertEqual(self.client.get(адрес).status_code, 200)
        список = self.client.get(reverse('cards:list'))
        self.assertEqual([к.pk for к in список.context['чужие']], [self.колода.pk])

    def test_неверный_ключ_не_открывает(self):
        self.client.force_login(self.чужой)
        ответ = self.client.get(reverse('cards:deck', args=[self.колода.pk]),
                                {'k': 'не-тот-ключ'})
        self.assertEqual(ответ.status_code, 404)

    def test_ссылка_даёт_читать_но_не_править(self):
        self.client.force_login(self.чужой)
        self.client.get(reverse('cards:deck', args=[self.колода.pk]),
                        {'k': self.колода.share_token})
        for имя in ('import', 'edit', 'edit_cards'):
            ответ = self.client.get(reverse('cards:%s' % имя, args=[self.колода.pk]))
            self.assertEqual(ответ.status_code, 404, имя)

    def test_гостю_ссылка_работает_в_рамках_сеанса(self):
        адрес = reverse('cards:deck', args=[self.колода.pk])
        self.assertEqual(
            self.client.get(адрес, {'k': self.колода.share_token}).status_code, 200)
        self.assertEqual(self.client.get(адрес).status_code, 200)

    def test_у_каждой_колоды_свой_ключ(self):
        другая = Deck.objects.create(title='Другая', owner=self.автор)
        self.assertTrue(self.колода.share_token)
        self.assertNotEqual(self.колода.share_token, другая.share_token)
        self.assertGreaterEqual(len(self.колода.share_token), 20)

    def test_предпросмотр_не_создаёт_карточек(self):
        self.client.force_login(self.автор)
        self.client.post(reverse('cards:import', args=[self.колода.pk]),
                         {'текст': 'Синус | отношение', 'предпросмотр': '1'})
        self.assertEqual(self.колода.cards.count(), 1)

    def test_сохранение_добавляет_карточки(self):
        self.client.force_login(self.автор)
        ответ = self.client.post(
            reverse('cards:import', args=[self.колода.pk]),
            {'текст': 'Синус | отношение\nКосинус | другое отношение',
             'сохранить': '1'},
        )
        self.assertEqual(ответ.status_code, 302)
        self.assertEqual(self.колода.cards.count(), 3)

    def test_страница_повторения_отдаёт_очередь(self):
        self.client.force_login(self.автор)
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        self.assertEqual(ответ.status_code, 200)
        # Очередь уезжает на страницу через json_script, а он экранирует
        # кириллицу — искать текст прямо в разметке бессмысленно.
        задания = ответ.context['задания']
        self.assertEqual(len(задания), 1)
        self.assertEqual(задания[0]['вопрос'], 'Площадь круга')
        self.assertEqual(задания[0]['секция'], CardState.НЕ_РАЗОБРАНА)
        self.assertEqual(ответ.context['размер_раунда'], self.колода.round_size)

    def test_карточка_кладётся_в_секцию(self):
        self.client.force_login(self.автор)
        карточка = self.колода.cards.get()
        ответ = self.client.post(
            reverse('cards:answer', args=[self.колода.pk]),
            data={'card': карточка.pk, 'direction': 0,
                  'секция': CardState.ТРУДНО},
            content_type='application/json',
        )
        self.assertEqual(ответ.status_code, 200)
        состояние = CardState.objects.get(card=карточка)
        self.assertEqual(состояние.section, CardState.ТРУДНО)
        self.assertEqual(состояние.shows, 1)

    def test_секцию_можно_поменять_позже(self):
        """Ровно ради этого раскладку и делает человек, а не программа."""
        self.client.force_login(self.автор)
        карточка = self.колода.cards.get()
        адрес = reverse('cards:answer', args=[self.колода.pk])
        for секция in (CardState.ТРУДНО, CardState.ЛЕГКО):
            self.client.post(адрес, content_type='application/json',
                             data={'card': карточка.pk, 'direction': 0,
                                   'секция': секция})
        self.assertEqual(CardState.objects.get(card=карточка).section,
                         CardState.ЛЕГКО)
        self.assertEqual(CardState.objects.filter(card=карточка).count(), 1)

    def test_несуществующая_секция_отклоняется(self):
        self.client.force_login(self.автор)
        карточка = self.колода.cards.get()
        ответ = self.client.post(
            reverse('cards:answer', args=[self.колода.pk]),
            data={'card': карточка.pk, 'секция': 9},
            content_type='application/json',
        )
        self.assertEqual(ответ.status_code, 400)

    def test_проверка_текстового_ответа_прощает_опечатку(self):
        колода = Deck.objects.create(
            title='Термины', owner=self.автор,
        )
        карточка = Card.objects.create(
            deck=колода, front='Отрезок из вершины к середине стороны',
            back='медиана',
        )
        self.client.force_login(self.автор)
        for набрано, ожидаем in (('медиана', True), ('медиaна', True),
                                 ('Медиана ', True), ('биссектриса', False)):
            ответ = self.client.post(
                reverse('cards:check', args=[колода.pk]),
                data={'card': карточка.pk, 'direction': 0, 'typed': набрано},
                content_type='application/json',
            )
            self.assertEqual(ответ.json()['верно'], ожидаем, набрано)

    def test_проверка_математического_ответа(self):
        """Делить колоды на «математические» и «текстовые» оказалось незачем.

        Вид ответа виден по самому ответу: в одной колоде спокойно уживаются
        «Париж» и «2,5», и сравнение по значению включается там, где есть что
        сравнивать по значению.
        """
        колода = Deck.objects.create(title='Уравнения', owner=self.автор)
        карточка = Card.objects.create(deck=колода, front='2x = 5', back='2,5')
        self.client.force_login(self.автор)
        for набрано, ожидаем in (('2,5', True), ('2.5', True), ('3', False)):
            ответ = self.client.post(
                reverse('cards:check', args=[колода.pk]),
                data={'card': карточка.pk, 'direction': 0, 'typed': набрано},
                content_type='application/json',
            )
            self.assertEqual(ответ.json()['верно'], ожидаем, набрано)

    def test_способ_вопроса_выбирает_человек(self):
        """Колода его не назначает: три кнопки есть на самой странице занятия."""
        self.client.force_login(self.автор)
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        разметка = ответ.content.decode('utf-8')
        for способ in ('flip', 'choice', 'typed'):
            self.assertIn('data-способ="%s"' % способ, разметка)
        # И честное предупреждение, когда собрать варианты не из чего.
        self.assertIn('Не из чего собрать варианты', разметка)
        self.assertNotIn('вид', ответ.context['задания'][0])

    def test_список_колод_считает_и_новые_карточки(self):
        """Пока карточку никуда не положили, она числится неразобранной."""
        self.client.force_login(self.автор)
        ответ = self.client.get(reverse('cards:list'))
        колода = ответ.context['мои'][0]
        self.assertEqual(колода.неразобрано, 1)
        self.assertEqual(колода.трудных, 0)

        CardState.objects.create(
            user=self.автор, card=self.колода.cards.get(),
            direction=CardState.ПРЯМОЕ, section=CardState.ТРУДНО,
        )
        ответ = self.client.get(reverse('cards:list'))
        self.assertEqual(ответ.context['мои'][0].неразобрано, 0)
        self.assertEqual(ответ.context['мои'][0].трудных, 1)

    def test_правило_открыто_без_входа(self):
        ответ = self.client.get(reverse('cards:prompt'))
        self.assertEqual(ответ.status_code, 200)
        self.assertContains(ответ, 'лицевая сторона | оборотная сторона')


class ФормаЧисла(TestCase):
    """Django-фильтр pluralize умеет только две формы и на трёх молча даёт пустую строку."""

    def test_три_формы(self):
        КАРТОЧКИ = 'карточка,карточки,карточек'
        for число, ожидаем in ((1, 'карточка'), (2, 'карточки'), (4, 'карточки'),
                               (5, 'карточек'), (11, 'карточек'), (12, 'карточек'),
                               (14, 'карточек'), (21, 'карточка'), (22, 'карточки'),
                               (25, 'карточек'), (0, 'карточек'), (101, 'карточка')):
            self.assertEqual(слово(число, КАРТОЧКИ), ожидаем, число)

    def test_мусор_на_входе_не_роняет_страницу(self):
        self.assertEqual(слово(None, 'а,б,в'), 'в')
        self.assertEqual(слово(3, 'штука'), 'штука')


class РежимыТренировки(TestCase):
    """Заучивание, тест и подбор.

    Ключевое свойство: режимы НИЧЕГО не пишут в расписание. Заучивание за один
    вечер и планирование на месяцы вперёд — разные задачи, и если тренировка
    начнёт двигать сроки, интервальное повторение перестанет работать.
    """

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(
            title='Термины', owner=self.user,
        )
        for i in range(8):
            Card.objects.create(deck=self.колода, front='вопрос %d' % i,
                                back='ответ %d' % i, order=i)
        self.client.force_login(self.user)

    def test_страницы_режимов_открываются(self):
        for имя in ('learn', 'test', 'match'):
            ответ = self.client.get(reverse('cards:%s' % имя, args=[self.колода.pk]))
            self.assertEqual(ответ.status_code, 200, имя)
            self.assertEqual(len(ответ.context['набор']), 8, имя)

    def test_режимы_не_трогают_расписание(self):
        for имя in ('learn', 'test', 'match'):
            self.client.get(reverse('cards:%s' % имя, args=[self.колода.pk]))
        карточка = self.колода.cards.first()
        self.client.post(
            reverse('cards:check', args=[self.колода.pk]),
            data={'card': карточка.pk, 'direction': 0, 'typed': 'ответ 0'},
            content_type='application/json',
        )
        self.assertEqual(CardState.objects.count(), 0)

    def test_мало_карточек_для_режима(self):
        мелкая = Deck.objects.create(title='Мелкая', owner=self.user)
        Card.objects.create(deck=мелкая, front='а', back='б')
        ответ = self.client.get(reverse('cards:match', args=[мелкая.pk]))
        self.assertFalse(ответ.context['хватает'])
        ответ = self.client.get(reverse('cards:learn', args=[мелкая.pk]))
        self.assertFalse(ответ.context['хватает'])       # для заучивания нужно две
        self.assertFalse(ответ.context['есть_выбор'])    # и четыре для вариантов

    def test_тест_идёт_целиком_и_одним_видом(self):
        """Раньше тест шёл стопками по семь и мешал выбор с вводом в одной
        стопке. Так делать нельзя: человек каждый раз заново соображает, что
        от него хотят, и сравнивать такие результаты между собой нельзя."""
        разметка = self.client.get(
            reverse('cards:test', args=[self.колода.pk])).content.decode()
        self.assertNotIn('В_СТОПКЕ', разметка)
        self.assertNotIn('Следующая стопка', разметка)
        # Вид выбирается один раз на весь тест.
        self.assertIn('Начать тест', разметка)

    def test_заучивание_идёт_раундами_без_прогресса(self):
        """Раунд вместо полного прогона по колоде, и никакого счёта выученного:
        заучивание — это прогон, а не зачёт."""
        ответ = self.client.get(reverse('cards:learn', args=[self.колода.pk]))
        self.assertEqual(ответ.context['размер_раунда'],
                         self.колода.round_size)
        разметка = ответ.content.decode()
        self.assertIn('Следующий раунд', разметка)
        # Слова берём точные: «полоса» встречается и в общем шаблоне сайта.
        for пропавшее in ('Выучено', 'Осталось выучить', 'id="полоса"',
                          'Следующий прогон'):
            self.assertNotIn(пропавшее, разметка,
                             'прогресс должен был уйти из заучивания')

    def test_пачка_ответов_проверяется_разом(self):
        карточки = list(self.колода.cards.all()[:3])
        ответ = self.client.post(
            reverse('cards:check_many', args=[self.колода.pk]),
            data={'ответы': [
                {'card': карточки[0].pk, 'direction': 0, 'typed': 'ответ 0'},
                {'card': карточки[1].pk, 'direction': 0, 'typed': 'ответ 1 '},
                {'card': карточки[2].pk, 'direction': 0, 'typed': 'чепуха'},
            ]},
            content_type='application/json',
        )
        итог = ответ.json()['ответы']
        self.assertEqual([п['верно'] for п in итог], [True, True, False])
        self.assertEqual(итог[2]['эталон'], 'ответ 2')

    def test_пачка_не_принимает_мусор(self):
        ответ = self.client.post(
            reverse('cards:check_many', args=[self.колода.pk]),
            data={'ответы': 'не список'}, content_type='application/json',
        )
        self.assertEqual(ответ.status_code, 400)

    def test_чужая_карточка_в_пачке_не_раскрывается(self):
        """Ответы чужой колоды нельзя вытащить, подсунув её id."""
        чужак = User.objects.create_user('чужак', 'пароль')
        секрет = Deck.objects.create(title='Секрет', owner=чужак)
        карточка = Card.objects.create(deck=секрет, front='тайна', back='разгадка')
        ответ = self.client.post(
            reverse('cards:check_many', args=[self.колода.pk]),
            data={'ответы': [{'card': карточка.pk, 'direction': 0, 'typed': 'x'}]},
            content_type='application/json',
        )
        итог = ответ.json()['ответы'][0]
        self.assertFalse(итог['верно'])
        self.assertEqual(итог['эталон'], '')

    def test_колода_по_ссылке_тренируется_без_входа(self):
        self.client.logout()
        карточка = self.колода.cards.first()
        self.client.get(reverse('cards:deck', args=[self.колода.pk]),
                        {'k': self.колода.share_token})
        for имя in ('learn', 'test', 'match'):
            ответ = self.client.get(reverse('cards:%s' % имя, args=[self.колода.pk]))
            self.assertEqual(ответ.status_code, 200, имя)
        ответ = self.client.post(
            reverse('cards:check', args=[self.колода.pk]),
            data={'card': карточка.pk, 'direction': 0, 'typed': 'ответ 0'},
            content_type='application/json',
        )
        self.assertTrue(ответ.json()['верно'])


class НеверныеВариантыВРазборе(TestCase):
    """Столбцы с восклицательным знаком — заведомо неверные ответы."""

    def test_сколько_угодно_неверных(self):
        карточки, _ = разобрать(
            'Столица Франции | Париж | !Лион | !Марсель | !Бордо | !Ницца'
        )
        self.assertEqual(карточки[0]['distractors'].splitlines(),
                         ['Лион', 'Марсель', 'Бордо', 'Ницца'])

    def test_подсказка_и_неверные_в_любом_порядке(self):
        карточки, _ = разобрать('Вопрос | Ответ | !Мимо | пояснение | !Тоже мимо')
        self.assertEqual(карточки[0]['hint'], 'пояснение')
        self.assertEqual(карточки[0]['distractors'].splitlines(), ['Мимо', 'Тоже мимо'])

    def test_отрицательное_число_остаётся_числом(self):
        """Метка — восклицание, а не минус: иначе половина ответов по математике
        превратилась бы в неверные варианты."""
        карточки, _ = разобрать('2 + 2 | 4 | !5 | !-4')
        self.assertEqual(карточки[0]['back'], '4')
        self.assertEqual(карточки[0]['distractors'].splitlines(), ['5', '-4'])

    def test_без_верного_ответа_строка_не_принимается(self):
        карточки, замечания = разобрать('Вопрос | !только неверный')
        self.assertEqual(карточки, [])
        self.assertTrue(any('верного ответа нет' in з for з in замечания))

    def test_обычная_карточка_без_вариантов(self):
        карточки, _ = разобрать('Синус | отношение')
        self.assertEqual(карточки[0]['distractors'], '')


class ОбратныеКарточки(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(
            title='Слова', owner=self.user, reverse_enabled=True,
        )
        for i in range(4):
            Card.objects.create(deck=self.колода, front='词%d' % i,
                                back='слово %d' % i, order=i)
        self.client.force_login(self.user)

    def test_режимы_видят_обе_стороны(self):
        ответ = self.client.get(reverse('cards:learn', args=[self.колода.pk]))
        набор = ответ.context['набор']
        self.assertEqual(len(набор), 8)
        self.assertEqual({з['direction'] for з in набор}, {0, 1})
        self.assertEqual(len({з['ключ'] for з in набор}), 8)

    def test_обратная_сторона_спрашивает_оборот(self):
        ответ = self.client.get(reverse('cards:learn', args=[self.колода.pk]))
        прямое = [з for з in ответ.context['набор'] if з['direction'] == 0][0]
        обратное = [з for з in ответ.context['набор']
                    if з['direction'] == 1 and з['card'] == прямое['card']][0]
        self.assertEqual(прямое['вопрос'], обратное['ответ'])
        self.assertEqual(прямое['ответ'], обратное['вопрос'])

    def test_без_обратных_карточек_сторона_одна(self):
        self.колода.reverse_enabled = False
        self.колода.save()
        ответ = self.client.get(reverse('cards:learn', args=[self.колода.pk]))
        self.assertEqual(len(ответ.context['набор']), 4)


class ВариантыОтвета(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(
            title='География', owner=self.user,
        )
        self.карточка = Card.objects.create(
            deck=self.колода, front='Столица Франции', back='Париж',
            distractors='Лион\nМарсель\nБордо',
        )
        for i in range(5):
            Card.objects.create(deck=self.колода, front='Вопрос %d' % i,
                                back='Ответ %d' % i, order=i + 1)
        self.client.force_login(self.user)

    def _варианты(self):
        все = list(self.колода.cards.all())
        return views.варианты_выбора(self.колода, self.карточка,
                                     CardState.ПРЯМОЕ, все)

    def test_сначала_свои_неверные(self):
        """Своя правдоподобная ошибка проверяет больше, чем ответ из чужой темы."""
        варианты = self._варианты()
        self.assertEqual(len(варианты), 4)
        self.assertIn('Париж', варианты)
        self.assertEqual(set(варианты) - {'Париж'}, {'Лион', 'Марсель', 'Бордо'})

    def test_добор_чужими_ответами(self):
        self.карточка.distractors = 'Лион'
        self.карточка.save()
        варианты = self._варианты()
        self.assertEqual(len(варианты), 4)
        self.assertIn('Париж', варианты)
        self.assertIn('Лион', варианты)

    def test_верный_ответ_не_дублируется_в_вариантах(self):
        self.карточка.distractors = 'Париж\nЛион'
        self.карточка.save()
        варианты = self._варианты()
        self.assertEqual(варианты.count('Париж'), 1)

    def test_в_обратную_сторону_свои_неверные_не_годятся(self):
        """Они написаны к обороту; в обратную сторону спрашивают лицевую."""
        все = list(self.колода.cards.all())
        варианты = views.варианты_выбора(self.колода, self.карточка,
                                         CardState.ОБРАТНОЕ, все)
        self.assertIn('Столица Франции', варианты)
        self.assertNotIn('Лион', варианты)

    def test_мало_карточек_вариантов_нет(self):
        крошка = Deck.objects.create(title='Крошка', owner=self.user)
        Card.objects.create(deck=крошка, front='а', back='б')
        ответ = self.client.get(reverse('cards:study', args=[крошка.pk]))
        self.assertLess(len(ответ.context['задания'][0]['варианты']), 2)

    def test_варианты_приходят_на_страницу_повторения(self):
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        задание = [з for з in ответ.context['задания']
                   if з['card'] == self.карточка.pk][0]
        self.assertIn(задание['ответ'], задание['варианты'])
        self.assertTrue(задание['свои_неверные'])


class Самопроверка(TestCase):
    """Ученик пишет ответ, видит верный и сам решает, был ли прав."""

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(
            title='Определения', owner=self.user,
            check_mode=Deck.САМ,
        )
        Card.objects.create(deck=self.колода, front='Медиана',
                            back='отрезок от вершины к середине стороны')
        self.client.force_login(self.user)

    def test_страница_знает_кто_проверяет(self):
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        разметка = ответ.content.decode('utf-8')
        self.assertIn("ПРОВЕРЯЕТ = 'self'", разметка)
        self.assertIn('id="сам-решает"', разметка)

    def test_тест_не_предлагает_ввод_при_самопроверке(self):
        """Самопроверка по каждому из семи вопросов — это не тест."""
        ответ = self.client.get(reverse('cards:test', args=[self.колода.pk]))
        self.assertFalse(ответ.context['можно_вводить'])

        self.колода.check_mode = Deck.АВТОМАТ
        self.колода.save()
        ответ = self.client.get(reverse('cards:test', args=[self.колода.pk]))
        self.assertTrue(ответ.context['можно_вводить'])


class ЧисткаРазметки(TestCase):
    """Форматирование в карточках — это та же дверь, через которую заходит скрипт.

    Содержимое пишут ученики, колоды бывают общими, а показывается оно теперь
    как разметка. Поэтому чистка на входе — не украшение, а условие.
    """

    def test_начертания_остаются(self):
        self.assertEqual(очистить('<b>Париж</b>'), '<b>Париж</b>')
        self.assertEqual(очистить('<strong>Париж</strong>'), '<b>Париж</b>')
        self.assertEqual(очистить('<em>Париж</em>'), '<i>Париж</i>')
        self.assertEqual(очистить('<u>Париж</u>'), '<u>Париж</u>')

    def test_скрипт_и_обработчики_не_проходят(self):
        for опасное in (
            '<script>alert(1)</script>Париж',
            '<img src=x onerror=alert(1)>Париж',
            '<b onclick="alert(1)">Париж</b>',
            '<a href="javascript:alert(1)">Париж</a>',
            '<iframe src="//зло"></iframe>Париж',
            '<svg/onload=alert(1)>Париж',
        ):
            вышло = очистить(опасное)
            self.assertNotIn('script', вышло.lower(), опасное)
            self.assertNotIn('onerror', вышло.lower(), опасное)
            self.assertNotIn('onclick', вышло.lower(), опасное)
            self.assertNotIn('javascript', вышло.lower(), опасное)
            self.assertIn('Париж', вышло, опасное)

    def test_цвет_только_настоящий(self):
        вышло = очистить('<span style="color: #ff0000">красный</span>')
        self.assertEqual(вышло, '<span style="color: #ff0000">красный</span>')

        # Оформление — известный способ вернуть выполнение кода.
        for мусор in ('expression(alert(1))', 'url(//зло)'):
            вышло = очистить('<span style="color: %s">текст</span>' % мусор)
            self.assertEqual(вышло, 'текст', мусор)

        # Годное свойство рядом с негодным: style собирается заново из
        # разрешённого, поэтому цвет остаётся, а лишнее не проходит.
        вышло = очистить('<span style="color: red; behavior: url(#)">текст</span>')
        self.assertEqual(вышло, '<span style="color: red">текст</span>')

    def test_чужие_свойства_оформления_выбрасываются(self):
        вышло = очистить('<span style="color: red; position: fixed; width: 9999px">x</span>')
        self.assertIn('color: red', вышло)
        self.assertNotIn('position', вышло)
        self.assertNotIn('width', вышло)

    def test_старый_тег_font_превращается_в_span(self):
        self.assertEqual(очистить('<font color="red">текст</font>'),
                         '<span style="color: red">текст</span>')

    def test_переносы_приводятся_к_обычным(self):
        """Один вид хранения на все браузеры: contenteditable выдаёт то br, то div."""
        self.assertEqual(очистить('первая<br>вторая'), 'первая\nвторая')
        self.assertEqual(очистить('первая<div>вторая</div>'), 'первая\nвторая')
        self.assertEqual(очистить('<p>первая</p><p>вторая</p>'), 'первая\nвторая')

    def test_угловые_скобки_в_тексте_остаются_видимыми(self):
        self.assertEqual(очистить('a < b и 5 > 3'), 'a &lt; b и 5 &gt; 3')

    def test_пустые_теги_убираются(self):
        self.assertEqual(очистить('<b></b><span style="color: red"></span>'), '')

    def test_текстом_снимает_разметку(self):
        self.assertEqual(текстом('<b>Па</b><i>риж</i>'), 'Париж')
        self.assertEqual(текстом('a &lt; b'), 'a < b')

    def test_чистка_срабатывает_при_записи(self):
        """Забыть про чистку в шаблоне легко, в save() — нет."""
        ученик = User.objects.create_user('ученик', 'пароль')
        колода = Deck.objects.create(title='К', owner=ученик)
        карточка = Card.objects.create(
            deck=колода,
            front='<script>alert(1)</script><b>Столица</b>',
            back='<img src=x onerror=alert(1)>Париж',
            hint='<b onclick="alert(1)">на Сене</b>',
            distractors='<script>x</script>Лион\n<b>Марсель</b>',
        )
        карточка.refresh_from_db()
        self.assertEqual(карточка.front, '<b>Столица</b>')
        self.assertEqual(карточка.back, 'Париж')
        self.assertEqual(карточка.hint, '<b>на Сене</b>')
        self.assertEqual(карточка.неверные(), ['Лион', '<b>Марсель</b>'])

    def test_массовое_добавление_тоже_чистится(self):
        """bulk_create идёт мимо save() — самая вероятная дыра."""
        автор = User.objects.create_user('автор', 'пароль')
        колода = Deck.objects.create(title='К', owner=автор)
        self.client.force_login(автор)
        self.client.post(
            reverse('cards:import', args=[колода.pk]),
            {'текст': '<script>alert(1)</script>Вопрос | <b>Ответ</b> | !<script>x</script>Мимо',
             'сохранить': '1'},
        )
        карточка = колода.cards.get()
        self.assertNotIn('script', карточка.front.lower())
        self.assertEqual(карточка.back, '<b>Ответ</b>')
        self.assertEqual(карточка.неверные(), ['Мимо'])

    def test_проверка_ответа_не_видит_разметки(self):
        """Ученик набирает «Париж», а в базе может лежать «<b>Париж</b>»."""
        автор = User.objects.create_user('автор', 'пароль')
        колода = Deck.objects.create(title='К', owner=автор)
        карточка = Card.objects.create(deck=колода, front='Столица',
                                       back='<b>Париж</b>')
        self.client.force_login(автор)
        ответ = self.client.post(
            reverse('cards:check', args=[колода.pk]),
            data={'card': карточка.pk, 'direction': 0, 'typed': 'Париж'},
            content_type='application/json',
        )
        self.assertTrue(ответ.json()['верно'])
        self.assertEqual(ответ.json()['эталон'], 'Париж')


class ПростойРедактор(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('автор', 'пароль')
        self.client.force_login(self.user)

    def _карточки(self, *пары):
        return json.dumps([
            {'id': п[0], 'front': п[1], 'back': п[2], 'hint': п[3] if len(п) > 3 else ''}
            for п in пары
        ])

    def test_создание_колоды_вместе_с_карточками(self):
        ответ = self.client.post(reverse('cards:create'), {
            'title': 'Столицы', 'description': 'проба',
            'карточки': self._карточки(
                (None, '<b>Франция</b>', 'Париж', 'на Сене'),
                (None, 'Япония', 'Токио'),
            ),
        })
        self.assertEqual(ответ.status_code, 302)
        колода = Deck.objects.get(title='Столицы')
        self.assertEqual(колода.owner, self.user)
        self.assertEqual(колода.cards.count(), 2)
        первая = колода.cards.first()
        self.assertEqual(первая.front, '<b>Франция</b>')
        self.assertEqual(первая.hint, 'на Сене')

    def test_пустые_строки_не_становятся_карточками(self):
        self.client.post(reverse('cards:create'), {
            'title': 'Колода', 'карточки': self._карточки(
                (None, 'Вопрос', 'Ответ'),
                (None, '', ''),
                (None, '<b></b>', '   '),
            ),
        })
        self.assertEqual(Deck.objects.get(title='Колода').cards.count(), 1)

    def test_колода_без_карточек_не_создаётся(self):
        ответ = self.client.post(reverse('cards:create'), {
            'title': 'Пустая', 'карточки': '[]',
        })
        self.assertEqual(ответ.status_code, 200)
        self.assertFalse(Deck.objects.filter(title='Пустая').exists())
        self.assertIn('хотя бы одну', ответ.context['ошибка'])

    def test_битые_данные_не_роняют_страницу(self):
        ответ = self.client.post(reverse('cards:create'), {
            'title': 'Колода', 'карточки': 'не json',
        })
        self.assertEqual(ответ.status_code, 200)
        self.assertTrue(ответ.context['ошибка'])
        self.assertFalse(Deck.objects.exists())

    def test_правка_сохраняет_прогресс_ученика(self):
        """Карточки обновляются по номеру, а не пересоздаются.

        Пересоздание удалило бы вместе с карточкой то, ради чего ученик и
        сидел над колодой: раскладку по секциям.
        """
        колода = Deck.objects.create(title='Слова', owner=self.user)
        карточка = Card.objects.create(deck=колода, front='старое', back='ответ')
        CardState.objects.create(
            user=self.user, card=карточка, direction=CardState.ПРЯМОЕ,
            section=CardState.СЛОЖНО,
        )

        self.client.post(reverse('cards:edit_cards', args=[колода.pk]), {
            'title': 'Слова', 'description': '',
            'карточки': self._карточки((карточка.pk, 'новое', 'ответ')),
        })

        карточка.refresh_from_db()
        self.assertEqual(карточка.front, 'новое')
        self.assertEqual(CardState.objects.filter(card=карточка).count(), 1)
        self.assertEqual(CardState.objects.get(card=карточка).section,
                         CardState.СЛОЖНО)

    def test_убранная_из_редактора_карточка_удаляется(self):
        колода = Deck.objects.create(title='Слова', owner=self.user)
        первая = Card.objects.create(deck=колода, front='а', back='1', order=0)
        вторая = Card.objects.create(deck=колода, front='б', back='2', order=1)

        self.client.post(reverse('cards:edit_cards', args=[колода.pk]), {
            'title': 'Слова', 'description': '',
            'карточки': self._карточки((вторая.pk, 'б', '2')),
        })
        self.assertEqual(list(колода.cards.values_list('pk', flat=True)), [вторая.pk])
        self.assertFalse(Card.objects.filter(pk=первая.pk).exists())

    def test_порядок_берётся_из_редактора(self):
        колода = Deck.objects.create(title='Слова', owner=self.user)
        первая = Card.objects.create(deck=колода, front='а', back='1', order=0)
        вторая = Card.objects.create(deck=колода, front='б', back='2', order=1)

        self.client.post(reverse('cards:edit_cards', args=[колода.pk]), {
            'title': 'Слова', 'description': '',
            'карточки': self._карточки((вторая.pk, 'б', '2'), (первая.pk, 'а', '1')),
        })
        self.assertEqual(list(колода.cards.values_list('front', flat=True)), ['б', 'а'])

    def test_чужой_номер_карточки_не_утаскивает_чужую(self):
        чужак = User.objects.create_user('чужак', 'пароль')
        чужая_колода = Deck.objects.create(title='Чужая', owner=чужак)
        чужая = Card.objects.create(deck=чужая_колода, front='секрет', back='ответ')

        своя = Deck.objects.create(title='Своя', owner=self.user)
        self.client.post(reverse('cards:edit_cards', args=[своя.pk]), {
            'title': 'Своя', 'description': '',
            'карточки': self._карточки((чужая.pk, 'подмена', 'подмена')),
        })
        чужая.refresh_from_db()
        self.assertEqual(чужая.front, 'секрет')
        self.assertEqual(чужая.deck, чужая_колода)
        self.assertEqual(своя.cards.count(), 1)

    def test_чужую_колоду_править_нельзя(self):
        чужак = User.objects.create_user('чужак', 'пароль')
        колода = Deck.objects.create(title='Чужая', owner=чужак)
        ответ = self.client.get(reverse('cards:edit_cards', args=[колода.pk]))
        self.assertEqual(ответ.status_code, 404)

    def test_подробный_путь_остался_отдельно(self):
        ответ = self.client.get(reverse('cards:create_full'))
        self.assertEqual(ответ.status_code, 200)
        self.assertIn('check_mode', ответ.context['форма'].fields)
        # А простой — без настроек: в этом весь смысл.
        простой = self.client.get(reverse('cards:create'))
        self.assertEqual(list(простой.context['форма'].fields), ['title', 'description'])



class РазборБезКолоды(TestCase):
    """Вставить список хочется ещё до того, как колода создана."""

    def setUp(self):
        self.user = User.objects.create_user('автор', 'пароль')
        self.client.force_login(self.user)

    def _разобрать(self, текст):
        return self.client.post(
            reverse('cards:parse'), data={'текст': текст},
            content_type='application/json',
        )

    def test_возвращает_карточки_и_ничего_не_создаёт(self):
        ответ = self._разобрать(
            'Столица Франции | Париж | !Лион | !Марсель | город на Сене\n'
            'Столица Японии | Токио'
        )
        данные = ответ.json()
        self.assertEqual(len(данные['карточки']), 2)
        self.assertEqual(данные['карточки'][0]['distractors'], 'Лион\nМарсель')
        self.assertEqual(данные['карточки'][0]['hint'], 'город на Сене')
        self.assertEqual(Card.objects.count(), 0)
        self.assertEqual(Deck.objects.count(), 0)

    def test_замечания_доезжают(self):
        данные = self._разобрать('Конечно! Вот список:\nСинус | отношение').json()
        self.assertEqual(len(данные['карточки']), 1)
        self.assertTrue(данные['замечания'])

    def test_разметка_чистится_и_здесь(self):
        данные = self._разобрать('<script>alert(1)</script>Вопрос | <b>Ответ</b>').json()
        self.assertNotIn('script', данные['карточки'][0]['front'].lower())
        self.assertEqual(данные['карточки'][0]['back'], '<b>Ответ</b>')

    def test_гостю_разбор_недоступен(self):
        self.client.logout()
        ответ = self._разобрать('Вопрос | Ответ')
        self.assertIn(ответ.status_code, (302, 403, 404))

    def test_огромный_кусок_отвергается(self):
        ответ = self._разобрать('а | б\n' * 40000)
        self.assertEqual(ответ.status_code, 400)


class НеверныеВариантыВРедакторе(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('автор', 'пароль')
        self.client.force_login(self.user)

    def test_сохраняются_из_редактора(self):
        self.client.post(reverse('cards:create'), {
            'title': 'Столицы',
            'карточки': json.dumps([{
                'id': None, 'front': 'Столица Франции', 'back': 'Париж',
                'hint': '', 'distractors': 'Лион\nМарсель\nБордо',
            }]),
        })
        карточка = Deck.objects.get(title='Столицы').cards.get()
        self.assertEqual(карточка.неверные(), ['Лион', 'Марсель', 'Бордо'])

    def test_возвращаются_в_редактор_при_правке(self):
        колода = Deck.objects.create(title='Столицы', owner=self.user)
        Card.objects.create(deck=колода, front='а', back='б', distractors='в\nг')
        ответ = self.client.get(reverse('cards:edit_cards', args=[колода.pk]))
        self.assertEqual(ответ.context['карточки_json'][0]['distractors'], 'в\nг')

    def test_поле_есть_в_разметке_редактора(self):
        ответ = self.client.get(reverse('cards:create'))
        разметка = ответ.content.decode('utf-8')
        self.assertIn('data-поле="distractors"', разметка)
        # И кнопка вставки списком — её не было, а список вставить хочется сразу.
        self.assertIn('кнопка-вставить', разметка)
        self.assertIn(reverse('cards:parse'), разметка)


class ПодсказкаДоОтвета(TestCase):
    """Подсказка, которую видно только после ответа, — не подсказка."""

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(title='Столицы', owner=self.user)
        Card.objects.create(deck=self.колода, front='Столица Франции',
                            back='Париж', hint='город на Сене')
        Card.objects.create(deck=self.колода, front='Столица Японии', back='Токио')
        self.client.force_login(self.user)

    def test_подсказка_приходит_с_заданием(self):
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        задания = ответ.context['задания']
        с_подсказкой = [з for з in задания if з['подсказка']]
        self.assertEqual(len(с_подсказкой), 1)
        self.assertEqual(с_подсказкой[0]['подсказка'], 'город на Сене')

    def test_кнопка_подсказки_есть_на_обоих_экранах(self):
        for имя in ('study', 'learn'):
            разметка = self.client.get(
                reverse('cards:%s' % имя, args=[self.колода.pk])
            ).content.decode('utf-8')
            self.assertIn('id="кнопка-подсказки"', разметка, имя)


class СвоиОкнаВместоСистемных(TestCase):
    """Системное окно браузера подписано «Сайт сообщает…» и пугает ученика."""

    def setUp(self):
        self.user = User.objects.create_user('автор', 'пароль')
        self.колода = Deck.objects.create(title='Колода', owner=self.user)
        Card.objects.create(deck=self.колода, front='а', back='б')
        self.client.force_login(self.user)

    def test_в_разделе_не_осталось_системных_окон(self):
        адреса = [
            reverse('cards:deck', args=[self.колода.pk]),
            reverse('cards:edit', args=[self.колода.pk]),
            reverse('cards:edit_cards', args=[self.колода.pk]),
            reverse('cards:create'),
        ]
        for адрес in адреса:
            разметка = self.client.get(адрес).content.decode('utf-8')
            self.assertNotIn('confirm(', разметка, адрес)
            self.assertNotIn('alert(', разметка, адрес)

    def test_удаление_подтверждается_своим_окном(self):
        разметка = self.client.get(
            reverse('cards:deck', args=[self.колода.pk])).content.decode('utf-8')
        self.assertIn('data-спросить=', разметка)
        self.assertIn('data-опасно', разметка)

    def test_компонент_окон_подключён_на_всех_страницах(self):
        разметка = self.client.get(reverse('cards:list')).content.decode('utf-8')
        self.assertIn('js/ui_dialog.js', разметка)



class ЗабытаяПометкаВарианта(TestCase):
    """Забытый восклицательный знак опаснее потерянного варианта.

    Непомеченный столбец становится ПОДСКАЗКОЙ — и неверный ответ показывается
    ученику как помощь. Отличить забытую пометку от законной подсказки разбор не
    может, поэтому не отказывает, а говорит вслух.
    """

    def test_обычная_подсказка_не_вызывает_замечаний(self):
        карточки, замечания = разобрать('Столица Франции | Париж | город на Сене')
        self.assertEqual(карточки[0]['hint'], 'город на Сене')
        self.assertFalse(замечания)

    def test_смешанные_пометки_в_строке(self):
        """Один вариант помечен, второй нет — почти наверняка забыли знак."""
        карточки, замечания = разобрать('Столица Франции | Париж | !Лион | Марсель')
        # Поведение прежнее: ничего не теряется и не переставляется.
        self.assertEqual(карточки[0]['distractors'], 'Лион')
        self.assertEqual(карточки[0]['hint'], 'Марсель')
        self.assertEqual(len(замечания), 1)
        self.assertIn('Марсель', замечания[0])
        self.assertIn('без восклицательного знака', замечания[0])

    def test_два_и_более_непомеченных_столбца(self):
        """Подсказку почти никто не разбивает на части, а список вариантов — да."""
        карточки, замечания = разобрать('Столица Франции | Париж | Лион | Марсель')
        self.assertEqual(карточки[0]['hint'], 'Лион · Марсель')
        self.assertEqual(len(замечания), 1)
        self.assertIn('склеены в одну подсказку', замечания[0])

    def test_три_и_более_тоже_замечаются(self):
        _, замечания = разобрать('A | 1 | Лион | Марсель | Бордо')
        self.assertEqual(len(замечания), 1)
        self.assertIn('3 столбца', замечания[0])

    def test_строка_выбившаяся_из_размеченного_списка(self):
        """Если варианты помечены у большинства, непомеченная строка выбивается."""
        _, замечания = разобрать('A | 1 | !x | !y\n'
                                 'B | 2 | !x | !y\n'
                                 'C | 3 | z')
        self.assertEqual(len(замечания), 1)
        self.assertIn('Строка 3', замечания[0])
        self.assertIn('в остальных строках варианты помечены', замечания[0])

    def test_список_из_одних_подсказок_молчит(self):
        """Третий столбец задуман подсказкой — ругаться на него было бы вредно."""
        _, замечания = разобрать('A | 1 | пример\nB | 2 | пример\nC | 3 | пример')
        self.assertFalse(замечания)

    def test_редкий_вариант_среди_подсказок_не_делает_их_подозрительными(self):
        _, замечания = разобрать('A | 1 | !x\n'
                                 'B | 2 | пример\n'
                                 'C | 3 | пример\n'
                                 'D | 4 | пример')
        self.assertFalse(замечания)

    def test_однотипные_замечания_сворачиваются(self):
        """Список на полсотни строк не должен утонуть в одинаковых строчках."""
        текст = '\n'.join('A%d | %d | x | y' % (i, i) for i in range(12))
        _, замечания = разобрать(текст)
        self.assertLessEqual(len(замечания), 6)
        self.assertTrue(any('и ещё' in з for з in замечания))

    def test_карточки_всё_равно_создаются(self):
        """Замечание — это предупреждение, а не отказ: строка остаётся карточкой."""
        карточки, замечания = разобрать('A | 1 | Лион | Марсель')
        self.assertEqual(len(карточки), 1)
        self.assertTrue(замечания)



class ЦенаСтраницы(TestCase):
    """Сколько запросов к базе стоит страница повторения.

    Проверка не на скорость, а на УСТРОЙСТВО: число запросов не должно расти
    вместе с колодой. Такое ломается тихо — на десяти карточках незаметно, а у
    ученика с двумя сотнями страница встаёт, и модульные тесты этого не видят,
    потому что содержимое-то верное.

    Так уже было: предпросмотр кнопок строил планировщик по четыре раза на
    карточку, и каждый лез в базу за личными весами ученика. Десять карточек
    стоили 51 запроса, двести — 91.
    """

    ПРЕДЕЛ = 25

    def setUp(self):
        self.ученик = User.objects.create_user('ученик', 'пароль')
        self.client.force_login(self.ученик)

    def _колода(self, сколько, название):
        колода = Deck.objects.create(title=название, owner=self.ученик)
        Card.objects.bulk_create([
            Card(deck=колода, front='Вопрос %d' % i, back='Ответ %d' % i)
            for i in range(сколько)
        ])
        return колода

    def _сколько_запросов(self, колода):
        адрес = reverse('cards:study', args=[колода.pk])
        with CaptureQueriesContext(connection) as запросы:
            ответ = self.client.get(адрес)
        self.assertEqual(ответ.status_code, 200)
        return len(запросы)

    def test_число_запросов_не_растёт_с_колодой(self):
        мало = self._сколько_запросов(self._колода(5, 'Маленькая'))
        много = self._сколько_запросов(self._колода(60, 'Большая'))
        self.assertEqual(
            мало, много,
            'страница повторения делает %d запросов на 5 карточках и %d на 60 — '
            'значит, запрос уходит в цикле' % (мало, много))
        self.assertLess(мало, self.ПРЕДЕЛ,
                        'запросов и так многовато: %d' % мало)
