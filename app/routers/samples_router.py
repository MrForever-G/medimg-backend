import os
import hashlib
from typing import List
from datetime import timezone

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from app.db import get_session
from app.models import Sample, Dataset, SampleOut, Approval, ResourceType, Decision, Visibility
from app.deps import get_current_user
from app.config import settings
from app.audit import log_action
from app.utils.time import utc_now

router = APIRouter(prefix="/samples", tags=["samples"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def sha256_of_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def ensure_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("/upload/{dataset_id}", status_code=status.HTTP_201_CREATED, response_model=SampleOut)
async def upload_sample(
    dataset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    name = file.filename
    _, ext = os.path.splitext(name.lower())
    if ext not in ALLOWED_EXT:
        log_action(db, current.id, "upload_sample", request, result="deny", detail=f"invalid ext: {ext}")
        raise HTTPException(400, f"文件类型不允许: {ext}")

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        log_action(db, current.id, "upload_sample", request, result="deny", detail="dataset not found")
        raise HTTPException(404, "数据集不存在")

    content = await file.read()
    digest = sha256_of_bytes(content)

    exists = db.query(Sample).filter(Sample.sha256 == digest).first()
    if exists:
        log_action(db, current.id, "upload_sample", request, result="deny", detail="sha256 duplicate")
        raise HTTPException(409, "该文件已存在（SHA256重复）")

    save_dir = f"dataset_{dataset_id}"
    abs_dir = os.path.join(settings.STORAGE_ROOT, save_dir)
    os.makedirs(abs_dir, exist_ok=True)

    abs_path = os.path.join(abs_dir, name)
    with open(abs_path, "wb") as f:
        f.write(content)

    relative_path = f"{save_dir}/{name}"

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
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        log_action(db, current.id, "list_sample", request, result="deny", detail="dataset not found")
        raise HTTPException(404, "数据集不存在")

    records = (
        db.query(Sample)
        .filter(Sample.dataset_id == dataset_id)
        .order_by(Sample.id.desc())
        .all()
    )

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


@router.get("/{sample_id}/download")
def download_sample(
    sample_id: int,
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        log_action(db, current.id, "download_sample", request, result="deny", detail="sample not found")
        raise HTTPException(404, "样本不存在")

    approval = (
        db.query(Approval)
        .filter(
            Approval.applicant_id == current.id,
            Approval.resource_type == ResourceType.sample,
            Approval.resource_id == sample_id,
        )
        .order_by(Approval.id.desc())
        .first()
    )

    if not approval:
        log_action(db, current.id, "download_sample", request, result="deny", detail="no approval")
        raise HTTPException(403, "无下载权限（未申请审批）")

    if approval.decision != Decision.approved:
        log_action(db, current.id, "download_sample", request, result="deny", detail="not approved")
        raise HTTPException(403, "审批未通过")

    expires_at = ensure_utc(approval.expires_at)
    if expires_at and expires_at < utc_now():
        log_action(db, current.id, "download_sample", request, result="deny", detail="approval expired")
        raise HTTPException(403, "审批已过期")

    abs_path = os.path.join(settings.STORAGE_ROOT, sample.file_path)
    if not os.path.exists(abs_path):
        log_action(db, current.id, "download_sample", request, result="error", detail="file not found")
        raise HTTPException(500, "文件不存在")

    log_action(
        db,
        current.id,
        "download_sample",
        request,
        resource_type="sample",
        resource_id=sample_id,
        result="ok",
    )

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

    if sample.created_by != current.id and current.role not in ["admin", "data_admin"]:
        log_action(db, current.id, "delete_sample", request, result="deny")
        raise HTTPException(403, "无权删除该样本")

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


@router.get("/", response_model=list[SampleOut])
def list_all_samples(
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    query = db.query(Sample)

    if current.role not in ["admin", "data_admin"]:
        query = query.filter(Sample.created_by == current.id)

    records = query.order_by(Sample.id.desc()).all()

    log_action(
        db,
        current.id,
        "list_all_samples",
        request,
        resource_type="sample",
        result="ok",
    )

    return records


@router.get("/{sample_id}", response_model=SampleOut)
def get_sample_detail(
    sample_id: int,
    db: Session = Depends(get_session),
    current=Depends(get_current_user),
    request: Request = None,
):
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        log_action(db, current.id, "get_sample", request, result="deny", detail="sample not found")
        raise HTTPException(404, "样本不存在")

    dataset = db.query(Dataset).filter(Dataset.id == sample.dataset_id).first()
    if not dataset:
        log_action(db, current.id, "get_sample", request, result="deny", detail="dataset not found")
        raise HTTPException(404, "所属数据集不存在")

    if current.role not in ["admin", "data_admin"]:
        if sample.created_by != current.id and dataset.visibility == Visibility.private:
            log_action(db, current.id, "get_sample", request, result="deny", detail="no permission")
            raise HTTPException(403, "无权访问该样本")

    log_action(
        db,
        current.id,
        "get_sample",
        request,
        resource_type="sample",
        resource_id=sample_id,
        result="ok",
    )

    return sample
