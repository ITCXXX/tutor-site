# -*- coding: utf-8 -*-
"""Пометка «у меня вопрос» на задаче: users/chat.py и chat_toggle_question.

Пометка живёт не в отдельной табличке, а обычным сообщением в личной переписке
ученика с преподавателем — пустым, с ссылкой на задание. Из этого решения
растут все проверки ниже: пометка должна гаснуть ответом в чате, не плодиться
от повторных нажатий, не утаскивать за собой написанный руками текст и не
показываться чужому преподавателю.

Проверяем числа и поведение. Тексты сообщений-подсказок и разметку страницы не
трогаем сознательно: они меняются чаще, чем правила.
"""

from django.urls import reverse
from django.utils import timezone

from .chat import (ask_question, open_questions_for, question_of,
                   withdraw_question)
from .models import Message, Thread
from .tests_base import (КабинетTestCase, записать, сделать_курс,
                         сделать_преподавателя, сделать_ученика, сделать_урок,
                         сделать_задачу)


class ПометкаВопросаTests(КабинетTestCase):
    """Работа самих функций chat.py, без страниц."""

    # ───────────────────────── заведение пометки ─────────────────────────

    def test_ask_question_заводит_пустую_пометку_в_личной_ветке(self):
        """Иначе нажатие «у меня вопрос» не доходит до преподавателя вовсе."""
        m, завели = ask_question(self.ученик, self.задача1)

        self.assertTrue(завели)
        self.assertIsNotNone(m)
        # Текста нет намеренно: пометка стоит одно нажатие.
        self.assertEqual(m.text, '')
        self.assertTrue(m.is_question)
        self.assertIsNone(m.answered_at)
        self.assertEqual(m.about_assignment_id, self.задача1.id)
        self.assertEqual(m.author_id, self.ученик.id)
        # Ровно одно сообщение на весь сайт — лишних заведено не было.
        self.assertEqual(Message.objects.count(), 1)

    def test_пометка_ложится_в_личную_ветку_с_преподавателем(self):
        """Иначе вопрос уедет в чужую переписку — или заведёт вторую ветку с
        тем же человеком, и половина истории пропадёт."""
        m, _ = ask_question(self.ученик, self.задача1)

        ветка = m.thread
        self.assertEqual(ветка.kind, Thread.KIND_DIRECT)
        self.assertEqual(
            ветка.pair_key,
            Thread.make_pair_key(self.ученик.id, self.преподаватель.id))
        участники = set(ветка.memberships.values_list('user_id', flat=True))
        self.assertEqual(участники, {self.ученик.id, self.преподаватель.id})
        self.assertEqual(Thread.objects.count(), 1)

    def test_повторный_ask_question_не_плодит_вторую_пометку(self):
        """Иначе двойной клик (или обновление страницы) забьёт преподавателю
        полку вопросов десятком одинаковых пустышек по одной задаче."""
        первая, завели1 = ask_question(self.ученик, self.задача1)
        вторая, завели2 = ask_question(self.ученик, self.задача1)

        self.assertTrue(завели1)
        self.assertFalse(завели2)
        self.assertEqual(вторая.pk, первая.pk)
        self.assertEqual(Message.objects.count(), 1)

    def test_пометки_на_разных_задачах_живут_порознь(self):
        """Иначе вопрос по задаче 1 показывался бы висящим на задаче 2 —
        и ученик не смог бы пометить вторую задачу отдельно."""
        первая, _ = ask_question(self.ученик, self.задача1)
        вторая, завели = ask_question(self.ученик, self.задача2)

        self.assertTrue(завели)
        self.assertNotEqual(вторая.pk, первая.pk)
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(question_of(self.ученик, self.задача1).pk, первая.pk)
        self.assertEqual(question_of(self.ученик, self.задача2).pk, вторая.pk)

    # ───────────────────────── открыт / отвечен ──────────────────────────

    def test_question_of_находит_открытую_пометку(self):
        """Иначе кнопка на странице задачи всегда показывает «пометить», и
        ученик не может её снять — только ставит новые."""
        m, _ = ask_question(self.ученик, self.задача1)

        найдено = question_of(self.ученик, self.задача1)
        self.assertIsNotNone(найдено)
        self.assertEqual(найдено.pk, m.pk)

    def test_пометка_гаснет_ответом_сама(self):
        """Иначе преподаватель ответил в переписке, а вопрос всё висит и на
        задаче, и в его же полке неотвеченного — и он отвечает второй раз."""
        m, _ = ask_question(self.ученик, self.задача1)

        m.answered_at = timezone.now()
        m.save(update_fields=['answered_at'])

        self.assertIsNone(question_of(self.ученик, self.задача1))
        # Сообщение при этом остаётся в переписке — гаснет пометка, не история.
        self.assertTrue(Message.objects.filter(pk=m.pk).exists())

    def test_question_of_без_пометки_возвращает_None(self):
        """Иначе на чистой задаче показывалась бы кнопка «снять пометку»."""
        self.assertIsNone(question_of(self.ученик, self.задача1))

    # ────────────────────────── снятие пометки ───────────────────────────

    def test_withdraw_question_снимает_пустую_пометку(self):
        """Иначе передумавший ученик не может убрать вопрос, и преподаватель
        разбирает полку вопросов, которых уже нет."""
        m, _ = ask_question(self.ученик, self.задача1)

        снято = withdraw_question(self.ученик, self.задача1)

        self.assertTrue(снято)
        self.assertFalse(Message.objects.filter(pk=m.pk).exists())
        self.assertEqual(Message.objects.count(), 0)
        self.assertIsNone(question_of(self.ученик, self.задача1))

    def test_withdraw_question_не_удаляет_пометку_с_текстом(self):
        """Иначе нажатие на кнопку молча стирает из переписки написанный
        руками вопрос — тот, что преподаватель, возможно, уже прочитал."""
        m, _ = ask_question(self.ученик, self.задача1)
        m.text = 'Не понимаю, откуда во втором пункте берётся минус'
        m.save(update_fields=['text'])

        снято = withdraw_question(self.ученик, self.задача1)

        self.assertFalse(снято)
        m.refresh_from_db()
        self.assertEqual(
            m.text, 'Не понимаю, откуда во втором пункте берётся минус')
        self.assertEqual(Message.objects.count(), 1)
        # И пометка остаётся открытой: вопрос-то никуда не делся.
        self.assertIsNotNone(question_of(self.ученик, self.задача1))

    def test_withdraw_question_снимает_только_свою_задачу(self):
        """Иначе снятие вопроса по одной задаче гасит вопросы по всем
        остальным разом."""
        первая, _ = ask_question(self.ученик, self.задача1)
        вторая, _ = ask_question(self.ученик, self.задача2)

        self.assertTrue(withdraw_question(self.ученик, self.задача1))

        self.assertFalse(Message.objects.filter(pk=первая.pk).exists())
        self.assertTrue(Message.objects.filter(pk=вторая.pk).exists())
        self.assertIsNotNone(question_of(self.ученик, self.задача2))

    def test_withdraw_question_без_пометки_возвращает_False(self):
        """Иначе повторное нажатие на несуществующую пометку роняет страницу."""
        self.assertFalse(withdraw_question(self.ученик, self.задача1))
        self.assertEqual(Message.objects.count(), 0)

    # ─────────────────────── полка преподавателя ─────────────────────────

    def test_open_questions_for_видит_своих_и_не_видит_чужих(self):
        """Иначе преподаватель разбирает вопросы чужих учеников (а свои при
        этом ждут) — и заодно видит переписку, к которой не имеет отношения."""
        чужой_преподаватель = сделать_преподавателя(
            username='prepod2', display='Второй Учитель')
        чужой_ученик = сделать_ученика(
            username='uchenik2', display='Чужой Ученик',
            teacher=чужой_преподаватель)
        чужой_курс = сделать_курс(чужой_преподаватель, title='Чужой курс',
                                  slug='chuzhoy')
        чужой_урок = сделать_урок(чужой_курс, title='Чужой урок')
        чужая_задача = сделать_задачу(чужой_урок, 'Чужая задача')
        записать(чужой_ученик, чужой_курс)

        моя, _ = ask_question(self.ученик, self.задача1)
        чужая, _ = ask_question(чужой_ученик, чужая_задача)

        мои = open_questions_for(self.преподаватель)
        self.assertEqual([m.pk for m in мои], [моя.pk])

        их = open_questions_for(чужой_преподаватель)
        self.assertEqual([m.pk for m in их], [чужая.pk])

    def test_open_questions_for_не_показывает_отвеченное(self):
        """Иначе полка неотвеченного растёт вечно и перестаёт быть списком дел."""
        отвеченная, _ = ask_question(self.ученик, self.задача1)
        открытая, _ = ask_question(self.ученик, self.задача2)
        отвеченная.answered_at = timezone.now()
        отвеченная.save(update_fields=['answered_at'])

        полка = open_questions_for(self.преподаватель)

        self.assertEqual([m.pk for m in полка], [открытая.pk])

    # ────────────────────── ученик без преподавателя ─────────────────────

    def test_ученик_без_преподавателя_не_получает_пометку(self):
        """Иначе только что заведённый ученик, у которого преподаватель ещё не
        назначен, роняет страницу задачи нажатием на кнопку."""
        сирота = сделать_ученика(username='sirota', display='Без Наставника',
                                 teacher=None)

        m, завели = ask_question(сирота, self.задача1)

        self.assertIsNone(m)
        self.assertFalse(завели)
        # Ничего не создано: ни сообщения, ни повисшей ветки «сам с собой».
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(Thread.objects.count(), 0)
        self.assertIsNone(question_of(сирота, self.задача1))
        self.assertFalse(withdraw_question(сирота, self.задача1))


class ПометкаЧерезСтраницуTests(КабинетTestCase):
    """Тот же тракт, но через POST на chat_toggle_question."""

    def setUp(self):
        super().setUp()
        self.адрес = reverse('chat_toggle_question', args=[self.задача1.id])

    def test_post_ставит_и_снимает_пометку(self):
        """Иначе кнопка на странице урока не работает: либо не ставит вопрос,
        либо не даёт его снять повторным нажатием."""
        self.client.force_login(self.ученик)

        первый = self.client.post(self.адрес)
        self.assertEqual(первый.status_code, 302)
        self.assertIsNotNone(question_of(self.ученик, self.задача1))
        self.assertEqual(Message.objects.count(), 1)

        второй = self.client.post(self.адрес)
        self.assertEqual(второй.status_code, 302)
        self.assertIsNone(question_of(self.ученик, self.задача1))
        self.assertEqual(Message.objects.count(), 0)

    def test_преподавателю_адрес_недоступен(self):
        """Иначе преподаватель ставит вопросы от чужого имени — и полка
        неотвеченного наполняется тем, чего ученик не спрашивал."""
        self.client.force_login(self.преподаватель)

        ответ = self.client.post(self.адрес)

        self.assertEqual(ответ.status_code, 404)
        self.assertEqual(Message.objects.count(), 0)

    def test_не_записанный_на_курс_пометку_не_поставит(self):
        """Иначе любой ученик помечает вопросом задачу из курса, которого он не
        покупал, — и тем самым узнаёт, что в этом курсе за задачи."""
        чужой_преподаватель = сделать_преподавателя(username='prepod2')
        посторонний = сделать_ученика(username='postoronniy',
                                      teacher=чужой_преподаватель)
        self.client.force_login(посторонний)

        ответ = self.client.post(self.адрес)

        self.assertEqual(ответ.status_code, 404)
        self.assertEqual(Message.objects.count(), 0)
