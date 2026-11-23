"""Master orchestrator — the command execution engine (Phase 3 + 4 + 5).

Pipeline (an explicit state machine in code; it mirrors the LangGraph graph
UNDERSTAND → PLAN → PERMISSION_CHECK → EXECUTE → VERIFY → PERSIST → REPORT
node-for-node, so swapping in LangGraph later changes only this module):

  UNDERSTAND        rule-based intent routing, English + Roman Urdu keywords
  PLAN              create the Task row + TaskStep rows
  MEMORY            search saved memories, put hits into the agent context
  PERMISSION_CHECK  permissions table decides AUTOMATIC / APPROVAL_REQUIRED /
                    ALWAYS_MANUAL before anything executes
  EXECUTE           run the selected specialist agent
  VERIFY            COMPLETED only when the agent result has verified=True
  PERSIST + REPORT  messages, conversation summary memory, activity logs,
                    final reply text

The master NEVER claims completion without verification.
"""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .agents import get_agent
from .deps import log_activity
from .models import (
    Agent,
    Approval,
    Conversation,
    Memory,
    Message,
    Permission,
    PermissionTier,
    Priority,
    Task,
    TaskStatus,
    TaskStep,
    User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# UNDERSTAND — intent routing (English + Roman Urdu)
# --------------------------------------------------------------------------
class Route:
    def __init__(self, agent_key: str, action: str, operation: str = "run", params: dict | None = None):
        self.agent_key = agent_key
        self.action = action
        self.operation = operation
        self.params = params or {}


def understand(text: str) -> Route:
    """Map a natural-language command to (agent, permission action, operation).

    Order matters: manual-only and approval-gated intents are checked first so
    they can never slip into an automatic route.
    """
    t = f" {text.lower()} "
    has = lambda *words: any(w in t for w in words)  # noqa: E731

    # ALWAYS_MANUAL intents
    if has("transfer money", "money transfer", "send money", "paise transfer", "rupay transfer",
           "rupay bhejo", "paise bhejo", "payment transfer") or ("transfer" in t and has("rupay", "rupee", "rs", "paisa", "paise", "money")):
        return Route("finance", "money.transfer")
    if has("delete my account", "account delete karo", "delete account permanently"):
        return Route("master", "account.delete_irreversible")
    if has("show my password", "password batao", "password disclose", "reveal password"):
        return Route("master", "credentials.disclose")

    # APPROVAL_REQUIRED intents
    if has("send email", "send an email", "email bhejo", "email send karo", "mail bhejo", "send mail"):
        return Route("communication", "email.send_external", operation="send")
    if "publish" in t and has("report", "summary"):
        return Route("reporting", "web.publish", operation="generate", params={"kind": "summary"})
    if has("publish website", "publish the website", "website publish", "publish content"):
        return Route("developer", "web.publish")

    # AUTOMATIC intents — period reports first (Phase 6: daily/weekly kinds)
    if has("daily report", "rozana report", "aaj ki report"):
        return Route("reporting", "reports.create", operation="generate", params={"kind": "daily"})
    if has("weekly report", "haftawar report", "hafta ki report"):
        return Route("reporting", "reports.create", operation="generate", params={"kind": "weekly"})

    # Finance (Phase 6) — tracking only; transfers were refused above.
    if has("kharcha", "kharch", "expense", "hisab", "aamdani", "tankhwah", "income"):
        return Route("finance", "finance.track")

    # Developer (Phase 6)
    if has("review project files", "review files", "files review"):
        return Route("developer", "developer.build", operation="review")
    if has("website banao", "website bana", "website create", "create a website", "create website",
           "build a website", "make a website", "app banao", "app bana", "site banao",
           "code likho", "code banao", "write code"):
        return Route("developer", "developer.build", operation="create")

    # Marketing (Phase 6)
    if has("marketing", "seo", "post likho", "social media post", "content plan"):
        return Route("marketing", "marketing.plan")

    # Business (Phase 6)
    if has("business plan", "business strategy", "strategy banao", "market analysis", "business idea"):
        return Route("business", "business.plan")

    # Client find must precede research ("client dhoondo" contains "dhoondo").
    if has("client", "customer", "grahak") and has("find client", "client dhoondo", "search client", "client find"):
        return Route("clients", "clients.manage", operation="find")

    # Research (Phase 6) — extended EN + Roman Urdu keywords
    if has("research", "tahqeeq", "investigate", "dhoondo", "find out", "maloom karo", "competitor"):
        return Route("research", "research.run")

    # Communication (Phase 6) — drafts automatic; inbox honest-fails (Phase 8)
    if has("inbox", "read my email", "read email", "emails dikhao"):
        return Route("communication", "email.draft", operation="inbox")
    if has("draft email", "email draft", "draft likho", "draft banao", "draft an email", "email likho"):
        return Route("communication", "email.draft", operation="draft")

    # Clients (Phase 6) — sub-intents parsed here, details parsed by the agent
    if has("client", "customer", "grahak"):
        if has("inquiry", "complaint", "shikayat"):
            return Route("clients", "clients.manage", operation="inquiry")
        if has("add client", "client add", "naya client", "new client", "add a client"):
            return Route("clients", "clients.manage", operation="add")
        if has("find client", "client dhoondo", "search client", "client find"):
            return Route("clients", "clients.manage", operation="find")
        return Route("clients", "clients.manage", operation="list")

    # Task create/list precede the project rules so "create a task about a
    # blocker" creates a task instead of routing to the blockers view.
    if has("create a task", "create task", "add a task", "add task", "new task",
           "task banao", "task bana", "task create karo", "kaam add karo"):
        return Route("tasks", "tasks.manage_internal", operation="create",
                     params={"title": _extract_task_title(text), "description": text,
                             "priority": _extract_priority(t), "due_at": _extract_due(text)})
    if has("list", "dikhao", "show", "pending", "meri tasks", "mere tasks", "mere kaam",
           "list karo", "batao") and has("task", "tasks", "kaam", "pending"):
        return Route("tasks", "tasks.manage_internal", operation="list",
                     params={"pending_only": "pending" in t})

    # Projects (Phase 6)
    if has("blocker", "blockers", "rukawat"):
        return Route("projects", "projects.manage", operation="blockers")
    if has("progress") and has("project"):
        return Route("projects", "projects.manage", operation="progress")
    if has("create project", "project banao", "new project", "add project", "project create", "start project"):
        return Route("projects", "projects.manage", operation="create")

    if has("report", "summary", "progress report", "report banao", "report bana", "summary banao"):
        return Route("reporting", "reports.create", operation="generate", params={"kind": "summary"})
    if has("email", "mail", "inbox"):
        return Route("communication", "email.draft", operation="draft")
    if has("project", "mansooba"):
        return Route("projects", "projects.manage", operation="list")
    if has("task", "tasks", "kaam"):
        return Route("tasks", "tasks.manage_internal", operation="list",
                     params={"pending_only": "pending" in t})

    # Default: general command/question → master answers via the AI layer.
    return Route("master", "ai.chat", operation="general")


def _extract_task_title(text: str) -> str:
    m = re.search(r"task\s+to\s+(.+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".")
    m = re.search(r"task\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".")
    cleaned = re.sub(
        r"(?i)\b(create|add|make|new|a|an|the|task|banao|bana|karo|kar)\b", " ", text
    ).strip(" .:-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or text.strip())[:255]


def _extract_priority(t: str) -> str:
    """t is the space-padded lowercase command text."""
    if "urgent" in t or "fawri" in t:
        return "URGENT"
    if "bohat zaroori" in t or "bohut zaroori" in t or "high priority" in t or " high " in t:
        return "HIGH"
    if "low priority" in t or " low " in t or "kam zaroori" in t:
        return "LOW"
    return "NORMAL"


def _extract_due(text: str) -> str | None:
    """Simple deadline forms -> ISO timestamp (end of day, UTC):
    an ISO date (2026-12-01), 'tomorrow' / 'kal', 'today' / 'aaj'."""
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m:
        try:
            due = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 23, 59, tzinfo=timezone.utc)
            return due.isoformat()
        except ValueError:
            return None
    low = text.lower()
    if "tomorrow" in low or re.search(r"\bkal\b", low):
        due = datetime.now(timezone.utc) + timedelta(days=1)
        return due.replace(hour=23, minute=59, second=0, microsecond=0).isoformat()
    if "today" in low or re.search(r"\baaj\b", low):
        due = datetime.now(timezone.utc)
        return due.replace(hour=23, minute=59, second=0, microsecond=0).isoformat()
    return None


# --------------------------------------------------------------------------
# MEMORY — keyword search over saved memories
# --------------------------------------------------------------------------
def search_memories(db: Session, user_id: str, text: str, limit: int = 5) -> list[dict]:
    words = {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}
    if not words:
        return []
    hits = []
    for mem in db.query(Memory).filter(Memory.user_id == user_id).order_by(Memory.created_at.desc()).limit(200).all():
        haystack = f"{mem.title} {mem.content} {' '.join(mem.tags or [])}".lower()
        score = sum(1 for w in words if w in haystack)
        if score:
            hits.append((score, mem))
    hits.sort(key=lambda pair: -pair[0])
    return [
        {"id": m.id, "kind": m.kind, "title": m.title, "content": m.content, "tags": m.tags}
        for _, m in hits[:limit]
    ]


# --------------------------------------------------------------------------
# Pipeline helpers
# --------------------------------------------------------------------------
def _task_log(task: Task, message: str, level: str = "info") -> None:
    task.logs = [*(task.logs or []), {"ts": _now().isoformat(), "level": level, "message": message}]


def _set_step(db: Session, task: Task, order: int, status: TaskStatus, error: str | None = None) -> None:
    step = next((s for s in task.steps if s.order == order), None)
    if step is None:
        return
    if status == TaskStatus.RUNNING and step.started_at is None:
        step.started_at = _now()
    if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.WAITING_FOR_APPROVAL):
        step.completed_at = _now()
    step.status = status
    if error:
        step.error = error


def permission_tier_for(db: Session, action: str) -> PermissionTier:
    row = db.query(Permission).filter_by(action=action).first()
    return row.tier if row else PermissionTier.AUTOMATIC  # unlisted internal actions run automatically


def _execute_task(db: Session, user: User, task: Task, route: Route, memories: list[dict]) -> dict:
    """EXECUTE + VERIFY states. Returns the agent's raw result dict."""
    task.status = TaskStatus.RUNNING
    task.started_at = _now()
    _set_step(db, task, 4, TaskStatus.RUNNING)
    _task_log(task, f"Execution started with agent '{route.agent_key}' (operation: {route.operation}).")
    log_activity(db, "task.running", actor="master", user_id=user.id, entity="tasks", entity_id=task.id)
    db.flush()

    agent = get_agent(route.agent_key)
    context = {"operation": route.operation, "params": route.params, "memories": memories, "user_id": user.id}
    try:
        outcome = agent.run(db, task, context)
    except Exception as exc:  # an agent crash is a FAILED task, never a fake success
        outcome = {"result": None, "verified": False, "error": f"Agent crashed: {exc}", "logs": []}
    for line in outcome.get("logs", []):
        _task_log(task, line)
    if outcome.get("report_id"):
        task.logs = task.logs  # no-op clarity; report id is in the agent logs

    _set_step(db, task, 5, TaskStatus.RUNNING)
    task.completed_at = _now()
    if outcome.get("verified") and outcome.get("result"):
        task.status = TaskStatus.COMPLETED
        task.verified = True
        task.result = outcome["result"]
        task.error = None
        _set_step(db, task, 4, TaskStatus.COMPLETED)
        _set_step(db, task, 5, TaskStatus.COMPLETED)
        _task_log(task, "Result verified — task COMPLETED.")
        log_activity(db, "task.completed", actor=route.agent_key, user_id=user.id, entity="tasks", entity_id=task.id)
    else:
        task.status = TaskStatus.FAILED
        task.verified = False
        task.error = outcome.get("error") or "Agent result could not be verified."
        _set_step(db, task, 4, TaskStatus.FAILED, error=task.error)
        _set_step(db, task, 5, TaskStatus.FAILED, error=task.error)
        _task_log(task, f"Verification failed — task FAILED: {task.error}", level="error")
        log_activity(db, "task.failed", actor=route.agent_key, user_id=user.id, entity="tasks", entity_id=task.id,
                     details={"error": task.error})
    db.flush()
    return outcome


# --------------------------------------------------------------------------
# Main entry — POST /commands
# --------------------------------------------------------------------------
def run_command(db: Session, user: User, text: str, conversation_id: str | None = None) -> dict:
    # Conversation persistence (part of PERSIST, done first so nothing is lost).
    conversation = None
    if conversation_id:
        conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=user.id).first()
    if conversation is None:
        conversation = Conversation(user_id=user.id, title=text[:80])
        db.add(conversation)
        db.flush()
    db.add(Message(conversation_id=conversation.id, role="user", content=text))
    db.flush()
    log_activity(db, "command.received", actor="user", user_id=user.id,
                 entity="conversations", entity_id=conversation.id, details={"text": text[:200]})

    # UNDERSTAND
    route = understand(text)

    # MEMORY first — relevant saved memories go into the agent context.
    memories = search_memories(db, user.id, text)

    # PLAN — task row + step rows.
    tier = permission_tier_for(db, route.action)
    agent_row = db.query(Agent).filter_by(key=route.agent_key).first()
    task = Task(
        user_id=user.id,
        agent_id=agent_row.id if agent_row else None,
        agent_key=route.agent_key,
        title=text[:120],
        description=text,
        status=TaskStatus.PLANNING,
        permission_tier=tier,
    )
    db.add(task)
    db.flush()
    step_specs = [
        (1, "master", "Understand command and identify objective"),
        (2, "master", f"Plan and select agent '{route.agent_key}' for action '{route.action}'"),
        (3, "master", f"Permission check for action '{route.action}'"),
        (4, route.agent_key, f"Execute with the {route.agent_key} agent (operation: {route.operation})"),
        (5, "master", "Verify result and write final report"),
    ]
    for order, key, desc in step_specs:
        db.add(TaskStep(task_id=task.id, order=order, agent_key=key, description=desc))
    db.flush()
    db.refresh(task)
    _set_step(db, task, 1, TaskStatus.COMPLETED)
    _set_step(db, task, 2, TaskStatus.COMPLETED)
    _task_log(task, f"Understood objective; routed to agent '{route.agent_key}', action '{route.action}'.")
    _task_log(task, f"Memory search returned {len(memories)} hit(s).")
    log_activity(db, "task.created", actor="master", user_id=user.id, entity="tasks", entity_id=task.id,
                 details={"agent": route.agent_key, "action": route.action})

    # PERMISSION_CHECK
    _set_step(db, task, 3, TaskStatus.RUNNING)
    approval_id = None
    if tier == PermissionTier.ALWAYS_MANUAL:
        reason = (
            f"Action '{route.action}' is ALWAYS_MANUAL: PERSONAL OS never performs it automatically. "
            "Please do it yourself manually."
        )
        task.status = TaskStatus.CANCELLED
        task.error = reason
        task.completed_at = _now()
        _set_step(db, task, 3, TaskStatus.CANCELLED, error=reason)
        _set_step(db, task, 4, TaskStatus.CANCELLED, error=reason)
        _set_step(db, task, 5, TaskStatus.CANCELLED, error=reason)
        _task_log(task, reason, level="error")
        log_activity(db, "task.cancelled_manual", actor="master", user_id=user.id, entity="tasks",
                     entity_id=task.id, details={"action": route.action})
        reply = f"Refused: {reason}"
        db.flush()
        _persist_reply(db, user, conversation, task, route, reply)
        return {"task_id": task.id, "status": task.status.value, "reply": reply,
                "agent": route.agent_key, "conversation_id": conversation.id, "approval_id": None}

    if tier == PermissionTier.APPROVAL_REQUIRED:
        approval = Approval(
            task_id=task.id,
            user_id=user.id,
            action=route.action,
            summary=f"Approval needed to run '{route.action}' via the {route.agent_key} agent for command: {text[:160]}",
            payload={"agent_key": route.agent_key, "action": route.action,
                     "operation": route.operation, "params": route.params, "command_text": text},
            status="pending",
        )
        db.add(approval)
        task.status = TaskStatus.WAITING_FOR_APPROVAL
        _set_step(db, task, 3, TaskStatus.WAITING_FOR_APPROVAL)
        _set_step(db, task, 4, TaskStatus.WAITING_FOR_APPROVAL)
        _task_log(task, f"Permission tier APPROVAL_REQUIRED — held for user approval (approval id: pending flush).")
        db.flush()
        approval_id = approval.id
        _task_log(task, f"Approval row created: {approval_id}. Nothing has been executed.")
        log_activity(db, "task.waiting_for_approval", actor="master", user_id=user.id, entity="tasks",
                     entity_id=task.id, details={"approval_id": approval_id, "action": route.action})
        reply = (
            f"Approval required: action '{route.action}' needs your approval before the "
            f"{route.agent_key} agent runs. Task {task.id} is WAITING_FOR_APPROVAL "
            f"(approval id: {approval_id}). Nothing has been executed yet."
        )
        _persist_reply(db, user, conversation, task, route, reply)
        return {"task_id": task.id, "status": task.status.value, "reply": reply,
                "agent": route.agent_key, "conversation_id": conversation.id, "approval_id": approval_id}

    _set_step(db, task, 3, TaskStatus.COMPLETED)

    # EXECUTE + VERIFY
    outcome = _execute_task(db, user, task, route, memories)

    # REPORT — final reply text.
    if task.status == TaskStatus.COMPLETED:
        reply = task.result or ""
    else:
        reply = f"Task FAILED: {task.error}"
    _persist_reply(db, user, conversation, task, route, reply)
    return {"task_id": task.id, "status": task.status.value, "reply": reply,
            "agent": route.agent_key, "conversation_id": conversation.id, "approval_id": None}


def _persist_reply(db: Session, user: User, conversation: Conversation, task: Task, route: Route, reply: str) -> None:
    """PERSIST state: assistant message, conversation summary, summary memory."""
    db.add(Message(conversation_id=conversation.id, role="assistant", agent_key=route.agent_key,
                   content=reply, meta={"task_id": task.id, "status": task.status.value}))
    summary = f"Command '{task.description[:80]}' → agent {route.agent_key}, status {task.status.value}."
    conversation.summary = summary
    db.add(Memory(
        user_id=user.id,
        kind="conversation_summary",
        title=f"Command: {task.description[:60]}",
        content=f"{summary} Result: {(task.result or task.error or '')[:500]}",
        tags=[route.agent_key, task.status.value],
        source_ref=task.id,
    ))
    db.flush()


# --------------------------------------------------------------------------
# Approval decision — execute (or cancel) a held task
# --------------------------------------------------------------------------
def execute_approved_task(db: Session, user: User, approval: Approval) -> Task:
    task = db.get(Task, approval.task_id)
    if task is None:
        raise ValueError("Approval references a missing task")
    payload = approval.payload or {}
    route = Route(
        agent_key=payload.get("agent_key", task.agent_key),
        action=payload.get("action", approval.action),
        operation=payload.get("operation", "run"),
        params=payload.get("params", {}),
    )
    _set_step(db, task, 3, TaskStatus.COMPLETED)
    _task_log(task, f"Approval {approval.id} approved by user — executing held action '{route.action}'.")
    log_activity(db, "task.approved_execution", actor="user", user_id=user.id, entity="tasks", entity_id=task.id)
    memories = search_memories(db, user.id, task.description)
    _execute_task(db, user, task, route, memories)
    db.flush()
    return task
