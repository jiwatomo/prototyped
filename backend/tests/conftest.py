"""Test fixtures: isolated seeded database and authenticated API clients."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = tempfile.mkdtemp(prefix="scholar-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["AI_PROVIDER"] = "mock"
os.environ["AI_FALLBACK_ENABLED"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import (  # noqa: E402
    DEMO_ADMIN_PASSWORD,
    DEMO_DESCRIPTION,
    DEMO_STUDENT_PASSWORD,
    run_seed,
)

STUDENT_USERNAME = "demo-student"
ADMIN_USERNAME = "demo-admin"


@pytest.fixture()
def seeded_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        run_seed(db)


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def anon_client(seeded_db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def client(seeded_db):
    """Authenticated as the demo student."""
    with TestClient(app) as test_client:
        test_client.headers.update(
            auth_headers(login(test_client, STUDENT_USERNAME, DEMO_STUDENT_PASSWORD))
        )
        yield test_client


@pytest.fixture()
def admin_client(seeded_db):
    """Authenticated as the demo admin."""
    with TestClient(app) as test_client:
        test_client.headers.update(
            auth_headers(login(test_client, ADMIN_USERNAME, DEMO_ADMIN_PASSWORD))
        )
        yield test_client


def analyze(client, description: str = DEMO_DESCRIPTION) -> dict:
    response = client.post(
        "/api/profile/demo-student/analyze", json={"description": description}
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirm_payload(analysis: dict, decisions: dict[str, str] | None = None, **fact_overrides) -> dict:
    """Build a confirm payload from an analysis result.

    decisions maps (slug, context) -> "confirm"|"reject"; default is confirm
    for every suggestion that was not previously rejected.
    """
    facts = {fact["field_key"]: fact["value"] for fact in analysis["facts"]}
    facts.update(fact_overrides)
    tags = []
    for tag in analysis["suggested_tags"]:
        key = (tag["slug"], tag["context"])
        if decisions and key in decisions:
            decision = decisions[key]
        elif tag.get("previously_rejected"):
            decision = "reject"
        else:
            decision = "confirm"
        tags.append({"slug": tag["slug"], "context": tag["context"], "decision": decision})

    return {
        "analysis_id": analysis["analysis_id"],
        "facts": {
            "education_level": facts.get("education_level"),
            "major": facts.get("major"),
            "institution": facts.get("institution"),
            "gpa": facts.get("gpa"),
            "domicile": facts.get("domicile"),
            "toefl_type": facts.get("toefl_type"),
            "toefl_score": facts.get("toefl_score"),
            "achievements": facts.get("achievements") or [],
        },
        "tags": tags,
    }


def analyze_and_confirm(client, description: str = DEMO_DESCRIPTION, **fact_overrides) -> dict:
    analysis = analyze(client, description)
    response = client.post(
        "/api/profile/demo-student/confirm",
        json=confirm_payload(analysis, **fact_overrides),
    )
    assert response.status_code == 200, response.text
    return response.json()
