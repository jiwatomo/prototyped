"""Deterministic MockAIProvider.

No network access. Rules are keyword/regex based on fixtures so the demo works
offline and every output stays schema-valid and inside the Master Tag list.
"""
from __future__ import annotations

import re
from typing import Any

MONTHS = (
    "Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|"
    "November|Desember|January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)

EDUCATION_PATTERNS: list[tuple[str, str]] = [
    (r"\bs3\b|\bdoktor\b", "S3"),
    (r"\bs2\b|\bmagister\b", "S2"),
    (r"\bs1\b|\bsarjana\b|\bundergraduate\b", "S1"),
    (r"\bd4\b", "D4"),
    (r"\bd3\b|\bdiploma tiga\b", "D3"),
    (r"\bsmk\b|\bkejuruan\b", "SMK"),
    (r"\bsma\b|\bsekolah menengah atas\b", "SMA"),
]

MAJOR_PATTERNS: list[tuple[str, str]] = [
    (r"\binformatika\b|\bcomputer science\b|\bilmu komputer\b|\bteknik informatika\b", "Informatika"),
    (r"\bsistem informasi\b|\binformation systems?\b", "Sistem Informasi"),
    (r"\bteknik\b|\bengineering\b", "Teknik"),
    (r"\bkedokteran\b|\bmedicine\b", "Kedokteran"),
    (r"\bekonomi\b|\beconomics?\b", "Ekonomi"),
    (r"\bhukum\b|\blaw\b", "Hukum"),
    (r"\bpendidikan\b|\beducation\b", "Pendidikan"),
]

CITIES = [
    ("palembang", "Palembang", "geo.sumatera_selatan"),
    ("sumatera selatan", "Sumatera Selatan", "geo.sumatera_selatan"),
    ("sumatra selatan", "Sumatera Selatan", "geo.sumatera_selatan"),
    ("padang", "Padang", "geo.sumatera_barat"),
    ("sumatera barat", "Sumatera Barat", "geo.sumatera_barat"),
    ("bandung", "Bandung", "geo.jawa_barat"),
    ("jawa barat", "Jawa Barat", "geo.jawa_barat"),
    ("jakarta", "Jakarta", "geo.jakarta"),
    ("indonesia", "Indonesia", "geo.indonesia"),
]

# (regex, [(slug, context), ...]) — user profile contexts
USER_TAG_RULES: list[tuple[str, list[tuple[str, str]]]] = [
    (r"\bbulu tangkis\b|\bbadminton\b", [("sport.badminton", "achievement"), ("sport.athlete", "achievement")]),
    (r"\bsepak bola\b|\bfootball\b", [("sport.football", "achievement")]),
    (r"\bbasket\b|\bbasketball\b", [("sport.basketball", "achievement")]),
    (r"\brenang\b|\bswimming\b", [("sport.swimming", "achievement")]),
    (r"\bpencak silat\b", [("sport.pencak_silat", "achievement")]),
    (r"\bolimpiade\b|\bolympiad\b", [("achievement.olympiad", "achievement")]),
    (r"\bpenelitian\b|\briset\b|\bresearch\b", [("achievement.research", "achievement")]),
    (r"\bpublikasi\b|\bjurnal\b|\bpublication\b", [("achievement.publication", "achievement")]),
    (r"\bjuara\b|\bkompetisi\b|\blomba\b|\bcompetition\b", [("achievement.non_academic", "achievement")]),
    (r"\borganisasi\b|\borganization\b", [("org.student_organization", "profile")]),
    (r"\bketua\b|\bleadership\b|\bkepemimpinan\b", [("org.leadership", "profile")]),
    (r"\brelawan\b|\bvolunteer\b|\bksr\b", [("org.volunteer", "profile")]),
    (r"\bteknologi\b|\btechnology\b|\btech\b", [("interest.technology", "interest")]),
    (r"\bkecerdasan buatan\b|\bartificial intelligence\b|\b\bai\b", [("interest.ai", "interest")]),
    (r"\bbisnis\b|\bbusiness\b|\bwirausaha\b", [("interest.business", "interest")]),
    (r"\blingkungan\b|\benvironment\b", [("interest.environment", "interest")]),
    (r"\btoefl\b|\bielts\b|\bbahasa inggris\b|\benglish\b", [("lang.english", "language")]),
    (r"\bbahasa jepang\b|\bjapanese\b", [("lang.japanese", "language")]),
    (r"\bmandarin\b|\bchinese\b", [("lang.mandarin", "language")]),
    (r"\bkurang mampu\b|\btidak mampu\b|\bekonomi lemah\b|\bkip\b|\bbantuan biaya\b", [("econ.low_income", "economic")]),
    (r"\bpenerima bantuan sosial\b|\bpkh\b|\bbantuan sosial\b", [("econ.social_assistance_recipient", "economic")]),
]

# Scholarship-facing keyword rules (context must be a scholarship context)
SCHOLARSHIP_TAG_RULES: list[tuple[str, list[tuple[str, str]]]] = [
    (r"\binformatika\b|\bilmu komputer\b|\bcomputer science\b", [("field.informatics", "field")]),
    (r"\bsistem informasi\b", [("field.information_systems", "field")]),
    (r"\bteknik\b|\bengineering\b", [("field.engineering", "field")]),
    (r"\bkedokteran\b|\bmedicine\b", [("field.medicine", "field")]),
    (r"\bekonomi\b|\beconomics?\b", [("field.economics", "field")]),
    (r"\bhukum\b|\blaw\b", [("field.law", "field")]),
    (r"\bteknologi\b|\btechnology\b", [("interest.technology", "field")]),
    (r"\bbulu tangkis\b|\bbadminton\b|\bolahraga\b|\batlet\b", [("sport.athlete", "achievement")]),
    (r"\bbulu tangkis\b|\bbadminton\b", [("sport.badminton", "achievement")]),
    (r"\bpenelitian\b|\briset\b|\bresearch\b", [("achievement.research", "achievement")]),
    (r"\bkurang mampu\b|\bekonomi lemah\b|\btidak mampu\b|\bkip\b", [("econ.low_income", "eligibility")]),
    (r"\bbiaya (?:pendidikan|kuliah)\b|\bukt\b|\btuition\b", [("benefit.tuition", "benefit")]),
    (r"\buang saku\b|\bstipend\b", [("benefit.stipend", "benefit")]),
    (r"\bpenuh\b|\bfull scholarship\b", [("program.full_scholarship", "program")]),
    (r"\bdalam negeri\b|\bdomestik\b", [("program.domestic", "program")]),
    (r"\bluar negeri\b|\boverseas\b", [("program.overseas", "program")]),
]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _evidence_for(text: str, pattern: str) -> str:
    regex = re.compile(pattern, re.IGNORECASE)
    for sentence in _sentences(text):
        if regex.search(sentence):
            return sentence[:300]
    match = regex.search(text)
    if match:
        start = max(0, match.start() - 80)
        return text[start : match.end() + 80].strip()[:300]
    return ""


class MockAIProvider:
    """Deterministic offline provider used as demo default and as fallback."""

    name = "mock"
    model: str | None = None

    # ------------------------------------------------------------- profile
    async def extract_user_profile(
        self,
        description: str,
        allowed_tags: list[dict[str, Any]],
        aliases: dict[str, str],
    ) -> dict[str, Any]:
        extracted = self._extract_facts(description)
        fact_rows = extracted["facts"]
        fact_map = {f["field_key"]: f["value"] for f in fact_rows}
        fact_evidence = {f["field_key"]: f.get("evidence", "") for f in fact_rows}

        tags: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        if fact_map.get("education_level"):
            slug = f"edu.level.{str(fact_map['education_level']).lower()}"
            tags.append(
                {
                    "slug": slug,
                    "context": "profile",
                    "confidence": 0.95,
                    "evidence": fact_evidence.get("education_level", ""),
                }
            )
        if fact_map.get("major"):
            for pattern, name in MAJOR_PATTERNS:
                if name.lower() in str(fact_map["major"]).lower():
                    slug = {
                        "Informatika": "field.informatics",
                        "Sistem Informasi": "field.information_systems",
                        "Teknik": "field.engineering",
                        "Kedokteran": "field.medicine",
                        "Ekonomi": "field.economics",
                        "Hukum": "field.law",
                        "Pendidikan": "field.education",
                    }.get(name)
                    if slug:
                        tags.append(
                            {
                                "slug": slug,
                                "context": "profile",
                                "confidence": 0.93,
                                "evidence": fact_evidence.get("major", ""),
                            }
                        )
                    break

        for pattern, slug_pairs in USER_TAG_RULES:
            if not re.search(pattern, description, re.IGNORECASE):
                continue
            evidence = _evidence_for(description, pattern)
            for slug, context in slug_pairs:
                tags.append(
                    {
                        "slug": slug,
                        "context": context,
                        "confidence": 0.85,
                        "evidence": evidence,
                    }
                )

        allowed = {t["slug"]: t for t in allowed_tags}
        result: list[dict[str, Any]] = []
        for tag in tags:
            key = (tag["slug"], tag["context"])
            if tag["slug"] not in allowed or key in seen:
                continue
            seen.add(key)
            result.append(tag)

        return {"facts": [dict(f) for f in fact_rows], "suggested_tags": result}

    def _extract_facts(self, text: str) -> dict[str, Any]:
        facts: list[dict[str, Any]] = []
        evidence: dict[str, str] = {}

        for pattern, level in EDUCATION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                facts.append(
                    {
                        "field_key": "education_level",
                        "value": level,
                        "confidence": 0.95,
                        "evidence": _evidence_for(text, pattern),
                    }
                )
                evidence["education_level"] = _evidence_for(text, pattern)
                break

        for pattern, major in MAJOR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                facts.append(
                    {
                        "field_key": "major",
                        "value": major,
                        "confidence": 0.9,
                        "evidence": _evidence_for(text, pattern),
                    }
                )
                evidence["major"] = _evidence_for(text, pattern)
                break

        gpa_match = re.search(r"(?:ipk|gpa)\s*(?:saya\s*)?(?:adalah\s*)?([0-4](?:[.,]\d{1,2})?)", text, re.IGNORECASE)
        if gpa_match:
            facts.append(
                {
                    "field_key": "gpa",
                    "value": float(gpa_match.group(1).replace(",", ".")),
                    "confidence": 0.98,
                    "evidence": _evidence_for(text, r"(?:ipk|gpa)"),
                }
            )

        toefl_match = re.search(
            r"toefl(?:\s*(?:itp|ibt|pbt))?[^\d\n]{0,25}(\d{2,3})", text, re.IGNORECASE
        )
        if toefl_match:
            facts.append(
                {
                    "field_key": "toefl_score",
                    "value": int(toefl_match.group(1)),
                    "confidence": 0.97,
                    "evidence": _evidence_for(text, r"toefl"),
                }
            )
            kind = "iBT" if re.search(r"toefl\s*ibt", text, re.IGNORECASE) else "ITP"
            facts.append(
                {
                    "field_key": "toefl_type",
                    "value": kind,
                    "confidence": 0.8,
                    "evidence": _evidence_for(text, r"toefl"),
                }
            )

        semester_match = re.search(r"semester\s*(\d{1,2})", text, re.IGNORECASE)
        if semester_match:
            facts.append(
                {
                    "field_key": "semester",
                    "value": int(semester_match.group(1)),
                    "confidence": 0.95,
                    "evidence": _evidence_for(text, r"semester"),
                }
            )

        for keyword, canonical, _geo_slug in CITIES:
            if re.search(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE):
                facts.append(
                    {
                        "field_key": "domicile",
                        "value": canonical,
                        "confidence": 0.9,
                        "evidence": _evidence_for(text, re.escape(keyword)),
                    }
                )
                break

        institution_match = re.search(
            r"\b(Universitas|Institut|Politeknik|Sekolah Tinggi)\s+([A-Z][\w\-]*(?:\s+[A-Z][\w\-]*){0,3})",
            text,
        )
        if institution_match:
            facts.append(
                {
                    "field_key": "institution",
                    "value": institution_match.group(0).strip(),
                    "confidence": 0.85,
                    "evidence": _evidence_for(text, r"(Universitas|Institut|Politeknik)"),
                }
            )

        achievements = [
            s
            for s in _sentences(text)
            if re.search(r"\b(juara|kompetisi|lomba|olimpiade|prestasi)\b", s, re.IGNORECASE)
        ]
        if achievements:
            facts.append(
                {
                    "field_key": "achievements",
                    "value": achievements[:3],
                    "confidence": 0.9,
                    "evidence": achievements[0][:300],
                }
            )

        return {"facts": facts, "_evidence": evidence}

    # -------------------------------------------------------- classification
    async def classify_tags(
        self,
        text: str,
        allowed_tags: list[dict[str, Any]],
        context: str | None = None,
    ) -> dict[str, Any]:
        allowed = {t["slug"] for t in allowed_tags}
        tags: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pattern, slug_pairs in USER_TAG_RULES + SCHOLARSHIP_TAG_RULES:
            if not re.search(pattern, text, re.IGNORECASE):
                continue
            for slug, ctx in slug_pairs:
                if context and ctx != context:
                    continue
                if slug not in allowed or slug in seen:
                    continue
                seen.add(slug)
                tags.append(
                    {
                        "slug": slug,
                        "context": ctx,
                        "confidence": 0.8,
                        "evidence": _evidence_for(text, pattern),
                    }
                )
        return {"tags": tags[:12]}

    # ------------------------------------------------------------ extraction
    async def extract_scholarship(
        self,
        source_text: str,
        source_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        text = source_text or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        name = ""
        name_match = re.search(r"(?im)^\s*(beasiswa[^\n\.]{2,120})", text)
        if name_match:
            name = name_match.group(1).strip()
        elif lines:
            name = lines[0][:120]
        # Keep the title clean when the whole source arrives as a single line.
        name = re.split(r"(?i)\s*penyelenggara\b", name)[0].strip()[:120]

        organizer = ""
        org_match = re.search(r"(?i)penyelenggara\s*[:\-]\s*([^\n]{2,160})", text)
        if org_match:
            organizer = re.split(
                r"(?i)\s*(?:ditujukan|manfaat|batas|persyaratan|syarat|deadline)\b",
                org_match.group(1),
            )[0].strip()

        levels = []
        for pattern, level in EDUCATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE) and level not in levels:
                levels.append(level)

        benefits: list[str] = []
        benefit_rules = [
            (r"\bbiaya (?:pendidikan|kuliah)\b|\bukt\b|\btuition\b", "Biaya pendidikan"),
            (r"\buang saku\b|\bstipend\b", "Uang saku"),
            (r"\basrama\b|\bakomodasi\b|\baccommodation\b", "Akomodasi"),
            (r"\bdana penelitian\b|\bresearch funding\b", "Dana penelitian"),
        ]
        for pattern, label in benefit_rules:
            if re.search(pattern, text, re.IGNORECASE) and label not in benefits:
                benefits.append(label)

        deadline = None
        date_match = re.search(rf"(\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}})", text)
        if date_match:
            deadline = date_match.group(1)
        else:
            iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if iso_match:
                deadline = iso_match.group(1)

        requirements: list[dict[str, Any]] = []
        existing_fields: set[str] = set()

        gpa_match = re.search(
            r"(?i)ipk\s*(?:minimal|minimum|min\.?)?\s*([0-4](?:[.,]\d{1,2})?)", text
        )
        if gpa_match:
            requirements.append(
                {
                    "group": "Persyaratan Utama",
                    "group_operator": "AND",
                    "is_mandatory": True,
                    "field_key": "gpa",
                    "operator": "gte",
                    "value": float(gpa_match.group(1).replace(",", ".")),
                    "unit": "score",
                    "description": "IPK minimum",
                    "source_reference": _evidence_for(text, r"ipk"),
                }
            )
            existing_fields.add("gpa")

        toefl_match = re.search(
            r"(?i)toefl\s*(?:itp\s*)?(?:minimal|minimum|min\.?)?\s*(\d{2,3})", text
        )
        if toefl_match:
            requirements.append(
                {
                    "group": "Persyaratan Utama",
                    "group_operator": "AND",
                    "is_mandatory": True,
                    "field_key": "toefl_score",
                    "operator": "gte",
                    "value": int(toefl_match.group(1)),
                    "unit": "score",
                    "description": "Skor TOEFL minimum",
                    "source_reference": _evidence_for(text, r"toefl"),
                }
            )
            existing_fields.add("toefl_score")

        if re.search(r"(?i)\bprestasi olahraga\b|\batlet\b", text):
            requirements.append(
                {
                    "group": "Persyaratan Utama",
                    "group_operator": "AND",
                    "is_mandatory": True,
                    "tag_slug": "sport.athlete",
                    "operator": "eq",
                    "value": True,
                    "description": "Memiliki prestasi olahraga",
                    "source_reference": _evidence_for(text, r"prestasi olahraga|atlet"),
                }
            )

        if re.search(r"(?i)\bkurang mampu\b|\bekonomi lemah\b|\bkip\b", text):
            requirements.append(
                {
                    "group": "Persyaratan Utama",
                    "group_operator": "AND",
                    "is_mandatory": True,
                    "tag_slug": "econ.low_income",
                    "operator": "eq",
                    "value": True,
                    "description": "Ditujukan bagi pelamar dari keluarga kurang mampu",
                    "source_reference": _evidence_for(text, r"kurang mampu|ekonomi lemah|kip"),
                }
            )

        suggested: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()
        for pattern, slug_pairs in SCHOLARSHIP_TAG_RULES:
            if not re.search(pattern, text, re.IGNORECASE):
                continue
            for slug, ctx in slug_pairs:
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                suggested.append(
                    {
                        "slug": slug,
                        "context": ctx,
                        "confidence": 0.82,
                        "evidence": _evidence_for(text, pattern),
                    }
                )

        if levels:
            level = levels[0]
            suggested.append(
                {
                    "slug": f"edu.level.{level.lower()}",
                    "context": "target_audience",
                    "confidence": 0.9,
                    "evidence": _evidence_for(text, EDUCATION_PATTERNS[0][0]) or text[:120],
                }
            )

        description = text.strip()[:600]
        return {
            "scholarship": {
                "name": name or "Beasiswa Tanpa Judul",
                "organizer": organizer,
                "description": description,
                "education_levels": levels,
                "benefits": benefits,
                "application_start": None,
                "application_deadline": deadline,
            },
            "suggested_tags": suggested[:12],
            "requirements": requirements,
            "verification_status": "pending_verification",
        }

    # ---------------------------------------------------------- explanation
    async def explain_recommendation(
        self,
        profile: dict[str, Any],
        scholarship: dict[str, Any],
        matching_result: dict[str, Any],
    ) -> dict[str, Any]:
        status = matching_result.get("eligibility_status")
        score = matching_result.get("relevance_score")
        score_text = "belum cukup preferensi" if score is None else f"{score:.1f}"
        failed = [
            r
            for r in matching_result.get("requirements", [])
            if r.get("status") == "not_met"
        ]
        unknown = [
            r
            for r in matching_result.get("requirements", [])
            if r.get("status") == "unknown"
        ]
        parts = [
            f"Relevansi tag {score_text} untuk {scholarship.get('name', 'beasiswa ini')}."
        ]
        if status == "eligible":
            parts.append("Seluruh persyaratan wajib terpenuhi berdasarkan data profil yang dikonfirmasi.")
        elif status == "not_eligible":
            names = ", ".join(r.get("description") or r.get("field_key", "") for r in failed)
            parts.append(f"Belum memenuhi persyaratan wajib: {names}.")
        else:
            names = ", ".join(r.get("description") or r.get("field_key", "") for r in unknown)
            parts.append(f"Sebagian persyaratan wajib belum dapat dinilai: {names}.")
        parts.append("Skor relevansi bukan probabilitas diterima.")
        return {"explanation": " ".join(parts)}
