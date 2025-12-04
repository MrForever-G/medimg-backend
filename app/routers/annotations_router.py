from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Annotation, Sample, User, AnnoType, AnnoStatus
from app.deps import get_current_user

router = APIRouter(prefix="/annotations", tags=["annotations"])


# 创建标注入参
class AnnotationCreate(BaseModel):
    anno_type: AnnoType
    payload_json: str


# 创建标注
@router.post("/{sample_id}")
def create_annotation(
    sample_id: int,
    body: AnnotationCreate,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 查询样本是否存在
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="样本不存在")

    # 计算下一版版本号
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

    return anno


# 按样本列出所有标注
@router.get("/by-sample/{sample_id}")
def list_by_sample(
    sample_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 查询样本是否存在
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="样本不存在")

    # 查询标注列表
    annos = db.query(Annotation).filter(Annotation.sample_id == sample_id).all()
    return annos
