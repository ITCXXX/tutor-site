# -*- coding: utf-8 -*-
"""Сроки домашки и напоминания о них.

Цена ошибки здесь не в красной строчке в отчёте, а в том, что ученик получает
письмо «срок вышел» ровно в тот день, когда преподаватель лично разрешил ему
сдать позже. Поэтому почти каждая проверка ниже — про ЛИЧНЫЙ срок против
общего: сроки урока и продления считаются в одном месте (homework.dates_for),
и все тракты — кабинет, сводка, ночная рассылка — обязаны видеть одно и то же.

Даты везде относительные, от сегодняшнего дня. Календарных чисел в файле нет
намеренно: тест с датой «2026-09-05» протухает молча и падает через неделю не
по делу.
"""

import datetime
from io import StringIO
from django.db import connection
from django.test.utils import CaptureQueriesContext

from django.core.management import call_command
from django.utils import timezone

from .homework import accepts_from, dates_for, homework_for, is_late_for
from .models import Enrollment, HomeworkExtension, Notification
from .tests_base import КабинетTestCase, записать, сделать_ученика, сделать_урок, сделать_задачу


def дата(сдвиг):
    """Сегодня плюс N дней. Отрицательное — в прошлое."""
    return timezone.localdate() + datetime.timedelta(days=сдвиг)


def строка_урока(ученик, урок):
    """Строка сводки homework_for именно про этот урок (или None)."""
    for r in homework_for(ученик):
        if r['lesson'].id == урок.id:
            return r
    return None


class СрокиДомашкиTests(КабинетTestCase):
    """Как homework_for считает срок, просрочку и закрытый приём."""

    def setUp(self):
        super().setUp()
        # Второй ученик того же преподавателя на том же курсе: нужен, чтобы
        # отличить «продлили ЭТОМУ» от «сдвинули срок всем».
        self.второй = сделать_ученика(username='uchenik2', display='Боря Второй',
                                      teacher=self.преподаватель)
        записать(self.второй, self.курс)

    # ── продление ────────────────────────────────────────────────────────

    def test_срок_не_вышел_если_есть_личное_продление(self):
        """Ученик с продлением увидит «срок вышел» и решит, что его наказали."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])
        HomeworkExtension.objects.create(
            lesson=self.урок, student=self.ученик, due_date=дата(7),
            granted_by=self.преподаватель, reason='болел')

        r = строка_урока(self.ученик, self.урок)
        self.assertIsNotNone(r)
        self.assertEqual(r['due'], дата(7))      # видит СВОЙ срок, не общий
        self.assertFalse(r['overdue'])
        self.assertEqual(r['days_left'], 7)
        self.assertTrue(r['extended'])           # и знает, что срок личный

    def test_продление_действует_только_на_своего_ученика(self):
        """Продление одному тихо продлит срок всему классу — сроки перестанут значить что-либо."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])
        HomeworkExtension.objects.create(
            lesson=self.урок, student=self.ученик, due_date=дата(7))

        r = строка_урока(self.второй, self.урок)
        self.assertEqual(r['due'], дата(-1))     # у соседа срок общий
        self.assertTrue(r['overdue'])
        self.assertEqual(r['days_left'], -1)
        self.assertFalse(r['extended'])

    def test_опоздание_считается_по_личному_сроку(self):
        """Сдавшему в свой срок поставят метку «опоздал» и снизят оценку ни за что."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])
        ext = HomeworkExtension.objects.create(
            lesson=self.урок, student=self.ученик, due_date=дата(7))

        # Сдал сегодня: для общего срока это опоздание, для личного — нет.
        self.assertFalse(is_late_for(self.урок, self.ученик, дата(0), ext))
        self.assertTrue(is_late_for(self.урок, self.второй, дата(0)))
        # А после личного срока опоздание считается и с продлением.
        self.assertTrue(is_late_for(self.урок, self.ученик, дата(8), ext))

    # ── закрытый приём ───────────────────────────────────────────────────

    def test_приём_закрыт_если_отсечка_позавчера(self):
        """Ученик будет пытаться сдать работу, которую сервер уже не примет."""
        self.урок.due_date = дата(-3)
        self.урок.cutoff_date = дата(-2)
        self.урок.save(update_fields=['due_date', 'cutoff_date'])

        r = строка_урока(self.ученик, self.урок)
        self.assertIsNotNone(r)          # из списка НЕ пропадает: он должен видеть
        self.assertTrue(r['closed'])
        self.assertTrue(r['overdue'])
        self.assertEqual(r['cutoff'], дата(-2))

    def test_в_день_отсечки_приём_ещё_открыт(self):
        """Сдвиг границы на день отнимет у ученика последний день сдачи."""
        self.урок.cutoff_date = дата(0)
        self.урок.save(update_fields=['cutoff_date'])

        self.assertFalse(строка_урока(self.ученик, self.урок)['closed'])
        self.assertTrue(accepts_from(self.урок, self.ученик, дата(0)))
        self.assertFalse(accepts_from(self.урок, self.ученик, дата(1)))

    def test_личное_продление_приёма_открывает_сдачу(self):
        """Преподаватель разрешил досдать, а сервер всё равно не примет работу."""
        self.урок.due_date = дата(-3)
        self.урок.cutoff_date = дата(-2)
        self.урок.save(update_fields=['due_date', 'cutoff_date'])
        HomeworkExtension.objects.create(
            lesson=self.урок, student=self.ученик, cutoff_date=дата(3))

        r = строка_урока(self.ученик, self.урок)
        self.assertFalse(r['closed'])
        self.assertEqual(r['cutoff'], дата(3))
        # Срок при этом остался общим — продлили только приём.
        self.assertEqual(r['due'], дата(-3))
        self.assertTrue(r['overdue'])
        # А соседу приём по-прежнему закрыт.
        self.assertTrue(строка_урока(self.второй, self.урок)['closed'])

    def test_отсечка_не_может_быть_раньше_личного_срока(self):
        """Продление срока станет пустым обещанием: срок есть, а сдать нельзя."""
        self.урок.due_date = дата(-1)
        self.урок.cutoff_date = дата(0)
        self.урок.save(update_fields=['due_date', 'cutoff_date'])
        ext = HomeworkExtension.objects.create(
            lesson=self.урок, student=self.ученик, due_date=дата(7))

        срок, приём_до = dates_for(self.урок, self.ученик, ext)
        self.assertEqual(срок, дата(7))
        self.assertEqual(приём_до, дата(7))       # отсечка подтянулась к сроку
        self.assertFalse(строка_урока(self.ученик, self.урок)['closed'])

    # ── урок без срока ───────────────────────────────────────────────────

    def test_урок_без_срока_не_просрочен_и_не_торопит(self):
        """Бессрочная домашка покраснеет как просроченная — ученик побежит сдавать несуществующий долг."""
        self.assertIsNone(self.урок.due_date)
        self.assertIsNone(self.урок.cutoff_date)

        r = строка_урока(self.ученик, self.урок)
        self.assertIsNotNone(r)          # в списке есть — задавали же
        self.assertIsNone(r['due'])
        self.assertFalse(r['overdue'])
        self.assertIsNone(r['days_left'])   # «подходит срок» посчитать не из чего
        self.assertFalse(r['closed'])

    def test_просроченные_идут_первыми(self):
        """Ученик откроет кабинет и не увидит долг: он окажется в хвосте списка."""
        поздний = сделать_урок(self.курс, 'Поздний', order=2, due=дата(5))
        from .tests_base import сделать_задачу
        сделать_задачу(поздний, 'З', points=1, order=1)
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])

        порядок = [r['lesson'].id for r in homework_for(self.ученик)]
        self.assertEqual(порядок[0], self.урок.id)


class НапоминанияTests(КабинетTestCase):
    """Ночная рассылка remind_homework: кому и сколько раз."""

    def setUp(self):
        super().setUp()
        self.второй = сделать_ученика(username='uchenik2', display='Боря Второй',
                                      teacher=self.преподаватель)
        записать(self.второй, self.курс)

    def запустить(self, **опции):
        call_command('remind_homework', stdout=StringIO(), **опции)

    def кинды(self, кому):
        """Сколько уведомлений про сроки пришло человеку."""
        return Notification.objects.filter(
            user=кому,
            kind__in=(Notification.KIND_DUE_SOON, Notification.KIND_DUE_PASSED),
        ).count()

    def test_ученику_с_продлением_не_шлём_напоминаний_о_сроке(self):
        """Ученик получит ночью «срок вышел» ровно после того, как ему лично продлили срок."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])
        HomeworkExtension.objects.create(
            lesson=self.урок, student=self.ученик, due_date=дата(7))

        self.запустить()

        self.assertEqual(self.кинды(self.ученик), 0)
        self.assertEqual(Notification.objects.filter(user=self.ученик).count(), 0)
        # А тому, кому не продлевали, напоминание пришло — рассылка работает.
        self.assertEqual(
            Notification.objects.filter(
                user=self.второй, kind=Notification.KIND_DUE_PASSED).count(), 1)

    def test_за_день_до_срока_приходит_предупреждение(self):
        """Ученик узнает о сроке уже после того, как тот прошёл."""
        self.урок.due_date = дата(1)
        self.урок.save(update_fields=['due_date'])

        self.запустить()

        self.assertEqual(
            Notification.objects.filter(
                user=self.ученик, kind=Notification.KIND_DUE_SOON).count(), 1)
        self.assertEqual(
            Notification.objects.filter(
                user=self.ученик, kind=Notification.KIND_DUE_PASSED).count(), 0)

    def test_срок_дальше_порога_молчит(self):
        """Рассылка станет спамить про сроки на неделю вперёд, и её перестанут читать."""
        self.урок.due_date = дата(5)
        self.урок.save(update_fields=['due_date'])

        self.запустить()

        self.assertEqual(self.кинды(self.ученик), 0)

    def test_бессрочная_домашка_напоминаний_не_порождает(self):
        """Ученик получит напоминание о сроке, которого преподаватель не ставил."""
        self.assertIsNone(self.урок.due_date)

        self.запустить()

        self.assertEqual(Notification.objects.count(), 0)

    def test_закрытый_приём_даёт_одно_уведомление_а_не_два(self):
        """За один урок ученику придут сразу «срок вышел» и «приём закрыт»."""
        self.урок.due_date = дата(-3)
        self.урок.cutoff_date = дата(-2)
        self.урок.save(update_fields=['due_date', 'cutoff_date'])

        self.запустить()

        self.assertEqual(
            Notification.objects.filter(
                user=self.ученик, kind=Notification.KIND_DUE_PASSED).count(), 1)

    def test_повторный_запуск_не_плодит_уведомления(self):
        """Таймер срабатывает каждую ночь — ученик утонет в копиях одного письма."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])

        self.запустить()
        после_первого = Notification.objects.count()
        self.assertGreater(после_первого, 0)     # иначе тест ничего не значит

        self.запустить()
        self.assertEqual(Notification.objects.count(), после_первого)

    def test_вхолостую_ничего_не_записывает(self):
        """--dry-run на проде разошлёт всем настоящие письма."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])

        self.запустить(dry_run=True)

        self.assertEqual(Notification.objects.count(), 0)

    def test_преподавателю_одна_сводка_а_не_письмо_на_ученика(self):
        """Преподаватель получит по уведомлению на каждого должника — в классе на 30 человек это 30 писем за ночь."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])

        self.запустить()

        self.assertEqual(
            Notification.objects.filter(
                user=self.преподаватель, kind=Notification.KIND_DIGEST).count(), 1)
        # Оба ученика просрочили — но сводка всё равно одна.
        self.assertEqual(
            Notification.objects.filter(
                user=self.второй, kind=Notification.KIND_DUE_PASSED).count(), 1)

    def test_ученик_с_продлением_не_попадает_в_сводку_долгов(self):
        """Преподаватель увидит в списке должников того, кому сам продлил срок."""
        self.урок.due_date = дата(-1)
        self.урок.save(update_fields=['due_date'])
        # Продлили ОБОИМ — должников не осталось, значит и сводки быть не должно.
        # Проверяем именно фактом отсутствия записи, а не разбором её текста:
        # текст перепишут, а смысл проверки должен пережить это.
        for кто in (self.ученик, self.второй):
            HomeworkExtension.objects.create(
                lesson=self.урок, student=кто, due_date=дата(7))

        self.запустить()

        self.assertEqual(
            Notification.objects.filter(
                user=self.преподаватель, kind=Notification.KIND_DIGEST).count(), 0)


class ЗапросыПачкамиTests(КабинетTestCase):
    """Сторож против возврата N+1 в списке домашек.

    Модуль homework.py обещает в своём же описании считать «пачками». Обещание
    держалось только на словах: «продление не передавали» и «продления нет»
    обозначались одним и тем же None, поэтому для урока БЕЗ продления
    dates_for шла в базу сама — и ещё раз из accepts_from. Шесть уроков без
    единого продления стоили восемнадцать запросов вместо шести.

    Тест считает запросы, а не время: время плавает от машины к машине, а
    число запросов — нет.
    """

    def test_список_домашек_не_ходит_за_каждым_продлением(self):
        сегодня = timezone.localdate()
        for i in range(6):
            урок = сделать_урок(self.курс, 'Урок %d' % (i + 2), order=i + 2,
                                due=сегодня + datetime.timedelta(days=i + 1))
            сделать_задачу(урок, 'Задача %d' % i)

        with CaptureQueriesContext(connection) as запросы:
            строки = homework_for(self.ученик)

        про_продления = [q for q in запросы.captured_queries
                         if 'homeworkextension' in q['sql'].lower()]
        self.assertGreaterEqual(len(строки), 6)
        # Одна пачка на весь список. Раньше их было тринадцать.
        self.assertLessEqual(
            len(про_продления), 2,
            'за продлениями сходили %d раз — вернулся запрос на каждый урок'
            % len(про_продления))


class СрокиОтЗаписиTests(КабинетTestCase):
    """Срок «через N дней после записи» — то, что делает курс многоразовым.

    Пока сроки были календарными, курс годился ровно одному ученику: второму
    пришлось бы переписывать каждую дату руками. Если эти проверки покраснеют —
    вернулись к одноразовым курсам.
    """

    def записан_дней_назад(self, сколько):
        зап = Enrollment.objects.get(student=self.ученик, course=self.курс)
        Enrollment.objects.filter(pk=зап.pk).update(
            enrolled_at=timezone.now() - datetime.timedelta(days=сколько))
        return Enrollment.objects.get(pk=зап.pk).enrolled_at

    def test_срок_считается_от_дня_записи(self):
        self.записан_дней_назад(3)
        self.урок.due_offset_days = 7
        self.урок.save(update_fields=['due_offset_days'])
        срок, _ = dates_for(self.урок, self.ученик)
        self.assertEqual(срок, timezone.localdate() + datetime.timedelta(days=4))

    def test_у_второго_ученика_свой_срок(self):
        """Тот же урок, разные дни записи — разные сроки. В этом весь смысл."""
        второй = сделать_ученика(username='vtoroy', display='Ваня',
                                 teacher=self.преподаватель)
        записать(второй, self.курс)
        self.записан_дней_назад(10)
        self.урок.due_offset_days = 14
        self.урок.save(update_fields=['due_offset_days'])

        мой, _ = dates_for(self.урок, self.ученик)
        его, _ = dates_for(self.урок, второй)
        self.assertNotEqual(мой, его)
        self.assertEqual(мой, timezone.localdate() + datetime.timedelta(days=4))
        self.assertEqual(его, timezone.localdate() + datetime.timedelta(days=14))

    def test_смещение_старше_календарной_даты(self):
        self.записан_дней_назад(0)
        self.урок.due_date = timezone.localdate() - datetime.timedelta(days=30)
        self.урок.due_offset_days = 5
        self.урок.save(update_fields=['due_date', 'due_offset_days'])
        срок, _ = dates_for(self.урок, self.ученик)
        self.assertEqual(срок, timezone.localdate() + datetime.timedelta(days=5))

    def test_личное_продление_старше_смещения(self):
        """Решение преподавателя про конкретного человека старше расписания."""
        self.записан_дней_назад(0)
        self.урок.due_offset_days = 5
        self.урок.save(update_fields=['due_offset_days'])
        личный = timezone.localdate() + datetime.timedelta(days=40)
        ext = HomeworkExtension.objects.create(
            lesson=self.урок, student=self.ученик, due_date=личный,
            reason='болел', granted_by=self.преподаватель)
        срок, _ = dates_for(self.урок, self.ученик, ext)
        self.assertEqual(срок, личный)

    def test_без_смещения_работает_календарная_дата(self):
        дата = timezone.localdate() + datetime.timedelta(days=9)
        self.урок.due_date = дата
        self.урок.save(update_fields=['due_date'])
        срок, _ = dates_for(self.урок, self.ученик)
        self.assertEqual(срок, дата)

    def test_смещения_не_возвращают_запрос_на_каждый_урок(self):
        """Тот же сторож, что и для продлений: пачка, а не урок за уроком."""
        for i in range(6):
            урок = сделать_урок(self.курс, 'Урок %d' % (i + 2), order=i + 2)
            урок.due_offset_days = 7 + i
            урок.save(update_fields=['due_offset_days'])
            сделать_задачу(урок, 'Задача %d' % i)

        with CaptureQueriesContext(connection) as запросы:
            homework_for(self.ученик)

        про_записи = [q for q in запросы.captured_queries
                      if 'users_enrollment' in q['sql'].lower()]
        self.assertLessEqual(
            len(про_записи), 2,
            'за днём записи сходили %d раз — вернулась N+1' % len(про_записи))
