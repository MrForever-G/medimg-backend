from enum import Enum
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import String, Text, Enum as SAEnum, Index, ForeignKey
from sqlalchemy.types import Integer
from pydantic import BaseModel, ConfigDict


# 枚举定义

class UserRole(str, Enum):
    admin = "admin"
    data_admin = "data_admin"
    researcher = "researcher"


class Visibility(str, Enum):
    group = "group"
    private = "private"


class AnnoType(str, Enum):
    bbox = "bbox"
    polygon = "polygon"
    brush = "brush"
    tag = "tag"


class AnnoStatus(str, Enum):
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class ResourceType(str, Enum):
    dataset = "dataset"
    sample = "sample"


class Decision(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AuditResult(str, Enum):
    ok = "ok"
    deny = "deny"
    error = "error"


# 用户表

class User(SQLModel, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    hashed_password: str = Field(sa_column=Column(String(255), nullable=False))
    role: UserRole = Field(sa_column=Column(SAEnum(UserRole), nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    datasets: list["Dataset"] = Relationship(back_populates="creator")
    samples: list["Sample"] = Relationship(back_populates="creator")
    annotations: list["Annotation"] = Relationship(back_populates="author")


# 数据集表

class Dataset(SQLModel, table=True):
    __tablename__ = "dataset"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(128), unique=True, nullable=False, index=True))
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    version: Optional[str] = Field(default=None, sa_column=Column(String(32)))
    visibility: Visibility = Field(sa_column=Column(SAEnum(Visibility), nullable=False))
    created_by: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    creator: "User" = Relationship(back_populates="datasets")

    # ORM 级联仅用于会话内一致性，实际删除行为由数据库外键 ON DELETE CASCADE 保证
    samples: list["Sample"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )


# 样本文件表

class Sample(SQLModel, table=True):
    __tablename__ = "sample"

    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键级联删除必须通过 sa_column 显式声明，避免 SQLModel foreign_key 与 sa_column 冲突
    dataset_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("dataset.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    filename: str = Field(sa_column=Column(String(255), nullable=False))
    file_path: str = Field(sa_column=Column(String(512), nullable=False))
    sha256: str = Field(sa_column=Column(String(64), nullable=False, unique=True, index=True))
    mime: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    created_by: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    dataset: "Dataset" = Relationship(back_populates="samples")
    creator: "User" = Relationship(back_populates="samples")
    annotations: list["Annotation"] = Relationship(back_populates="sample")


# 标注表

class Annotation(SQLModel, table=True):
    __tablename__ = "annotation"

    id: Optional[int] = Field(default=None, primary_key=True)
    sample_id: int = Field(foreign_key="sample.id", nullable=False, index=True)
    author_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    anno_type: AnnoType = Field(sa_column=Column(SAEnum(AnnoType), nullable=False))
    payload_json: str = Field(sa_column=Column(Text, nullable=False))
    status: AnnoStatus = Field(sa_column=Column(SAEnum(AnnoStatus), nullable=False))
    version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    sample: "Sample" = Relationship(back_populates="annotations")
    author: "User" = Relationship(back_populates="annotations")


# 下载授权表

class Approval(SQLModel, table=True):
    __tablename__ = "approval"

    id: Optional[int] = Field(default=None, primary_key=True)
    applicant_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    resource_type: ResourceType = Field(sa_column=Column(SAEnum(ResourceType), nullable=False))
    resource_id: int = Field(nullable=False, index=True)
    purpose: Optional[str] = Field(default=None, sa_column=Column(Text))
    decision: Decision = Field(sa_column=Column(SAEnum(Decision), nullable=False))
    expires_at: Optional[datetime] = None
    reviewed_by: Optional[int] = Field(default=None, foreign_key="user.id")
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


# 审计日志表

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    action: str = Field(sa_column=Column(String(64), nullable=False))
    resource_type: Optional[str] = Field(default=None, sa_column=Column(String(32)))
    resource_id: Optional[int] = Field(default=None, index=True)
    ip: Optional[str] = Field(default=None, sa_column=Column(String(45)))
    result: AuditResult = Field(sa_column=Column(SAEnum(AuditResult), nullable=False))
    detail: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


# 索引

Index("ix_sample_dataset_sha", Sample.dataset_id, Sample.sha256, unique=True)
Index("ix_approval_target", Approval.resource_type, Approval.resource_id)


# 输出模型（用于接口返回）

class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    version: str | None
    visibility: Visibility
    created_by: int
    created_at: datetime


class SampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    filename: str
    file_path: str
    sha256: str
    mime: str | None
    created_by: int
    created_at: datetime


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sample_id: int
    author_id: int
    anno_type: AnnoType
    payload_json: str
    status: AnnoStatus
    version: int
    created_at: datetime


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    applicant_id: int
    resource_type: ResourceType
    resource_id: int
    purpose: str | None
    decision: Decision
    expires_at: datetime | None
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    action: str
    resource_type: str | None
    resource_id: int | None
    ip: str | None
    result: AuditResult
    detail: str | None
    created_at: datetime
