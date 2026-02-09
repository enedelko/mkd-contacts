# BE-01: Backend — Python/FastAPI под Uvicorn (SR-BE01-003)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

# Секрет мастер-ключа (BE-02) НЕ копируется в образ — подаётся через
# Docker Secrets или bind mount при запуске. См. docs/deploy/01-bootstrap.md
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
