# -*- coding: utf-8 -*-
"""Проверки раздела карточек.

Главное внимание — разбору вставленного текста и планировщику. Это два места,
где ошибка тихая: разбор молча потеряет половину списка, планировщик молча
назначит повторение не туда, и заметить это по внешнему виду нельзя.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import User

from . import srs, views
from .ai_prompt import собрать
from .models import Card, CardReview, CardState, Deck, SchedulerWeights
from .parsing import разобрать
from .templatetags.cards_extras import колоды_урока, слово


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


class Планировщик(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(title='Формулы', owner=self.user)
        self.карточка = Card.objects.create(
            deck=self.колода, front='Площадь круга', back='$\\pi R^2$',
        )

    def _состояние(self):
        return srs.состояние_для(self.user, self.карточка, CardState.ПРЯМОЕ)

    def test_оценка_двигает_срок_и_пишет_журнал(self):
        состояние = self._состояние()
        было = состояние.due
        состояние, срок = srs.оценить(состояние, 3, длительность=1500)
        self.assertGreater(срок, было)
        self.assertEqual(состояние.reps, 1)
        self.assertIsNotNone(состояние.started_at)
        журнал = CardReview.objects.get()
        self.assertEqual(журнал.rating, 3)
        self.assertEqual(журнал.duration_ms, 1500)

    def test_на_кнопках_четыре_срока_и_они_растут(self):
        кнопки = srs.предпросмотр(self._состояние())
        self.assertEqual(sorted(кнопки), [1, 2, 3, 4])
        self.assertTrue(all(кнопки.values()))

    def test_дата_экзамена_ограничивает_интервал(self):
        """Без потолка интервалы дорастают до десятков лет — для экзамена это бессмыслица."""
        self.колода.exam_date = timezone.localdate() + timedelta(days=30)
        self.колода.save()
        состояние = self._состояние()
        for _ in range(8):
            состояние, срок = srs.оценить(состояние, 4)
            состояние.due = timezone.now()      # как будто ученик пришёл вовремя
        предел = timezone.now() + timedelta(days=31)
        self.assertLess(срок, предел)

    def test_трудно_не_держит_карточку_в_изучении_вечно(self):
        """Оценка «Трудно» повторяет шаг обучения; после предела карточка выпускается."""
        состояние = self._состояние()
        for _ in range(srs.ПРЕДЕЛ_ШАГОВ + 1):
            состояние, срок = srs.оценить(состояние, 2)
            состояние.due = timezone.now()
        self.assertEqual(состояние.state, CardState.ПОВТОРЕНИЕ)

    def test_забывание_считается_отдельно(self):
        состояние = self._состояние()
        for _ in range(3):
            состояние, _ = srs.оценить(состояние, 4)
            состояние.due = timezone.now()
        self.assertEqual(состояние.state, CardState.ПОВТОРЕНИЕ)
        состояние, _ = srs.оценить(состояние, 1)
        self.assertEqual(состояние.lapses, 1)


class Очередь(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(
            title='Слова', owner=self.user, new_per_day=3,
        )
        for i in range(10):
            Card.objects.create(deck=self.колода, front='вопрос %d' % i,
                                back='ответ %d' % i, order=i)

    def test_дневной_потолок_новых(self):
        очередь = srs.очередь(self.user, self.колода)
        self.assertEqual(len(очередь), 3)

    def test_обратное_направление_удваивает_карточки(self):
        self.колода.reverse_enabled = True
        self.колода.new_per_day = 100
        self.колода.save()
        очередь = srs.очередь(self.user, self.колода)
        self.assertEqual(len(очередь), 20)

    def test_отложенная_карточка_не_показывается(self):
        карточка = self.колода.cards.first()
        CardState.objects.create(
            user=self.user, card=карточка, suspended=True,
            due=timezone.now() - timedelta(days=1),
        )
        показанные = {к.pk for к, _н, _с in srs.очередь(self.user, self.колода)}
        self.assertNotIn(карточка.pk, показанные)


class Страницы(TestCase):

    def setUp(self):
        self.автор = User.objects.create_user('автор', 'пароль')
        self.чужой = User.objects.create_user('чужой', 'пароль')
        self.колода = Deck.objects.create(title='Формулы', owner=self.автор)
        Card.objects.create(deck=self.колода, front='Площадь круга', back='pi R^2')

    def test_личная_колода_чужому_не_видна(self):
        self.client.force_login(self.чужой)
        ответ = self.client.get(reverse('cards:deck', args=[self.колода.pk]))
        self.assertEqual(ответ.status_code, 404)

    def test_общая_колода_видна_всем_вошедшим(self):
        self.колода.visibility = Deck.ОБЩАЯ
        self.колода.save()
        self.client.force_login(self.чужой)
        ответ = self.client.get(reverse('cards:deck', args=[self.колода.pk]))
        self.assertEqual(ответ.status_code, 200)

    def test_чужой_не_правит_карточки(self):
        self.колода.visibility = Deck.ОБЩАЯ
        self.колода.save()
        self.client.force_login(self.чужой)
        ответ = self.client.get(reverse('cards:import', args=[self.колода.pk]))
        self.assertEqual(ответ.status_code, 404)

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
        self.assertTrue(задания[0]['новая'])
        self.assertEqual(sorted(задания[0]['кнопки']), [1, 2, 3, 4])

    def test_ответ_записывается(self):
        self.client.force_login(self.автор)
        карточка = self.колода.cards.get()
        ответ = self.client.post(
            reverse('cards:answer', args=[self.колода.pk]),
            data={'card': карточка.pk, 'direction': 0, 'rating': 3,
                  'duration_ms': 2000},
            content_type='application/json',
        )
        self.assertEqual(ответ.status_code, 200)
        self.assertIn('пауза', ответ.json())
        self.assertEqual(CardReview.objects.count(), 1)

    def test_оценка_вне_шкалы_отклоняется(self):
        self.client.force_login(self.автор)
        карточка = self.колода.cards.get()
        ответ = self.client.post(
            reverse('cards:answer', args=[self.колода.pk]),
            data={'card': карточка.pk, 'rating': 9},
            content_type='application/json',
        )
        self.assertEqual(ответ.status_code, 400)

    def test_проверка_текстового_ответа_прощает_опечатку(self):
        колода = Deck.objects.create(
            title='Термины', owner=self.автор, kind=Deck.ТЕКСТ, ask_mode=Deck.ВВОД,
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
        колода = Deck.objects.create(
            title='Уравнения', owner=self.автор, kind=Deck.МАТЕМАТИКА,
            ask_mode=Deck.ВВОД,
        )
        карточка = Card.objects.create(deck=колода, front='2x = 5', back='2,5')
        self.client.force_login(self.автор)
        for набрано, ожидаем in (('2,5', True), ('2.5', True), ('3', False)):
            ответ = self.client.post(
                reverse('cards:check', args=[колода.pk]),
                data={'card': карточка.pk, 'direction': 0, 'typed': набрано},
                content_type='application/json',
            )
            self.assertEqual(ответ.json()['верно'], ожидаем, набрано)

    def test_способ_вопроса_приходит_с_карточкой(self):
        """Разметка на странице одна на все три способа, выбирает её вид карточки."""
        колода = Deck.objects.create(
            title='Термины', owner=self.автор, kind=Deck.ТЕКСТ, ask_mode=Deck.ВВОД,
        )
        Card.objects.create(deck=колода, front='вопрос', back='ответ')
        self.client.force_login(self.автор)

        ответ = self.client.get(reverse('cards:study', args=[колода.pk]))
        self.assertEqual(ответ.context['задания'][0]['вид'], 'typed')
        self.assertContains(ответ, reverse('cards:check', args=[колода.pk]))

        переворот = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        self.assertEqual(переворот.context['задания'][0]['вид'], 'flip')

    def test_список_колод_считает_и_новые_карточки(self):
        """Колода, где все карточки новые, не должна писать «на сегодня всё»."""
        self.client.force_login(self.автор)
        ответ = self.client.get(reverse('cards:list'))
        колода = ответ.context['мои'][0]
        self.assertEqual(колода.ждёт, 1)

        # После оценки карточка уходит в будущее, новых больше нет — пусто.
        состояние = srs.состояние_для(
            self.автор, self.колода.cards.get(), CardState.ПРЯМОЕ,
        )
        srs.оценить(состояние, 4)
        ответ = self.client.get(reverse('cards:list'))
        self.assertEqual(ответ.context['мои'][0].ждёт, 0)

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
            title='Термины', owner=self.user, kind=Deck.ТЕКСТ, ask_mode=Deck.ВВОД,
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
        self.assertEqual(CardReview.objects.count(), 0)

    def test_мало_карточек_для_режима(self):
        мелкая = Deck.objects.create(title='Мелкая', owner=self.user)
        Card.objects.create(deck=мелкая, front='а', back='б')
        ответ = self.client.get(reverse('cards:match', args=[мелкая.pk]))
        self.assertFalse(ответ.context['хватает'])
        ответ = self.client.get(reverse('cards:learn', args=[мелкая.pk]))
        self.assertFalse(ответ.context['хватает'])       # для заучивания нужно две
        self.assertFalse(ответ.context['есть_выбор'])    # и четыре для вариантов

    def test_число_вопросов_теста_не_больше_колоды(self):
        ответ = self.client.get(reverse('cards:test', args=[self.колода.pk]),
                                {'вопросов': 500})
        self.assertEqual(ответ.context['вопросов'], 8)
        ответ = self.client.get(reverse('cards:test', args=[self.колода.pk]),
                                {'вопросов': 'ерунда'})
        self.assertEqual(ответ.context['вопросов'], 8)

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

    def test_открытая_колода_тренируется_без_входа(self):
        self.client.logout()
        self.колода.visibility = Deck.ОТКРЫТАЯ
        self.колода.save()
        карточка = self.колода.cards.first()
        for имя in ('learn', 'test', 'match'):
            ответ = self.client.get(reverse('cards:%s' % имя, args=[self.колода.pk]))
            self.assertEqual(ответ.status_code, 200, имя)
        ответ = self.client.post(
            reverse('cards:check', args=[self.колода.pk]),
            data={'card': карточка.pk, 'direction': 0, 'typed': 'ответ 0'},
            content_type='application/json',
        )
        self.assertTrue(ответ.json()['верно'])


class Статистика(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(title='Формулы', owner=self.user)
        self.карточки = [
            Card.objects.create(deck=self.колода, front='в %d' % i,
                                back='о %d' % i, order=i)
            for i in range(5)
        ]
        self.client.force_login(self.user)

    def test_пустая_колода_показывает_всё_как_неначатое(self):
        ответ = self.client.get(reverse('cards:stats', args=[self.колода.pk]))
        self.assertEqual(ответ.status_code, 200)
        self.assertEqual(ответ.context['не_начато'], 5)
        self.assertEqual(ответ.context['закрепилось'], 0)
        self.assertEqual(ответ.context['всего_повторений'], 0)
        self.assertEqual(len(ответ.context['прогноз']), 14)
        self.assertEqual(len(ответ.context['активность']), 30)

    def test_прогноз_и_счётчики_после_занятия(self):
        состояние = srs.состояние_для(self.user, self.карточки[0], CardState.ПРЯМОЕ)
        srs.оценить(состояние, 3)
        ответ = self.client.get(reverse('cards:stats', args=[self.колода.pk]))
        self.assertEqual(ответ.context['не_начато'], 4)
        self.assertEqual(ответ.context['всего_повторений'], 1)
        # Карточка на шаге обучения возвращается сегодня же.
        self.assertEqual(ответ.context['прогноз'][0]['сколько'], 1)
        self.assertEqual(ответ.context['активность'][-1]['сколько'], 1)
        self.assertEqual(ответ.context['дней_подряд'], 1)

    def test_трудные_карточки_попадают_в_список(self):
        состояние = srs.состояние_для(self.user, self.карточки[0], CardState.ПРЯМОЕ)
        состояние.lapses = 4
        состояние.save()
        ответ = self.client.get(reverse('cards:stats', args=[self.колода.pk]))
        self.assertEqual(list(ответ.context['трудные']), [состояние])

    def test_чужая_статистика_недоступна(self):
        чужак = User.objects.create_user('чужак', 'пароль')
        self.client.force_login(чужак)
        ответ = self.client.get(reverse('cards:stats', args=[self.колода.pk]))
        self.assertEqual(ответ.status_code, 404)


class КолодыНаУроке(TestCase):

    def test_тег_отдаёт_только_видимые_колоды(self):
        from users.models import Course, Lesson, Module

        автор = User.objects.create_user('автор', 'пароль')
        чужак = User.objects.create_user('чужак', 'пароль')
        курс = Course.objects.create(title='Курс', slug='kurs')
        модуль = Module.objects.create(course=курс, title='Модуль', order=1)
        урок = Lesson.objects.create(module=модуль, title='Урок', order=1)

        своя = Deck.objects.create(title='Личная', owner=автор, lesson=урок)
        общая = Deck.objects.create(title='Общая', owner=автор, lesson=урок,
                                    visibility=Deck.ОБЩАЯ)
        Deck.objects.create(title='Без урока', owner=автор)

        свои = колоды_урока({'user': автор}, урок)['колоды']
        self.assertEqual({к.pk for к in свои}, {своя.pk, общая.pk})

        чужие = колоды_урока({'user': чужак}, урок)['колоды']
        self.assertEqual([к.pk for к in чужие], [общая.pk])


class ОтветыБезСети(TestCase):
    """Оценки, накопленные без связи, приходят пачкой позже.

    Считать интервал от момента доставки нельзя: FSRS смотрит, сколько прошло
    с прошлого показа, и поездка в метро сдвинула бы всё расписание.
    """

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(title='Формулы', owner=self.user)
        self.карточка = Card.objects.create(
            deck=self.колода, front='вопрос', back='ответ',
        )
        self.client.force_login(self.user)

    def _ответить(self, **лишнее):
        тело = {'card': self.карточка.pk, 'direction': 0, 'rating': 3}
        тело.update(лишнее)
        return self.client.post(
            reverse('cards:answer', args=[self.колода.pk]),
            data=тело, content_type='application/json',
        )

    def test_время_ответа_из_браузера_попадает_в_журнал(self):
        было = timezone.now() - timedelta(hours=3)
        ответ = self._ответить(when=было.isoformat())
        self.assertEqual(ответ.status_code, 200)
        запись = CardReview.objects.get()
        self.assertLess(abs((запись.reviewed_at - было).total_seconds()), 2)

    def test_время_из_будущего_не_принимается(self):
        вперёд = timezone.now() + timedelta(days=1)
        self._ответить(when=вперёд.isoformat())
        запись = CardReview.objects.get()
        self.assertLess(запись.reviewed_at, timezone.now() + timedelta(minutes=1))

    def test_слишком_старое_время_не_принимается(self):
        давно = timezone.now() - timedelta(days=100)
        self._ответить(when=давно.isoformat())
        запись = CardReview.objects.get()
        self.assertGreater(запись.reviewed_at, timezone.now() - timedelta(minutes=1))

    def test_мусор_вместо_времени_не_роняет_ответ(self):
        for метка in ('вчера', '', None, 12345, '2026-13-45T99:99:99'):
            CardReview.objects.all().delete()
            ответ = self._ответить(when=метка)
            self.assertEqual(ответ.status_code, 200, метка)
            self.assertEqual(CardReview.objects.count(), 1, метка)

    def test_страница_повторения_умеет_копить_оценки(self):
        """Разметка и ключ хранилища — то, на чём очередь отправки держится."""
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        разметка = ответ.content.decode('utf-8')
        self.assertIn('cards-pending-%d' % self.колода.pk, разметка)
        self.assertIn('id="не-отправлено"', разметка)
        self.assertIn("addEventListener('online'", разметка)


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
            front_lang='zh', back_lang='ru',
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

    def test_язык_сторон_меняется_вместе_с_направлением(self):
        """Без языка браузер рисует китайские иероглифы японским начертанием."""
        ответ = self.client.get(reverse('cards:learn', args=[self.колода.pk]))
        прямое = [з for з in ответ.context['набор'] if з['direction'] == 0][0]
        обратное = [з for з in ответ.context['набор'] if з['direction'] == 1][0]
        self.assertEqual((прямое['язык_вопроса'], прямое['язык_ответа']), ('zh', 'ru'))
        self.assertEqual((обратное['язык_вопроса'], обратное['язык_ответа']), ('ru', 'zh'))

    def test_без_обратных_карточек_сторона_одна(self):
        self.колода.reverse_enabled = False
        self.колода.save()
        ответ = self.client.get(reverse('cards:learn', args=[self.колода.pk]))
        self.assertEqual(len(ответ.context['набор']), 4)


class ВариантыОтвета(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(
            title='География', owner=self.user, ask_mode=Deck.ВЫБОР,
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

    def test_мало_карточек_выбор_не_собрать(self):
        крошка = Deck.objects.create(title='Крошка', owner=self.user,
                                     ask_mode=Deck.ВЫБОР)
        Card.objects.create(deck=крошка, front='а', back='б')
        ответ = self.client.get(reverse('cards:study', args=[крошка.pk]))
        # Не из чего выбирать — вопрос молча становится переворотом.
        self.assertEqual(ответ.context['задания'][0]['вид'], 'flip')

    def test_выбор_приходит_на_страницу_повторения(self):
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        задание = [з for з in ответ.context['задания']
                   if з['card'] == self.карточка.pk][0]
        self.assertEqual(задание['вид'], 'choice')
        self.assertIn(задание['ответ'], задание['варианты'])


class Самопроверка(TestCase):
    """Ученик пишет ответ, видит верный и сам решает, был ли прав."""

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(
            title='Определения', owner=self.user,
            ask_mode=Deck.ВВОД, check_mode=Deck.САМ,
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
        """Два десятка вопросов с самопроверкой по каждому — это не тест."""
        ответ = self.client.get(reverse('cards:test', args=[self.колода.pk]))
        self.assertFalse(ответ.context['просить_ввод'])

        self.колода.check_mode = Deck.АВТОМАТ
        self.колода.save()
        ответ = self.client.get(reverse('cards:test', args=[self.колода.pk]))
        self.assertTrue(ответ.context['просить_ввод'])


class ВесаПланировщика(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(title='Формулы', owner=self.user)
        self.карточка = Card.objects.create(deck=self.колода, front='в', back='о')

    def test_без_записи_берутся_стандартные(self):
        self.assertIsNone(srs.веса(self.user))

    def test_свои_веса_меняют_интервалы(self):
        состояние = srs.состояние_для(self.user, self.карточка, CardState.ПРЯМОЕ)
        обычные = srs.предпросмотр(состояние)

        # Первые четыре числа — стартовая прочность по каждой оценке. Подняв
        # их, получаем заметно более длинные интервалы.
        свои = list(srs.планировщик(self.колода).parameters)
        свои[0], свои[1], свои[2], свои[3] = 20.0, 25.0, 30.0, 40.0
        SchedulerWeights.objects.create(user=self.user, parameters=свои,
                                        reviews_used=600)
        self.assertEqual(srs.веса(self.user), свои)
        self.assertNotEqual(srs.предпросмотр(состояние)[4], обычные[4])

    def test_испорченные_веса_не_ломают_занятие(self):
        SchedulerWeights.objects.create(user=self.user, parameters=[0.0] * 21,
                                        reviews_used=600)
        состояние = srs.состояние_для(self.user, self.карточка, CardState.ПРЯМОЕ)
        # Ноль вне допустимых границ — планировщик молча возвращается к
        # стандартным весам, а не падает посреди повторения.
        self.assertEqual(sorted(srs.предпросмотр(состояние)), [1, 2, 3, 4])

    def test_неполный_набор_весов_игнорируется(self):
        SchedulerWeights.objects.create(user=self.user, parameters=[1.0, 2.0],
                                        reviews_used=600)
        self.assertIsNone(srs.веса(self.user))


class КомандаОптимизатора(TestCase):

    def test_мало_истории_ничего_не_записывает(self):
        from io import StringIO

        from django.core.management import call_command

        ученик = User.objects.create_user('ученик', 'пароль')
        колода = Deck.objects.create(title='Формулы', owner=ученик)
        карточка = Card.objects.create(deck=колода, front='в', back='о')
        состояние = srs.состояние_для(ученик, карточка, CardState.ПРЯМОЕ)
        srs.оценить(состояние, 3)

        вывод = StringIO()
        call_command('fsrs_optimize', stdout=вывод)
        self.assertIn('мало', вывод.getvalue())
        self.assertEqual(SchedulerWeights.objects.count(), 0)

    def test_без_истории_говорит_прямо(self):
        from io import StringIO

        from django.core.management import call_command

        вывод = StringIO()
        call_command('fsrs_optimize', stdout=вывод)
        self.assertIn('Ни у кого нет истории', вывод.getvalue())


class ОчередьБезСети(TestCase):
    """Страница должна уметь продолжить заход, когда сети нет."""

    def setUp(self):
        self.user = User.objects.create_user('ученик', 'пароль')
        self.колода = Deck.objects.create(title='Формулы', owner=self.user)
        for i in range(3):
            Card.objects.create(deck=self.колода, front='в %d' % i,
                                back='о %d' % i, order=i)
        self.client.force_login(self.user)

    def test_страница_запасает_очередь_и_отсеивает_отвеченное(self):
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        разметка = ответ.content.decode('utf-8')
        self.assertIn('cards-queue-%d' % self.колода.pk, разметка)
        self.assertIn('cards-pending-%d' % self.колода.pk, разметка)
        # Ключ пары «карточка+сторона» — то, по чему отсеиваются уже отвеченные.
        self.assertIn('отвеченные[з.ключ]', разметка)

    def test_у_каждого_задания_есть_ключ(self):
        ответ = self.client.get(reverse('cards:study', args=[self.колода.pk]))
        for задание in ответ.context['задания']:
            self.assertEqual(задание['ключ'],
                             '%d-%d' % (задание['card'], задание['direction']))

