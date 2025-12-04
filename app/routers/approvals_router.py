from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime, timedelta

from app.db import get_session
from app.models import Approval, User, UserRole
from app.deps import get_current_user, require_role

router = APIRouter(prefix="/approvals", tags=["approvals"])


# 研究员发起下载申请
@router.post("/request")
def request_approval(
    resource_type: str,
    resource_id: int,
    purpose: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 校验资源类型
    if resource_type not in {"dataset", "sample"}:
        raise HTTPException(status_code=400, detail="resource_type 必须是 dataset 或 sample")

    # 创建审批记录
    req = Approval(
        applicant_id=current.id,
        resource_type=resource_type,
        resource_id=resource_id,
        purpose=purpose,
        decision="pending",
        created_at=datetime.utcnow(),
    )

    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# 管理员/数据管理员审核
@router.post("/{approval_id}/review")
def review_approval(
    approval_id: int,
    decision: str,
    ttl_minutes: int | None = None,
    db: Session = Depends(get_session),
    current: User = Depends(require_role(UserRole.admin, UserRole.data_admin)),
):
    # 查询审批记录
    stmt = select(Approval).where(Approval.id == approval_id)
    approval = db.execute(stmt).scalars().first()
    if not approval:
        raise HTTPException(status_code=404, detail="审批请求不存在")

    # 已审核不能重复审核
    if approval.decision != "pending":
        raise HTTPException(status_code=400, detail="该请求已审核过")

    # 审核决策
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision 必须是 approved 或 rejected")

    approval.decision = decision
    approval.reviewed_by = current.id
    approval.reviewed_at = datetime.utcnow()

    # 若审核通过，设置下载链接有效期
    if decision == "approved" and ttl_minutes:
        approval.expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval
