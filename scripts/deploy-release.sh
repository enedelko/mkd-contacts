#!/usr/bin/env bash
# Деплой релиза: по умолчанию бэкап (БД + манифест), затем git checkout, build, up, smoke-check.
# Запуск из любой директории: APP_DIR=/path/to/repo ./scripts/deploy-release.sh [ТЕГ|main] [--no-backup]
# По умолчанию: ветка main, с бэкапом.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Корень приложения: APP_DIR, или первый аргумент если это каталог, иначе родитель scripts/
if [[ -n "$APP_DIR" && -d "$APP_DIR" ]]; then
  APP_DIR="$(cd "$APP_DIR" && pwd)"
elif [[ -n "$1" && "$1" != main && "$1" != --no-backup && -d "$1" ]]; then
  APP_DIR="$(cd "$1" && pwd)"
  shift
else
  APP_DIR="$REPO_ROOT"
fi

cd "$APP_DIR"
if [[ ! -f docker-compose.yml || ! -f .env ]]; then
  echo "Ошибка: в $APP_DIR должны быть docker-compose.yml и .env" >&2
  exit 1
fi

# Парсинг аргументов: ТЕГ_ИЛИ_ВЕТКА и --no-backup
TARGET=main
DO_BACKUP=true
for arg in "$@"; do
  if [[ "$arg" == --no-backup ]]; then DO_BACKUP=false; fi
done
for arg in "$@"; do
  if [[ "$arg" != --no-backup && -n "$arg" ]]; then TARGET="$arg"; break; fi
done

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

echo "Деплой: цель=$TARGET, бэкап=$DO_BACKUP, APP_DIR=$APP_DIR"

if [[ "$DO_BACKUP" == true ]]; then
  mkdir -p backups
  STAMP="$(date +%Y%m%d_%H%M%S)"
  BACKUP_BASE="backups/backup_$STAMP"
  echo "Бэкап: БД и манифест -> $BACKUP_BASE.*"
  docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "${BACKUP_BASE}.sql"
  {
    echo "date=$STAMP"
    echo "git_rev=$(git rev-parse HEAD 2>/dev/null || echo '?')"
    echo "git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    git describe --tags --exact-match 2>/dev/null && echo "git_tag=$(git describe --tags --exact-match)" || true
  } > "${BACKUP_BASE}.manifest.txt"
  echo "Бэкап сохранён: ${BACKUP_BASE}.sql, ${BACKUP_BASE}.manifest.txt"
fi

echo "Обновление кода: fetch и checkout $TARGET..."
git fetch origin
if git rev-parse "refs/tags/$TARGET" >/dev/null 2>&1; then
  git checkout "tags/$TARGET"
else
  git checkout "$TARGET"
  git pull origin "$TARGET" 2>/dev/null || true
fi

echo "Сборка образов..."
docker compose build --no-cache

echo "Запуск контейнеров..."
docker compose up -d

echo "Ожидание готовности сервисов (10 с)..."
sleep 10

echo "Smoke-проверки..."
"$SCRIPT_DIR/smoke-check.sh" "$APP_DIR" || { echo "Smoke проверки не пройдены" >&2; exit 1; }

echo ""
docker compose ps
echo ""
echo "Деплой завершён. Проверьте приложение в браузере."
