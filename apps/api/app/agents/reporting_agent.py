"""Reporting Agent — builds reports from REAL database counts and stores
them as `reports` rows. Never reports planned work as done: counts come
straight from the tasks/projects/clients tables.

Report kinds (context["params"]["kind"]):
  summary — all-time counts (no period filter)
  daily   — only tasks created today (UTC), period_start/end stored
  weekly  — only tasks created in the last 7 days, period_start/end stored
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import ActivityLog, Agent, Client, Project, Report, Task, TaskStatus
from .base import BaseAgent


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class ReportingAgent(BaseAgent):
    key = "reporting"
    name = "Reporting Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        kind = context.get("params", {}).get("kind", "summary")
        now = datetime.now(timezone.utc)
        period_start = period_end = None
        if kind == "daily":
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = now
        elif kind == "weekly":
            period_start = now - timedelta(days=7)
            period_end = now

        status_counts = {s.value: 0 for s in TaskStatus}
        task_rows = (
            db.query(Task.status, Task.created_at).filter(Task.user_id == task.user_id).all()
        )
        for status, created_at in task_rows:
            if period_start is not None and not (period_start <= _as_utc(created_at) <= period_end):
                continue
            status_counts[status.value] += 1
        total_tasks = sum(status_counts.values())
        active_agents = db.query(func.count(Agent.id)).filter(Agent.status != "disabled").scalar() or 0
        projects_in_progress = (
            db.query(func.count(Project.id))
            .filter(Project.user_id == task.user_id, Project.status == "active")
            .scalar()
            or 0
        )
        total_clients = db.query(func.count(Client.id)).scalar() or 0
        recent = (
            db.query(ActivityLog)
            .filter(ActivityLog.user_id == task.user_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(5)
            .all()
        )

        data = {
            "tasks_by_status": status_counts,
            "total_tasks": total_tasks,
            "active_agents": active_agents,
            "projects_in_progress": projects_in_progress,
            "total_clients": total_clients,
            "recent_activity": [r.action for r in recent],
        }
        if period_start is not None:
            data["period_start"] = period_start.isoformat()
            data["period_end"] = period_end.isoformat()
        period_label = {
            "daily": f"daily report for {now:%Y-%m-%d}",
            "weekly": f"weekly report ({period_start:%Y-%m-%d} to {now:%Y-%m-%d})" if period_start else "weekly report",
        }.get(kind, "summary report")
        lines = [
            f"PERSONAL OS {period_label} — {now:%Y-%m-%d %H:%M UTC}",
            f"Tasks total: {total_tasks} "
            + "("
            + ", ".join(f"{k}: {v}" for k, v in status_counts.items())
            + ")",
            f"Active agents: {active_agents}",
            f"Projects in progress: {projects_in_progress}",
            f"Clients on record: {total_clients}",
            "Recent activity: " + (", ".join(data["recent_activity"]) if recent else "none recorded"),
        ]
        content = "\n".join(lines)

        report = Report(kind=kind, title=f"{kind.capitalize()} Report — {now:%Y-%m-%d %H:%M UTC}",
                        content=content, data=data, period_start=period_start, period_end=period_end)
        db.add(report)
        db.flush()
        saved = db.get(Report, report.id)  # verify the row really landed
        if saved is None:
            msg = "Report row could not be verified in the database."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        return {
            "result": content,
            "verified": True,
            "logs": [f"Report row {saved.id} created from live DB counts."],
            "report_id": saved.id,
        }
