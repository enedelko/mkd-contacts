#!/usr/bin/env bash
# Восстановление из бэкапа: БД из .sql, при наличии — образы из .images.tar, затем up и smoke-check.
# Запуск: ./scripts/restore-backup.sh ПУТЬ_К_БЭКАПУ [--no-images] [-y]
# ПУТЬ_К_БЭКАПУ — путь к .sql или к базовому имени (например backups/backup_20250101_120000).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-$REPO_ROOT}"
APP_DIR="$(cd "$APP_DIR" && pwd)"

if [[ ! -f "$APP_DIR/docker-compose.yml" || ! -f "$APP_DIR/.env" ]]; then
  echo "Ошибка: в $APP_DIR должны быть docker-compose.yml и .env" >&2
  exit 1
fi

# Первый аргумент — путь к бэкапу (.sql или базовое имя)
BACKUP_ARG="${1:?Укажите путь к файлу бэкапа (.sql) или базовое имя (например backups/backup_20250101_120000)}"
shift || true
CONFIRM=true
LOAD_IMAGES=true
for arg in "$@"; do
  if [[ "$arg" == -y ]]; then CONFIRM=false; fi
  if [[ "$arg" == --no-images ]]; then LOAD_IMAGES=false; fi
done

cd "$APP_DIR"

# Определить путь к .sql
if [[ -f "$BACKUP_ARG" ]]; then
  SQL_FILE="$BACKUP_ARG"
else
  if [[ "$BACKUP_ARG" == *.sql ]]; then
    SQL_FILE="$BACKUP_ARG"
  else
    SQL_FILE="${BACKUP_ARG}.sql"
  fi
  if [[ ! -f "$SQL_FILE" ]]; then
    # попробовать относительно APP_DIR
    SQL_FILE="$APP_DIR/$SQL_FILE"
  fi
  if [[ ! -f "$SQL_FILE" ]]; then
    echo "Ошибка: файл не найден: $SQL_FILE" >&2
    exit 1
  fi
fi
SQL_FILE="$(cd "$(dirname "$SQL_FILE")" && pwd)/$(basename "$SQL_FILE")"
BACKUP_BASE="${SQL_FILE%.sql}"
IMAGES_TAR="${BACKUP_BASE}.images.tar"

# POSTGRES_USER, POSTGRES_DB из .env
POSTGRES_USER="${POSTGRES_USER:-mkd}"
POSTGRES_DB="${POSTGRES_DB:-mkd_contacts}"
if [[ -f .env ]]; then
  while IFS= read -r line; do
    if [[ "$line" =~ ^POSTGRES_USER= ]]; then
      POSTGRES_USER="${line#POSTGRES_USER=}"
      POSTGRES_USER="${POSTGRES_USER%%[[:space:]]#*}"
    elif [[ "$line" =~ ^POSTGRES_DB= ]]; then
      POSTGRES_DB="${line#POSTGRES_DB=}"
      POSTGRES_DB="${POSTGRES_DB%%[[:space:]]#*}"
    fi
  done < .env
fi

if [[ "$CONFIRM" == true ]]; then
  echo "Внимание: текущие данные БД будут заменены данными из $SQL_FILE"
  read -r -p "Продолжить? [y/N] " ans
  if [[ "${ans,,}" != y && "${ans,,}" != yes ]]; then
    echo "Отменено."
    exit 0
  fi
fi

echo "Остановка backend и frontend..."
docker compose stop backend frontend 2>/dev/null || true

echo "Восстановление БД из $SQL_FILE..."
docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB" < "$SQL_FILE"

if [[ "$LOAD_IMAGES" == true && -f "$IMAGES_TAR" ]]; then
  echo "Загрузка образов из $IMAGES_TAR..."
  docker load -i "$IMAGES_TAR"
elif [[ -f "$IMAGES_TAR" ]]; then
  echo "Пропуск загрузки образов (--no-images)."
fi

echo "Запуск контейнеров..."
docker compose up -d

echo "Ожидание готовности (10 с)..."
sleep 10

echo "Smoke-проверки..."
"$SCRIPT_DIR/smoke-check.sh" "$APP_DIR" || { echo "Smoke проверки не пройдены" >&2; exit 1; }

echo ""
docker compose ps
echo "Восстановление завершено."
