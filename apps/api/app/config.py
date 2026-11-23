"""Configuration from environment only. No secrets in code."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # apps/api/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    # SQLite file lives in apps/api/ by default; override with DATABASE_URL
    # e.g. postgresql+psycopg://user:pass@host:5432/personal_os (Supabase/Postgres)
    database_url: str = f"sqlite:///{BASE_DIR / 'personal_os.db'}"

    jwt_secret: str = "dev-only-change-me"  # override via JWT_SECRET in real use
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    admin_email: str | None = None
    admin_password: str | None = None
    admin_name: str = "Admin"

    # AI providers — keys come from env only (OPENAI_API_KEY / GEMINI_API_KEY).
    # ai_provider optionally forces one of: openai | gemini | pollinations | offline.
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-2.0-flash"
    ai_provider: str | None = None
    ai_timeout_seconds: float = 30.0

    web_origin: str = "http://localhost:3000"
    # CORS allow-list (Phase 9): comma-separated env ALLOWED_ORIGINS wins
    # when set; otherwise the single web_origin above is used.
    allowed_origins: str | None = None

    # Integrations (Phase 8) — secrets come from env / .env only, are read
    # at check time, and are NEVER stored in the DB or returned by the API.
    github_token: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    app_base_url: str = "http://localhost:8000"

    # Developer Agent workspace: generated sites/apps live under this dir
    # (default apps/api/agent_workspace). Override with AGENT_WORKSPACE_DIR.
    agent_workspace_dir: str | None = None


settings = Settings()
