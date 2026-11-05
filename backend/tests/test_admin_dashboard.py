"""Admin dashboard: stats, user management and scholarship management."""
from __future__ import annotations

from tests.conftest import auth_headers, login

NEW_USER = {
    "username": "siswa.baru",
    "display_name": "Siswa Baru",
    "role": "student",
    "password": "rahasia123",
}


def test_stats_reflect_seed(admin_client):
    stats = admin_client.get("/api/admin/stats").json()
    assert stats["users"]["total"] == 2
    assert stats["users"]["students"] == 1
    assert stats["users"]["admins"] == 1
    assert stats["scholarships"]["total"] == 4
    assert stats["scholarships"]["verified"] == 3
    assert stats["scholarships"]["pending"] == 1
    assert stats["extractions"]["total"] >= 1


def test_students_cannot_open_admin_pages(client):
    assert client.get("/api/admin/stats").status_code == 403
    assert client.get("/api/admin/users").status_code == 403
    assert client.get("/api/admin/scholarships").status_code == 403


def test_list_users_shows_roles_and_profile_state(admin_client):
    users = admin_client.get("/api/admin/users").json()["users"]
    assert {u["username"] for u in users} == {"demo-student", "demo-admin"}
    student = next(u for u in users if u["username"] == "demo-student")
    assert student["role"] == "student"
    assert student["profile_status"] == "draft"
    assert student["profile_submitted"] is False
    assert "password_hash" not in student


def test_create_student_can_login_and_gets_a_profile(admin_client, anon_client):
    response = admin_client.post("/api/admin/users", json=NEW_USER)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["role"] == "student"

    token = login(anon_client, NEW_USER["username"], NEW_USER["password"])
    profile = anon_client.get(
        "/api/profile/siswa.baru", headers=auth_headers(token)
    )
    assert profile.status_code == 200
    assert profile.json()["profile_status"] == "draft"
    assert profile.json()["submitted"] is False


def test_create_user_validations(admin_client):
    duplicate = admin_client.post("/api/admin/users", json={**NEW_USER, "username": "demo-admin"})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "username_taken"

    short = admin_client.post("/api/admin/users", json={**NEW_USER, "password": "pendek"})
    assert short.status_code == 422

    bad_name = admin_client.post("/api/admin/users", json={**NEW_USER, "username": "spasi salah"})
    assert bad_name.status_code == 422


def test_reset_password_revokes_sessions(admin_client, anon_client):
    admin_client.post("/api/admin/users", json=NEW_USER)
    old_token = login(anon_client, NEW_USER["username"], NEW_USER["password"])
    assert (
        anon_client.get("/api/auth/session", headers=auth_headers(old_token)).status_code == 200
    )

    users = admin_client.get("/api/admin/users").json()["users"]
    user_id = next(u["id"] for u in users if u["username"] == NEW_USER["username"])
    reset = admin_client.post(
        f"/api/admin/users/{user_id}/reset-password", json={"password": "barusekali123"}
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["sessions_revoked"] is True

    # old session is revoked
    assert (
        anon_client.get("/api/auth/session", headers=auth_headers(old_token)).status_code == 401
    )
    # old password no longer works, new one does
    assert (
        anon_client.post(
            "/api/auth/login",
            json={"username": NEW_USER["username"], "password": NEW_USER["password"]},
        ).status_code
        == 401
    )
    login(anon_client, NEW_USER["username"], "barusekali123")


def test_reset_password_can_generate_one(admin_client):
    admin_client.post("/api/admin/users", json=NEW_USER)
    users = admin_client.get("/api/admin/users").json()["users"]
    user_id = next(u["id"] for u in users if u["username"] == NEW_USER["username"])
    response = admin_client.post(f"/api/admin/users/{user_id}/reset-password", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["generated"] is True
    assert body["temporary_password"]
    assert len(body["temporary_password"]) >= 8


def test_scholarship_list_and_filters(admin_client):
    data = admin_client.get("/api/admin/scholarships").json()
    assert data["count"] == 4
    first = data["scholarships"][0]
    assert {"id", "name", "verification_status", "tag_count", "requirement_count"} <= set(first)

    verified = admin_client.get("/api/admin/scholarships?status=verified").json()
    assert verified["count"] == 3

    search = admin_client.get("/api/admin/scholarships?search=Atlet").json()
    assert search["count"] == 1
    assert search["scholarships"][0]["name"] == "Beasiswa Atlet Muda"


def test_scholarship_detail_exposes_review_state(admin_client):
    detail = admin_client.get("/api/admin/scholarships/demo-pending-004").json()
    assert detail["verification_status"] == "pending_verification"
    assert detail["tags"] and all(tag["review_status"] == "pending" for tag in detail["tags"])
    assert detail["requirements"]
    assert detail["extraction_id"]


def test_admin_can_edit_and_approve_a_scholarship(admin_client):
    detail = admin_client.get("/api/admin/scholarships/demo-pending-004").json()
    tag_slug = detail["tags"][0]["slug"]

    patched = admin_client.patch(
        "/api/admin/scholarships/demo-pending-004",
        json={
            "name": "Beasiswa Riset Muda (revisi)",
            "organizer": "Pusat Riset Demo",
            "tags": [{"slug": tag_slug, "decision": "approve"}],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Beasiswa Riset Muda (revisi)"
    approved_tag = next(t for t in patched.json()["tags"] if t["slug"] == tag_slug)
    assert approved_tag["review_status"] == "approved"

    approved = admin_client.post("/api/admin/scholarships/demo-pending-004/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["verification_status"] == "verified"
    assert approved.json()["history"][0]["decision"] == "approved"

    catalog = admin_client.get("/api/scholarships").json()["scholarships"]
    assert "Beasiswa Riset Muda (revisi)" in {s["name"] for s in catalog}


def test_admin_reject_requires_reason(admin_client):
    empty = admin_client.post(
        "/api/admin/scholarships/demo-pending-004/reject", json={"reason": "  "}
    )
    assert empty.status_code == 422

    rejected = admin_client.post(
        "/api/admin/scholarships/demo-pending-004/reject",
        json={"reason": "Sumber tidak kredibel (demo)"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["verification_status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Sumber tidak kredibel (demo)"

    catalog = admin_client.get("/api/scholarships").json()["scholarships"]
    assert "demo-pending-004" not in {s["id"] for s in catalog}


def test_already_verified_scholarship_cannot_be_approved_again(admin_client):
    response = admin_client.post("/api/admin/scholarships/demo-tech-001/approve")
    assert response.status_code == 409
    assert response.json()["code"] == "already_verified"


def test_student_cannot_decide_on_scholarships(client):
    assert client.post("/api/admin/scholarships/demo-pending-004/approve").status_code == 403
    assert (
        client.patch(
            "/api/admin/scholarships/demo-pending-004", json={"name": "Hack"}
        ).status_code
        == 403
    )
