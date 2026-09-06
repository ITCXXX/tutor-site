# -*- coding: utf-8 -*-
"""Счёт файлов доски и уборка мусора.

Главное здесь — то, на чём я ошибся в первый раз: удалил картинку с доски, а
счётчик не сдвинулся. Считать надо ТО, ЧТО В ХОДУ, а не то, что лежит на диске.
"""

import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from .models import Board, BoardElement
from .views import _board_files_usage, _файлы_в_ходу

User = get_user_model()
ВРЕМЕННАЯ = tempfile.mkdtemp(prefix='медиа-доски-')


@override_settings(MEDIA_ROOT=ВРЕМЕННАЯ)
class СчётФайловДоски(TestCase):

    def setUp(self):
        self.хозяин = User.objects.create_user(username='prepod', password='x',
                                               role='teacher')
        self.доска = Board.objects.create(code='abc123', owner=self.хозяин,
                                          title='Доска')
        self.папка = os.path.join(ВРЕМЕННАЯ, 'board', 'abc123')
        os.makedirs(self.папка, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(os.path.join(ВРЕМЕННАЯ, 'board'), ignore_errors=True)

    def файл(self, имя='a' * 32 + '.jpg', байт=1000):
        путь = os.path.join(self.папка, имя)
        with open(путь, 'wb') as f:
            f.write(b'x' * байт)
        return имя

    def картинка_на_доске(self, имя, eid='e1'):
        return BoardElement.objects.create(
            board=self.доска, element_id=eid, type='image',
            data={'x': 0, 'y': 0, 'url': '/media/board/abc123/' + имя})

    # ── счёт ─────────────────────────────────────────────────────────────

    def test_файл_с_объектом_считается(self):
        имя = self.файл()
        self.картинка_на_доске(имя)
        n, b = _board_files_usage('abc123')
        self.assertEqual(n, 1)
        self.assertEqual(b, 1000)

    def test_после_удаления_объекта_счётчик_падает(self):
        """ТО САМОЕ. Раньше счётчик умел только расти, и удаление картинки
        ничего не меняло."""
        имя = self.файл()
        объект = self.картинка_на_доске(имя)
        self.assertEqual(_board_files_usage('abc123')[0], 1)
        объект.delete()
        self.assertEqual(_board_files_usage('abc123')[0], 0,
                         'объект удалён, а файл всё ещё в счёте')

    def test_файл_остаётся_на_диске_ради_отмены(self):
        """Ctrl+Z возвращает объект с прежним адресом. Если убрать файл сразу,
        отменённая картинка окажется битой."""
        имя = self.файл()
        объект = self.картинка_на_доске(имя)
        объект.delete()
        self.assertTrue(os.path.exists(os.path.join(self.папка, имя)),
                        'файл убран сразу — отмена вернёт битую картинку')

    def test_чужой_файл_в_папке_не_считается(self):
        self.файл('b' * 32 + '.png', 5000)      # ничей
        имя = self.файл()
        self.картинка_на_доске(имя)
        n, b = _board_files_usage('abc123')
        self.assertEqual((n, b), (1, 1000))

    def test_имя_ищется_во_всех_данных_а_не_только_в_url(self):
        """Картинка может прийти внутри текста, а не отдельным объектом."""
        имя = self.файл()
        BoardElement.objects.create(
            board=self.доска, element_id='t1', type='textbox',
            data={'html': '<p>вот <img src="/media/board/abc123/%s"> она</p>' % имя})
        self.assertIn(имя, _файлы_в_ходу('abc123'))
        self.assertEqual(_board_files_usage('abc123')[0], 1)

    def test_несколько_объектов_на_один_файл_считаются_раз(self):
        имя = self.файл()
        self.картинка_на_доске(имя, 'e1')
        self.картинка_на_доске(имя, 'e2')
        self.assertEqual(_board_files_usage('abc123')[0], 1)

    # ── уборка ───────────────────────────────────────────────────────────

    def test_уборка_без_флага_ничего_не_удаляет(self):
        имя = self.файл()
        старым(os.path.join(self.папка, имя))
        call_command('убрать_ненужные_файлы')
        self.assertTrue(os.path.exists(os.path.join(self.папка, имя)))

    def test_уборка_убирает_ненужный_старый_файл(self):
        имя = self.файл()
        старым(os.path.join(self.папка, имя))
        call_command('убрать_ненужные_файлы', применить=True)
        self.assertFalse(os.path.exists(os.path.join(self.папка, имя)))

    def test_уборка_не_трогает_нужный_файл(self):
        имя = self.файл()
        старым(os.path.join(self.папка, имя))
        self.картинка_на_доске(имя)
        call_command('убрать_ненужные_файлы', применить=True)
        self.assertTrue(os.path.exists(os.path.join(self.папка, имя)),
                        'убрали файл, которым пользуется объект')

    def test_уборка_не_трогает_свежий_файл(self):
        """Свежий может ещё понадобиться отмене."""
        имя = self.файл()
        call_command('убрать_ненужные_файлы', применить=True)
        self.assertTrue(os.path.exists(os.path.join(self.папка, имя)))


def старым(путь, дней=30):
    """Состарить файл: уборка смотрит на время изменения."""
    когда = os.path.getmtime(путь) - дней * 86400
    os.utime(путь, (когда, когда))
