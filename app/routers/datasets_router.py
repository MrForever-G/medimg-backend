from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Dataset, Visibility, User, UserRole, DatasetOut
from app.deps import get_current_user
from app.audit import log_action

router = APIRouter(prefix="/datasets", tags=["datasets"])


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
        # 数据集名称缺失，记录日志
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

    # 成功创建数据集，记录日志
    log_action(
        db,
        current.id,
        "create_dataset",
        request,
        resource_type="dataset",
        resource_id=dataset.id,
        result="ok",
    )

    # 返回 ORM 实体，由 Pydantic 自动序列化
    return dataset


# 列出数据集
@router.get("/", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    query = db.query(Dataset)

    # 研究员能看到 group 或自己创建的 private
    if current.role == UserRole.researcher:
        query = query.filter(
            (Dataset.visibility == Visibility.group)
            | (Dataset.created_by == current.id)
        )

    datasets = query.all()

    # 返回 ORM 列表
    return datasets


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
        # 数据集不存在，记录日志
        log_action(db, current.id, "get_dataset", request, result="deny", detail="not found")
        raise HTTPException(404, "数据集不存在")

    # 私有数据集权限校验
    if current.role == UserRole.researcher:
        if d.visibility == Visibility.private and d.created_by != current.id:
            # 无权限访问该数据集，记录日志
            log_action(db, current.id, "get_dataset", request, result="deny", detail="no permission")
            raise HTTPException(403, "无权访问该数据集")

    # 成功获取数据集详情，记录日志
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
