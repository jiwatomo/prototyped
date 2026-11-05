"""Admin-typed scholarships: creation, review and approval path."""
from __future__ import annotations

from tests.conftest import analyze_and_confirm

MANUAL = {
    "name": "Beasiswa Manual Demo",
    "organizer": "Yayasan Manual Demo",
    "description": "Data sintetis yang diketik langsung oleh admin.",
    "education_levels": ["S1"],
    "benefits": ["Biaya pendidikan"],
    "application_start": None,
    "application_deadline": "2027-05-31",
    "tags": [
        {"slug": "edu.level.s1", "context": "target_audience"},
        {"slug": "field.informatics", "context": "field"},
        {"slug": "benefit.tuition", "context": "benefit"},
    ],
    "requirements": [
        {
            "field_key": "gpa",
            "operator": "gte",
            "value": 3.2,
            "unit": "score",
            "description": "IPK minimum 3.20",
            "is_mandatory": True,
        },
        {
            "field_key": "toefl_score",
            "operator": "gte",
            "value": 500,
            "description": "TOEFL minimum 500 (nilai tambah)",
            "is_mandatory": False,
        },
    ],
}


def create_manual(admin_client, payload=None):
    return admin_client.post("/api/admin/scholarships", json=payload or MANUAL)


def test_manual_scholarship_enters_pending_queue(admin_client):
    response = create_manual(admin_client)
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["source_type"] == "manual"
    assert job["status"] == "completed"
    assert job["scholarship"]["verification_status"] == "pending_verification"
    assert job["scholarship"]["name"] == "Beasiswa Manual Demo"
    assert len(job["tags"]) == 3
    assert all(tag["review_status"] == "pending" for tag in job["tags"])
    assert len(job["requirements"]) == 2
    assert job["sources"][0]["source_type"] == "manual"

    pending = admin_client.get("/api/admin/scholarships/pending").json()["scholarships"]
    match = next(row for row in pending if row["name"] == "Beasiswa Manual Demo")
    assert match["extraction_id"] == job["extraction_id"]


def test_manual_scholarship_can_be_edited_and_approved(admin_client):
    job = create_manual(admin_client).json()
    extraction_id = job["extraction_id"]

    patched = admin_client.patch(
        f"/api/admin/extractions/{extraction_id}",
        json={"name": "Beasiswa Manual Diperbaiki", "organizer": "Yayasan Manual"},
    )
    assert patched.status_code == 200
    assert patched.json()["scholarship"]["name"] == "Beasiswa Manual Diperbaiki"

    approved = admin_client.post(f"/api/admin/extractions/{extraction_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["scholarship"]["verification_status"] == "verified"

    catalog = admin_client.get("/api/scholarships").json()["scholarships"]
    assert "Beasiswa Manual Diperbaiki" in {item["name"] for item in catalog}


def test_manual_scholarship_reaches_recommendations(client, admin_client):
    analyze_and_confirm(client)
    job = create_manual(admin_client).json()
    admin_client.post(f"/api/admin/extractions/{job['extraction_id']}/approve")

    recs = client.get("/api/recommendations/demo-student").json()["results"]
    entry = next(item for item in recs if item["name"] == "Beasiswa Manual Demo")
    assert entry["eligibility_status"] in {"eligible", "potentially_eligible", "not_eligible"}
    assert entry["verification_status"] == "verified"
    # TOEFL 450 < 500 is optional, so it must not disqualify.
    assert entry["eligibility_status"] != "not_eligible"


def test_manual_scholarship_requires_at_least_one_tag(admin_client):
    payload = {**MANUAL, "tags": []}
    response = create_manual(admin_client, payload)
    assert response.status_code == 422


def test_manual_scholarship_rejects_unknown_tag(admin_client):
    payload = {**MANUAL, "tags": [{"slug": "sport.curling", "context": "achievement"}]}
    response = create_manual(admin_client, payload)
    assert response.status_code == 422
    assert response.json()["code"] == "unknown_tag"


def test_manual_scholarship_rejects_invalid_context(admin_client):
    payload = {**MANUAL, "tags": [{"slug": "edu.level.s1", "context": "profile"}]}
    response = create_manual(admin_client, payload)
    assert response.status_code == 422


def test_manual_scholarship_rejects_empty_name(admin_client):
    payload = {**MANUAL, "name": "  "}
    assert create_manual(admin_client, payload).status_code == 422


def test_students_cannot_create_scholarships(client):
    assert client.post("/api/admin/scholarships", json=MANUAL).status_code == 403


def test_seeded_pending_scholarship_is_openable_and_approvable(admin_client):
    pending = admin_client.get("/api/admin/scholarships/pending").json()["scholarships"]
    seeded = next(row for row in pending if row["scholarship_id"] == "demo-pending-004")
    assert seeded["extraction_id"], "seeded pending record must expose an extraction id"

    response = admin_client.post(f"/api/admin/extractions/{seeded['extraction_id']}/approve")
    assert response.status_code == 200, response.text
    assert response.json()["scholarship"]["verification_status"] == "verified"
