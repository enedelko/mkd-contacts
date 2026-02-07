#!/bin/sh
# LOST-01: применение миграций при развёртывании (SR-LOST01-006)
set -e
cd /app
if [ -n "$DATABASE_URL" ]; then
  export DATABASE_URL
  alembic upgrade head
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
