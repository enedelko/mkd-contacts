# LOST-01, BE-02, ADM-01, ADM-04 — Базовый админ и схема БД

Инструкции по миграциям, шифрованию, Telegram OAuth и управлению админами ([03-basic-admin.md](../srs/03-basic-admin.md)).

---

## 1. Миграции (LOST-01)

### 1.1. Применение при развёртывании

Backend при старте выполняет `alembic upgrade head` (см. `backend/entrypoint.sh`). Либо вручную:

```bash
docker compose exec backend alembic upgrade head
```

Или локально (при наличии `DATABASE_URL`):

```bash
cd backend && export DATABASE_URL=postgresql://... && alembic upgrade head
```

### 1.2. Откат (SR-LOST01-007)

Только там, где это безопасно и предусмотрено процессом:

```bash
alembic downgrade -1
```

Перед откатом — резервная копия БД.

### 1.3. Таблицы

- **admins** — telegram_id (PK), role, created_at
- **premises** — id, cadastral_number, area, entrance, floor, premises_type, premises_number
- **contacts** — связь с premises, ПДн (зашифрованы), phone_idx/email_idx/telegram_id_idx, status и др.
- **oss_voting** — contact_id, position_for, vote_format, voted_in_ed, voted

---

## 2. BE-02 — Шифрование

- Ключ только из файла: `MASTER_KEY_PATH` (по умолчанию `/run/secrets/master_key`). При старте, если `MASTER_KEY_PATH` задан в окружении, приложение проверяет наличие ключа; при отсутствии — не стартует (AF-1).
- Не передавать ключ через ENV (SR-BE02-006).
- Blind Index: задать `BLIND_INDEX_PEPPER` в окружении; используется для колонок phone_idx, email_idx, telegram_id_idx.

---

## 3. ADM-01 — Telegram OAuth и первый админ (Bootstrap)

### 3.1. Настройка бота

1. Создать бота через [@BotFather](https://t.me/botfather).
2. Выполнить `/setdomain` и указать домен фронтенда (например `yourdomain.ru`).

### 3.2. Bootstrap первого администратора (SR-ADM01-008)

Первый админ добавляется вручную в БД (без API):

```bash
docker compose exec db psql -U mkd -d mkd_contacts -c \
  "INSERT INTO admins (telegram_id, role) VALUES ('123456789', 'super_administrator');"
```

Подставить свой `telegram_id` (получить можно после входа через виджет или у @userinfobot).

После появления записи в `admins` пользователь может нажать «Войти через Telegram» и получить JWT.

### 3.3. Callback и JWT

- **GET** `/api/auth/telegram/callback?hash=...&id=...&first_name=...&username=...&auth_date=...`
- При успехе: `{"access_token": "...", "token_type": "bearer", "role": "..."}`.
- При отказе (не в white-list): 403, `{"detail": "Access denied: not in white-list"}`.

---

## 4. ADM-04 — Управление админами

Доступно только с JWT с ролью `super_administrator`.

- **GET** `/api/superadmin/admins` — список (telegram_id, role, created_at).
- **POST** `/api/superadmin/admins` — тело: `{"telegram_id": "...", "role": "administrator"}`.
- **DELETE** `/api/superadmin/admins/{telegram_id}` — удалить. Нельзя удалить себя и последнего super_administrator.

Заголовок: `Authorization: Bearer <access_token>`.
