"""Shared dependencies: current-user auth + activity-log helper."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import ActivityLog, User
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def log_activity(
    db: Session,
    action: str,
    actor: str = "system",
    user_id: str | None = None,
    entity: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
) -> ActivityLog:
    """Write one row to activity_logs (audit trail). Caller commits."""
    entry = ActivityLog(
        action=action,
        actor=actor,
        user_id=user_id,
        entity=entity,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(entry)
    return entry


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    user_id = decode_access_token(creds.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def require_owner_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Role gate (Phase 9): only owner/admin users may proceed.

    Registered users default to role "owner" (single-user personal
    deployment); accounts created with any other role (e.g. "member")
    get 403 on owner-only endpoints such as GET /permissions and
    POST /integrations/{key}/check.
    """
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Owner or admin role required for this endpoint",
        )
    return current_user
