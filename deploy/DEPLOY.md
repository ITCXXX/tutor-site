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

# Запускаем gunicorn (HTTP) и daphne (WebSocket доски) через systemd
systemctl enable --now tutor tutor-ws
systemctl status tutor tutor-ws
# Если красно — смотри: journalctl -u tutor -n 50   (для доски: journalctl -u tutor-ws -n 50)
```

После этого сайт уже работает по http (без SSL): открыть `http://<IP>` в браузере.
Совместная доска (`/board/`) обслуживается через `tutor-ws` (daphne) — nginx роутит
`/ws/` на него; после https доска пойдёт по `wss://`.

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

## Часть 10. Ретранслятор для голоса (coturn)

Голосовая связь на доске работает и без него: браузеры соединяются напрямую.
Но примерно **у каждого пятого** участника домашний роутер или мобильный
оператор прямое соединение не пропускают — у такого человека в панели голоса
будет написано «не удалось соединиться». Эта часть чинит именно такие случаи.

Для остальных ретранслятор не задействуется, поэтому задержка у большинства
не вырастет.

Ставится один раз, минут за двадцать. Голос до этого уже должен работать
хотя бы между двумя вашими устройствами в одной сети — иначе сначала ищите
проблему в другом месте.

### 10.1. Поставить coturn

```bash
apt update && apt install -y coturn
```

Разрешить автозапуск (в Debian/Ubuntu это отдельный флаг):

```bash
sed -i 's/^#*TURNSERVER_ENABLED=.*/TURNSERVER_ENABLED=1/' /etc/default/coturn
```

### 10.2. Придумать общий секрет

Это пароль, которым сайт подписывает временные пропуска, а coturn их
проверяет. Постоянных логинов нет — так вшитый в страницу пароль не утечёт.

```bash
openssl rand -hex 32
```

Скопируйте вывод — он понадобится дважды, в двух местах, и должен совпадать.

### 10.3. Конфиг

```bash
cp /opt/tutor/deploy/coturn.conf.example /etc/turnserver.conf
nano /etc/turnserver.conf
```

Заменить в файле:

| Что | На что |
|-----|--------|
| `<IP_ВАШЕГО_VPS>` | белый IP сервера |
| `<ТОТ_ЖЕ_СЕКРЕТ_ЧТО_В_ENV>` | секрет из шага 10.2 |

Домен `zenchenkoim.ru` менять не нужно, если он ваш.

### 10.4. Дать coturn читать сертификат

Тут спотыкаются чаще всего. coturn работает под своим пользователем и по
умолчанию **не имеет права** читать файлы Let's Encrypt — сервис молча не
поднимется по TLS.

```bash
groupadd -f ssl-cert
usermod -aG ssl-cert turnserver
chgrp -R ssl-cert /etc/letsencrypt/live /etc/letsencrypt/archive
chmod -R g+rX /etc/letsencrypt/live /etc/letsencrypt/archive
```

Certbot при обновлении сертификата сбрасывает права обратно, поэтому добавим
хук, который их возвращает и перезапускает coturn:

```bash
cat > /etc/letsencrypt/renewal-hooks/deploy/coturn.sh <<'EOF'
#!/bin/sh
chgrp -R ssl-cert /etc/letsencrypt/live /etc/letsencrypt/archive
chmod -R g+rX /etc/letsencrypt/live /etc/letsencrypt/archive
systemctl restart coturn
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/coturn.sh
```

Без этого хука голос у «трудных» участников однажды сломается через три
месяца — при первом же продлении сертификата, и найти причину будет тяжело.

### 10.5. Открыть порты

```bash
ufw allow 3478/tcp
ufw allow 3478/udp
ufw allow 5349/tcp
ufw allow 5349/udp
ufw allow 49160:49200/udp
```

Диапазон `49160:49200` — это порты, через которые пойдёт сам звук. Без них
ретранслятор ответит на запрос, но звука не будет.

### 10.6. Прописать секрет на сайте

В `/opt/tutor/.env` добавить (секрет — **тот же самый**, что в 10.2):

```
TURN_URLS=turn:zenchenkoim.ru:3478,turns:zenchenkoim.ru:5349
TURN_SECRET=<СЕКРЕТ_ИЗ_ШАГА_10.2>
```

И перезапустить оба сервиса сайта:

```bash
systemctl restart tutor tutor-ws
```

### 10.7. Запустить и проверить

```bash
systemctl enable --now coturn
systemctl status coturn --no-pager
```

Проверка, что порты слушаются:

```bash
ss -lnup | grep -E '3478|5349'
ss -lntp | grep -E '3478|5349'
```

Проверка, что сайт выдаёт пропуска (должны появиться `turn:` и `turns:`):

```bash
cd /opt/tutor && sudo -u tutor venv/bin/python manage.py shell -c \
  "from board.turn import ice_servers; print(ice_servers())"
```

Живая проверка: откройте доску, включите голос и посмотрите в панели, что
участники переходят в «на связи». Самый честный тест — попросить кого-нибудь
подключиться **с мобильного интернета**, а не из вашей же сети: именно там
прямое соединение чаще всего и не проходит.

### Если голос всё равно не соединяется

| Симптом | Куда смотреть |
|---------|---------------|
| coturn не стартует | `journalctl -u coturn -n 50` — почти всегда права на сертификат (шаг 10.4) |
| В панели «не удалось соединиться» | открыты ли порты 49160–49200/udp; совпадает ли секрет в `.env` и `/etc/turnserver.conf` |
| Пусто в списке серверов | `.env` не перечитан — перезапустите `tutor` и `tutor-ws` |
| Работает у вас, не работает у ученика | проверьте с мобильного интернета: это и есть тот случай, ради которого ставился coturn |

### Когда понадобится не ретранслятор, а медиасервер

coturn перекидывает звук, но не смешивает его: участники по-прежнему
соединяются каждый с каждым. При двух-трёх это лучший вариант — минимум
задержки. Начиная примерно с шести человек соединений становится слишком
много, и тогда нужен медиасервер (SFU), где каждый шлёт звук только на
сервер. Это отдельная работа: конфиг сервера плюс переписывание браузерной
части. Список серверов связи сайт уже отдаёт из `board/turn.py`, так что
переезд не потребует правок в разметке и настройках страницы.

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
systemctl restart tutor tutor-ws
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
| Доска не подключается (WebSocket) | `systemctl status tutor-ws`, `journalctl -u tutor-ws -n 50`; проверь `location /ws/` в nginx и что `certbot` перенёс его в https-блок |
