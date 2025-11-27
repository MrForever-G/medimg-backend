from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import String, Text, Enum as SAEnum, Index


# 让 db.init_db() 可引用到统一的 Base（SQLModel 自身即可）
Base = SQLModel


# ---- 枚举定义 ----
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


# ---- 表定义 ----
class User(SQLModel, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    hashed_password: str = Field(sa_column=Column(String(255), nullable=False))
    role: UserRole = Field(sa_column=Column(SAEnum(UserRole), nullable=False, default=UserRole.researcher))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    datasets: list["Dataset"] = Relationship(back_populates="creator")
    samples: list["Sample"] = Relationship(back_populates="creator")
    annotations: list["Annotation"] = Relationship(back_populates="author")


class Dataset(SQLModel, table=True):
    __tablename__ = "dataset"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(128), unique=True, nullable=False, index=True))
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    version: Optional[str] = Field(default=None, sa_column=Column(String(32)))
    visibility: Visibility = Field(sa_column=Column(SAEnum(Visibility), nullable=False, default=Visibility.group))
    created_by: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    creator: Optional[User] = Relationship(back_populates="datasets")
    samples: list["Sample"] = Relationship(back_populates="dataset")


class Sample(SQLModel, table=True):
    __tablename__ = "sample"

    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="dataset.id", nullable=False, index=True)
    file_path: str = Field(sa_column=Column(String(512), nullable=False))
    sha256: str = Field(sa_column=Column(String(64), nullable=False, unique=True, index=True))
    mime: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    created_by: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    dataset: Optional[Dataset] = Relationship(back_populates="samples")
    creator: Optional[User] = Relationship(back_populates="samples")
    annotations: list["Annotation"] = Relationship(back_populates="sample")


class Annotation(SQLModel, table=True):
    __tablename__ = "annotation"

    id: Optional[int] = Field(default=None, primary_key=True)
    sample_id: int = Field(foreign_key="sample.id", nullable=False, index=True)
    author_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    anno_type: AnnoType = Field(sa_column=Column(SAEnum(AnnoType), nullable=False))
    payload_json: str = Field(sa_column=Column(Text, nullable=False))  # 前端 JSON 串
    status: AnnoStatus = Field(sa_column=Column(SAEnum(AnnoStatus), nullable=False, default=AnnoStatus.submitted))
    version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    sample: Optional[Sample] = Relationship(back_populates="annotations")
    author: Optional[User] = Relationship(back_populates="annotations")


class Approval(SQLModel, table=True):
    __tablename__ = "approval"

    id: Optional[int] = Field(default=None, primary_key=True)
    applicant_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    resource_type: ResourceType = Field(sa_column=Column(SAEnum(ResourceType), nullable=False))
    resource_id: int = Field(nullable=False, index=True)
    purpose: Optional[str] = Field(default=None, sa_column=Column(Text))
    decision: Decision = Field(sa_column=Column(SAEnum(Decision), nullable=False, default=Decision.pending))
    expires_at: Optional[datetime] = None
    reviewed_by: Optional[int] = Field(default=None, foreign_key="user.id")
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    action: str = Field(sa_column=Column(String(64), nullable=False))            # e.g., "login", "upload", "approve"
    resource_type: Optional[str] = Field(default=None, sa_column=Column(String(32)))
    resource_id: Optional[int] = Field(default=None, index=True)
    ip: Optional[str] = Field(default=None, sa_column=Column(String(45)))
    result: AuditResult = Field(sa_column=Column(SAEnum(AuditResult), nullable=False, default=AuditResult.ok))
    detail: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


# ---- 索引（可选但有益） ----
Index("ix_sample_dataset_sha", Sample.dataset_id, Sample.sha256, unique=True)
Index("ix_approval_target", Approval.resource_type, Approval.resource_id)
