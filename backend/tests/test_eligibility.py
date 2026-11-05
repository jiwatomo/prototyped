"""Eligibility engine: operators, AND/OR groups and gap analysis statuses."""
from __future__ import annotations

from app.services.eligibility_service import evaluate, evaluate_requirement

PROFILE = {
    "education_level": "S1",
    "major": "Informatika",
    "gpa": 3.45,
    "toefl_score": 450,
    "domicile": "Palembang",
}
NO_TAGS: list[dict] = []


def req(field_key=None, operator="eq", value=None, tag_id=None, description="persyaratan"):
    return {
        "id": f"req-{field_key or tag_id}",
        "field_key": field_key,
        "operator": operator,
        "value": value,
        "tag_id": tag_id,
        "description": description,
    }


def group(name, operator, is_mandatory, requirements):
    return {
        "id": name,
        "name": name,
        "operator": operator,
        "is_mandatory": is_mandatory,
        "requirements": requirements,
    }


def status_of(requirement, profile=None):
    return evaluate_requirement(requirement, PROFILE if profile is None else profile, set())["status"]


def test_numeric_operators():
    assert status_of(req("gpa", "gte", 3.0)) == "met"
    assert status_of(req("gpa", "gte", 3.5)) == "not_met"
    assert status_of(req("gpa", "lte", 3.5)) == "met"
    assert status_of(req("gpa", "gt", 3.45)) == "not_met"
    assert status_of(req("gpa", "lt", 3.46)) == "met"
    assert status_of(req("toefl_score", "eq", 450)) == "met"


def test_text_and_list_operators():
    assert status_of(req("education_level", "eq", "s1")) == "met"
    assert status_of(req("major", "contains", "informatika")) == "met"
    assert status_of(req("education_level", "in", ["SMA", "S1"])) == "met"
    assert status_of(req("education_level", "not_in", ["SMA", "SMK"])) == "met"
    assert status_of(req("gpa", "between", [3.0, 3.5])) == "met"
    assert status_of(req("gpa", "between", [3.5, 4.0])) == "not_met"


def test_missing_value_is_unknown_not_false():
    assert status_of(req("toefl_score", "gte", 500), profile={}) == "unknown"
    assert status_of(req("gpa", "between", [3.0]), profile={}) == "unknown"


def test_tag_requirement_uses_confirmed_tags_only():
    result = evaluate_requirement(req(tag_id="tag-1"), PROFILE, set())
    assert result["status"] == "unknown"
    confirmed = evaluate_requirement(req(tag_id="tag-1"), PROFILE, {"tag-1"})
    assert confirmed["status"] == "met"


def test_all_mandatory_met_is_eligible():
    groups = [group("Utama", "AND", True, [req("gpa", "gte", 3.0), req("toefl_score", "gte", 450)])]
    result = evaluate(groups, PROFILE, NO_TAGS)
    assert result["eligibility_status"] == "eligible"
    assert result["summary"]["met"] == 2


def test_one_mandatory_failure_is_not_eligible():
    groups = [
        group("Utama", "AND", True, [req("gpa", "gte", 3.0), req("toefl_score", "gte", 500)])
    ]
    result = evaluate(groups, PROFILE, NO_TAGS)
    assert result["eligibility_status"] == "not_eligible"


def test_unknown_mandatory_is_potentially_eligible():
    groups = [group("Utama", "AND", True, [req("gpa", "gte", 3.0), req("toefl_score", "gte", 500)])]
    result = evaluate(groups, {"gpa": 3.45}, NO_TAGS)
    assert result["eligibility_status"] == "potentially_eligible"


def test_or_group_needs_one_match():
    groups = [
        group(
            "Alternatif",
            "OR",
            True,
            [
                req("toefl_score", "gte", 500),
                req("achievements", "contains", "juara"),
            ],
        )
    ]
    profile = {**PROFILE, "achievements": ["Juara 1 bulu tangkis"]}
    assert evaluate(groups, profile, NO_TAGS)["eligibility_status"] == "eligible"

    failing = [
        group("Alternatif", "OR", True, [req("toefl_score", "gte", 600), req("gpa", "gte", 4.0)])
    ]
    assert evaluate(failing, PROFILE, NO_TAGS)["eligibility_status"] == "not_eligible"

    unknown = [
        group("Alternatif", "OR", True, [req("toefl_score", "gte", 600), req("age", "gte", 17)])
    ]
    assert evaluate(unknown, PROFILE, NO_TAGS)["eligibility_status"] == "potentially_eligible"


def test_optional_requirement_never_disqualifies():
    groups = [
        group("Utama", "AND", True, [req("gpa", "gte", 3.0)]),
        group("Nilai tambah", "AND", False, [req("toefl_score", "gte", 600)]),
    ]
    result = evaluate(groups, PROFILE, NO_TAGS)
    assert result["eligibility_status"] == "eligible"
    optional = result["groups"][1]
    assert optional["is_mandatory"] is False
    assert optional["status"] == "not_met"


def test_gap_analysis_reports_every_status():
    groups = [
        group(
            "Utama",
            "AND",
            True,
            [req("gpa", "gte", 3.0), req("toefl_score", "gte", 500), req("domicile", "eq", "Jakarta")],
        )
    ]
    result = evaluate(groups, PROFILE, NO_TAGS)
    statuses = {r["field_key"]: r["status"] for r in result["requirements"]}
    assert statuses["gpa"] == "met"
    assert statuses["toefl_score"] == "not_met"
    assert statuses["domicile"] == "not_met"
