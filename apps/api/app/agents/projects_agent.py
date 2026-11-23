"""Project Manager Agent — real project tracking on the `projects` table.

Progress uses REAL linked-task counts: the tasks table already carries a
nullable project_id FK, so a project's progress = counts of its linked tasks
grouped by status (plus its own status field). No schema change was needed.

Operations (context["operation"]):
  create   — insert a projects row (name parsed from the command), verified
             by re-reading it.
  list     — list the user's projects with status + linked-task counts.
  progress — per-project status + linked tasks by status; for a named
             project, just that one.
  blockers — FAILED tasks (all the user's) + the longest-PENDING tasks —
             these are the real blockers, read straight from the DB.
"""
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Project, Task, TaskStatus
from .base import BaseAgent


def _fail(msg: str) -> dict:
    return {"result": None, "verified": False, "error": msg, "logs": [msg]}


def parse_project_name(text: str) -> str:
    m = re.search(r"project[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".")[:255]
    cleaned = re.sub(
        r"(?i)\b(create|add|new|a|an|the|project|banao|bana|karo|kar|start)\b", " ", text
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .:,-")
    return (cleaned or "Untitled project")[:255]


def _linked_counts(db: Session, project_id: str) -> dict[str, int]:
    counts = {s.value: 0 for s in TaskStatus}
    for status, count in (
        db.query(Task.status, func.count(Task.id)).filter(Task.project_id == project_id).group_by(Task.status).all()
    ):
        counts[status.value] = count
    return counts


class ProjectsAgent(BaseAgent):
    key = "projects"
    name = "Project Manager Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        op = context.get("operation", "list")
        handler = {"create": self._create, "list": self._list,
                   "progress": self._progress, "blockers": self._blockers}.get(op)
        if handler is None:
            return _fail(f"Projects agent does not support operation '{op}'.")
        return handler(db, task)

    def _create(self, db: Session, task: Task) -> dict:
        name = parse_project_name(task.description)
        project = Project(user_id=task.user_id, name=name, description=task.description, status="active")
        db.add(project)
        db.flush()
        saved = db.get(Project, project.id)
        if saved is None:
            return _fail("Project row could not be verified in the database.")
        result = f"Project created: '{saved.name}' (id: {saved.id}, status: active)."
        return {"result": result, "verified": True, "logs": [result]}

    def _list(self, db: Session, task: Task) -> dict:
        rows = (
            db.query(Project)
            .filter(Project.user_id == task.user_id)
            .order_by(Project.created_at.desc())
            .all()
        )
        if not rows:
            result = "No projects on record."
        else:
            lines = [f"Found {len(rows)} project(s):"]
            for p in rows:
                counts = _linked_counts(db, p.id)
                done = counts["COMPLETED"]
                total = sum(counts.values())
                lines.append(f"- {p.name} (status: {p.status}, linked tasks: {total}, completed: {done})")
            result = "\n".join(lines)
        return {"result": result, "verified": True, "logs": [f"Listed {len(rows)} project(s) from DB."]}

    def _progress(self, db: Session, task: Task) -> dict:
        rows = (
            db.query(Project)
            .filter(Project.user_id == task.user_id)
            .order_by(Project.created_at.desc())
            .all()
        )
        low = task.description.lower()
        named = [p for p in rows if p.name.lower() in low]
        if named:
            rows = named
        if not rows:
            result = "No projects on record, so there is no progress to report."
            return {"result": result, "verified": True, "logs": [result]}
        lines = ["Project progress (from real linked-task counts):"]
        for p in rows:
            counts = _linked_counts(db, p.id)
            total = sum(counts.values())
            pct = round(100 * counts["COMPLETED"] / total) if total else 0
            detail = ", ".join(f"{k}: {v}" for k, v in counts.items() if v)
            lines.append(f"- {p.name} (status: {p.status}): {pct}% complete" + (f" — {detail}" if detail else " — no linked tasks yet"))
        result = "\n".join(lines)
        return {"result": result, "verified": True, "logs": [f"Progress computed for {len(rows)} project(s) from linked tasks."]}

    def _blockers(self, db: Session, task: Task) -> dict:
        failed = (
            db.query(Task)
            .filter(Task.user_id == task.user_id, Task.status == TaskStatus.FAILED, Task.id != task.id)
            .order_by(Task.created_at.desc())
            .limit(5)
            .all()
        )
        oldest_pending = (
            db.query(Task)
            .filter(Task.user_id == task.user_id, Task.status == TaskStatus.PENDING, Task.id != task.id)
            .order_by(Task.created_at.asc())
            .limit(5)
            .all()
        )
        lines = ["Blockers (real, from the tasks table):"]
        if failed:
            lines.append("Failed tasks:")
            lines += [f"- [FAILED] {t.title} — {t.error or 'no error recorded'}" for t in failed]
        if oldest_pending:
            lines.append("Longest-waiting pending tasks:")
            lines += [f"- [PENDING since {t.created_at:%Y-%m-%d}] {t.title} (agent: {t.agent_key})" for t in oldest_pending]
        if not failed and not oldest_pending:
            lines.append("None — no failed tasks and no pending tasks waiting.")
        result = "\n".join(lines)
        return {"result": result, "verified": True,
                "logs": [f"Blockers read from DB: {len(failed)} failed, {len(oldest_pending)} oldest pending."]}
