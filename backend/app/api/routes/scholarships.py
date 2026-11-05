"""Scholarship catalog and recommendation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_self_or_admin
from app.core.database import get_db
from app.models.entities import Scholarship, User
from app.services import profile_service, recommendation_service
from app.services.ai.factory import get_ai_service

router = APIRouter(tags=["scholarships"])


@router.get("/scholarships")
def list_scholarships(
    include_all: bool = Query(default=False, description="Tampilkan semua status (khusus admin)"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    stmt = select(Scholarship)
    if not include_all:
        stmt = stmt.where(Scholarship.verification_status == "verified")
    rows = db.execute(stmt.order_by(Scholarship.name)).scalars().all()
    return {
        "count": len(rows),
        "data_label": "DATA DEMO SINTETIS — BUKAN INFORMASI BEASISWA NYATA",
        "scholarships": [
            {
                "id": s.id,
                "name": s.name,
                "organizer": s.organizer,
                "description": s.description,
                "education_levels": s.education_levels or [],
                "benefits": s.benefits or [],
                "application_start": s.application_start,
                "application_deadline": s.application_deadline,
                "verification_status": s.verification_status,
                "application_status": recommendation_service._application_status(s),
                "is_demo": s.is_demo,
            }
            for s in rows
        ],
    }


@router.get("/scholarships/{scholarship_id}")
def get_scholarship(
    scholarship_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    from app.services.errors import ServiceError

    scholarship = db.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id)
    ).scalar_one_or_none()
    if scholarship is None:
        raise ServiceError("Beasiswa tidak ditemukan.", 404, "not_found")
    tags = recommendation_service.scholarship_tags(db, scholarship.id)
    groups = recommendation_service.requirement_groups(db, scholarship.id)
    return {
        "id": scholarship.id,
        "name": scholarship.name,
        "organizer": scholarship.organizer,
        "description": scholarship.description,
        "education_levels": scholarship.education_levels or [],
        "benefits": scholarship.benefits or [],
        "application_start": scholarship.application_start,
        "application_deadline": scholarship.application_deadline,
        "verification_status": scholarship.verification_status,
        "application_status": recommendation_service._application_status(scholarship),
        "is_demo": scholarship.is_demo,
        "tags": tags,
        "requirement_groups": groups,
        "sources": [
            {"source_type": s.source_type, "source_url": s.source_url}
            for s in scholarship.sources
        ],
    }


@router.get("/recommendations/{username}")
def recommendations(
    username: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_self_or_admin),
) -> dict:
    user = profile_service.get_user(db, username)
    profile = profile_service.get_profile(db, user)
    payload = recommendation_service.compute(db, user, profile)
    payload["provider_mode"] = get_ai_service().describe()["provider_mode"]
    payload["warnings"] = _warnings(profile)
    return payload


@router.post("/recommendations/recompute")
def recompute(
    username: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    from app.services.errors import ServiceError

    target = username or actor.username
    if actor.role != "admin" and actor.username != target:
        raise ServiceError("Anda tidak berhak menghitung ulang profil ini.", 403, "forbidden")
    user = profile_service.get_user(db, target)
    profile = profile_service.get_profile(db, user)
    payload = recommendation_service.compute(db, user, profile)
    payload["provider_mode"] = get_ai_service().describe()["provider_mode"]
    payload["warnings"] = _warnings(profile)
    payload["recomputed"] = True
    return payload


def _warnings(profile) -> list[str]:
    warnings: list[str] = []
    if profile.profile_status != "confirmed":
        warnings.append(
            "Profil belum dikonfirmasi. Rekomendasi memakai fakta/tag terkonfirmasi terakhir."
        )
    if not profile.facts_confirmed_at:
        warnings.append(
            "Fakta profil belum pernah dikonfirmasi; persyaratan numerik akan berstatus belum diketahui."
        )
    return warnings
