"""Integration framework (Phase 8) — real, honest connection checks.

Hard rules:
- A status is only ever what a real check produced. Nothing is faked as
  "connected": GitHub is verified with a live API call, Supabase with a
  live HTTP probe, OpenAI/Gemini by key *presence* only (no API calls are
  burned), and the Google services honestly report that they need OAuth
  credentials the user has not provided yet.
- Secrets are read from the process environment (or the settings/.env
  fallback) at check time. They are NEVER written to the database, NEVER
  put into an integration's config, and NEVER returned by the API —
  `public_config()` additionally masks any sensitive-looking key as
  defence in depth.
- Google OAuth is never completed here: with credentials present we only
  build the authorization URL the user would open themselves.
"""
import os
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .models import Integration

# key -> display name
PROVIDERS: dict[str, str] = {
    "gmail": "Gmail",
    "google_calendar": "Google Calendar",
    "google_drive": "Google Drive",
    "github": "GitHub",
    "supabase": "Supabase",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
}

GOOGLE_PROVIDERS = ("gmail", "google_calendar", "google_drive")

GOOGLE_SCOPES = {
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly",
              "https://www.googleapis.com/auth/gmail.send"],
    "google_calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
    "google_drive": ["https://www.googleapis.com/auth/drive.readonly"],
}

GOOGLE_OAUTH_NOTE = "Requires Google OAuth credentials — see docs/INTEGRATIONS.md"

_SENSITIVE_MARKERS = ("token", "secret", "key", "password", "credential", "auth")


def _env(name: str, settings_attr: str | None = None) -> str | None:
    """Env var at call time (so checks reflect the live environment and
    tests can monkeypatch), falling back to the pydantic settings value
    (which covers apps/api/.env)."""
    value = os.environ.get(name)
    if value:
        return value
    if settings_attr:
        fallback = getattr(settings, settings_attr, None)
        if fallback:
            return fallback
    return None


def public_config(config: dict | None) -> dict:
    """Config safe to return from the API: sensitive-looking keys masked."""
    out = {}
    for key, value in (config or {}).items():
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_MARKERS) and "auth_url" not in lowered:
            out[key] = "***"
        else:
            out[key] = value
    return out


def ensure_integrations(db: Session) -> list[Integration]:
    """Create one row per known provider if missing (status not_connected)."""
    rows = []
    for key, name in PROVIDERS.items():
        row = db.query(Integration).filter_by(provider=key).first()
        if row is None:
            row = Integration(provider=key, status="not_connected",
                              account_label=None, config={"name": name})
            db.add(row)
        rows.append(row)
    db.flush()
    return rows


# ---------------------------------------------------------------------------
# Individual checks. Each returns (status, account_label, config) and never
# raises — failures become status "error" with the real reason recorded.
# ---------------------------------------------------------------------------
def _check_github() -> tuple[str, str | None, dict]:
    token = _env("GITHUB_TOKEN", "github_token")
    if not token:
        return "not_connected", None, {
            "note": "Set GITHUB_TOKEN in the API environment — see docs/INTEGRATIONS.md",
        }
    try:
        resp = httpx.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "personal-os",
            },
            timeout=10.0,
        )
    except Exception as exc:  # network failure — report the real reason
        return "error", None, {"reason": f"GitHub API unreachable: {exc}"[:300]}
    if resp.status_code == 200:
        login = resp.json().get("login")
        return "connected", login, {"login": login}
    return "error", None, {
        "http_status": resp.status_code,
        "note": f"GitHub rejected the configured token (HTTP {resp.status_code}).",
    }


def _check_openai() -> tuple[str, str | None, dict]:
    if not _env("OPENAI_API_KEY", "openai_api_key"):
        return "not_connected", None, {
            "note": "Set OPENAI_API_KEY in the API environment — see docs/INTEGRATIONS.md",
        }
    # Presence check only — no API call is burned.
    model = os.environ.get("OPENAI_MODEL") or settings.openai_model
    return "connected", None, {"model": model, "check": "key present (no API call made)"}


def _check_gemini() -> tuple[str, str | None, dict]:
    if not _env("GEMINI_API_KEY", "gemini_api_key"):
        return "not_connected", None, {
            "note": "Set GEMINI_API_KEY in the API environment — see docs/INTEGRATIONS.md",
        }
    model = os.environ.get("GEMINI_MODEL") or settings.gemini_model
    return "connected", None, {"model": model, "check": "key present (no API call made)"}


def _check_supabase() -> tuple[str, str | None, dict]:
    url = _env("SUPABASE_URL", "supabase_url")
    anon_key = _env("SUPABASE_ANON_KEY", "supabase_anon_key")
    if not url or not anon_key:
        return "not_connected", None, {
            "note": "Set SUPABASE_URL and SUPABASE_ANON_KEY in the API environment — see docs/INTEGRATIONS.md",
        }
    base = url.rstrip("/")
    try:
        resp = httpx.get(
            f"{base}/rest/v1/",
            headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
            timeout=10.0,
        )
    except Exception as exc:
        return "error", None, {"reason": f"Supabase unreachable: {exc}"[:300]}
    # Any HTTP response (200/401/404 included) proves the project is reachable.
    host = urlparse(base).netloc
    return "connected", host, {
        "http_status": resp.status_code,
        "url_host": host,
        "note": f"REST endpoint reachable (HTTP {resp.status_code}).",
    }


def _check_google(key: str) -> tuple[str, str | None, dict]:
    client_id = _env("GOOGLE_CLIENT_ID", "google_client_id")
    client_secret = _env("GOOGLE_CLIENT_SECRET", "google_client_secret")
    if not client_id or not client_secret:
        return "not_connected", None, {"note": GOOGLE_OAUTH_NOTE}
    base = (_env("APP_BASE_URL", "app_base_url") or "http://localhost:8000").rstrip("/")
    params = {
        "client_id": client_id,
        "redirect_uri": f"{base}/integrations/google/callback",
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES[key]),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return "awaiting_oauth", None, {
        "auth_url": auth_url,
        "note": "OAuth credentials configured. Open auth_url and complete the "
                "Google consent flow to finish connecting (never automated).",
    }


_CHECKS = {
    "github": _check_github,
    "openai": _check_openai,
    "gemini": _check_gemini,
    "supabase": _check_supabase,
}


def run_check(db: Session, key: str) -> Integration:
    """Run the real check for one provider and persist the honest result."""
    if key not in PROVIDERS:
        raise KeyError(f"Unknown integration '{key}'")
    ensure_integrations(db)
    row = db.query(Integration).filter_by(provider=key).first()
    if key in GOOGLE_PROVIDERS:
        status, account_label, config = _check_google(key)
    else:
        status, account_label, config = _CHECKS[key]()
    config = {"name": PROVIDERS[key], **config}
    row.status = status
    row.account_label = account_label
    row.config = config
    row.last_checked_at = datetime.now(timezone.utc)
    db.flush()
    return row
