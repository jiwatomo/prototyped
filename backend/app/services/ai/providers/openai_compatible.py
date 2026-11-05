"""Generic OpenAI-compatible chat completions adapter (no vendor SDK)."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.services.ai.interfaces import AIProviderError, InvalidOutputError

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _extract_json(content: str) -> Any:
    cleaned = _FENCE_RE.sub("", content).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise InvalidOutputError("model response was not valid JSON")


class OpenAICompatibleProvider:
    """Calls any endpoint that speaks the OpenAI chat completions format."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        path: str = "/chat/completions",
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        temperature: float = 0.1,
    ) -> None:
        self.name = "openai_compatible"
        self.model = model
        self._url = base_url.rstrip("/") + "/" + path.lstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._temperature = temperature

    async def _chat(self, system: str, user: str) -> Any:
        payload = {
            "model": self.model,
            "temperature": self._temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        last_reason = "provider_error"
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(self._url, json=payload, headers=headers)
                if response.status_code >= 500 or response.status_code == 429:
                    last_reason = "provider_error"
                    raise AIProviderError(last_reason, f"upstream status {response.status_code}")
                if response.status_code >= 400:
                    # 4xx (bad key/model) will not improve with retries.
                    raise AIProviderError("provider_error", f"upstream status {response.status_code}")
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return _extract_json(content)
            except httpx.TimeoutException as exc:
                last_reason = "timeout"
                if attempt >= self._max_retries:
                    raise AIProviderError("timeout", "AI request timed out") from exc
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise InvalidOutputError("unexpected response shape") from exc
            except AIProviderError:
                if attempt >= self._max_retries:
                    raise
            except httpx.HTTPError as exc:
                last_reason = "provider_error"
                if attempt >= self._max_retries:
                    raise AIProviderError("provider_error", str(exc)) from exc
            await asyncio.sleep(0.5 * (attempt + 1))
        raise AIProviderError(last_reason)

    async def extract_user_profile(
        self,
        description: str,
        allowed_tags: list[dict[str, Any]],
        aliases: dict[str, str],
    ) -> dict[str, Any]:
        system = load_prompt("profile_extraction")
        user = json.dumps(
            {
                "description": description,
                "allowed_tags": allowed_tags,
                "aliases": aliases,
                "schema": {
                    "facts": [
                        {
                            "field_key": "education_level|major|institution|gpa|domicile|toefl_type|toefl_score|semester|achievements",
                            "value": "string|number|array|null",
                            "confidence": "0..1",
                            "evidence": "kutipan dari deskripsi",
                        }
                    ],
                    "suggested_tags": [
                        {
                            "slug": "slug dari allowed_tags",
                            "context": "profile|interest|achievement|preference|location|language|economic",
                            "confidence": "0..1",
                            "evidence": "kutipan dari deskripsi",
                        }
                    ],
                },
            },
            ensure_ascii=False,
        )
        return await self._chat(system, user)

    async def classify_tags(
        self,
        text: str,
        allowed_tags: list[dict[str, Any]],
        context: str | None = None,
    ) -> dict[str, Any]:
        system = load_prompt("classification")
        user = json.dumps(
            {"text": text, "allowed_tags": allowed_tags, "context": context},
            ensure_ascii=False,
        )
        return await self._chat(system, user)

    async def extract_scholarship(
        self,
        source_text: str,
        source_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        system = load_prompt("extraction")
        user = json.dumps(
            {"source_text": source_text, "source_metadata": source_metadata},
            ensure_ascii=False,
        )
        return await self._chat(system, user)

    async def explain_recommendation(
        self,
        profile: dict[str, Any],
        scholarship: dict[str, Any],
        matching_result: dict[str, Any],
    ) -> dict[str, Any]:
        system = load_prompt("explanation")
        user = json.dumps(
            {"profile": profile, "scholarship": scholarship, "result": matching_result},
            ensure_ascii=False,
        )
        return await self._chat(system, user)
