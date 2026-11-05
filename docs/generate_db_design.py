"""Generate docs/db-design.html from the live SQLAlchemy metadata + SQLite counts."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  (register mappings)

OUT = Path(__file__).resolve().parent / "db-design.html"
DB = BACKEND / "app.db"

PURPOSE = {
    "users": "Akun demo: pengguna dan admin, termasuk hash kata sandi.",
    "auth_sessions": "Sesi login opaque; hanya SHA-256 token yang disimpan, dengan masa berlaku dan revokasi.",
    "student_profiles": "Deskripsi asli, hasil analisis sementara, fakta terstruktur terkonfirmasi, dan penanda kirim sekali.",
    "tag_categories": "Kategori induk Universal Master Tag (14 kategori seed).",
    "tags": "Master Tag tunggal untuk pengguna dan beasiswa; slug unik, hierarki via parent_id.",
    "tag_aliases": "Sinonim/variasi bahasa yang dinormalisasi ke slug resmi.",
    "user_tags": "Relasi pengguna–tag: konteks, sumber, confidence, status konfirmasi, bobot, bukti.",
    "scholarships": "Data beasiswa dan status verifikasi (status pendaftaran dihitung dari tanggal).",
    "scholarship_tags": "Relasi beasiswa–tag: konteks, status review admin, bobot, bukti.",
    "scholarship_sources": "Sumber beasiswa: URL, teks, PDF, atau input manual, terkait job ekstraksi.",
    "scholarship_requirement_groups": "Kelompok persyaratan dengan operator AND/OR dan flag wajib/opsional.",
    "scholarship_requirements": "Aturan persyaratan terstruktur: field/operator/nilai atau tag.",
    "extraction_jobs": "Riwayat ekstraksi (AI maupun manual): sumber, status, hasil JSON, metadata provider.",
    "scholarship_verifications": "Jejak keputusan admin: approved/rejected beserta alasan.",
    "user_scholarship_bookmarks": "Bookmark pengguna (skema siap; UI belum memakai).",
    "user_scholarship_submissions": "Screenshot beasiswa kiriman pengguna untuk antrean verifikasi admin.",
}

COLUMN_NOTES = {
    "id": "UUID string (36 karakter), primary key.",
    "created_at": "Waktu pembuatan (UTC).",
    "updated_at": "Waktu perubahan terakhir (UTC).",
    "user_id": "Pemilik data.",
    "tag_id": "Referensi ke Master Tag.",
    "context": "Konteks relasi tag (lihat catatan desain).",
    "weight": "Bobot 0–1; default 1.0.",
    "confidence": "Keyakinan AI 0–1; bukan bukti kebenaran.",
    "evidence": "JSON kutipan/alasan penetapan.",
    "review_status": "pending / approved / rejected (admin).",
    "confirmation_status": "suggested / confirmed / rejected (pengguna/sistem).",
    "verification_status": "draft / pending_verification / verified / rejected.",
    "assignment_source": "system / ai / user / admin.",
    "profile_status": "draft / analyzed / confirmed.",
    "profile_submitted_at": "Penanda kirim sekali; bila terisi, analyze & confirm ditolak 409.",
    "latest_analysis_id": "UUID analisis terbaru yang boleh dikonfirmasi.",
    "confirmed_analysis_id": "Analisis yang sudah dikonfirmasi (sekali pakai).",
    "extracted_facts_json": "Hasil AI yang belum dikonfirmasi.",
    "password_hash": "PBKDF2-SHA256 (200k iterasi); tidak pernah dikembalikan API.",
    "token_hash": "SHA-256 token sesi; token asli hanya di klien.",
    "expires_at": "Akhir masa berlaku sesi.",
    "revoked_at": "Diisi saat logout / reset password.",
    "slug": "Identifier stabil untuk integrasi.",
    "parent_id": "Hierarki Master Tag (nullable).",
    "operator": "eq/neq/gt/gte/lt/lte/in/not_in/between/contains (requirement) atau AND/OR (group).",
    "value_json": "Nilai atau daftar nilai pembanding.",
    "field_key": "gpa/toefl_score/education_level/major/domicile/semester/age/achievements.",
    "is_mandatory": "Persyaratan wajib menggugurkan kelayakan; opsional tidak.",
    "application_status": "Tidak disimpan; dihitung dari tanggal (open/upcoming/closed/unknown).",
    "image_data": "BLOB gambar screenshot (PNG/JPEG/WEBP, maks 5 MB).",
    "status": "Status proses (job/sesi/kiriman) sesuai tabel.",
}

UNIQUE_NOTES = {
    "user_tags": "(user_id, tag_id, context)",
    "scholarship_tags": "(scholarship_id, tag_id, context)",
    "user_scholarship_bookmarks": "(user_id, scholarship_id)",
}

CSS = """
:root { --bg:#f5f6f8; --surface:#fff; --border:#d8dce3; --text:#1d2430; --muted:#5d6675;
        --primary:#1f5fa8; --pk:#8a5a09; --fk:#17487f; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text);
       font-family:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif; line-height:1.5; }
.wrap { max-width:1180px; margin:0 auto; padding:2rem 1.25rem 4rem; }
h1 { font-size:1.6rem; margin:0 0 .3rem; letter-spacing:-.01em; }
h2 { font-size:1.1rem; margin:2.2rem 0 .6rem; }
h3 { font-size:1rem; margin:1.4rem 0 .4rem; }
p { margin:.3rem 0 .8rem; }
.muted { color:var(--muted); }
.small { font-size:.82rem; }
.banner { background:#fff6d6; color:#6b4b00; border:1px solid #ecd9a0; border-radius:8px;
          padding:.55rem .8rem; font-size:.84rem; margin:1rem 0 1.6rem; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px;
        padding:1rem 1.1rem; margin:.8rem 0; box-shadow:0 1px 2px rgba(20,30,45,.06); }
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:.84rem; background:var(--surface); }
caption { caption-side:top; text-align:left; font-weight:700; padding:.5rem .2rem; }
th, td { border-bottom:1px solid var(--border); padding:.4rem .55rem; text-align:left; vertical-align:top; }
th { background:#eef2f7; font-size:.74rem; text-transform:uppercase; letter-spacing:.04em; color:#39424f; }
tbody tr:hover { background:#fafbfd; }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.8rem;
       background:#eef2f7; padding:.05rem .3rem; border-radius:4px; }
.tag { display:inline-block; padding:.05rem .4rem; border-radius:999px; font-size:.7rem;
       font-weight:700; margin-right:.25rem; }
.pk { background:#fdf1dc; color:var(--pk); }
.fk { background:#e4eefb; color:var(--fk); }
.uq { background:#e4f4e8; color:#1c6b34; }
.null { color:#8a5a09; font-weight:600; }
.yes { color:#1c6b34; }
.foot { margin-top:2.5rem; color:var(--muted); font-size:.8rem; border-top:1px solid var(--border); padding-top:.8rem; }
@media print { body { background:#fff; } .card { box-shadow:none; } }
"""


def col_type(col) -> str:
    return str(col.type).replace("VARCHAR", "VARCHAR").replace("DATETIME", "DATETIME")


def keys_for(col) -> str:
    labels = []
    if col.primary_key:
        labels.append('<span class="tag pk">PK</span>')
    for fk in col.foreign_keys:
        labels.append(f'<span class="tag fk">FK</span>')
    if col.unique:
        labels.append('<span class="tag uq">UQ</span>')
    return "".join(labels) or '<span class="muted">—</span>'


def fk_targets(col) -> str:
    parts = [f"{fk.column.table.name}.{fk.column.name}" for fk in col.foreign_keys]
    return ", ".join(f"<code>{escape(p)}</code>" for p in parts) or '<span class="muted">—</span>'


def build() -> str:
    counts = {}
    if DB.exists():
        con = sqlite3.connect(DB)
        for (name,) in con.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
        ):
            counts[name] = con.execute(f'select count(*) from "{name}"').fetchone()[0]
        con.close()

    tables = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
    relations = []
    for table in tables:
        for col in table.columns:
            for fk in col.foreign_keys:
                relations.append((table.name, col.name, fk.column.table.name, fk.column.name,
                                  fk.ondelete or "NO ACTION"))

    rows = []
    for table in tables:
        purpose = PURPOSE.get(table.name, "")
        rows.append(f"""
        <tr>
          <td><code>{escape(table.name)}</code></td>
          <td>{escape(purpose)}</td>
          <td class="small">{len(table.columns)}</td>
          <td class="small">{counts.get(table.name, "—")}</td>
        </tr>""")

    sections = []
    for table in tables:
        col_rows = []
        for col in table.columns:
            note = COLUMN_NOTES.get(col.name, "")
            nullable = "NULL" if col.nullable else "NOT NULL"
            null_mark = '<span class="null">NULL</span>' if col.nullable else "NOT NULL"
            col_rows.append(f"""
              <tr>
                <td><code>{escape(col.name)}</code></td>
                <td class="small">{escape(col_type(col))}</td>
                <td class="small">{null_mark}</td>
                <td>{keys_for(col)}</td>
                <td class="small">{fk_targets(col)}</td>
                <td class="small">{escape(note)}</td>
              </tr>""")

        constraints = []
        for constraint in table.constraints:
            kind = type(constraint).__name__
            if kind == "UniqueConstraint":
                cols = ", ".join(c.name for c in constraint.columns)
                constraints.append(f"UNIQUE ({escape(cols)})")
            elif kind == "PrimaryKeyConstraint":
                continue
        unique_note = UNIQUE_NOTES.get(table.name)
        if unique_note and not constraints:
            constraints.append(f"UNIQUE {escape(unique_note)}")

        constraint_html = (
            "<p class='small muted'>Batasan: " + " · ".join(constraints) + "</p>"
            if constraints
            else ""
        )
        sections.append(f"""
        <section class="card">
          <h3><code>{escape(table.name)}</code></h3>
          <p class="small muted">{escape(PURPOSE.get(table.name, ""))}</p>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Kolom</th><th>Tipe</th><th>Null</th><th>Key</th><th>Referensi</th><th>Keterangan</th></tr>
              </thead>
              <tbody>{''.join(col_rows)}</tbody>
            </table>
          </div>
          {constraint_html}
        </section>""")

    relation_rows = "".join(
        f"""
        <tr>
          <td><code>{escape(t)}.{escape(c)}</code></td>
          <td><code>{escape(rt)}.{escape(rc)}</code></td>
          <td class="small">{escape(od)}</td>
        </tr>"""
        for t, c, rt, rc, od in sorted(relations)
    )

    generated = datetime.now().strftime("%d %B %Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Database Design — BeasiswaMatch</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>Database Design — BeasiswaMatch</h1>
  <p class="muted small">SQLite · SQLAlchemy 2.x · UUID string · dibuat {generated}</p>

  <div class="banner">
    DATA DEMO SINTETIS — skema ini untuk prototipe. Kolom jumlah baris adalah snapshot database lokal saat dokumen dibuat.
  </div>

  <h2>Ringkasan tabel</h2>
  <div class="table-wrap card">
    <table>
      <thead><tr><th>Tabel</th><th>Fungsi</th><th>Kolom</th><th>Baris</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>

  <h2>Detail kolom</h2>
  {''.join(sections)}

  <h2>Relasi antar tabel</h2>
  <div class="table-wrap card">
    <table>
      <thead><tr><th>Dari</th><th>Ke</th><th>On delete</th></tr></thead>
      <tbody>{relation_rows}</tbody>
    </table>
  </div>

  <h2>Catatan desain</h2>
  <div class="card">
    <ul class="small">
      <li>Identifier memakai UUID string (36) agar mudah dipindah ke PostgreSQL; tidak ada auto-increment.</li>
      <li>Satu <code>tags</code> dipakai bersama pengguna dan beasiswa; konteks disimpan di tabel relasi
          (<code>user_tags.context</code>, <code>scholarship_tags.context</code>), bukan tabel tag terpisah.</li>
      <li>Nilai enum disimpan sebagai string (mis. <code>verification_status</code>) agar mudah dibaca; validasi dilakukan di service, bukan CHECK constraint.</li>
      <li>Kolom JSON (<code>*_json</code>, <code>value_json</code>, <code>evidence</code>) menyimpan struktur fleksibel; tipe/rentang tetap divalidasi Pydantic sebelum disimpan.</li>
      <li>Skema dibuat lewat <code>Base.metadata.create_all</code> saat startup/seed (tanpa migrasi Alembic); perubahan kolom memerlukan reset database demo.</li>
      <li>Status pendaftaran (<code>open/upcoming/closed/unknown</code>) tidak disimpan — dihitung dari <code>application_start</code>/<code>application_deadline</code>.</li>
      <li><code>user_tags</code> dan <code>scholarship_tags</code> memakai unique gabungan agar satu tag tidak dobel pada konteks yang sama.</li>
      <li>Sesi login menyimpan hash token, bukan token asli; reset kata sandi mencabut semua sesi pengguna.</li>
    </ul>
  </div>

  <p class="foot">
    Dibuat otomatis dari metadata SQLAlchemy (<code>backend/app/models/entities.py</code>) dan snapshot
    <code>backend/app.db</code>. Regenerasi dengan <code>python docs/generate_db_design.py</code>.
  </p>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"written {OUT} ({len(html)} chars, {html.count('<table')} tables, {len(Base.metadata.tables)} model tables)")
