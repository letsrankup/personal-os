"""Phase 3–5 tests: command pipeline, permissions/approvals, AI layer."""
import uuid

import pytest

from app.models import Report, Task, TaskStatus


def _auth(client) -> dict:
    email = f"cmd-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "password123", "name": "Cmd"})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_endpoints_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/memories").status_code == 401
    assert client.get("/overview").status_code == 401
    assert client.post("/commands", json={"text": "hi"}).status_code == 401


def test_command_create_task_completes(client, db):
    h = _auth(client)
    r = client.post("/commands", json={"text": "Create a task to test the system"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "tasks"
    assert "test the system" in body["reply"]

    detail = client.get(f"/tasks/{body['task_id']}", headers=h)
    assert detail.status_code == 200
    d = detail.json()
    assert d["status"] == "COMPLETED"
    assert d["verified"] is True
    assert d["result"]
    assert len(d["steps"]) == 5
    assert all(s["status"] == "COMPLETED" for s in d["steps"])

    # The tasks agent created a real PENDING sub-task row.
    created = db.query(Task).filter(Task.title == "test the system").all()
    assert len(created) == 1
    assert created[0].status == TaskStatus.PENDING


def test_command_list_tasks_roman_urdu(client):
    h = _auth(client)
    client.post("/commands", json={"text": "Create a task to buy milk"}, headers=h)
    r = client.post("/commands", json={"text": "Meri pending tasks list karo"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "tasks"
    assert "buy milk" in body["reply"]


def test_report_command_creates_report_row(client, db):
    h = _auth(client)
    before = db.query(Report).count()
    r = client.post("/commands", json={"text": "Generate a summary report"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "reporting"
    assert "Tasks total:" in body["reply"]
    db.expire_all()
    assert db.query(Report).count() == before + 1
    latest = db.query(Report).order_by(Report.created_at.desc()).first()
    assert latest.kind == "summary"
    assert latest.data["total_tasks"] >= 1


def test_approval_required_flow_executes_after_approval(client, db):
    h = _auth(client)
    before = db.query(Report).count()
    r = client.post("/commands", json={"text": "Publish a summary report"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "WAITING_FOR_APPROVAL"
    assert body["approval_id"]
    db.expire_all()
    assert db.query(Report).count() == before  # nothing executed yet

    pending = client.get("/approvals", headers=h)
    assert pending.status_code == 200
    assert any(a["id"] == body["approval_id"] for a in pending.json())

    decided = client.post(
        f"/approvals/{body['approval_id']}/decide", json={"decision": "approved"}, headers=h
    )
    assert decided.status_code == 200, decided.text
    out = decided.json()
    assert out["task_status"] == "COMPLETED"
    assert out["result"] and "Tasks total:" in out["result"]
    db.expire_all()
    assert db.query(Report).count() == before + 1  # held work really ran


def test_approval_rejection_cancels_task(client):
    h = _auth(client)
    r = client.post("/commands", json={"text": "Publish a summary report"}, headers=h)
    body = r.json()
    decided = client.post(
        f"/approvals/{body['approval_id']}/decide", json={"decision": "rejected"}, headers=h
    )
    assert decided.status_code == 200
    assert decided.json()["task_status"] == "CANCELLED"
    detail = client.get(f"/tasks/{body['task_id']}", headers=h).json()
    assert detail["status"] == "CANCELLED"
    assert "never executed" in detail["error"]


def test_send_email_holds_for_approval_then_fails_honestly(client):
    """email.send_external is APPROVAL_REQUIRED; after approval the Phase-6
    communication agent fails honestly — Gmail is not connected until
    Phase 8, so the task is FAILED, never a fake send."""
    h = _auth(client)
    r = client.post("/commands", json={"text": "Send email to the client about the invoice"}, headers=h)
    body = r.json()
    assert body["status"] == "WAITING_FOR_APPROVAL"
    decided = client.post(
        f"/approvals/{body['approval_id']}/decide", json={"decision": "approved"}, headers=h
    )
    out = decided.json()
    assert out["task_status"] == "FAILED"
    assert "Gmail integration not connected" in out["error"]


@pytest.mark.parametrize(
    "text",
    ["Transfer 5000 rupees to Ahmed", "Ahmed ko 5000 rupay transfer karo", "Send money to my brother"],
)
def test_always_manual_actions_refused(client, text):
    h = _auth(client)
    r = client.post("/commands", json={"text": text}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "CANCELLED"
    assert "ALWAYS_MANUAL" in body["reply"]
    detail = client.get(f"/tasks/{body['task_id']}", headers=h).json()
    assert detail["status"] == "CANCELLED"
    assert detail["verified"] is False


def test_research_fails_honestly_without_network(client, monkeypatch):
    """Phase 6: the research agent is real — with the network blocked it
    returns FAILED with the real error, never fabricated results."""
    import httpx

    def _blocked(*args, **kwargs):
        raise httpx.ConnectError("network blocked in test")

    monkeypatch.setattr(httpx, "get", _blocked)
    h = _auth(client)
    r = client.post("/commands", json={"text": "Research the market for electric bikes"}, headers=h)
    body = r.json()
    assert body["status"] == "FAILED"
    assert body["agent"] == "research"
    assert "Web search failed" in body["reply"]
    assert "not yet implemented" not in body["reply"]


def test_general_command_offline_ai(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_provider", "offline")
    h = _auth(client)
    r = client.post("/commands", json={"text": "What is the capital of France?"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["agent"] == "master"
    assert "Offline AI mode" in body["reply"]


def test_conversation_and_messages_persisted(client):
    h = _auth(client)
    r = client.post("/commands", json={"text": "Create a task to check persistence"}, headers=h)
    conv_id = r.json()["conversation_id"]
    convs = client.get("/conversations", headers=h).json()
    assert any(c["id"] == conv_id for c in convs)
    msgs = client.get(f"/conversations/{conv_id}/messages", headers=h).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "Create a task to check persistence"
    # A conversation_summary memory was saved by the pipeline.
    mems = client.get("/memories", params={"kind": "conversation_summary"}, headers=h).json()
    assert any("check persistence" in m["content"] or "check persistence" in m["title"] for m in mems)


def test_tasks_filter_and_cancel(client):
    h = _auth(client)
    client.post("/commands", json={"text": "Create a task to be cancelled"}, headers=h)
    pending = client.get("/tasks", params={"status": "PENDING"}, headers=h).json()
    target = next(t for t in pending if t["title"] == "be cancelled")
    cancelled = client.post(f"/tasks/{target['id']}/cancel", headers=h)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    again = client.post(f"/tasks/{target['id']}/cancel", headers=h)
    assert again.status_code == 409
    by_agent = client.get("/tasks", params={"agent": "tasks"}, headers=h).json()
    assert by_agent and all(t["agent_key"] == "tasks" for t in by_agent)
    assert client.get("/tasks", params={"status": "NOPE"}, headers=h).status_code == 400


def test_agents_and_overview(client):
    h = _auth(client)
    agents = client.get("/agents", headers=h).json()
    assert len(agents) == 11
    assert {a["key"] for a in agents} >= {"master", "tasks", "reporting"}
    client.post("/commands", json={"text": "Create a task for the overview"}, headers=h)
    ov = client.get("/overview", headers=h).json()
    assert ov["total_tasks"] >= 2  # orchestrator task + created sub-task
    assert ov["completed_tasks"] >= 1
    assert ov["active_agents"] == 11
    assert "tasks_by_status" in ov and "recent_activity" in ov and "latest_reports" in ov


def test_ai_layer_offline_and_provider_name(monkeypatch):
    from app import ai
    from app.config import settings

    monkeypatch.setattr(settings, "ai_provider", "offline")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    assert ai.provider_name() == "offline"
    out = ai.chat("Hello, what can you do?")
    assert "Offline AI mode" in out
    assert "Hello, what can you do?" in out

    monkeypatch.setattr(settings, "ai_provider", None)
    assert ai.provider_name() == "pollinations"  # free no-key fallback is next
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-not-real")
    assert ai.provider_name() == "openai"
