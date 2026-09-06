# -*- coding: utf-8 -*-
"""Вход в систему, когда логины могут повторяться.

Самое дорогое место на сайте: ошибка здесь пускает человека в чужой кабинет —
к чужим оценкам, работам и переписке. Поэтому проверок больше, чем кажется
нужным, и половина из них про ОТКАЗ, а не про вход.

Правило, которое проверяем, одно: различает людей пара «логин + пароль».
Подошла ровно одному — пускаем. Подошла нескольким — не пускаем никого.
"""

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse

from .auth_backends import сколько_подходит
from .models import StudentProfile, TeacherProfile

User = get_user_model()


def ученик(username, password, display=None):
    u = User.objects.create_user(username=username, password=password, role='student')
    StudentProfile.objects.create(user=u, display_name=display or username)
    return u


class ВходСПовторяющимисяЛогинами(TestCase):
    """Сам вход: кого пускаем, кого нет."""

    def setUp(self):
        self.аня = ученик('полина', 'парольА', 'Полина Смирнова')
        self.вера = ученик('полина', 'парольВ', 'Полина Кузнецова')

    def войти(self, логин, пароль):
        return self.client.post(reverse('login'),
                                {'username': логин, 'password': пароль})

    # ── что должно работать ──────────────────────────────────────────────

    def test_две_полины_с_разными_паролями_входят_каждая_к_себе(self):
        self.войти('полина', 'парольА')
        self.assertEqual(self.client.session['_auth_user_id'], str(self.аня.pk))
        self.client.logout()
        self.войти('полина', 'парольВ')
        self.assertEqual(self.client.session['_auth_user_id'], str(self.вера.pk))

    def test_логин_можно_завести_третий_раз(self):
        третья = ученик('полина', 'парольТ')
        self.войти('полина', 'парольТ')
        self.assertEqual(self.client.session['_auth_user_id'], str(третья.pk))

    def test_одиночный_логин_работает_как_раньше(self):
        один = ученик('уникум', 'пароль1')
        self.войти('уникум', 'пароль1')
        self.assertEqual(self.client.session['_auth_user_id'], str(один.pk))

    def test_пробел_на_конце_логина_не_мешает(self):
        """Телефонная клавиатура дописывает пробел вслед за подсказкой."""
        self.войти('полина ', 'парольА')
        self.assertEqual(self.client.session['_auth_user_id'], str(self.аня.pk))

    def test_заглавная_первая_буква_не_мешает(self):
        """Тоже клавиатура телефона: она делает первую букву заглавной."""
        self.войти('Полина', 'парольВ')
        self.assertEqual(self.client.session['_auth_user_id'], str(self.вера.pk))

    def test_разный_регистр_логина_разные_люди_каждый_к_себе(self):
        большая = ученик('ПОЛИНА', 'парольБ')
        self.войти('полина', 'парольБ')
        self.assertEqual(self.client.session['_auth_user_id'], str(большая.pk))

    # ── что должно НЕ работать ───────────────────────────────────────────

    def test_совпали_и_логин_и_пароль_не_пускаем_никого(self):
        """Главная проверка. Различить людей нечем, и пустить наугад нельзя."""
        ученик('полина', 'парольА')          # тот же логин И тот же пароль
        ответ = self.войти('полина', 'парольА')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(ответ, 'сразу у нескольких')

    def test_неверный_пароль_не_пускает(self):
        self.войти('полина', 'мимо')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_несуществующий_логин_не_пускает(self):
        self.войти('никого', 'парольА')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_отключённый_аккаунт_не_пускает(self):
        self.аня.is_active = False
        self.аня.save(update_fields=['is_active'])
        self.войти('полина', 'парольА')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_отключённая_полина_не_мешает_войти_второй(self):
        """Отключённая запись не должна ни пускать себя, ни блокировать тёзку."""
        self.аня.is_active = False
        self.аня.save(update_fields=['is_active'])
        self.войти('полина', 'парольВ')
        self.assertEqual(self.client.session['_auth_user_id'], str(self.вера.pk))

    def test_пустой_пароль_не_пускает(self):
        self.войти('полина', '')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_текст_ошибки_при_столкновении_отличается_от_опечатки(self):
        """Человеку надо сказать разное: опечатку он починит сам, столкновение
        логина с паролем — нет."""
        опечатка = self.войти('полина', 'мимо')
        self.assertContains(опечатка, 'Неверный логин или пароль')
        ученик('полина', 'парольА')
        столкновение = self.войти('полина', 'парольА')
        self.assertContains(столкновение, 'Попросите преподавателя')


class МеханизмВходаНапрямую(TestCase):
    """Проверки самого механизма, в обход страницы входа.

    Нужны отдельно, и вот почему. Страница сама обрезает пробелы и сама смотрит
    на is_active, поэтому её проверки зелёные даже когда механизм этого не
    делает. Но через механизм ходит не только страница: client.login, будущее
    приложение, любой другой вход. Порча кода это и показала — обе проверки
    оказались зелёными при сломанном механизме.
    """

    def test_отключённого_не_пускает_и_сам_механизм(self):
        u = ученик('спящий', 'пароль')
        u.is_active = False
        u.save(update_fields=['is_active'])
        self.assertIsNone(authenticate(username='спящий', password='пароль'))

    def test_пробелы_обрезает_сам_механизм(self):
        u = ученик('ваня', 'пароль')
        self.assertEqual(authenticate(username='  ваня  ', password='пароль'), u)

    def test_регистр_учитывает_сам_механизм(self):
        u = ученик('полина', 'пароль')
        self.assertEqual(authenticate(username='ПОЛИНА', password='пароль'), u)

    def test_столкновение_не_пускает_и_сам_механизм(self):
        ученик('оля', 'один')
        ученик('оля', 'один')
        self.assertIsNone(authenticate(username='оля', password='один'))

    def test_пароль_от_тёзки_не_пускает_в_чужой_кабинет(self):
        """Самое страшное: пустить не того. Пароль Веры должен открывать
        кабинет Веры, а не Ани, даже когда логин у них общий."""
        аня = ученик('тёзка', 'пароль-ани')
        вера = ученик('тёзка', 'пароль-веры')
        self.assertEqual(authenticate(username='тёзка', password='пароль-веры'), вера)
        self.assertEqual(authenticate(username='тёзка', password='пароль-ани'), аня)


class СколькоПодходит(TestCase):
    """Счётчик, по которому страница входа отличает опечатку от столкновения."""

    def test_ноль_когда_никого(self):
        self.assertEqual(сколько_подходит('нет', 'нет'), 0)

    def test_один_когда_один(self):
        ученик('ваня', 'п1')
        self.assertEqual(сколько_подходит('ваня', 'п1'), 1)

    def test_один_когда_логин_общий_а_пароли_разные(self):
        ученик('ваня', 'п1')
        ученик('ваня', 'п2')
        self.assertEqual(сколько_подходит('ваня', 'п1'), 1)

    def test_два_когда_совпали_обе_части(self):
        ученик('ваня', 'п1')
        ученик('ваня', 'п1')
        self.assertEqual(сколько_подходит('ваня', 'п1'), 2)


class СозданиеУченикаСПовторомЛогина(TestCase):
    """Преподаватель заводит учеников: логин повторять можно, пару — нет."""

    def setUp(self):
        self.препод = User.objects.create_user(username='prepod', password='x',
                                               role='teacher')
        TeacherProfile.objects.create(user=self.препод, display_name='Пётр')
        self.client.force_login(self.препод)
        self.адрес = reverse('teacher_student_new')

    def завести(self, логин, пароль, имя='Ученик'):
        return self.client.post(self.адрес, {
            'username': логин, 'password': пароль, 'display_name': имя,
        }, follow=True)

    def test_повторить_логин_с_другим_паролем_можно(self):
        ученик('полина', 'старый')
        self.завести('полина', 'новый', 'Полина Вторая')
        self.assertEqual(User.objects.filter(username='полина').count(), 2)

    def test_повторить_логин_И_пароль_нельзя(self):
        ученик('полина', 'одинаковый')
        ответ = self.завести('полина', 'одинаковый', 'Полина Вторая')
        self.assertEqual(User.objects.filter(username='полина').count(), 1)
        self.assertContains(ответ, 'пароль нужен другой')

    def test_после_отказа_созданный_ученик_входит(self):
        """Отказ не должен оставлять полузаписанного человека."""
        ученик('полина', 'одинаковый')
        self.завести('полина', 'одинаковый')
        self.завести('полина', 'другой', 'Полина Вторая')
        self.assertEqual(User.objects.filter(username='полина').count(), 2)
        вошли = self.client.login(username='полина', password='другой')
        self.assertTrue(вошли)


class ЛогинБезУникальностиВБазе(TestCase):
    """База должна физически разрешать повтор — иначе всё выше бессмысленно."""

    def test_два_пользователя_с_одним_логином_сохраняются(self):
        User.objects.create_user(username='один', password='а')
        User.objects.create_user(username='один', password='б')
        self.assertEqual(User.objects.filter(username='один').count(), 2)

    def test_поиск_по_логину_остаётся_быстрым(self):
        """Индекс по логину должен сохраниться: сняв unique, его легко потерять,
        а по логину ищут при каждом входе."""
        поле = User._meta.get_field('username')
        self.assertTrue(поле.db_index or поле.unique,
                        'по логину нет индекса — каждый вход читает всю таблицу')
