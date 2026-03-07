"""
Кворум-МКД — Backend.
Точка входа FastAPI. Запуск: uvicorn app.main:app --host 0.0.0.0 --port 8000
LOST-01, BE-02, ADM-01, ADM-04 (03-basic-admin). OPS-03: /health проверяет БД.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy import text

from app.db import get_db
from app.routers import admin_contacts, audit, auth, bot, import_register, policy, premises, quorum, submit, superadmin

# SR-OPS02-001: единый текст 503 без внутренних деталей
SERVICE_UNAVAILABLE_DETAIL = "Service temporarily unavailable"

app = FastAPI(
    title="Кворум-МКД",
    description="API для системы контактов МКД",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(policy.router)
app.include_router(superadmin.router)
app.include_router(import_register.router)
app.include_router(premises.router)
app.include_router(submit.router)
app.include_router(admin_contacts.router)
app.include_router(audit.router)
app.include_router(quorum.router)
app.include_router(bot.router)


@app.on_event("startup")
def startup():
    """BE-02: при наличии MASTER_KEY_PATH проверить ключ при старте (AF-1)."""
    if os.environ.get("MASTER_KEY_PATH"):
        from app.crypto import get_fernet
        get_fernet()


@app.get("/health")
def health():
    """Проверка доступности сервиса и БД (SR-BE01-003, SR-OPS03-003)."""
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"detail": SERVICE_UNAVAILABLE_DETAIL},
        )
    return {"status": "ok", "db": "connected"}


@app.get("/")
def root():
    """Корневой эндпоинт."""
    return {"service": "mkd-contacts-backend", "docs": "/docs"}
