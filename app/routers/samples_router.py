import os
import hashlib
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Sample, Dataset, SampleOut
from app.deps import get_current_user
from app.config import settings
from app.audit import log_action


router = APIRouter(prefix="/samples", tags=["samples"])

# 允许上传的扩展名
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def sha256_of_bytes(data: bytes) -> str:
    # 计算SHA256
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


@router.post("/upload/{dataset_id}", status_code=status.HTTP_201_CREATED, response_model=SampleOut)
async def upload_sample(
    dataset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    # 校验扩展名
    name = file.filename
    _, ext = os.path.splitext(name.lower())
    if ext not in ALLOWED_EXT:
        # 文件扩展名不允许，记录日志
        log_action(db, current.id, "upload_sample", request, result="deny", detail=f"invalid ext: {ext}")
        raise HTTPException(400, f"文件类型不允许: {ext}")

    # 校验数据集存在
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        # 目标数据集不存在，记录日志
        log_action(db, current.id, "upload_sample", request, result="deny", detail="dataset not found")
        raise HTTPException(404, "数据集不存在")

    # 读取文件内容
    content = await file.read()
    digest = sha256_of_bytes(content)

    # 判断 SHA256 是否重复
    exists = db.query(Sample).filter(Sample.sha256 == digest).first()
    if exists:
        # SHA256 冲突，记录日志
        log_action(db, current.id, "upload_sample", request, result="deny", detail="sha256 duplicate")
        raise HTTPException(409, "该文件已存在（SHA256重复）")

    # 保存路径
    save_dir = os.path.join(settings.STORAGE_ROOT, f"dataset_{dataset_id}")
    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, name)
    with open(save_path, "wb") as f:
        f.write(content)

    # 写入数据库
    sample = Sample(
        dataset_id=dataset_id,
        file_path=save_path,
        sha256=digest,
        mime=file.content_type,
        created_by=current.id,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)

    # 成功上传样本，记录日志
    log_action(
        db,
        current.id,
        "upload_sample",
        request,
        resource_type="sample",
        resource_id=sample.id,
        result="ok",
    )

    return sample


@router.get("/by-dataset/{dataset_id}", response_model=list[SampleOut])
def list_by_dataset(
    dataset_id: int,
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    # 校验数据集存在
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        # 数据集不存在，记录日志
        log_action(db, current.id, "list_sample", request, result="deny", detail="dataset not found")
        raise HTTPException(404, "数据集不存在")

    records = (
        db.query(Sample)
        .filter(Sample.dataset_id == dataset_id)
        .order_by(Sample.id.desc())
        .all()
    )

    # 成功列出样本，记录日志
    log_action(
        db,
        current.id,
        "list_sample",
        request,
        resource_type="dataset",
        resource_id=dataset_id,
        result="ok",
    )

    return records
