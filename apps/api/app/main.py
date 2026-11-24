"""PERSONAL OS API — FastAPI application (Phases 1–9)."""
import asyncio
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, engine, get_db, init_db
from .deps import get_current_user, log_activity, require_owner_or_admin
from . import ai as ai_layer
from . import integrations as integrations_mod
from . import jobs as jobs_mod
from .models import (
    ActivityLog,
    Agent,
    Approval,
    Client,
    Conversation,
    FileRecord,
    FinanceEntry,
    Integration,
    Memory,
    Message,
    Permission,
    Project,
    Report,
    ScheduledJob,
    Task,
    TaskStatus,
    User,
)
from .ratelimit import rate_limit
from .orchestrator import execute_approved_task, run_command
from .schemas import (
    MEMORY_KINDS,
    ActivityOut,
    AgentOut,
    ApprovalOut,
    ClientOut,
    FileOut,
    FinanceEntryOut,
    IntegrationOut,
    JobIn,
    JobOut,
    PermissionOut,
    ProjectOut,
    ReportOut,
    CommandIn,
    CommandOut,
    ConversationOut,
    DecideIn,
    LoginIn,
    MemoryIn,
    MemoryOut,
    MemoryPatch,
    MessageOut,
    RegisterIn,
    TaskDetailOut,
    TaskOut,
    TokenOut,
    UserOut,
)
from .security import create_access_token, hash_password, verify_password
from .seed import seed_all


async def _jobs_loop() -> None:
    """Background scheduler (Phase 9): run due jobs every 60s.

    Fully guarded — a busy/locked DB or a failing job must never take
    the API down; the failure is swallowed here and recorded in
    activity_logs by the jobs module whenever it gets far enough.
    """
    while True:
        try:
            await asyncio.sleep(60)
            with SessionLocal() as db:
                jobs_mod.run_due_jobs(db)
        except asyncio.CancelledError:
            raise
        except Exception:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_all(db)  # agents + permission tiers + integrations (+ admin only if env is set)
    loop_task = asyncio.create_task(_jobs_loop())
    try:
        yield
    finally:
        loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await loop_task


app = FastAPI(title="PERSONAL OS API", version="0.3.0", lifespan=lifespan)


def _allowed_origins() -> list[str]:
    """CORS allow-list (Phase 9): env ALLOWED_ORIGINS (comma-separated)
    when set, else the configured web origin. Never wide open."""
    raw = os.environ.get("ALLOWED_ORIGINS") or settings.allowed_origins or settings.web_origin
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = "error"
    return {"status": "ok", "service": "personal-os-api", "db": db_ok, "ai_provider": ai_layer.provider_name()}


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
          dependencies=[Depends(rate_limit("auth"))])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    # Password policy (Phase 9): RegisterIn enforces min_length=8 → 422.
    if db.query(User).filter_by(email=body.email).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    log_activity(db, "auth.register", actor="user", user_id=user.id, entity="users", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=TokenOut, dependencies=[Depends(rate_limit("auth"))])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        # Audit failures too (Phase 9) — committed before the 401 is raised.
        log_activity(db, "auth.login_failed", actor="anonymous",
                     user_id=user.id if user else None,
                     entity="users", entity_id=user.id if user else None,
                     details={"email": body.email})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    log_activity(db, "auth.login", actor="user", user_id=user.id, entity="users", entity_id=user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id))


@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Command Center (Phase 3/4) — runs the master orchestrator pipeline
# ---------------------------------------------------------------------------
@app.post("/commands", response_model=CommandOut, dependencies=[Depends(rate_limit("commands"))])
def create_command(
    body: CommandIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = run_command(db, current_user, body.text, body.conversation_id)
    db.commit()
    return result


@app.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Conversation)
        .filter_by(user_id=current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(100)
        .all()
    )


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=current_user.id).first()
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return (
        db.query(Message)
        .filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
def _task_out(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "agent_key": task.agent_key,
        "priority": task.priority.value,
        "status": task.status.value,
        "permission_tier": task.permission_tier.value,
        "result": task.result,
        "error": task.error,
        "verified": task.verified,
        "logs": task.logs or [],
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "created_at": task.created_at,
    }


@app.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    status_filter: str | None = Query(None, alias="status"),
    agent: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Task).filter_by(user_id=current_user.id)
    if status_filter:
        try:
            q = q.filter(Task.status == TaskStatus(status_filter))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid task status '{status_filter}'")
    if agent:
        q = q.filter(Task.agent_key == agent)
    return [_task_out(t) for t in q.order_by(Task.created_at.desc()).limit(200).all()]


@app.get("/tasks/{task_id}", response_model=TaskDetailOut)
def get_task(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter_by(id=task_id, user_id=current_user.id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    out = _task_out(task)
    out["steps"] = [
        {
            "id": s.id,
            "order": s.order,
            "agent_key": s.agent_key,
            "description": s.description,
            "status": s.status.value,
            "error": s.error,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
        }
        for s in sorted(task.steps, key=lambda s: s.order)
    ]
    return out


@app.post("/tasks/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter_by(id=task_id, user_id=current_user.id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Task is already {task.status.value}")
    task.status = TaskStatus.CANCELLED
    task.completed_at = datetime.now(timezone.utc)
    task.error = "Cancelled by user."
    pending = (
        db.query(Approval)
        .filter_by(task_id=task.id, status="pending")
        .first()
    )
    if pending is not None:
        pending.status = "rejected"
        pending.decided_at = datetime.now(timezone.utc)
    log_activity(db, "task.cancelled", actor="user", user_id=current_user.id, entity="tasks", entity_id=task.id)
    db.commit()
    db.refresh(task)
    return _task_out(task)


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------
@app.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Approval)
        .filter_by(user_id=current_user.id, status="pending")
        .order_by(Approval.created_at.desc())
        .all()
    )


@app.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    body: DecideIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approval = db.query(Approval).filter_by(id=approval_id, user_id=current_user.id).first()
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval not found")
    if approval.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Approval already {approval.status}")
    approval.status = body.decision
    approval.decided_at = datetime.now(timezone.utc)
    task = db.get(Task, approval.task_id) if approval.task_id else None
    log_activity(db, f"approval.{body.decision}", actor="user", user_id=current_user.id,
                 entity="approvals", entity_id=approval.id)
    if body.decision == "rejected":
        if task is not None and task.status == TaskStatus.WAITING_FOR_APPROVAL:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            task.error = "Approval rejected by user — held action was never executed."
        db.commit()
        return {"approval_id": approval.id, "decision": "rejected",
                "task_id": task.id if task else None,
                "task_status": task.status.value if task else None}
    # Approved → execute the held task's agent now.
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Held task not found")
    execute_approved_task(db, current_user, approval)
    db.commit()
    db.refresh(task)
    return {"approval_id": approval.id, "decision": "approved",
            "task_id": task.id, "task_status": task.status.value,
            "result": task.result, "error": task.error}


# ---------------------------------------------------------------------------
# Memories (Phase 5)
# ---------------------------------------------------------------------------
@app.post("/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def create_memory(body: MemoryIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mem = Memory(user_id=current_user.id, kind=body.kind, title=body.title,
                 content=body.content, tags=body.tags, source_ref=body.source_ref)
    db.add(mem)
    log_activity(db, "memory.created", actor="user", user_id=current_user.id, entity="memories")
    db.commit()
    db.refresh(mem)
    return mem


@app.get("/memories", response_model=list[MemoryOut])
def list_memories(
    q: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Memory).filter_by(user_id=current_user.id)
    if kind:
        query = query.filter(Memory.kind == kind)
    rows = query.order_by(Memory.created_at.desc()).limit(200).all()
    if q:
        needle = q.lower()
        rows = [
            m for m in rows
            if needle in m.title.lower() or needle in m.content.lower()
            or any(needle in str(tag).lower() for tag in (m.tags or []))
        ]
    return rows


def _get_memory(db: Session, user_id: str, memory_id: str) -> Memory:
    mem = db.query(Memory).filter_by(id=memory_id, user_id=user_id).first()
    if mem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    return mem


@app.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_memory(db, current_user.id, memory_id)


@app.patch("/memories/{memory_id}", response_model=MemoryOut)
def patch_memory(
    memory_id: str,
    body: MemoryPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mem = _get_memory(db, current_user.id, memory_id)
    updates = body.model_dump(exclude_unset=True)
    if "kind" in updates and updates["kind"] is not None and updates["kind"] not in MEMORY_KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid memory kind '{updates['kind']}'")
    for field, value in updates.items():
        if value is not None:
            setattr(mem, field, value)
    log_activity(db, "memory.updated", actor="user", user_id=current_user.id, entity="memories", entity_id=mem.id)
    db.commit()
    db.refresh(mem)
    return mem


@app.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mem = _get_memory(db, current_user.id, memory_id)
    log_activity(db, "memory.deleted", actor="user", user_id=current_user.id, entity="memories", entity_id=mem.id)
    db.delete(mem)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Agents + dashboard overview
# ---------------------------------------------------------------------------
@app.get("/agents", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Agent).order_by(Agent.key.asc()).all()


@app.get("/overview")
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    status_counts = {s.value: 0 for s in TaskStatus}
    for st, count in (
        db.query(Task.status, func.count(Task.id)).filter_by(user_id=current_user.id).group_by(Task.status).all()
    ):
        status_counts[st.value] = count
    recent = (
        db.query(ActivityLog)
        .filter_by(user_id=current_user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
        .all()
    )
    latest_reports = (
        db.query(Report).order_by(Report.created_at.desc()).limit(5).all()
    )
    return {
        "total_tasks": sum(status_counts.values()),
        "tasks_by_status": status_counts,
        "completed_tasks": status_counts["COMPLETED"],
        "running_tasks": status_counts["RUNNING"],
        "failed_tasks": status_counts["FAILED"],
        "active_agents": db.query(func.count(Agent.id)).filter(Agent.status != "disabled").scalar() or 0,
        "projects_in_progress": db.query(func.count(Project.id)).filter_by(user_id=current_user.id, status="active").scalar() or 0,
        "recent_activity": [
            {"action": r.action, "actor": r.actor, "entity": r.entity, "created_at": r.created_at.isoformat()}
            for r in recent
        ],
        "latest_reports": [
            {"id": r.id, "kind": r.kind, "title": r.title, "created_at": r.created_at.isoformat()}
            for r in latest_reports
        ],
    }


# ---------------------------------------------------------------------------
# Phase 7 read endpoints (dashboard data: projects, clients, files, reports,
# integrations, permissions, activity audit). All JWT-protected, read-only.
# ---------------------------------------------------------------------------
def _project_out(db: Session, project: Project) -> ProjectOut:
    total = db.query(func.count(Task.id)).filter_by(project_id=project.id).scalar() or 0
    done = (
        db.query(func.count(Task.id))
        .filter_by(project_id=project.id, status=TaskStatus.COMPLETED)
        .scalar()
        or 0
    )
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        meta=project.meta or {},
        total_tasks=total,
        completed_tasks=done,
        progress_pct=int(round(100 * done / total)) if total else 0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(Project)
        .filter_by(user_id=current_user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    return [_project_out(db, p) for p in rows]


@app.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter_by(id=project_id, user_id=current_user.id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_out(db, project)


@app.get("/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Clients table has no user_id by design (see clients_agent) — shared list.
    return db.query(Client).order_by(Client.updated_at.desc()).all()


@app.get("/clients/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = db.query(Client).filter_by(id=client_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@app.get("/files", response_model=list[FileOut])
def list_files(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(FileRecord)
        .filter_by(user_id=current_user.id)
        .order_by(FileRecord.created_at.desc())
        .all()
    )


@app.get("/reports", response_model=list[ReportOut])
def list_reports(
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Report)
    if kind:
        q = q.filter_by(kind=kind)
    return q.order_by(Report.created_at.desc()).limit(200).all()


@app.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = db.query(Report).filter_by(id=report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


def _integration_out(row: Integration) -> dict:
    return {
        "id": row.id,
        "provider": row.provider,
        "status": row.status,
        "account_label": row.account_label,
        "config": integrations_mod.public_config(row.config),
        "last_checked_at": row.last_checked_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@app.get("/integrations", response_model=list[IntegrationOut])
def list_integrations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    integrations_mod.ensure_integrations(db)
    db.commit()
    rows = db.query(Integration).order_by(Integration.provider.asc()).all()
    return [_integration_out(r) for r in rows]


@app.post("/integrations/{key}/check", response_model=IntegrationOut)
def check_integration(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    """Run the real connection check for one provider (Phase 8).

    Owner/admin only. The result — connected / not_connected /
    awaiting_oauth / error — is whatever the live check produced; the
    check itself never stores or returns a secret. Audited.
    """
    if key not in integrations_mod.PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown integration '{key}'")
    row = integrations_mod.run_check(db, key)
    log_activity(db, "integration.check", actor="user", user_id=current_user.id,
                 entity="integrations", entity_id=row.id,
                 details={"provider": key, "status": row.status})
    db.commit()
    db.refresh(row)
    return _integration_out(row)


@app.get("/permissions", response_model=list[PermissionOut])
def list_permissions(db: Session = Depends(get_db), current_user: User = Depends(require_owner_or_admin)):
    rows = db.query(Permission).order_by(Permission.action.asc()).all()
    return [
        PermissionOut(id=p.id, action=p.action, tier=p.tier.value, description=p.description)
        for p in rows
    ]


@app.get("/activity", response_model=list[ActivityOut])
def list_activity(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(ActivityLog)
        .filter_by(user_id=current_user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/finance", response_model=list[FinanceEntryOut])
def list_finance_entries(
    limit: int = Query(default=200, ge=1, le=500),
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only finance ledger (Futuristic UI): rows are written only by the
    Finance Agent through commands; totals are computed by the client from
    these real rows. No money ever moves through this endpoint."""
    q = db.query(FinanceEntry).filter_by(user_id=current_user.id)
    if kind in ("income", "expense"):
        q = q.filter_by(kind=kind)
    return q.order_by(FinanceEntry.occurred_at.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# Scheduled jobs (Phase 9) — kind="report" jobs run the Reporting Agent
# ---------------------------------------------------------------------------
def _job_out(job: ScheduledJob) -> dict:
    return {
        "id": job.id,
        "name": job.name,
        "kind": job.kind,
        "report_kind": (job.payload or {}).get("report_kind", "summary"),
        "interval": (job.schedule or {}).get("interval", "once"),
        "enabled": job.enabled,
        "last_run_at": job.last_run_at,
        "next_run_at": job.next_run_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(ScheduledJob).order_by(ScheduledJob.created_at.desc()).all()
    return [_job_out(j) for j in rows]


@app.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(body: JobIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if db.query(ScheduledJob).filter_by(name=body.name).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A job named '{body.name}' already exists")
    now = datetime.now(timezone.utc)
    if body.run_at is not None:
        run_at = body.run_at if body.run_at.tzinfo else body.run_at.replace(tzinfo=timezone.utc)
        interval = "once"
        next_run_at = run_at
    else:
        interval = body.interval or "daily"
        next_run_at = now + jobs_mod._INTERVAL_DELTAS[interval]
    job = ScheduledJob(
        name=body.name,
        kind=body.kind,
        schedule={"interval": interval},
        payload={"report_kind": body.report_kind, "user_id": current_user.id},
        enabled=True,
        next_run_at=next_run_at,
    )
    db.add(job)
    db.flush()
    log_activity(db, "job.created", actor="user", user_id=current_user.id,
                 entity="scheduled_jobs", entity_id=job.id,
                 details={"name": job.name, "report_kind": body.report_kind, "interval": interval})
    db.commit()
    db.refresh(job)
    return _job_out(job)


@app.post("/jobs/{job_id}/run")
def run_job_now(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ScheduledJob).filter_by(id=job_id).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    summary = jobs_mod.execute_job(db, job)
    db.commit()
    db.refresh(job)
    out = _job_out(job)
    out["executed"] = summary["error"] is None
    out["report_id"] = summary["report_id"]
    out["error"] = summary["error"]
    return out


@app.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ScheduledJob).filter_by(id=job_id).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    log_activity(db, "job.deleted", actor="user", user_id=current_user.id,
                 entity="scheduled_jobs", entity_id=job.id, details={"name": job.name})
    db.delete(job)
    db.commit()
    return None
