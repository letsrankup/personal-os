"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

MEMORY_KINDS = (
    "preference",
    "instruction",
    "project",
    "task",
    "conversation_summary",
    "research",
    "decision",
    "file_ref",
)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


# --- Commands / conversations ---------------------------------------------
class CommandIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class CommandOut(BaseModel):
    task_id: str
    status: str
    reply: str
    agent: str
    conversation_id: str
    approval_id: str | None = None


class ConversationOut(BaseModel):
    id: str
    title: str
    summary: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    agent_key: str | None
    content: str
    meta: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Tasks ------------------------------------------------------------------
class TaskStepOut(BaseModel):
    id: str
    order: int
    agent_key: str
    description: str
    status: str
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: str
    title: str
    description: str
    agent_key: str
    priority: str
    status: str
    permission_tier: str
    result: str | None
    error: str | None
    verified: bool
    logs: list
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskDetailOut(TaskOut):
    steps: list[TaskStepOut] = []


# --- Approvals ---------------------------------------------------------------
class ApprovalOut(BaseModel):
    id: str
    task_id: str | None
    action: str
    summary: str
    payload: dict
    status: str
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class DecideIn(BaseModel):
    decision: Literal["approved", "rejected"]


# --- Memories ------------------------------------------------------------------
class MemoryIn(BaseModel):
    kind: Literal[
        "preference", "instruction", "project", "task",
        "conversation_summary", "research", "decision", "file_ref",
    ]
    title: str = ""
    content: str = Field(min_length=1)
    tags: list[str] = []
    source_ref: str | None = None


class MemoryPatch(BaseModel):
    kind: str | None = None
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    source_ref: str | None = None


class MemoryOut(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    tags: list
    source_ref: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Agents ---------------------------------------------------------------------
class AgentOut(BaseModel):
    id: str
    key: str
    name: str
    role: str
    status: str
    model: str | None

    model_config = {"from_attributes": True}


# --- Phase 7 read endpoints: projects / clients / files / reports / misc -----
class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    status: str
    meta: dict
    total_tasks: int = 0
    completed_tasks: int = 0
    progress_pct: int = 0
    created_at: datetime
    updated_at: datetime


class ClientOut(BaseModel):
    id: str
    name: str
    email: str | None
    phone: str | None
    company: str | None
    category: str
    status: str
    notes: str
    meta: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileOut(BaseModel):
    id: str
    project_id: str | None
    name: str
    path: str
    kind: str
    size_bytes: int | None
    meta: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    data: dict
    period_start: datetime | None
    period_end: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IntegrationOut(BaseModel):
    id: str
    provider: str
    status: str
    account_label: str | None
    # Non-secret display config only (login/model/note/auth_url). The API
    # masks sensitive-looking keys before this ever leaves the server.
    config: dict = {}
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Scheduled jobs (Phase 9) -------------------------------------------------
class JobIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: Literal["report"] = "report"
    report_kind: Literal["summary", "daily", "weekly"] = "summary"
    interval: Literal["daily", "weekly"] | None = None
    run_at: datetime | None = None  # one-off: run at this ISO time instead


class JobOut(BaseModel):
    id: str
    name: str
    kind: str
    report_kind: str
    interval: str
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PermissionOut(BaseModel):
    id: str
    action: str
    tier: str
    description: str

    model_config = {"from_attributes": True}


class ActivityOut(BaseModel):
    id: str
    actor: str
    action: str
    entity: str | None
    entity_id: str | None
    details: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class FinanceEntryOut(BaseModel):
    id: str
    kind: str  # income | expense
    amount: float
    currency: str
    category: str
    note: str
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
