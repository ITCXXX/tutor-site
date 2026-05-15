# -*- coding: utf-8 -*-
"""
Опциональный fallback: дамп контент-таблиц без учеников.

⚠️ ОСНОВНОЙ путь переноса на новый сервер — через seed-команды
   (см. deploy/DEPLOY.md, шаг 5):
       python manage.py populate_oge15_run_all
       python manage.py seed_oge16
       python manage.py seed_oge17
       python manage.py seed_oge18
       python manage.py seed_oge19

Эта команда нужна, только если в БД есть РУЧНЫЕ правки контента
(например, материалы загруженные через админку), которые нельзя
восстановить через seed.

Что попадает:
    - Course / Module / Lesson / Assignment / TestQuestion / AnswerOption
    - ProblemGenerator
    - Material / MaterialCategory
    - TaskGroup / GroupSubQuestion

Что НЕ попадает:
    - User, StudentProfile, TeacherProfile, Enrollment
    - StudentProgress / ManualMark / StudentSubmission / HomeworkAttempt
    - GeneratedProblem / ProblemAttempt / GroupAttempt
    - PDFBookmark / PDFAnnotation
    - sessions, admin logs, auth, contenttypes

⚠️ Поля FK на User (например, Course.created_by) при loaddata
   на новом сервере станут NULL — это нормально (поля помечены null=True).

Использование:
    python manage.py dumpdata_for_deploy -o deploy_data.json

Залить на сервере:
    python manage.py loaddata deploy_data.json
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

# Чёрный список моделей.
# Стандартные приложения (auth, admin, contenttypes, sessions) — целиком.
# Из users — всё, что относится к ученикам/учителям/прогрессу.
EXCLUDE = [
    "auth",
    "admin",
    "contenttypes",
    "sessions",
    "users.User",
    "users.StudentProfile",
    "users.TeacherProfile",
    "users.Enrollment",
    "users.StudentProgress",
    "users.ManualMark",
    "users.StudentSubmission",
    "users.HomeworkAttempt",
    "users.GeneratedProblem",
    "users.ProblemAttempt",
    "users.GroupAttempt",
    "users.PDFBookmark",
    "users.PDFAnnotation",
]


class Command(BaseCommand):
    help = "Дамп контент-таблиц без учеников (опциональный fallback для деплоя)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", "-o", default=None,
            help="Файл для сохранения. По умолчанию вывод в stdout.",
        )
        parser.add_argument(
            "--indent", type=int, default=2,
            help="Отступ JSON (по умолчанию 2).",
        )

    def handle(self, *args, **opts):
        # Django's dumpdata --output на Windows пишет файл в кодировке системы
        # (cp1251 для русской Windows), а не в UTF-8. Это ломает JSON
        # для loaddata на Linux-сервере. Чтобы это обойти, открываем файл
        # сами и направляем туда stdout dumpdata вручную.
        kwargs = {
            "exclude": EXCLUDE,
            "indent": opts["indent"],
        }
        if opts["output"]:
            self.stdout.write(f"Дампим в {opts['output']}…")
            with open(opts["output"], "w", encoding="utf-8") as f:
                call_command("dumpdata", stdout=f, **kwargs)
            self.stdout.write(self.style.SUCCESS(f"Готово → {opts['output']}"))
        else:
            # call_command сам пишет в stdout, если output не задан.
            # На Windows может ломать кодировку при редиректе через `>`.
            # Рекомендуется всегда использовать -o/--output.
            call_command("dumpdata", **kwargs)
