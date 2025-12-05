from datetime import datetime
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session
from app.models import AuditLog


def get_client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def log_action(
    db: Session,
    actor_id: Optional[int],
    action: str,
    request: Optional[Request] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    result: Optional[str] = None,
    detail: Optional[str] = None,
):
    """写入审计日志"""
    ip = get_client_ip(request)
    actor_value = actor_id if actor_id is not None and actor_id > 0 else None

    log = AuditLog(
        actor_id=actor_value,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=ip,
        result=result,
        detail=detail,
        created_at=datetime.utcnow(),
    )

    db.add(log)
    db.commit()
