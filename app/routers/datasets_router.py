from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.config import settings

from app.utils.time import utc_now
from app.db import get_session
from app.models import Dataset, Visibility, User, UserRole, DatasetOut
from app.deps import get_current_user
from app.audit import log_action

from datetime import timezone
import os
import shutil
import tempfile
from fastapi.responses import FileResponse
from app.models import Approval, ResourceType, Decision

router = APIRouter(prefix="/datasets", tags=["datasets"])


def ensure_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# 创建数据集
@router.post("/", status_code=201, response_model=DatasetOut)
def create_dataset(
    body: dict,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    name = body.get("name")
    if not name:
        log_action(db, current.id, "create_dataset", request, result="deny", detail="missing name")
        raise HTTPException(400, "缺少数据集名称")

    dataset = Dataset(
        name=name,
        description=body.get("description"),
        version=body.get("version"),
        visibility=body.get("visibility", Visibility.group),
        created_by=current.id,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    log_action(
        db,
        current.id,
        "create_dataset",
        request,
        resource_type="dataset",
        resource_id=dataset.id,
        result="ok",
    )

    return dataset


# 列出数据集
@router.get("/", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    query = db.query(Dataset)

    if current.role == UserRole.researcher:
        query = query.filter(
            (Dataset.visibility == Visibility.group)
            | (Dataset.created_by == current.id)
        )

    return query.all()


# 获取数据集详情
@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    d = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not d:
        log_action(db, current.id, "get_dataset", request, result="deny", detail="not found")
        raise HTTPException(404, "数据集不存在")

    if current.role == UserRole.researcher:
        if d.visibility == Visibility.private and d.created_by != current.id:
            log_action(db, current.id, "get_dataset", request, result="deny", detail="no permission")
            raise HTTPException(403, "无权访问该数据集")

    log_action(
        db,
        current.id,
        "get_dataset",
        request,
        resource_type="dataset",
        resource_id=d.id,
        result="ok",
    )

    return d


# 下载整个数据集（需审批通过）
@router.get("/{dataset_id}/download")
def download_dataset(
    dataset_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        log_action(db, current.id, "download_dataset", request, result="deny", detail="dataset not found")
        raise HTTPException(404, "数据集不存在")

    approval = (
        db.query(Approval)
        .filter(
            Approval.applicant_id == current.id,
            Approval.resource_type == ResourceType.dataset,
            Approval.resource_id == dataset_id,
        )
        .order_by(Approval.id.desc())
        .first()
    )

    if not approval:
        log_action(db, current.id, "download_dataset", request, result="deny", detail="no approval")
        raise HTTPException(403, "无下载权限（未申请审批）")

    if approval.decision != Decision.approved:
        log_action(db, current.id, "download_dataset", request, result="deny", detail="not approved")
        raise HTTPException(403, "审批未通过")

    expires_at = ensure_utc(approval.expires_at)
    if expires_at and expires_at < utc_now():
        log_action(db, current.id, "download_dataset", request, result="deny", detail="approval expired")
        raise HTTPException(403, "审批已过期")

    folder = os.path.join(settings.STORAGE_ROOT, f"dataset_{dataset_id}")
    if not os.path.exists(folder):
        log_action(db, current.id, "download_dataset", request, result="error", detail="folder missing")
        raise HTTPException(500, "数据集目录不存在")

    tmp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(tmp_dir, f"dataset_{dataset_id}.zip")

    shutil.make_archive(
        base_name=zip_path.replace(".zip", ""),
        format="zip",
        root_dir=folder
    )

    log_action(
        db,
        current.id,
        "download_dataset",
        request,
        resource_type="dataset",
        resource_id=dataset_id,
        result="ok",
    )

    return FileResponse(
        zip_path,
        filename=f"dataset_{dataset_id}.zip",
        media_type="application/zip",
    )


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
    request: Request = None,
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(404, "数据集不存在")

    if dataset.created_by != current.id and current.role not in ["admin", "data_admin"]:
        log_action(db, current.id, "delete_dataset", request, result="deny")
        raise HTTPException(403, "无权删除该数据集")

    dataset_dir = os.path.join(settings.STORAGE_ROOT, f"dataset_{dataset_id}")
    if os.path.exists(dataset_dir):
        shutil.rmtree(dataset_dir)

    db.delete(dataset)
    db.commit()

    log_action(
        db,
        current.id,
        "delete_dataset",
        request,
        resource_type="dataset",
        resource_id=dataset_id,
        result="ok",
    )
