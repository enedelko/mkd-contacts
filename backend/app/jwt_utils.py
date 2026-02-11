"""
ADM-01: Выдача и проверка JWT. Роль из белого списка (admins).
"""
from datetime import datetime, timezone, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import JWT_ALGORITHM, JWT_ACCESS_EXPIRE_SECONDS, JWT_SECRET

security = HTTPBearer(auto_error=False)


def create_access_token(telegram_id: str, role: str) -> str:
    """Выдать JWT с ролью (SR-ADM01-005)."""
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set")
    payload = {
        "sub": telegram_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=JWT_ACCESS_EXPIRE_SECONDS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Декодировать и проверить JWT. Иначе HTTPException 401."""
    if not JWT_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth not configured")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_super_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any]:
    """Зависимость: только super_administrator (ADM-04)."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if payload.get("role") != "super_administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-admin only")
    return payload


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any]:
    """Зависимость: administrator или super_administrator (CORE-01, SR-CORE01-001)."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    role = payload.get("role")
    if role not in ("administrator", "super_administrator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return payload
