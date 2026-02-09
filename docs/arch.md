# Архитектура: МКД-Контакты (mkd-contacts)

Краткое описание стека и схемы развёртывания. Детали требований — [docs/srs/](srs/), развёртывание — [docs/deploy/01-bootstrap.md](deploy/01-bootstrap.md).

---

## 1. Технологический стек

* **Frontend:** React 18 (Vite), react-router-dom. Статический SPA: выбор помещения (каскадные фильтры), форма анкеты, загрузка реестра (админ).
* **Backend:** Python 3.x, FastAPI. Uvicorn/Gunicorn. Модули: авторизация (Telegram OAuth, JWT), импорт реестра, контакты, валидация статусов, аудит.
* **СУБД:** PostgreSQL 15+. Таблицы: admins, premises (кадастровый номер — PK), contacts (ПДн в зашифрованном виде, Blind Index), oss_voting, audit_log.
* **Инфраструктура:** Docker Compose (frontend, backend, db). Перед контейнерами — **Nginx на хост-машине** как единственная публичная точка входа (80/443). Порты контейнеров привязаны к localhost (127.0.0.1:8080 — frontend, 127.0.0.1:8000 — backend), доступны только хостовому Nginx.

---

## 2. Схема взаимодействия компонентов

1. **Client (React SPA):**
   * Маршруты: выбор помещения (/premises), форма анкеты (/form), загрузка файла (/upload), админ-разделы. Запросы к API — относительные пути (/api/...), проксируются хостовым Nginx на backend.
   * Авторизация: JWT после входа через Telegram OAuth; токен в заголовке `Authorization: Bearer`.
2. **Server (FastAPI):**
   * **Auth Module:** Telegram OAuth, проверка по белому списку (таблица admins), выдача JWT.
   * **Logic Module:** помещения (каскадные фильтры), приём анкеты (submit), импорт реестра (CORE-01), контакты и валидация статусов (VAL-01), админ-API (добавление контакта, смена статуса). Шифрование ПДн и Blind Index (BE-02).
   * **Auto-Doc:** Swagger UI (/docs) для тестирования эндпоинтов.
3. **Database (PostgreSQL):**
   * Хранение: админы, помещения (по кадастровому номеру), контакты (зашифрованные phone/email/telegram_id, how_to_address; индексы phone_idx, email_idx, telegram_id_idx), голосование_в_ОСС, audit_log. Реестр не содержит ФИО; связь импорт–контакты — по кадастровому номеру помещения.

---

## 3. Развёртывание (Docker и Nginx на хосте)

* **Хост:** Nginx слушает 80 (и при необходимости 443). Проксирует `/` → 127.0.0.1:8080 (контейнер frontend), `/api/` → 127.0.0.1:8000 (контейнер backend). Пример конфига: [docs/deploy/nginx-host.example.conf](deploy/nginx-host.example.conf).
* **Контейнеры:** `frontend` (Nginx + статика React, порт 80 → 127.0.0.1:8080), `backend` (Uvicorn, порт 8000 → 127.0.0.1:8000), `db` (PostgreSQL 15, порт 5432 только во внутренней сети). Размещение — только в РФ (152-ФЗ); секреты и мастер-ключ шифрования не в репозитории — см. [01-bootstrap.md](deploy/01-bootstrap.md).

Архитектура может уточняться в соответствии с SRS и бэклогом ([docs/srs/98-backlog.md](srs/98-backlog.md), [99-summary.md](srs/99-summary.md)).
