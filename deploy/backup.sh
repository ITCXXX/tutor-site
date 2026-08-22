#!/usr/bin/env bash
# ============================================================================
# Резервное копирование tutor_site: база + загруженные файлы.
#
# Запускается systemd-таймером раз в сутки (deploy/tutor-backup.timer).
# Кладёт копии в /var/backups/tutor и сам удаляет старые, чтобы не забить диск:
# сервер маленький, 15 ГБ.
#
# ВАЖНО: копии лежат НА ТОМ ЖЕ сервере. Это спасает от неудачной миграции,
# случайного удаления и кривого импорта, но НЕ спасает, если пропадёт сам
# сервер. Регулярно забирайте копии к себе — как, написано в DEPLOY.md.
# ============================================================================

set -euo pipefail

APP_DIR="/opt/tutor"
DB_NAME="tutor_db"
DEST="/var/backups/tutor"
MEDIA_DIR="${APP_DIR}/media"

# Сколько копий держим. База жмётся в единицы мегабайт — её храним долго.
# Архив медиа тяжелее (туда идут PDF и картинки с досок), поэтому реже и меньше.
KEEP_DB=14          # ежедневных копий базы
KEEP_MEDIA=3        # копий загруженных файлов
MIN_FREE_MB=1024    # ниже этого порога копию не делаем, иначе добьём диск

STAMP="$(date +%F_%H%M)"
mkdir -p "${DEST}"

free_mb() { df -Pm "${DEST}" | awk 'NR==2 {print $4}'; }

if [[ "$(free_mb)" -lt "${MIN_FREE_MB}" ]]; then
    echo "backup: на диске меньше ${MIN_FREE_MB} МБ — копия не делается" >&2
    exit 1
fi

# ---- База ----
# Через postgres-пользователя: пароль не нужен, а значит его негде засветить.
DB_FILE="${DEST}/db_${STAMP}.sql.gz"
sudo -u postgres pg_dump --no-owner --no-privileges "${DB_NAME}" | gzip -9 > "${DB_FILE}"
# Пустой дамп — это провал, а не копия. Лучше убрать и сообщить.
if [[ ! -s "${DB_FILE}" ]] || [[ "$(stat -c %s "${DB_FILE}")" -lt 1024 ]]; then
    rm -f "${DB_FILE}"
    echo "backup: дамп базы пустой — копия не сохранена" >&2
    exit 1
fi

# ---- Загруженные файлы ----
# Только если внутри что-то есть: пустой архив каждый день не нужен.
if [[ -d "${MEDIA_DIR}" ]] && [[ -n "$(ls -A "${MEDIA_DIR}" 2>/dev/null)" ]]; then
    tar -czf "${DEST}/media_${STAMP}.tar.gz" -C "${APP_DIR}" media
fi

# ---- Убираем старое ----
# Сортировка по имени работает: в имени дата в формате ГГГГ-ММ-ДД.
ls -1t "${DEST}"/db_*.sql.gz    2>/dev/null | tail -n +$((KEEP_DB + 1))    | xargs -r rm -f
ls -1t "${DEST}"/media_*.tar.gz 2>/dev/null | tail -n +$((KEEP_MEDIA + 1)) | xargs -r rm -f

chmod 600 "${DEST}"/* 2>/dev/null || true

echo "backup: готово ${STAMP}; занято под копии: $(du -sh "${DEST}" | cut -f1); свободно: $(free_mb) МБ"
