# Деплой tutor_site на Timeweb Cloud Server (Ubuntu 24.04)

Полный путь от пустого VPS до работающего `https://zenchenkoim.ru` за ~30 минут.

---

## Часть 0. Что нужно перед началом

- ✅ Домен `zenchenkoim.ru` (у тебя на Reg.ru)
- ⏳ VPS на Timeweb Cloud (см. шаг 1)
- ✅ GitHub-репозиторий с актуальным кодом

---

## Часть 1. Покупка и базовая настройка VPS

1. Зайти на [timeweb.cloud](https://timeweb.cloud), создать **Cloud Server**:
   - **OS**: `Ubuntu 24.04 LTS`
   - **Тариф**: минимальный (1 vCPU, 1 ГБ RAM, 15 ГБ NVMe) — около 250–300 ₽/мес
   - **Регион**: ближайший (Москва или Петербург)
   - **SSH-ключ**: добавить свой публичный ключ (или получить root-пароль на email)
2. Дождаться, пока сервер запустится. Записать **IP-адрес**.

---

## Часть 2. DNS на Reg.ru

В личном кабинете Reg.ru → раздел «Мои домены» → `zenchenkoim.ru` → «DNS-серверы и управление зоной»:

| Тип | Имя | Значение | TTL |
|-----|-----|----------|-----|
| A | `@` | `<IP_ВАШЕГО_VPS>` | 3600 |
| A | `www` | `<IP_ВАШЕГО_VPS>` | 3600 |

Сохранить. Подождать **15 минут — 2 часа**, пока DNS распространится. Проверить:
```bash
nslookup zenchenkoim.ru
```
должен показать твой IP.

---

## Часть 3. SSH на сервер и запуск bootstrap

С локалки (Windows: PowerShell или Git Bash):

```bash
ssh root@<IP>
```

На сервере:

```bash
# Скачиваем setup-скрипт прямо из репо (он клонирует репо целиком)
wget https://raw.githubusercontent.com/ITCXXX/tutor-site/main/deploy/setup_server.sh
bash setup_server.sh
```

Скрипт сделает:
- обновит систему
- поставит python, postgres, nginx, certbot, git, ufw
- создаст пользователя `tutor`
- создаст PostgreSQL базу + случайный пароль (сохранён в `/root/tutor_db_credentials.txt`)
- клонирует репо в `/opt/tutor`
- создаст venv и поставит зависимости из `requirements.txt`
- создаст `/opt/tutor/.env` с правильными ALLOWED_HOSTS и DATABASE_URL
- скопирует nginx-конфиг и systemd unit
- откроет фаервол (22, 80, 443)

**Скрипт сам сообщит, что делать дальше.** Это шаги 4–9 ниже.

---

## Часть 4. Миграции и статика

```bash
cd /opt/tutor
sudo -u tutor venv/bin/python manage.py migrate
sudo -u tutor venv/bin/python manage.py collectstatic --noinput
```

Должно пройти без ошибок (если упало — смотри `journalctl -xe`).

---

## Часть 5. Перенос данных с локалки

Есть два пути. **Рекомендую путь A** (чище и проще).

### 5.A. (рекомендуется) Переустановка контента через seed-команды

Все курсы, уроки, генераторы и группы заданий описаны кодом в репозитории
(`populate_oge15_*.py`, `seed_oge16/17/18/19.py`). Переустановка с нуля:

```bash
cd /opt/tutor

# Все 35 групп заданий 1-5 (Шины/Дороги/План/Печи/Форматы/Квартира)
sudo -u tutor venv/bin/python manage.py populate_oge15_run_all

# Задания 16-19 (Окружность, Четырёхугольники, Клетки, Высказывания)
sudo -u tutor venv/bin/python manage.py seed_oge16
sudo -u tutor venv/bin/python manage.py seed_oge17
sudo -u tutor venv/bin/python manage.py seed_oge18
sudo -u tutor venv/bin/python manage.py seed_oge19

# Прочие seed-скрипты, если нужны:
# sudo -u tutor venv/bin/python manage.py seed_oge6
# ... seed_oge7, seed_oge8, seed_oge9, ...
# sudo -u tutor venv/bin/python manage.py populate_ege1
# ... populate_ege2, ...
```

Список всех доступных скриптов:
```bash
sudo -u tutor venv/bin/python manage.py help 2>&1 | grep -E "populate|seed"
```

После этого нужно **скопировать media-файлы** (картинки планов и таблиц
из `oge15_*` групп — без них у тех заданий не будет иллюстраций):

```powershell
# С локалки (Windows PowerShell):
cd D:\tutor_site
scp -r media root@<IP>:/tmp/media-upload/
```

```bash
# На сервере:
sudo cp -r /tmp/media-upload/* /opt/tutor/media/
sudo chown -R tutor:tutor /opt/tutor/media
rm -rf /tmp/media-upload
```

**Плюс этого пути**: репо — единственный источник правды. Если потом
поменяешь генератор и хочешь обновить прод — просто `git pull` и
`python manage.py seed_oge17` на сервере.

### 5.B. (fallback) Перенос через dumpdata

Используй, если в БД на локалке есть РУЧНЫЕ правки контента
(материалы залитые через админку, тонкая настройка курсов и т.п.),
которые нельзя восстановить через seed.

На локалке (Windows PowerShell):

```powershell
cd D:\tutor_site
.\venv\Scripts\python.exe manage.py dumpdata_for_deploy > deploy_data.json
scp deploy_data.json root@<IP>:/tmp/
scp -r media root@<IP>:/tmp/media-upload/
```

На сервере:

```bash
sudo -u tutor cp /tmp/deploy_data.json /opt/tutor/
cd /opt/tutor
sudo -u tutor venv/bin/python manage.py loaddata deploy_data.json

sudo cp -r /tmp/media-upload/* /opt/tutor/media/
sudo chown -R tutor:tutor /opt/tutor/media

rm /tmp/deploy_data.json
rm -rf /tmp/media-upload
```

⚠️ Поля `Course.created_by` и подобные после loaddata будут NULL
(так как соответствующих юзеров на проде нет) — это нормально.

---

## Часть 6. Создаём суперюзера и запускаем сервис

```bash
cd /opt/tutor
sudo -u tutor venv/bin/python manage.py createsuperuser
# (логин/email/пароль — придумать)

# Запускаем gunicorn через systemd
systemctl enable --now tutor
systemctl status tutor
# Если красно — смотри: journalctl -u tutor -n 50
```

После этого сайт уже работает по http (без SSL): открыть `http://<IP>` в браузере.

---

## Часть 7. SSL через Let's Encrypt

**ТОЛЬКО** когда DNS A-запись уже распространилась (`nslookup zenchenkoim.ru` показывает твой IP):

```bash
certbot --nginx -d zenchenkoim.ru -d www.zenchenkoim.ru
# На вопросы:
#   - email — свой
#   - согласие с TOS — Y
#   - newsletter — N
#   - "Redirect HTTP traffic to HTTPS, removing HTTP access?" — 2 (Redirect)
```

Сертификат на 90 дней, certbot сам настроит автообновление через таймер systemd.

---

## Часть 8. Проверка

1. Открыть `https://zenchenkoim.ru` — должен открыться сайт.
2. Открыть `https://zenchenkoim.ru/admin/` — войти под суперюзером.
3. Проверить любой урок: картинки заданий должны отображаться.

---

## Часть 9. Поднимаем HSTS до года

После того как убедился, что https работает безупречно:

```bash
nano /opt/tutor/.env
# заменить:
#   DJANGO_HSTS_SECONDS=60
# на:
#   DJANGO_HSTS_SECONDS=31536000

systemctl restart tutor
```

Браузеры запомнят «сайт только по https» на год → защита от downgrade-атак.

---

## Обновление кода в будущем

Когда внесёшь изменения локально, закоммитишь и запушишь в GitHub:

```bash
ssh root@<IP>
cd /opt/tutor
sudo -u tutor git pull
sudo -u tutor venv/bin/pip install -r requirements.txt   # если новые зависимости
sudo -u tutor venv/bin/python manage.py migrate          # если новые миграции
sudo -u tutor venv/bin/python manage.py collectstatic --noinput
systemctl restart tutor
```

(Можно запихнуть это в скрипт `deploy/update.sh` — позже сделаю, если будет нужно.)

---

## Полезные команды

```bash
# Логи приложения
journalctl -u tutor -f

# Логи nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Перезапуск
systemctl restart tutor
systemctl reload nginx

# Бэкап БД (на сервере)
sudo -u postgres pg_dump tutor_db > backup_$(date +%F).sql

# Бэкап БД на локалку
scp root@<IP>:/root/backup_*.sql .

# Свободное место
df -h
du -sh /opt/tutor /var/lib/postgresql
```

---

## Если что-то пошло не так

| Симптом | Куда смотреть |
|---------|---------------|
| `502 Bad Gateway` | `journalctl -u tutor -n 50` — gunicorn упал |
| `404` при открытии главной | `nginx -t`, проверить sites-enabled |
| Картинки заданий не грузятся | `ls -la /opt/tutor/media`, права `tutor:tutor` |
| `csrf verification failed` | проверить `DJANGO_CSRF_TRUSTED_ORIGINS` в `.env` |
| `DisallowedHost` | проверить `DJANGO_ALLOWED_HOSTS` в `.env` |
| `relation "..." does not exist` | забыл `migrate` |
| Статика без стилей | забыл `collectstatic` |
