"""Authentication dependencies for FastAPI routes."""
from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import AuthSession, User
from app.services import auth_service
from app.services.errors import ServiceError

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> tuple[AuthSession, User]:
    if credentials is None or not (credentials.credentials or "").strip():
        raise ServiceError("Silakan masuk terlebih dahulu.", 401, "unauthenticated")
    return auth_service.resolve_session(db, credentials.credentials)


def get_current_user(ctx: tuple[AuthSession, User] = Depends(get_current_session)) -> User:
    return ctx[1]


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise ServiceError("Endpoint ini hanya untuk admin.", 403, "forbidden")
    return user


def require_self(username: str, user: User = Depends(get_current_user)) -> User:
    if user.username != username:
        raise ServiceError("Anda hanya dapat mengakses profil sendiri.", 403, "forbidden")
    return user


def require_self_or_admin(username: str, user: User = Depends(get_current_user)) -> User:
    if user.role != "admin" and user.username != username:
        raise ServiceError("Anda tidak berhak mengakses data pengguna ini.", 403, "forbidden")
    return user
