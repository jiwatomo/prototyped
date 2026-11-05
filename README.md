# Prototipe Platform Rekomendasi Beasiswa

Prototipe demo untuk membantu siswa/mahasiswa menemukan beasiswa berdasarkan deskripsi diri
berbahasa alami. Semua data beasiswa adalah **DATA DEMO SINTETIS — BUKAN INFORMASI BEASISWA NYATA**.

Dokumentasi: `update_agent.md` (kondisi proyek), `flow.md` + `docs/flows/*.mmd` (diagram backend),
`docs/db-design.html` (desain database, buka langsung di browser).

## Struktur

```
backend/
  app/
    main.py                 # FastAPI, CORS, error handler
    core/                   # config (.env) + database (SQLite)
    models/                 # SQLAlchemy 2.x, UUID string, Master Tag tunggal
    schemas/                # Pydantic request + output AI
    api/routes/             # health, profile, scholarships, admin
    services/
      tagging_service.py    # Master Tag, alias, hierarki
      matching_service.py   # skor relevansi deterministik
      eligibility_service.py# requirement + gap analysis
      extraction_service.py # URL/teks/PDF -> AI -> draft beasiswa
      verification_service.py
      profile_service.py    # analyze / confirm / update
      recommendation_service.py
      ai/                   # interfaces, factory, prompts, providers (mock, openai_compatible)
    seed.py                 # seed idempoten
  tests/                    # 45 unit/integration tests
frontend/                   # HTML + CSS + vanilla JS (tanpa build)
```

## Menjalankan

Backend (terminal 1):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
python -m http.server 5500
```

- Landing page: http://127.0.0.1:5500/
- Login: http://127.0.0.1:5500/login.html?role=user (atau `?role=admin`)
- Input profil (pengguna): http://127.0.0.1:5500/profile.html
- Profil terkirim (pengguna): http://127.0.0.1:5500/my-profile.html
- Rekomendasi (pengguna): http://127.0.0.1:5500/app.html
- Kirim info beasiswa (screenshot): http://127.0.0.1:5500/submit-scholarship.html
- Admin dashboard: http://127.0.0.1:5500/admin.html
- Admin · pengguna: http://127.0.0.1:5500/admin-users.html
- Admin · tambah beasiswa: http://127.0.0.1:5500/admin-new-scholarship.html
- Admin · kelola beasiswa: http://127.0.0.1:5500/admin-scholarships.html
- API: http://127.0.0.1:8000/api — dokumentasi: http://127.0.0.1:8000/docs

Jika database lama dibuat sebelum fitur login ada, hapus `backend/app.db` lalu jalankan seed ulang
(kolom `users.password_hash` dan tabel `auth_sessions` tidak dibuat otomatis pada file lama).

Jangan membuka `index.html` lewat `file://`; `fetch()` dan CORS memerlukan server statis.

## Konfigurasi AI

| Mode | Perilaku |
|---|---|
| `AI_PROVIDER=auto` (default) | LLM bila `AI_API_BASE_URL`, `AI_API_KEY`, `AI_MODEL` lengkap; selain itu mock |
| `AI_PROVIDER=llm` | Paksa LLM; bila gagal/no config, fallback ke mock hanya jika `AI_FALLBACK_ENABLED=true` |
| `AI_PROVIDER=mock` | Selalu mock, tidak ada request jaringan |

Setiap hasil AI membawa `provider_mode` (`llm` / `mock` / `mock_fallback`), `provider_name`, `model`,
dan `fallback_reason`. UI menampilkan `LLM aktif`, `Simulasi AI`, atau
`LLM gagal — menggunakan simulasi`. Mock tidak pernah melewati validasi Pydantic, validasi slug
Master Tag, atau persetujuan admin.

## Login dan sesi demo

| Akun | Kata sandi | Peran |
|---|---|---|
| `demo-student` | `student123` | Pengguna |
| `demo-admin` | `admin123` | Admin |

- Halaman awal (`index.html`) adalah landing page; pengguna memilih masuk sebagai Pengguna atau Admin.
- Tidak ada lagi tombol/tab pengalih Pengguna–Admin di dalam aplikasi: peran ditentukan oleh akun
  yang dipakai saat login, dan setiap halaman memeriksa perannya sendiri
  (`profile.html`/`app.html` untuk pengguna, `admin.html` untuk admin).
- Alur pengguna: login → `profile.html` (isi deskripsi → analisis → kirim) → otomatis diarahkan ke
  `app.html` yang menampilkan rekomendasi. Membuka `profile.html` lagi setelah mengirim akan
  mengarahkan balik ke `app.html`.
- Login (`POST /api/auth/login`) menerbitkan token opaque; server hanya menyimpan SHA-256 token
  pada tabel `auth_sessions` beserta masa berlaku (`SESSION_TTL_MINUTES`, default 480 menit).
- Frontend menyimpan token di `sessionStorage` dan mengirim `Authorization: Bearer <token>`.
  Membuka `app.html` tanpa sesi valid akan mengarahkan kembali ke landing page.
- `POST /api/auth/logout` mencabut sesi di server; token yang sudah dicabut/kedaluwarsa ditolak 401.
- Otorisasi: pengguna hanya dapat mengubah profilnya sendiri; admin dapat membaca profil dan
  rekomendasi, tetapi tidak mengubah profil pengguna; endpoint `/api/admin/*` hanya untuk admin.
- Ini **autentikasi demo**, bukan sistem produksi: tanpa SSO/OAuth, tanpa reset kata sandi, tanpa
  verifikasi email. Kata sandi di-hash dengan PBKDF2-SHA256 (200k iterasi) dan tidak pernah
  dikembalikan API.

### Pengiriman tag satu kali

- `POST /api/profile/demo-student/confirm` menyetel `profile_submitted_at` dan hanya boleh berhasil
  sekali per pengguna. Percobaan kedua → `409 already_submitted`.
- Setelah itu `POST .../analyze` juga ditolak (`409 already_submitted`) dan perubahan deskripsi
  ditolak (`409 description_locked`) agar tidak ada jalur pengiriman ulang.
- Nilai fakta (IPK, TOEFL, domisili, dst.) masih dapat diperbaiki lewat `PUT /api/profile/...`
  tanpa memanggil AI — matching dan eligibility dihitung ulang deterministik.

## Alur demo

Landing:
1. Buka `http://127.0.0.1:5500/` → pilih **Masuk sebagai Pengguna** atau **Masuk sebagai Admin**.
2. Halaman login sudah terisi kredensial demo sesuai peran; tekan **Masuk**.

Pengguna:
1. Login → diarahkan ke `profile.html` selama profil belum pernah dikirim.
2. Deskripsi bebas sudah terisi profil demo; tekan **Analisis Profil dengan AI**.
3. Koreksi fakta, lalu **Kirim Profil** (konfirmasi dialog, sekali saja). Tag tidak ditampilkan ke
   pengguna: saran AI diterima otomatis oleh sistem dan hanya dipakai untuk perhitungan.
4. Otomatis diarahkan ke `app.html`: skor relevansi, status kelayakan, gap analysis per persyaratan.
5. Ringkasan profil terkirim ada di halaman terpisah `my-profile.html` (fakta + deskripsi asli).
   Halaman rekomendasi menampilkan **Lagi hot** di atas (deadline terdekat + paling banyak disimpan)
   dan **Baru ditambahkan** di bawah.
6. Tombol **Kirim screenshot** membuka `submit-scholarship.html`: unggah PNG/JPEG/WEBP (maks 5 MB),
   kiriman masuk antrean admin (`user_scholarship_submissions`). Tidak ada OCR — admin membaca
   gambarnya di `admin-scholarships.html` lalu menambah beasiswa lewat menu Tambah beasiswa.
   Ubah TOEFL 450 → 520 di sana lalu **Simpan Fakta & Hitung Ulang** (tidak memanggil AI);
   deskripsi terkunci setelah pengiriman.

Admin (empat halaman terpisah, tanpa pengalih mode):
1. `admin.html` — dashboard: jumlah pengguna, beasiswa per status, ekstraksi, dan antrean verifikasi.
2. `admin-users.html` — tambah pengguna/admin (`POST /api/admin/users`) dan reset kata sandi
   (`POST /api/admin/users/{id}/reset-password`) yang mencabut semua sesi akun tersebut.
3. `admin-new-scholarship.html` — ekstraksi dari URL/teks/PDF atau input manual (tag + persyaratan).
   Setelah tersimpan, diarahkan ke halaman kelola dengan `?id=`.
4. `admin-scholarships.html` — daftar/filter beasiswa, buka detail, edit field, putuskan tag,
   lalu **Setujui** (`POST /api/admin/scholarships/{id}/approve`) atau **Tolak** dengan alasan.
   Keputusan tercatat di riwayat (`scholarship_verifications`).
2. Periksa/edit hasil; setujui atau tolak tag; **Simpan Perubahan**.
3. **Setujui Beasiswa** (status menjadi `verified`, muncul di katalog pengguna) atau **Tolak**
   dengan alasan wajib.

## Asumsi implementasi

- Login sesi demo ditambahkan atas permintaan pengguna meskipun AGENT.md mengecualikan login/SSO
  produksi: implementasinya sengaja minimal (tanpa OAuth, reset kata sandi, atau PII) dan diberi
  label simulasi di UI. Pengalihan peran Pengguna/Admin kini dilakukan lewat login, bukan tab bebas.
- Setiap respons 401 berisi kode `unauthenticated`, `session_expired`, atau `invalid_credentials`
  agar frontend dapat membedakan sesi habis dari salah kata sandi.

- Identifier memakai string UUID agar mudah dipindah ke PostgreSQL; SQLite dipakai untuk demo.
- Tabel `user_scholarship_bookmarks` dibuat tetapi belum punya endpoint (bookmark tidak termasuk
  kriteria demo).
- Beasiswa yang diketik admin disimpan sebagai `extraction_jobs` dengan `source_type="manual"` dan
  `provider_mode="manual"` supaya memakai alur review/approve yang sama; UI menandainya
  "Input manual", bukan "Simulasi AI".
- Setiap beasiswa `pending_verification` selalu memiliki job review (termasuk data seed), agar admin
  dapat membuka dan menyetujuinya.
- Verifikasi sekarang berbasis beasiswa (`/api/admin/scholarships/{id}/approve|reject`), sehingga
  record tanpa job ekstraksi pun tetap bisa dikelola; endpoint ekstraksi mendelegasikan ke fungsi
  yang sama.
- Akun demo baru dibuat admin tetap memakai PBKDF2; reset kata sandi mencabut sesi lama dan dapat
  menghasilkan kata sandi sementara yang hanya ditampilkan sekali.
- `explanation` rekomendasi dibangun deterministik dari hasil backend; operasi
  `explain_recommendation` tetap tersedia pada kontrak `AIProvider` untuk pemakaian LLM di masa depan.
- Skor relevansi = `bobot tag pengguna yang cocok / total bobot tag yang konteksnya komparabel × 100`.
  Nilai `null` + status `insufficient_preferences` bila tidak ada tag pembanding.
- Tag adalah detail internal: halaman pengguna (`profile.html`, `my-profile.html`, `app.html`) tidak
  menampilkan slug/nama tag sama sekali. Saat profil dikirim tanpa daftar tag, backend mengonfirmasi
  saran AI secara otomatis (menghormati penolakan yang tercatat) agar matching tetap berjalan.
  Admin tetap melihat dan menyetujui tag beasiswa di `admin.html`.
- Persyaratan berbasis tag dinilai `met` bila tag terkonfirmasi (atau turunannya), selain itu
  `unknown` — sistem tidak menyimpulkan `not_met` dari ketiadaan tag.
- `application_status` dihitung dari tanggal; `verified` tidak berarti pendaftaran dibuka.
- PDF hasil scan ditolak dengan pesan jelas (OCR di luar cakupan).

## Pengujian

```bash
cd backend && .venv/bin/python -m pytest -q
```

Mencakup ekstraksi fakta eksplisit, validasi slug Master Tag, konfirmasi sebelum pemakaian,
penolakan tag, konteks matching, anti hitung ganda, operator numerik, kelompok AND/OR,
persyaratan opsional, status kelayakan, alur admin (approve/reject), dan perilaku provider/fallback.
