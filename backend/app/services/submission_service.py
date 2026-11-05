"""Student-submitted scholarship screenshots and admin review."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import User, UserScholarshipSubmission
from app.services.errors import ServiceError

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 5_000_000


def create_submission(
    db: Session, user: User, image_bytes: bytes, mime: str, note: str | None
) -> UserScholarshipSubmission:
    if not image_bytes:
        raise ServiceError("File gambar kosong.", 422, "empty_file")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ServiceError(
            f"Ukuran gambar melebihi {MAX_IMAGE_BYTES // 1_000_000} MB.", 413, "file_too_large"
        )
    if mime not in ALLOWED_IMAGE_TYPES:
        raise ServiceError(
            "Format gambar harus PNG, JPEG, atau WEBP.", 422, "invalid_image_type"
        )

    submission = UserScholarshipSubmission(
        user_id=user.id,
        note=(note or "").strip()[:1000] or None,
        image_mime=mime,
        image_data=image_bytes,
        status="pending",
    )
    db.add(submission)
    db.commit()
    return submission


def get_submission(db: Session, submission_id: str) -> UserScholarshipSubmission:
    submission = db.execute(
        select(UserScholarshipSubmission).where(UserScholarshipSubmission.id == submission_id)
    ).scalar_one_or_none()
    if submission is None:
        raise ServiceError("Kiriman tidak ditemukan.", 404, "not_found")
    return submission


def payload(submission: UserScholarshipSubmission, username: str | None = None) -> dict[str, Any]:
    return {
        "id": submission.id,
        "username": username,
        "note": submission.note,
        "status": submission.status,
        "reason": submission.reason,
        "scholarship_id": submission.scholarship_id,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
        "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
        "image_url": f"/admin/submissions/{submission.id}/image",
        "image_mime": submission.image_mime,
    }


def list_for_user(db: Session, user: User) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(UserScholarshipSubmission)
            .where(UserScholarshipSubmission.user_id == user.id)
            .order_by(UserScholarshipSubmission.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [payload(row, user.username) for row in rows]


def list_admin(db: Session, status: str | None = None) -> list[dict[str, Any]]:
    stmt = select(UserScholarshipSubmission, User).join(
        User, User.id == UserScholarshipSubmission.user_id
    )
    if status:
        stmt = stmt.where(UserScholarshipSubmission.status == status)
    rows = db.execute(stmt.order_by(UserScholarshipSubmission.created_at.desc())).all()
    return [payload(submission, user.username) for submission, user in rows]


def process(
    db: Session,
    submission: UserScholarshipSubmission,
    status: str,
    reason: str | None,
    admin_id: str | None,
    scholarship_id: str | None = None,
) -> UserScholarshipSubmission:
    if status not in {"processed", "rejected"}:
        raise ServiceError("Status harus 'processed' atau 'rejected'.", 422, "invalid_status")
    if submission.status != "pending":
        raise ServiceError("Kiriman ini sudah diproses.", 409, "already_reviewed")

    submission.status = status
    submission.reason = (reason or "").strip() or None
    submission.scholarship_id = scholarship_id
    submission.reviewed_at = datetime.now(timezone.utc)
    submission.reviewed_by = admin_id
    db.commit()
    return submission


def stats(db: Session) -> dict[str, int]:
    from sqlalchemy import func

    total = db.execute(select(func.count()).select_from(UserScholarshipSubmission)).scalar_one()
    pending = db.execute(
        select(func.count())
        .select_from(UserScholarshipSubmission)
        .where(UserScholarshipSubmission.status == "pending")
    ).scalar_one()
    return {"total": total, "pending": pending}
