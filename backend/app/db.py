"""
Сессия БД (sync). LOST-01 — использование таблиц admins, premises, contacts, oss_voting.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_admins_table() -> bool:
    """Проверить наличие таблицы admins (миграции применены)."""
    with get_db() as db:
        r = db.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = 'admins' LIMIT 1"))
        return r.scalar() is not None
