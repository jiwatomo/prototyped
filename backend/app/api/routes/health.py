"""Health, demo session and Master Tag endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import Tag, TagCategory, User
from app.services.ai.factory import get_ai_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Public endpoint: configuration state only, never secrets."""
    ai = get_ai_service()
    db_ok = True
    try:
        db.execute(select(func.count()).select_from(Tag))
    except Exception:  # noqa: BLE001 - health must never raise
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "ai": ai.describe(),
    }


@router.get("/demo/session")
def demo_session(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    users = db.execute(select(User).order_by(User.username)).scalars().all()
    return {
        "mode_note": "Pergantian mode pengguna/admin dilakukan melalui login demo, bukan autentikasi produksi.",
        "data_label": "DATA DEMO SINTETIS — BUKAN INFORMASI BEASISWA NYATA",
        "personas": [
            {"username": u.username, "display_name": u.display_name, "role": u.role}
            for u in users
        ],
    }


@router.get("/tags")
def list_tags(
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    stmt = (
        select(Tag, TagCategory)
        .join(TagCategory, TagCategory.id == Tag.category_id)
        .where(Tag.is_active.is_(True))
    )
    if category:
        stmt = stmt.where(TagCategory.code == category.upper())
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where((Tag.slug.ilike(pattern)) | (Tag.name.ilike(pattern)))
    rows = db.execute(stmt.order_by(TagCategory.code, Tag.slug)).all()
    return {
        "count": len(rows),
        "tags": [
            {
                "id": tag.id,
                "slug": tag.slug,
                "name": tag.name,
                "category": cat.code,
                "category_name": cat.name,
                "parent_id": tag.parent_id,
                "description": tag.description,
            }
            for tag, cat in rows
        ],
    }
