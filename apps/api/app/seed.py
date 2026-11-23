"""Seeding: the 11 agents (master + 10 specialists) and default permission tiers.

Admin user seeding happens ONLY from env vars (ADMIN_EMAIL / ADMIN_PASSWORD).
No password is hardcoded anywhere; if the env vars are absent, admin seeding
is skipped. Run standalone with:  python -m app.seed
"""
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, init_db
from .integrations import ensure_integrations
from .models import Agent, Permission, PermissionTier, User
from .security import hash_password

AGENTS: list[dict] = [
    {"key": "master", "name": "Master Agent", "role": "Orchestrator: understand commands (English + Roman Urdu), plan, delegate to specialists, monitor, verify results, save memory, and produce the final report. Never claims completion without verification."},
    {"key": "research", "name": "Research Agent", "role": "Web research, information collection, competitor analysis, source verification, research reports."},
    {"key": "tasks", "name": "Task Management Agent", "role": "Create tasks, update status, set priorities, track deadlines, identify pending work."},
    {"key": "communication", "name": "Communication Agent", "role": "Read authorized emails, draft replies, organize conversations, prepare follow-ups."},
    {"key": "clients", "name": "Client Management Agent", "role": "Organize client information, handle inquiries, categorize complaints, prepare responses, track follow-ups."},
    {"key": "business", "name": "Business Agent", "role": "Business research and planning, workflow management, market analysis, operational reports."},
    {"key": "developer", "name": "Developer Agent", "role": "Generate code, create websites and applications, debug, run tests, review files, prepare deployment configurations."},
    {"key": "finance", "name": "Finance Agent", "role": "Track income/expenses from authorized records, create invoices, financial summaries and expense reports. NEVER executes payments or transfers."},
    {"key": "marketing", "name": "Marketing Agent", "role": "SEO research, content planning, social media drafts, marketing campaigns, performance analysis."},
    {"key": "projects", "name": "Project Manager Agent", "role": "Monitor all projects, track milestones, identify blockers, assign tasks, maintain project history."},
    {"key": "reporting", "name": "Reporting Agent", "role": "Daily, weekly and monthly reports; agent performance and task completion reports. Never reports planned work as completed work."},
]

DEFAULT_PERMISSIONS: list[dict] = [
    {"action": "research.run", "tier": PermissionTier.AUTOMATIC, "description": "Web research and information collection"},
    {"action": "files.read_authorized", "tier": PermissionTier.AUTOMATIC, "description": "Read authorized files"},
    {"action": "reports.create", "tier": PermissionTier.AUTOMATIC, "description": "Create internal reports"},
    {"action": "tasks.manage_internal", "tier": PermissionTier.AUTOMATIC, "description": "Create/update internal tasks"},
    {"action": "email.draft", "tier": PermissionTier.AUTOMATIC, "description": "Prepare email drafts (not send)"},
    {"action": "email.send_external", "tier": PermissionTier.APPROVAL_REQUIRED, "description": "Send external email"},
    {"action": "web.publish", "tier": PermissionTier.APPROVAL_REQUIRED, "description": "Publish websites or content"},
    {"action": "forms.submit", "tier": PermissionTier.APPROVAL_REQUIRED, "description": "Submit external forms"},
    {"action": "account.change_settings", "tier": PermissionTier.APPROVAL_REQUIRED, "description": "Change important account settings"},
    {"action": "files.share_external", "tier": PermissionTier.APPROVAL_REQUIRED, "description": "Share files externally"},
    {"action": "clients.contact_new", "tier": PermissionTier.APPROVAL_REQUIRED, "description": "Contact new clients"},
    {"action": "money.transfer", "tier": PermissionTier.ALWAYS_MANUAL, "description": "Money transfers / financial transactions — never automated"},
    {"action": "credentials.disclose", "tier": PermissionTier.ALWAYS_MANUAL, "description": "Password/secret disclosure — never automated"},
    {"action": "account.delete_irreversible", "tier": PermissionTier.ALWAYS_MANUAL, "description": "Irreversible account deletion — never automated"},
]


def seed_agents(db: Session) -> int:
    created = 0
    for spec in AGENTS:
        if db.query(Agent).filter_by(key=spec["key"]).first() is None:
            db.add(Agent(**spec, status="idle"))
            created += 1
    db.commit()
    return created


def seed_permissions(db: Session) -> int:
    created = 0
    for spec in DEFAULT_PERMISSIONS:
        if db.query(Permission).filter_by(action=spec["action"]).first() is None:
            db.add(Permission(**spec))
            created += 1
    db.commit()
    return created


def seed_admin(db: Session) -> bool:
    """Create the admin user only if ADMIN_EMAIL and ADMIN_PASSWORD are set."""
    if not settings.admin_email or not settings.admin_password:
        return False
    if db.query(User).filter_by(email=settings.admin_email).first() is not None:
        return False
    db.add(
        User(
            email=settings.admin_email,
            name=settings.admin_name,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
    )
    db.commit()
    return True


def seed_integrations(db: Session) -> int:
    """Ensure one honest `not_connected` row per known provider (Phase 8)."""
    from .models import Integration

    existing = db.query(Integration).count()
    ensure_integrations(db)
    db.commit()
    return db.query(Integration).count() - existing


def seed_all(db: Session) -> dict:
    return {
        "agents_created": seed_agents(db),
        "permissions_created": seed_permissions(db),
        "integrations_created": seed_integrations(db),
        "admin_created": seed_admin(db),
    }


if __name__ == "__main__":
    init_db()
    with SessionLocal() as db:
        print(seed_all(db))
