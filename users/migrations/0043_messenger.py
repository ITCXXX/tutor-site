# -*- coding: utf-8 -*-
"""Мессенджер: участники ветки переезжают в отдельную таблицу.

Переезд идёт в ОДНОЙ миграции намеренно: сначала заводим новое, потом
переносим данные, и только потом сносим старые поля. Разбей это на три файла —
и между ними появится момент, когда участники уже нигде не записаны, а старые
поля ещё живы: остановись развёртывание на середине, переписка осиротеет.

Что переносим:
  • пара teacher/student  → две строки ThreadMember;
  • pair_key              → «меньший id — больший id»;
  • Message.read_at       → ThreadMember.last_read_at того, КТО читал.
    Отметка была одна на сообщение, поэтому «докуда прочитано» у читателя —
    это время самого позднего прочитанного им сообщения.
"""

from django.db import migrations, models
import django.db.models.deletion


def перенести(apps, schema_editor):
    Thread = apps.get_model('users', 'Thread')
    ThreadMember = apps.get_model('users', 'ThreadMember')
    Message = apps.get_model('users', 'Message')

    for t in Thread.objects.all().iterator():
        участники = [t.teacher_id, t.student_id]
        малый, большой = sorted(участники)
        t.kind = 'direct'
        t.pair_key = '%d-%d' % (малый, большой)
        t.owner_id = t.teacher_id
        t.save(update_fields=['kind', 'pair_key', 'owner'])

        for uid in участники:
            # Прочитанное этим человеком — это сообщения ЧУЖИЕ и с отметкой.
            последнее = (Message.objects
                         .filter(thread=t, read_at__isnull=False)
                         .exclude(author_id=uid)
                         .order_by('-read_at')
                         .values_list('read_at', flat=True)
                         .first())
            ThreadMember.objects.create(
                thread=t, user_id=uid,
                is_admin=(uid == t.teacher_id),
                last_read_at=последнее,
            )


def обратно(apps, schema_editor):
    """Обратный ход невозможен без потерь: группы в пару полей не сложить.

    Явная ошибка честнее тихого отката, который развалит групповые ветки.
    """
    raise RuntimeError(
        'Откат мессенджера не поддерживается: групповые ветки некуда положить.')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0042_grade'),
    ]

    operations = [
        # ── 1. Снимаем старые ограничения и индексы ──────────────────────
        migrations.RemoveConstraint(
            model_name='thread', name='uniq_general_thread_per_pair'),
        migrations.RemoveConstraint(
            model_name='thread', name='uniq_lesson_thread_per_pair'),
        migrations.RemoveIndex(
            model_name='thread', name='users_threa_teacher_3faa4b_idx'),
        migrations.RemoveIndex(
            model_name='thread', name='users_threa_student_a68277_idx'),
        migrations.RemoveIndex(
            model_name='message', name='users_messa_thread__4067e8_idx'),

        # ── 2. Заводим новое ─────────────────────────────────────────────
        migrations.AddField(
            model_name='thread',
            name='kind',
            field=models.CharField(
                choices=[('direct', 'Личная переписка'), ('group', 'Группа')],
                default='direct', max_length=8, verbose_name='Тип'),
        ),
        migrations.AddField(
            model_name='thread',
            name='title',
            field=models.CharField(blank=True, max_length=120,
                                   verbose_name='Название группы'),
        ),
        migrations.AddField(
            model_name='thread',
            name='owner',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='threads_owned', to='users.user',
                verbose_name='Кто собрал'),
        ),
        migrations.AddField(
            model_name='thread',
            name='pair_key',
            field=models.CharField(blank=True, db_index=True, max_length=40,
                                   verbose_name='Ключ пары'),
        ),
        migrations.CreateModel(
            name='ThreadMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('is_admin', models.BooleanField(default=False,
                                                 verbose_name='Распорядитель')),
                ('joined_at', models.DateTimeField(auto_now_add=True,
                                                   verbose_name='Вошёл')),
                ('last_read_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Докуда прочитано')),
                ('thread', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='memberships', to='users.thread',
                    verbose_name='Ветка')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_memberships', to='users.user',
                    verbose_name='Участник')),
            ],
            options={
                'verbose_name': 'Участник переписки',
                'verbose_name_plural': 'Участники переписки',
            },
        ),
        migrations.AddField(
            model_name='message',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True,
                                       verbose_name='Правлено'),
        ),
        migrations.AddField(
            model_name='message',
            name='reply_to',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='replies', to='users.message',
                verbose_name='В ответ на'),
        ),
        migrations.AddField(
            model_name='message',
            name='about_assignment',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='chat_mentions', to='users.assignment',
                verbose_name='О задании'),
        ),
        migrations.AddField(
            model_name='message',
            name='is_question',
            field=models.BooleanField(default=False, verbose_name='Это вопрос'),
        ),
        migrations.AddField(
            model_name='message',
            name='answered_at',
            field=models.DateTimeField(blank=True, null=True,
                                       verbose_name='Отвечено'),
        ),

        # ── 3. Переносим данные, пока старые поля ещё на месте ───────────
        migrations.RunPython(перенести, обратно),

        # ── 4. Сносим старое ─────────────────────────────────────────────
        migrations.RemoveField(model_name='thread', name='teacher'),
        migrations.RemoveField(model_name='thread', name='student'),
        migrations.RemoveField(model_name='thread', name='lesson'),
        migrations.RemoveField(model_name='message', name='read_at'),

        # ── 5. Новые ограничения и индексы ───────────────────────────────
        migrations.AddConstraint(
            model_name='threadmember',
            constraint=models.UniqueConstraint(fields=('thread', 'user'),
                                               name='uniq_thread_member'),
        ),
        migrations.AddIndex(
            model_name='threadmember',
            index=models.Index(fields=['user', 'thread'],
                               name='users_threa_user_id_237f4d_idx'),
        ),
        migrations.AddConstraint(
            model_name='thread',
            constraint=models.UniqueConstraint(
                condition=models.Q(('kind', 'direct')),
                fields=('pair_key',), name='uniq_direct_pair'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['thread', 'is_question', 'answered_at'],
                               name='users_messa_thread__c30ac0_idx'),
        ),
    ]
