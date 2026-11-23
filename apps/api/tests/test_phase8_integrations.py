"""Phase 8: integrations framework — honest statuses, real checks, no secrets.

All network access is monkeypatched; env is scrubbed/set per test. The API
must never return a secret value in any response.
"""
import uuid

import httpx
import pytest

import app.integrations as integrations

SECRET_ENV = [
    "GITHUB_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "SUPABASE_URL", "SUPABASE_ANON_KEY",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in SECRET_ENV:
        monkeypatch.delenv(name, raising=False)
    # settings fallback must not leak a developer's real .env into tests
    from app.config import settings

    for attr in ("github_token", "google_client_id", "google_client_secret",
                 "supabase_url", "supabase_anon_key", "openai_api_key", "gemini_api_key"):
        monkeypatch.setattr(settings, attr, None)
    yield


def _auth(client, tag: str) -> dict:
    email = f"p8-{tag}-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "password123", "name": "P8"})
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_all_providers_present_and_not_connected_without_env(client):
    h = _auth(client, "none")
    rows = client.get("/integrations", headers=h).json()
    providers = {r["provider"] for r in rows}
    assert providers == {"gmail", "google_calendar", "google_drive", "github",
                         "supabase", "openai", "gemini"}
    assert all(r["status"] == "not_connected" for r in rows)

    for key in sorted(providers):
        r = client.post(f"/integrations/{key}/check", headers=h)
        assert r.status_code == 200, key
        body = r.json()
        assert body["status"] == "not_connected", key
        assert body["last_checked_at"] is not None
        if key in ("gmail", "google_calendar", "google_drive"):
            assert body["config"]["note"] == integrations.GOOGLE_OAUTH_NOTE


def test_github_bogus_token_gives_error_not_connected(client, monkeypatch):
    h = _auth(client, "gh-bad")
    monkeypatch.setenv("GITHUB_TOKEN", "bogus-token-value-123")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(401, {"message": "Bad credentials"}))
    r = client.post("/integrations/github/check", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert body["config"]["http_status"] == 401
    assert "bogus-token-value-123" not in r.text  # token never returned


def test_github_valid_token_connects_and_stores_login_only(client, monkeypatch):
    h = _auth(client, "gh-ok")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_real-looking-secret")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(200, {"login": "octocat"}))
    r = client.post("/integrations/github/check", headers=h)
    body = r.json()
    assert body["status"] == "connected"
    assert body["account_label"] == "octocat"
    assert body["config"]["login"] == "octocat"
    assert "ghp_real-looking-secret" not in r.text


def test_github_network_failure_is_error_with_reason(client, monkeypatch):
    h = _auth(client, "gh-net")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def _boom(*a, **k):
        raise httpx.ConnectError("no route", request=httpx.Request("GET", "https://api.github.com/user"))

    monkeypatch.setattr(httpx, "get", _boom)
    body = client.post("/integrations/github/check", headers=h).json()
    assert body["status"] == "error"
    assert "reason" in body["config"]


def test_openai_gemini_presence_check_shows_model_not_key(client, monkeypatch):
    h = _auth(client, "ai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret")
    body = client.post("/integrations/openai/check", headers=h)
    assert body.json()["status"] == "connected"
    assert body.json()["config"]["model"]  # model name is shown
    assert "sk-super-secret" not in body.text  # the key never is

    body = client.post("/integrations/gemini/check", headers=h).json()
    assert body["status"] == "not_connected"  # no GEMINI_API_KEY set


def test_google_with_credentials_is_awaiting_oauth_with_auth_url(client, monkeypatch):
    h = _auth(client, "google")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id-123")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret-xyz")
    r = client.post("/integrations/gmail/check", headers=h)
    body = r.json()
    assert body["status"] == "awaiting_oauth"
    auth_url = body["config"]["auth_url"]
    assert auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=client-id-123" in auth_url
    assert "google-secret-xyz" not in r.text  # client secret never returned


def test_supabase_any_http_response_proves_reachability(client, monkeypatch):
    h = _auth(client, "supa")
    monkeypatch.setenv("SUPABASE_URL", "https://proj.example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-secret")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(401))
    r = client.post("/integrations/supabase/check", headers=h)
    body = r.json()
    assert body["status"] == "connected"  # 401 still proves reachability
    assert body["config"]["http_status"] == 401
    assert "anon-key-secret" not in r.text


def test_check_unknown_provider_404_and_requires_auth(client):
    h = _auth(client, "misc8")
    assert client.post("/integrations/nope/check", headers=h).status_code == 404
    assert client.post("/integrations/github/check").status_code == 401


def test_integration_check_is_audited(client):
    h = _auth(client, "audit")
    client.post("/integrations/github/check", headers=h)
    activity = client.get("/activity", headers=h).json()
    assert any(a["action"] == "integration.check" for a in activity)
