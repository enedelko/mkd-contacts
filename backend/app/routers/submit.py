"""
FE-04: POST /api/submit — приём анкеты (форма сбора данных).
CORE-02: валидация, лимит 10 pending на помещение, дедупликация. Капча Turnstile.
"""
import logging
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from app.config import SUBMIT_RATE_LIMIT_PER_HOUR
from app.rate_limit import check_submit_rate_limit
from app.captcha import verify_turnstile
from app.submit_service import submit_questionnaire

logger = logging.getLogger(__name__)

router = APIRouter(tags=["submit"])


class SubmitBody(BaseModel):
    premise_id: str = Field(..., description="Кадастровый номер помещения (cadastral_number)")
    is_owner: bool = Field(..., description="Я собственник")
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    barrier_vote: str | None = Field(None, description="for | against | undecided")
    vote_format: str | None = Field(None, description="electronic | paper | undecided")
    registered_ed: str | None = Field(None, description="yes | no")
    consent_version: str | None = None
    captcha_token: str | None = Field(None, alias="captcha_token")


@router.post("/api/submit")
def submit(
    body: SubmitBody,
    request: Request,
) -> dict[str, Any]:
    """
    FE-04: Принять анкету. Обязательно хотя бы одно из: phone, email, telegram_id.
    Капча проверяется, если задан TURNSTILE_SECRET_KEY.
    """
    client_ip = request.client.host if request.client else None
    allowed, retry_after = check_submit_rate_limit(client_ip or "", SUBMIT_RATE_LIMIT_PER_HOUR)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry_after)})
    captcha_ok = verify_turnstile(body.captcha_token, client_ip)
    result = submit_questionnaire(
        premise_id=body.premise_id,
        is_owner=body.is_owner,
        phone=body.phone,
        email=body.email,
        telegram_id=body.telegram_id,
        barrier_vote=body.barrier_vote,
        vote_format=body.vote_format,
        registered_ed=body.registered_ed,
        consent_version=body.consent_version,
        client_ip=client_ip,
        captcha_verified=captcha_ok,
    )
    if result.get("success"):
        return {"success": True, "message": result.get("message", "Данные приняты")}
    if result.get("code") == "CONTACT_CONFLICT":
        raise HTTPException(status_code=409, detail=result["detail"])
    if result.get("code") == "PREMISE_LIMIT_EXCEEDED":
        raise HTTPException(status_code=400, detail=result["detail"])
    if result.get("code") == "PREMISE_NOT_FOUND":
        raise HTTPException(status_code=404, detail=result["detail"])
    if result.get("errors"):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"detail": result.get("detail", "Validation failed"), "errors": result["errors"]},
        )
    raise HTTPException(status_code=400, detail=result.get("detail", "Error"))
