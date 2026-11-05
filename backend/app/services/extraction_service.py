"""Scholarship extraction pipeline: source -> AI -> validated draft -> DB."""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    ExtractionJob,
    Scholarship,
    ScholarshipRequirement,
    ScholarshipRequirementGroup,
    ScholarshipSource,
    ScholarshipTag,
    Tag,
)
from app.schemas.ai import ManualScholarshipRequest, ScholarshipExtraction
from app.services import tagging_service
from app.services.ai.factory import AIService, AIUnavailableError
from app.services.errors import ServiceError

URL_FETCH_TIMEOUT = 15.0
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


async def fetch_url_text(url: str) -> str:
    if not re.match(r"^https?://", url):
        raise ServiceError("URL harus diawali http:// atau https://.", 422, "invalid_url")
    try:
        async with httpx.AsyncClient(timeout=URL_FETCH_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "scholarship-prototype/1.0"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ServiceError(
            "Gagal mengambil konten URL. Tempelkan teks sumber secara manual.",
            502,
            "url_fetch_failed",
        ) from exc
    html = response.text
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return _WS_RE.sub("\n\n", text).strip()


def extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ServiceError("Pembaca PDF tidak tersedia di server.", 500, "pdf_unavailable") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - surface a clear message, never a stack trace
        raise ServiceError("File PDF tidak dapat dibaca.", 422, "invalid_pdf") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise ServiceError(
            "PDF tidak mengandung teks (kemungkinan hasil scan). Prototipe tidak mendukung OCR; "
            "silakan tempelkan teks sumber.",
            422,
            "pdf_without_text",
        )
    return text


async def create_extraction(
    db: Session,
    ai: AIService,
    source_type: str,
    source_text: str | None = None,
    source_url: str | None = None,
    pdf_bytes: bytes | None = None,
    created_by: str | None = None,
) -> ExtractionJob:
    text = ""
    if pdf_bytes is not None:
        if len(pdf_bytes) > settings.max_pdf_bytes:
            raise ServiceError(
                f"Ukuran PDF melebihi batas {settings.max_pdf_bytes // 1_000_000} MB.",
                413,
                "pdf_too_large",
            )
        text = extract_pdf_text(pdf_bytes)
        source_type = "pdf"
    elif source_url:
        text = await fetch_url_text(source_url)
        source_type = "url"
    elif source_text:
        text = source_text.strip()
    else:
        raise ServiceError(
            "Salah satu dari source_url, source_text, atau file PDF wajib diisi.",
            422,
            "missing_source",
        )

    if not text.strip():
        raise ServiceError("Teks sumber kosong.", 422, "empty_source")
    if len(text) > settings.ai_max_input_chars:
        raise ServiceError(
            f"Teks sumber melebihi batas {settings.ai_max_input_chars} karakter.",
            422,
            "source_too_long",
        )

    job = ExtractionJob(
        source_type=source_type,
        source_url=source_url,
        source_text=text[: settings.ai_max_input_chars],
        status="processing",
        started_at=datetime.now(timezone.utc),
        created_by=created_by,
    )
    db.add(job)
    db.commit()

    try:
        extraction, meta = await ai.extract_scholarship(
            text, {"source_type": source_type, "source_url": source_url}
        )
    except AIUnavailableError as exc:
        job.status = "failed"
        job.error = exc.message
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise ServiceError(exc.message, 503, "ai_unavailable") from exc

    scholarship, unknown_slugs = _persist_extraction(db, job, extraction)
    job.status = "completed"
    job.finished_at = datetime.now(timezone.utc)
    job.provider_mode = meta.provider_mode
    job.provider_name = meta.provider_name
    job.model = meta.model
    job.fallback_reason = meta.fallback_reason
    job.scholarship_id = scholarship.id
    job.result_json = extraction.model_dump()
    job.result_json["unknown_tag_slugs"] = unknown_slugs
    db.commit()
    return job


def _persist_extraction(
    db: Session, job: ExtractionJob, extraction: ScholarshipExtraction
) -> tuple[Scholarship, list[str]]:
    info = extraction.scholarship
    scholarship = Scholarship(
        name=info.name.strip() or "Beasiswa Tanpa Judul",
        organizer=info.organizer.strip(),
        description=info.description,
        education_levels=info.education_levels,
        benefits=info.benefits,
        application_start=info.application_start,
        application_deadline=info.application_deadline,
        verification_status="pending_verification",
        is_demo=True,
    )
    db.add(scholarship)
    db.flush()

    unknown_slugs: list[str] = []
    for tag_data in extraction.suggested_tags:
        tag = tagging_service.find_tag(db, tag_data.slug)
        if tag is None:
            unknown_slugs.append(tag_data.slug)
            continue
        db.add(
            ScholarshipTag(
                scholarship_id=scholarship.id,
                tag_id=tag.id,
                context=tag_data.context,
                assignment_source="ai",
                confidence=tag_data.confidence,
                review_status="pending",
                weight=1.0,
                evidence={"quote": tag_data.evidence, "provider_mode": job.provider_mode},
            )
        )

    groups: dict[tuple[str, str, bool], ScholarshipRequirementGroup] = {}
    for req in extraction.requirements:
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
                unknown_slugs.append(req.tag_slug)
            else:
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

    db.add(
        ScholarshipSource(
            scholarship_id=scholarship.id,
            extraction_job_id=job.id,
            source_type=job.source_type,
            source_url=job.source_url,
            raw_text=(job.source_text or "")[:5000],
        )
    )
    db.flush()
    return scholarship, unknown_slugs



def create_manual_scholarship(
    db: Session, data: ManualScholarshipRequest, admin_id: str | None
) -> ExtractionJob:
    """Admin-typed scholarship: same tables and review path as an AI extraction."""
    now = datetime.now(timezone.utc)
    job = ExtractionJob(
        source_type="manual",
        status="processing",
        started_at=now,
        created_by=admin_id,
        provider_mode="manual",
        provider_name="manual_entry",
    )
    db.add(job)
    db.commit()

    resolved: list[tuple[Tag, object]] = []
    for tag_input in data.tags:
        tag = tagging_service.find_tag(db, tag_input.slug)
        if tag is None:
            raise ServiceError(f"Tag tidak dikenal: {tag_input.slug}", 422, "unknown_tag")
        resolved.append((tag, tag_input))

    scholarship = Scholarship(
        name=data.name,
        organizer=data.organizer.strip(),
        description=data.description,
        education_levels=data.education_levels,
        benefits=data.benefits,
        application_start=data.application_start,
        application_deadline=data.application_deadline,
        verification_status="pending_verification",
        is_demo=True,
    )
    db.add(scholarship)
    db.flush()

    for tag, tag_input in resolved:
        db.add(
            ScholarshipTag(
                scholarship_id=scholarship.id,
                tag_id=tag.id,
                context=tag_input.context,
                assignment_source="admin",
                confidence=None,
                review_status="pending",
                weight=tag_input.weight,
                evidence={"note": "Input manual admin", "source": "admin_form"},
            )
        )

    mandatory = [r for r in data.requirements if r.is_mandatory]
    optional = [r for r in data.requirements if not r.is_mandatory]
    for group_name, operator, is_mandatory, rows in (
        ("Persyaratan Utama", "AND", True, mandatory),
        ("Persyaratan Tambahan", "AND", False, optional),
    ):
        if not rows:
            continue
        group = ScholarshipRequirementGroup(
            scholarship_id=scholarship.id,
            name=group_name,
            operator=operator,
            is_mandatory=is_mandatory,
        )
        db.add(group)
        db.flush()
        for row in rows:
            tag_id = None
            if row.tag_slug:
                tag = tagging_service.find_tag(db, row.tag_slug)
                if tag is None:
                    raise ServiceError(f"Tag tidak dikenal: {row.tag_slug}", 422, "unknown_tag")
                tag_id = tag.id
            if not row.field_key and not tag_id:
                raise ServiceError(
                    "Setiap persyaratan harus memiliki field atau tag.", 422, "invalid_requirement"
                )
            db.add(
                ScholarshipRequirement(
                    group_id=group.id,
                    tag_id=tag_id,
                    field_key=row.field_key,
                    operator=row.operator,
                    value_json=row.value,
                    unit=row.unit,
                    is_mandatory=row.is_mandatory,
                    source_reference="Input manual admin",
                    description=row.description,
                )
            )

    db.add(
        ScholarshipSource(
            scholarship_id=scholarship.id,
            extraction_job_id=job.id,
            source_type="manual",
            source_url=None,
            raw_text=data.description or f"Input manual admin: {data.name}",
        )
    )

    job.scholarship_id = scholarship.id
    job.status = "completed"
    job.finished_at = datetime.now(timezone.utc)
    job.result_json = {**data.model_dump(), "unknown_tag_slugs": []}
    db.commit()
    return job


def job_payload(db: Session, job: ExtractionJob) -> dict[str, Any]:
    scholarship = (
        db.execute(select(Scholarship).where(Scholarship.id == job.scholarship_id)).scalar_one_or_none()
        if job.scholarship_id
        else None
    )
    tags: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    if scholarship is not None:
        rows = (
            db.execute(
                select(ScholarshipTag, Tag)
                .join(Tag, Tag.id == ScholarshipTag.tag_id)
                .where(ScholarshipTag.scholarship_id == scholarship.id)
            )
            .all()
        )
        tags = [
            {
                "slug": tag.slug,
                "name": tag.name,
                "context": sch_tag.context,
                "confidence": sch_tag.confidence,
                "review_status": sch_tag.review_status,
                "weight": sch_tag.weight,
                "evidence": sch_tag.evidence,
                "assignment_source": sch_tag.assignment_source,
            }
            for sch_tag, tag in rows
        ]
        groups = (
            db.execute(
                select(ScholarshipRequirementGroup).where(
                    ScholarshipRequirementGroup.scholarship_id == scholarship.id
                )
            )
            .scalars()
            .all()
        )
        for group in groups:
            reqs = (
                db.execute(
                    select(ScholarshipRequirement, Tag)
                    .outerjoin(Tag, Tag.id == ScholarshipRequirement.tag_id)
                    .where(ScholarshipRequirement.group_id == group.id)
                )
                .all()
            )
            for req, tag in reqs:
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
        sources = [
            {
                "source_type": s.source_type,
                "source_url": s.source_url,
                "checked_at": s.checked_at.isoformat() if s.checked_at else None,
                "excerpt": (s.raw_text or "")[:300],
            }
            for s in scholarship.sources
        ]

    return {
        "extraction_id": job.id,
        "status": job.status,
        "source_type": job.source_type,
        "source_url": job.source_url,
        "source_excerpt": (job.source_text or "")[:500],
        "error": job.error,
        "provider_mode": job.provider_mode,
        "provider_name": job.provider_name,
        "model": job.model,
        "fallback_reason": job.fallback_reason,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "scholarship": (
            {
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
            }
            if scholarship
            else None
        ),
        "tags": tags,
        "requirements": requirements,
        "sources": sources,
        "unknown_tag_slugs": (job.result_json or {}).get("unknown_tag_slugs", []),
    }
