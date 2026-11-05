"""Demo authentication: salted PBKDF2 password hashes and opaque server-side sessions.

This is prototype-grade auth for a local demo, not a production identity system:
no SSO/OAuth, no password reset, no email verification, and no PII beyond a username.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AuthSession, User, new_uuid
from app.services.errors import ServiceError

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, *, salt: str | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm, iterations, salt, expected = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; normalise before comparing."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    # Constant-ish response: always run a hash comparison to avoid a trivial timing oracle.
    stored = user.password_hash if user else hash_password("invalid-placeholder")
    if not user or not verify_password(password, stored):
        raise ServiceError("Username atau kata sandi tidak sesuai.", 401, "invalid_credentials")
    return user


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session = AuthSession(
        id=new_uuid(),
        token_hash=_token_hash(token),
        user_id=user.id,
        role=user.role,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
    )
    db.add(session)
    db.commit()
    return token, session


def resolve_session(db: Session, token: str) -> tuple[AuthSession, User]:
    session = db.execute(
        select(AuthSession).where(AuthSession.token_hash == _token_hash(token))
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise ServiceError("Sesi tidak valid. Silakan masuk kembali.", 401, "unauthenticated")
    if _aware(session.expires_at) <= datetime.now(timezone.utc):
        raise ServiceError("Sesi telah berakhir. Silakan masuk kembali.", 401, "session_expired")
    user = db.execute(select(User).where(User.id == session.user_id)).scalar_one_or_none()
    if user is None:
        raise ServiceError("Pengguna sesi tidak ditemukan.", 401, "unauthenticated")
    session.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return session, user


def revoke_session(db: Session, session: AuthSession) -> None:
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()


def session_payload(session: AuthSession, user: User) -> dict:
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        },
        "role": user.role,
        "expires_at": _aware(session.expires_at).isoformat(),
        "last_seen_at": _aware(session.last_seen_at).isoformat(),
    }
