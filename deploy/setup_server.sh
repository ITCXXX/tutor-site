#!/usr/bin/env bash
# ============================================================================
# Bootstrap-скрипт для свежего Ubuntu 24.04 VPS.
# Запускать ПОД ROOT после первого ssh:
#   bash setup_server.sh
#
# Что делает:
#   1. Обновляет систему
#   2. Ставит python, postgresql, nginx, certbot, git
#   3. Создаёт пользователя `tutor` без права на ssh-логин
#   4. Создаёт PostgreSQL базу + пользователя
#   5. Клонирует репо в /opt/tutor (если не клонировано)
#   6. Создаёт venv, ставит зависимости
#   7. Копирует .env.example в .env (НУЖНО ОТРЕДАКТИРОВАТЬ)
#   8. Копирует systemd unit и nginx conf
#   9. Открывает фаервол
#   10. ПРОПУСКАЕТ certbot и migrate — это делается вручную
#       после редактирования .env (см. DEPLOY.md, шаги 5-8).
#
# После этого скрипта прочитай DEPLOY.md и выполни шаги 5-9.
# ============================================================================

set -euo pipefail

# ---- НАСТРОЙКИ (можно поменять) ----
APP_NAME="tutor"
APP_USER="tutor"
APP_DIR="/opt/${APP_NAME}"
REPO_URL="${REPO_URL:-https://github.com/ITCXXX/tutor-site.git}"
DB_NAME="${APP_NAME}_db"
DB_USER="${APP_NAME}_user"
DB_PASS="$(openssl rand -hex 24)"  # сгенерируется случайный пароль

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: запускай под root (или через sudo bash setup_server.sh)" >&2
    exit 1
fi

echo "=== 1/9. Обновление системы ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade -y

echo "=== 2/9. Установка пакетов ==="
apt-get install -y \
    python3 python3-venv python3-pip python3-dev \
    build-essential libpq-dev libffi-dev \
    postgresql postgresql-contrib \
    nginx \
    certbot python3-certbot-nginx \
    git curl ufw

echo "=== 3/9. Создание пользователя ${APP_USER} ==="
if ! id -u "${APP_USER}" &>/dev/null; then
    adduser --system --group --home "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

echo "=== 4/9. Создание PostgreSQL базы ==="
sudo -u postgres psql <<EOF
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '${DB_USER}') THEN
        CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
    END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec
ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
EOF

# Сохраним пароль для пользователя — пригодится для .env.
echo "DB_NAME=${DB_NAME}" > /root/tutor_db_credentials.txt
echo "DB_USER=${DB_USER}" >> /root/tutor_db_credentials.txt
echo "DB_PASS=${DB_PASS}" >> /root/tutor_db_credentials.txt
chmod 600 /root/tutor_db_credentials.txt
echo "  → Пароль БД сохранён в /root/tutor_db_credentials.txt"

echo "=== 5/9. Клонирование репозитория ==="
if [[ ! -d "${APP_DIR}/.git" ]]; then
    git clone "${REPO_URL}" "${APP_DIR}"
fi
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "=== 6/9. venv + зависимости ==="
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/venv"
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "=== 7/9. .env (если его ещё нет) ==="
if [[ ! -f "${APP_DIR}/.env" ]]; then
    SECRET_KEY=$("${APP_DIR}/venv/bin/python" -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    cat > "${APP_DIR}/.env" <<EOF
DJANGO_DEBUG=False
SECRET_KEY=${SECRET_KEY}
DJANGO_ALLOWED_HOSTS=zenchenkoim.ru,www.zenchenkoim.ru
DJANGO_CSRF_TRUSTED_ORIGINS=https://zenchenkoim.ru,https://www.zenchenkoim.ru
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
DJANGO_HSTS_SECONDS=60
DJANGO_LOG_LEVEL=INFO
EOF
    chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"
    chmod 640 "${APP_DIR}/.env"
    echo "  → .env создан с защитой DJANGO_HSTS_SECONDS=60 (для безопасного теста)"
fi

echo "=== 8/9. systemd + nginx конфиги ==="
cp "${APP_DIR}/deploy/tutor.service.example" /etc/systemd/system/tutor.service
cp "${APP_DIR}/deploy/nginx.conf.example" /etc/nginx/sites-available/tutor
ln -sf /etc/nginx/sites-available/tutor /etc/nginx/sites-enabled/tutor
rm -f /etc/nginx/sites-enabled/default

# Папка для ACME (Let's Encrypt http-01 challenge).
mkdir -p /var/www/letsencrypt
chown -R www-data:www-data /var/www/letsencrypt

# Чтобы nginx (www-data) мог стучаться в unix-сокет gunicorn,
# добавим www-data в группу tutor.
usermod -aG tutor www-data

# Папки, в которые писать tutor должен иметь право — заранее создаём.
sudo -u "${APP_USER}" mkdir -p "${APP_DIR}/media" "${APP_DIR}/staticfiles"

systemctl daemon-reload
nginx -t
systemctl reload nginx

echo "=== 9/9. UFW (фаервол) ==="
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo ""
echo "============================================================================"
echo "Bootstrap завершён."
echo ""
echo "Дальнейшие шаги (вручную):"
echo "  1. Проверь /opt/tutor/.env (особенно ALLOWED_HOSTS и DATABASE_URL)."
echo "  2. cd /opt/tutor && sudo -u tutor venv/bin/python manage.py migrate"
echo "  3. sudo -u tutor venv/bin/python manage.py collectstatic --noinput"
echo "  4. sudo -u tutor venv/bin/python manage.py createsuperuser"
echo "  5. systemctl enable --now tutor"
echo "  6. (после того как DNS A-запись на Reg.ru уже распространилась)"
echo "     certbot --nginx -d zenchenkoim.ru -d www.zenchenkoim.ru"
echo "  7. После проверки https подними DJANGO_HSTS_SECONDS=31536000 в .env"
echo "     и перезапусти: systemctl restart tutor"
echo ""
echo "Полная инструкция: deploy/DEPLOY.md"
echo "============================================================================"
