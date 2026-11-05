"""Recommendation assembly: matching + eligibility + gap analysis + ordering."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Scholarship,
    ScholarshipRequirement,
    ScholarshipRequirementGroup,
    ScholarshipTag,
    StudentProfile,
    Tag,
    User,
    UserScholarshipBookmark,
    UserTag,
)
from app.services import eligibility_service, matching_service
from app.services.tagging_service import TagGraph, build_graph

ORDER = {"eligible": 0, "potentially_eligible": 1, "not_eligible": 2}


def confirmed_user_tag_rows(db: Session, user: User) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(UserTag, Tag)
            .join(Tag, Tag.id == UserTag.tag_id)
            .where(
                UserTag.user_id == user.id,
                UserTag.confirmation_status == "confirmed",
                Tag.is_active.is_(True),
            )
        )
        .all()
    )
    return [
        {
            "tag_id": tag.id,
            "slug": tag.slug,
            "context": user_tag.context,
            "weight": float(user_tag.weight or 1.0),
        }
        for user_tag, tag in rows
    ]


def scholarship_tags(db: Session, scholarship_id: str) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(ScholarshipTag, Tag)
            .join(Tag, Tag.id == ScholarshipTag.tag_id)
            .where(
                ScholarshipTag.scholarship_id == scholarship_id,
                ScholarshipTag.review_status == "approved",
                Tag.is_active.is_(True),
            )
        )
        .all()
    )
    return [
        {
            "tag_id": tag.id,
            "slug": tag.slug,
            "name": tag.name,
            "context": sch_tag.context,
            "weight": float(sch_tag.weight or 1.0),
            "evidence": sch_tag.evidence,
        }
        for sch_tag, tag in rows
    ]


def requirement_groups(db: Session, scholarship_id: str) -> list[dict[str, Any]]:
    groups = (
        db.execute(
            select(ScholarshipRequirementGroup)
            .where(ScholarshipRequirementGroup.scholarship_id == scholarship_id)
            .order_by(ScholarshipRequirementGroup.name)
        )
        .scalars()
        .all()
    )
    result = []
    for group in groups:
        requirements = (
            db.execute(
                select(ScholarshipRequirement, Tag)
                .outerjoin(Tag, Tag.id == ScholarshipRequirement.tag_id)
                .where(ScholarshipRequirement.group_id == group.id)
            )
            .all()
        )
        result.append(
            {
                "id": group.id,
                "name": group.name,
                "operator": group.operator,
                "is_mandatory": group.is_mandatory,
                "requirements": [
                    {
                        "id": req.id,
                        "field_key": req.field_key,
                        "operator": req.operator,
                        "value": req.value_json,
                        "unit": req.unit,
                        "tag_id": req.tag_id,
                        "tag_slug": tag.slug if tag else None,
                        "is_mandatory": req.is_mandatory,
                        "description": req.description,
                        "source_reference": req.source_reference,
                    }
                    for req, tag in requirements
                ],
            }
        )
    return result


def _explain(entry: dict[str, Any], scholarship: Scholarship) -> str:
    score = entry["relevance_score"]
    status = entry["eligibility_status"]
    parts: list[str] = []
    if score is None:
        parts.append("Belum cukup preferensi untuk menghitung skor relevansi.")
    else:
        parts.append(f"Skor relevansi profil {score:.1f}%.")
    failed = [r for r in entry["requirements"] if r["status"] == "not_met"]
    unknown = [r for r in entry["requirements"] if r["status"] == "unknown"]
    if status == "eligible":
        parts.append("Seluruh persyaratan wajib terpenuhi sesuai data profil yang dikonfirmasi.")
    elif status == "not_eligible":
        parts.append(
            "Belum memenuhi persyaratan wajib: "
            + "; ".join(r["description"] for r in failed)
            + "."
        )
    else:
        parts.append(
            "Persyaratan wajib yang belum dapat dinilai: "
            + "; ".join(r["description"] for r in unknown)
            + "."
        )
    parts.append("Skor relevansi bukan probabilitas diterima beasiswa.")
    return " ".join(parts)


def build_entry(
    db: Session,
    profile: StudentProfile,
    scholarship: Scholarship,
    user_tags: list[dict[str, Any]],
    graph: TagGraph,
) -> dict[str, Any]:
    sch_tags = scholarship_tags(db, scholarship.id)
    groups = requirement_groups(db, scholarship.id)
    match = matching_service.match_tags(user_tags, sch_tags, graph)
    eligibility = eligibility_service.evaluate(groups, _profile_facts(profile), user_tags, graph)

    entry = {
        "scholarship_id": scholarship.id,
        "name": scholarship.name,
        "organizer": scholarship.organizer,
        "description": scholarship.description,
        "verification_status": scholarship.verification_status,
        "application_status": _application_status(scholarship),
        "application_start": scholarship.application_start,
        "application_deadline": scholarship.application_deadline,
        "benefits": scholarship.benefits or [],
        "education_levels": scholarship.education_levels or [],
        "relevance_score": match["relevance_score"],
        "score_status": match["score_status"],
        "matched_tags": match["matched_tags"],
        "matched_pairs": match["matched_pairs"],
        "unmatched_user_tags": match["unmatched_user_tags"],
        "matching_reasons": match["reasons"],
        "scholarship_tags": [
            {"slug": t["slug"], "name": t["name"], "context": t["context"]}
            for t in sch_tags
        ],
        "eligibility_status": eligibility["eligibility_status"],
        "requirements": eligibility["requirements"],
        "requirement_groups": eligibility["groups"],
        "requirement_summary": eligibility["summary"],
        "explanation": "",
        "is_demo": scholarship.is_demo,
        "created_at": scholarship.created_at.isoformat() if scholarship.created_at else None,
    }
    entry["explanation"] = _explain(entry, scholarship)
    return entry


def _profile_facts(profile: StudentProfile) -> dict[str, Any]:
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


def _application_status(scholarship: Scholarship) -> str:
    """Derived from dates only. `verified` never implies an open application."""
    deadline = scholarship.application_deadline
    if not deadline:
        return "unknown"
    from datetime import date

    parsed = None
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            parsed = datetime.strptime(deadline.strip(), fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return "unknown"
    today = date.today()
    if parsed < today:
        return "closed"
    start = scholarship.application_start
    if start:
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
            try:
                start_date = datetime.strptime(start.strip(), fmt).date()
                return "open" if start_date <= today <= parsed else "upcoming"
            except ValueError:
                continue
    return "open"


def compute(db: Session, user: User, profile: StudentProfile) -> dict[str, Any]:
    graph = build_graph(db)
    user_tags = confirmed_user_tag_rows(db, user)
    scholarships = (
        db.execute(
            select(Scholarship).where(Scholarship.verification_status == "verified")
        )
        .scalars()
        .all()
    )
    results = [build_entry(db, profile, s, user_tags, graph) for s in scholarships]
    results.sort(
        key=lambda e: (
            ORDER.get(e["eligibility_status"], 3),
            -(e["relevance_score"] if e["relevance_score"] is not None else -1),
        )
    )

    bookmarks = dict(
        db.execute(
            select(
                UserScholarshipBookmark.scholarship_id,
                func.count(),
            ).group_by(UserScholarshipBookmark.scholarship_id)
        ).all()
    )

    def due_key(entry: dict) -> str:
        deadline = (entry.get("application_deadline") or "").strip()
        parsed = None
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
            try:
                parsed = datetime.strptime(deadline, fmt).date()
                break
            except ValueError:
                continue
        return parsed.isoformat() if parsed else "9999-12-31"

    hot_pool = sorted(
        results,
        key=lambda e: (
            0 if e["application_status"] in {"open", "upcoming"} else 1,
            -int(bookmarks.get(e["scholarship_id"], 0)),
            due_key(e),
            -(e["relevance_score"] if e["relevance_score"] is not None else -1),
        ),
    )
    hot = hot_pool[:3]
    recent = sorted(
        results, key=lambda e: e.get("created_at") or "", reverse=True
    )[:3]

    return {
        "user_id": user.id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_status": profile.profile_status,
        "counts": {
            "total": len(results),
            "eligible": sum(1 for r in results if r["eligibility_status"] == "eligible"),
            "potentially_eligible": sum(
                1 for r in results if r["eligibility_status"] == "potentially_eligible"
            ),
            "not_eligible": sum(
                1 for r in results if r["eligibility_status"] == "not_eligible"
            ),
        },
        "results": results,
        "hot": hot,
        "recent": recent,
    }
