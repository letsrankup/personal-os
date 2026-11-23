"""Scheduled jobs (Phase 9) — the `scheduled_jobs` table made real.

A job with kind="report" runs the Reporting Agent, which creates a real
`reports` row from live DB counts (never a fabricated one). Jobs are due
when `enabled` is true and `next_run_at <= now`. After a run:

- interval "daily"  → next_run_at advances by 1 day (past slots skipped)
- interval "weekly" → next_run_at advances by 7 days (past slots skipped)
- interval "once" (created with an explicit run_at) → job disabled

Every execution is written to `activity_logs`. The FastAPI app calls
`run_due_jobs` from a background loop every 60 seconds; tests and the
manual-run endpoint call the same functions directly.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .agents import get_agent
from .deps import log_activity
from .models import ScheduledJob, Task

_INTERVAL_DELTAS = {"daily": timedelta(days=1), "weekly": timedelta(days=7)}
REPORT_KINDS = ("summary", "daily", "weekly")


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _advance(job: ScheduledJob, now: datetime) -> datetime | None:
    """Next run time after `now`, or None for one-off jobs."""
    delta = _INTERVAL_DELTAS.get((job.schedule or {}).get("interval", ""))
    if delta is None:
        return None
    nxt = _as_utc(job.next_run_at) if job.next_run_at else now
    nxt = nxt + delta
    while nxt <= now:  # skip slots missed while the app was down
        nxt += delta
    return nxt


def execute_job(db: Session, job: ScheduledJob, now: datetime | None = None) -> dict:
    """Execute one job now. Caller commits. Returns an execution summary."""
    now = now or datetime.now(timezone.utc)
    payload = job.payload or {}
    summary: dict = {"job_id": job.id, "name": job.name, "kind": job.kind, "report_id": None, "error": None}

    if job.kind == "report":
        report_kind = payload.get("report_kind", "summary")
        if report_kind not in REPORT_KINDS:
            report_kind = "summary"
        # The reporting agent only needs a task carrying the owner's id;
        # it builds the report from live DB counts and stores a real row.
        carrier = Task(
            user_id=payload.get("user_id"),
            agent_key="reporting",
            title=f"Scheduled {report_kind} report",
            description=f"Scheduled {report_kind} report (job: {job.name})",
        )
        result = get_agent("reporting").run(
            db, carrier, {"params": {"kind": report_kind}, "command": carrier.description}
        )
        if result.get("verified") and result.get("report_id"):
            summary["report_id"] = result["report_id"]
        else:
            summary["error"] = result.get("error") or "Reporting agent did not produce a verified report."
    else:
        summary["error"] = f"Job kind '{job.kind}' is not supported yet — nothing was executed."

    job.last_run_at = now
    nxt = _advance(job, now)
    if nxt is None:
        job.enabled = False
        job.next_run_at = None
    else:
        job.next_run_at = nxt
    db.flush()

    log_activity(
        db,
        "job.executed" if summary["error"] is None else "job.failed",
        actor="system",
        user_id=payload.get("user_id"),
        entity="scheduled_jobs",
        entity_id=job.id,
        details={"name": job.name, "kind": job.kind,
                 "report_id": summary["report_id"], "error": summary["error"]},
    )
    return summary


def run_due_jobs(db: Session, now: datetime | None = None) -> list[dict]:
    """Execute every enabled job whose next_run_at has passed. Commits."""
    now = now or datetime.now(timezone.utc)
    due = [
        job
        for job in db.query(ScheduledJob).filter_by(enabled=True).all()
        if job.next_run_at is not None and _as_utc(job.next_run_at) <= now
    ]
    results = [execute_job(db, job, now) for job in due]
    db.commit()
    return results
