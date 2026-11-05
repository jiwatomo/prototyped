"""Profile flow: extraction -> confirmation -> deterministic recompute."""
from __future__ import annotations

from app.services.ai.factory import AIService

from tests.conftest import analyze, analyze_and_confirm, confirm_payload

DEMO_TAGS = "/api/profile/demo-student/tags"


def test_extraction_only_reports_explicit_facts(client):
    result = analyze(client, "Saya mahasiswa S1 Informatika di Palembang, aktif di organisasi kampus.")
    keys = {fact["field_key"] for fact in result["facts"]}
    assert "education_level" in keys
    assert "major" in keys
    assert "gpa" not in keys
    assert "toefl_score" not in keys
    values = {fact["field_key"]: fact["value"] for fact in result["facts"]}
    assert values["education_level"] == "S1"
    assert values["major"] == "Informatika"


def test_suggested_tags_come_from_master_tag_list(client):
    master = {tag["slug"] for tag in client.get("/api/tags").json()["tags"]}
    result = analyze(client)
    asserted = {tag["slug"] for tag in result["suggested_tags"]}
    assert asserted
    assert asserted <= master
    assert result["provider_mode"] == "mock"


def test_analysis_is_not_used_before_confirmation(client):
    analyze(client)
    tags = client.get(DEMO_TAGS).json()["tags"]
    assert tags == [] or all(t["confirmation_status"] == "suggested" for t in tags)

    recs = client.get("/api/recommendations/demo-student").json()
    assert recs["results"]
    for item in recs["results"]:
        assert item["relevance_score"] is None
        assert item["eligibility_status"] != "eligible"


def test_confirmation_persists_facts_and_tags(client):
    payload = analyze_and_confirm(client)
    assert payload["profile_status"] == "confirmed"
    facts = payload["facts"]
    assert facts["education_level"] == "S1"
    assert facts["gpa"] == 3.45
    assert facts["toefl_score"] == 450
    confirmed = [t for t in payload["tags"] if t["confirmation_status"] == "confirmed"]
    assert any(t["slug"] == "edu.level.s1" for t in confirmed)


def test_rejected_tag_stays_rejected_after_submission(client):
    analysis = analyze(client)
    payload = confirm_payload(analysis, decisions={("sport.badminton", "achievement"): "reject"})
    assert client.post("/api/profile/demo-student/confirm", json=payload).status_code == 200

    tags = client.get(DEMO_TAGS).json()["tags"]
    statuses = {(t["slug"], t["context"]): t["confirmation_status"] for t in tags}
    assert statuses[("sport.badminton", "achievement")] == "rejected"
    assert ("sport.badminton", "achievement") not in {
        key for key, value in statuses.items() if value == "confirmed"
    }


def test_tag_submission_is_allowed_only_once(client):
    analysis = analyze(client)
    first = client.post("/api/profile/demo-student/confirm", json=confirm_payload(analysis))
    assert first.status_code == 200
    assert first.json()["submitted"] is True
    assert first.json()["profile_submitted_at"]

    second = client.post("/api/profile/demo-student/confirm", json=confirm_payload(analysis))
    assert second.status_code == 409
    assert second.json()["code"] == "already_submitted"

    reanalyze = client.post(
        "/api/profile/demo-student/analyze", json={"description": "Deskripsi baru sama sekali."}
    )
    assert reanalyze.status_code == 409
    assert reanalyze.json()["code"] == "already_submitted"


def test_description_is_locked_after_submission_but_facts_are_not(client):
    analyze_and_confirm(client)
    locked = client.put(
        "/api/profile/demo-student", json={"description": "Deskripsi yang diubah setelah kirim."}
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "description_locked"

    facts = client.get("/api/profile/demo-student").json()["facts"]
    facts["toefl_score"] = 530
    allowed = client.put("/api/profile/demo-student", json={"facts": facts})
    assert allowed.status_code == 200
    assert allowed.json()["facts"]["toefl_score"] == 530


def test_only_latest_analysis_can_be_confirmed(client):
    first = analyze(client)
    second = analyze(client)
    assert first["analysis_id"] != second["analysis_id"]
    response = client.post(
        "/api/profile/demo-student/confirm", json=confirm_payload(first)
    )
    assert response.status_code == 409


def test_analysis_can_only_be_confirmed_once(client):
    analysis = analyze(client)
    payload = confirm_payload(analysis)
    assert client.post("/api/profile/demo-student/confirm", json=payload).status_code == 200
    response = client.post("/api/profile/demo-student/confirm", json=payload)
    assert response.status_code == 409


def test_description_change_requires_new_analysis(client):
    analysis = analyze(client)
    response = client.put(
        "/api/profile/demo-student",
        json={"description": "Saya mahasiswa S1 Informatika dengan IPK 3,60."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile_status"] == "draft"
    assert body["latest_analysis_id"] is None
    assert body["needs_analysis"] is True

    stale = client.post("/api/profile/demo-student/confirm", json=confirm_payload(analysis))
    assert stale.status_code == 409


def test_structured_only_update_does_not_call_ai(client, monkeypatch):
    analyze_and_confirm(client)

    async def boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("LLM/AI must not be called for structured-only updates")

    monkeypatch.setattr(AIService, "extract_user_profile", boom)

    facts = client.get("/api/profile/demo-student").json()["facts"]
    facts["gpa"] = 3.6
    response = client.put("/api/profile/demo-student", json={"facts": facts})
    assert response.status_code == 200
    assert response.json()["facts"]["gpa"] == 3.6


def test_toefl_change_updates_recommendations(client):
    analyze_and_confirm(client)
    before = {
        item["name"]: item
        for item in client.get("/api/recommendations/demo-student").json()["results"]
    }
    assert before["Beasiswa Teknologi Nusantara"]["eligibility_status"] == "not_eligible"
    assert before["Beasiswa Atlet Muda"]["eligibility_status"] == "eligible"

    facts = client.get("/api/profile/demo-student").json()["facts"]
    facts["toefl_score"] = 520
    assert client.put("/api/profile/demo-student", json={"facts": facts}).status_code == 200

    after = {
        item["name"]: item
        for item in client.get("/api/recommendations/demo-student").json()["results"]
    }
    assert after["Beasiswa Teknologi Nusantara"]["eligibility_status"] == "eligible"
    toefl_req = next(
        r
        for r in after["Beasiswa Teknologi Nusantara"]["requirements"]
        if r["field_key"] == "toefl_score"
    )
    assert toefl_req["status"] == "met"
    assert toefl_req["actual"] == 520


def test_empty_description_is_rejected(client):
    response = client.post("/api/profile/demo-student/analyze", json={"description": "   "})
    assert response.status_code == 422


def test_confirmation_without_tag_decisions_uses_ai_suggestions(client):
    """The UI never shows tags; the system still records them for matching."""
    analysis = analyze(client)
    payload = confirm_payload(analysis)
    payload["tags"] = []

    response = client.post("/api/profile/demo-student/confirm", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["submitted"] is True

    tags = client.get(DEMO_TAGS).json()["tags"]
    confirmed = [t for t in tags if t["confirmation_status"] == "confirmed"]
    assert len(confirmed) >= 3
    assert any(t["slug"] == "field.informatics" for t in confirmed)

    recs = client.get("/api/recommendations/demo-student").json()["results"]
    tech = next(item for item in recs if item["name"] == "Beasiswa Teknologi Nusantara")
    assert tech["relevance_score"] is not None
