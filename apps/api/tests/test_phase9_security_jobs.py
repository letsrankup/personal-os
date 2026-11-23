"""Phase 9: security hardening (rate limits, password policy, role gates,
login-failure audit) + scheduled report jobs."""
import uuid
from datetime import datetime, timedelta, timezone

from app.jobs import run_due_jobs
from app.models import Report, ScheduledJob, User
from app.security import create_access_token, hash_password


def _register(client, tag: str) -> tuple[str, dict]:
    email = f"p9-{tag}-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "password123", "name": "P9"})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    return email, {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_short_password_rejected_422(client):
    r = client.post("/auth/register", json={
        "email": f"p9-short-{uuid.uuid4().hex[:8]}@example.com",
        "password": "short",
        "name": "Short",
    })
    assert r.status_code == 422
    ok = client.post("/auth/register", json={
        "email": f"p9-eight-{uuid.uuid4().hex[:8]}@example.com",
        "password": "12345678",
        "name": "Eight",
    })
    assert ok.status_code == 201  # exactly 8 chars passes


def test_rate_limit_on_login_returns_429(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MIN", "5")
    email = f"p9-rl-{uuid.uuid4().hex[:8]}@example.com"
    # register consumes 1 of the 5 allowed auth calls
    assert client.post("/auth/register", json={
        "email": email, "password": "password123", "name": "RL"}).status_code == 201
    for _ in range(4):  # 4 more = 5 total, all fine
        assert client.post("/auth/login", json={
            "email": email, "password": "password123"}).status_code == 200
    blocked = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert blocked.status_code == 429
    assert "Rate limit exceeded" in blocked.json()["detail"]


def test_login_failure_is_audited(client):
    email, h = _register(client, "failaudit")
    bad = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert bad.status_code == 401
    activity = client.get("/activity", headers=h).json()
    assert any(a["action"] == "auth.login_failed" for a in activity)
    assert any(a["action"] == "auth.login" for a in activity)


def test_member_role_is_forbidden_from_owner_endpoints(client, db):
    member = User(email=f"p9-member-{uuid.uuid4().hex[:8]}@example.com",
                  name="Member", password_hash=hash_password("password123"), role="member")
    db.add(member)
    db.commit()
    mh = {"Authorization": f"Bearer {create_access_token(member.id)}"}
    assert client.get("/permissions", headers=mh).status_code == 403
    assert client.post("/integrations/github/check", headers=mh).status_code == 403
    # …but ordinary authenticated endpoints still work for a member
    assert client.get("/integrations", headers=mh).status_code == 200
    assert client.get("/activity", headers=mh).status_code == 200

    _, owner_h = _register(client, "ownerok")
    assert client.get("/permissions", headers=owner_h).status_code == 200
    assert client.post("/integrations/github/check", headers=owner_h).status_code == 200


def test_jobs_require_auth(client):
    assert client.get("/jobs").status_code == 401
    assert client.post("/jobs", json={"name": "x"}).status_code == 401


def test_job_crud_and_manual_run_creates_real_report(client, db):
    _, h = _register(client, "jobs")
    name = f"Manual summary {uuid.uuid4().hex[:6]}"
    r = client.post("/jobs", headers=h, json={
        "name": name, "kind": "report", "report_kind": "summary", "interval": "daily"})
    assert r.status_code == 201
    job = r.json()
    assert job["next_run_at"] is not None and job["enabled"] is True

    before = db.query(Report).filter_by(kind="summary").count()
    run = client.post(f"/jobs/{job['id']}/run", headers=h)
    assert run.status_code == 200
    assert run.json()["executed"] is True
    assert run.json()["report_id"] is not None
    assert run.json()["last_run_at"] is not None
    db.expire_all()
    assert db.query(Report).filter_by(kind="summary").count() == before + 1
    report = db.get(Report, run.json()["report_id"])
    assert report is not None and "Tasks total:" in report.content

    listed = client.get("/jobs", headers=h).json()
    assert any(j["id"] == job["id"] for j in listed)

    dup = client.post("/jobs", headers=h, json={"name": name, "kind": "report"})
    assert dup.status_code == 409

    assert client.delete(f"/jobs/{job['id']}", headers=h).status_code == 204
    assert client.get("/jobs", headers=h).json() == [
        j for j in client.get("/jobs", headers=h).json() if j["id"] != job["id"]
    ]


def test_run_due_jobs_executes_and_advances_schedule(client, db):
    _, h = _register(client, "due")
    me = client.get("/auth/me", headers=h).json()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    job = ScheduledJob(
        name=f"Due daily {uuid.uuid4().hex[:6]}",
        kind="report",
        schedule={"interval": "daily"},
        payload={"report_kind": "daily", "user_id": me["id"]},
        enabled=True,
        next_run_at=past,
    )
    db.add(job)
    db.commit()

    before = db.query(Report).filter_by(kind="daily").count()
    results = run_due_jobs(db, datetime.now(timezone.utc))
    mine = [r for r in results if r["job_id"] == job.id]
    assert len(mine) == 1 and mine[0]["error"] is None and mine[0]["report_id"]
    db.expire_all()
    assert db.query(Report).filter_by(kind="daily").count() == before + 1
    refreshed = db.get(ScheduledJob, job.id)
    assert refreshed.last_run_at is not None
    nxt = refreshed.next_run_at
    if nxt.tzinfo is None:  # SQLite reads back naive — normalize for comparison
        nxt = nxt.replace(tzinfo=timezone.utc)
    assert nxt > datetime.now(timezone.utc)  # advanced ~1 day out

    # not due anymore → a second sweep runs nothing for this job
    results2 = run_due_jobs(db, datetime.now(timezone.utc))
    assert all(r["job_id"] != job.id for r in results2)


def test_one_off_job_disables_after_run(client, db):
    _, h = _register(client, "once")
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    r = client.post("/jobs", headers=h, json={
        "name": f"One off {uuid.uuid4().hex[:6]}", "kind": "report",
        "report_kind": "weekly", "run_at": past})
    assert r.status_code == 201
    job_id = r.json()["id"]
    results = run_due_jobs(db, datetime.now(timezone.utc))
    assert any(x["job_id"] == job_id and x["report_id"] for x in results)
    db.expire_all()
    job = db.get(ScheduledJob, job_id)
    assert job.enabled is False and job.next_run_at is None
