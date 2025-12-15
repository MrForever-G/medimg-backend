from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from datetime import datetime, timedelta

from app.db import get_session
from app.models import Approval, User, UserRole, ResourceType, Decision, ApprovalOut
from app.deps import get_current_user, require_role
from app.audit import log_action

router = APIRouter(prefix="/approvals", tags=["approvals"])


# 研究员发起下载申请
@router.post("/request", response_model=ApprovalOut)
def request_approval(
    resource_type: ResourceType,
    resource_id: int,
    purpose: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    # 创建审批请求对象
    req = Approval(
        applicant_id=current.id,
        resource_type=resource_type,
        resource_id=resource_id,
        purpose=purpose,
        decision=Decision.pending,
        created_at=datetime.utcnow(),
    )

    db.add(req)
    db.commit()
    db.refresh(req)

    # 成功发起下载申请，记录日志
    log_action(
        db,
        current.id,
        "request_approval",
        request,
        resource_type=resource_type.value,  # Enum 转字符串用于日志
        resource_id=resource_id,
        result="ok",
    )

    return req


# 管理员/数据管理员审核
@router.post("/{approval_id}/review", response_model=ApprovalOut)
def review_approval(
    approval_id: int,
    decision: Decision,
    ttl_minutes: int | None = None,
    db: Session = Depends(get_session),
    current: User = Depends(require_role(UserRole.admin, UserRole.data_admin)),
    request: Request = None,
):
    # 查询审批记录
    stmt = select(Approval).where(Approval.id == approval_id)
    approval = db.execute(stmt).scalars().first()
    if not approval:
        # 审批记录不存在，记录日志
        log_action(db, current.id, "review_approval", request, result="deny", detail="not found")
        raise HTTPException(status_code=404, detail="审批请求不存在")

    # 已审核不能重复审核
    if approval.decision != Decision.pending:
        # 重复审核，记录日志
        log_action(db, current.id, "review_approval", request, result="deny", detail="already reviewed")
        raise HTTPException(status_code=400, detail="该请求已审核过")

    # 设置审核信息
    approval.decision = decision
    approval.reviewed_by = current.id
    approval.reviewed_at = datetime.utcnow()

    # 若审核通过，设置过期时间
    if decision == Decision.approved and ttl_minutes:
        approval.expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

    db.add(approval)
    db.commit()
    db.refresh(approval)

    # 审核成功，记录日志
    log_action(
        db,
        current.id,
        "review_approval",
        request,
        resource_type=approval.resource_type.value,
        resource_id=approval.id,
        result="ok",
    )

    return approval

# 列出所有审批请求
@router.get("/", response_model=list[ApprovalOut])
def list_approvals(
    db: Session = Depends(get_session),
    current: User = Depends(require_role(UserRole.admin, UserRole.data_admin)),
):
    stmt = select(Approval).order_by(Approval.created_at.desc())
    return db.execute(stmt).scalars().all()

# 当前用户查询自己某个资源的最新审批状态
@router.get("/my", response_model=ApprovalOut | None)
def get_my_approval(
    resource_type: ResourceType,
    resource_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    stmt = (
        select(Approval)
        .where(
            Approval.applicant_id == current.id,
            Approval.resource_type == resource_type,
            Approval.resource_id == resource_id,
        )
        .order_by(Approval.created_at.desc())
        .limit(1)
    )

    # 若从未申请过，返回 None
    approval = db.execute(stmt).scalars().first()
    return approval
