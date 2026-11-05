"""Idempotent seed: Master Tag taxonomy, demo personas and synthetic scholarships.

Run from backend/:  python -m app.seed
Re-running never deletes or overwrites data that already exists.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.models.entities import (
    ExtractionJob,
    Scholarship,
    ScholarshipRequirement,
    ScholarshipRequirementGroup,
    ScholarshipSource,
    ScholarshipTag,
    StudentProfile,
    Tag,
    TagAlias,
    TagCategory,
    User,
)
from app.services.ai.providers.mock import MockAIProvider
from app.services.auth_service import hash_password

DATA_LABEL = "DATA DEMO SINTETIS — BUKAN INFORMASI BEASISWA NYATA"

CATEGORIES: list[tuple[str, str]] = [
    ("EDU", "Pendidikan"),
    ("FIELD", "Bidang Keilmuan"),
    ("INTEREST", "Minat dan Industri"),
    ("ACH", "Prestasi"),
    ("SPORT", "Olahraga"),
    ("ART", "Seni dan Kreativitas"),
    ("ORG", "Organisasi dan Kepemimpinan"),
    ("ECON", "Kondisi Ekonomi"),
    ("GEO", "Wilayah dan Domisili"),
    ("LANG", "Bahasa"),
    ("PROFILE", "Karakteristik Penerima"),
    ("BENEFIT", "Manfaat Beasiswa"),
    ("PROGRAM", "Karakteristik Program"),
    ("OBLIGATION", "Ketentuan dan Kewajiban"),
]

# (slug, name, category code, parent slug)
TAGS: list[tuple[str, str, str, str | None]] = [
    ("edu.level.sma", "SMA", "EDU", None),
    ("edu.level.smk", "SMK", "EDU", None),
    ("edu.level.d3", "D3", "EDU", None),
    ("edu.level.d4", "D4", "EDU", None),
    ("edu.level.s1", "S1", "EDU", None),
    ("edu.level.s2", "S2", "EDU", None),
    ("edu.level.s3", "S3", "EDU", None),
    ("edu.status.active_student", "Mahasiswa Aktif", "EDU", None),
    ("edu.status.new_student", "Mahasiswa Baru", "EDU", None),
    ("field.informatics", "Informatika", "FIELD", None),
    ("field.information_systems", "Sistem Informasi", "FIELD", None),
    ("field.engineering", "Teknik", "FIELD", None),
    ("field.medicine", "Kedokteran", "FIELD", None),
    ("field.economics", "Ekonomi", "FIELD", None),
    ("field.education", "Pendidikan", "FIELD", None),
    ("field.law", "Hukum", "FIELD", None),
    ("interest.technology", "Teknologi", "INTEREST", None),
    ("interest.ai", "Kecerdasan Buatan", "INTEREST", "interest.technology"),
    ("interest.business", "Bisnis", "INTEREST", None),
    ("interest.environment", "Lingkungan", "INTEREST", None),
    ("interest.education", "Pendidikan", "INTEREST", None),
    ("achievement.academic", "Prestasi Akademik", "ACH", None),
    ("achievement.non_academic", "Prestasi Non-Akademik", "ACH", None),
    ("achievement.olympiad", "Olimpiade", "ACH", "achievement.non_academic"),
    ("achievement.research", "Penelitian", "ACH", "achievement.academic"),
    ("achievement.publication", "Publikasi", "ACH", "achievement.academic"),
    ("sport.athlete", "Atlet", "SPORT", None),
    ("sport.badminton", "Bulu Tangkis", "SPORT", "sport.athlete"),
    ("sport.football", "Sepak Bola", "SPORT", "sport.athlete"),
    ("sport.basketball", "Basket", "SPORT", "sport.athlete"),
    ("sport.swimming", "Renang", "SPORT", "sport.athlete"),
    ("sport.pencak_silat", "Pencak Silat", "SPORT", "sport.athlete"),
    ("art.music", "Musik", "ART", None),
    ("art.dance", "Tari", "ART", None),
    ("art.design", "Desain", "ART", None),
    ("art.photography", "Fotografi", "ART", None),
    ("art.literature", "Sastra", "ART", None),
    ("org.leadership", "Kepemimpinan", "ORG", None),
    ("org.student_organization", "Organisasi Kemahasiswaan", "ORG", None),
    ("org.volunteer", "Relawan", "ORG", None),
    ("org.community_service", "Pengabdian Masyarakat", "ORG", None),
    ("econ.low_income", "Keluarga Kurang Mampu", "ECON", None),
    ("econ.social_assistance_recipient", "Penerima Bantuan Sosial", "ECON", None),
    ("geo.indonesia", "Indonesia", "GEO", None),
    ("geo.sumatera_selatan", "Sumatera Selatan", "GEO", "geo.indonesia"),
    ("geo.sumatera_barat", "Sumatera Barat", "GEO", "geo.indonesia"),
    ("geo.jawa_barat", "Jawa Barat", "GEO", "geo.indonesia"),
    ("geo.jakarta", "Jakarta", "GEO", "geo.indonesia"),
    ("lang.indonesian", "Bahasa Indonesia", "LANG", None),
    ("lang.english", "Bahasa Inggris", "LANG", None),
    ("lang.japanese", "Bahasa Jepang", "LANG", None),
    ("lang.mandarin", "Bahasa Mandarin", "LANG", None),
    ("profile.high_school_student", "Siswa SMA/SMK", "PROFILE", None),
    ("profile.active_student", "Mahasiswa Aktif", "PROFILE", None),
    ("profile.new_student", "Mahasiswa Baru", "PROFILE", None),
    ("profile.final_year_student", "Mahasiswa Tingkat Akhir", "PROFILE", None),
    ("benefit.tuition", "Biaya Pendidikan", "BENEFIT", None),
    ("benefit.living_allowance", "Biaya Hidup", "BENEFIT", None),
    ("benefit.stipend", "Stipend", "BENEFIT", None),
    ("benefit.accommodation", "Akomodasi", "BENEFIT", None),
    ("benefit.research_funding", "Dana Penelitian", "BENEFIT", None),
    ("benefit.travel_funding", "Dana Perjalanan", "BENEFIT", None),
    ("program.full_scholarship", "Beasiswa Penuh", "PROGRAM", None),
    ("program.partial_scholarship", "Beasiswa Parsial", "PROGRAM", None),
    ("program.domestic", "Dalam Negeri", "PROGRAM", None),
    ("program.overseas", "Luar Negeri", "PROGRAM", None),
    ("program.exchange", "Pertukaran Pelajar", "PROGRAM", None),
    ("obligation.no_service_bond", "Tanpa Ikatan Dinas", "OBLIGATION", None),
    ("obligation.service_bond", "Ikatan Dinas", "OBLIGATION", None),
    ("obligation.community_service", "Pengabdian Masyarakat", "OBLIGATION", None),
    ("obligation.internship", "Magang", "OBLIGATION", None),
]

ALIASES: list[tuple[str, str]] = [
    ("Badminton", "sport.badminton"),
    ("Bulu Tangkis", "sport.badminton"),
    ("Computer Science", "field.informatics"),
    ("Ilmu Komputer", "field.informatics"),
    ("Sepak Bola", "sport.football"),
    ("TOEFL", "lang.english"),
    ("IELTS", "lang.english"),
    ("Sarjana", "edu.level.s1"),
]

DEMO_STUDENT_PASSWORD = "student123"
DEMO_ADMIN_PASSWORD = "admin123"

DEMO_DESCRIPTION = (
    "Saya mahasiswa S1 Informatika semester 4 di Palembang dengan IPK 3,45. "
    "Saya tertarik pada teknologi dan penelitian, aktif dalam organisasi kampus, "
    "serta pernah mengikuti kompetisi bulu tangkis tingkat universitas. "
    "Skor TOEFL saya 450."
)


def seed_categories(db: Session) -> dict[str, TagCategory]:
    categories: dict[str, TagCategory] = {}
    for code, name in CATEGORIES:
        existing = db.execute(select(TagCategory).where(TagCategory.code == code)).scalar_one_or_none()
        if existing is None:
            existing = TagCategory(code=code, name=name)
            db.add(existing)
            db.flush()
        categories[code] = existing
    return categories


def seed_tags(db: Session, categories: dict[str, TagCategory]) -> dict[str, Tag]:
    tags: dict[str, Tag] = {}
    for slug, name, code, parent_slug in TAGS:
        existing = db.execute(select(Tag).where(Tag.slug == slug)).scalar_one_or_none()
        if existing is None:
            existing = Tag(
                slug=slug,
                name=name,
                category_id=categories[code].id,
                description=f"Master Tag demo: {name}",
                is_active=True,
            )
            db.add(existing)
            db.flush()
        tags[slug] = existing

    # second pass for parents now that all rows exist
    for slug, _name, _code, parent_slug in TAGS:
        if parent_slug and tags[slug].parent_id is None:
            tags[slug].parent_id = tags[parent_slug].id

    for alias, slug in ALIASES:
        exists = db.execute(
            select(TagAlias).where(TagAlias.alias == alias, TagAlias.tag_id == tags[slug].id)
        ).scalar_one_or_none()
        if exists is None:
            db.add(TagAlias(tag_id=tags[slug].id, alias=alias, language="id"))
    db.flush()
    return tags


def seed_users(db: Session) -> tuple[User, User, StudentProfile]:
    student = db.execute(select(User).where(User.username == "demo-student")).scalar_one_or_none()
    if student is None:
        student = User(username="demo-student", display_name="Mahasiswa Demo", role="student")
        db.add(student)
        db.flush()

    admin = db.execute(select(User).where(User.username == "demo-admin")).scalar_one_or_none()
    if admin is None:
        admin = User(username="demo-admin", display_name="Admin Demo", role="admin")
        db.add(admin)
        db.flush()

    # Demo credentials only; hashed with PBKDF2 and never returned by the API.
    if not student.password_hash:
        student.password_hash = hash_password(DEMO_STUDENT_PASSWORD)
    if not admin.password_hash:
        admin.password_hash = hash_password(DEMO_ADMIN_PASSWORD)
    db.flush()

    profile = db.execute(
        select(StudentProfile).where(StudentProfile.user_id == student.id)
    ).scalar_one_or_none()
    if profile is None:
        profile = StudentProfile(
            user_id=student.id,
            description=DEMO_DESCRIPTION,
            profile_status="draft",
        )
        db.add(profile)
        db.flush()
    return student, admin, profile


def _add_scholarship(
    db: Session,
    *,
    scholarship_id: str,
    name: str,
    organizer: str,
    description: str,
    status: str,
    levels: list[str],
    benefits: list[str],
    tags: list[tuple[str, str]],
    groups: list[dict],
    tag_map: dict[str, Tag],
    admin: User,
    deadline: str | None = None,
) -> Scholarship | None:
    existing = db.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    scholarship = Scholarship(
        id=scholarship_id,
        name=name,
        organizer=organizer,
        description=description,
        education_levels=levels,
        benefits=benefits,
        application_start=None,
        application_deadline=deadline,
        verification_status=status,
        is_demo=True,
    )
    db.add(scholarship)
    db.flush()

    for slug, context in tags:
        tag = tag_map[slug]
        db.add(
            ScholarshipTag(
                scholarship_id=scholarship.id,
                tag_id=tag.id,
                context=context,
                assignment_source="admin",
                confidence=None,
                review_status="approved" if status == "verified" else "pending",
                weight=1.0,
                evidence={"note": "Data demo sintetis", "label": DATA_LABEL},
            )
        )

    for group_data in groups:
        group = ScholarshipRequirementGroup(
            scholarship_id=scholarship.id,
            name=group_data["name"],
            operator=group_data.get("operator", "AND"),
            is_mandatory=group_data.get("is_mandatory", True),
        )
        db.add(group)
        db.flush()
        for req in group_data["requirements"]:
            db.add(
                ScholarshipRequirement(
                    group_id=group.id,
                    tag_id=tag_map[req["tag_slug"]].id if req.get("tag_slug") else None,
                    field_key=req.get("field_key"),
                    operator=req.get("operator", "eq"),
                    value_json=req.get("value"),
                    unit=req.get("unit"),
                    is_mandatory=req.get("is_mandatory", True),
                    source_reference="Data demo sintetis",
                    description=req.get("description"),
                )
            )

    db.add(
        ScholarshipSource(
            scholarship_id=scholarship.id,
            source_type="text",
            source_url=None,
            raw_text=f"{DATA_LABEL}. {name} — {description}",
        )
    )
    db.flush()
    return scholarship


def seed_scholarships(db: Session, admin: User, tag_map: dict[str, Tag]) -> list[Scholarship]:
    created: list[Scholarship] = []

    tech = _add_scholarship(
        db,
        scholarship_id="demo-tech-001",
        name="Beasiswa Teknologi Nusantara",
        organizer="Yayasan Teknologi Nusantara (demo)",
        description=(
            "Beasiswa sintetis untuk mahasiswa S1 bidang teknologi/informatika dalam negeri. "
            "Mencakup biaya pendidikan. Data ini hanya untuk demonstrasi prototipe."
        ),
        status="verified",
        levels=["S1"],
        benefits=["Biaya pendidikan"],
        tags=[
            ("edu.level.s1", "target_audience"),
            ("field.informatics", "field"),
            ("interest.technology", "field"),
            ("benefit.tuition", "benefit"),
            ("program.domestic", "program"),
        ],
        groups=[
            {
                "name": "Persyaratan Utama",
                "operator": "AND",
                "is_mandatory": True,
                "requirements": [
                    {
                        "field_key": "education_level",
                        "operator": "eq",
                        "value": "S1",
                        "description": "Jenjang pendidikan S1",
                    },
                    {
                        "field_key": "major",
                        "operator": "contains",
                        "value": "Informatika",
                        "description": "Jurusan terkait informatika",
                    },
                    {
                        "field_key": "gpa",
                        "operator": "gte",
                        "value": 3.0,
                        "unit": "score",
                        "description": "IPK minimum 3.00",
                    },
                    {
                        "field_key": "toefl_score",
                        "operator": "gte",
                        "value": 500,
                        "unit": "score",
                        "description": "Skor TOEFL minimum 500",
                    },
                ],
            },
            {
                "name": "Nilai Tambah",
                "operator": "AND",
                "is_mandatory": False,
                "requirements": [
                    {
                        "tag_slug": "achievement.research",
                        "operator": "eq",
                        "value": True,
                        "is_mandatory": False,
                        "description": "Pengalaman penelitian (nilai tambah)",
                    }
                ],
            },
        ],
        tag_map=tag_map,
        admin=admin,
        deadline="2027-03-31",
    )
    created.append(tech)

    sport = _add_scholarship(
        db,
        scholarship_id="demo-sport-002",
        name="Beasiswa Atlet Muda",
        organizer="Komunitas Atlet Muda (demo)",
        description=(
            "Beasiswa sintetis untuk atlet berprestasi cabang bulu tangkis pada jenjang "
            "SMA/SMK/S1. Memberikan stipend. Data demo, bukan beasiswa nyata."
        ),
        status="verified",
        levels=["SMA", "SMK", "S1"],
        benefits=["Stipend"],
        tags=[
            ("sport.athlete", "achievement"),
            ("sport.badminton", "achievement"),
            ("edu.level.s1", "target_audience"),
            ("benefit.stipend", "benefit"),
        ],
        groups=[
            {
                "name": "Persyaratan Utama",
                "operator": "AND",
                "is_mandatory": True,
                "requirements": [
                    {
                        "tag_slug": "sport.badminton",
                        "operator": "eq",
                        "value": True,
                        "description": "Memiliki prestasi bulu tangkis",
                    }
                ],
            },
            {
                "name": "Persyaratan Tambahan",
                "operator": "AND",
                "is_mandatory": False,
                "requirements": [
                    {
                        "field_key": "education_level",
                        "operator": "in",
                        "value": ["SMA", "SMK", "S1"],
                        "is_mandatory": False,
                        "description": "Jenjang SMA/SMK/S1 (tidak menggugurkan)",
                    }
                ],
            },
        ],
        tag_map=tag_map,
        admin=admin,
        deadline="2026-12-20",
    )
    created.append(sport)

    econ = _add_scholarship(
        db,
        scholarship_id="demo-econ-003",
        name="Bantuan Pendidikan Nusantara",
        organizer="Lembaga Bantuan Pendidikan (demo)",
        description=(
            "Bantuan biaya pendidikan sintetis bagi keluarga kurang mampu. Kondisi ekonomi "
            "harus dinyatakan eksplisit oleh pelamar. Data demo."
        ),
        status="verified",
        levels=["S1", "D3", "D4"],
        benefits=["Biaya pendidikan"],
        tags=[
            ("econ.low_income", "eligibility"),
            ("benefit.tuition", "benefit"),
            ("program.partial_scholarship", "program"),
        ],
        groups=[
            {
                "name": "Persyaratan Utama",
                "operator": "AND",
                "is_mandatory": True,
                "requirements": [
                    {
                        "tag_slug": "econ.low_income",
                        "operator": "eq",
                        "value": True,
                        "description": "Tergolong keluarga kurang mampu (harus dinyatakan eksplisit)",
                    }
                ],
            }
        ],
        tag_map=tag_map,
        admin=admin,
        deadline=None,
    )
    created.append(econ)

    pending = _add_scholarship(
        db,
        scholarship_id="demo-pending-004",
        name="Beasiswa Riset Muda",
        organizer="Pusat Riset Demo",
        description=(
            "Contoh beasiswa sintetis yang masih menunggu verifikasi admin. Tidak boleh "
            "muncul pada rekomendasi utama."
        ),
        status="pending_verification",
        levels=["S1"],
        benefits=["Dana penelitian"],
        tags=[("achievement.research", "achievement"), ("edu.level.s1", "target_audience")],
        groups=[
            {
                "name": "Persyaratan Utama",
                "operator": "AND",
                "is_mandatory": True,
                "requirements": [
                    {
                        "field_key": "gpa",
                        "operator": "gte",
                        "value": 3.2,
                        "unit": "score",
                        "description": "IPK minimum 3.20",
                    }
                ],
            }
        ],
        tag_map=tag_map,
        admin=admin,
        deadline="2027-01-15",
    )
    created.append(pending)
    return created


def ensure_review_job(db: Session, scholarship: Scholarship, admin: User) -> ExtractionJob | None:
    """Every pending scholarship needs a job so admins can open and decide on it."""
    job = db.execute(
        select(ExtractionJob).where(ExtractionJob.scholarship_id == scholarship.id)
    ).scalar_one_or_none()
    if job is not None:
        return job
    now = datetime.now(timezone.utc)
    job = ExtractionJob(
        source_type="manual",
        status="completed",
        scholarship_id=scholarship.id,
        provider_mode="manual",
        provider_name="manual_entry",
        started_at=now,
        finished_at=now,
        created_by=admin.id,
        result_json={"note": "Data demo sintetis yang menunggu verifikasi", "unknown_tag_slugs": []},
    )
    db.add(job)
    db.flush()
    return job


def run_seed(db: Session) -> dict[str, int]:
    categories = seed_categories(db)
    tags = seed_tags(db, categories)
    student, admin, profile = seed_users(db)
    scholarships = seed_scholarships(db, admin, tags)
    for scholarship in scholarships:
        if scholarship.verification_status == "pending_verification":
            ensure_review_job(db, scholarship, admin)
    db.commit()

    # Deterministic sanity check on the demo description (no network, no LLM).
    mock = MockAIProvider()
    allowed = [{"slug": slug} for slug in tags]
    import asyncio

    extraction = asyncio.run(mock.extract_user_profile(DEMO_DESCRIPTION, allowed, {}))
    return {
        "categories": len(categories),
        "tags": len(tags),
        "scholarships": len(scholarships),
        "demo_facts_detected": len(extraction["facts"]),
        "demo_tags_detected": len(extraction["suggested_tags"]),
    }


def main() -> None:
    init_db()
    with SessionLocal() as db:
        summary = run_seed(db)
    print("Seed selesai (idempoten).")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(f"  label: {DATA_LABEL}")
    print("  login pengguna: demo-student / " + DEMO_STUDENT_PASSWORD)
    print("  login admin   : demo-admin / " + DEMO_ADMIN_PASSWORD)


if __name__ == "__main__":
    main()
