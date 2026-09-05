# -*- coding: utf-8 -*-
"""Оценка переезжает со сдачи на пару «ученик — задача».

Делается СЕЙЧАС именно потому, что таблица пуста: сегодня это одна миграция,
а с накопленными оценками была бы миграция с переносом и разбором дублей (у
одного ученика по одной задаче могло оказаться несколько сдач, а значит и
несколько оценок, — и пришлось бы решать, какая из них настоящая).

Перенос всё равно написан: если строки где-то появились (другая машина, копия
базы), ученик и задача возьмутся из сдачи, а не потеряются.
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def перенести(apps, schema_editor):
    """Заполнить ученика и задачу из сдачи, к которой оценка была привязана."""
    Grade = apps.get_model('users', 'Grade')
    for g in Grade.objects.select_related('submission').iterator():
        if g.submission_id and (g.student_id is None or g.assignment_id is None):
            g.student_id = g.submission.student_id
            g.assignment_id = g.submission.assignment_id
            g.save(update_fields=['student', 'assignment'])


def обратно(apps, schema_editor):
    """Обратный ход теряет оценки без сдачи — те, ради которых всё и делалось."""
    raise RuntimeError(
        'Откат невозможен: оценки, поставленные без сдачи (контрольная на '
        'бумаге, устный ответ), привязать к сдаче нельзя — её не существует.')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0043_messenger'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='grade', name='users_grade_submiss_a941d0_idx'),

        # ── 1. Заводим поля пустыми, чтобы было куда переносить ──────────
        migrations.AddField(
            model_name='grade', name='student',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='grades', to='users.user', verbose_name='Ученик'),
        ),
        migrations.AddField(
            model_name='grade', name='assignment',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='grades', to='users.assignment',
                verbose_name='Задача'),
        ),
        migrations.AddField(
            model_name='grade', name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now,
                verbose_name='Когда поставлена впервые'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='grade', name='graded_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Когда правлена'),
        ),

        # ── 2. Сдача становится НЕобязательной ссылкой ───────────────────
        migrations.AlterField(
            model_name='grade', name='submission',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='grades', to='users.studentsubmission',
                verbose_name='За какую работу'),
        ),

        # ── 3. Переносим ────────────────────────────────────────────────
        migrations.RunPython(перенести, обратно),

        # ── 4. Теперь ученик и задача обязательны ───────────────────────
        migrations.AlterField(
            model_name='grade', name='student',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='grades', to='users.user', verbose_name='Ученик'),
        ),
        migrations.AlterField(
            model_name='grade', name='assignment',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='grades', to='users.assignment',
                verbose_name='Задача'),
        ),

        migrations.AddIndex(
            model_name='grade',
            index=models.Index(fields=['assignment', 'student'],
                               name='users_grade_assignm_999a35_idx'),
        ),
        migrations.AddConstraint(
            model_name='grade',
            constraint=models.UniqueConstraint(
                fields=('student', 'assignment'), name='uniq_grade_per_task'),
        ),
    ]
