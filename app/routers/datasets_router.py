from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Dataset, Visibility, User, UserRole
from app.deps import get_current_user

router = APIRouter(prefix="/datasets", tags=["datasets"])


# 创建数据集
@router.post("/", status_code=201)
def create_dataset(
    body: dict,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    name = body.get("name")
    if not name:
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
    return {"id": dataset.id, "name": dataset.name, "visibility": dataset.visibility}


# 列出数据集
@router.get("/")
def list_datasets(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    query = db.query(Dataset)

    # 研究员只能看到 group 或者自己创建的 private
    if current.role == UserRole.researcher:
        query = query.filter(
            (Dataset.visibility == Visibility.group)
            | (Dataset.created_by == current.id)
        )

    datasets = query.all()

    return [
        {
            "id": d.id,
            "name": d.name,
            "visibility": d.visibility,
            "created_by": d.created_by,
            "created_at": d.created_at,
        }
        for d in datasets
    ]


# 获取数据集详情
@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    d = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not d:
        raise HTTPException(404, "数据集不存在")

    # 研究员访问 private 必须是自己创建的
    if current.role == UserRole.researcher:
        if d.visibility == Visibility.private and d.created_by != current.id:
            raise HTTPException(403, "无权访问该数据集")

    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "version": d.version,
        "visibility": d.visibility,
        "created_by": d.created_by,
        "created_at": d.created_at,
    }
