# -*- coding: utf-8 -*-
"""Очищает поле plaintext_password у всех is_staff/is_superuser пользователей.

Plaintext-копия пароля задумана только для учеников (чтобы преподаватель
мог напомнить забывшему). Хранить её для админов и преподавателей —
неоправданный риск: при утечке БД утекают и административные пароли.

После этой миграции login админов продолжает работать (хеш в password
не трогается), просто пароль больше не видно в открытом виде в админке.
"""

from django.db import migrations


def clear_admin_plaintext(apps, schema_editor):
    User = apps.get_model('users', 'User')
    qs = User.objects.filter(plaintext_password__gt='').filter(
        # is_staff ИЛИ is_superuser
        # (Q-объекты через apps.get_model — обычный фильтр работает по полям)
    )
    # Делаем два прохода вместо OR для совместимости с миграционным API
    n1 = User.objects.filter(is_staff=True).exclude(
        plaintext_password=''
    ).update(plaintext_password='')
    n2 = User.objects.filter(is_superuser=True).exclude(
        plaintext_password=''
    ).update(plaintext_password='')
    # update идемпотентный — пересечение is_staff+is_superuser обработается в n1
    print(f"  Очищено plaintext_password у админов: is_staff={n1}, is_superuser={n2}")


def noop(apps, schema_editor):
    """Откат миграции — данные не восстанавливаем (это секреты, не должны
    лежать в коде). Откат не делает ничего."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0022_groupsubquestion_unique_subquestion_group_order_and_more'),
    ]

    operations = [
        migrations.RunPython(clear_admin_plaintext, reverse_code=noop),
    ]
