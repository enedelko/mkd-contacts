#!/usr/bin/env bash
# Установка логина и пароля для администратора (вызов от имени суперадмина по API).
# Для первой установки (когда у суперадмина ещё нет логина/пароля) используйте
#   scripts/set-admin-login-password-bootstrap.sh <telegram_id> <login> <password>
#
# Использование:
#   ./scripts/set-admin-login-password.sh <telegram_id> <login> [password]
#   или переменные окружения: TARGET_TELEGRAM_ID, NEW_LOGIN, NEW_PASSWORD,
#   SUPERADMIN_LOGIN, SUPERADMIN_PASSWORD, BASE_URL.
# Пароль можно не передавать в аргументах — будет запрошен с stdin (без эха).
# Пример: SUPERADMIN_LOGIN=super SUPERADMIN_PASSWORD=xxx ./scripts/set-admin-login-password.sh 123456789 admin1 'новый_пароль'

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v jq >/dev/null 2>&1; then
  echo "Ошибка: для работы скрипта нужен jq (установите: apt install jq / yum install jq)." >&2
  exit 1
fi

APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Использование: $0 [ -b BASE_URL ] [ -u SUPERADMIN_LOGIN ] [ -p SUPERADMIN_PASSWORD ] <telegram_id> <login> [password]" >&2
  echo "  -b BASE_URL              URL бэкенда (по умолчанию: из BACKEND_URL или http://127.0.0.1:8082)" >&2
  echo "  -u SUPERADMIN_LOGIN      Логин суперадмина (или env SUPERADMIN_LOGIN)" >&2
  echo "  -p SUPERADMIN_PASSWORD   Пароль суперадмина (или env SUPERADMIN_PASSWORD)" >&2
  echo "  telegram_id              Telegram ID админа, которому задаём логин/пароль" >&2
  echo "  login                    Новый логин для этого админа" >&2
  echo "  password                 Новый пароль (не короче 8 символов); если не указан — запрос с stdin" >&2
  echo "" >&2
  echo "Переменные окружения: BASE_URL, SUPERADMIN_LOGIN, SUPERADMIN_PASSWORD, TARGET_TELEGRAM_ID, NEW_LOGIN, NEW_PASSWORD" >&2
  exit 1
}

BASE_URL="${BASE_URL:-}"
SUPERADMIN_LOGIN="${SUPERADMIN_LOGIN:-}"
SUPERADMIN_PASSWORD="${SUPERADMIN_PASSWORD:-}"
TARGET_TELEGRAM_ID="${TARGET_TELEGRAM_ID:-}"
NEW_LOGIN="${NEW_LOGIN:-}"
NEW_PASSWORD="${NEW_PASSWORD:-}"

while getopts "b:u:p:h" opt; do
  case "$opt" in
    b) BASE_URL="$OPTARG" ;;
    u) SUPERADMIN_LOGIN="$OPTARG" ;;
    p) SUPERADMIN_PASSWORD="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))

if [[ -n "$1" ]]; then TARGET_TELEGRAM_ID="$1"; fi
if [[ -n "$2" ]]; then NEW_LOGIN="$2"; fi
if [[ -n "$3" ]]; then NEW_PASSWORD="$3"; fi

if [[ -z "$BASE_URL" ]]; then
  if [[ -n "$BACKEND_URL" ]]; then
    BASE_URL="$BACKEND_URL"
  elif [[ -f "$APP_DIR/docker-compose.override.yml" ]] && command -v docker >/dev/null 2>&1; then
    BACKEND_PORT=$(cd "$APP_DIR" && docker compose port backend 8000 2>/dev/null | cut -d: -f2)
    [[ -n "$BACKEND_PORT" ]] && BASE_URL="http://127.0.0.1:${BACKEND_PORT}"
  fi
  BASE_URL="${BASE_URL:-http://127.0.0.1:8082}"
fi
# убрать trailing slash
BASE_URL="${BASE_URL%/}"

if [[ -z "$TARGET_TELEGRAM_ID" || -z "$NEW_LOGIN" ]]; then
  echo "Ошибка: укажите telegram_id и login (аргументами или TARGET_TELEGRAM_ID, NEW_LOGIN)." >&2
  usage
fi

if [[ -z "$SUPERADMIN_LOGIN" ]]; then
  echo -n "Логин суперадмина: " >&2
  read -r SUPERADMIN_LOGIN
fi
if [[ -z "$SUPERADMIN_PASSWORD" ]]; then
  echo -n "Пароль суперадмина: " >&2
  read -rs SUPERADMIN_PASSWORD
  echo "" >&2
fi
if [[ -z "$NEW_PASSWORD" ]]; then
  echo -n "Новый пароль для админа (не короче 8 символов): " >&2
  read -rs NEW_PASSWORD
  echo "" >&2
fi

if [[ ${#NEW_PASSWORD} -lt 8 ]]; then
  echo "Ошибка: новый пароль должен быть не короче 8 символов." >&2
  exit 1
fi

CURL_TIMEOUT=15
echo "Получение JWT (логин суперадмина)..." >&2
LOGIN_RESP=$(curl -s -w "\n%{http_code}" --connect-timeout 5 --max-time "$CURL_TIMEOUT" \
  -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"login\":$(echo "$SUPERADMIN_LOGIN" | jq -Rs .),\"password\":$(echo "$SUPERADMIN_PASSWORD" | jq -Rs .)}" 2>/dev/null) || true
HTTP_CODE=$(echo "$LOGIN_RESP" | tail -n1)
BODY=$(echo "$LOGIN_RESP" | sed '$d')

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Ошибка входа суперадмина (HTTP $HTTP_CODE). Проверьте логин и пароль." >&2
  echo "$BODY" | jq -r '.detail // .' 2>/dev/null || echo "$BODY" >&2
  exit 1
fi

TOKEN=$(echo "$BODY" | jq -r '.access_token // empty')
if [[ -z "$TOKEN" ]]; then
  echo "Ошибка: в ответе нет access_token." >&2
  exit 1
fi

echo "Установка логина и пароля для telegram_id=$TARGET_TELEGRAM_ID..." >&2
PATCH_RESP=$(curl -s -w "\n%{http_code}" --connect-timeout 5 --max-time "$CURL_TIMEOUT" \
  -X PATCH "${BASE_URL}/api/superadmin/admins/${TARGET_TELEGRAM_ID}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"login\":$(echo "$NEW_LOGIN" | jq -Rs .),\"password\":$(echo "$NEW_PASSWORD" | jq -Rs .)}" 2>/dev/null) || true
PATCH_CODE=$(echo "$PATCH_RESP" | tail -n1)
PATCH_BODY=$(echo "$PATCH_RESP" | sed '$d')

if [[ "$PATCH_CODE" == "200" ]]; then
  echo "Готово: для админа telegram_id=$TARGET_TELEGRAM_ID установлены логин \"$NEW_LOGIN\" и пароль." >&2
  exit 0
fi

echo "Ошибка PATCH (HTTP $PATCH_CODE):" >&2
echo "$PATCH_BODY" | jq -r '.detail // .' 2>/dev/null || echo "$PATCH_BODY" >&2
exit 1
