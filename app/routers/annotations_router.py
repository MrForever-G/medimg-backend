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
