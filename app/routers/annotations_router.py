from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Annotation, Sample, User, AnnoType, AnnoStatus, AnnotationOut
from app.deps import get_current_user
from app.audit import log_action

router = APIRouter(prefix="/annotations", tags=["annotations"])


# 创建标注入参
class AnnotationCreate(BaseModel):
    anno_type: AnnoType
    payload_json: str


# 创建标注
@router.post("/{sample_id}", response_model=AnnotationOut)
def create_annotation(
    sample_id: int,
    body: AnnotationCreate,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    # 查询样本是否存在
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        # 样本不存在，记录日志
        log_action(db, current.id, "create_annotation", request, result="deny", detail="sample not found")
        raise HTTPException(status_code=404, detail="样本不存在")

    # 获取下一版本号
    last_version_row = (
        db.query(Annotation.version)
        .filter(Annotation.sample_id == sample_id)
        .order_by(Annotation.version.desc())
        .first()
    )
    last_version = last_version_row[0] if last_version_row else 0
    next_version = last_version + 1

    # 创建标注记录
    anno = Annotation(
        sample_id=sample_id,
        author_id=current.id,
        anno_type=body.anno_type,
        payload_json=body.payload_json,
        status=AnnoStatus.submitted,
        version=next_version,
        created_at=datetime.utcnow(),
    )

    db.add(anno)
    db.commit()
    db.refresh(anno)

    # 成功创建标注，记录日志
    log_action(
        db,
        current.id,
        "create_annotation",
        request,
        resource_type="annotation",
        resource_id=anno.id,
        result="ok",
    )

    # 返回 ORM，由 Pydantic 自动转换为 AnnotationOut
    return anno


# 按样本列出所有标注
@router.get("/by-sample/{sample_id}", response_model=list[AnnotationOut])
def list_by_sample(
    sample_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    # 查询样本是否存在
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        # 样本不存在，记录日志
        log_action(db, current.id, "list_annotation", request, result="deny", detail="sample not found")
        raise HTTPException(status_code=404, detail="样本不存在")

    # 查询标注列表
    annos = db.query(Annotation).filter(Annotation.sample_id == sample_id).all()

    # 成功查询标注列表，记录日志
    log_action(
        db,
        current.id,
        "list_annotation",
        request,
        resource_type="sample",
        resource_id=sample_id,
        result="ok",
    )

    # 返回 ORM 列表
    return annos

# 标注审批过程
@router.post("/{annotation_id}/approve", response_model=AnnotationOut)
def approve_annotation(
    annotation_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    # 仅管理员 / 数据管理员可审批
    if current.role not in ["admin", "data_admin"]:
        log_action(db, current.id, "approve_annotation", request, result="deny", detail="no permission")
        raise HTTPException(status_code=403, detail="无审批权限")

    anno = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not anno:
        log_action(db, current.id, "approve_annotation", request, result="deny", detail="not found")
        raise HTTPException(status_code=404, detail="标注不存在")

    # 仅允许对 submitted 状态进行审批
    if anno.status != AnnoStatus.submitted:
        log_action(
            db,
            current.id,
            "approve_annotation",
            request,
            resource_type="annotation",
            resource_id=annotation_id,
            result="deny",
            detail=f"invalid status: {anno.status}",
        )
        raise HTTPException(status_code=400, detail="当前标注状态不可审批")

    anno.status = AnnoStatus.approved
    anno.reviewed_at = datetime.utcnow()
    anno.reviewed_by = current.id

    db.commit()
    db.refresh(anno)

    log_action(
        db,
        current.id,
        "approve_annotation",
        request,
        resource_type="annotation",
        resource_id=annotation_id,
        result="ok",
    )

    return anno

@router.post("/{annotation_id}/reject", response_model=AnnotationOut)
def reject_annotation(
    annotation_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    if current.role not in ["admin", "data_admin"]:
        log_action(db, current.id, "reject_annotation", request, result="deny", detail="no permission")
        raise HTTPException(status_code=403, detail="无审批权限")

    anno = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not anno:
        log_action(db, current.id, "reject_annotation", request, result="deny", detail="not found")
        raise HTTPException(status_code=404, detail="标注不存在")

    if anno.status != AnnoStatus.submitted:
        log_action(
            db,
            current.id,
            "reject_annotation",
            request,
            resource_type="annotation",
            resource_id=annotation_id,
            result="deny",
            detail=f"invalid status: {anno.status}",
        )
        raise HTTPException(status_code=400, detail="当前标注状态不可驳回")

    anno.status = AnnoStatus.rejected
    anno.reviewed_at = datetime.utcnow()
    anno.reviewed_by = current.id

    db.commit()
    db.refresh(anno)

    log_action(
        db,
        current.id,
        "reject_annotation",
        request,
        resource_type="annotation",
        resource_id=annotation_id,
        result="ok",
    )

    return anno
