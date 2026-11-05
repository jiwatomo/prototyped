"""Profile lifecycle: free-text analysis, human confirmation, deterministic updates."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import StudentProfile, Tag, User, UserTag, new_uuid
from app.schemas.ai import ProfileConfirmRequest, ProfileUpdateRequest
from app.services import tagging_service
from app.services.ai.factory import AIService
from app.services.errors import ServiceError


def _iso(value: datetime | None) -> str | None:
    """SQLite returns naive datetimes; expose them as explicit UTC ISO strings."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def get_user(db: Session, username: str) -> User:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise ServiceError("Pengguna demo tidak ditemukan. Jalankan seed terlebih dahulu.", 404, "not_found")
    return user


def get_profile(db: Session, user: User) -> StudentProfile:
    profile = db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise ServiceError("Profil belum dibuat. Jalankan seed terlebih dahulu.", 404, "not_found")
    return profile


def confirmed_facts(profile: StudentProfile) -> dict[str, Any]:
    return {
        "education_level": profile.education_level,
        "major": profile.major,
        "institution": profile.institution,
        "gpa": profile.gpa,
        "domicile": profile.domicile,
        "toefl_type": profile.toefl_type,
        "toefl_score": profile.toefl_score,
        "achievements": profile.achievements_json or [],
    }


def user_tags_payload(db: Session, user: User) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(UserTag, Tag)
            .join(Tag, Tag.id == UserTag.tag_id)
            .where(UserTag.user_id == user.id)
            .order_by(UserTag.context, Tag.slug)
        )
        .all()
    )
    return [
        {
            "tag_id": tag.id,
            "slug": tag.slug,
            "name": tag.name,
            "context": user_tag.context,
            "assignment_source": user_tag.assignment_source,
            "confidence": user_tag.confidence,
            "confirmation_status": user_tag.confirmation_status,
            "weight": user_tag.weight,
            "evidence": user_tag.evidence,
        }
        for user_tag, tag in rows
    ]


def profile_payload(db: Session, user: User, profile: StudentProfile) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "description": profile.description,
        "profile_status": profile.profile_status,
        "latest_analysis_id": profile.latest_analysis_id,
        "confirmed_analysis_id": profile.confirmed_analysis_id,
        "facts_confirmed_at": _iso(profile.facts_confirmed_at),
        "submitted": profile.profile_submitted_at is not None,
        "profile_submitted_at": _iso(profile.profile_submitted_at),
        "facts": confirmed_facts(profile),
        "last_analysis": profile.extracted_facts_json,
        "tags": user_tags_payload(db, user),
    }


async def analyze_profile(
    db: Session,
    user: User,
    profile: StudentProfile,
    description: str,
    ai: AIService,
) -> dict[str, Any]:
    if profile.profile_submitted_at is not None:
        raise ServiceError(
            "Profil sudah pernah dikirim. Tag rekomendasi hanya dapat dikirim satu kali.",
            409,
            "already_submitted",
        )

    text = (description or "").strip()
    if not text:
        raise ServiceError("Deskripsi profil tidak boleh kosong.", 422, "empty_description")
    if len(text) > settings.ai_max_input_chars:
        raise ServiceError(
            f"Deskripsi melebihi batas {settings.ai_max_input_chars} karakter.",
            422,
            "description_too_long",
        )

    allowed = tagging_service.allowed_tags(db)
    aliases = tagging_service.alias_map(db)
    extraction, meta = await ai.extract_user_profile(text, allowed, aliases)

    analysis_id = new_uuid()
    tags_payload = [
        {
            "slug": tag.slug,
            "name": next((t["name"] for t in allowed if t["slug"] == tag.slug), tag.slug),
            "context": tag.context,
            "confidence": tag.confidence,
            "evidence": tag.evidence,
        }
        for tag in extraction.suggested_tags
    ]

    rejected = {
        (row.tag.slug, row.context)
        for row in db.execute(
            select(UserTag).where(
                UserTag.user_id == user.id, UserTag.confirmation_status == "rejected"
            )
        ).scalars()
        if row.tag is not None
    }
    for tag in tags_payload:
        tag["previously_rejected"] = (tag["slug"], tag["context"]) in rejected

    profile.description = text
    profile.extracted_facts_json = {
        "analysis_id": analysis_id,
        "facts": [fact.model_dump() for fact in extraction.facts],
        "suggested_tags": tags_payload,
        "provider": meta.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    profile.latest_analysis_id = analysis_id
    profile.profile_status = "analyzed"
    db.commit()

    return {
        "analysis_id": analysis_id,
        "profile_status": profile.profile_status,
        "facts": [fact.model_dump() for fact in extraction.facts],
        "suggested_tags": tags_payload,
        "description": profile.description,
        **meta.model_dump(),
    }


def _upsert_user_tag(
    db: Session,
    user: User,
    tag: Tag,
    context: str,
    status: str,
    source: str,
    confidence: float | None,
    evidence: dict[str, Any] | None,
    weight: float = 1.0,
    analysis_id: str | None = None,
) -> UserTag:
    existing = db.execute(
        select(UserTag).where(
            UserTag.user_id == user.id,
            UserTag.tag_id == tag.id,
            UserTag.context == context,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = UserTag(
            user_id=user.id,
            tag_id=tag.id,
            context=context,
            assignment_source=source,
            confidence=confidence,
            confirmation_status=status,
            weight=weight,
            evidence=evidence,
            analysis_id=analysis_id,
        )
        db.add(existing)
    else:
        existing.confirmation_status = status
        existing.assignment_source = source
        existing.confidence = confidence
        existing.weight = weight
        existing.evidence = evidence
        existing.analysis_id = analysis_id
    return existing


def confirm_profile(
    db: Session, user: User, profile: StudentProfile, payload: ProfileConfirmRequest
) -> dict[str, Any]:
    if profile.profile_submitted_at is not None:
        raise ServiceError(
            "Profil sudah pernah dikirim. Tag rekomendasi hanya dapat dikirim satu kali.",
            409,
            "already_submitted",
        )
    if not profile.latest_analysis_id or payload.analysis_id != profile.latest_analysis_id:
        raise ServiceError(
            "Hasil analisis bukan yang terbaru. Jalankan analisis ulang sebelum konfirmasi.",
            409,
            "stale_analysis",
        )
    if profile.confirmed_analysis_id == payload.analysis_id:
        raise ServiceError(
            "Hasil analisis ini sudah dikonfirmasi.", 409, "already_confirmed"
        )

    facts = payload.facts
    profile.education_level = facts.education_level
    profile.major = facts.major
    profile.institution = facts.institution
    profile.gpa = facts.gpa
    profile.domicile = facts.domicile
    profile.toefl_type = facts.toefl_type
    profile.toefl_score = facts.toefl_score
    profile.achievements_json = facts.achievements or []
    profile.profile_status = "confirmed"
    profile.facts_confirmed_at = datetime.now(timezone.utc)
    profile.confirmed_analysis_id = payload.analysis_id
    profile.profile_submitted_at = datetime.now(timezone.utc)

    analysis = profile.extracted_facts_json or {}
    suggestions = {
        (t["slug"], t["context"]): t for t in analysis.get("suggested_tags", [])
    }

    # Tags are an internal detail: the user confirms facts, the system accepts the
    # AI suggestions (still honouring earlier rejections recorded by an admin).
    decisions = payload.tags
    if not decisions:
        from app.schemas.ai import TagDecision

        decisions = [
            TagDecision(
                slug=item["slug"],
                context=item["context"],
                decision="reject" if item.get("previously_rejected") else "confirm",
            )
            for item in analysis.get("suggested_tags", [])
        ]

    for decision in decisions:
        tag = tagging_service.find_tag(db, decision.slug)
        if tag is None:
            raise ServiceError(f"Tag tidak dikenal: {decision.slug}", 422, "unknown_tag")
        suggestion = suggestions.get((decision.slug, decision.context), {})
        _upsert_user_tag(
            db,
            user,
            tag,
            decision.context,
            status="confirmed" if decision.decision == "confirm" else "rejected",
            source="user",
            confidence=suggestion.get("confidence"),
            evidence={
                "quote": suggestion.get("evidence", ""),
                "decided_by": "user",
            },
            weight=decision.weight if decision.weight is not None else 1.0,
            analysis_id=payload.analysis_id,
        )

    # Deterministic tags derived from confirmed facts (education level, major, domicile, language).
    decided = {(d.slug, d.context) for d in decisions}
    for derived in tagging_service.tags_from_facts(confirmed_facts(profile)):
        tag = tagging_service.find_tag(db, derived["slug"])
        if tag is None or (derived["slug"], derived["context"]) in decided:
            continue
        existing = db.execute(
            select(UserTag).where(
                UserTag.user_id == user.id,
                UserTag.tag_id == tag.id,
                UserTag.context == derived["context"],
            )
        ).scalar_one_or_none()
        if existing is not None and existing.confirmation_status == "rejected":
            continue  # never resurrect an explicit rejection silently
        _upsert_user_tag(
            db,
            user,
            tag,
            derived["context"],
            status="confirmed",
            source="system",
            confidence=None,
            evidence=derived["evidence"],
            analysis_id=payload.analysis_id,
        )

    db.commit()
    return profile_payload(db, user, profile)


def update_profile(
    db: Session, user: User, profile: StudentProfile, payload: ProfileUpdateRequest
) -> dict[str, Any]:
    if payload.description is None and payload.facts is None:
        raise ServiceError("Tidak ada perubahan yang dikirim.", 422, "empty_update")

    description_changed = False
    if payload.description is not None:
        text = payload.description.strip()
        if not text:
            raise ServiceError("Deskripsi profil tidak boleh kosong.", 422, "empty_description")
        if len(text) > settings.ai_max_input_chars:
            raise ServiceError(
                f"Deskripsi melebihi batas {settings.ai_max_input_chars} karakter.",
                422,
                "description_too_long",
            )
        if text != profile.description and profile.profile_submitted_at is not None:
            raise ServiceError(
                "Deskripsi terkunci setelah profil dikirim. Perbaiki nilai fakta pada halaman utama.",
                409,
                "description_locked",
            )
        if text != profile.description:
            description_changed = True
            profile.description = text
            profile.latest_analysis_id = None
            profile.extracted_facts_json = None
            profile.profile_status = "draft"

    if payload.facts is not None:
        facts = payload.facts
        profile.education_level = facts.education_level
        profile.major = facts.major
        profile.institution = facts.institution
        profile.gpa = facts.gpa
        profile.domicile = facts.domicile
        profile.toefl_type = facts.toefl_type
        profile.toefl_score = facts.toefl_score
        profile.achievements_json = facts.achievements or []
        profile.facts_confirmed_at = datetime.now(timezone.utc)
        if not description_changed:
            profile.profile_status = "confirmed"

    db.commit()
    result = profile_payload(db, user, profile)
    result["needs_analysis"] = description_changed or profile.profile_status != "confirmed"
    return result


def decide_single_tag(
    db: Session, user: User, profile: StudentProfile, tag_id: str, decision: str
) -> dict[str, Any]:
    tag = db.execute(select(Tag).where(Tag.id == tag_id)).scalar_one_or_none()
    if tag is None:
        raise ServiceError("Tag tidak ditemukan.", 404, "not_found")
    row = db.execute(
        select(UserTag).where(UserTag.user_id == user.id, UserTag.tag_id == tag_id)
    ).scalar_one_or_none()
    if row is None:
        raise ServiceError("Tag ini tidak terkait dengan profil pengguna.", 404, "not_found")
    row.confirmation_status = "confirmed" if decision == "confirm" else "rejected"
    row.assignment_source = "user"
    db.commit()
    return {"tag_id": tag_id, "slug": tag.slug, "confirmation_status": row.confirmation_status}


def ensure_analysis_uuid(value: str) -> str:
    """Guarantee a malformed analysis id is rejected before any DB lookup."""
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ServiceError("analysis_id tidak valid.", 422, "invalid_analysis_id") from exc
