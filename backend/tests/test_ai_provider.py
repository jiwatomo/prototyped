"""AI provider factory, fallback behaviour and UI labels."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.services.ai.factory import AIService, AIUnavailableError
from app.services.ai.interfaces import AIProviderError

ALLOWED = [
    {"slug": "edu.level.s1", "name": "S1", "category": "EDU"},
    {"slug": "field.informatics", "name": "Informatika", "category": "FIELD"},
    {"slug": "interest.technology", "name": "Teknologi", "category": "INTEREST"},
]
DESCRIPTION = "Saya mahasiswa S1 Informatika yang tertarik pada teknologi."


def make_settings(**overrides) -> Settings:
    base = {
        "ai_provider": "auto",
        "ai_fallback_enabled": True,
        "ai_api_base_url": "https://llm.example.test/v1",
        "ai_api_key": "super-secret-key",
        "ai_model": "demo-model",
    }
    base.update(overrides)
    return Settings(**base)


def run(coro):
    return asyncio.run(coro)


def test_auto_with_full_config_selects_llm():
    service = AIService(make_settings())
    info = service.describe()
    assert info["provider_mode"] == "llm"
    assert info["provider_name"] == "openai_compatible"
    assert info["model"] == "demo-model"
    assert "super-secret-key" not in json.dumps(info)


def test_auto_without_config_selects_mock():
    service = AIService(make_settings(ai_api_base_url="", ai_api_key="", ai_model=""))
    info = service.describe()
    assert info["provider_mode"] == "mock"
    assert info["llm_configured"] is False


class FailingLLM:
    name = "fake"
    model = "fake-model"

    def __init__(self, reason="timeout"):
        self.reason = reason

    async def extract_user_profile(self, *args, **kwargs):
        raise AIProviderError(self.reason, "upstream failure")


class BadSlugLLM:
    name = "fake"
    model = "fake-model"

    async def extract_user_profile(self, *args, **kwargs):
        return {
            "facts": [],
            "suggested_tags": [
                {"slug": "made.up.slug", "context": "profile", "confidence": 0.9, "evidence": "x"}
            ],
        }


def test_timeout_falls_back_to_mock():
    service = AIService(make_settings())
    service.llm = FailingLLM("timeout")
    extraction, meta = run(service.extract_user_profile(DESCRIPTION, ALLOWED, {}))
    assert meta.provider_mode == "mock_fallback"
    assert meta.fallback_reason == "timeout"
    assert meta.model is None
    assert extraction.suggested_tags  # mock filled in the result
    assert {t.slug for t in extraction.suggested_tags} <= {t["slug"] for t in ALLOWED}


def test_unknown_slug_from_llm_triggers_fallback():
    service = AIService(make_settings())
    service.llm = BadSlugLLM()
    _, meta = run(service.extract_user_profile(DESCRIPTION, ALLOWED, {}))
    assert meta.provider_mode == "mock_fallback"
    assert meta.fallback_reason == "invalid_output"


def test_fallback_disabled_returns_structured_error():
    service = AIService(
        make_settings(ai_provider="llm", ai_api_key="", ai_api_base_url="", ai_model="", ai_fallback_enabled=False)
    )
    with pytest.raises(AIUnavailableError) as exc:
        run(service.extract_user_profile(DESCRIPTION, ALLOWED, {}))
    assert exc.value.reason == "missing_config"


def test_llm_failure_without_fallback_raises():
    service = AIService(make_settings(ai_fallback_enabled=False))
    service.llm = FailingLLM("provider_error")
    with pytest.raises(AIUnavailableError) as exc:
        run(service.extract_user_profile(DESCRIPTION, ALLOWED, {}))
    assert exc.value.reason == "provider_error"


def test_mock_mode_makes_no_network_call(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network access is forbidden in mock mode")

    monkeypatch.setattr(httpx, "AsyncClient", boom)
    service = AIService(make_settings(ai_provider="mock"))
    extraction, meta = run(service.extract_user_profile(DESCRIPTION, ALLOWED, {}))
    assert meta.provider_mode == "mock"
    assert meta.fallback_reason is None
    assert extraction.facts


def test_ui_labels_distinguish_all_provider_modes():
    components = Path(__file__).resolve().parents[2] / "frontend" / "js" / "components.js"
    source = components.read_text(encoding="utf-8")
    assert "LLM aktif" in source
    assert "Simulasi AI" in source
    assert "LLM gagal — menggunakan simulasi" in source
