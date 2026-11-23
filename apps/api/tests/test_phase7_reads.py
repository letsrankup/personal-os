"""Phase 7 read endpoints: projects, clients, files, reports, integrations,
permissions, activity — all JWT-protected, real rows only."""
import uuid

from app.models import Client, FileRecord, Project, Report, Task, TaskStatus


def _auth(client, tag: str) -> dict:
    email = f"p7-{tag}-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "password123", "name": "P7"})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _uid(client, headers) -> str:
    return client.get("/auth/me", headers=headers).json()["id"]


READ_PATHS = ["/projects", "/clients", "/files", "/reports", "/integrations", "/permissions", "/activity"]


def test_read_endpoints_require_auth(client):
    for path in READ_PATHS:
        assert client.get(path).status_code == 401, path


def test_projects_list_detail_and_progress(client, db):
    h = _auth(client, "proj")
    uid = _uid(client, h)
    project = Project(user_id=uid, name="Alpha Site", description="d", status="active")
    db.add(project)
    db.flush()
    db.add_all([
        Task(user_id=uid, project_id=project.id, description="t1", status=TaskStatus.COMPLETED),
        Task(user_id=uid, project_id=project.id, description="t2", status=TaskStatus.PENDING),
    ])
    db.commit()

    rows = client.get("/projects", headers=h).json()
    mine = [r for r in rows if r["id"] == project.id]
    assert len(mine) == 1
    assert mine[0]["total_tasks"] == 2
    assert mine[0]["completed_tasks"] == 1
    assert mine[0]["progress_pct"] == 50

    one = client.get(f"/projects/{project.id}", headers=h)
    assert one.status_code == 200 and one.json()["name"] == "Alpha Site"
    assert client.get("/projects/does-not-exist", headers=h).status_code == 404

    h2 = _auth(client, "proj2")
    assert client.get(f"/projects/{project.id}", headers=h2).status_code == 404


def test_clients_list_and_detail(client, db):
    h = _auth(client, "cli")
    c = Client(name="Phase7 Client", email="c@example.com", status="new", notes="n")
    db.add(c)
    db.commit()
    rows = client.get("/clients", headers=h).json()
    assert any(r["id"] == c.id and r["email"] == "c@example.com" for r in rows)
    one = client.get(f"/clients/{c.id}", headers=h)
    assert one.status_code == 200 and one.json()["name"] == "Phase7 Client"
    assert client.get("/clients/nope", headers=h).status_code == 404


def test_files_list_scoped_to_user(client, db):
    h = _auth(client, "files")
    uid = _uid(client, h)
    db.add(FileRecord(user_id=uid, name="a.txt", path="/tmp/a.txt", kind="file", size_bytes=12))
    db.commit()
    rows = client.get("/files", headers=h).json()
    assert any(r["name"] == "a.txt" and r["size_bytes"] == 12 for r in rows)
    h2 = _auth(client, "files2")
    assert all(r["name"] != "a.txt" for r in client.get("/files", headers=h2).json())


def test_reports_list_filter_and_detail(client, db):
    h = _auth(client, "rep")
    rep = Report(kind="summary", title="Phase7 Report", content="body text")
    db.add(rep)
    db.commit()
    rows = client.get("/reports", headers=h).json()
    assert any(r["id"] == rep.id for r in rows)
    filtered = client.get("/reports", params={"kind": "summary"}, headers=h).json()
    assert all(r["kind"] == "summary" for r in filtered)
    one = client.get(f"/reports/{rep.id}", headers=h)
    assert one.status_code == 200 and one.json()["content"] == "body text"
    assert client.get("/reports/nope", headers=h).status_code == 404


def test_integrations_permissions_activity(client):
    h = _auth(client, "misc")
    integrations = client.get("/integrations", headers=h).json()
    assert isinstance(integrations, list)  # seeded rows may or may not exist; shape must hold

    perms = client.get("/permissions", headers=h).json()
    assert len(perms) >= 10  # seeded defaults
    tiers = {p["tier"] for p in perms}
    assert tiers == {"AUTOMATIC", "APPROVAL_REQUIRED", "ALWAYS_MANUAL"}

    activity = client.get("/activity", headers=h).json()
    assert any(a["action"] == "auth.register" for a in activity)
