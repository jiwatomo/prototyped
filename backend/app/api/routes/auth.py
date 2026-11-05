"""Login, session introspection and logout (demo auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_session
from app.core.database import get_db
from app.models.entities import AuthSession, User
from app.schemas.ai import LoginRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = auth_service.authenticate(db, payload.username.strip(), payload.password)
    token, session = auth_service.create_session(db, user)
    return {
        "token": token,
        "token_type": "bearer",
        **auth_service.session_payload(session, user),
    }


@router.get("/session")
def read_session(
    ctx: tuple[AuthSession, User] = Depends(get_current_session),
) -> dict:
    session, user = ctx
    return auth_service.session_payload(session, user)


@router.post("/logout")
def logout(
    ctx: tuple[AuthSession, User] = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    session, _user = ctx
    auth_service.revoke_session(db, session)
    return {"revoked": True}
