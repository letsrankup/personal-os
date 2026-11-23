"""Agent interface.

Every specialist agent implements `run(db, task, context) -> dict` with keys:
  result   — human-readable result text (or None on failure)
  verified — True ONLY when the agent confirmed its own result against the DB
  logs     — list of short execution log strings
  error    — error text when the run failed (optional)

Agents must never fabricate results: a "not implemented" agent returns
verified=False with an explicit error instead of a fake success.
"""
from sqlalchemy.orm import Session

from ..models import Task


class BaseAgent:
    key: str = "base"
    name: str = "Base Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        raise NotImplementedError


class NotImplementedAgent(BaseAgent):
    """Placeholder for specialists that arrive in Phase 6.

    Returns a FAILED, unverified result — it never pretends to have done work.
    """

    def __init__(self, key: str, name: str):
        self.key = key
        self.name = name

    def run(self, db: Session, task: Task, context: dict) -> dict:
        msg = (
            f"Agent '{self.key}' ({self.name}) is not yet implemented — "
            "it arrives in Phase 6. No work was performed and nothing was fabricated."
        )
        return {"result": None, "verified": False, "error": msg, "logs": [msg]}
