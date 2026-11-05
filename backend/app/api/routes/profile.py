"""User profile endpoints: free-text analysis, confirmation and updates."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_self, require_self_or_admin
from app.core.database import get_db
from app.models.entities import User
from app.schemas.ai import ProfileAnalyzeRequest, ProfileConfirmRequest, ProfileUpdateRequest
from app.services import profile_service
from app.services.ai.factory import get_ai_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/{username}")
def get_profile(
    username: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self_or_admin),
) -> dict:
    user = profile_service.get_user(db, username)
    profile = profile_service.get_profile(db, user)
    return profile_service.profile_payload(db, user, profile)


@router.post("/{username}/analyze")
async def analyze_profile(
    username: str,
    payload: ProfileAnalyzeRequest,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self),
) -> dict:
    user = profile_service.get_user(db, username)
    profile = profile_service.get_profile(db, user)
    result = await profile_service.analyze_profile(
        db, user, profile, payload.description, get_ai_service()
    )
    return result


@router.post("/{username}/confirm")
def confirm_profile(
    username: str,
    payload: ProfileConfirmRequest,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self),
) -> dict:
    user = profile_service.get_user(db, username)
    profile = profile_service.get_profile(db, user)
    profile_service.ensure_analysis_uuid(payload.analysis_id)
    return profile_service.confirm_profile(db, user, profile, payload)


@router.put("/{username}")
def update_profile(
    username: str,
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self),
) -> dict:
    user = profile_service.get_user(db, username)
    profile = profile_service.get_profile(db, user)
    return profile_service.update_profile(db, user, profile, payload)


@router.get("/{username}/tags")
def list_user_tags(
    username: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self_or_admin),
) -> dict:
    user = profile_service.get_user(db, username)
    profile_service.get_profile(db, user)
    return {"tags": profile_service.user_tags_payload(db, user)}


@router.post("/{username}/tags/{tag_id}/confirm")
def confirm_tag(
    username: str,
    tag_id: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self),
) -> dict:
    user = profile_service.get_user(db, username)
    profile = profile_service.get_profile(db, user)
    return profile_service.decide_single_tag(db, user, profile, tag_id, "confirm")


@router.post("/{username}/tags/{tag_id}/reject")
def reject_tag(
    username: str,
    tag_id: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self),
) -> dict:
    user = profile_service.get_user(db, username)
    profile = profile_service.get_profile(db, user)
    return profile_service.decide_single_tag(db, user, profile, tag_id, "reject")
