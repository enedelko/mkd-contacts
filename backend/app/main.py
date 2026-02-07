"""
Кворум-МКД — Backend.
Точка входа FastAPI. Запуск: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
def health():
    """Проверка доступности сервиса (SR-BE01-003)."""
    return {"status": "ok"}


@app.get("/")
def root():
    """Корневой эндпоинт."""
    return {"service": "mkd-contacts-backend", "docs": "/docs"}
