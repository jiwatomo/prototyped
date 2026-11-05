"""Home highlights (hot / newly added) and screenshot submissions."""
from __future__ import annotations

from pathlib import Path

from tests.conftest import analyze_and_confirm

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 32
)


def test_home_payload_has_hot_and_recent_lists(client):
    analyze_and_confirm(client)
    payload = client.get("/api/recommendations/demo-student").json()

    assert "hot" in payload and "recent" in payload
    hot_ids = [item["scholarship_id"] for item in payload["hot"]]
    recent_ids = [item["scholarship_id"] for item in payload["recent"]]
    assert hot_ids, "hot section should not be empty"
    assert len(hot_ids) <= 3 and len(recent_ids) <= 3
    created = [item["created_at"] for item in payload["recent"]]
    assert created == sorted(created, reverse=True)
    assert all("created_at" in item for item in payload["results"])


def test_hot_prefers_open_or_upcoming_scholarships(client):
    payload = client.get("/api/recommendations/demo-student").json()
    statuses = [item["application_status"] for item in payload["hot"]]
    assert statuses
    assert statuses[0] in {"open", "upcoming", "unknown"}


def test_student_can_submit_a_screenshot(client):
    response = client.post(
        "/api/submissions",
        files={"file": ("beasiswa.png", PNG_BYTES, "image/png")},
        data={"note": "Info beasiswa dari grup kampus"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["username"] == "demo-student"
    assert body["image_url"].endswith("/image")

    mine = client.get("/api/submissions/me").json()
    assert mine["count"] == 1
    assert mine["submissions"][0]["id"] == body["id"]


def test_submission_rejects_non_image(client):
    response = client.post(
        "/api/submissions",
        files={"file": ("catatan.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_image_type"


def test_admin_sees_and_serves_the_screenshot(admin_client, client):
    created = client.post(
        "/api/submissions",
        files={"file": ("beasiswa.png", PNG_BYTES, "image/png")},
        data={"note": "Screenshot dari WhatsApp"},
    ).json()

    listing = admin_client.get("/api/admin/submissions?status=pending").json()
    assert listing["count"] == 1
    assert listing["submissions"][0]["username"] == "demo-student"
    assert listing["submissions"][0]["note"] == "Screenshot dari WhatsApp"

    image = admin_client.get(f"/api/admin/submissions/{created['id']}/image")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content == PNG_BYTES


def test_admin_can_process_and_reject_submissions(admin_client, client):
    first = client.post(
        "/api/submissions", files={"file": ("a.png", PNG_BYTES, "image/png")}
    ).json()
    processed = admin_client.post(
        f"/api/admin/submissions/{first['id']}/process", json={"status": "processed"}
    )
    assert processed.status_code == 200
    assert processed.json()["status"] == "processed"

    again = admin_client.post(
        f"/api/admin/submissions/{first['id']}/process", json={"status": "rejected"}
    )
    assert again.status_code == 409

    second = client.post(
        "/api/submissions", files={"file": ("b.png", PNG_BYTES, "image/png")}
    ).json()
    rejected = admin_client.post(
        f"/api/admin/submissions/{second['id']}/process",
        json={"status": "rejected", "reason": "Bukan beasiswa (demo)"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["reason"] == "Bukan beasiswa (demo)"


def test_submission_role_boundaries(client, admin_client):
    assert client.get("/api/admin/submissions").status_code == 403
    assert (
        admin_client.post(
            "/api/submissions", files={"file": ("a.png", PNG_BYTES, "image/png")}
        ).status_code
        == 403
    )


def test_submission_page_and_home_sections_wired():
    page = (FRONTEND / "submit-scholarship.html").read_text(encoding="utf-8")
    assert 'id="submission-file"' in page
    assert "js/submit-scholarship.js" in page

    home = (FRONTEND / "app.html").read_text(encoding="utf-8")
    assert 'id="hot-list"' in home
    assert 'id="recent-list"' in home
    assert "submit-scholarship.html" in home
