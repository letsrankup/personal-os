"""Finance Agent — income/expense tracking on the `finance_entries` table.

Operations (parsed from the command text):
  add     — "kharcha 5000 khana" / "income 50000 salary" / "expense 1200 petrol":
            amount (first number), kind (expense/income keywords, EN + Roman
            Urdu) and category (keyword map) are parsed and a real row is
            inserted; verified by re-reading it.
  list    — list the user's recent entries.
  summary — totals by kind and by category for the CURRENT month, computed
            from the real rows (hisab).

The finance agent NEVER moves money: transfers/payments stay ALWAYS_MANUAL
and are refused by the orchestrator before this agent ever runs.
"""
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import FinanceEntry, Task
from .base import BaseAgent

_AMOUNT_RE = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)")
_EXPENSE_WORDS = ("kharcha", "kharch", "expense", "spent", "spend", "kharid", "paid for")
_INCOME_WORDS = ("income", "aamdani", "salary", "tankhwah", "received", "kamai", "earned")
_CATEGORY_WORDS = {
    "food": ("khana", "food", "khaana", "lunch", "dinner", "nashta", "restaurant", "grocer"),
    "transport": ("petrol", "fuel", "transport", "rickshaw", "bus", "taxi", "safar"),
    "rent": ("rent", "kiraya"),
    "utilities": ("bill", "bijli", "gas", "utility", "utilities", "internet"),
    "shopping": ("shopping", "kapre", "clothes"),
    "health": ("dawai", "medicine", "doctor", "health"),
    "salary": ("salary", "tankhwah"),
    "business": ("business", "client payment", "freelance"),
}


def _fail(msg: str) -> dict:
    return {"result": None, "verified": False, "error": msg, "logs": [msg]}


def parse_entry(text: str) -> dict | None:
    low = f" {text.lower()} "
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    amount = float(m.group(1).replace(",", ""))
    kind = "income" if any(w in low for w in _INCOME_WORDS) else "expense"
    if any(w in low for w in _EXPENSE_WORDS):
        kind = "expense"
    category = "general"
    for cat, words in _CATEGORY_WORDS.items():
        if any(w in low for w in words):
            category = cat
            break
    currency = "USD" if ("dollar" in low or " usd" in low or "$" in text) else "PKR"
    return {"kind": kind, "amount": amount, "category": category, "currency": currency}


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class FinanceAgent(BaseAgent):
    key = "finance"
    name = "Finance Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        low = f" {task.description.lower()} "
        if any(w in low for w in ("summary", "hisab", "total", "report")):
            return self._summary(db, task)
        if any(w in low for w in ("list", "dikhao", "show")) and not _AMOUNT_RE.search(task.description):
            return self._list(db, task)
        return self._add(db, task)

    def _add(self, db: Session, task: Task) -> dict:
        parsed = parse_entry(task.description)
        if parsed is None:
            return _fail(
                "Could not find an amount in the command, so no finance entry was recorded. "
                "Example: 'kharcha 5000 khana' or 'income 50000 salary'."
            )
        entry = FinanceEntry(
            user_id=task.user_id,
            kind=parsed["kind"],
            amount=parsed["amount"],
            currency=parsed["currency"],
            category=parsed["category"],
            note=task.description[:500],
        )
        db.add(entry)
        db.flush()
        saved = db.get(FinanceEntry, entry.id)
        if saved is None:
            return _fail("Finance entry could not be verified in the database.")
        result = (
            f"{saved.kind.capitalize()} recorded: {saved.amount:,.2f} {saved.currency} "
            f"(category: {saved.category}, id: {saved.id})."
        )
        return {"result": result, "verified": True, "logs": [result]}

    def _list(self, db: Session, task: Task) -> dict:
        rows = (
            db.query(FinanceEntry)
            .filter(FinanceEntry.user_id == task.user_id)
            .order_by(FinanceEntry.occurred_at.desc())
            .limit(20)
            .all()
        )
        if not rows:
            result = "No finance entries recorded yet."
        else:
            lines = [f"Latest {len(rows)} finance entr{'y' if len(rows) == 1 else 'ies'}:"]
            for e in rows:
                lines.append(
                    f"- {_as_utc(e.occurred_at):%Y-%m-%d} {e.kind} {e.amount:,.2f} {e.currency} ({e.category})"
                )
            result = "\n".join(lines)
        return {"result": result, "verified": True, "logs": [f"Listed {len(rows)} finance entr(ies) from DB."]}

    def _summary(self, db: Session, task: Task) -> dict:
        now = datetime.now(timezone.utc)
        rows = db.query(FinanceEntry).filter(FinanceEntry.user_id == task.user_id).all()
        month_rows = [e for e in rows if (_as_utc(e.occurred_at).year, _as_utc(e.occurred_at).month) == (now.year, now.month)]
        total_income = round(sum(e.amount for e in month_rows if e.kind == "income"), 2)
        total_expense = round(sum(e.amount for e in month_rows if e.kind == "expense"), 2)
        by_category: dict[str, float] = {}
        for e in month_rows:
            by_category[e.category] = round(by_category.get(e.category, 0.0) + e.amount, 2)
        currency = month_rows[0].currency if month_rows else "PKR"
        lines = [
            f"Finance summary for {now:%B %Y} (from {len(month_rows)} recorded entr{'y' if len(month_rows) == 1 else 'ies'}):",
            f"Total income: {total_income:,.2f} {currency}",
            f"Total expenses: {total_expense:,.2f} {currency}",
            f"Net: {total_income - total_expense:,.2f} {currency}",
        ]
        if by_category:
            lines.append("By category: " + ", ".join(f"{k}: {v:,.2f}" for k, v in sorted(by_category.items())))
        else:
            lines.append("No entries recorded this month yet.")
        result = "\n".join(lines)
        return {"result": result, "verified": True,
                "logs": [f"Summary computed from {len(month_rows)} real finance_entries row(s) for {now:%Y-%m}."]}
