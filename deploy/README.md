# `deploy/` — конфиги для прода

| Файл | Что это |
|------|---------|
| **[DEPLOY.md](DEPLOY.md)** | 📖 Главная пошаговая инструкция: от пустого VPS до `https://zenchenkoim.ru`. **Начни отсюда.** |
| `setup_server.sh` | Bash-скрипт для первичной настройки Ubuntu 24.04. Запускается один раз под root: ставит python/postgres/nginx/certbot, создаёт пользователя `tutor`, БД, `.env`, копирует конфиги. |
| `nginx.conf.example` | Шаблон конфига nginx (reverse proxy на gunicorn через unix-сокет, отдача `/media/`). Скрипт сам копирует в `/etc/nginx/sites-available/tutor`. После `certbot --nginx` он сам допишет SSL-блок. |
| `tutor.service.example` | systemd unit для gunicorn. Скрипт сам копирует в `/etc/systemd/system/tutor.service`. |

## Краткий план (без подробностей — детали в DEPLOY.md)

1. Купить VPS на Timeweb (Ubuntu 24.04, ~250₽/мес).
2. Настроить DNS на Reg.ru: A-записи `zenchenkoim.ru` и `www.zenchenkoim.ru` → IP сервера.
3. SSH на сервер: `wget … setup_server.sh && bash setup_server.sh`.
4. `migrate`, `collectstatic`, `createsuperuser`, перенос контента, `systemctl enable --now tutor`.
5. `certbot --nginx -d zenchenkoim.ru -d www.zenchenkoim.ru`.
6. Поднять `DJANGO_HSTS_SECONDS` до года.

## Обновление кода в будущем

```bash
ssh root@<IP>
cd /opt/tutor
sudo -u tutor git pull
sudo -u tutor venv/bin/pip install -r requirements.txt
sudo -u tutor venv/bin/python manage.py migrate
sudo -u tutor venv/bin/python manage.py collectstatic --noinput
systemctl restart tutor
```
