from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_alter_generatedproblem_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='testquestion',
            name='image_svg',
            field=models.TextField(
                blank=True,
                help_text='Встроенный SVG-код для задач с картинкой',
                verbose_name='SVG иллюстрация',
            ),
        ),
    ]
