"""Admin extraction + verification flow."""
from __future__ import annotations

SOURCE_TEXT = (
    "Beasiswa Teknologi Digital\n"
    "Penyelenggara: Yayasan Digital Demo\n"
    "Ditujukan bagi mahasiswa S1 jurusan Informatika dengan IPK minimal 3,20 "
    "dan TOEFL minimal 500.\n"
    "Manfaat: biaya pendidikan.\n"
    "Batas akhir 31 Maret 2027.\n"
)


def create_extraction(admin_client, text: str = SOURCE_TEXT) -> dict:
    response = admin_client.post("/api/admin/extractions", json={"source_text": text})
    assert response.status_code == 201, response.text
    return response.json()


def test_extraction_creates_pending_scholarship(admin_client):
    job = create_extraction(admin_client)
    assert job["status"] == "completed"
    assert job["provider_mode"] == "mock"
    assert job["scholarship"]["verification_status"] == "pending_verification"
    assert job["scholarship"]["name"] == "Beasiswa Teknologi Digital"
    assert job["scholarship"]["organizer"] == "Yayasan Digital Demo"
    assert job["tags"]
    assert all(tag["review_status"] == "pending" for tag in job["tags"])
    contexts = {tag["context"] for tag in job["tags"]}
    allowed = {
        "eligibility",
        "target_audience",
        "field",
        "achievement",
        "benefit",
        "program",
        "location",
        "obligation",
    }
    assert contexts <= allowed

    fields = {r["field_key"] for r in job["requirements"]}
    assert {"gpa", "toefl_score"} <= fields


def test_extraction_requires_a_source(admin_client):
    response = admin_client.post("/api/admin/extractions", json={"source_text": "   "})
    assert response.status_code == 422


def test_pending_list_contains_new_extraction(admin_client):
    job = create_extraction(admin_client)
    pending = admin_client.get("/api/admin/scholarships/pending").json()
    ids = {row["scholarship_id"] for row in pending["scholarships"]}
    assert "demo-pending-004" in ids
    assert job["scholarship"]["id"] in ids


def test_approval_publishes_scholarship_and_tags(admin_client):
    job = create_extraction(admin_client)
    scholarship_id = job["scholarship"]["id"]

    catalog_before = admin_client.get("/api/scholarships").json()["scholarships"]
    assert scholarship_id not in {s["id"] for s in catalog_before}

    approved = admin_client.post(f"/api/admin/extractions/{job['extraction_id']}/approve")
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["scholarship"]["verification_status"] == "verified"
    assert all(tag["review_status"] == "approved" for tag in body["tags"])

    catalog_after = admin_client.get("/api/scholarships").json()["scholarships"]
    assert scholarship_id in {s["id"] for s in catalog_after}


def test_approval_is_idempotent_guarded(admin_client):
    job = create_extraction(admin_client)
    assert admin_client.post(f"/api/admin/extractions/{job['extraction_id']}/approve").status_code == 200
    second = admin_client.post(f"/api/admin/extractions/{job['extraction_id']}/approve")
    assert second.status_code == 409


def test_rejection_requires_reason(admin_client):
    job = create_extraction(admin_client)
    empty = admin_client.post(f"/api/admin/extractions/{job['extraction_id']}/reject", json={"reason": "  "})
    assert empty.status_code == 422

    rejected = admin_client.post(
        f"/api/admin/extractions/{job['extraction_id']}/reject",
        json={"reason": "Sumber tidak kredibel (demo)"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["scholarship"]["verification_status"] == "rejected"

    catalog = admin_client.get("/api/scholarships").json()["scholarships"]
    assert rejected.json()["scholarship"]["id"] not in {s["id"] for s in catalog}


def test_patch_updates_extraction_result(admin_client):
    job = create_extraction(admin_client)
    response = admin_client.patch(
        f"/api/admin/extractions/{job['extraction_id']}",
        json={"name": "Beasiswa Digital Nusantara", "organizer": "Yayasan Digital"},
    )
    assert response.status_code == 200
    assert response.json()["scholarship"]["name"] == "Beasiswa Digital Nusantara"
    assert response.json()["scholarship"]["organizer"] == "Yayasan Digital"


def test_patch_rejects_unknown_tag_slug(admin_client):
    job = create_extraction(admin_client)
    response = admin_client.patch(
        f"/api/admin/extractions/{job['extraction_id']}",
        json={"tags": [{"slug": "sport.curling", "decision": "approve"}]},
    )
    assert response.status_code == 422


def test_soft_deleted_statuses_never_reach_recommendations(admin_client):
    job = create_extraction(admin_client)
    admin_client.post(f"/api/admin/extractions/{job['extraction_id']}/reject", json={"reason": "demo"})
    recs = admin_client.get("/api/recommendations/demo-student").json()
    names = {item["name"] for item in recs["results"]}
    assert "Beasiswa Riset Muda" not in names  # seeded pending record
    assert job["scholarship"]["name"] not in names


def test_extraction_requires_source_text_url_or_pdf(admin_client):
    response = admin_client.post("/api/admin/extractions", json={})
    assert response.status_code == 422
    assert response.json()["code"] == "missing_source"
