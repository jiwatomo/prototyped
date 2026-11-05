"""Admin user management: create demo accounts and reset passwords."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AuthSession, StudentProfile, User, new_uuid
from app.services import auth_service
from app.services.errors import ServiceError

MIN_PASSWORD_LENGTH = 8


def list_users(db: Session) -> list[dict]:
    users = db.execute(select(User).order_by(User.role, User.username)).scalars().all()
    profiles = {
        p.user_id: p for p in db.execute(select(StudentProfile)).scalars().all()
    }
    return [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "has_password": bool(user.password_hash),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "profile_status": profiles[user.id].profile_status
            if user.id in profiles
            else None,
            "profile_submitted": bool(
                profiles[user.id].profile_submitted_at
            )
            if user.id in profiles
            else None,
        }
        for user in users
    ]


def get_user(db: Session, user_id: str) -> User:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise ServiceError("Pengguna tidak ditemukan.", 404, "not_found")
    return user


def create_user(
    db: Session, *, username: str, display_name: str, role: str, password: str
) -> User:
    username = username.strip().lower()
    if role not in {"student", "admin"}:
        raise ServiceError("Role harus 'student' atau 'admin'.", 422, "invalid_role")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ServiceError(
            f"Kata sandi minimal {MIN_PASSWORD_LENGTH} karakter.", 422, "weak_password"
        )
    existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if existing is not None:
        raise ServiceError("Username sudah dipakai.", 409, "username_taken")

    user = User(
        id=new_uuid(),
        username=username,
        display_name=display_name.strip() or username,
        role=role,
        password_hash=auth_service.hash_password(password),
    )
    db.add(user)
    db.flush()

    if role == "student":
        db.add(StudentProfile(user_id=user.id, description="", profile_status="draft"))
    db.commit()
    return user


def reset_password(db: Session, user: User, password: str | None) -> tuple[str, bool]:
    """Set a new password (generated when omitted) and revoke existing sessions."""
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(9)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ServiceError(
            f"Kata sandi minimal {MIN_PASSWORD_LENGTH} karakter.", 422, "weak_password"
        )
    user.password_hash = auth_service.hash_password(password)
    for session in (
        db.execute(select(AuthSession).where(AuthSession.user_id == user.id))
        .scalars()
        .all()
    ):
        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return password, generated
