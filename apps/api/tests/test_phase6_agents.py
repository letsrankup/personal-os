"""Phase 6 tests: the eight real specialist agents.

All tests run offline (AI_PROVIDER forced to the offline provider) and the
research tests monkeypatch httpx, so nothing depends on the live network.
Every assertion is against real DB rows or real files on disk.
"""
import uuid

import httpx
import pytest

from app.models import Client, FinanceEntry, Memory, Report, Task


def _auth(client) -> dict:
    email = f"p6-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "password123", "name": "P6"})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _cmd(client, h, text) -> dict:
    r = client.post("/commands", json={"text": text}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(autouse=True)
def _offline_ai(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_provider", "offline")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)


# ---------------------------------------------------------------- research
_DDG_HTML = """
<html><body>
<div class="result"><a class="result__a" href="https://example.com/solar-guide">Solar Guide Pakistan</a>
<a class="result__snippet" href="#">Solar panels cost guide for Pakistan homes.</a></div>
<div class="result"><a class="result__a" href="https://example.com/solar-prices">Solar Prices</a>
<a class="result__snippet" href="#">Latest solar panel prices and net metering.</a></div>
</body></html>
"""
_PAGE_HTML = "<html><head><title>Solar</title></head><body><p>Solar panels in Pakistan: full guide text.</p></body></html>"


def _fake_httpx_get(url, **kwargs):
    request = httpx.Request("GET", str(url))
    if "duckduckgo" in str(url):
        return httpx.Response(200, text=_DDG_HTML, request=request)
    return httpx.Response(200, text=_PAGE_HTML, request=request)


def test_research_real_pipeline_saves_memory(client, db, monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_httpx_get)
    h = _auth(client)
    me = client.get("/auth/me", headers=h).json()
    body = _cmd(client, h, "Research solar panels in Pakistan")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "research"
    assert "example.com/solar-guide" in body["reply"]  # real source list
    assert "Sources:" in body["reply"]
    saved = (
        db.query(Memory)
        .filter(Memory.user_id == me["id"], Memory.kind == "research")
        .all()
    )
    assert saved and "solar" in saved[0].title.lower()
    assert any("example.com/solar-prices" in (t or "") for t in (saved[0].tags or []))


# ------------------------------------------------------------ communication
def test_communication_draft_saved_not_sent(client, db):
    h = _auth(client)
    me = client.get("/auth/me", headers=h).json()
    body = _cmd(client, h, "Draft email to Sara about the project update")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "communication"
    assert "has NOT been sent" in body["reply"]
    drafts = (
        db.query(Memory)
        .filter(Memory.user_id == me["id"], Memory.kind == "file_ref")
        .all()
    )
    assert drafts and "Sara" in drafts[0].title
    assert "email_draft" in (drafts[0].tags or [])


# ------------------------------------------------------------------ clients
def _unique_client_name() -> str:
    return "Testclient " + "".join(c for c in uuid.uuid4().hex[:8] if c.isalpha() or c.isdigit())


def test_clients_add_list_find(client):
    h = _auth(client)
    name = _unique_client_name()
    body = _cmd(client, h, f"Add client {name}")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "clients"
    assert name in body["reply"]

    body = _cmd(client, h, "Clients list karo")
    assert body["status"] == "COMPLETED"
    assert name in body["reply"]

    body = _cmd(client, h, f"Find client {name}")
    assert body["status"] == "COMPLETED"
    assert name in body["reply"]


def test_clients_inquiry_creates_followup_task(client, db):
    h = _auth(client)
    name = _unique_client_name()
    _cmd(client, h, f"Add client {name}")
    body = _cmd(client, h, f"Client {name} complaint: delivery was late")
    assert body["status"] == "COMPLETED"
    assert "complaint" in body["reply"]
    assert "Follow-up task created" in body["reply"]
    follow = db.query(Task).filter(Task.title.like(f"Follow up with {name}%")).all()
    assert len(follow) == 1
    saved_client = db.query(Client).filter(Client.name == name).first()
    inquiries = (saved_client.meta or {}).get("inquiries") or []
    assert inquiries and inquiries[-1]["category"] == "complaint"
    assert "COMPLAINT" in saved_client.notes


# ----------------------------------------------------------------- business
def test_business_plan_saved_as_report(client, db):
    h = _auth(client)
    before = db.query(Report).filter(Report.kind == "business").count()
    body = _cmd(client, h, "Business plan for a coffee shop in Lahore")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "business"
    assert "estimate" in body["reply"].lower()  # figures labelled as estimates
    db.expire_all()
    assert db.query(Report).filter(Report.kind == "business").count() == before + 1


# ---------------------------------------------------------------- developer
def test_developer_creates_real_website_files(client, monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "agent_workspace_dir", str(tmp_path))
    h = _auth(client)
    body = _cmd(client, h, "Website banao for a bakery")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "developer"
    site = tmp_path / "bakery"
    index = site / "index.html"
    assert index.is_file() and (site / "style.css").is_file() and (site / "script.js").is_file()
    html = index.read_text(encoding="utf-8")
    assert "<html" in html.lower() and "<title>" in html.lower()

    body = _cmd(client, h, "Review project files")
    assert body["status"] == "COMPLETED"
    assert "bakery" in body["reply"]


# ------------------------------------------------------------------ finance
def test_finance_add_and_summary_math(client, db):
    h = _auth(client)
    me = client.get("/auth/me", headers=h).json()
    body = _cmd(client, h, "Kharcha 5000 khana")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "finance"
    assert "Expense recorded: 5,000.00 PKR" in body["reply"]
    body = _cmd(client, h, "Income 50000 salary")
    assert body["status"] == "COMPLETED"
    assert "Income recorded: 50,000.00 PKR" in body["reply"]

    rows = db.query(FinanceEntry).filter(FinanceEntry.user_id == me["id"]).all()
    assert len(rows) == 2
    assert sum(r.amount for r in rows if r.kind == "income") == 50000.0
    assert sum(r.amount for r in rows if r.kind == "expense") == 5000.0
    assert {r.category for r in rows} == {"food", "salary"}

    body = _cmd(client, h, "Hisab dikhao")
    assert body["status"] == "COMPLETED"
    assert "Total income: 50,000.00" in body["reply"]
    assert "Total expenses: 5,000.00" in body["reply"]
    assert "Net: 45,000.00" in body["reply"]


# ---------------------------------------------------------------- marketing
def test_marketing_plan_drafts_only(client, db):
    h = _auth(client)
    before = db.query(Report).filter(Report.kind == "marketing").count()
    body = _cmd(client, h, "Marketing aur SEO plan for my bakery")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "marketing"
    assert "nothing was published" in body["reply"]
    db.expire_all()
    assert db.query(Report).filter(Report.kind == "marketing").count() == before + 1


# ----------------------------------------------------------------- projects
def test_projects_create_list_progress(client):
    h = _auth(client)
    name = "Proj" + uuid.uuid4().hex[:6]
    body = _cmd(client, h, f"Create project {name}")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "projects"
    assert name in body["reply"]

    body = _cmd(client, h, "List projects")
    assert body["status"] == "COMPLETED"
    assert name in body["reply"]

    body = _cmd(client, h, "Project progress dikhao")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "projects"
    assert name in body["reply"]
    assert "complete" in body["reply"]


def test_projects_blockers_from_real_tasks(client):
    h = _auth(client)
    _cmd(client, h, "Create a task to be a blocker")
    body = _cmd(client, h, "Blockers dikhao")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "projects"
    assert "Blockers" in body["reply"]
    assert "be a blocker" in body["reply"]


# ------------------------------------------------------- tasks priority/due
def test_task_create_priority_and_deadline_parsing(client, db):
    h = _auth(client)
    body = _cmd(client, h, "Create a task to finish the deck tomorrow, bohat zaroori hai")
    assert body["status"] == "COMPLETED"
    assert "priority: HIGH" in body["reply"]
    assert "due:" in body["reply"]
    from app.models import TaskStatus

    created = db.query(Task).filter(
        Task.title.like("%finish the deck%"), Task.status == TaskStatus.PENDING
    ).all()
    assert len(created) == 1
    assert created[0].priority.value == "HIGH"
    assert created[0].due_at is not None

    body = _cmd(client, h, "Create a task to submit the form by 2027-01-15")
    assert body["status"] == "COMPLETED"
    created = db.query(Task).filter(
        Task.title.like("%submit the form%"), Task.status == TaskStatus.PENDING
    ).all()
    assert len(created) == 1
    assert created[0].due_at is not None
    assert created[0].due_at.year == 2027 and created[0].due_at.month == 1 and created[0].due_at.day == 15


# ---------------------------------------------------------------- reporting
def test_reporting_daily_period(client, db):
    h = _auth(client)
    body = _cmd(client, h, "Daily report banao")
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "reporting"
    assert "daily report" in body["reply"]
    latest = db.query(Report).filter(Report.kind == "daily").order_by(Report.created_at.desc()).first()
    assert latest is not None
    assert latest.period_start is not None and latest.period_end is not None
