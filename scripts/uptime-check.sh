#!/usr/bin/env bash
# OPS-03: проверка доступности приложения (GET /health). При двух подряд неуспехах — уведомление в Telegram.
# Вызов: из cron каждые 5–15 мин, например: */10 * * * * UPTIME_CHECK_URL=https://example.com/api/health TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... /path/to/scripts/uptime-check.sh
# Переменные: UPTIME_CHECK_URL (обязателен с хоста), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (для алерта), FAILURES_FILE (по умолчанию /tmp/mkd-uptime-failures).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-$REPO_ROOT}"
FAILURES_FILE="${FAILURES_FILE:-/tmp/mkd-uptime-failures}"
UPTIME_CHECK_URL="${UPTIME_CHECK_URL:-http://127.0.0.1/api/health}"
CURL_TIMEOUT=15

failures=0
if [[ -f "$FAILURES_FILE" ]]; then
  read -r failures < "$FAILURES_FILE" || true
fi
[[ ! "$failures" =~ ^[0-9]+$ ]] && failures=0

code="000"
body=""
if command -v curl >/dev/null 2>&1; then
  code=$(curl -s -o /tmp/mkd-uptime-health-body -w "%{http_code}" --connect-timeout 5 --max-time "$CURL_TIMEOUT" "$UPTIME_CHECK_URL" 2>/dev/null || echo "000")
  body=$(cat /tmp/mkd-uptime-health-body 2>/dev/null || echo "")
  rm -f /tmp/mkd-uptime-health-body
fi

if [[ "$code" == "200" ]] && [[ "$body" == *"status"* ]]; then
  echo "0" > "$FAILURES_FILE"
  exit 0
fi

# Неуспех: не 2xx или таймаут
failures=$((failures + 1))
echo "$failures" > "$FAILURES_FILE"

if [[ "$failures" -lt 2 ]]; then
  exit 0
fi

# Два подряд неуспеха — отправить уведомление (SR-OPS03-004)
if [[ -n "$TELEGRAM_BOT_TOKEN" && -n "$TELEGRAM_CHAT_ID" ]]; then
  msg="Сервис Кворум-МКД недоступен, время $(date -Iseconds 2>/dev/null || date)"
  msg_enc=$(printf '%s' "$msg" | sed "s/ /%20/g; s/:/%3A/g")
  url="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage?chat_id=${TELEGRAM_CHAT_ID}&text=${msg_enc}"
  curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$url" >/dev/null 2>&1 || true
fi

exit 0