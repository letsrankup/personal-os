"""Master Agent — the orchestrator's own agent face.

The full pipeline lives in app/orchestrator.py. When a task is assigned to
the master directly (a general question/command with no specialist route),
the master answers it through the AI provider layer (app/ai.py) and cites
any memory hits the orchestrator put in the context.
"""
from sqlalchemy.orm import Session

from .. import ai
from ..models import Task
from .base import BaseAgent

SYSTEM_PROMPT = (
    "You are PERSONAL OS, a private personal AI employee. Answer helpfully and "
    "concisely in the user's language (English or Roman Urdu). Never invent "
    "facts, clients, emails or results you do not have."
)


class MasterAgent(BaseAgent):
    key = "master"
    name = "Master Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        memories = context.get("memories", [])
        prompt = task.description
        if memories:
            notes = "\n".join(f"- {m['title']}: {m['content'][:200]}" for m in memories)
            prompt = f"Relevant saved memory:\n{notes}\n\nUser command: {task.description}"
        reply = ai.chat(prompt, system=SYSTEM_PROMPT)
        verified = bool(reply and reply.strip())
        return {
            "result": reply if verified else None,
            "verified": verified,
            "error": None if verified else "AI provider returned an empty answer.",
            "logs": [f"Answered via AI provider '{ai.provider_name()}' with {len(memories)} memory hit(s) in context."],
        }
