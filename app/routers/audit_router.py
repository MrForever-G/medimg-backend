from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import AuditLog, AuditLogOut, UserRole
from app.deps import require_role

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("/", response_model=list[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_session),
    current=Depends(require_role(UserRole.admin, UserRole.data_admin)),
    request: Request = None,
):
    """
    查询系统审计日志（只读）

    仅管理员 / 数据管理员可访问，用于安全审计与行为追溯。
    """

    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )

    return logs
