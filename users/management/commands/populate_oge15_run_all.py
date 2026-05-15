# -*- coding: utf-8 -*-
"""Запускает все индивидуальные populate_oge15_<GID>-команды по очереди.

Использование:
    python manage.py populate_oge15_run_all              # все группы
    python manage.py populate_oge15_run_all --only shiny # только Шины
    python manage.py populate_oge15_run_all --gids 47E80B,34E199  # выборочно
"""

import importlib
import os
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand


# Группы, сгруппированные по темам (порядок отражает структуру урока)
GROUPS = {
    "shiny": [
        "47E80B", "77CC6F", "0FF955", "1F235A", "3482E5", "4FD630",
        "583B68", "62541F", "6312CF", "87F592", "AD8FEE", "89CE07",
        "9E5B99", "EAAB14", "B1570A", "AAE77F", "CF1833", "DB5DF7",
    ],
    "tarify": ["F4978F"],
    "dorogi": [
        "34E199", "35C016", "650747", "79233F", "8C173F",
        "BA66FC", "C09A0A", "E4DF9C", "EAE764", "F6B6DD",
    ],
    "planuch": ["272C13", "856918", "5BF94C"],
    "pechi":   ["8889B9"],
    "bumaga":  ["B9A7F7"],
    "kvartira": ["eF7420"],
}

# Названия для красивого вывода
THEME_NAMES = {
    "shiny": "Шины",
    "tarify": "Тарифы",
    "dorogi": "Дороги (4-точечные)",
    "planuch": "План домохозяйства",
    "pechi": "Печи для бани",
    "bumaga": "Форматы листов А",
    "kvartira": "План квартиры",
}


def discover_existing_gids():
    """Находит фактически существующие populate_oge15_<GID>.py файлы."""
    cmd_dir = Path(__file__).parent
    gids = set()
    for f in cmd_dir.glob("populate_oge15_*.py"):
        name = f.stem  # populate_oge15_47E80B
        if name in ("populate_oge15_all", "populate_oge15_run_all"):
            continue
        gid = name.replace("populate_oge15_", "")
        gids.add(gid)
    return gids


class Command(BaseCommand):
    help = "Запускает все populate_oge15_<GID>-команды (35 групп ОГЭ №1-5)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only", default=None,
            help=f"Только одна тема: {', '.join(GROUPS.keys())}",
        )
        parser.add_argument(
            "--gids", default=None,
            help="Список конкретных GID через запятую (например, 47E80B,34E199)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Только показать список команд без запуска",
        )

    def handle(self, *args, **opts):
        existing = discover_existing_gids()

        # Собираем список команд для запуска
        if opts["gids"]:
            requested = [g.strip() for g in opts["gids"].split(",") if g.strip()]
            plan = [(None, g) for g in requested]
        elif opts["only"]:
            theme = opts["only"]
            if theme not in GROUPS:
                self.stdout.write(self.style.ERROR(
                    f"Неизвестная тема: {theme}. Доступные: {', '.join(GROUPS.keys())}"))
                return
            plan = [(theme, g) for g in GROUPS[theme]]
        else:
            plan = [(theme, g) for theme, gs in GROUPS.items() for g in gs]

        # Проверяем, что все скрипты существуют
        missing = [g for _, g in plan if g not in existing]
        if missing:
            self.stdout.write(self.style.WARNING(
                f"Пропущены (нет файла populate_oge15_<GID>.py): {', '.join(missing)}"))
        plan = [(t, g) for t, g in plan if g in existing]

        if not plan:
            self.stdout.write(self.style.ERROR("Нет групп для запуска."))
            return

        self.stdout.write(self.style.NOTICE(
            f"Будет запущено {len(plan)} команд:"))

        # Группируем по темам для красивого вывода
        if opts["dry_run"]:
            current_theme = object()
            for theme, gid in plan:
                if theme != current_theme:
                    self.stdout.write(f"\n--- {THEME_NAMES.get(theme, theme or 'manual')} ---")
                    current_theme = theme
                self.stdout.write(f"  python manage.py populate_oge15_{gid}")
            self.stdout.write(self.style.NOTICE("\n(--dry-run: команды не запущены)"))
            return

        # Запускаем
        ok = 0
        failed = []
        current_theme = object()
        for theme, gid in plan:
            if theme != current_theme:
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f"\n=== {THEME_NAMES.get(theme, theme or 'manual')} ==="))
                current_theme = theme
            cmd_name = f"populate_oge15_{gid}"
            self.stdout.write(self.style.HTTP_INFO(f"\n>>> {cmd_name}"))
            try:
                call_command(cmd_name)
                ok += 1
            except Exception as e:
                failed.append((gid, str(e)))
                self.stdout.write(self.style.ERROR(f"!!! ОШИБКА {gid}: {e}"))

        # Итог
        self.stdout.write(self.style.SUCCESS(
            f"\n\nГотово: успешно {ok}/{len(plan)}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"С ошибками ({len(failed)}):"))
            for gid, err in failed:
                self.stdout.write(self.style.ERROR(f"  {gid}: {err}"))
