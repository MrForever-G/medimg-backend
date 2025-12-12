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
    save_dir = f"dataset_{dataset_id}"                      # 相对目录，不含根路径
    abs_dir = os.path.join(settings.STORAGE_ROOT, save_dir)  # 绝对路径用于保存
    os.makedirs(abs_dir, exist_ok=True)

    abs_path = os.path.join(abs_dir, name)  # 真实文件保存路径
    with open(abs_path, "wb") as f:
        f.write(content)

    relative_path = f"{save_dir}/{name}"  # 相对路径写入数据库

    # 写入数据库（用相对路径）
    sample = Sample(
        dataset_id=dataset_id,
        filename=file.filename,  
        file_path=relative_path,
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

from fastapi.responses import FileResponse
from app.models import Approval, ResourceType, Decision
from sqlalchemy.orm import Session
from datetime import datetime

# 下载样本文件（需审批通过）
@router.get("/{sample_id}/download")
def download_sample(
    sample_id: int,
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    # 校验样本是否存在
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        # 数据不存在，记录日志
        log_action(db, current.id, "download_sample", request, result="deny", detail="sample not found")
        raise HTTPException(404, "样本不存在")

    # 查询审批记录
    approval = (
        db.query(Approval)
        .filter(
            Approval.applicant_id == current.id,
            Approval.resource_type == ResourceType.sample,
            Approval.resource_id == sample_id,
        )
        .order_by(Approval.id.desc())  # 取最新一条
        .first()
    )

    if not approval:
        log_action(db, current.id, "download_sample", request, result="deny", detail="no approval")
        raise HTTPException(403, "无下载权限（未申请审批）")

    # 审批状态检查
    if approval.decision != Decision.approved:
        log_action(db, current.id, "download_sample", request, result="deny", detail="not approved")
        raise HTTPException(403, "审批未通过")

    # 过期时间检查
    if approval.expires_at and approval.expires_at < datetime.utcnow():
        log_action(db, current.id, "download_sample", request, result="deny", detail="approval expired")
        raise HTTPException(403, "审批已过期")

    # 全部校验通过，允许下载
    abs_path = os.path.join(settings.STORAGE_ROOT, sample.file_path)
    if not os.path.exists(abs_path):
        # 文件缺失（一般不会出现）
        log_action(db, current.id, "download_sample", request, result="error", detail="file not found")
        raise HTTPException(500, "文件不存在")

    # 成功下载行为写入日志
    log_action(
        db,
        current.id,
        "download_sample",
        request,
        resource_type="sample",
        resource_id=sample_id,
        result="ok",
    )

    # 返回真实文件
    return FileResponse(
        abs_path,
        filename=os.path.basename(abs_path),
        media_type=sample.mime or "application/octet-stream"
    )

@router.delete("/{sample_id}", status_code=204)
def delete_sample(
    sample_id: int,
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(404, "样本不存在")

    # 权限判断
    if sample.created_by != current.id and current.role not in ["admin", "data_admin"]:
        log_action(db, current.id, "delete_sample", request, result="deny")
        raise HTTPException(403, "无权删除该样本")

    # 删除磁盘文件
    abs_path = os.path.join(settings.STORAGE_ROOT, sample.file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)

    db.delete(sample)
    db.commit()

    log_action(
        db,
        current.id,
        "delete_sample",
        request,
        resource_type="sample",
        resource_id=sample_id,
        result="ok",
    )
