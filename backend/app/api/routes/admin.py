"""Admin endpoints: extraction jobs, review and verification."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.entities import ExtractionJob, User
from app.schemas.ai import (
    AdminPasswordReset,
    SubmissionProcess,
    AdminUserCreate,
    ExtractionPatchRequest,
    ManualScholarshipRequest,
    RejectRequest,
)
from app.services import extraction_service, submission_service, user_service, verification_service
from app.services.ai.factory import get_ai_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _admin_id(db: Session) -> str | None:
    admin = db.execute(select(User).where(User.username == "demo-admin")).scalar_one_or_none()
    return admin.id if admin else None


async def _read_source(request: Request) -> dict[str, Any]:
    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data") or content_type.startswith(
        "application/x-www-form-urlencoded"
    ):
        form = await request.form()
        upload = form.get("file")
        pdf_bytes = None
        if upload is not None and getattr(upload, "filename", None):
            pdf_bytes = await upload.read()
        return {
            "source_url": (form.get("source_url") or None) or None,
            "source_text": (form.get("source_text") or None) or None,
            "pdf_bytes": pdf_bytes,
        }
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise ServiceError("Body harus berupa JSON atau form multipart.", 422, "invalid_body") from exc
    return {
        "source_url": body.get("source_url") or None,
        "source_text": body.get("source_text") or None,
        "pdf_bytes": None,
    }


@router.get("/extractions")
def list_extractions(db: Session = Depends(get_db)) -> dict:
    jobs = (
        db.execute(select(ExtractionJob).order_by(ExtractionJob.created_at.desc()))
        .scalars()
        .all()
    )
    return {
        "count": len(jobs),
        "extractions": [
            {
                "extraction_id": job.id,
                "status": job.status,
                "source_type": job.source_type,
                "source_url": job.source_url,
                "provider_mode": job.provider_mode,
                "fallback_reason": job.fallback_reason,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "scholarship_id": job.scholarship_id,
                "error": job.error,
            }
            for job in jobs
        ],
    }


@router.post("/extractions", status_code=201)
async def create_extraction(request: Request, db: Session = Depends(get_db)) -> dict:
    source = await _read_source(request)
    job = await extraction_service.create_extraction(
        db,
        get_ai_service(),
        source_type="text",
        source_text=source["source_text"],
        source_url=source["source_url"],
        pdf_bytes=source["pdf_bytes"],
        created_by=_admin_id(db),
    )
    return extraction_service.job_payload(db, job)


@router.get("/extractions/{extraction_id}")
def get_extraction(extraction_id: str, db: Session = Depends(get_db)) -> dict:
    job = verification_service.get_job(db, extraction_id)
    return extraction_service.job_payload(db, job)


@router.patch("/extractions/{extraction_id}")
def patch_extraction(
    extraction_id: str, payload: ExtractionPatchRequest, db: Session = Depends(get_db)
) -> dict:
    job = verification_service.get_job(db, extraction_id)
    return verification_service.patch_extraction(db, job, payload)


@router.post("/extractions/{extraction_id}/approve")
def approve_extraction(
    extraction_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    job = verification_service.get_job(db, extraction_id)
    return verification_service.approve(db, job, admin.id)


@router.post("/extractions/{extraction_id}/reject")
def reject_extraction(
    extraction_id: str,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    job = verification_service.get_job(db, extraction_id)
    return verification_service.reject(db, job, payload.reason, admin.id)


@router.post("/scholarships", status_code=201)
def create_manual_scholarship(
    payload: ManualScholarshipRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Admin types a scholarship directly; it enters the same pending review queue."""
    job = extraction_service.create_manual_scholarship(db, payload, admin.id)
    return extraction_service.job_payload(db, job)


@router.get("/scholarships/pending")
def pending_scholarships(db: Session = Depends(get_db)) -> dict:
    rows = verification_service.pending_scholarships(db)
    return {"count": len(rows), "scholarships": rows}


# ------------------------------------------------------------------ dashboard


@router.get("/stats")
def admin_stats(db: Session = Depends(get_db)) -> dict:
    return verification_service.admin_stats(db)


# ---------------------------------------------------------------------- users


@router.get("/users")
def list_users(db: Session = Depends(get_db)) -> dict:
    users = user_service.list_users(db)
    return {"count": len(users), "users": users}


@router.post("/users", status_code=201)
def create_user(payload: AdminUserCreate, db: Session = Depends(get_db)) -> dict:
    user = user_service.create_user(
        db,
        username=payload.username,
        display_name=payload.display_name,
        role=payload.role,
        password=payload.password,
    )
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "created": True,
    }


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: str, payload: AdminPasswordReset, db: Session = Depends(get_db)
) -> dict:
    user = user_service.get_user(db, user_id)
    password, generated = user_service.reset_password(db, user, payload.password)
    return {
        "user_id": user.id,
        "username": user.username,
        "generated": generated,
        "temporary_password": password if generated else None,
        "sessions_revoked": True,
    }


# --------------------------------------------------- scholarship management


@router.get("/scholarships")
def list_scholarships_admin(
    status: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    rows = verification_service.list_scholarships(db, status=status, search=search)
    return {"count": len(rows), "scholarships": rows}


@router.get("/scholarships/{scholarship_id}")
def get_scholarship_admin(scholarship_id: str, db: Session = Depends(get_db)) -> dict:
    scholarship = verification_service.get_scholarship(db, scholarship_id)
    return verification_service.scholarship_payload(db, scholarship)


@router.patch("/scholarships/{scholarship_id}")
def patch_scholarship_admin(
    scholarship_id: str, payload: ExtractionPatchRequest, db: Session = Depends(get_db)
) -> dict:
    scholarship = verification_service.get_scholarship(db, scholarship_id)
    verification_service.patch_scholarship(db, scholarship, payload)
    db.commit()
    return verification_service.scholarship_payload(db, scholarship)


@router.post("/scholarships/{scholarship_id}/approve")
def approve_scholarship_admin(
    scholarship_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    scholarship = verification_service.get_scholarship(db, scholarship_id)
    verification_service.approve_scholarship(db, scholarship, admin.id)
    return verification_service.scholarship_payload(db, scholarship)


@router.post("/scholarships/{scholarship_id}/reject")
def reject_scholarship_admin(
    scholarship_id: str,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    scholarship = verification_service.get_scholarship(db, scholarship_id)
    verification_service.reject_scholarship(db, scholarship, payload.reason, admin.id)
    return verification_service.scholarship_payload(db, scholarship)

# ------------------------------------------------- screenshot submissions


@router.get("/submissions")
def list_submissions(status: str | None = None, db: Session = Depends(get_db)) -> dict:
    rows = submission_service.list_admin(db, status=status)
    return {"count": len(rows), "submissions": rows}


@router.get("/submissions/{submission_id}/image")
def submission_image(submission_id: str, db: Session = Depends(get_db)) -> Response:
    submission = submission_service.get_submission(db, submission_id)
    return Response(
        content=submission.image_data,
        media_type=submission.image_mime,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/submissions/{submission_id}/process")
def process_submission(
    submission_id: str,
    payload: SubmissionProcess,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    submission = submission_service.get_submission(db, submission_id)
    updated = submission_service.process(
        db,
        submission,
        payload.status,
        payload.reason,
        admin.id,
        payload.scholarship_id,
    )
    return submission_service.payload(updated)
