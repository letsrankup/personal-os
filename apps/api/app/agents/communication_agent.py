"""Communication Agent — email DRAFTS only (Phase 6).

Storage choice (documented): a draft is stored as a `memories` row with
kind="file_ref", title "Email draft to <name>: <topic>", the full draft text
in content, and tags ["email_draft", <recipient>]. The memories table is the
user-visible document store until the Phase 7 file UI lands.

Sending is a separate, APPROVAL_REQUIRED action (seeded permission
email.send_external). Gmail is not connected until Phase 8, so when an
approved send reaches this agent it returns FAILED with the exact reason
"Gmail integration not connected" — it never pretends an email was sent.
Reading the inbox fails honestly for the same reason.
"""
import re

from sqlalchemy.orm import Session

from .. import ai
from ..models import Memory, Task
from .base import BaseAgent

GMAIL_NOT_CONNECTED = (
    "Gmail integration not connected — sending email becomes possible only after "
    "the Gmail integration is connected in Phase 8. Nothing was sent."
)


def parse_draft_request(text: str) -> tuple[str, str]:
    """'draft email to <name> about <topic>' -> (name, topic)."""
    m = re.search(r"\bto\s+(.+?)\s+about\s+(.+)", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip(" .,"), m.group(2).strip().rstrip(".")
    m = re.search(r"\bto\s+(.+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip(" .,"), text.strip()
    return "the recipient", text.strip()


class CommunicationAgent(BaseAgent):
    key = "communication"
    name = "Communication Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        op = context.get("operation", "draft")
        if op == "run" and task.permission_tier is not None and task.permission_tier.value == "APPROVAL_REQUIRED":
            op = "send"  # an approved email.send_external task arriving without an explicit operation
        if op == "send":
            return {"result": None, "verified": False, "error": GMAIL_NOT_CONNECTED,
                    "logs": [GMAIL_NOT_CONNECTED]}
        if op == "inbox":
            msg = (
                "Gmail integration not connected — reading the inbox becomes possible "
                "only after the Gmail integration is connected in Phase 8. No emails were read."
            )
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        if op != "draft":
            msg = f"Communication agent does not support operation '{op}'."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}

        name, topic = parse_draft_request(task.description)
        draft = ai.chat(
            f"Write a short, professional email draft to {name} about: {topic}. "
            "Include a subject line. Output only the draft.",
            system="You are the PERSONAL OS Communication Agent. Draft emails only; never claim an email was sent.",
        )
        if not draft or not draft.strip():
            msg = "AI provider returned an empty draft."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}

        row = Memory(
            user_id=task.user_id,
            kind="file_ref",
            title=f"Email draft to {name}: {topic}"[:255],
            content=draft,
            tags=["email_draft", name],
            source_ref=task.id,
        )
        db.add(row)
        db.flush()
        saved = db.get(Memory, row.id)  # verify the draft really landed
        if saved is None or saved.content != draft:
            msg = "Email draft could not be verified in the database."
            return {"result": None, "verified": False, "error": msg, "logs": [msg]}
        result = (
            f"Email draft prepared for {name} (topic: {topic}) and saved as memory {saved.id}. "
            f"It has NOT been sent — sending needs your approval and the Gmail integration (Phase 8).\n\n{draft}"
        )
        return {"result": result, "verified": True,
                "logs": [f"Draft generated via AI provider '{ai.provider_name()}' and stored as file_ref memory {saved.id}."]}
