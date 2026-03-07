# 08 — Uptime-check и уведомление админов (OPS-03)

Периодическая проверка доступности приложения (GET /health) и отправка уведомления в Telegram при двух подряд неуспешных проверках. Спецификация — [16-ops02-ops03-graceful-uptime.md](../srs/16-ops02-ops03-graceful-uptime.md).

## 1. Эндпоинт /health

Backend отдаёт `GET /health`: при доступности БД — **200** и `{"status": "ok", "db": "connected"}`; при недоступности БД — **503** и `{"detail": "Service temporarily unavailable"}`.

---

## 2. Сервисный контейнер (рекомендуется)

В `docker-compose.yml` добавлен сервис **uptime-check**: лёгкий контейнер (Alpine + curl), который в цикле вызывает скрипт `scripts/uptime-check.sh` с заданным интервалом.

**Переменные окружения (в `.env` или в `environment`):**

| Переменная | Описание |
|------------|----------|
| **UPTIME_CHECK_URL** | URL для проверки. По умолчанию `http://backend:8000/health` (внутри сети compose). Для проверки «снаружи» (через Nginx) задайте, например, `https://your-domain.example/api/health`. |
| **UPTIME_CHECK_INTERVAL_SEC** | Интервал между проверками в секундах (по умолчанию 600, т.е. 10 мин). |
| **TELEGRAM_BOT_TOKEN** | Токен бота для отправки алертов (можно тот же, что для входа/бота, или отдельный). |
| **UPTIME_TELEGRAM_CHAT_ID** | ID чата или группы для алертов (число или строка). |

Если `TELEGRAM_BOT_TOKEN` или `UPTIME_TELEGRAM_CHAT_ID` не заданы, контейнер только ведёт счётчик неудач и не отправляет сообщения в Telegram.

**Запуск:**

```bash
docker compose up -d uptime-check
```

Контейнер поднимается вместе с остальными при `docker compose up -d`. Логи: `docker compose logs -f uptime-check`.

**Сборка образа:** при первом запуске или после изменения `scripts/uptime-check.sh` или `uptime-check/Dockerfile` выполните `docker compose build uptime-check`.

---

## 3. Скрипт и логика

Скрипт `scripts/uptime-check.sh` вызывается из контейнера (или вручную / из cron). Логика:

- При ответе **200** и наличии `"status"` в теле — счётчик подряд неудач сбрасывается.
- При не-2xx или таймауте счётчик увеличивается; при **двух подряд** неуспехах отправляется сообщение в Telegram: «Сервис Кворум-МКД недоступен, время &lt;ISO8601&gt;». Дальнейшие неуспехи не приводят к повторной отправке до следующего успешного ответа.

Дополнительная переменная **FAILURES_FILE** (по умолчанию `/tmp/mkd-uptime-failures`) задаёт файл счётчика; в контейнере его можно не менять.

---

## 4. Вариант через cron (на хосте)

Если не использовать контейнер, можно запускать скрипт по cron на хосте. Пример:

```bash
# crontab -e; каждые 10 минут
*/10 * * * * UPTIME_CHECK_URL=https://your-domain.example/api/health TELEGRAM_BOT_TOKEN=... UPTIME_TELEGRAM_CHAT_ID=... /path/to/mkd-contacts/scripts/uptime-check.sh
```

Секреты можно вынести в файл (например `/etc/mkd-contacts/uptime.env` с правами 600) и подключать в cron через `source`.

---

## 5. Проверка

**С контейнером:** после `docker compose up -d` остановите backend: `docker compose stop backend`. Подождите два интервала (по умолчанию 20 мин) или уменьшите `UPTIME_CHECK_INTERVAL_SEC` до 30 и подождите ~1 мин — при заданных токене и chat_id должно прийти уведомление в Telegram.

**Вручную (скрипт):**

```bash
UPTIME_CHECK_URL=http://127.0.0.1:8000/health ./scripts/uptime-check.sh
```

Два раза подряд при остановленном backend — во второй раз отправится уведомление (если заданы токен и chat_id).
