"""SQLAlchemy models. Single Master Tag table shared by users and scholarships."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | admin
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    extracted_facts_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latest_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmed_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    profile_status: Mapped[str] = mapped_column(String(20), default="draft")

    education_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    major: Mapped[str | None] = mapped_column(String(120), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(160), nullable=True)
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    domicile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    toefl_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    toefl_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    achievements_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    facts_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # One-time onboarding marker: tag submission is allowed exactly once per user.
    profile_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")


class TagCategory(Base):
    __tablename__ = "tag_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(80))

    tags: Mapped[list["Tag"]] = relationship(back_populates="category")


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("tag_categories.id"))
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tags.id"), nullable=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[TagCategory] = relationship(back_populates="tags")
    aliases: Mapped[list["TagAlias"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class TagAlias(Base):
    __tablename__ = "tag_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(160), index=True)
    language: Mapped[str] = mapped_column(String(10), default="id")

    tag: Mapped[Tag] = relationship(back_populates="aliases")


class UserTag(Base, TimestampMixin):
    __tablename__ = "user_tags"
    __table_args__ = (UniqueConstraint("user_id", "tag_id", "context", name="uq_user_tag_context"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"))
    context: Mapped[str] = mapped_column(String(30))
    assignment_source: Mapped[str] = mapped_column(String(20), default="ai")  # system|ai|user
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmation_status: Mapped[str] = mapped_column(String(20), default="suggested")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    tag: Mapped[Tag] = relationship()


class Scholarship(Base, TimestampMixin):
    __tablename__ = "scholarships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    organizer: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    education_levels: Mapped[list | None] = mapped_column(JSON, nullable=True)
    benefits: Mapped[list | None] = mapped_column(JSON, nullable=True)
    application_start: Mapped[str | None] = mapped_column(String(40), nullable=True)
    application_deadline: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="draft")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)

    tags: Mapped[list["ScholarshipTag"]] = relationship(
        back_populates="scholarship", cascade="all, delete-orphan"
    )
    sources: Mapped[list["ScholarshipSource"]] = relationship(
        back_populates="scholarship", cascade="all, delete-orphan"
    )
    requirement_groups: Mapped[list["ScholarshipRequirementGroup"]] = relationship(
        back_populates="scholarship", cascade="all, delete-orphan"
    )


class ScholarshipTag(Base, TimestampMixin):
    __tablename__ = "scholarship_tags"
    __table_args__ = (
        UniqueConstraint("scholarship_id", "tag_id", "context", name="uq_scholarship_tag_context"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scholarship_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scholarships.id", ondelete="CASCADE")
    )
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"))
    context: Mapped[str] = mapped_column(String(30))
    assignment_source: Mapped[str] = mapped_column(String(20), default="ai")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scholarship: Mapped[Scholarship] = relationship(back_populates="tags")
    tag: Mapped[Tag] = relationship()


class ScholarshipSource(Base):
    __tablename__ = "scholarship_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scholarship_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scholarships.id", ondelete="CASCADE"), nullable=True
    )
    extraction_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20))  # url|text|pdf
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scholarship: Mapped[Scholarship | None] = relationship(back_populates="sources")


class ScholarshipRequirementGroup(Base):
    __tablename__ = "scholarship_requirement_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scholarship_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scholarships.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(160), default="Persyaratan")
    operator: Mapped[str] = mapped_column(String(5), default="AND")  # AND|OR
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)

    scholarship: Mapped[Scholarship] = relationship(back_populates="requirement_groups")
    requirements: Mapped[list["ScholarshipRequirement"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class ScholarshipRequirement(Base):
    __tablename__ = "scholarship_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scholarship_requirement_groups.id", ondelete="CASCADE")
    )
    tag_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tags.id"), nullable=True)
    field_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    operator: Mapped[str] = mapped_column(String(20), default="eq")
    value_json: Mapped[dict | list | str | int | float | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    group: Mapped[ScholarshipRequirementGroup] = relationship(back_populates="requirements")
    tag: Mapped[Tag | None] = relationship()


class ExtractionJob(Base, TimestampMixin):
    __tablename__ = "extraction_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scholarship_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), default="text")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ScholarshipVerification(Base):
    __tablename__ = "scholarship_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scholarship_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scholarships.id", ondelete="CASCADE")
    )
    extraction_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision: Mapped[str] = mapped_column(String(20))  # approved|rejected
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserScholarshipSubmission(Base):
    """Screenshot a student sends for admin review (no OCR: admin transcribes)."""

    __tablename__ = "user_scholarship_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_mime: Mapped[str] = mapped_column(String(60))
    image_data: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scholarship_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    user: Mapped[User] = relationship()


class AuthSession(Base):
    """Opaque demo session. Only the SHA-256 hash of the token is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()


class UserScholarshipBookmark(Base):
    __tablename__ = "user_scholarship_bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "scholarship_id", name="uq_user_scholarship_bookmark"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    scholarship_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scholarships.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
