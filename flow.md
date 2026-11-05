# flow.md — Flowchart Backend

Diagram Mermaid untuk alur backend BeasiswaMatch. Semua endpoint di bawah prefix `/api`.
Salin blok `mermaid` ke penampil Mermaid (GitHub, VS Code, mermaid.live).

> **Cara melihat:** setiap diagram berada di dalam blok berpagar `mermaid`.
> Render langsung di GitHub/VS Code, atau pakai file satu-diagram-per-file di `docs/flows/`
> (mis. `docs/flows/01-peta-sistem.mmd`). Jangan menempelkan seluruh dokumen ini ke mermaid.live —
> penampil itu hanya menerima satu diagram, sehinbgga judul dan paragraf di atas memicu
> `UnknownDiagramError`.


---

## 1. Peta sistem

```mermaid
flowchart LR
  B["Browser :5500"] -->|"fetch + Bearer token"| F["FastAPI :8000"]
  F --> R["Router /api"]
  R --> D["Dependency auth & role"]
  D --> S["Service layer"]
  S --> DB[("SQLite app.db")]
  S --> AI["AIProvider"]
  AI --> L["openai_compatible (DeepSeek)"]
  AI --> M["MockAIProvider"]
```

---

## 2. Pipeline request dan otorisasi

```mermaid
flowchart TD
  A["HTTP request"] --> B{"Origin diizinkan CORS?"}
  B -->|"tidak"| B1["Ditolak browser"]
  B -->|"ya"| C["Router cocok?"]
  C -->|"tidak"| C1["404 not_found"]
  C -->|"ya"| D{"Endpoint publik?"}
  D -->|"ya"| H["Handler"]
  D -->|"tidak"| E{"Header Authorization ada?"}
  E -->|"tidak"| E1["401 unauthenticated"]
  E -->|"ya"| F{"Sesi valid?"}
  F -->|"tidak"| F1["401 unauthenticated"]
  F -->|"kedaluwarsa"| F2["401 session_expired"]
  F -->|"ya"| G{"Role / kepemilikan cukup?"}
  G -->|"tidak"| G1["403 forbidden"]
  G -->|"ya"| H["Handler"]
  H --> I["Service + SQLAlchemy"]
  I --> J{"ServiceError?"}
  J -->|"ya"| J1["JSON detail + code, status sesuai"]
  J -->|"tidak"| K["200/201 JSON"]
```

---

## 3. Login, sesi, logout

```mermaid
sequenceDiagram
  participant U as Browser
  participant A as /api/auth
  participant DB as auth_sessions
  participant S as Service

  U->>A: POST /auth/login dengan kredensial
  A->>S: authenticate()
  S->>DB: cari user + verifikasi PBKDF2
  alt kredensial salah
    S-->>U: 401 invalid_credentials
  else valid
    S->>DB: simpan SHA-256(token), expires_at
    S-->>U: 200 {token, role, expires_at}
  end

  U->>A: GET /auth/session (Bearer)
  A->>DB: lookup token_hash
  alt revoked / expired
    A-->>U: 401
  else aktif
    A-->>U: 200 {user, role, expires_at}
  end

  U->>A: POST /auth/logout (Bearer)
  A->>DB: set revoked_at
  A-->>U: 200 {revoked: true}
```

---

## 4. Onboarding profil (analisis → kirim sekali)

```mermaid
flowchart TD
  A["POST /api/profile/{u}/analyze"] --> B{"Deskripsi kosong atau lebih dari 30000 karakter?"}
  B -->|"ya"| B1["422 empty_description / description_too_long"]
  B -->|"tidak"| C{"profile_submitted_at sudah terisi?"}
  C -->|"ya"| C1["409 already_submitted"]
  C -->|"tidak"| D["Muat Master Tag aktif + alias"]
  D --> E["AIProvider.extract_user_profile()"]
  E --> F["Validasi Pydantic + whitelist slug + context"]
  F --> G["Simpan extracted_facts_json + analysis_id, status analyzed"]
  G --> H["UI hanya menampilkan FAKTA (tag disembunyikan)"]

  H --> I["POST /api/profile/{u}/confirm (tags kosong dari UI)"]
  I --> J{"analysis_id == latest dan belum dikirim?"}
  J -->|"tidak"| J1["409 stale_analysis / already_confirmed"]
  J -->|"ya"| K["Auto-confirm saran AI + tag turunan fakta"]
  K --> L["Tulis fakta terkonfirmasi, set profile_submitted_at"]
  L --> M["302 di frontend ke app.html"]
```

### Cabang fallback AI

```mermaid
flowchart TD
  A["Operasi AI dipanggil"] --> B{"Mode = mock?"}
  B -->|"ya"| M["MockAIProvider (tanpa jaringan)"]
  B -->|"tidak"| C{"Konfigurasi LLM lengkap?"}
  C -->|"tidak"| C1{"Fallback aktif?"}
  C1 -->|"ya"| M2["mock, mode=mock_fallback, reason=missing_config"]
  C1 -->|"tidak"| E1["503 ai_unavailable"]
  C -->|"ya"| D["Request ke LLM (timeout + retry terbatas)"]
  D --> D1{"Sukses & lolos validasi?"}
  D1 -->|"ya"| OK["Hasil, mode=llm"]
  D1 -->|"tidak"| F{"Timeout / HTTP error / JSON invalid / slug asing"}
  F -->|"fallback aktif"| M3["mock, mode=mock_fallback, reason=timeout provider_error invalid_output"]
  F -->|"fallback mati"| E1
```

---

## 5. Rekomendasi, hot, dan recent

```mermaid
flowchart TD
  A["GET /api/recommendations/{u}"] --> B{"u = pemilik atau admin?"}
  B -->|"tidak"| B1["403 forbidden"]
  B -->|"ya"| C["Ambil user_tags confirmed"]
  C --> D["Ambil scholarships verified + scholarship_tags approved"]
  D --> E["Matching Engine"]
  E --> E1["Filter konteks kompatibel"]
  E1 --> E2["Cocokkan tag_id / leluhur-turunan"]
  E2 --> E3["Hindari hitung ganda anak-leluhur"]
  E3 --> E4["skor = bobot cocok / bobot komparabel x 100"]
  D --> F["Eligibility Engine"]
  F --> F1["Evaluasi operator per requirement"]
  F1 --> F2["Gabung grup AND / OR"]
  F2 --> F3["Status: met / not_met / unknown"]
  F3 --> F4["eligible / potentially_eligible / not_eligible"]
  E4 --> G["Rakit entri + penjelasan deterministik"]
  F4 --> G
  G --> H["Urut: status kelayakan, lalu skor turun"]
  H --> I["Hot: open/upcoming, bookmark, deadline, skor"]
  H --> J["Recent: created_at terbaru"]
  I --> K["Response {results, hot, recent, counts, warnings}"]
  J --> K
```

---

## 6. Siklus hidup beasiswa (admin)

```mermaid
stateDiagram-v2
  [*] --> pending_verification : ekstraksi AI selesai / input manual
  pending_verification --> verified : approve - butuh nama dan sumber
  pending_verification --> rejected : reject - wajib alasan
  verified --> rejected : reject - wajib alasan
  rejected --> verified : approve ulang
  verified --> [*] : tampil di katalog pengguna
```

### Dua jalur pembuatan beasiswa

```mermaid
flowchart TD
  subgraph EX["Ekstraksi AI"]
    A1["POST /api/admin/extractions"] --> A2{"Sumber?"}
    A2 -->|"URL"| A3["Fetch + strip HTML"]
    A2 -->|"teks"| A4["Validasi panjang"]
    A2 -->|"PDF"| A5["pypdf; tolak bila tanpa teks"]
    A3 --> A6["AIProvider.extract_scholarship()"]
    A4 --> A6
    A5 --> A6
    A6 --> A7["Buat job + scholarship pending + tag pending + requirements"]
  end

  subgraph MAN["Input manual"]
    B1["POST /api/admin/scholarships"] --> B2{"Tag dikenal & context valid?"}
    B2 -->|"tidak"| B3["422 unknown_tag / invalid context"]
    B2 -->|"ya"| B4["Job manual + scholarship pending + tag/requirements"]
  end

  A7 --> C["Antrean admin /api/admin/scholarships/pending"]
  B4 --> C
  C --> D["GET /api/admin/scholarships/{id}"]
  D --> E["PATCH: field, keputusan tag, requirements"]
  E --> F{"Keputusan"}
  F -->|"approve"| G["verified + tag non-rejected approved + riwayat"]
  F -->|"reject"| H["rejected + alasan + riwayat"]
  G --> I["Katalog pengguna + rekomendasi"]
```

---

## 7. Kiriman screenshot pengguna

```mermaid
flowchart TD
  A["POST /api/submissions (multipart)"] --> B{"Role = student?"}
  B -->|"tidak"| B1["403 forbidden"]
  B -->|"ya"| C{"MIME PNG/JPEG/WEBP dan <= 5 MB?"}
  C -->|"tidak"| C1["422 invalid_image_type / 413 file_too_large"]
  C -->|"ya"| D["Simpan user_scholarship_submissions status=pending"]
  D --> E["Admin: GET /api/admin/submissions?status=pending"]
  E --> F["GET /api/admin/submissions/{id}/image (Bearer admin)"]
  F --> G{"Admin membaca gambar (tanpa OCR)"}
  G -->|"valid"| H["Tambah beasiswa manual di admin-new-scholarship"]
  H --> I["POST .../process {status: processed}"]
  G -->|"tidak"| J["POST .../process {status: rejected, reason}"]
```

---

## 8. Model data (ringkas)

```mermaid
erDiagram
  USERS ||--o| STUDENT_PROFILES : memiliki
  USERS ||--o{ AUTH_SESSIONS : membuka
  USERS ||--o{ USER_TAGS : punya
  USERS ||--o{ USER_SCHOLARSHIP_SUBMISSIONS : mengirim
  USERS ||--o{ USER_SCHOLARSHIP_BOOKMARKS : menyimpan
  TAG_CATEGORIES ||--o{ TAGS : mengelompokkan
  TAGS ||--o{ TAG_ALIASES : memiliki
  TAGS ||--o{ USER_TAGS : dirujuk
  SCHOLARSHIPS ||--o{ SCHOLARSHIP_TAGS : diberi
  TAGS ||--o{ SCHOLARSHIP_TAGS : dirujuk
  SCHOLARSHIPS ||--o{ SCHOLARSHIP_SOURCES : bersumber
  SCHOLARSHIPS ||--o{ SCHOLARSHIP_REQUIREMENT_GROUPS : memiliki
  SCHOLARSHIP_REQUIREMENT_GROUPS ||--o{ SCHOLARSHIP_REQUIREMENTS : berisi
  TAGS ||--o{ SCHOLARSHIP_REQUIREMENTS : syarat_tag
  SCHOLARSHIPS ||--o{ EXTRACTION_JOBS : diekstrak
  SCHOLARSHIPS ||--o{ SCHOLARSHIP_VERIFICATIONS : riwayat
  EXTRACTION_JOBS ||--o{ SCHOLARSHIP_VERIFICATIONS : memicu
```

---

## 9. Reset password pengguna (admin)

```mermaid
flowchart TD
  A["POST /api/admin/users/{id}/reset-password"] --> B{"Admin?"}
  B -->|"tidak"| B1["403 forbidden"]
  B -->|"ya"| C{"Password dikirim?"}
  C -->|"tidak"| D["Generate token acak"]
  C -->|"ya"| E{"Panjang >= 8?"}
  E -->|"tidak"| E1["422 weak_password"]
  D --> F["Hash PBKDF2 + simpan"]
  E -->|"ya"| F
  F --> G["Revoke semua auth_sessions user"]
  G --> H["200 {generated, temporary_password?}"]
```

---

## 10. Bagaimana rekomendasi dimunculkan (end-to-end)

Dari pemicu di UI sampai kartu tampil — termasuk titik di mana profil belum dikirim, dan
mengapa ada tiga kelompok kartu.

```mermaid
flowchart TD
  subgraph TRIG["Pemicu di UI"]
    T1["Selesai Kirim Profil (redirect app.html)"]
    T2["Simpan fakta di my-profile.html"]
    T3["Buka / reload app.html"]
    T4["Tombol Hitung ulang"]
  end

  subgraph FE["Frontend"]
    F0["load(): GET /api/profile/{username}"]
    F0a{"profile.submitted?"}
    FX["redirect profile.html"]
    F2["GET /api/recommendations/{username}"]
    F3["renderRecommendations(payload)"]
    F4["Kartu utama (selain not_eligible)"]
    F5["Section Belum cocok (not_eligible)"]
    F6["Section Lagi hot (paling atas)"]
    F7["Section Baru ditambahkan (paling bawah)"]
  end

  subgraph BE["Backend"]
    B1["require_self_or_admin + sesi"]
    B1x["403 forbidden / 401"]
    B2["Ambil user_tags status confirmed"]
    B3["Ambil scholarships verified + scholarship_tags approved"]
    M1["matching_service.match_tags()"]
    M1a["Filter konteks kompatibel"]
    M1b["Cocokkan tag_id atau leluhur/turunan"]
    M1c["Anti hitung ganda anak-leluhur"]
    M1d["skor = bobot cocok / bobot komparabel x 100"]
    E1["eligibility_service.evaluate()"]
    E1a["Evaluasi operator per requirement"]
    E1b["Gabung grup AND / OR"]
    E1c["eligible / potentially_eligible / not_eligible"]
    A1["build_entry: skor, status, requirements, explanation"]
    S1["Urut: kelayakan lalu skor menurun"]
    H1["hot: open/upcoming, bookmark, deadline, skor"]
    R1["recent: created_at terbaru"]
    P["Response: results, hot, recent, counts, warnings"]
  end

  T1 --> F0
  T2 --> F0
  T3 --> F0
  T4 --> F2

  F0 --> F0a
  F0a -->|"tidak"| FX
  F0a -->|"ya"| F2

  F2 --> B1
  B1 -->|"gagal"| B1x
  B1 -->|"lolos"| B2
  B1 -->|"lolos"| B3

  B2 --> M1
  B3 --> M1
  M1 --> M1a --> M1b --> M1c --> M1d

  B3 --> E1
  E1 --> E1a --> E1b --> E1c

  M1d --> A1
  E1c --> A1
  A1 --> S1
  S1 --> H1 --> P
  S1 --> R1 --> P

  P --> F3
  F3 --> F4
  F3 --> F5
  F3 --> F6
  F3 --> F7
```

Catatan perilaku:

- **Belum pernah kirim profil** → `app.html` tidak menghitung apa pun; langsung redirect ke `profile.html`.
- **Profil terkirim** → kartu utama memuat `eligible` dan `potentially_eligible`; `not_eligible` dipisah
  ke "Belum cocok" agar skor tinggi tidak menyamarkan persyaratan yang gagal.
- **Tombol Hitung ulang** memanggil ulang `GET /api/recommendations/{username}` (bukan `POST
  /api/recommendations/recompute`; endpoint POST itu tersedia untuk pemakaian API langsung).
- **Section hot** dihitung dari seluruh hasil (bukan dari kartu utama), **recent** dari `created_at`;
  keduanya maksimal 3 kartu dan boleh tumpang tindih.
- Skor `null` + "Belum cukup preferensi" muncul bila tidak ada tag pembanding — bukan 0%.
