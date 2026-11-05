"""User-facing screenshot submission for scholarship info."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.services import submission_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", status_code=201)
async def submit_scholarship(
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role != "student":
        raise ServiceError("Hanya pengguna yang dapat mengirim info beasiswa.", 403, "forbidden")

    content = await file.read()
    submission = submission_service.create_submission(
        db, user, content, file.content_type or "", note
    )
    return submission_service.payload(submission, user.username)


@router.get("/me")
def my_submissions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    rows = submission_service.list_for_user(db, user)
    return {"count": len(rows), "submissions": rows}
