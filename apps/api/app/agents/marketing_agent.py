"""Marketing Agent — SEO keywords, content plan and social post DRAFTS.

Everything is produced via the AI provider chain from the topic/business in
the command and saved as a `reports` row (kind="marketing"), verified by
re-reading it. Publishing is NOT performed: no social integration is
connected, so the output is drafts only and the result says so plainly.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import ai
from ..models import Report, Task
from .base import BaseAgent

DRAFTS_NOTICE = (
    "Drafts only — nothing was published. No social-media integration is connected, "
    "so these posts are saved for your review, not posted anywhere."
)


class MarketingAgent(BaseAgent):
    key = "marketing"
    name = "Marketing Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        topic = task.description.strip()
        prompt = (
            f"Marketing request: {topic}\n\n"
            "Produce: 1) a list of SEO keyword ideas, 2) a short content plan "
            "(topics + cadence), 3) exactly 3 ready-to-post social media drafts."
        )
        plan = ai.chat(
            prompt,
            system="You are the PERSONAL OS Marketing Agent. Create practical SEO and content plans and social media drafts. Never claim anything was published.",
        )
        if not plan or not plan.strip():
            msg = "AI provider returned an empty marketing plan."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}

        now = datetime.now(timezone.utc)
        content = f"Marketing plan — {topic[:120]}\n\n{plan}\n\n{DRAFTS_NOTICE}"
        report = Report(
            kind="marketing",
            title=f"Marketing Plan — {now:%Y-%m-%d %H:%M UTC}",
            content=content,
            data={"request": topic, "published": False},
        )
        db.add(report)
        db.flush()
        saved = db.get(Report, report.id)
        if saved is None:
            msg = "Marketing report row could not be verified in the database."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        result = f"{content}\n\n(Saved as report {saved.id}.)"
        return {"result": result, "verified": True,
                "logs": [f"Marketing plan + drafts generated via AI provider '{ai.provider_name()}'; report row {saved.id} verified. Nothing published."],
                "report_id": saved.id}
