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
