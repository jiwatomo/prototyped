"""Deterministic tag relevance engine (no LLM)."""
from __future__ import annotations

from typing import Any

from app.services.tagging_service import TagGraph

# user context -> compatible scholarship contexts
COMPATIBLE_CONTEXTS: dict[str, set[str]] = {
    "profile": {"target_audience", "eligibility"},
    "interest": {"field"},
    "achievement": {"achievement"},
    "preference": {"benefit", "program", "obligation"},
    "location": {"location"},
    "language": {"eligibility"},
    "economic": {"eligibility", "target_audience"},
}

UNIVERSAL_USER_CONTEXTS = {"profile", "interest", "achievement", "preference", "location", "language", "economic"}


def contexts_compatible(user_context: str, scholarship_context: str) -> bool:
    return scholarship_context in COMPATIBLE_CONTEXTS.get(user_context, set())


def eligible_user_tags(
    user_tags: list[dict[str, Any]], scholarship_tags: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """User tags whose context can be compared to at least one scholarship tag."""
    scholarship_contexts = {t["context"] for t in scholarship_tags}
    result = []
    for tag in user_tags:
        ctx = tag.get("context", "")
        if any(contexts_compatible(ctx, sc) for sc in scholarship_contexts):
            result.append(tag)
    return result


def match_tags(
    user_tags: list[dict[str, Any]],
    scholarship_tags: list[dict[str, Any]],
    graph: TagGraph | None = None,
) -> dict[str, Any]:
    """Score relevance between confirmed user tags and approved scholarship tags.

    `user_tags` items: {tag_id, slug, context, weight}
    `scholarship_tags` items: {tag_id, slug, context, weight}
    The score is relevance, never an admission probability.
    """
    comparable = eligible_user_tags(user_tags, scholarship_tags)
    total_weight = sum(float(t.get("weight") or 1.0) for t in comparable)

    pairs: list[dict[str, Any]] = []
    counted_ids: set[str] = set()
    matched_weight = 0.0

    for user_tag in sorted(
        comparable, key=lambda t: (graph.depth(t["tag_id"]) if graph else 0)
    ):
        match = _find_match(user_tag, scholarship_tags, graph)
        if not match:
            continue
        # Avoid double counting a child and its ancestor.
        if graph and any(
            graph.is_same_or_descendant(user_tag["tag_id"], parent) for parent in counted_ids
        ):
            pairs.append(
                {
                    "user_slug": user_tag["slug"],
                    "scholarship_slug": match["slug"],
                    "weight": float(user_tag.get("weight") or 1.0),
                    "counted": False,
                }
            )
            continue
        counted_ids.add(user_tag["tag_id"])
        matched_weight += float(user_tag.get("weight") or 1.0)
        pairs.append(
            {
                "user_slug": user_tag["slug"],
                "scholarship_slug": match["slug"],
                "weight": float(user_tag.get("weight") or 1.0),
                "counted": True,
            }
        )

    if total_weight <= 0:
        score = None
        status = "insufficient_preferences"
    else:
        score = round(matched_weight / total_weight * 100, 1)
        status = "scored"

    matched_slugs = [p["user_slug"] for p in pairs if p["counted"]]
    matched_user_ids = {p["user_slug"] for p in pairs if p["counted"]}
    return {
        "relevance_score": score,
        "score_status": status,
        "matched_tags": matched_slugs,
        "matched_pairs": pairs,
        "unmatched_user_tags": [
            t["slug"] for t in comparable if t["slug"] not in matched_user_ids
        ],
        "reasons": _reasons(pairs, matched_slugs),
    }


def _find_match(
    user_tag: dict[str, Any],
    scholarship_tags: list[dict[str, Any]],
    graph: TagGraph | None,
) -> dict[str, Any] | None:
    for sch_tag in scholarship_tags:
        if not contexts_compatible(user_tag["context"], sch_tag["context"]):
            continue
        if user_tag["tag_id"] == sch_tag["tag_id"]:
            return sch_tag
        if graph and (
            graph.is_same_or_descendant(user_tag["tag_id"], sch_tag["tag_id"])
            or graph.is_same_or_descendant(sch_tag["tag_id"], user_tag["tag_id"])
        ):
            return sch_tag
    return None


def _reasons(pairs: list[dict[str, Any]], matched_slugs: list[str]) -> list[str]:
    if not matched_slugs:
        return ["Tidak ada tag pengguna yang cocok dengan tag beasiswa pada konteks yang kompatibel."]
    reasons = [
        f"Tag {p['user_slug']} cocok dengan {p['scholarship_slug']} (bobot {p['weight']:.2f})."
        for p in pairs
        if p["counted"]
    ]
    deduped = [p for p in pairs if not p["counted"]]
    if deduped:
        reasons.append(
            "Tag anak dilewati agar tidak dihitung ganda dengan leluhurnya: "
            + ", ".join(p["user_slug"] for p in deduped)
        )
    reasons.append("Skor relevansi bukan probabilitas diterima beasiswa.")
    return reasons
