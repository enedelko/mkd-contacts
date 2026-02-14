#!/usr/bin/env bash
# Smoke-проверки: контейнеры (frontend, backend) и при возможности Nginx на хосте.
# Вызов: ./scripts/smoke-check.sh [APP_DIR]
# APP_DIR можно задать переменной окружения или аргументом.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-${1:-$REPO_ROOT}}"
APP_DIR="$(cd "$APP_DIR" && pwd)"

if [[ ! -f "$APP_DIR/docker-compose.yml" ]]; then
  echo "Ошибка: в $APP_DIR не найден docker-compose.yml" >&2
  exit 1
fi

CURL_TIMEOUT=10
FAILED=0

# Порты: из env (FRONTEND_PORT, BACKEND_PORT) или по умолчанию 8080/8000
# При override используйте: FRONTEND_PORT=8081 BACKEND_PORT=8082 ./scripts/smoke-check.sh
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
if [[ -f "$APP_DIR/docker-compose.override.yml" ]] && command -v docker >/dev/null 2>&1; then
  (cd "$APP_DIR" && docker compose port frontend 80 2>/dev/null) | grep -q ':' && \
    FRONTEND_PORT=$(cd "$APP_DIR" && docker compose port frontend 80 2>/dev/null | cut -d: -f2)
  (cd "$APP_DIR" && docker compose port backend 8000 2>/dev/null) | grep -q ':' && \
    BACKEND_PORT=$(cd "$APP_DIR" && docker compose port backend 8000 2>/dev/null | cut -d: -f2)
fi
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"

check_url() {
  local url="$1"
  local desc="$2"
  local expect="${3:-200}"
  local out
  out=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time "$CURL_TIMEOUT" "$url" 2>/dev/null || echo "000")
  if [[ "$out" == "$expect" ]]; then
    echo "  OK $desc ($url) -> $out"
    return 0
  else
    echo "  FAIL $desc ($url) -> $out (ожидалось $expect)" >&2
    return 1
  fi
}

check_health_body() {
  local url="$1"
  local desc="$2"
  local body
  body=$(curl -s --connect-timeout 5 --max-time "$CURL_TIMEOUT" "$url" 2>/dev/null || echo "")
  if [[ "$body" == *"status"* && "$body" == *"ok"* ]]; then
    echo "  OK $desc ($url)"
    return 0
  fi
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time "$CURL_TIMEOUT" "$url" 2>/dev/null || echo "000")
  echo "  FAIL $desc ($url) -> код $code или неверное тело" >&2
  return 1
}

check_front_body() {
  local url="$1"
  local desc="$2"
  local body
  body=$(curl -s --connect-timeout 5 --max-time "$CURL_TIMEOUT" "$url" 2>/dev/null || echo "")
  if [[ "$body" == *"Кворум"* || "$body" == *"html"* || "$body" == *"<!DOCTYPE"* ]]; then
    echo "  OK $desc ($url)"
    return 0
  fi
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time "$CURL_TIMEOUT" "$url" 2>/dev/null || echo "000")
  echo "  FAIL $desc ($url) -> код $code или неверное тело" >&2
  return 1
}

echo "Smoke: проверка контейнеров (frontend=$FRONTEND_PORT, backend=$BACKEND_PORT)..."
if ! check_front_body "${FRONTEND_URL}/" "frontend (контейнер)"; then
  FAILED=1
fi
if ! check_health_body "${BACKEND_URL}/health" "backend (контейнер)"; then
  FAILED=1
fi

echo "Smoke: проверка Nginx на хосте (порт 80)..."
if check_front_body "http://127.0.0.1:80/" "Nginx -> frontend"; then
  if ! check_health_body "http://127.0.0.1:80/api/health" "Nginx -> backend"; then
    echo "  Предупреждение: Nginx -> backend (/api/health) недоступен или путь не проксируется на backend /health" >&2
  fi
else
  echo "  Предупреждение: Nginx (порт 80) недоступен — проверьте хостовой Nginx" >&2
fi

if [[ $FAILED -eq 1 ]]; then
  echo "Smoke: есть неудачные проверки" >&2
  exit 1
fi
echo "Smoke: OK"
