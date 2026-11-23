"""Task Management Agent — real DB-backed task operations.

Operations (context["operation"]):
  list   — list the user's tasks (context["params"]["pending_only"] filters to PENDING)
  create — create a new task row from context["params"]
           {title, description, priority, agent_key, due_at (ISO string, optional)}
  update — set a task's status from context["params"] {task_id, status}
Priorities (LOW/NORMAL/HIGH/URGENT) and deadlines are parsed by the
orchestrator from the command text (incl. Roman Urdu: "bohat zaroori" =
high priority, "kal" = due tomorrow) and stored on the row (due_at column).
Every operation re-reads the DB before claiming verified=True.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Priority, Task, TaskStatus
from .base import BaseAgent


class TasksAgent(BaseAgent):
    key = "tasks"
    name = "Task Management Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        op = context.get("operation", "list")
        params = context.get("params", {})
        handler = {"list": self._list, "create": self._create, "update": self._update}.get(op)
        if handler is None:
            msg = f"Tasks agent does not support operation '{op}'."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        return handler(db, task, params)

    def _list(self, db: Session, task: Task, params: dict) -> dict:
        q = db.query(Task).filter(Task.user_id == task.user_id, Task.id != task.id)
        pending_only = bool(params.get("pending_only"))
        if pending_only:
            q = q.filter(Task.status == TaskStatus.PENDING)
        rows = q.order_by(Task.created_at.desc()).limit(50).all()
        label = "pending task" if pending_only else "task"
        if not rows:
            result = f"No {label}s found."
        else:
            lines = [f"Found {len(rows)} {label}(s):"]
            for r in rows:
                due = f", due: {r.due_at:%Y-%m-%d}" if r.due_at else ""
                lines.append(f"- [{r.status.value}] {r.title} (agent: {r.agent_key}, priority: {r.priority.value}{due})")
            result = "\n".join(lines)
        return {"result": result, "verified": True, "logs": [f"Listed {len(rows)} task(s) from DB (pending_only={pending_only})."]}

    def _create(self, db: Session, task: Task, params: dict) -> dict:
        title = (params.get("title") or "Untitled task").strip()
        try:
            priority = Priority(params.get("priority", "NORMAL"))
        except ValueError:
            priority = Priority.NORMAL
        due_at = None
        if params.get("due_at"):
            try:
                due_at = datetime.fromisoformat(str(params["due_at"]))
            except ValueError:
                due_at = None
        new_task = Task(
            user_id=task.user_id,
            agent_key=params.get("agent_key", "tasks"),
            title=title,
            description=params.get("description") or title,
            priority=priority,
            status=TaskStatus.PENDING,
            due_at=due_at,
        )
        db.add(new_task)
        db.flush()
        # Verify by re-reading the row we just wrote.
        saved = db.get(Task, new_task.id)
        if saved is None:
            msg = "Task create could not be verified in the database."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        due_txt = f", due: {saved.due_at:%Y-%m-%d}" if saved.due_at else ""
        result = f"Task created: '{saved.title}' (id: {saved.id}, status: PENDING, priority: {saved.priority.value}{due_txt})."
        return {"result": result, "verified": True, "logs": [result]}

    def _update(self, db: Session, task: Task, params: dict) -> dict:
        target = db.get(Task, params.get("task_id", ""))
        if target is None or target.user_id != task.user_id:
            msg = f"Task '{params.get('task_id')}' not found for this user."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        try:
            new_status = TaskStatus(params.get("status", ""))
        except ValueError:
            msg = f"Invalid task status '{params.get('status')}'."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        target.status = new_status
        db.flush()
        db.refresh(target)
        result = f"Task '{target.title}' updated to status {target.status.value}."
        return {"result": result, "verified": target.status == new_status, "logs": [result]}
