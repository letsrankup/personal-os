EMAIL = "owner@example.com"
PASSWORD = "test-password-123"


def test_register_login_me_flow(client):
    r = client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "Owner"})
    assert r.status_code == 201
    assert r.json()["email"] == EMAIL
    assert "password" not in r.text  # hash/password never returned

    r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["token_type"] == "bearer"

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_login_wrong_password_rejected(client):
    r = client.post("/auth/login", json={"email": EMAIL, "password": "wrong-password"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer bogus"}).status_code == 401


def test_duplicate_register_conflict(client):
    r = client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 409
