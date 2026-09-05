# -*- coding: utf-8 -*-
"""Переписка: доступ, ветки, счёт непрочитанного, отметки, сокет.

Проверяем два самых дорогих места тракта.

Первое — ДОСТУП. Ошибка здесь не роняет сайт, а тихо показывает человеку чужой
разговор; заметят её не по красному экрану, а по жалобе. Поэтому проверяем не
«страница открылась», а «постороннему отвечает 404» — именно 404, потому что
«нет доступа» уже выдаёт факт существования переписки.

Второе — СЧЁТ непрочитанного. Он опасен тем, что при ошибке даёт правдоподобный
ответ: не ноль и не миллион, а «2» вместо «0». Такое не замечают месяцами.
Поэтому числа проверяем точно, а не «больше нуля».

Разметку и тексты сообщений здесь не проверяем сознательно: они меняются каждую
неделю, и тест на них только мешает править шаблон.
"""

import asyncio
from datetime import timedelta

from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .chat import (addressable_for, create_group, direct_thread, mark_read,
                   may_talk_to, unread_by_thread, unread_total)
from .consumers import ChatConsumer
from .models import Message, Thread, ThreadMember
from .tests_base import (КабинетTestCase, сделать_преподавателя,
                         сделать_ученика)


def написать(ветка, автор, текст='привет'):
    """Сообщение в ветку. Отдельной заготовки на это в tests_base нет."""
    return Message.objects.create(thread=ветка, author=автор, text=текст)


# ───────────────────────────── доступ ─────────────────────────────

class ДоступКПерепискеTests(КабинетTestCase):
    """Кто вправе открыть ветку и кому вправе писать."""

    def setUp(self):
        super().setUp()
        # Третий человек: сам преподаватель, но к этой паре отношения не имеет.
        self.посторонний = сделать_преподавателя('chuzhoy', 'Чужой Преподаватель')
        self.ветка = direct_thread(self.преподаватель, self.ученик)

    def test_uchastnik_otkryvaet_svoyu_vetku(self):
        """Если покраснеет — ученик не может открыть собственную переписку."""
        self.client.login(username='uchenik', password='x')
        ответ = self.client.get(reverse('chat_thread', args=[self.ветка.id]))
        self.assertEqual(ответ.status_code, 200)

    def test_postoronniy_poluchaet_404_a_ne_otkaz(self):
        """Если покраснеет — посторонний читает чужую переписку целиком."""
        self.client.login(username='chuzhoy', password='x')
        ответ = self.client.get(reverse('chat_thread', args=[self.ветка.id]))
        self.assertEqual(ответ.status_code, 404)

    def test_nesuschestvuyuschaya_vetka_i_chuzhaya_otvechayut_odinakovo(self):
        """Если покраснеет — по коду ответа видно, какие переписки существуют:
        перебором номеров узнают, кто с кем переписывается."""
        self.client.login(username='chuzhoy', password='x')
        чужая = self.client.get(reverse('chat_thread', args=[self.ветка.id]))
        нет_такой = self.client.get(
            reverse('chat_thread', args=[self.ветка.id + 10_000]))
        self.assertEqual(чужая.status_code, нет_такой.status_code)
        self.assertEqual(чужая.status_code, 404)

    def test_uchenik_ne_pishet_ne_svoemu_prepodavatelyu(self):
        """Если покраснеет — ученик пишет любому человеку сайта, зная лишь номер."""
        self.client.login(username='uchenik', password='x')
        ответ = self.client.get(
            reverse('chat_start', args=[self.посторонний.id]))
        self.assertEqual(ответ.status_code, 404)
        # И ветки при этом не завелось: 404 должен быть отказом, а не «уже создал».
        self.assertFalse(
            Thread.objects.filter(
                pair_key=Thread.make_pair_key(
                    self.ученик.id, self.посторонний.id)).exists())

    def test_uchenik_ne_pishet_drugomu_ucheniku(self):
        """Если покраснеет — ученики переписываются между собой мимо преподавателя."""
        сосед = сделать_ученика('sosed', 'Сосед', teacher=self.преподаватель)
        self.client.login(username='uchenik', password='x')
        ответ = self.client.get(reverse('chat_start', args=[сосед.id]))
        self.assertEqual(ответ.status_code, 404)

    def test_prepodavatel_ne_pishet_chuzhomu_ucheniku(self):
        """Если покраснеет — преподаватель заводит переписку с чужим учеником."""
        чужой_ученик = сделать_ученика('chuzhoy_uch', 'Чужой Ученик',
                                       teacher=self.посторонний)
        self.client.login(username='prepod', password='x')
        ответ = self.client.get(reverse('chat_start', args=[чужой_ученик.id]))
        self.assertEqual(ответ.status_code, 404)

    def test_uchenik_pishet_svoemu_prepodavatelyu(self):
        """Если покраснеет — ученику вообще некому написать: кнопка ведёт в 404."""
        self.client.login(username='uchenik', password='x')
        ответ = self.client.get(
            reverse('chat_start', args=[self.преподаватель.id]))
        self.assertEqual(ответ.status_code, 302)
        self.assertEqual(ответ['Location'],
                         reverse('chat_thread', args=[self.ветка.id]))

    def test_spisok_sobesednikov_uchenika_tolko_ego_prepodavatel(self):
        """Если покраснеет — в списке «кому написать» ученик видит посторонних."""
        кому = addressable_for(self.ученик)
        self.assertEqual([u.id for u in кому], [self.преподаватель.id])
        self.assertTrue(may_talk_to(self.ученик, self.преподаватель))
        self.assertFalse(may_talk_to(self.ученик, self.посторонний))


# ───────────────────────────── ветки ──────────────────────────────

class ВеткиTests(КабинетTestCase):
    """Одна ветка на пару и состав участников."""

    def test_direct_thread_odna_na_paru_v_lyubom_poryadke(self):
        """Если покраснеет — половина истории уезжает во вторую «личную» ветку,
        и человек её больше не видит."""
        первая = direct_thread(self.преподаватель, self.ученик)
        вторая = direct_thread(self.ученик, self.преподаватель)
        self.assertEqual(первая.id, вторая.id)
        self.assertEqual(Thread.objects.filter(kind=Thread.KIND_DIRECT).count(), 1)

    def test_v_lichnoy_vetke_rovno_dvoe(self):
        """Если покраснеет — в личной переписке оказывается лишний участник
        (или пропадает нужный, и собеседник не получает сообщений)."""
        ветка = direct_thread(self.преподаватель, self.ученик)
        участники = set(ThreadMember.objects
                        .filter(thread=ветка)
                        .values_list('user_id', flat=True))
        self.assertEqual(участники, {self.преподаватель.id, self.ученик.id})

    def test_povtornyy_vhod_ne_plodit_uchastnikov(self):
        """Если покраснеет — при каждом открытии переписки участник дублируется,
        и счёт непрочитанного умножается на число дублей."""
        ветка = direct_thread(self.преподаватель, self.ученик)
        direct_thread(self.ученик, self.преподаватель)
        self.assertEqual(ThreadMember.objects.filter(thread=ветка).count(), 2)

    def test_gruppa_soderzhit_sozdatelya_i_vseh_pozvannyh(self):
        """Если покраснеет — преподаватель собрал группу и сам в неё не попал:
        своих сообщений не видит и уведомлений не получает."""
        ученик2 = сделать_ученика('uchenik2', 'Второй', teacher=self.преподаватель)
        группа = create_group(self.преподаватель, 'Кружок',
                              [self.ученик, ученик2])
        участники = set(ThreadMember.objects
                        .filter(thread=группа)
                        .values_list('user_id', flat=True))
        self.assertEqual(участники,
                         {self.преподаватель.id, self.ученик.id, ученик2.id})
        self.assertEqual(группа.kind, Thread.KIND_GROUP)

    def test_v_gruppu_ne_popadaet_postoronniy(self):
        """Если покраснеет — посторонний читает групповую переписку класса."""
        ученик2 = сделать_ученика('uchenik2', 'Второй', teacher=self.преподаватель)
        посторонний = сделать_ученика('daleko', 'Далёкий', teacher=None)
        группа = create_group(self.преподаватель, 'Кружок',
                              [self.ученик, ученик2])
        self.assertFalse(группа.has_access(посторонний))
        self.client.login(username='daleko', password='x')
        ответ = self.client.get(reverse('chat_thread', args=[группа.id]))
        self.assertEqual(ответ.status_code, 404)

    def test_sozdatel_v_spiske_pozvannyh_ne_udvaivaetsya(self):
        """Если покраснеет — создатель числится в группе дважды, и рассылка
        уходит ему в двух экземплярах."""
        группа = create_group(self.преподаватель, 'Кружок',
                              [self.преподаватель, self.ученик])
        self.assertEqual(ThreadMember.objects.filter(thread=группа).count(), 2)
        self.assertEqual(
            ThreadMember.objects.filter(thread=группа,
                                        user=self.преподаватель).count(), 1)


# ─────────────────────── счёт непрочитанного ──────────────────────

class НепрочитанноеTests(КабинетTestCase):
    """Числа в значке. Ошибка здесь выглядит правдоподобно — считаем точно."""

    def setUp(self):
        super().setUp()
        self.ветка = direct_thread(self.преподаватель, self.ученик)

    def test_kazhdyy_vidit_tolko_chuzhie_soobscheniya(self):
        """Если покраснеет — в значке висит число, включающее твои собственные
        сообщения: непрочитанное не сходится никогда."""
        написать(self.ветка, self.преподаватель, 'раз')
        написать(self.ветка, self.преподаватель, 'два')
        написать(self.ветка, self.ученик, 'поняла')

        у_ученика = unread_by_thread(self.ученик)
        у_преподавателя = unread_by_thread(self.преподаватель)
        self.assertEqual(у_ученика.get(self.ветка.id), 2)
        self.assertEqual(у_преподавателя.get(self.ветка.id), 1)

    def test_svoi_soobscheniya_ne_dayut_zapisi_voobsche(self):
        """Если покраснеет — человек, который сам написал в пустую ветку,
        видит у себя непрочитанное от самого себя."""
        написать(self.ветка, self.ученик, 'первый вопрос')
        self.assertEqual(unread_by_thread(self.ученик), {})
        self.assertEqual(unread_total(self.ученик), 0)

    def test_posle_prochteniya_ostaetsya_nol(self):
        """Если покраснеет — значок не гаснет после прочтения переписки."""
        написать(self.ветка, self.преподаватель, 'раз')
        написать(self.ветка, self.преподаватель, 'два')
        mark_read(self.ветка, self.ученик)
        self.assertEqual(unread_by_thread(self.ученик).get(self.ветка.id, 0), 0)

    def test_otmetka_sobesednika_ne_vliyaet_na_moy_schet(self):
        """Самое коварное место: если условия «участник — это я» и «прочитано
        досюда» окажутся про РАЗНЫХ участников, ученик увидит непрочитанное в
        переписке, которую только что дочитал. Ответ будет правдоподобным."""
        написать(self.ветка, self.преподаватель, 'раз')
        написать(self.ветка, self.преподаватель, 'два')
        mark_read(self.ветка, self.ученик)          # преподаватель НЕ читал
        self.assertEqual(unread_by_thread(self.ученик).get(self.ветка.id, 0), 0)
        # А у преподавателя своя, нетронутая отметка: его непрочитанное на месте.
        написать(self.ветка, self.ученик, 'спасибо')
        self.assertEqual(unread_by_thread(self.преподаватель)[self.ветка.id], 1)

    def test_novoe_soobschenie_posle_otmetki_snova_neprochitano(self):
        """Если покраснеет — прочитал переписку один раз, и новые сообщения в
        ней больше никогда не подсвечиваются."""
        написать(self.ветка, self.преподаватель, 'раз')
        mark_read(self.ветка, self.ученик)
        написать(self.ветка, self.преподаватель, 'два')
        self.assertEqual(unread_by_thread(self.ученик)[self.ветка.id], 1)

    def test_schet_ne_smeshivaet_raznye_vetki(self):
        """Если покраснеет — непрочитанное одного ученика показывается в
        переписке с другим, и преподаватель ищет сообщение не там."""
        ученик2 = сделать_ученика('uchenik2', 'Второй', teacher=self.преподаватель)
        вторая = direct_thread(self.преподаватель, ученик2)
        написать(self.ветка, self.ученик, 'от первого')
        написать(вторая, ученик2, 'от второго — раз')
        написать(вторая, ученик2, 'от второго — два')

        счёт = unread_by_thread(self.преподаватель)
        self.assertEqual(счёт.get(self.ветка.id), 1)
        self.assertEqual(счёт.get(вторая.id), 2)
        self.assertEqual(unread_total(self.преподаватель), 3)

    def test_chuzhaya_vetka_v_schet_ne_popadaet(self):
        """Если покраснеет — в значке учитывается переписка, к которой человек
        не имеет отношения (и по клику он получит 404)."""
        второй_препод = сделать_преподавателя('prepod2', 'Второй Учитель')
        чужой_ученик = сделать_ученика('chuzhoy_uch', 'Чужой',
                                       teacher=второй_препод)
        чужая = direct_thread(второй_препод, чужой_ученик)
        написать(чужая, второй_препод, 'не для тебя')
        self.assertEqual(unread_by_thread(self.ученик), {})
        self.assertEqual(unread_total(self.ученик), 0)


# ──────────────────────── отметка прочтения ───────────────────────

class ОтметкаПрочтенияTests(КабинетTestCase):

    def setUp(self):
        super().setUp()
        self.ветка = direct_thread(self.преподаватель, self.ученик)

    def _отметка(self):
        return (ThreadMember.objects
                .get(thread=self.ветка, user=self.ученик).last_read_at)

    def test_mark_read_ne_dvigaet_otmetku_nazad(self):
        """Если покраснеет — вкладка обновилась, отметка откатилась, и уже
        прочитанные сообщения снова горят непрочитанными."""
        сейчас = timezone.now()
        mark_read(self.ветка, self.ученик, when=сейчас)
        изменено = mark_read(self.ветка, self.ученик,
                             when=сейчас - timedelta(days=1))
        self.assertEqual(изменено, 0)
        self.assertEqual(self._отметка(), сейчас)

    def test_mark_read_dvigaet_otmetku_vpered(self):
        """Если покраснеет — отметка застревает на первом прочтении, и значок
        не гаснет уже никогда."""
        сейчас = timezone.now()
        mark_read(self.ветка, self.ученик, when=сейчас)
        позже = сейчас + timedelta(minutes=5)
        изменено = mark_read(self.ветка, self.ученик, when=позже)
        self.assertEqual(изменено, 1)
        self.assertEqual(self._отметка(), позже)

    def test_mark_read_ne_trogaet_otmetku_sobesednika(self):
        """Если покраснеет — ученик открыл переписку и погасил непрочитанное
        преподавателю: тот не узнает, что ему написали."""
        mark_read(self.ветка, self.ученик)
        отметка_препода = (ThreadMember.objects
                           .get(thread=self.ветка, user=self.преподаватель)
                           .last_read_at)
        self.assertIsNone(отметка_препода)

    def test_mark_read_ne_zavodit_uchastiya_postoronnemu(self):
        """Если покраснеет — посторонний попадает в участники ветки тем, что
        просто дёрнул «прочитано»."""
        посторонний = сделать_преподавателя('chuzhoy', 'Чужой')
        изменено = mark_read(self.ветка, посторонний)
        self.assertEqual(изменено, 0)
        self.assertEqual(ThreadMember.objects.filter(thread=self.ветка).count(), 2)


# ───────────────────────────── сокет ──────────────────────────────

async def подключиться(ветка, пользователь):
    """Подключиться к ветке и забрать первый ответ обработчика."""
    c = WebsocketCommunicator(ChatConsumer.as_asgi(), '/ws/chat/%d/' % ветка.id)
    c.scope['user'] = пользователь
    c.scope['url_route'] = {'kwargs': {'thread_id': str(ветка.id)}}
    ok, _ = await c.connect()
    payload = await c.receive_json_from(timeout=5) if ok else None
    await c.disconnect()
    return ok, payload


class СокетTests(TransactionTestCase):
    """Самое дорогое место файла: если подключение падает, переписка не работает
    вообще ни у кого — страница открывается, а сообщения не ходят.

    TransactionTestCase, а не TestCase: обработчик ходит в базу из другого
    потока, и внутри незакрытой транзакции TestCase он не увидел бы данных.
    """

    def setUp(self):
        self.преподаватель = сделать_преподавателя()
        self.ученик = сделать_ученика(teacher=self.преподаватель)
        self.посторонний = сделать_преподавателя('chuzhoy', 'Чужой Преподаватель')
        self.ветка = direct_thread(self.преподаватель, self.ученик)
        написать(self.ветка, self.преподаватель, 'первое')
        написать(self.ветка, self.ученик, 'второе')

    def test_uchastnik_poluchaet_istoriyu_i_otmetki(self):
        """Если покраснеет — переписка мертва: соединение встаёт, история не
        приходит, и вместо ленты человек видит пустой экран."""
        ok, payload = asyncio.run(подключиться(self.ветка, self.ученик))
        self.assertTrue(ok)
        self.assertEqual(payload['action'], 'history')
        self.assertEqual(payload['me'], self.ученик.id)
        # История: оба сообщения, старое сверху.
        self.assertEqual([m['text'] for m in payload['messages']],
                         ['первое', 'второе'])
        # Отметки — по всем участникам ветки, иначе «прочитано» не показать.
        self.assertEqual({r['id'] for r in payload['readers']},
                         {self.преподаватель.id, self.ученик.id})

    def test_postoronniy_ne_podklyuchaetsya(self):
        """Если покраснеет — чужой человек подключается к ветке по её номеру и
        читает переписку в прямом эфире."""
        ok, payload = asyncio.run(подключиться(self.ветка, self.посторонний))
        self.assertFalse(ok)
        self.assertIsNone(payload)

    def test_vhod_v_vetku_gasit_neprochitannoe(self):
        """Если покраснеет — человек прочитал переписку, а значок продолжает
        показывать непрочитанное."""
        self.assertEqual(unread_by_thread(self.ученик)[self.ветка.id], 1)
        ok, _ = asyncio.run(подключиться(self.ветка, self.ученик))
        self.assertTrue(ok)
        self.assertEqual(unread_by_thread(self.ученик).get(self.ветка.id, 0), 0)
        # Преподавателю чужое прочтение отметку не двигало.
        self.assertEqual(unread_by_thread(self.преподаватель)[self.ветка.id], 1)
