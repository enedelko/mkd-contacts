#!/usr/bin/env bash
# Первичная установка логина и пароля для администратора (без JWT).
# Используется, когда у суперадмина ещё нет логина/пароля и войти по API нельзя.
# Выполняет UPDATE в БД через backend-контейнер (Python + app.auth_password).
#
# Использование:
#   ./scripts/set-admin-login-password-bootstrap.sh <telegram_id> <login> <password>
#   или: TARGET_TELEGRAM_ID=... NEW_LOGIN=... NEW_PASSWORD=... ./scripts/set-admin-login-password-bootstrap.sh
#
# Требуется: docker compose и запущенный контейнер backend. Пароль — не короче 8 символов.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -f "$APP_DIR/docker-compose.yml" ]]; then
  echo "Ошибка: в $APP_DIR не найден docker-compose.yml" >&2
  exit 1
fi

TARGET_TELEGRAM_ID="${TARGET_TELEGRAM_ID:-$1}"
NEW_LOGIN="${NEW_LOGIN:-$2}"
NEW_PASSWORD="${NEW_PASSWORD:-$3}"

if [[ -z "$TARGET_TELEGRAM_ID" || -z "$NEW_LOGIN" || -z "$NEW_PASSWORD" ]]; then
  echo "Использование: $0 <telegram_id> <login> <password>" >&2
  echo "  или переменные: TARGET_TELEGRAM_ID, NEW_LOGIN, NEW_PASSWORD" >&2
  exit 1
fi

if [[ ${#NEW_PASSWORD} -lt 8 ]]; then
  echo "Ошибка: пароль должен быть не короче 8 символов." >&2
  exit 1
fi

echo "Установка логина и пароля для telegram_id=$TARGET_TELEGRAM_ID (прямое обновление БД)..." >&2

# Передаём данные через env, чтобы не подставлять пароль в командную строку
export TARGET_TELEGRAM_ID NEW_LOGIN NEW_PASSWORD
PYERR=$(mktemp)
trap 'rm -f "$PYERR"' EXIT
if (cd "$APP_DIR" && docker compose exec -T -e TARGET_TELEGRAM_ID -e NEW_LOGIN -e NEW_PASSWORD backend python -c '
import os
from app.auth_password import hash_password
from app.db import get_db
from sqlalchemy import text
tid = os.environ["TARGET_TELEGRAM_ID"]
login = os.environ.get("NEW_LOGIN", "").strip().lower()
password = os.environ.get("NEW_PASSWORD", "")
if not login or not password:
    print("ERROR: empty login or password", flush=True)
    exit(1)
ph = hash_password(password)
with get_db() as db:
    r = db.execute(text("SELECT 1 FROM admins WHERE telegram_id = :tid"), {"tid": tid}).fetchone()
    if not r:
        print("ERROR: admin not found", flush=True)
        exit(1)
    db.execute(text("UPDATE admins SET login = :login, password_hash = :ph WHERE telegram_id = :tid"),
               {"login": login, "ph": ph, "tid": tid})
    db.commit()
print("OK", flush=True)
' 2> "$PYERR"); then
  echo "Готово: для админа telegram_id=$TARGET_TELEGRAM_ID установлены логин \"$NEW_LOGIN\" и пароль. Теперь можно входить по логину и паролю." >&2
  exit 0
fi

echo "Ошибка: администратор с таким telegram_id не найден в БД или ошибка выполнения." >&2
[[ -s "$PYERR" ]] && cat "$PYERR" >&2
exit 1
