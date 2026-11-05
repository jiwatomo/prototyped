"""Demo authentication: login, session lifecycle and role enforcement."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import AuthSession, User

from tests.conftest import ADMIN_USERNAME, STUDENT_USERNAME, auth_headers, login

ADMIN_PASSWORD = "admin123"
STUDENT_PASSWORD = "student123"


def test_login_returns_token_and_role(anon_client):
    response = anon_client.post(
        "/api/auth/login", json={"username": STUDENT_USERNAME, "password": STUDENT_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["token_type"] == "bearer"
    assert body["role"] == "student"
    assert body["user"]["username"] == STUDENT_USERNAME
    assert body["expires_at"]
    assert "password" not in str(body.keys())
    assert "password_hash" not in response.text


def test_admin_login_reports_admin_role(anon_client):
    response = anon_client.post(
        "/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_wrong_password_is_rejected_generically(anon_client):
    response = anon_client.post(
        "/api/auth/login", json={"username": STUDENT_USERNAME, "password": "salah"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert "kata sandi" in response.json()["detail"]


def test_unknown_user_is_rejected(anon_client):
    response = anon_client.post(
        "/api/auth/login", json={"username": "tidak-ada", "password": "apa-saja"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_protected_endpoints_require_token(anon_client):
    for path in [
        "/api/profile/demo-student",
        "/api/recommendations/demo-student",
        "/api/admin/extractions",
        "/api/tags",
    ]:
        response = anon_client.get(path)
        assert response.status_code == 401, path
        assert response.json()["code"] == "unauthenticated"


def test_health_stays_public(anon_client):
    response = anon_client.get("/api/health")
    assert response.status_code == 200
    assert "password" not in response.text.lower()
    assert "api_key" not in response.text.lower()


def test_invalid_token_is_rejected(anon_client):
    response = anon_client.get(
        "/api/profile/demo-student", headers=auth_headers("not-a-real-token")
    )
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_session_endpoint_returns_current_user(anon_client):
    token = login(anon_client, STUDENT_USERNAME, STUDENT_PASSWORD)
    response = anon_client.get("/api/auth/session", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["user"]["username"] == STUDENT_USERNAME
    assert response.json()["role"] == "student"


def test_logout_revokes_the_session(anon_client):
    token = login(anon_client, STUDENT_USERNAME, STUDENT_PASSWORD)
    assert anon_client.get("/api/auth/session", headers=auth_headers(token)).status_code == 200
    assert anon_client.post("/api/auth/logout", headers=auth_headers(token)).status_code == 200
    after = anon_client.get("/api/auth/session", headers=auth_headers(token))
    assert after.status_code == 401
    assert after.json()["code"] == "unauthenticated"


def test_expired_session_is_rejected(anon_client):
    token = login(anon_client, STUDENT_USERNAME, STUDENT_PASSWORD)
    with SessionLocal() as db:
        session = db.execute(select(AuthSession)).scalars().first()
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    response = anon_client.get("/api/auth/session", headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["code"] == "session_expired"


def test_student_cannot_reach_admin_endpoints(client):
    response = client.get("/api/admin/extractions")
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_student_cannot_mutate_another_profile(client):
    response = client.post(
        "/api/profile/demo-admin/analyze", json={"description": "Saya admin"}
    )
    assert response.status_code == 403


def test_admin_can_read_but_not_edit_student_profile(admin_client):
    read = admin_client.get("/api/profile/demo-student")
    assert read.status_code == 200
    edit = admin_client.post(
        "/api/profile/demo-student/analyze",
        json={"description": "Saya mahasiswa S1 Informatika."},
    )
    assert edit.status_code == 403


def test_admin_can_access_admin_endpoints(admin_client):
    assert admin_client.get("/api/admin/extractions").status_code == 200
    assert admin_client.get("/api/admin/scholarships/pending").status_code == 200


def test_passwords_are_hashed_and_tokens_stored_hashed(anon_client):
    token = login(anon_client, STUDENT_USERNAME, STUDENT_PASSWORD)
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.username == STUDENT_USERNAME)).scalar_one()
        assert user.password_hash.startswith("pbkdf2_sha256$")
        assert STUDENT_PASSWORD not in user.password_hash
        session = db.execute(select(AuthSession)).scalars().first()
        assert session.token_hash != token
        assert len(session.token_hash) == 64
