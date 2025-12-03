# app/routers/samples_router.py

import os
import hashlib
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Sample, Dataset
from app.deps import get_current_user
from app.config import settings


router = APIRouter(prefix="/samples", tags=["samples"])

# 允许上传的扩展名
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def sha256_of_bytes(data: bytes) -> str:
    # 计算SHA256
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


@router.post("/upload/{dataset_id}", status_code=status.HTTP_201_CREATED)
async def upload_sample(
    dataset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
):
    # 校验扩展名
    name = file.filename
    _, ext = os.path.splitext(name.lower())
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"文件类型不允许: {ext}")

    # 校验数据集存在
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(404, "数据集不存在")

    # 读取文件内容
    content = await file.read()
    digest = sha256_of_bytes(content)

    # 检查是否已有相同 SHA256
    exists = db.query(Sample).filter(Sample.sha256 == digest).first()
    if exists:
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

    return {
        "id": sample.id,
        "sha256": sample.sha256,
        "path": sample.file_path,
    }


@router.get("/by-dataset/{dataset_id}")
def list_by_dataset(
    dataset_id: int,
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
):
    # 校验数据集存在
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(404, "数据集不存在")

    # 列出文件
    records = (
        db.query(Sample)
        .filter(Sample.dataset_id == dataset_id)
        .order_by(Sample.id.desc())
        .all()
    )

    return records
