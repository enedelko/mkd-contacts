# Кворум-МКД (mkd-contacts)

Веб-приложение для сбора контактов собственников и проживающих в МКД, подготовки ОСС, расчёта кворума. Обработка ПДн по 152-ФЗ: шифрование, локализация в РФ, аудит доступа.

---

## Стек и окружение

| Слой | Технологии |
|------|------------|
| **Frontend** | React 18, Vite, react-router-dom. SPA: каскадные фильтры помещений, форма анкеты, админ-разделы. |
| **Backend** | Python 3.11, FastAPI, Uvicorn. Модули: auth (Telegram OAuth + JWT), импорт реестра, контакты, валидация, аудит. |
| **Бот** | Python 3.12, aiogram 3.x, webhook. FSM в SQLite (volume `bot_data`), HTTP-клиент к backend по внутренней сети Docker. |
| **БД** | PostgreSQL 15+. Таблицы: `admins`, `premises`, `contacts` (ПДн зашифрованы, Blind Index), `oss_voting`, `audit_log`, `premise_type_aliases`, `bot_unrecognized`. |
| **Инфра** | Docker Compose (frontend, backend, db, bot). Публичный вход — **Nginx на хосте**; порты контейнеров только localhost (8080 → frontend, 8000 → backend, 8443 → bot/webhook). |

Детали: [docs/arch.md](docs/arch.md).

---

## Структура репозитория

```
mkd-contacts/
├── backend/                    # FastAPI-приложение
│   ├── app/
│   │   ├── main.py             # Точка входа, подключение роутеров, CORS
│   │   ├── db.py               # Сессия БД (sync), check_admins_table
│   │   ├── crypto.py           # BE-02: шифрование ПДн (AES), мастер-ключ
│   │   ├── auth_telegram.py    # Проверка Telegram OAuth, белый список admins
│   │   ├── auth_password.py    # Логин/пароль: bcrypt, get_admin_by_login
│   │   ├── jwt_utils.py        # JWT: create_access_token, require_admin, require_super_admin
│   │   ├── submit_service.py   # CORE-02: приём анкеты, валидация, шифрование, лимиты
│   │   ├── import_register.py  # Парсинг CSV/XLS реестра (используется роутером)
│   │   ├── validators.py       # Нормализация телефона/email/telegram
│   │   ├── room_normalizer.py  # Нормализация номера помещения (FE-03, CORE-01)
│   │   ├── captcha.py          # Turnstile
│   │   ├── rate_limit.py       # BE-04: лимит запросов по IP и telegram_id_idx
│   │   ├── auth_bot.py         # BOT-01..04: X-Bot-Token для запросов от бота
│   │   ├── bot_premise_resolver.py # BOT-01: fuzzy-поиск помещения, синонимы типов
│   │   ├── config.py
│   │   └── routers/            # API-эндпоинты
│   │       ├── auth.py         # /api/auth — Telegram callback, логин/пароль, смена пароля
│   │       ├── policy.py       # /api/policy/admins — публичный список админов (ФИО, помещение)
│   │       ├── superadmin.py   # /api/superadmin/* — CRUD админов, словарь бота, лог нераспознанных (только суперадмин)
│   │       ├── premises.py     # /api/premises — фильтры подъезд/этаж/тип/номер
│   │       ├── submit.py       # POST /api/submit — приём анкеты (публично)
│   │       ├── bot.py          # /api/bot/* — эндпоинты для Telegram-бота (опрос собственников)
│   │       ├── admin_contacts.py # /api/admin/contacts — контакты, смена статуса (VAL-01)
│   │       ├── import_register.py # /api/admin/import/* — реестр, контакты, шаблон XLSX
│   │       ├── audit.py        # /api/admin/audit — просмотр лога
│   │       └── quorum.py       # /api/buildings/{id}/quorum — расчёт кворума
│   ├── alembic/
│   │   └── versions/           # Миграции (LOST-01)
│   │       ├── 001_admins_premises_contacts_oss_voting.py
│   │       ├── 002_audit_log.py
│   │       ├── 003_*.py, 004_*.py, 005_admins_login_password.py
│   │       ├── 006_admins_full_name_premises.py  # ФИО и помещение для админов
│   │       └── 008_bot_tables.py  # BOT-01..04: contacts.source, premise_type_aliases, bot_unrecognized
│   ├── entrypoint.sh           # При старте: alembic upgrade head, затем uvicorn
│   ├── Dockerfile
│   └── requirements.txt
│
├── bot/                        # Telegram-бот (BOT-01..04)
│   ├── app/
│   │   ├── main.py             # Точка входа, webhook, регистрация роутеров
│   │   ├── config.py           # TELEGRAM_BOT_TOKEN, BOT_API_TOKEN, WEBHOOK_HOST/SECRET и т.п.
│   │   ├── backend_client.py   # Async HTTP-клиент к backend (/api/bot/*)
│   │   ├── states.py           # FSM-состояния (IDLE, PREMISES_OVERVIEW, VOTE_METHOD, ...)
│   │   ├── keyboards.py        # Inline/Reply-клавиатуры
│   │   ├── storage/
│   │   │   └── sqlite_storage.py # FSM в SQLite (volume bot_data), TTL сессий
│   │   └── handlers/           # Обработчики по группам состояний
│   │       ├── start.py        # /start, /help, /mydata, IDLE
│   │       ├── premises.py     # Поиск и привязка помещений (BOT-01, часть BOT-02)
│   │       ├── survey.py       # VOTE_METHOD, BARRIER_VOTE, DONE
│   │       ├── contact.py      # CONTACT_MANAGE, ENTER_PHONE, CONFIRM_DELETE
│   │       └── mydata.py       # MY_DATA_VIEW, CONFIRM_FORGET
│   ├── Dockerfile              # Контейнер бота (aiogram + aiohttp + aiosqlite)
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Роутинг, навбар, проверка JWT
│   │   ├── main.jsx
│   │   ├── pages/               # Страницы по маршрутам
│   │   │   ├── Premises.jsx     # /premises — каскадные фильтры, переход к форме
│   │   │   ├── Form.jsx         # /form — анкета (FE-04), капча, submit
│   │   │   ├── Policy.jsx       # /policy — политика конфиденциальности, раздел 9 — список админов
│   │   │   ├── Login.jsx        # /login — вход Telegram / логин-пароль
│   │   │   ├── AuthCallback.jsx # /auth/callback — callback после Telegram
│   │   │   ├── Upload.jsx       # /upload — загрузка реестра/контактов (админ)
│   │   │   ├── AdminContacts.jsx    # /admin/contacts — добавление/редактирование контакта
│   │   │   ├── AdminContactsList.jsx # /admin/contacts/list — список, смена статуса
│   │   │   ├── AuditLog.jsx     # /admin/audit
│   │   │   ├── SuperadminAdmins.jsx # /admin/superadmin — белый список админов, ФИО/помещение
│   │   │   ├── BotAliases.jsx       # /admin/bot-aliases — словарь синонимов типов помещений (бот)
│   │   │   └── BotUnrecognized.jsx  # /admin/bot-unrecognized — лог нераспознанных вводов бота
│   │   │   ├── ChangePassword.jsx   # /admin/change-password
│   │   ├── components/          # TelegramIcon и др.
│   │   └── utils/               # phoneFormat, entranceLabel
│   ├── Dockerfile               # Сборка Vite, Nginx раздаёт статику
│   └── package.json
│
├── docs/
│   ├── arch.md                 # Архитектура, стек, схема деплоя
│   ├── brd.md                  # Бизнес-требования
│   ├── feature-list.md         # Таблица фич (ID, статус Готово/Бэклог), связь с SRS
│   ├── site-map.md             # Маршруты фронта, кто куда попадает
│   ├── srs/                    # Спецификация требований (SRS)
│   │   ├── 00-INDEX.md         # Навигация по SRS, карта зависимостей, быстрый поиск по коду фичи
│   │   ├── 01-definitions.md   # Атомарность требований SR-xxx
│   │   ├── 02-BE-01-infrastructure.md
│   │   ├── 03-basic-admin.md   # LOST-01, BE-02, ADM-01, ADM-04; модель admins/premises/contacts
│   │   ├── 04-import-chain.md  # CORE-01, LOST-02
│   │   ├── 05-add-contacts.md  # FE-03, FE-04, форма анкеты, Policy (SR-FE04-007, SR-FE04-013)
│   │   ├── 06-validation.md    # VAL-01, CORE-02
│   │   ├── 07-audit-ratelimit.md, 08-core04-quorum.md
│   │   ├── 09-admin-login-password.md, 10-import-contacts.md, 11-adm02-adm05-*.md
│   │   ├── 98-backlog.md      # Фичи в бэклоге
│   │   └── 99-summary.md      # Итоговая сводка
│   └── deploy/                 # Пошаговое развёртывание
│       ├── 01-bootstrap.md     # Быстрый старт, .env, Nginx, docker compose up
│       ├── 02-production-server.md
│       ├── 03-basic-admin.md   # Bootstrap первого админа (INSERT в admins)
│       ├── 04-import-chain.md, 05-add-contacts.md, 06-validation.md
│       └── 05-bot-setup.md     # BOT-01..04: настройка и проверка Telegram-бота
│       └── nginx-host.example.conf  # Пример конфига Nginx на хосте
│
├── scripts/
│   ├── deploy-release.sh       # Деплой релиза
│   ├── smoke-check.sh          # Проверка доступности после деплоя
│   ├── set-admin-login-password-bootstrap.sh  # Первая настройка логина/пароля
│   ├── set-admin-login-password.sh
│   ├── restore-backup.sh
│   └── ...
│
├── docker-compose.yml          # Сервисы: db, backend, frontend, bot (порты на 127.0.0.1)
├── docker-compose.override.yml
├── .env.example                # Шаблон переменных (POSTGRES_*, JWT_SECRET, TELEGRAM_BOT_TOKEN, BLIND_INDEX_PEPPER, MASTER_KEY_PATH, BOT_API_TOKEN, WEBHOOK_SECRET, WEBHOOK_HOST)
└── backups/                   # Дампы БД (если настроено)
```

---

## Деплой и миграции

- **Запуск:** на хосте в РФ поднимают Nginx, затем `docker compose up -d`. Конфиг Nginx: [docs/deploy/nginx-host.example.conf](docs/deploy/nginx-host.example.conf).
- **Миграции:** выполняются **автоматически** при каждом старте контейнера backend: в [backend/entrypoint.sh](backend/entrypoint.sh) перед `uvicorn` вызывается `alembic upgrade head` (если задан `DATABASE_URL`). Ручной запуск при обычном деплое не нужен.
- **Первый админ:** добавляется вручную в БД (INSERT в `admins`), см. [docs/deploy/03-basic-admin.md](docs/deploy/03-basic-admin.md).
- **Telegram-бот (опрос собственников):** настройка webhook, Nginx и секретов описана в [docs/deploy/05-bot-setup.md](docs/deploy/05-bot-setup.md).
- **Production:** обязательно свой `.env` с уникальными паролями и секретами; дефолты в `docker-compose.yml` — только для разработки ([docs/deploy/01-bootstrap.md](docs/deploy/01-bootstrap.md)).

---

## Где что искать (быстрый контекст)

| Задача | Где смотреть |
|--------|----------------|
| Требования к фиче, коду | [docs/srs/00-INDEX.md](docs/srs/00-INDEX.md) → нужный модуль SRS (03–11, 98) |
| Реализовано ли по SRS | [docs/feature-list.md](docs/feature-list.md) |
| API-эндпоинты | [backend/app/main.py](backend/app/main.py) (подключение роутеров), папка [backend/app/routers/](backend/app/routers/) |
| Схема БД, миграции | [backend/alembic/versions/](backend/alembic/versions/), SRS [03-basic-admin.md](docs/srs/03-basic-admin.md) |
| Страницы и маршруты фронта | [frontend/src/App.jsx](frontend/src/App.jsx), [frontend/src/pages/](frontend/src/pages/), [docs/site-map.md](docs/site-map.md) |
| Развёртывание с нуля | [docs/deploy/01-bootstrap.md](docs/deploy/01-bootstrap.md) |
| Настройка Telegram-бота | [docs/deploy/05-bot-setup.md](docs/deploy/05-bot-setup.md) |
| Архитектура и стек | [docs/arch.md](docs/arch.md) |
