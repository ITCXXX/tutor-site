# -*- coding: utf-8 -*-
"""Наполнение второй части ОГЭ (№20) в курсе oge-maths.

Модуль «Вторая часть» → урок «№20» → по каждому типу набор групп-вариантов
(TaskGroup), сгенерированных параметрическими генераторами из
users/oge20_generators.py. Каждая группа = 5 задач (как в части 1).
Внутри подзадачи — условие + полное решение в <details>.

Перезапуск идемпотентен: группы перечитываемого типа удаляются и создаются заново.
Запуск:  manage.py populate_oge20
"""

from django.core.management.base import BaseCommand
from django.db.models import Max

from users.models import Course, Module, Lesson, TaskGroup, GroupSubQuestion
from users.oge20_generators import generate, GENERATORS


MODULE_TITLE = "Вторая часть"
LESSON_TITLE = "№20. Алгебраические выражения, уравнения, неравенства"

# Какие типы наполняем и сколько вариантов (по 5 задач в каждом).
#   (номер_типа, число_вариантов)
BUILD = [
    (1, 3),
]

PER_VARIANT = 5


def _subq_html(prob):
    """Условие + сворачиваемое решение."""
    return (
        f'<div class="oge20-question">{prob["question_html"]}</div>'
        f'<details class="oge20-solution" style="margin-top:.5rem">'
        f'<summary style="cursor:pointer;color:#2563eb;font-weight:600">Показать решение</summary>'
        f'<div style="margin-top:.4rem">{prob["solution_html"]}</div>'
        f'</details>'
    )


def _distinct_problems(type_num, count, stdout):
    """Генерирует count различных задач типа (по тексту условия)."""
    seen, out = set(), []
    attempts = 0
    while len(out) < count and attempts < count * 200:
        attempts += 1
        prob = generate(type_num)
        key = prob['question_html']
        if key in seen:
            continue
        seen.add(key)
        out.append(prob)
    if len(out) < count:
        stdout.write(f"  ! тип {type_num}: удалось сгенерировать только {len(out)} из {count}")
    return out


class Command(BaseCommand):
    help = "Наполняет вторую часть ОГЭ (№20) генераторами"

    def handle(self, *args, **opts):
        course = Course.objects.get(slug="oge-maths")

        mod_order = (course.modules.aggregate(Max("order"))["order__max"] or 0) + 1
        module, created = Module.objects.get_or_create(
            course=course, title=MODULE_TITLE,
            defaults={"order": mod_order, "description":
                      "Задания с развёрнутым решением (часть 2)."},
        )
        self.stdout.write(("Создан" if created else "Найден") + f" модуль: {module.title}")

        lesson, _ = Lesson.objects.get_or_create(
            module=module, title=LESSON_TITLE,
            defaults={"lesson_type": "practice", "order": 0,
                      "content": "", "is_free": False},
        )

        for type_num, n_variants in BUILD:
            if type_num not in GENERATORS:
                self.stdout.write(f"  пропуск: тип {type_num} не реализован")
                continue
            ctx = f"OGE20T{type_num}"

            # Идемпотентность: убираем прежние группы этого типа.
            TaskGroup.objects.filter(lesson=lesson, fipi_ctx_id=ctx).delete()

            need = n_variants * PER_VARIANT
            problems = _distinct_problems(type_num, need, self.stdout)

            base_order = (lesson.task_groups.aggregate(Max("order"))["order__max"] or 0)
            for v in range(n_variants):
                chunk = problems[v * PER_VARIANT:(v + 1) * PER_VARIANT]
                if not chunk:
                    break
                title = f"№20. Тип {type_num} · вариант {v + 1}"
                group = TaskGroup.objects.create(
                    lesson=lesson, fipi_ctx_id=ctx, title=title,
                    order=base_order + v + 1,
                    context_html=(
                        f"<p><b>№20. Тип {type_num}.</b> Решите задания и запишите "
                        f"ответ. Полное решение — по кнопке «Показать решение» "
                        f"под каждым заданием.</p>"
                    ),
                )
                for i, prob in enumerate(chunk, 1):
                    GroupSubQuestion.objects.create(
                        group=group,
                        question_html=_subq_html(prob),
                        correct_answer=prob["answer"],
                        t_type="",
                        fipi_task_id=ctx,
                        order=i,
                    )
                self.stdout.write(f"  {title}: {len(chunk)} задач")

        self.stdout.write(self.style.SUCCESS("Готово."))
