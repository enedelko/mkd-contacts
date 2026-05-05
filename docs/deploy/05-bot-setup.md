# BOT-01..04: Настройка Telegram-бота

## Предварительные условия

- Бот создан через @BotFather (тот же, что используется для Login Widget).
- Домен настроен, HTTPS через Nginx работает.
- `.env` содержит `BOT_API_TOKEN`, `WEBHOOK_SECRET`, `WEBHOOK_HOST`.

## Работа за NAT

Webhook работает так: **Telegram** отправляет HTTPS POST на ваш URL (`https://ваш-домен/api/tg-wh/...`). То есть входящие запросы из интернета должны доходить до сервера, где крутится Nginx.

| Ситуация | Что нужно |
|----------|-----------|
| Сервер с белым IP (VPS, выделенный сервер) | Достаточно настроить Nginx и HTTPS. NAT нет — сервер доступен снаружи. |
| Сервер за NAT (домашний роутер, офис) | На роутере сделать **проброс порта 443** (TCP) на IP машины с Nginx. Домен должен указывать на ваш внешний (белый) IP роутера. |

**Проверка «доходит ли снаружи до webhook»:**

1. С телефона или другого устройства **вне вашей сети** (мобильный интернет или другой провайдер) откройте в браузере:
   `https://ваш-домен/api/tg-wh/`  
   Ожидается ответ от бота (например 200 или 405 Method Not Allowed) — значит Telegram тоже сможет достучаться.

2. Если открываете с того же компьютера, где крутится Nginx, — это не проверка «из интернета». Нужен запрос именно извне (другая сеть).

Исходящие запросы (бот → backend, бот → api.telegram.org при `setWebhook`) из-за NAT не блокируются: исходящий трафик из домашней/офисной сети обычно разрешён.

## Исходящий доступ к Telegram через SOCKS5 (опционально)

Если сервер не может напрямую достучаться до `api.telegram.org` (но есть локальный или сетевой SOCKS5), задайте в `.env`:

```bash
TELEGRAM_SOCKS5_PROXY=socks5h://127.0.0.1:1080
# или с учётной записью: socks5h://user:secret@proxy-host:1080
```

Предпочтительно **`socks5h://`**: DNS для целевого хоста выполняется на стороне прокси. При **`socks5://`** клиент сам резолвит `api.telegram.org` и подключается по IP — на части сетей это даёт таймауты при доступе к Telegram.

Переменная пробрасывается в контейнеры `bot`, `backend` и `uptime-check`. Её используют только **исходящие** запросы к Telegram Bot API (регистрация webhook, отправка сообщений из бота, fallback `getMe` на backend, алерты uptime-check). Входящий webhook от Telegram на ваш Nginx на прокси не зависит.

На хосте для скриптов (`scripts/ssh-notify-telegram.sh`, `scripts/uptime-check.sh` вне Docker, `scripts/remote/mkd-backup-dump`) та же переменная может быть задана в `.env` приложения или в окружении процесса/cron.

**Проверка вручную через curl:** используйте короткую опцию `-x` (совместима с BusyBox и полным curl), значение в кавычках. Спецсимволы в пароле закодируйте в URL (`:` → `%3A`, `@` → `%40` и т.д.). При необходимости DNS через прокси для HTTPS попробуйте схему `socks5h://` вместо `socks5://`.

```bash
curl -sS -x 'socks5h://user:pass@host:1080' "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
```

## 1. Настройка `.env`

```bash
# Сгенерировать секреты
BOT_API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
WEBHOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

# Добавить в .env
echo "BOT_API_TOKEN=$BOT_API_TOKEN" >> .env
echo "WEBHOOK_SECRET=$WEBHOOK_SECRET" >> .env
echo "WEBHOOK_HOST=https://your-domain.ru" >> .env
```

## 2. Nginx: добавить location для webhook

В конфигурацию Nginx на хосте добавить:

```nginx
location /api/tg-wh/ {
    proxy_pass http://127.0.0.1:8443;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Перезагрузить Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 3. Применить миграцию

```bash
docker compose exec backend alembic upgrade head
```

Миграция 008 создаёт:
- `contacts.source` (varchar)
- `premise_type_aliases` (словарь синонимов + seed-данные)
- `bot_unrecognized` (лог нераспознанных вводов)

## 4. Собрать и запустить

```bash
docker compose up -d --build bot
```

Бот автоматически регистрирует webhook при старте (если `WEBHOOK_HOST` задан).

## 5. Проверить

```bash
# Логи бота
docker compose logs -f bot

# Проверить webhook через Telegram API
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

Ожидаемый ответ: `url` указывает на `https://your-domain.ru/api/tg-wh/<WEBHOOK_SECRET>`.

## 6. Проверить работу

1. Открыть бота в Telegram, нажать `/start`.
2. Нажать «Я собственник» → ввести номер помещения.
3. Проверить данные в админке (перезагрузить шахматку).

## Управление словарём синонимов

Суперадмин может добавлять/удалять синонимы через веб-интерфейс:
- Навигация → «Словарь бота»
- Просмотр нераспознанных вводов → «Нераспознанные вводы»
