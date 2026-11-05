"""Generate docs/services.html from the backend service modules (AST + curated notes)."""
from __future__ import annotations

import ast
import os
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "backend" / "app" / "services"
OUT = Path(__file__).resolve().parent / "services.html"

LAYERS = {
    "ai": ("AI", "ai"),
    "auth": ("Auth", "auth"),
    "profile": ("Profil", "profile"),
    "catalog": ("Katalog", "catalog"),
    "admin": ("Admin", "admin"),
    "core": ("Inti", "core"),
}

META = {
    "errors.py": {
        "title": "Errors",
        "layer": "core",
        "purpose": "Satu tipe error domain yang diterjemahkan menjadi respons JSON konsisten "
                   "(detail + code) tanpa membocorkan stack trace.",
        "callers": ["Semua route melalui exception handler di app/main.py"],
        "notes": [
            "status_code menentukan HTTP status (400/401/403/404/409/413/422/503).",
            "code dipakai frontend untuk membedakan kasus, mis. already_submitted vs session_expired.",
            "Pesan ditulis dalam bahasa pengguna; detail teknis tetap di log server.",
        ],
    },
    "auth_service.py": {
        "title": "Auth service",
        "layer": "auth",
        "purpose": "Hash kata sandi (PBKDF2-SHA256), menerbitkan sesi opaque, memvalidasi, dan mencabut sesi.",
        "callers": ["api/routes/auth.py", "api/deps.py", "user_service", "seed.py"],
        "notes": [
            "DB hanya menyimpan SHA-256 token; token asli hanya ada di klien.",
            "Masa berlaku dari SESSION_TTL_MINUTES (default 480 menit).",
            "Waktu dari SQLite dinormalisasi ke UTC sebelum dibandingkan (_aware).",
            "Perbandingan hash memakai hmac.compare_digest (anti timing).",
        ],
    },
    "user_service.py": {
        "title": "User service",
        "layer": "admin",
        "purpose": "Admin membuat akun demo (pengguna/admin) dan mereset kata sandi.",
        "callers": ["api/routes/admin.py"],
        "notes": [
            "Username unik, disimpan lowercase, minimal 3 karakter.",
            "Kata sandi minimal 8 karakter; hash PBKDF2.",
            "Akun student baru otomatis mendapat StudentProfile berstatus draft.",
            "Reset kata sandi mencabut seluruh sesi akun tersebut.",
        ],
    },
    "tagging_service.py": {
        "title": "Tagging service",
        "layer": "core",
        "purpose": "Pintu masuk Master Tag: daftar tag aktif untuk AI, peta alias, hierarki, dan penurunan tag dari fakta.",
        "callers": ["profile_service", "extraction_service", "verification_service", "recommendation_service (graph)"],
        "notes": [
            "Satu tabel tags dipakai bersama pengguna dan beasiswa.",
            "allowed_tags hanya mengirim slug/nama/kategori — tidak ada data sensitif ke model.",
            "tags_from_facts deterministik: jenjang, jurusan, domisili, TOEFL → tag sistem.",
            "TagGraph dipakai untuk mencocokkan leluhur/turunan dan mencegah hitung ganda.",
        ],
    },
    "matching_service.py": {
        "title": "Matching service",
        "layer": "catalog",
        "purpose": "Menghitung skor relevansi tag antara pengguna dan beasiswa. Fungsi murni: tanpa DB, tanpa AI.",
        "callers": ["recommendation_service.build_entry"],
        "notes": [
            "Hanya konteks kompatibel yang masuk pembagi (matriks di COMPATIBLE_CONTEXTS).",
            "Cocok bila tag_id sama atau relasi leluhur/turunan.",
            "Anak yang sudah terwakili leluhurnya tidak dihitung dua kali (dicatat counted=false).",
            "Tanpa tag pembanding → skor null + insufficient_preferences, bukan 0%.",
        ],
    },
    "eligibility_service.py": {
        "title": "Eligibility service",
        "layer": "catalog",
        "purpose": "Mengevaluasi persyaratan terstruktur (operator, grup AND/OR) dan menyimpulkan status kelayakan + gap analysis.",
        "callers": ["recommendation_service.build_entry"],
        "notes": [
            "Status per persyaratan: met / not_met / unknown.",
            "Grup AND: semua harus met; grup OR: satu cukup.",
            "Persyaratan opsional tidak pernah menggugurkan kelayakan.",
            "Persyaratan berbasis tag tidak disimpulkan not_met hanya karena tag tidak ada.",
            "Keputusan akhir: eligible / potentially_eligible / not_eligible.",
        ],
    },
    "profile_service.py": {
        "title": "Profile service",
        "layer": "profile",
        "purpose": "Siklus hidup profil: analisis deskripsi bebas, konfirmasi sekali, koreksi fakta, dan payload profil.",
        "callers": ["api/routes/profile.py"],
        "notes": [
            "Sekali kirim: profile_submitted_at mengunci analyze & confirm (409).",
            "Deskripsi terkunci setelah kirim; fakta masih bisa diperbaiki (recompute tanpa AI).",
            "Confirm tanpa daftar tag → saran AI diterima otomatis oleh sistem.",
            "Tag turunan fakta ditambahkan dengan source system; penolakan lama tidak dibangkitkan.",
            "Hanya analysis_id terbaru yang boleh dikonfirmasi, dan hanya sekali.",
        ],
    },
    "recommendation_service.py": {
        "title": "Recommendation service",
        "layer": "catalog",
        "purpose": "Merakit hasil akhir: gabungkan matching + eligibility, urutkan, hitung hot/recent, dan tulis penjelasan.",
        "callers": ["api/routes/scholarships.py"],
        "notes": [
            "Hanya user_tags confirmed dan scholarship_tags approved pada beasiswa verified.",
            "Urutan: eligible → potentially_eligible → not_eligible, lalu skor menurun.",
            "Hot: open/upcoming dulu, lalu bookmark, deadline terdekat, skor.",
            "Recent: created_at terbaru, maksimal 3, boleh tumpang tindih dengan hot.",
            "application_status dihitung dari tanggal, bukan disimpan.",
        ],
    },
    "extraction_service.py": {
        "title": "Extraction service",
        "layer": "admin",
        "purpose": "Mengubah sumber beasiswa (URL/teks/PDF) menjadi draft katalog, plus input manual admin.",
        "callers": ["api/routes/admin.py"],
        "notes": [
            "URL di-fetch lalu tag HTML dibersihkan; PDF hanya teks (tanpa OCR).",
            "Batas panjang input AI_MAX_INPUT_CHARS dan ukuran PDF MAX_PDF_BYTES.",
            "Setiap hasil membuat extraction_job (status, provider_mode, fallback_reason).",
            "Input manual memakai tabel dan alur review yang sama, source_type=manual.",
            "Gagal AI → job failed + ServiceError 503, tidak ada draft setengah jadi.",
        ],
    },
    "verification_service.py": {
        "title": "Verification service",
        "layer": "admin",
        "purpose": "Review dan keputusan katalog berbasis beasiswa: edit, setujui, tolak, riwayat, statistik.",
        "callers": ["api/routes/admin.py"],
        "notes": [
            "Approve butuh nama dan minimal satu sumber tercatat.",
            "Semua tag non-rejected menjadi approved saat approve.",
            "Reject wajib alasan dan mencatat ScholarshipVerification.",
            "Bekerja tanpa extraction job (record seed/import manual tetap bisa dikelola).",
            "Endpoint ekstraksi hanya membungkus fungsi yang sama (job_payload).",
        ],
    },
    "submission_service.py": {
        "title": "Submission service",
        "layer": "admin",
        "purpose": "Antrean screenshot beasiswa dari pengguna dan pemrosesan oleh admin.",
        "callers": ["api/routes/submissions.py", "api/routes/admin.py"],
        "notes": [
            "Hanya PNG/JPEG/WEBP, maksimal 5 MB; gambar disimpan sebagai BLOB.",
            "Status: pending → processed / rejected (sekali proses).",
            "Gambar hanya dapat diambil admin (endpoint ber-Bearer).",
            "Tanpa OCR: admin membaca gambar lalu menambah beasiswa manual.",
        ],
    },
    "ai/interfaces.py": {
        "title": "AI interfaces",
        "layer": "ai",
        "purpose": "Kontrak vendor-neutral untuk provider AI dan tipe error-nya.",
        "callers": ["factory", "providers/mock", "providers/openai_compatible"],
        "notes": [
            "Empat operasi: extract_user_profile, classify_tags, extract_scholarship, explain_recommendation.",
            "AIProviderError.reason berisi kode singkat: timeout / provider_error / invalid_output.",
        ],
    },
    "ai/factory.py": {
        "title": "AI factory",
        "layer": "ai",
        "purpose": "Memilih provider sesuai konfigurasi, memvalidasi output Pydantic + whitelist slug, dan menjalankan fallback transparan.",
        "callers": ["api/routes/*", "profile_service", "extraction_service"],
        "notes": [
            "Mode: auto / llm / mock; fallback mengikuti AI_FALLBACK_ENABLED.",
            "Slug di luar Master Tag atau context salah dianggap invalid_output → fallback.",
            "Setiap hasil membawa provider_mode, provider_name, model, fallback_reason.",
            "get_ai_service() cached; tidak pernah mengekspos API key.",
        ],
    },
    "ai/providers/mock.py": {
        "title": "Mock provider",
        "layer": "ai",
        "purpose": "Provider deterministik berbasis regex/kata kunci untuk demo offline dan fallback.",
        "callers": ["factory"],
        "notes": [
            "Tidak pernah melakukan request jaringan.",
            "Semua slug dibatasi allowed_tags; tidak mengarang tag baru.",
            "Meniru ekstraksi fakta + tag profil, ekstraksi beasiswa, dan penjelasan.",
            "Dipakai juga oleh seed untuk sanity check deskripsi demo.",
        ],
    },
    "ai/providers/openai_compatible.py": {
        "title": "OpenAI-compatible provider",
        "layer": "ai",
        "purpose": "Adapter HTTP generik ke endpoint /chat/completions (dipakai untuk DeepSeek).",
        "callers": ["factory (mode llm)"],
        "notes": [
            "httpx.AsyncClient async; timeout dan retry terbatas dari env.",
            "Prompt diambil dari services/ai/prompts/*.txt.",
            "Respons dibersihkan dari code fence lalu di-parse JSON.",
            "Authorization header tidak pernah dilog atau dikembalikan.",
        ],
    },
}

FUNC_NOTES = {
    "errors.py:ServiceError": "Error domain dengan pesan manusiawi, status HTTP, dan kode mesin.",
    "auth_service.py:hash_password": "PBKDF2-SHA256 dengan salt acak; format pbkdf2_sha256$iter$salt$hash.",
    "auth_service.py:verify_password": "Bandingkan hash secara konstan-waktu.",
    "auth_service.py:authenticate": "Cek username+password; selalu jalankan hash untuk mengurangi timing oracle.",
    "auth_service.py:create_session": "Terbitkan token acak, simpan hash + expires_at.",
    "auth_service.py:resolve_session": "Validasi token: ada, tidak revoked, belum kedaluwarsa; update last_seen_at.",
    "auth_service.py:revoke_session": "Tandai revoked_at (logout / reset password).",
    "auth_service.py:session_payload": "Bentuk respons sesi untuk API (tanpa token/hash).",
    "user_service.py:list_users": "Daftar akun + status profil untuk halaman admin.",
    "user_service.py:create_user": "Buat akun baru; student otomatis dapat profil draft.",
    "user_service.py:reset_password": "Set password baru (atau generate), cabut semua sesi.",
    "tagging_service.py:build_graph": "Bangun TagGraph dari tabel tags.",
    "tagging_service.py:allowed_tags": "Daftar tag aktif (slug/nama/kategori) untuk prompt AI.",
    "tagging_service.py:alias_map": "Peta alias → slug resmi.",
    "tagging_service.py:tags_from_facts": "Turunkan tag sistem dari fakta terkonfirmasi (tanpa AI).",
    "tagging_service.py:find_tag": "Cari tag berdasarkan slug.",
    "matching_service.py:contexts_compatible": "Cek pasangan konteks pengguna–beasiswa diizinkan.",
    "matching_service.py:eligible_user_tags": "Filter tag pengguna yang konteksnya komparabel.",
    "matching_service.py:match_tags": "Hitung pasangan cocok, anti dobel, dan skor relevansi.",
    "eligibility_service.py:evaluate_requirement": "Evaluasi satu persyaratan → met/not_met/unknown.",
    "eligibility_service.py:evaluate": "Evaluasi semua grup + status keseluruhan + ringkasan gap.",
    "profile_service.py:profile_payload": "Bentuk profil untuk API (fakta, status, penanda kirim).",
    "profile_service.py:analyze_profile": "Panggil AI, validasi, simpan analisis sementara (belum fakta aktif).",
    "profile_service.py:confirm_profile": "Kunci sekali kirim: simpan fakta, konfirmasi tag, set submitted_at.",
    "profile_service.py:update_profile": "Update deskripsi (sebelum kirim) atau fakta (kapan saja, tanpa AI).",
    "profile_service.py:decide_single_tag": "Konfirmasi/tolak satu tag pengguna (endpoint lama).",
    "recommendation_service.py:compute": "Hasil + hot + recent + counts untuk satu pengguna.",
    "recommendation_service.py:build_entry": "Satu entri beasiswa: skor, eligibility, requirements, penjelasan.",
    "recommendation_service.py:scholarship_tags": "Ambil tag beasiswa yang approved untuk matching.",
    "recommendation_service.py:requirement_groups": "Ambil grup + persyaratan siap dievaluasi.",
    "recommendation_service.py:confirmed_user_tag_rows": "Ambil tag pengguna confirmed + bobotnya.",
    "extraction_service.py:fetch_url_text": "Ambil halaman URL dan bersihkan HTML.",
    "extraction_service.py:extract_pdf_text": "Ambil teks PDF; tolak bila kosong (hasil scan).",
    "extraction_service.py:create_extraction": "Pipeline: sumber → AI → job + draft beasiswa pending.",
    "extraction_service.py:create_manual_scholarship": "Input manual admin dengan tabel/alur review yang sama.",
    "extraction_service.py:job_payload": "Bentuk detail job ekstraksi untuk API admin.",
    "verification_service.py:patch_scholarship": "Edit field, keputusan tag, dan ganti persyaratan.",
    "verification_service.py:approve_scholarship": "Set verified + approve tag non-rejected + catat riwayat.",
    "verification_service.py:reject_scholarship": "Set rejected + alasan + catat riwayat.",
    "verification_service.py:scholarship_payload": "Detail admin: field, tag (semua status), requirements, sumber, riwayat.",
    "verification_service.py:list_scholarships": "Daftar katalog admin + filter status/cari.",
    "verification_service.py:admin_stats": "Angka dashboard (users, scholarships, extractions).",
    "verification_service.py:pending_scholarships": "Antrean verifikasi (draft + pending).",
    "submission_service.py:create_submission": "Validasi + simpan screenshot sebagai pending.",
    "submission_service.py:process": "Tandai processed/rejected (sekali proses).",
    "submission_service.py:list_admin": "Daftar kiriman untuk admin (default semua status).",
    "ai/factory.py:get_ai_service": "Singleton AIService sesuai konfigurasi.",
    "ai/providers/mock.py:MockAIProvider": "Implementasi deterministik dari keempat operasi AI.",
    "ai/providers/openai_compatible.py:OpenAICompatibleProvider": "Adapter chat completions dengan retry + parsing JSON.",
}

CSS = """
:root { --bg:#f5f6f8; --surface:#fff; --border:#d8dce3; --text:#1d2430; --muted:#5d6675;
        --primary:#1f5fa8; --code:#eef2f7; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); line-height:1.55;
       font-family:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:1120px; margin:0 auto; padding:2rem 1.25rem 4rem; }
h1 { font-size:1.6rem; margin:0 0 .3rem; letter-spacing:-.01em; }
h2 { font-size:1.15rem; margin:2.2rem 0 .6rem; }
h3 { font-size:1rem; margin:0 0 .2rem; }
p { margin:.3rem 0 .7rem; }
.muted { color:var(--muted); }
.small { font-size:.83rem; }
.banner { background:#fff6d6; color:#6b4b00; border:1px solid #ecd9a0; border-radius:8px;
          padding:.55rem .8rem; font-size:.84rem; margin:1rem 0 1.6rem; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px;
        padding:1rem 1.1rem; margin:1rem 0; box-shadow:0 1px 2px rgba(20,30,45,.06); }
.card-head { display:flex; flex-wrap:wrap; gap:.5rem; align-items:baseline; justify-content:space-between; }
.path { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.78rem; color:var(--muted); }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.8rem;
       background:var(--code); padding:.05rem .3rem; border-radius:4px; }
pre { background:var(--code); border-radius:8px; padding:.55rem .7rem; overflow-x:auto; font-size:.78rem; margin:.25rem 0 .6rem; }
table { width:100%; border-collapse:collapse; font-size:.84rem; }
th, td { border-bottom:1px solid var(--border); padding:.4rem .5rem; text-align:left; vertical-align:top; }
th { background:#eef2f7; font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; color:#39424f; }
tbody tr:hover { background:#fafbfd; }
.badge { display:inline-block; padding:.08rem .45rem; border-radius:999px; font-size:.7rem; font-weight:700; }
.ai { background:#e4eefb; color:#17487f; }
.auth { background:#fdf1dc; color:#8a5a09; }
.profile { background:#e9e6fb; color:#4b3a8a; }
.catalog { background:#e4f4e8; color:#1c6b34; }
.admin { background:#fbe5e5; color:#98221f; }
.core { background:#eceff4; color:#39424f; }
.toc { display:grid; gap:.25rem; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); font-size:.86rem; }
.toc a { color:var(--primary); text-decoration:none; }
.toc a:hover { text-decoration:underline; }
ul.notes { margin:.3rem 0 .8rem; padding-left:1.1rem; font-size:.86rem; }
ul.notes li { margin:.15rem 0; }
.foot { margin-top:2.5rem; color:var(--muted); font-size:.8rem; border-top:1px solid var(--border); padding-top:.8rem; }
@media print { body { background:#fff; } .card { box-shadow:none; } }
"""


def signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    a = fn.args
    defaults = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
    for arg, default in zip(a.args, defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f" = {ast.unparse(default)}"
        args.append(text)
    if a.vararg:
        args.append("*" + a.vararg.arg)
    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        text = arg.arg
        if default is not None:
            text += f" = {ast.unparse(default)}"
        args.append(text)
    ret = f" -> {ast.unparse(fn.returns)}" if fn.returns is not None else ""
    prefix = "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {fn.name}({', '.join(args)}){ret}"


def module_anchor(name: str) -> str:
    return name.replace("/", "-").replace(".py", "").replace("_", "-")


def build() -> str:
    files = []
    for root, _, names in os.walk(SERVICES):
        if "__pycache__" in root:
            continue
        for name in sorted(names):
            if name == "__init__.py" or not name.endswith(".py"):
                continue
            path = Path(root) / name
            rel = str(path.relative_to(SERVICES)).replace(os.sep, "/")
            files.append((rel, path))

    order = ["errors.py", "tagging_service.py", "matching_service.py", "eligibility_service.py",
             "profile_service.py", "recommendation_service.py", "extraction_service.py",
             "verification_service.py", "submission_service.py", "auth_service.py",
             "user_service.py", "ai/interfaces.py", "ai/factory.py",
             "ai/providers/mock.py", "ai/providers/openai_compatible.py"]
    rank = {name: i for i, name in enumerate(order)}
    files.sort(key=lambda item: rank.get(item[0], 99))

    cards, toc = [], []
    for rel, path in files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        meta = META.get(rel, {})
        layer_key = meta.get("layer", "core")
        layer_label, layer_class = LAYERS[layer_key]
        anchor = module_anchor(rel)

        functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]

        toc.append(f'<a href="#{anchor}">{escape(meta.get("title", rel))}</a>')

        fn_rows = []
        for fn in functions:
            if fn.name.startswith("_") and fn.name not in {"__init__"}:
                continue
            note = FUNC_NOTES.get(f"{rel}:{fn.name}", "")
            if not note and ast.get_docstring(fn):
                note = ast.get_docstring(fn).strip().splitlines()[0]
            fn_rows.append(
                f"<tr><td><code>{escape(fn.name)}</code></td>"
                f"<td class='small'><code>{escape(signature(fn))}</code></td>"
                f"<td class='small'>{escape(note) or '<span class=\"muted\">—</span>'}</td></tr>"
            )
        for cls in classes:
            note = FUNC_NOTES.get(f"{rel}:{cls.name}", "")
            if not note and ast.get_docstring(cls):
                note = ast.get_docstring(cls).strip().splitlines()[0]
            fn_rows.append(
                f"<tr><td><code>{escape(cls.name)}</code></td>"
                f"<td class='small'><code>class</code></td>"
                f"<td class='small'>{escape(note) or '<span class=\"muted\">—</span>'}</td></tr>"
            )

        callers = "".join(f"<li><code>{escape(c)}</code></li>" for c in meta.get("callers", []))
        notes = "".join(f"<li>{escape(n)}</li>" for n in meta.get("notes", []))

        cards.append(f"""
        <section class="card" id="{anchor}">
          <div class="card-head">
            <div>
              <h3>{escape(meta.get("title", rel))}</h3>
              <div class="path">{escape(rel)} · {len(source.splitlines())} baris</div>
            </div>
            <span class="badge {layer_class}">{layer_label}</span>
          </div>
          <p class="small">{escape(meta.get("purpose", ""))}</p>
          <p class="small muted" style="margin:0 0 .2rem"><strong>Dipanggil oleh</strong></p>
          <ul class="notes">{callers or "<li>—</li>"}</ul>
          <p class="small muted" style="margin:0 0 .2rem"><strong>Aturan / catatan</strong></p>
          <ul class="notes">{notes or "<li>—</li>"}</ul>
          <div style="overflow-x:auto">
            <table>
              <thead><tr><th>Simbol</th><th>Signature</th><th>Ringkas</th></tr></thead>
              <tbody>{''.join(fn_rows)}</tbody>
            </table>
          </div>
        </section>""")

    generated = datetime.now().strftime("%d %B %Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Service Design — BeasiswaMatch</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>Service Design — BeasiswaMatch</h1>
  <p class="muted small">Backend FastAPI · {len(files)} modul service · dibuat {generated}</p>

  <div class="banner">
    Ringkasan per modul: tanggung jawab, pemanggil, aturan penting, dan fungsi publik beserta signature aslinya
    (dibaca langsung dari kode dengan <code>ast</code>, jadi selalu sinkron).
  </div>

  <h2>Peta service</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Lapisan</th><th>Modul</th><th>Peran singkat</th></tr></thead>
      <tbody>
        <tr><td><span class="badge ai">AI</span></td><td><code>ai/factory.py</code></td><td>Pilih provider + fallback + validasi output</td></tr>
        <tr><td><span class="badge ai">AI</span></td><td><code>ai/providers/*</code></td><td>Adapter LLM (DeepSeek) dan mock deterministik</td></tr>
        <tr><td><span class="badge profile">Profil</span></td><td><code>profile_service.py</code></td><td>Analisis deskripsi, kirim sekali, koreksi fakta</td></tr>
        <tr><td><span class="badge catalog">Katalog</span></td><td><code>matching_service.py</code></td><td>Skor relevansi tag (murni)</td></tr>
        <tr><td><span class="badge catalog">Katalog</span></td><td><code>eligibility_service.py</code></td><td>Persyaratan, grup AND/OR, gap analysis</td></tr>
        <tr><td><span class="badge catalog">Katalog</span></td><td><code>recommendation_service.py</code></td><td>Rakit hasil, urutkan, hot/recent</td></tr>
        <tr><td><span class="badge admin">Admin</span></td><td><code>extraction_service.py</code></td><td>Sumber → AI → draft; input manual</td></tr>
        <tr><td><span class="badge admin">Admin</span></td><td><code>verification_service.py</code></td><td>Edit, approve, reject, stats</td></tr>
        <tr><td><span class="badge admin">Admin</span></td><td><code>submission_service.py</code></td><td>Antrean screenshot pengguna</td></tr>
        <tr><td><span class="badge auth">Auth</span></td><td><code>auth_service.py</code></td><td>Hash password, sesi, revoke</td></tr>
        <tr><td><span class="badge admin">Admin</span></td><td><code>user_service.py</code></td><td>Tambah pengguna, reset password</td></tr>
        <tr><td><span class="badge core">Inti</span></td><td><code>tagging_service.py</code></td><td>Master Tag, alias, hierarki, tag dari fakta</td></tr>
        <tr><td><span class="badge core">Inti</span></td><td><code>errors.py</code></td><td>Error domain → respons JSON</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Daftar modul</h2>
  <div class="toc">{''.join(toc)}</div>

  <h2>Detail per modul</h2>
  {''.join(cards)}

  <p class="foot">
    Regenerasi: <code>python docs/generate_services_doc.py</code>. Signature dan daftar fungsi dibaca dari
    AST; ringkasan dan aturan berasal dari metadata di skrip generator.
  </p>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"written {OUT} ({len(html)} chars, {html.count('<section class=\"card\"')} service cards)")
