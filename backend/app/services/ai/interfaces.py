"""Vendor-neutral AI provider contract."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class AIProviderError(Exception):
    """Raised by adapters. `reason` is a short, secret-free code."""

    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason)


class InvalidOutputError(AIProviderError):
    def __init__(self, message: str = "invalid output") -> None:
        super().__init__("invalid_output", message)


@runtime_checkable
class AIProvider(Protocol):
    name: str
    model: str | None

    async def extract_user_profile(
        self,
        description: str,
        allowed_tags: list[dict[str, Any]],
        aliases: dict[str, str],
    ) -> dict[str, Any]:
        """Return facts + suggested tags as JSON-compatible dict."""

    async def classify_tags(
        self,
        text: str,
        allowed_tags: list[dict[str, Any]],
        context: str | None = None,
    ) -> dict[str, Any]:
        """Pick tags from the allowed Master Tag list."""

    async def extract_scholarship(
        self,
        source_text: str,
        source_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract scholarship info, tags and structured requirements."""

    async def explain_recommendation(
        self,
        profile: dict[str, Any],
        scholarship: dict[str, Any],
        matching_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Explain an already-computed result. Never changes statuses."""
