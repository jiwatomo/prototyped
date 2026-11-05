"""Provider selection, schema validation and transparent mock fallback."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Callable

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.ai import (
    PROFILE_FACT_KEYS,
    VALID_SCHOLARSHIP_CONTEXTS,
    VALID_USER_CONTEXTS,
    AIMeta,
    ProfileExtraction,
    RecommendationExplanation,
    ScholarshipExtraction,
    TagClassification,
)
from app.services.ai.interfaces import AIProviderError, InvalidOutputError
from app.services.ai.providers.mock import MockAIProvider
from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class AIUnavailableError(Exception):
    """Raised when the LLM path fails and fallback is disabled."""

    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        self.message = message or "Layanan AI tidak tersedia."
        super().__init__(self.message)


def _ensure_allowed_tags(tags: list[Any], allowed: set[str], contexts: set[str]) -> None:
    for tag in tags:
        if tag.slug not in allowed:
            raise InvalidOutputError(f"slug tidak dikenal: {tag.slug}")
        if tag.context not in contexts:
            raise InvalidOutputError(f"context tidak sesuai: {tag.context}")


class AIService:
    """Single entry point used by business services."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.mock = MockAIProvider()
        self._mode = self.settings.ai_provider.strip().lower()
        self.llm: OpenAICompatibleProvider | None = None
        if self._mode in {"auto", "llm"} and self.settings.llm_configured:
            self.llm = OpenAICompatibleProvider(
                base_url=self.settings.ai_api_base_url,
                api_key=self.settings.ai_api_key,
                model=self.settings.ai_model,
                path=self.settings.ai_chat_completions_path,
                timeout_seconds=self.settings.ai_timeout_seconds,
                max_retries=self.settings.ai_max_retries,
                temperature=self.settings.ai_temperature,
            )
        if self._mode == "llm" and not self.settings.llm_configured:
            if self.settings.ai_fallback_enabled:
                logger.warning(
                    "AI_PROVIDER=llm tetapi konfigurasi LLM tidak lengkap; memakai MockAIProvider."
                )
            else:
                logger.warning(
                    "AI_PROVIDER=llm tanpa konfigurasi lengkap dan fallback dimatikan; "
                    "operasi AI akan mengembalikan error."
                )

    # ------------------------------------------------------------------ meta
    def describe(self) -> dict[str, Any]:
        llm_active = self.llm is not None
        if self._mode == "mock":
            mode = "mock"
        elif llm_active:
            mode = "llm"
        elif self.settings.ai_fallback_enabled:
            mode = "mock"
        else:
            mode = "unavailable"
        return {
            "ai_provider_setting": self._mode,
            "provider_mode": mode,
            "provider_name": self.llm.name if llm_active else self.mock.name,
            "model": self.settings.ai_model if llm_active else None,
            "llm_configured": self.settings.llm_configured,
            "fallback_enabled": self.settings.ai_fallback_enabled,
            "max_input_chars": self.settings.ai_max_input_chars,
        }

    # ------------------------------------------------------------------- run
    async def _run(
        self,
        operation: str,
        call_llm: Callable[[], Any],
        call_mock: Callable[[], Any],
        validator: Callable[[Any], Any],
    ) -> tuple[Any, AIMeta]:
        use_llm = self.llm is not None

        if not use_llm:
            if self._mode == "llm" and not self.settings.ai_fallback_enabled:
                raise AIUnavailableError("missing_config", "Konfigurasi LLM belum lengkap.")
            validated = validator(await call_mock())
            reason = "missing_config" if self._mode == "llm" else None
            return validated, AIMeta(
                provider_mode="mock",
                provider_name=self.mock.name,
                model=None,
                fallback_reason=reason,
            )

        try:
            raw = await call_llm()
            validated = validator(raw)
            return validated, AIMeta(
                provider_mode="llm",
                provider_name=self.llm.name if self.llm else "llm",
                model=self.settings.ai_model or None,
            )
        except (AIProviderError, ValidationError) as exc:
            reason = getattr(exc, "reason", "invalid_output")
            if isinstance(exc, ValidationError):
                reason = "invalid_output"
            logger.warning("Operasi AI %s gagal (%s); fallback=%s", operation, reason,
                           self.settings.ai_fallback_enabled)
            if not self.settings.ai_fallback_enabled:
                raise AIUnavailableError(reason, "Model AI gagal dan fallback dimatikan.") from exc
            try:
                validated = validator(await call_mock())
            except (AIProviderError, ValidationError) as mock_exc:
                raise AIUnavailableError(
                    reason, "Model AI dan provider simulasi sama-sama gagal."
                ) from mock_exc
            return validated, AIMeta(
                provider_mode="mock_fallback",
                provider_name=self.mock.name,
                model=None,
                fallback_reason=reason,
            )

    # ------------------------------------------------------------- operations
    async def extract_user_profile(
        self,
        description: str,
        allowed_tags: list[dict[str, Any]],
        aliases: dict[str, str],
    ) -> tuple[ProfileExtraction, AIMeta]:
        allowed = {t["slug"] for t in allowed_tags}

        def validator(raw: Any) -> ProfileExtraction:
            parsed = ProfileExtraction.model_validate(raw)
            _ensure_allowed_tags(parsed.suggested_tags, allowed, VALID_USER_CONTEXTS)
            for fact in parsed.facts:
                if fact.field_key not in PROFILE_FACT_KEYS:
                    raise InvalidOutputError(f"field_key tidak dikenal: {fact.field_key}")
            return parsed

        return await self._run(
            "extract_user_profile",
            lambda: self.llm.extract_user_profile(description, allowed_tags, aliases) if self.llm else None,
            lambda: self.mock.extract_user_profile(description, allowed_tags, aliases),
            validator,
        )

    async def classify_tags(
        self,
        text: str,
        allowed_tags: list[dict[str, Any]],
        context: str | None = None,
    ) -> tuple[TagClassification, AIMeta]:
        allowed = {t["slug"] for t in allowed_tags}

        def validator(raw: Any) -> TagClassification:
            parsed = TagClassification.model_validate(raw)
            _ensure_allowed_tags(parsed.tags, allowed, VALID_USER_CONTEXTS | VALID_SCHOLARSHIP_CONTEXTS)
            if context:
                for tag in parsed.tags:
                    if tag.context != context:
                        raise InvalidOutputError("context tag tidak sesuai permintaan")
            return parsed

        return await self._run(
            "classify_tags",
            lambda: self.llm.classify_tags(text, allowed_tags, context) if self.llm else None,
            lambda: self.mock.classify_tags(text, allowed_tags, context),
            validator,
        )

    async def extract_scholarship(
        self,
        source_text: str,
        source_metadata: dict[str, Any],
    ) -> tuple[ScholarshipExtraction, AIMeta]:
        def validator(raw: Any) -> ScholarshipExtraction:
            parsed = ScholarshipExtraction.model_validate(raw)
            # Suggested tags for scholarships must use scholarship contexts.
            for tag in parsed.suggested_tags:
                if tag.context not in VALID_SCHOLARSHIP_CONTEXTS:
                    raise InvalidOutputError(f"context beasiswa tidak valid: {tag.context}")
            return parsed

        return await self._run(
            "extract_scholarship",
            lambda: self.llm.extract_scholarship(source_text, source_metadata) if self.llm else None,
            lambda: self.mock.extract_scholarship(source_text, source_metadata),
            validator,
        )

    async def explain_recommendation(
        self,
        profile: dict[str, Any],
        scholarship: dict[str, Any],
        matching_result: dict[str, Any],
    ) -> tuple[RecommendationExplanation, AIMeta]:
        def validator(raw: Any) -> RecommendationExplanation:
            return RecommendationExplanation.model_validate(raw)

        return await self._run(
            "explain_recommendation",
            lambda: self.llm.explain_recommendation(profile, scholarship, matching_result) if self.llm else None,
            lambda: self.mock.explain_recommendation(profile, scholarship, matching_result),
            validator,
        )


@lru_cache
def get_ai_service() -> AIService:
    return AIService()
