"""
Единая логика определения IP клиента за прокси (nginx).
Для корректного audit_log и rate-limit nginx на хосте должен передавать
X-Real-IP и X-Forwarded-For (см. docs/deploy/nginx-host.example.conf).
Если заголовки не приходят, подставляется request.client.host (например 172.19.0.1),
чтобы в аудит всегда записывался источник (требование по отслеживанию ПДн — не NULL).
"""
from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """
    IP клиента для аудита и rate-limit. Всегда возвращает значение, когда есть
    соединение: приоритет X-Forwarded-For → X-Real-IP → request.client.host.
    NULL только если request.client отсутствует (теоретически).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real = request.headers.get("x-real-ip")
    if real and real.strip():
        return real.strip()
    if request.client and request.client.host:
        return request.client.host.strip()
    return None
