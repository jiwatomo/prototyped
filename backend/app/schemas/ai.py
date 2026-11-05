"""Pydantic schemas for AI provider outputs and for request payloads."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_REQUIREMENT_OPERATORS = {
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "between",
    "contains",
}

VALID_USER_CONTEXTS = {
    "profile",
    "interest",
    "achievement",
    "preference",
    "location",
    "language",
    "economic",
}

VALID_SCHOLARSHIP_CONTEXTS = {
    "eligibility",
    "target_audience",
    "field",
    "achievement",
    "benefit",
    "program",
    "location",
    "obligation",
}

PROFILE_FACT_KEYS = {
    "education_level",
    "major",
    "institution",
    "gpa",
    "domicile",
    "toefl_type",
    "toefl_score",
    "semester",
    "achievements",
}

SENSITIVE_FACT_KEYS = {"economic_status", "disability", "religion"}


# --------------------------------------------------------------------------- AI


class SuggestedTag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    context: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""

    @field_validator("context")
    @classmethod
    def _context_ok(cls, value: str) -> str:
        if value not in VALID_USER_CONTEXTS | VALID_SCHOLARSHIP_CONTEXTS:
            raise ValueError(f"unknown tag context: {value}")
        return value


class ExtractedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_key: str
    value: str | float | int | list[str] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: str = ""

    @field_validator("field_key")
    @classmethod
    def _known_key(cls, value: str) -> str:
        if value not in PROFILE_FACT_KEYS:
            raise ValueError(f"unknown fact key: {value}")
        if value in SENSITIVE_FACT_KEYS:
            raise ValueError(f"sensitive fact key not allowed: {value}")
        return value


class ProfileExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[ExtractedFact] = Field(default_factory=list)
    suggested_tags: list[SuggestedTag] = Field(default_factory=list)


class ScholarshipInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    organizer: str = ""
    description: str = ""
    education_levels: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    application_start: str | None = None
    application_deadline: str | None = None


class ExtractedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str = "Persyaratan Utama"
    group_operator: Literal["AND", "OR"] = "AND"
    is_mandatory: bool = True
    tag_slug: str | None = None
    field_key: str | None = None
    operator: str = "eq"
    value: Any = None
    unit: str | None = None
    description: str | None = None
    source_reference: str | None = None

    @field_validator("operator")
    @classmethod
    def _operator_ok(cls, value: str) -> str:
        if value not in VALID_REQUIREMENT_OPERATORS:
            raise ValueError(f"unknown operator: {value}")
        return value


class ScholarshipExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scholarship: ScholarshipInfo
    suggested_tags: list[SuggestedTag] = Field(default_factory=list)
    requirements: list[ExtractedRequirement] = Field(default_factory=list)
    verification_status: str = "pending_verification"


class TagClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tags: list[SuggestedTag] = Field(default_factory=list)


class RecommendationExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str


class AIMeta(BaseModel):
    provider_mode: Literal["llm", "mock", "mock_fallback"]
    provider_name: str
    model: str | None = None
    fallback_reason: str | None = None


# ---------------------------------------------------------------------- requests


class ProfileAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class FactOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    education_level: str | None = None
    major: str | None = None
    institution: str | None = None
    gpa: float | None = None
    domicile: str | None = None
    toefl_type: str | None = None
    toefl_score: int | None = None
    achievements: list[str] | None = None

    @field_validator("gpa")
    @classmethod
    def _gpa_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 4.0):
            raise ValueError("gpa harus berada di antara 0 dan 4")
        return value

    @field_validator("toefl_score")
    @classmethod
    def _toefl_range(cls, value: int | None) -> int | None:
        if value is not None and not (0 <= value <= 677):
            raise ValueError("skor TOEFL harus berada di antara 0 dan 677")
        return value


class TagDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    context: str
    decision: Literal["confirm", "reject"]
    weight: float | None = Field(default=None, ge=0.0, le=1.0)


class ProfileConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    facts: FactOverride = Field(default_factory=FactOverride)
    tags: list[TagDecision] = Field(default_factory=list)


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    facts: FactOverride | None = None


class TagReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    decision: Literal["approve", "reject", "pending"]
    weight: float | None = Field(default=None, ge=0.0, le=1.0)


class ExtractionPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    organizer: str | None = None
    description: str | None = None
    education_levels: list[str] | None = None
    benefits: list[str] | None = None
    application_start: str | None = None
    application_deadline: str | None = None
    requirements: list[ExtractedRequirement] | None = None
    tags: list[TagReviewDecision] | None = None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("alasan penolakan wajib diisi")
        return value.strip()


# ------------------------------------------------------- manual admin entry


class ManualTagInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    context: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("context")
    @classmethod
    def _scholarship_context(cls, value: str) -> str:
        if value not in VALID_SCHOLARSHIP_CONTEXTS:
            raise ValueError(f"context beasiswa tidak valid: {value}")
        return value


class ManualRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_key: str | None = None
    tag_slug: str | None = None
    operator: str = "eq"
    value: Any = None
    unit: str | None = None
    description: str | None = None
    is_mandatory: bool = True

    @field_validator("operator")
    @classmethod
    def _operator_ok(cls, value: str) -> str:
        if value not in VALID_REQUIREMENT_OPERATORS:
            raise ValueError(f"unknown operator: {value}")
        return value

    @field_validator("value")
    @classmethod
    def _value_present(cls, value: Any) -> Any:
        if value is None or value == "":
            raise ValueError("nilai persyaratan wajib diisi")
        return value


class ManualScholarshipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=200)
    organizer: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    education_levels: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    application_start: str | None = None
    application_deadline: str | None = None
    tags: list[ManualTagInput] = Field(default_factory=list)
    requirements: list[ManualRequirementInput] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nama beasiswa wajib diisi")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def _one_tag(cls, value: list[ManualTagInput]) -> list[ManualTagInput]:
        if not value:
            raise ValueError("minimal satu tag diperlukan untuk pencocokan")
        seen = set()
        unique = []
        for tag in value:
            key = (tag.slug, tag.context)
            if key not in seen:
                seen.add(key)
                unique.append(tag)
        return unique


# ------------------------------------------------------------ admin: users


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$"
    )
    display_name: str = Field(default="", max_length=120)
    role: Literal["student", "admin"] = "student"
    password: str = Field(min_length=8, max_length=200)


class AdminPasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str | None = Field(default=None, max_length=200)


class SubmissionProcess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["processed", "rejected"]
    reason: str | None = None
    scholarship_id: str | None = None
