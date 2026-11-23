"""Client Management Agent — real CRUD on the `clients` table.

Operations (context["operation"], set by the orchestrator's routing):
  add     — parse name (+ optional email / phone / company) from the command
            and insert a clients row; verified by re-reading it.
  list    — list all clients on record.
  find    — find clients whose name matches the name mentioned in the command.
  inquiry — record an inquiry/complaint against the client named in the
            command: it is categorized (complaint / question / other by
            keywords), appended to the client's notes + meta["inquiries"],
            and a follow-up task (agent_key=clients) is auto-created.
            Verified by re-reading both rows.

Clients are a single-owner personal register (the clients table has no
user_id by design), so no per-user filtering applies here.
"""
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Client, Task, TaskStatus
from .base import BaseAgent

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s-]{7,}\d")
_COMPLAINT_WORDS = ("complaint", "shikayat", "problem", "issue", "bad", "kharab", "late", "ghalat", "refund", "angry")
_QUESTION_WORDS = ("question", "sawal", "ask", "pooch", "?", "query", "inquiry", "maloomat")


def _fail(msg: str) -> dict:
    return {"result": None, "verified": False, "error": msg, "logs": [msg]}


def categorize(text: str) -> str:
    low = f" {text.lower()} "
    if any(w in low for w in _COMPLAINT_WORDS):
        return "complaint"
    if any(w in low for w in _QUESTION_WORDS):
        return "question"
    return "other"


def parse_new_client(text: str) -> dict:
    email_m = _EMAIL_RE.search(text)
    phone_m = _PHONE_RE.search(text)
    company = None
    cm = re.search(r"company[:\s]+([A-Za-z0-9][A-Za-z0-9 &.'-]*)", text, flags=re.IGNORECASE)
    if cm:
        company = cm.group(1).strip(" .,")
    name_part = re.sub(
        r"(?i)\b(add|client|clients|naya|new|karo|kar|please)\b", " ", text
    )
    if email_m:
        name_part = name_part.replace(email_m.group(0), " ")
    if phone_m:
        name_part = name_part.replace(phone_m.group(0), " ")
    if cm:
        name_part = name_part.replace(cm.group(0), " ")
    name = re.sub(r"\s+", " ", name_part).strip(" .:,-")
    return {
        "name": (name or "Unnamed client")[:255],
        "email": email_m.group(0) if email_m else None,
        "phone": phone_m.group(0).strip() if phone_m else None,
        "company": company,
    }


def _find_named_client(db: Session, text: str) -> Client | None:
    """The client whose name literally appears in the command text."""
    low = text.lower()
    for client in db.query(Client).order_by(Client.created_at.asc()).all():
        if client.name and client.name.lower() in low:
            return client
    return None


class ClientsAgent(BaseAgent):
    key = "clients"
    name = "Client Management Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        op = context.get("operation", "list")
        handler = {"add": self._add, "list": self._list, "find": self._find,
                   "inquiry": self._inquiry}.get(op)
        if handler is None:
            return _fail(f"Clients agent does not support operation '{op}'.")
        return handler(db, task)

    def _add(self, db: Session, task: Task) -> dict:
        data = parse_new_client(task.description)
        client = Client(name=data["name"], email=data["email"], phone=data["phone"],
                        company=data["company"], status="new")
        db.add(client)
        db.flush()
        saved = db.get(Client, client.id)
        if saved is None:
            return _fail("Client row could not be verified in the database.")
        extras = ", ".join(
            f"{k}: {v}" for k, v in (("email", saved.email), ("phone", saved.phone), ("company", saved.company)) if v
        )
        result = f"Client added: '{saved.name}' (id: {saved.id}, status: new" + (f", {extras}" if extras else "") + ")."
        return {"result": result, "verified": True, "logs": [result]}

    def _list(self, db: Session, task: Task) -> dict:
        rows = db.query(Client).order_by(Client.created_at.asc()).all()
        if not rows:
            result = "No clients on record."
        else:
            lines = [f"Found {len(rows)} client(s):"]
            for c in rows:
                lines.append(f"- {c.name} (status: {c.status}" + (f", company: {c.company}" if c.company else "") + (f", email: {c.email}" if c.email else "") + ")")
            result = "\n".join(lines)
        return {"result": result, "verified": True, "logs": [f"Listed {len(rows)} client(s) from DB."]}

    def _find(self, db: Session, task: Task) -> dict:
        client = _find_named_client(db, task.description)
        if client is None:
            # Fall back to a fragment search on the last words of the command.
            words = [w for w in re.findall(r"[A-Za-z]+", task.description) if len(w) > 2]
            for w in reversed(words):
                hit = db.query(Client).filter(Client.name.ilike(f"%{w}%")).first()
                if hit:
                    client = hit
                    break
        if client is None:
            return _fail(f"No client matching the command was found on record: '{task.description[:120]}'")
        result = (
            f"Client found: '{client.name}' (id: {client.id}, status: {client.status}"
            + (f", company: {client.company}" if client.company else "")
            + (f", email: {client.email}" if client.email else "")
            + (f", phone: {client.phone}" if client.phone else "") + ")."
        )
        if client.notes:
            result += f"\nNotes: {client.notes}"
        return {"result": result, "verified": True, "logs": [result]}

    def _inquiry(self, db: Session, task: Task) -> dict:
        client = _find_named_client(db, task.description)
        if client is None:
            return _fail(
                "Inquiry could not be recorded: no client named in the command matches a client on record. "
                "Add the client first."
            )
        category = categorize(task.description)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = {"category": category, "text": task.description, "recorded_at": stamp, "task_id": task.id}
        meta = dict(client.meta or {})
        meta["inquiries"] = [*(meta.get("inquiries") or []), entry]
        client.meta = meta
        note_line = f"[{stamp}] {category.upper()}: {task.description}"
        client.notes = f"{client.notes}\n{note_line}".strip() if client.notes else note_line
        if category == "complaint":
            client.status = "follow_up"
        follow = Task(
            user_id=task.user_id,
            agent_key="clients",
            title=f"Follow up with {client.name}: {category} inquiry",
            description=f"Auto-created follow-up for a {category} inquiry from client '{client.name}': {task.description}",
            status=TaskStatus.PENDING,
        )
        db.add(follow)
        db.flush()
        # Verify by re-reading both rows.
        saved_client = db.get(Client, client.id)
        saved_follow = db.get(Task, follow.id)
        if saved_client is None or saved_follow is None:
            return _fail("Inquiry could not be verified in the database.")
        inquiries = (saved_client.meta or {}).get("inquiries") or []
        if not inquiries or inquiries[-1]["text"] != task.description:
            return _fail("Inquiry was not persisted on the client record.")
        result = (
            f"Inquiry recorded for client '{saved_client.name}' — category: {category}. "
            f"Follow-up task created: '{saved_follow.title}' (id: {saved_follow.id}, status: PENDING)."
        )
        return {"result": result, "verified": True, "logs": [result]}
