# update_agent.md — Kondisi Proyek Saat Ini

Dokumen ini menggambarkan prototipe **BeasiswaMatch** sebagaimana kondisinya sekarang:
apa yang sudah dibangun, aturan yang berlaku, dan bagian mana yang berbeda dari `AGENT.md`
(spesifikasi awal). `AGENT.md` tetap menjadi kontrak produk; dokumen ini adalah pembaruan
implementasi + deviasi yang disepakati selama pengerjaan.

Status: prototipe berjalan lokal dengan dua server (backend FastAPI + frontend statis),
database SQLite ter-seed, 110 test lulus.

---

## 1. Ringkasan produk

Pengguna menulis deskripsi diri dalam bahasa bebas → AI mengekstrak fakta + menyarankan tag →
pengguna memeriksa fakta dan mengirim profil **satu kali** → sistem mencocokkan tag dan
mengevaluasi persyaratan secara deterministik → rekomendasi beasiswa dengan skor relevansi dan
analisis celah persyaratan. Admin mengelola katalog (ekstraksi AI, input manual, verifikasi)
dan menerima kiriman screenshot dari pengguna.

---

## 2. Perubahan dari AGENT.md

| Area | AGENT.md | Implementasi sekarang |
|---|---|---|
| Login | Di luar cakupan (tanpa SSO) | **Login demo** dengan password hash PBKDF2 + sesi server (opaque token), bukan produksi |
| Pengalih mode | Tab Pengguna/Admin di UI | Dihapus; peran ditentukan akun saat login, tiap halaman punya guard sendiri |
| Pengiriman tag | Pengguna meninjau/menolak tag | **Satu kali kirim**; tag disembunyikan dari pengguna, saran AI diterima sistem |
| Tag di UI pengguna | Ditampilkan | Tidak ditampilkan sama sekali (hanya dipakai perhitungan dan terlihat di admin) |
| Halaman | Satu SPA dengan mode | Halaman terpisah: profil, profil terkirim, rekomendasi, kirim screenshot, 4 halaman admin |
| Admin | Satu halaman | Dashboard, Pengguna, Tambah Beasiswa, Kelola Beasiswa |
| Input beasiswa | Ekstraksi teks/URL/PDF | + **input manual** oleh admin (tag & persyaratan) |
| Kiriman pengguna | — | **Screenshot** dari pengguna masuk antrean admin (tanpa OCR) |
| Beranda | Hanya rekomendasi | + section **Lagi hot** (atas) dan **Baru ditambahkan** (bawah) |
| Verifikasi | Berbasis ekstraksi | Berbasis beasiswa (`/api/admin/scholarships/{id}/approve|reject`); record tanpa job tetap bisa dikelola |

Yang **tidak berubah**: satu tabel Master Tag untuk pengguna dan beasiswa, matching/eligibility
deterministik, hanya beasiswa `verified` yang masuk rekomendasi utama, skor relevansi bukan
probabilitas diterima, tidak ada modul kompetisi, tidak ada OCR.

---

## 3. Arsitektur runtime

```
Frontend statis  http://127.0.0.1:5500   (python -m http.server)
Backend FastAPI  http://127.0.0.1:8000   (uvicorn, prefix /api, docs /docs)
Database         backend/app.db          (SQLite, SQLAlchemy 2.x)
AI               DeepSeek (OpenAI-compatible) atau MockAIProvider
```

- Frontend **vanilla JS**, tanpa bundler; satu pintu jaringan `js/api.js` (`API_BASE_URL`).
- Token disimpan di `sessionStorage`, dikirim sebagai `Authorization: Bearer <token>`.
- CORS dibatasi ke origin `http://127.0.0.1:5500` dan `http://localhost:5500`.

---

## 4. Struktur folder

```
backend/app/
  main.py                    # FastAPI, CORS, error handler, lifespan
  core/config.py             # .env -> Settings (AI, DB, sesi, limit)
  core/database.py           # engine, SessionLocal, Base, get_db
  models/entities.py         # seluruh tabel SQLAlchemy
  schemas/ai.py              # Pydantic: output AI + request/response admin
  api/deps.py                # get_current_user, require_admin, require_self(_or_admin)
  api/routes/
    auth.py health.py profile.py scholarships.py submissions.py admin.py
  services/
    ai/ (interfaces, factory, providers/mock.py, providers/openai_compatible.py, prompts/)
    auth_service.py          # hash password, sesi, resolve/revoke
    user_service.py          # daftar/tambah pengguna, reset password
    tagging_service.py       # Master Tag, alias, hierarki, tag dari fakta
    matching_service.py      # skor relevansi deterministik
    eligibility_service.py   # operator, grup AND/OR, gap analysis
    recommendation_service.py# rakit hasil + hot/recent + penjelasan
    profile_service.py       # analyze/confirm/update + aturan satu kali
    extraction_service.py    # URL/teks/PDF + input manual admin
    verification_service.py  # patch/approve/reject, payload admin, stats
    submission_service.py    # screenshot pengguna + pemrosesan admin
  seed.py                    # seed idempoten
backend/tests/               # 110 test
frontend/
  index.html login.html profile.html my-profile.html app.html submit-scholarship.html
  admin.html admin-users.html admin-new-scholarship.html admin-scholarships.html
  css/styles.css  js/{api,auth,shell,components,state,landing,login,profile,home,my-profile,submit-scholarship,admin-dashboard,admin-users,admin-new,admin-manual,admin-scholarships}.js
```

---

## 5. Autentikasi dan sesi

- `POST /api/auth/login` → token opaque (`secrets.token_urlsafe`), DB hanya menyimpan SHA-256
  di `auth_sessions`, TTL `SESSION_TTL_MINUTES` (default 480).
- `GET /api/auth/session` → validasi + `last_seen_at`; `POST /api/auth/logout` → revoke.
- Password: PBKDF2-SHA256 200k iterasi; tidak pernah dikembalikan API.
- Akun demo: `demo-student / student123`, `demo-admin / admin123`.
- Otorisasi:
  - profil tulis = pemilik; profil baca + rekomendasi = pemilik atau admin;
  - `/api/admin/*` = admin;
  - katalog, tag, demo/session = semua yang login;
  - `GET /api/health` = publik.
- Admin dapat menambah pengguna dan mereset password (semua sesi akun dicabut).

---

## 6. Alur pengguna

1. `index.html` (landing) → `login.html?role=user|admin` → redirect sesuai peran.
2. Pengguna baru → `profile.html`:
   - tulis deskripsi → **Analisis Profil dengan AI** (LLM/mock);
   - tinjau **fakta** (tanpa tag), koreksi nilai, lalu **Kirim Profil** (sekali).
3. Kirim → `profile_submitted_at` diisi → redirect `app.html`.
4. `app.html`:
   - **Lagi hot** (paling atas), CTA kirim screenshot, rekomendasi, **Baru ditambahkan** (paling bawah);
   - kartu menampilkan status verifikasi, status pendaftaran, skor relevansi, status kelayakan,
     daftar persyaratan `Terpenuhi / Belum terpenuhi / Belum diketahui`.
5. `my-profile.html`: fakta terkirim + deskripsi asli + editor fakta (tanpa AI).
6. `submit-scholarship.html`: unggah screenshot (PNG/JPEG/WEBP ≤ 5 MB) + catatan → antrean admin.

### Aturan satu kali kirim

| Aksi | Sebelum kirim | Setelah kirim |
|---|---|---|
| `POST /profile/{u}/analyze` | 200 | **409 `already_submitted`** |
| `POST /profile/{u}/confirm` | 200 (set `profile_submitted_at`) | **409 `already_submitted`** |
| `PUT /profile/{u}` dengan `description` berubah | 200 (status → draft) | **409 `description_locked`** |
| `PUT /profile/{u}` fakta saja | 200 | 200 (recompute deterministik) |

Bila `confirm` dikirim tanpa daftar tag (UI sekarang begitu), backend otomatis mengonfirmasi
saran AI terbaru (menghormati penolakan yang tercatat) agar matching tetap berjalan.

---

## 7. Model data

| Tabel | Isi penting |
|---|---|
| `users` | username, display_name, role, password_hash |
| `auth_sessions` | token_hash, role, expires_at, revoked_at |
| `student_profiles` | description, extracted_facts_json, latest/confirmed_analysis_id, fakta terstruktur, `profile_submitted_at` |
| `tag_categories`, `tags`, `tag_aliases` | Master Tag tunggal (14 kategori, 71 tag seed, hierarki, alias) |
| `user_tags` | tag pengguna + context, source, confidence, status, weight, evidence |
| `scholarships` | data beasiswa, `verification_status`, `application_status` dihitung dari tanggal |
| `scholarship_tags` | tag beasiswa + context, review_status, weight, evidence |
| `scholarship_sources` | URL/teks/manual + job terkait |
| `scholarship_requirement_groups` / `_requirements` | grup AND/OR + operator terstruktur |
| `extraction_jobs` | sumber, status, hasil JSON, provider_mode/fallback |
| `scholarship_verifications` | riwayat keputusan admin |
| `user_scholarship_bookmarks` | ada, belum dipakai UI (dasar sinyal "hot") |
| `user_scholarship_submissions` | screenshot pengguna + status antrean |

---

## 8. Aturan domain

- **Tag** hanya dinilai bila konteks kompatibel (`profile↔target_audience/eligibility`,
  `interest↔field`, `achievement↔achievement`, `preference↔benefit/program/obligation`,
  `location↔location`, `language↔eligibility`, `economic↔eligibility/target_audience`).
- **Skor relevansi** = bobot tag pengguna yang cocok / total bobot tag komparabel × 100;
  tag anak tidak dihitung dua kali; `null` + `insufficient_preferences` bila tak ada pembanding.
- **Eligibility**: `eligible` (semua wajib met), `potentially_eligible` (ada unknown, tanpa not_met),
  `not_eligible` (ada not_met). Persyaratan opsional tidak menggugurkan.
- **Hot**: beasiswa verified, prioritas status open/upcoming → jumlah bookmark → deadline terdekat
  → skor relevansi. **Baru ditambahkan**: `created_at` terbaru (maks 3, boleh tumpang tindih).
- **Verifikasi**: approve butuh nama + sumber; semua tag non-rejected jadi approved; keputusan
  tercatat di `scholarship_verifications`. Status: `draft → pending_verification → verified/rejected`.
- **Screenshot**: tanpa OCR; admin membaca gambar lalu menambah beasiswa manual, kemudian menandai
  kiriman `processed`/`rejected`.

---

## 9. Lapisan AI

- Kontrak `AIProvider`: `extract_user_profile`, `classify_tags`, `extract_scholarship`,
  `explain_recommendation`.
- Provider: `openai_compatible` (dipakai untuk DeepSeek) dan `mock` (deterministik, tanpa jaringan).
- Mode: `auto` (LLM bila konfigurasi lengkap), `llm`, `mock`. Fallback otomatis bila timeout,
  HTTP error, JSON invalid, atau slug di luar Master Tag.
- Setiap hasil membawa `provider_mode` (`llm`/`mock`/`mock_fallback`), `provider_name`, `model`,
  `fallback_reason`. UI menampilkan `LLM aktif` / `Simulasi AI` / `LLM gagal — menggunakan simulasi`.
- Validasi wajib: Pydantic + whitelist slug + confidence 0..1 + context sesuai peran.
- Konfigurasi aktif di `backend/.env`: `AI_API_BASE_URL=https://api.deepseek.com/v1`,
  `AI_MODEL=deepseek-chat`, `AI_TIMEOUT_SECONDS=60`, `AI_FALLBACK_ENABLED=true`,
  `AI_MAX_INPUT_CHARS=30000`.

---

## 10. Ringkasan API

**Publik** `GET /api/health`

**Auth** `POST /api/auth/login`, `GET /api/auth/session`, `POST /api/auth/logout`

**Pengguna** `GET /api/demo/session`, `GET /api/tags`, `GET /api/scholarships`,
`GET /api/scholarships/{id}`, `GET /api/profile/{u}`, `POST /api/profile/{u}/analyze`,
`POST /api/profile/{u}/confirm`, `PUT /api/profile/{u}`, `GET /api/profile/{u}/tags`,
`POST /api/profile/{u}/tags/{tag_id}/confirm|reject`,
`GET /api/recommendations/{u}`, `POST /api/recommendations/recompute`,
`POST /api/submissions`, `GET /api/submissions/me`

**Admin** `GET /api/admin/stats`, `GET|POST /api/admin/users`,
`POST /api/admin/users/{id}/reset-password`, `GET|POST /api/admin/extractions`,
`GET|PATCH /api/admin/extractions/{id}`, `POST /api/admin/extractions/{id}/approve|reject`,
`GET|POST /api/admin/scholarships`, `GET|PATCH /api/admin/scholarships/{id}`,
`POST /api/admin/scholarships/{id}/approve|reject`, `GET /api/admin/scholarships/pending`,
`GET /api/admin/submissions`, `GET /api/admin/submissions/{id}/image`,
`POST /api/admin/submissions/{id}/process`

---

## 11. Menjalankan

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
env -u PYTHONPATH .venv/bin/python -m pip install -r requirements.txt
cp .env.example .env        # isi AI_API_KEY untuk DeepSeek
env -u PYTHONPATH .venv/bin/python -m app.seed
env -u PYTHONPATH .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend
cd frontend && python -m http.server 5500 --bind 127.0.0.1
```

Catatan: `env -u PYTHONPATH` penting bila shell mengekspor PYTHONPATH ke venv lain.

---

## 12. Pengujian

`backend/tests` — 110 test: profil & satu kali kirim, matching, eligibility, provider/fallback,
admin (ekstraksi, verifikasi, dashboard, pengguna), manual entry, highlight & submission,
struktur frontend. Jalankan:

```bash
cd backend && env -u PYTHONPATH .venv/bin/python -m pytest -q
```

---

## 13. Batasan dan asumsi

- Autentikasi demo, bukan produksi: tanpa SSO/OAuth, tanpa lupa password, token di `sessionStorage`.
- Tidak ada OCR: PDF scan ditolak, screenshot hanya dibaca manual oleh admin.
- Bookmark belum punya UI, sehingga komponen "hot" berbasis bookmark selalu 0.
- Tanpa pagination/rate limiting; cocok untuk demo satu mesin.
- Belum ada hapus/ubah peran pengguna (hanya tambah + reset password).
- `explanation` rekomendasi dibangun deterministik di backend (operasi AI explanation tersedia
  tetapi tidak dipakai UI).
- API pengguna masih mengembalikan `suggested_tags` pada respons analisis (dipakai sistem/uji),
  meskipun UI tidak menampilkannya.
