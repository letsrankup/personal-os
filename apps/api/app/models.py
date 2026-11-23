"""SQLAlchemy models — all 16 PERSONAL OS tables.

Conventions: UUID string primary keys, created_at/updated_at timestamps,
indexes on ownership/status/foreign keys, JSON columns for flexible payloads.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Priority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class PermissionTier(str, enum.Enum):
    AUTOMATIC = "AUTOMATIC"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    ALWAYS_MANUAL = "ALWAYS_MANUAL"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="owner")  # owner/admin/member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    tasks: Mapped[list["Task"]] = relationship(back_populates="user")
    memories: Mapped[list["Memory"]] = relationship(back_populates="user")
    projects: Mapped[list["Project"]] = relationship(back_populates="user")


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # master, research, ...
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="idle", index=True)  # idle/running/disabled
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    tasks: Mapped[list["Task"]] = relationship(back_populates="agent")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    summary: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(TimestampMixin, Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # user/assistant/agent/system
    agent_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Memory(TimestampMixin, Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)  # preference/instruction/project/decision/research/summary
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(back_populates="memories")


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_status_priority", "status", "priority"),
        Index("ix_tasks_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    agent_key: Mapped[str] = mapped_column(String(64), default="master", index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.NORMAL)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, index=True)
    permission_tier: Mapped[PermissionTier] = mapped_column(
        Enum(PermissionTier), default=PermissionTier.AUTOMATIC
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    logs: Mapped[list] = mapped_column(JSON, default=list)  # [{ts, level, message}]
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User | None] = relationship(back_populates="tasks")
    agent: Mapped[Agent | None] = relationship(back_populates="tasks")
    project: Mapped["Project | None"] = relationship(back_populates="tasks")
    steps: Mapped[list["TaskStep"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TaskStep(TimestampMixin, Base):
    __tablename__ = "task_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    agent_key: Mapped[str] = mapped_column(String(64), default="master")
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped[Task] = relationship(back_populates="steps")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)  # active/paused/done/archived
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped[User | None] = relationship(back_populates="projects")
    tasks: Mapped[list[Task]] = relationship(back_populates="project")


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)  # new/active/follow_up/closed
    notes: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class FileRecord(TimestampMixin, Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024))
    kind: Mapped[str] = mapped_column(String(64), default="file")  # file/report/image/doc
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(64), index=True)  # daily/weekly/monthly/task/agent/research
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Integration(TimestampMixin, Base):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # gmail/calendar/drive/github/ai:...
    status: Mapped[str] = mapped_column(String(32), default="not_connected")  # not_connected/connected/error
    account_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # non-secret config only; secrets stay in env/vault
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    action: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # e.g. email.send, web.publish
    tier: Mapped[PermissionTier] = mapped_column(Enum(PermissionTier))
    description: Mapped[str] = mapped_column(Text, default="")


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)  # pending/approved/rejected
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")  # user/master/agent key/system
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class FinanceEntry(TimestampMixin, Base):
    """One income or expense record (Phase 6, Finance Agent).

    Amounts are only ever recorded and totalled from these real rows — the
    finance agent never moves money (payments stay ALWAYS_MANUAL).
    """

    __tablename__ = "finance_entries"
    __table_args__ = (Index("ix_finance_user_kind_time", "user_id", "kind", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # income | expense
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    category: Mapped[str] = mapped_column(String(64), default="general", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ScheduledJob(TimestampMixin, Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(64))  # report/research/task/custom
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)  # cron-ish spec
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
