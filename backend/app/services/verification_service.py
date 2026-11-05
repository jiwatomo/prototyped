"""Admin verification: review, edit, approve or reject scholarships.

Scholarship-first so records without an extraction job (seeded or imported) can
still be managed. The extraction endpoints delegate to these functions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ExtractionJob,
    Scholarship,
    ScholarshipRequirement,
    ScholarshipRequirementGroup,
    ScholarshipSource,
    ScholarshipTag,
    ScholarshipVerification,
    StudentProfile,
    Tag,
    User,
)
from app.schemas.ai import ExtractionPatchRequest
from app.services import tagging_service
from app.services.errors import ServiceError
from app.services.extraction_service import job_payload

MINIMUM_FIELDS = ("name",)


# ------------------------------------------------------------------ lookups


def get_job(db: Session, extraction_id: str) -> ExtractionJob:
    job = db.execute(
        select(ExtractionJob).where(ExtractionJob.id == extraction_id)
    ).scalar_one_or_none()
    if job is None:
        raise ServiceError("Pekerjaan ekstraksi tidak ditemukan.", 404, "not_found")
    return job


def _get_scholarship(db: Session, job: ExtractionJob) -> Scholarship:
    if not job.scholarship_id:
        raise ServiceError("Ekstraksi ini belum memiliki data beasiswa.", 404, "not_found")
    scholarship = db.execute(
        select(Scholarship).where(Scholarship.id == job.scholarship_id)
    ).scalar_one_or_none()
    if scholarship is None:
        raise ServiceError("Beasiswa tidak ditemukan.", 404, "not_found")
    return scholarship


def get_scholarship(db: Session, scholarship_id: str) -> Scholarship:
    scholarship = db.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id)
    ).scalar_one_or_none()
    if scholarship is None:
        raise ServiceError("Beasiswa tidak ditemukan.", 404, "not_found")
    return scholarship


def _latest_job(db: Session, scholarship_id: str) -> ExtractionJob | None:
    return (
        db.execute(
            select(ExtractionJob)
            .where(ExtractionJob.scholarship_id == scholarship_id)
            .order_by(ExtractionJob.created_at.desc())
        )
        .scalars()
        .first()
    )


# ----------------------------------------------------------------- editing


def patch_scholarship(
    db: Session, scholarship: Scholarship, payload: ExtractionPatchRequest
) -> None:
    for field in (
        "name",
        "organizer",
        "description",
        "education_levels",
        "benefits",
        "application_start",
        "application_deadline",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(scholarship, field, value)

    if payload.tags is not None:
        for decision in payload.tags:
            tag = tagging_service.find_tag(db, decision.slug)
            if tag is None:
                raise ServiceError(f"Tag tidak dikenal: {decision.slug}", 422, "unknown_tag")
            row = db.execute(
                select(ScholarshipTag).where(
                    ScholarshipTag.scholarship_id == scholarship.id,
                    ScholarshipTag.tag_id == tag.id,
                )
            ).scalar_one_or_none()
            if row is None:
                raise ServiceError(
                    f"Tag {decision.slug} tidak terhubung ke beasiswa ini.", 404, "not_found"
                )
            row.review_status = {
                "approve": "approved",
                "reject": "rejected",
                "pending": "pending",
            }[decision.decision]
            if decision.weight is not None:
                row.weight = decision.weight
            row.reviewed_at = datetime.now(timezone.utc)

    if payload.requirements is not None:
        for group in (
            db.execute(
                select(ScholarshipRequirementGroup).where(
                    ScholarshipRequirementGroup.scholarship_id == scholarship.id
                )
            )
            .scalars()
            .all()
        ):
            for req in list(group.requirements):
                db.delete(req)
            db.delete(group)
        db.flush()

        groups: dict[tuple[str, str, bool], ScholarshipRequirementGroup] = {}
        for req in payload.requirements:
            key = (req.group, req.group_operator, req.is_mandatory)
            group = groups.get(key)
            if group is None:
                group = ScholarshipRequirementGroup(
                    scholarship_id=scholarship.id,
                    name=req.group,
                    operator=req.group_operator,
                    is_mandatory=req.is_mandatory,
                )
                db.add(group)
                db.flush()
                groups[key] = group
            tag_id = None
            if req.tag_slug:
                tag = tagging_service.find_tag(db, req.tag_slug)
                if tag is None:
                    raise ServiceError(f"Tag tidak dikenal: {req.tag_slug}", 422, "unknown_tag")
                tag_id = tag.id
            db.add(
                ScholarshipRequirement(
                    group_id=group.id,
                    tag_id=tag_id,
                    field_key=req.field_key,
                    operator=req.operator,
                    value_json=req.value,
                    unit=req.unit,
                    is_mandatory=req.is_mandatory,
                    source_reference=req.source_reference,
                    description=req.description,
                )
            )
    db.flush()


# ------------------------------------------------------------------ decisions


def approve_scholarship(
    db: Session, scholarship: Scholarship, admin_id: str | None, job_id: str | None = None
) -> Scholarship:
    if scholarship.verification_status == "verified":
        raise ServiceError("Beasiswa ini sudah diverifikasi.", 409, "already_verified")
    for field in MINIMUM_FIELDS:
        if not (getattr(scholarship, field) or "").strip():
            raise ServiceError(
                f"Field '{field}' wajib diisi sebelum menyetujui.", 422, "incomplete_data"
            )
    source_exists = db.execute(
        select(ScholarshipSource).where(ScholarshipSource.scholarship_id == scholarship.id)
    ).scalar_one_or_none()
    if source_exists is None:
        raise ServiceError("Sumber beasiswa wajib tercatat sebelum menyetujui.", 422, "missing_source")

    scholarship.verification_status = "verified"
    scholarship.rejection_reason = None
    now = datetime.now(timezone.utc)
    for row in (
        db.execute(
            select(ScholarshipTag).where(ScholarshipTag.scholarship_id == scholarship.id)
        )
        .scalars()
        .all()
    ):
        if row.review_status != "rejected":
            row.review_status = "approved"
            row.reviewed_by = admin_id
            row.reviewed_at = now

    db.add(
        ScholarshipVerification(
            scholarship_id=scholarship.id,
            extraction_job_id=job_id,
            decision="approved",
            reviewed_by=admin_id,
        )
    )
    db.commit()
    return scholarship


def reject_scholarship(
    db: Session,
    scholarship: Scholarship,
    reason: str,
    admin_id: str | None,
    job_id: str | None = None,
) -> Scholarship:
    if not reason.strip():
        raise ServiceError("Alasan penolakan wajib diisi.", 422, "missing_reason")
    if scholarship.verification_status == "rejected":
        raise ServiceError("Beasiswa ini sudah ditolak.", 409, "already_rejected")

    scholarship.verification_status = "rejected"
    scholarship.rejection_reason = reason.strip()
    now = datetime.now(timezone.utc)
    for row in (
        db.execute(
            select(ScholarshipTag).where(ScholarshipTag.scholarship_id == scholarship.id)
        )
        .scalars()
        .all()
    ):
        if row.review_status != "approved":
            row.review_status = "rejected"
            row.reviewed_at = now

    db.add(
        ScholarshipVerification(
            scholarship_id=scholarship.id,
            extraction_job_id=job_id,
            decision="rejected",
            reason=reason.strip(),
            reviewed_by=admin_id,
        )
    )
    db.commit()
    return scholarship


# ------------------------------------------------------------------ payloads


def scholarship_payload(db: Session, scholarship: Scholarship) -> dict[str, Any]:
    tags = (
        db.execute(
            select(ScholarshipTag, Tag)
            .join(Tag, Tag.id == ScholarshipTag.tag_id)
            .where(ScholarshipTag.scholarship_id == scholarship.id)
        )
        .all()
    )
    groups = (
        db.execute(
            select(ScholarshipRequirementGroup).where(
                ScholarshipRequirementGroup.scholarship_id == scholarship.id
            )
        )
        .scalars()
        .all()
    )
    requirements = []
    for group in groups:
        rows = (
            db.execute(
                select(ScholarshipRequirement, Tag)
                .outerjoin(Tag, Tag.id == ScholarshipRequirement.tag_id)
                .where(ScholarshipRequirement.group_id == group.id)
            )
            .all()
        )
        for req, tag in rows:
            requirements.append(
                {
                    "id": req.id,
                    "group": group.name,
                    "group_operator": group.operator,
                    "group_is_mandatory": group.is_mandatory,
                    "tag_slug": tag.slug if tag else None,
                    "field_key": req.field_key,
                    "operator": req.operator,
                    "value": req.value_json,
                    "unit": req.unit,
                    "is_mandatory": req.is_mandatory,
                    "description": req.description,
                    "source_reference": req.source_reference,
                }
            )

    job = _latest_job(db, scholarship.id)
    history = (
        db.execute(
            select(ScholarshipVerification)
            .where(ScholarshipVerification.scholarship_id == scholarship.id)
            .order_by(ScholarshipVerification.created_at.desc())
        )
        .scalars()
        .all()
    )

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
        "rejection_reason": scholarship.rejection_reason,
        "is_demo": scholarship.is_demo,
        "updated_at": scholarship.updated_at.isoformat() if scholarship.updated_at else None,
        "extraction_id": job.id if job else None,
        "source_type": job.source_type if job else None,
        "provider_mode": job.provider_mode if job else None,
        "tags": [
            {
                "slug": tag.slug,
                "name": tag.name,
                "context": sch_tag.context,
                "review_status": sch_tag.review_status,
                "weight": sch_tag.weight,
                "confidence": sch_tag.confidence,
                "evidence": sch_tag.evidence,
            }
            for sch_tag, tag in tags
        ],
        "requirements": requirements,
        "sources": [
            {"source_type": s.source_type, "source_url": s.source_url}
            for s in scholarship.sources
        ],
        "history": [
            {
                "decision": h.decision,
                "reason": h.reason,
                "reviewed_by": h.reviewed_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history
        ],
    }


def list_scholarships(
    db: Session, status: str | None = None, search: str | None = None
) -> list[dict[str, Any]]:
    stmt = select(Scholarship)
    if status:
        stmt = stmt.where(Scholarship.verification_status == status)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            (Scholarship.name.ilike(pattern)) | (Scholarship.organizer.ilike(pattern))
        )
    rows = db.execute(stmt.order_by(Scholarship.updated_at.desc())).scalars().all()
    result = []
    for scholarship in rows:
        tags = (
            db.execute(
                select(ScholarshipTag).where(ScholarshipTag.scholarship_id == scholarship.id)
            )
            .scalars()
            .all()
        )
        requirement_count = db.execute(
            select(func.count())
            .select_from(ScholarshipRequirement)
            .join(
                ScholarshipRequirementGroup,
                ScholarshipRequirementGroup.id == ScholarshipRequirement.group_id,
            )
            .where(ScholarshipRequirementGroup.scholarship_id == scholarship.id)
        ).scalar_one()
        job = _latest_job(db, scholarship.id)
        result.append(
            {
                "id": scholarship.id,
                "name": scholarship.name,
                "organizer": scholarship.organizer,
                "verification_status": scholarship.verification_status,
                "application_deadline": scholarship.application_deadline,
                "updated_at": scholarship.updated_at.isoformat()
                if scholarship.updated_at
                else None,
                "tag_count": len(tags),
                "approved_tags": sum(1 for t in tags if t.review_status == "approved"),
                "requirement_count": requirement_count,
                "extraction_id": job.id if job else None,
                "source_type": job.source_type if job else None,
            }
        )
    return result


def admin_stats(db: Session) -> dict[str, Any]:
    def count(model, *conditions) -> int:
        stmt = select(func.count()).select_from(model)
        for condition in conditions:
            stmt = stmt.where(condition)
        return db.execute(stmt).scalar_one()

    return {
        "users": {
            "total": count(User),
            "students": count(User, User.role == "student"),
            "admins": count(User, User.role == "admin"),
            "submitted_profiles": count(
                StudentProfile, StudentProfile.profile_submitted_at.isnot(None)
            ),
        },
        "scholarships": {
            "total": count(Scholarship),
            "verified": count(Scholarship, Scholarship.verification_status == "verified"),
            "pending": count(
                Scholarship, Scholarship.verification_status == "pending_verification"
            ),
            "draft": count(Scholarship, Scholarship.verification_status == "draft"),
            "rejected": count(Scholarship, Scholarship.verification_status == "rejected"),
        },
        "extractions": {
            "total": count(ExtractionJob),
            "completed": count(ExtractionJob, ExtractionJob.status == "completed"),
            "failed": count(ExtractionJob, ExtractionJob.status == "failed"),
        },
    }


# --------------------------------------------------- extraction-facing wrappers


def patch_extraction(
    db: Session, job: ExtractionJob, payload: ExtractionPatchRequest
) -> dict[str, Any]:
    if job.status != "completed":
        raise ServiceError("Hanya hasil ekstraksi yang selesai dapat diubah.", 409, "invalid_state")
    scholarship = _get_scholarship(db, job)
    patch_scholarship(db, scholarship, payload)
    job.result_json = {
        **(job.result_json or {}),
        "edited_by_admin": True,
        "edited_at": datetime.now(timezone.utc).isoformat(),
    }
    db.commit()
    return job_payload(db, job)


def approve(db: Session, job: ExtractionJob, admin_id: str | None) -> dict[str, Any]:
    scholarship = _get_scholarship(db, job)
    if job.status != "completed":
        raise ServiceError("Ekstraksi belum selesai.", 409, "invalid_state")
    approve_scholarship(db, scholarship, admin_id, job.id)
    return job_payload(db, job)


def reject(
    db: Session, job: ExtractionJob, reason: str, admin_id: str | None
) -> dict[str, Any]:
    scholarship = _get_scholarship(db, job)
    reject_scholarship(db, scholarship, reason, admin_id, job.id)
    return job_payload(db, job)


def pending_scholarships(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(Scholarship).where(
                Scholarship.verification_status.in_(["draft", "pending_verification"])
            )
        )
        .scalars()
        .all()
    )
    result = []
    for scholarship in rows:
        job = _latest_job(db, scholarship.id)
        result.append(
            {
                "scholarship_id": scholarship.id,
                "name": scholarship.name,
                "organizer": scholarship.organizer,
                "verification_status": scholarship.verification_status,
                "extraction_id": job.id if job else None,
                "provider_mode": job.provider_mode if job else None,
                "tags": [
                    {
                        "slug": st.tag.slug,
                        "context": st.context,
                        "review_status": st.review_status,
                    }
                    for st in scholarship.tags
                    if st.tag is not None
                ],
            }
        )
    return result
