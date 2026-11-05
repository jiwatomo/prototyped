"""Master Tag helpers: allowed lists, aliases, hierarchy and validation."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Tag, TagAlias, TagCategory

CITY_TAG_MAP = {
    "palembang": "geo.sumatera_selatan",
    "sumatera selatan": "geo.sumatera_selatan",
    "sumatra selatan": "geo.sumatera_selatan",
    "padang": "geo.sumatera_barat",
    "sumatera barat": "geo.sumatera_barat",
    "bandung": "geo.jawa_barat",
    "jawa barat": "geo.jawa_barat",
    "jakarta": "geo.jakarta",
    "indonesia": "geo.indonesia",
}

MAJOR_TAG_MAP = {
    "informatika": "field.informatics",
    "sistem informasi": "field.information_systems",
    "teknik": "field.engineering",
    "kedokteran": "field.medicine",
    "ekonomi": "field.economics",
    "hukum": "field.law",
    "pendidikan": "field.education",
}


class TagGraph:
    """Read-only view of the Master Tag hierarchy."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.by_id = {row["id"]: row for row in rows}
        self.by_slug = {row["slug"]: row for row in rows}

    def ancestors(self, tag_id: str) -> list[str]:
        chain: list[str] = []
        current = self.by_id.get(tag_id)
        seen: set[str] = set()
        while current and current.get("parent_id") and current["parent_id"] not in seen:
            seen.add(current["parent_id"])
            chain.append(current["parent_id"])
            current = self.by_id.get(current["parent_id"])
        return chain

    def is_same_or_descendant(self, candidate_id: str, ancestor_id: str) -> bool:
        if candidate_id == ancestor_id:
            return True
        return ancestor_id in self.ancestors(candidate_id)

    def depth(self, tag_id: str) -> int:
        return len(self.ancestors(tag_id))


def load_tag_rows(db: Session, active_only: bool = True) -> list[dict[str, Any]]:
    stmt = select(Tag)
    if active_only:
        stmt = stmt.where(Tag.is_active.is_(True))
    rows = db.execute(stmt.order_by(Tag.slug)).scalars().all()
    return [
        {
            "id": tag.id,
            "slug": tag.slug,
            "name": tag.name,
            "parent_id": tag.parent_id,
            "category_id": tag.category_id,
            "description": tag.description,
            "is_active": tag.is_active,
        }
        for tag in rows
    ]


def build_graph(db: Session, active_only: bool = True) -> TagGraph:
    return TagGraph(load_tag_rows(db, active_only=active_only))


def allowed_tags(db: Session) -> list[dict[str, Any]]:
    """Shape passed to AI adapters: minimal, non-secret tag descriptors."""
    categories = {
        c.id: c.code for c in db.execute(select(TagCategory)).scalars().all()
    }
    return [
        {
            "slug": row["slug"],
            "name": row["name"],
            "category": categories.get(row["category_id"], ""),
        }
        for row in load_tag_rows(db, active_only=True)
    ]


def alias_map(db: Session) -> dict[str, str]:
    aliases = db.execute(select(TagAlias)).scalars().all()
    tag_slugs = {t.id: t.slug for t in db.execute(select(Tag)).scalars().all()}
    return {a.alias: tag_slugs[a.tag_id] for a in aliases if a.tag_id in tag_slugs}


def tags_from_facts(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic tag derivation from confirmed facts (no AI involved)."""
    suggested: list[dict[str, Any]] = []
    level = facts.get("education_level")
    if level:
        suggested.append(
            {
                "slug": f"edu.level.{str(level).lower()}",
                "context": "profile",
                "source": "system",
                "evidence": {"field_key": "education_level", "value": level},
            }
        )
    major = (facts.get("major") or "").lower()
    for keyword, slug in MAJOR_TAG_MAP.items():
        if keyword in major:
            suggested.append(
                {
                    "slug": slug,
                    "context": "profile",
                    "source": "system",
                    "evidence": {"field_key": "major", "value": facts.get("major")},
                }
            )
            break
    domicile = (facts.get("domicile") or "").lower()
    for keyword, slug in CITY_TAG_MAP.items():
        if keyword in domicile:
            suggested.append(
                {
                    "slug": slug,
                    "context": "location",
                    "source": "system",
                    "evidence": {"field_key": "domicile", "value": facts.get("domicile")},
                }
            )
            break
    if facts.get("toefl_score"):
        suggested.append(
            {
                "slug": "lang.english",
                "context": "language",
                "source": "system",
                "evidence": {"field_key": "toefl_score", "value": facts.get("toefl_score")},
            }
        )
    return suggested


def find_tag(db: Session, slug: str) -> Tag | None:
    return db.execute(select(Tag).where(Tag.slug == slug)).scalar_one_or_none()
