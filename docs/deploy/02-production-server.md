# 02 — Пром-сервер, образы и релизы

Пошаговая настройка сервера для production, способы деплоя образов и организация релизов. Пример IP: **213.171.31.180** (подставьте свой домен при настройке Nginx).

---

## 1. Подготовка сервера (один раз)

### 1.1 ОС и пользователь

- Рекомендуется **Ubuntu 22.04 LTS** или **Debian 12**.
- Создать отдельного пользователя для деплоя (например `deploy`) или использовать своего с ключами SSH.

```bash
# От имени root или через sudo
apt update && apt upgrade -y
adduser deploy   # при желании
usermod -aG docker deploy   # после установки Docker
```

### 1.2 Docker и Docker Compose

```bash
# Ubuntu/Debian
apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker && systemctl start docker
```

Проверка: `docker --version`, `docker compose version`.

### 1.3 Nginx на хосте

```bash
apt install -y nginx
```

Конфиг создаётся ниже (п. 2.2). Порты 80 (и при необходимости 443) слушает только Nginx.

### 1.4 Файрвол (рекомендуется)

```bash
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw enable
ufw status
```

### 1.5 Директория приложения

```bash
# Вариант: развернуть в домашней директории пользователя
export APP_DIR=/home/deploy/mkd-contacts
mkdir -p "$APP_DIR" && cd "$APP_DIR"
```

Дальше либо клонировать репозиторий, либо использовать только образы из реестра (см. раздел 3).

---

## 2. Деплой «сборка на сервере» (простой вариант, под РФ)

Образы собираются на том же сервере из исходников. Реестр не нужен, данные не уходят за пределы сервера.

### 2.1 Клонирование и первый запуск

```bash
cd $APP_DIR
git clone https://github.com/enedelko/mkd-contacts.git .
# или: git pull origin main   # при обновлении

cp .env.example .env
nano .env   # задать POSTGRES_PASSWORD, JWT_SECRET, TELEGRAM_BOT_TOKEN, BLIND_INDEX_PEPPER, VITE_TELEGRAM_BOT_USERNAME, при необходимости MASTER_KEY_PATH
```

Создать мастер-ключ шифрования (BE-02) и положить на сервер в защищённую директорию, например `/etc/mkd/encryption.key` (права 600, владелец — пользователь, от которого запускается compose). В `.env` указать `MASTER_KEY_PATH=/app/encryption.key` и в `docker-compose.yml` для backend добавить volume:  
`- /etc/mkd/encryption.key:/app/encryption.key:ro`.

```bash
docker compose build --no-cache
docker compose up -d
docker compose ps
```

### 2.2 Nginx на хосте

Создать конфиг (подставьте свой домен или IP):

```bash
sudo nano /etc/nginx/sites-available/mkd-contacts
```

Содержимое (для доступа по IP 213.171.31.180 без домена — оставить `server_name _`):

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включить сайт и перезагрузить Nginx:

```bash
sudo ln -sf /etc/nginx/sites-available/mkd-contacts /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Проверка: `curl -s http://213.171.31.180/ | head -5`, `curl -s http://213.171.31.180/api/health`.

### 2.3 Обновление (релиз) при деплое «сборка на сервере»

**Скрипт деплоя (рекомендуется):** по умолчанию перед обновлением создаётся бэкап (БД + манифест), затем выполняется сборка, подъём контейнеров и smoke-проверки. Запускать можно из любой директории.

```bash
# Из корня репозитория на сервере
./scripts/deploy-release.sh

# Деплой ветки main без бэкапа
./scripts/deploy-release.sh main --no-backup

# Деплой по тегу (с бэкапом)
./scripts/deploy-release.sh v1.0.0

# Запуск из домашней директории
APP_DIR=/home/deploy/mkd-contacts /home/deploy/mkd-contacts/scripts/deploy-release.sh main
```

Скрипт сохраняет в `backups/` дамп БД (`backup_YYYYMMDD_HHMMSS.sql`) и манифест (`backup_YYYYMMDD_HHMMSS.manifest.txt` с git rev, веткой и тегом). После подъёма контейнеров проверяются ответы frontend, backend и при возможности Nginx на хосте (см. `scripts/smoke-check.sh`).

**Ручное обновление:**

```bash
cd $APP_DIR
git fetch origin
git checkout main
git pull origin main
# При релизе по тегу: git checkout tags/v1.0.0
docker compose build --no-cache
docker compose up -d
docker compose ps
```

При необходимости предварительно сделать бэкап БД (см. п. 5).

---

## 3. Деплой через реестр образов (опционально)

Если нужна схема «сборка в CI → образы в реестре → на сервере только pull», можно использовать **GitHub Container Registry (ghcr.io)** или **Docker Hub**.

### 3.1 Репозиторий образов

- **ghcr.io**: `ghcr.io/enedelko/mkd-contacts-frontend:latest`, `ghcr.io/enedelko/mkd-contacts-backend:latest`.
- Для релизов использовать теги: `ghcr.io/enedelko/mkd-contacts-frontend:v1.0.0`, `...backend:v1.0.0`.

### 3.2 Сборка и push (локально или в CI)

Пример для GitHub Actions (файл `.github/workflows/build-push.yml`):

- Триггер: push в `main` или создание тега `v*`.
- Шаги: checkout → docker compose build → docker tag по коммиту/тегу → docker push в ghcr.io (логин через `GITHUB_TOKEN` или отдельный PAT с правами `write:packages`).

Пример для ручного push с рабочей машины:

```bash
docker compose build
docker tag mkd-contacts-frontend:latest ghcr.io/enedelko/mkd-contacts-frontend:latest
docker tag mkd-contacts-backend:latest ghcr.io/enedelko/mkd-contacts-backend:latest
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
docker push ghcr.io/enedelko/mkd-contacts-frontend:latest
docker push ghcr.io/enedelko/mkd-contacts-backend:latest
```

На сервере в `docker-compose.yml` заменить `build:` на `image: ghcr.io/enedelko/mkd-contacts-frontend:latest` (и backend аналогично). Тогда обновление на сервере — только `docker compose pull && docker compose up -d`.

**Важно для РФ:** если политика — не тянуть образы из-за рубежа, либо собирать образы на сервере (п. 2), либо поднять свой реестр (Harbor, Registry) внутри РФ и push туда из CI/локально.

---

## 4. Организация релизов

### 4.1 Версионирование

- **Семантические теги в Git:** `v1.0.0`, `v1.1.0`. Создание тега = релиз.
- Команды:
  - Создать тег: `git tag -a v1.0.0 -m "Релиз 1.0.0"`
  - Отправить теги: `git push origin v1.0.0`

### 4.2 Чек-лист перед релизом

1. Убедиться, что тесты/проверки пройдены, `main` стабилен.
2. Обновить версию/ changelog в репозитории при необходимости.
3. Создать тег `vX.Y.Z`, push в origin.
4. На пром-сервере: обновить код (или образы), выполнить деплой (п. 2.3 или pull + up).
5. Проверить главную страницу, `/api/health`, вход админа, форму.

### 4.3 Откат (rollback)

- **Сборка на сервере:**  
  `git checkout tags/v1.0.0` (или предыдущий коммит) → `docker compose build --no-cache && docker compose up -d`.
- **Образы из реестра:** переключить в `docker-compose.yml` тег образа на предыдущий (например `v1.0.0`), затем `docker compose pull && docker compose up -d`.
- При проблемах с миграциями БД — восстанавливать из бэкапа (см. п. 5).

---

## 5. Резервное копирование и восстановление

**Скрипт восстановления:** восстанавливает БД из ранее созданного бэкапа (файл `.sql`), при наличии архива образов (`.images.tar`) может загрузить образы, поднимает контейнеры и запускает smoke-проверки.

```bash
# Из корня репозитория: путь к .sql или базовое имя набора
./scripts/restore-backup.sh backups/backup_20250101_120000

# Без интерактивного подтверждения
./scripts/restore-backup.sh backups/backup_20250101_120000 -y

# Не загружать образы из .images.tar (если есть)
./scripts/restore-backup.sh backups/backup_20250101_120000 --no-images -y

# Запуск из другой директории
APP_DIR=/home/deploy/mkd-contacts ./scripts/restore-backup.sh /home/deploy/mkd-contacts/backups/backup_20250101_120000 -y
```

Формат бэкапа (создаётся скриптом деплоя): `backups/backup_YYYYMMDD_HHMMSS.sql` (дамп БД), `backups/backup_YYYYMMDD_HHMMSS.manifest.txt` (git rev, ветка, тег). Опционально можно добавлять `backup_*.images.tar` (docker save) для полного восстановления образов.

**Ручной дамп (перед обновлением):**

```bash
docker compose exec db pg_dump -U mkd mkd_contacts > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Ручное восстановление:**

```bash
docker compose stop backend frontend
docker compose exec -T db psql -U mkd mkd_contacts < backup_YYYYMMDD_HHMMSS.sql
docker compose up -d
```

Полную процедуру бэкапов (частота, хранение, S3 и т.д.) см. в бэклоге (OPS-01).

---

## 6. Краткая шпаргалка по серверу 213.171.31.180

| Действие | Команды |
|----------|--------|
| Первая настройка | Установить Docker, Docker Compose, Nginx (п. 1). Клонировать репо, настроить `.env`, создать ключ шифрования, настроить Nginx (п. 2.1–2.2). |
| Запуск | `cd /path/to/mkd-contacts && docker compose up -d` |
| Деплой релиза (с бэкапом и smoke) | `./scripts/deploy-release.sh` или `./scripts/deploy-release.sh v1.0.0` |
| Деплой без бэкапа | `./scripts/deploy-release.sh main --no-backup` |
| Восстановление из бэкапа | `./scripts/restore-backup.sh backups/backup_YYYYMMDD_HHMMSS [-y]` |
| Smoke-проверки | `./scripts/smoke-check.sh` |
| Логи | `docker compose logs -f backend` |
| Остановка | `docker compose down` (том БД сохраняется) |

После настройки приложение доступно по адресу `http://213.171.31.180` (или по домену, если прописать его в `server_name` и при необходимости настроить HTTPS).
