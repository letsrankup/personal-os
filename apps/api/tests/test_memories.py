"""Phase 5 tests: memory CRUD + keyword search."""
import uuid


def _auth(client) -> dict:
    email = f"mem-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "password123", "name": "Mem"})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_memory_crud_and_search(client):
    h = _auth(client)
    r = client.post(
        "/memories",
        json={"kind": "preference", "title": "Coffee", "content": "User likes black coffee in the morning",
              "tags": ["drink", "morning"]},
        headers=h,
    )
    assert r.status_code == 201, r.text
    mem = r.json()
    assert mem["kind"] == "preference"

    client.post(
        "/memories",
        json={"kind": "decision", "title": "Shop platform", "content": "Chose Redbubble for designs", "tags": ["shop"]},
        headers=h,
    )

    # Search hits title, content and tags; misses unrelated terms.
    hits = client.get("/memories", params={"q": "coffee"}, headers=h).json()
    assert [m["id"] for m in hits] == [mem["id"]]
    hits = client.get("/memories", params={"q": "morning"}, headers=h).json()
    assert [m["id"] for m in hits] == [mem["id"]]
    assert client.get("/memories", params={"q": "spaceship"}, headers=h).json() == []
    by_kind = client.get("/memories", params={"kind": "decision"}, headers=h).json()
    assert len(by_kind) == 1 and by_kind[0]["title"] == "Shop platform"

    # Read / patch / delete round-trip.
    got = client.get(f"/memories/{mem['id']}", headers=h)
    assert got.status_code == 200
    patched = client.patch(f"/memories/{mem['id']}", json={"title": "Coffee (updated)"}, headers=h)
    assert patched.status_code == 200
    assert patched.json()["title"] == "Coffee (updated)"
    bad = client.patch(f"/memories/{mem['id']}", json={"kind": "nonsense"}, headers=h)
    assert bad.status_code == 422
    deleted = client.delete(f"/memories/{mem['id']}", headers=h)
    assert deleted.status_code == 204
    assert client.get(f"/memories/{mem['id']}", headers=h).status_code == 404


def test_memory_kind_validation_and_isolation(client):
    h1 = _auth(client)
    h2 = _auth(client)
    bad = client.post("/memories", json={"kind": "secret", "content": "x"}, headers=h1)
    assert bad.status_code == 422
    r = client.post("/memories", json={"kind": "instruction", "content": "Always reply in Roman Urdu"}, headers=h1)
    mem_id = r.json()["id"]
    # Another user cannot see or read it.
    assert client.get("/memories", headers=h2).json() == []
    assert client.get(f"/memories/{mem_id}", headers=h2).status_code == 404


def test_memory_retrieved_into_command_context(client):
    """A saved memory matching a later command is found by orchestrator search."""
    from app.orchestrator import search_memories
    from app.database import SessionLocal
    from app.models import User

    h = _auth(client)
    client.post(
        "/memories",
        json={"kind": "preference", "title": "Coffee", "content": "User likes black coffee", "tags": ["drink"]},
        headers=h,
    )
    me = client.get("/auth/me", headers=h).json()
    with SessionLocal() as db:
        hits = search_memories(db, me["id"], "What coffee do I like?")
        assert hits and hits[0]["title"] == "Coffee"
        assert search_memories(db, me["id"], "quantum physics lecture") == []
