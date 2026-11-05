"""Deterministic eligibility engine: requirements, groups and gap analysis."""
from __future__ import annotations

from typing import Any

from app.services.tagging_service import TagGraph

STATUS_MET = "met"
STATUS_NOT_MET = "not_met"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_APPLICABLE = "not_applicable"

ELIGIBLE = "eligible"
POTENTIALLY_ELIGIBLE = "potentially_eligible"
NOT_ELIGIBLE = "not_eligible"


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ".").strip())
        except ValueError:
            return None
    return None


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower()


def _compare(actual: Any, operator: str, required: Any) -> str:
    """Return met / not_met / unknown for one operator comparison."""
    if actual is None or actual == "":
        return STATUS_UNKNOWN

    if operator in {"in", "not_in"}:
        options = required if isinstance(required, list) else [required]
        if any(_normalize_text(actual) == _normalize_text(o) for o in options):
            return STATUS_MET if operator == "in" else STATUS_NOT_MET
        return STATUS_NOT_MET if operator == "in" else STATUS_MET

    if operator == "contains":
        if isinstance(actual, (list, tuple, set)):
            hit = any(_normalize_text(required) in _normalize_text(item) for item in actual)
        else:
            hit = _normalize_text(required) in _normalize_text(actual)
        return STATUS_MET if hit else STATUS_NOT_MET

    if operator == "between":
        if not isinstance(required, (list, tuple)) or len(required) != 2:
            return STATUS_UNKNOWN
        number = _to_number(actual)
        low, high = _to_number(required[0]), _to_number(required[1])
        if number is None or low is None or high is None:
            return STATUS_UNKNOWN
        return STATUS_MET if low <= number <= high else STATUS_NOT_MET

    if operator in {"gt", "gte", "lt", "lte"}:
        number, target = _to_number(actual), _to_number(required)
        if number is None or target is None:
            return STATUS_UNKNOWN
        checks = {
            "gt": number > target,
            "gte": number >= target,
            "lt": number < target,
            "lte": number <= target,
        }
        return STATUS_MET if checks[operator] else STATUS_NOT_MET

    if operator in {"eq", "neq"}:
        number, target = _to_number(actual), _to_number(required)
        if number is not None and target is not None:
            equal = abs(number - target) < 1e-9
        else:
            equal = _normalize_text(actual) == _normalize_text(required)
        if operator == "eq":
            return STATUS_MET if equal else STATUS_NOT_MET
        return STATUS_MET if not equal else STATUS_NOT_MET

    return STATUS_UNKNOWN


def evaluate_requirement(
    requirement: dict[str, Any],
    profile: dict[str, Any],
    confirmed_tag_ids: set[str],
    graph: TagGraph | None = None,
) -> dict[str, Any]:
    tag_id = requirement.get("tag_id")
    field_key = requirement.get("field_key")
    operator = (requirement.get("operator") or "eq").lower()
    required = requirement.get("value")

    actual: Any = None
    if tag_id:
        satisfied = tag_id in confirmed_tag_ids
        if not satisfied and graph:
            satisfied = any(graph.is_same_or_descendant(tid, tag_id) for tid in confirmed_tag_ids)
        status = STATUS_MET if satisfied else STATUS_UNKNOWN
        actual = "Sesuai profil" if satisfied else None
    elif field_key:
        actual = profile.get(field_key)
        status = _compare(actual, operator, required)
    else:
        status = STATUS_UNKNOWN

    return {
        "id": requirement.get("id"),
        "description": requirement.get("description")
        or (field_key or requirement.get("tag_slug") or "Persyaratan"),
        "field_key": field_key,
        "tag_slug": requirement.get("tag_slug"),
        "operator": operator,
        "required_value": required,
        "actual": actual,
        "unit": requirement.get("unit"),
        "status": status,
        "is_mandatory": bool(requirement.get("is_mandatory", True)),
        "group": requirement.get("group", "Persyaratan"),
        "group_operator": requirement.get("group_operator", "AND"),
        "group_is_mandatory": bool(requirement.get("group_is_mandatory", True)),
        "source_reference": requirement.get("source_reference"),
    }


def _group_status(group: dict[str, Any], results: list[dict[str, Any]]) -> str:
    statuses = [r["status"] for r in results]
    if not statuses:
        return STATUS_UNKNOWN
    operator = (group.get("operator") or "AND").upper()
    if operator == "OR":
        if STATUS_MET in statuses:
            return STATUS_MET
        if STATUS_UNKNOWN in statuses:
            return STATUS_UNKNOWN
        return STATUS_NOT_MET
    if STATUS_NOT_MET in statuses:
        return STATUS_NOT_MET
    if STATUS_UNKNOWN in statuses:
        return STATUS_UNKNOWN
    return STATUS_MET


def evaluate(
    groups: list[dict[str, Any]],
    profile: dict[str, Any],
    confirmed_tags: list[dict[str, Any]],
    graph: TagGraph | None = None,
) -> dict[str, Any]:
    """Evaluate all requirement groups and derive the overall status."""
    confirmed_tag_ids = {t["tag_id"] for t in confirmed_tags}
    evaluated_groups: list[dict[str, Any]] = []
    all_requirements: list[dict[str, Any]] = []

    for group in groups:
        results = [
            evaluate_requirement(req, profile, confirmed_tag_ids, graph)
            for req in group.get("requirements", [])
        ]
        for result in results:
            result["group"] = group.get("name", "Persyaratan")
            result["group_operator"] = (group.get("operator") or "AND").upper()
            result["group_is_mandatory"] = bool(group.get("is_mandatory", True))
        all_requirements.extend(results)
        evaluated_groups.append(
            {
                "id": group.get("id"),
                "name": group.get("name", "Persyaratan"),
                "operator": (group.get("operator") or "AND").upper(),
                "is_mandatory": bool(group.get("is_mandatory", True)),
                "status": _group_status(group, results),
                "requirements": results,
            }
        )

    mandatory = [g for g in evaluated_groups if g["is_mandatory"]]
    if any(g["status"] == STATUS_NOT_MET for g in mandatory):
        overall = NOT_ELIGIBLE
    elif any(g["status"] == STATUS_UNKNOWN for g in mandatory):
        overall = POTENTIALLY_ELIGIBLE
    else:
        overall = ELIGIBLE

    met = sum(1 for r in all_requirements if r["status"] == STATUS_MET)
    return {
        "eligibility_status": overall,
        "requirements": all_requirements,
        "groups": evaluated_groups,
        "summary": {
            "met": met,
            "not_met": sum(1 for r in all_requirements if r["status"] == STATUS_NOT_MET),
            "unknown": sum(1 for r in all_requirements if r["status"] == STATUS_UNKNOWN),
            "total": len(all_requirements),
        },
    }
